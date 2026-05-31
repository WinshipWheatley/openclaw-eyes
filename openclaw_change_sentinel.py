"""OpenClaw Change Sentinel v0.

Deterministic drift/change monitor for OpenClaw read-model state. The sentinel
reads existing local read models and optional read-only service status, compares
the current observation to a previous sentinel snapshot when present, and writes
JSON/SQLite/operator summaries.

This module does not call an LM, start services, install timers, push/fetch/pull
Git refs, open browsers/accounts, read workbooks, export PDFs, mutate ledgers,
or mutate production state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_SYSTEM_KNOWLEDGE_ROOT = Path("generated/system_knowledge")

SCHEMA_VERSION = "openclaw_change_sentinel_v0"
READ_MODEL_VERSION = "openclaw_change_sentinel_read_model_v0"
JSON_EXPORT_NAME = "openclaw_change_sentinel.json"
OPERATOR_EXPORT_NAME = "openclaw_change_sentinel_OPERATOR.md"
SQLITE_EXPORT_NAME = "openclaw_change_sentinel.sqlite"
SCHEMA_EXPORT_NAME = "openclaw_change_sentinel_SCHEMA.sql"
SEED_EXPORT_NAME = "openclaw_change_sentinel_SEED.sql"

SERVICE_NAME = "openclaw-request-response.service"
PROPOSED_TIMER_PATH = "~/.config/systemd/user/openclaw-change-sentinel.timer"
PROPOSED_SERVICE_PATH = "~/.config/systemd/user/openclaw-change-sentinel.service"

INPUT_READ_MODELS = {
    "reference_resolver": "openclaw_reference_resolver.json",
    "estate_topology": "openclaw_estate_topology_registry.json",
    "live_arts_bundle": "live_arts_md_invoice_review_bundle.json",
    "capital_hilton_bundle": "invoice_review_bundle.json",
    "sync_health": "sync_health.json",
    "request_response_service_status": "openclaw_request_response_service_status.json",
}

STATUS_VALUES = (
    "NO_MATERIAL_CHANGE",
    "MATERIAL_CHANGE_DETECTED",
    "DRIFT_DETECTED",
    "BRIDGE_STALE",
    "SERVICE_UNSTABLE",
    "REPO_DIRTY",
    "REMOTE_REF_MOVED",
    "WORKFLOW_STATE_CHANGED",
    "ACTION_REQUIRED",
    "UNKNOWN",
)

REQUIRED_SQLITE_TABLES = (
    "sentinel_run",
    "observed_target",
    "observed_change",
    "material_change",
    "recommended_action",
    "chief_queue_candidate",
    "hermes_summary",
)

NO_AUTHORITY_FLAGS = {
    "metadata_only": True,
    "read_model_only": True,
    "sqlite_registry_only": True,
    "deterministic_checks_only": True,
    "lm_called": False,
    "lm_summary_candidate_only": True,
    "services_started": False,
    "services_modified": False,
    "timer_installed": False,
    "timer_started": False,
    "git_fetch_pull_push_performed": False,
    "email_accessed": False,
    "gmail_accessed": False,
    "browser_accessed": False,
    "coupa_accessed": False,
    "workbook_cells_read": False,
    "pdf_generated_or_exported": False,
    "ledger_mutated": False,
    "production_state_mutated": False,
    "chief_launched": False,
}

CHANGE_STATUS_PRIORITY = (
    "SERVICE_UNSTABLE",
    "DRIFT_DETECTED",
    "BRIDGE_STALE",
    "REMOTE_REF_MOVED",
    "REPO_DIRTY",
    "WORKFLOW_STATE_CHANGED",
    "ACTION_REQUIRED",
    "MATERIAL_CHANGE_DETECTED",
)


@dataclass(frozen=True)
class ChangeSentinelExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    sqlite_path: str
    schema_sql_path: str
    seed_sql_path: str
    observed_target_count: int
    observed_change_count: int
    material_change_count: int
    run_status: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _rooted(path: str | Path, *, root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(root) / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _bool(value: bool) -> int:
    return 1 if value else 0


def _require_status(status: str) -> str:
    if status not in STATUS_VALUES:
        raise ValueError(f"unknown change sentinel status: {status}")
    return status


def _fingerprint(payload: Any) -> str:
    digest = hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()
    return "sha256:" + digest


def _read_json_object(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _nested(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _target_row(
    *,
    target_ref: str,
    target_type: str,
    source_path: str,
    observation_status: str,
    observed_value: str,
    observed_payload: dict[str, Any],
    observed_at: str,
    unreachable_reason: str = "",
) -> dict[str, Any]:
    _require_status(observation_status)
    fingerprint_payload = dict(observed_payload)
    fingerprint_payload.pop("observed_at", None)
    return {
        "target_ref": target_ref,
        "target_type": target_type,
        "source_path": source_path,
        "observation_status": observation_status,
        "observed_value": observed_value,
        "fingerprint": _fingerprint(fingerprint_payload),
        "observed_json": stable_json(observed_payload).strip(),
        "unreachable_reason": unreachable_reason,
        "observed_at": observed_at,
    }


def _input_read_models(read_model_root: str | Path) -> dict[str, dict[str, Any]]:
    root = _rooted(read_model_root)
    payloads: dict[str, dict[str, Any]] = {}
    for input_ref, filename in INPUT_READ_MODELS.items():
        payloads[input_ref] = _read_json_object(root / filename)
    return payloads


def _input_presence_targets(
    payloads: dict[str, dict[str, Any]],
    *,
    read_model_root: str | Path,
    observed_at: str,
) -> list[dict[str, Any]]:
    root = _rooted(read_model_root)
    rows: list[dict[str, Any]] = []
    for input_ref, filename in INPUT_READ_MODELS.items():
        path = root / filename
        exists = bool(payloads.get(input_ref))
        observed_payload = {
            "input_ref": input_ref,
            "path": _display_path(path),
            "exists": exists,
            "schema_version": payloads.get(input_ref, {}).get("schema_version", ""),
        }
        rows.append(
            _target_row(
                target_ref=f"input_read_model:{input_ref}",
                target_type="INPUT_READ_MODEL",
                source_path=_display_path(path),
                observation_status="NO_MATERIAL_CHANGE" if exists else "UNKNOWN",
                observed_value="present" if exists else "missing",
                observed_payload=observed_payload,
                observed_at=observed_at,
                unreachable_reason="" if exists else "input read model missing or not JSON",
            )
        )
    return rows


def _reference_resolver_targets(
    payload: dict[str, Any],
    *,
    source_path: str,
    observed_at: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for branch in payload.get("git_branch_refs", []):
        target_ref = str(branch.get("target_ref") or branch.get("repo_ref") or "unknown_git_branch")
        head_payload = {
            "target_ref": target_ref,
            "repo_ref": branch.get("repo_ref", ""),
            "repo_name": branch.get("repo_name", ""),
            "remote_url": branch.get("remote_url", ""),
            "branch": branch.get("branch", ""),
            "current_head_commit": branch.get("current_head_commit", ""),
            "resolution_status": branch.get("resolution_status", ""),
            "remote_status": branch.get("remote_status", ""),
            "resolution_source": branch.get("resolution_source", ""),
        }
        rows.append(
            _target_row(
                target_ref=f"git_branch:{target_ref}",
                target_type="GIT_BRANCH",
                source_path=source_path,
                observation_status="NO_MATERIAL_CHANGE",
                observed_value=str(branch.get("current_head_commit", "")),
                observed_payload=head_payload,
                observed_at=observed_at,
            )
        )
        dirty_payload = {
            "target_ref": target_ref,
            "repo_ref": branch.get("repo_ref", ""),
            "local_path": branch.get("local_path", ""),
            "dirty_status": branch.get("dirty_status", "UNKNOWN"),
            "local_status": branch.get("local_status", ""),
        }
        dirty_status = "REPO_DIRTY" if branch.get("dirty_status") == "DIRTY" else "NO_MATERIAL_CHANGE"
        rows.append(
            _target_row(
                target_ref=f"repo_dirty:{target_ref}",
                target_type="REPO_STATE",
                source_path=source_path,
                observation_status=dirty_status,
                observed_value=str(branch.get("dirty_status", "UNKNOWN")),
                observed_payload=dirty_payload,
                observed_at=observed_at,
            )
        )
        mirror_status = str(branch.get("mac_mirror_status", "UNKNOWN"))
        mirror_payload = {
            "target_ref": target_ref,
            "mac_mirror_path": branch.get("mac_mirror_path", ""),
            "mac_mirror_status": mirror_status,
            "mac_bridge_status": branch.get("mac_bridge_status", ""),
            "mac_bridge_resolution_path": branch.get("mac_bridge_resolution_path", ""),
        }
        rows.append(
            _target_row(
                target_ref=f"mac_mirror:{target_ref}",
                target_type="MAC_HEARTBEAT",
                source_path=source_path,
                observation_status="UNKNOWN" if mirror_status != "REACHABLE" else "NO_MATERIAL_CHANGE",
                observed_value=mirror_status,
                observed_payload=mirror_payload,
                observed_at=observed_at,
                unreachable_reason="" if mirror_status == "REACHABLE" else mirror_status,
            )
        )
    for resolution in payload.get("reference_resolutions", []):
        try:
            resolved_json = json.loads(resolution.get("resolved_json", "{}"))
        except json.JSONDecodeError:
            resolved_json = {}
        if resolved_json.get("target_type") != "READ_MODEL_MIRROR":
            continue
        status = str(resolution.get("resolved_status", "UNKNOWN"))
        if status == "DRIFT":
            observation_status = "DRIFT_DETECTED"
        elif status == "MISSING":
            observation_status = "BRIDGE_STALE"
        else:
            observation_status = "NO_MATERIAL_CHANGE"
        mirror_payload = {
            "target_ref": resolution.get("target_ref", ""),
            "source_path": resolved_json.get("source_path", ""),
            "bridge_path": resolved_json.get("bridge_path", ""),
            "source_exists": resolved_json.get("source_exists", False),
            "bridge_exists": resolved_json.get("bridge_exists", False),
            "hash_match": resolved_json.get("hash_match", False),
            "resolved_status": status,
        }
        rows.append(
            _target_row(
                target_ref=f"read_model_mirror:{resolution.get('target_ref', '')}",
                target_type="READ_MODEL_MIRROR",
                source_path=source_path,
                observation_status=observation_status,
                observed_value=f"{status}:{mirror_payload['hash_match']}:{mirror_payload['bridge_exists']}",
                observed_payload=mirror_payload,
                observed_at=observed_at,
                unreachable_reason=resolution.get("error_message", "") if status == "MISSING" else "",
            )
        )
    return rows


def _estate_targets(
    payload: dict[str, Any],
    *,
    source_path: str,
    observed_at: str,
) -> list[dict[str, Any]]:
    unknowns = [
        item for item in payload.get("known_unknowns", [])
        if item.get("status") in {"UNKNOWN", "MISSING", "PARTIAL"}
    ]
    codex_artifacts = [
        item for item in payload.get("codex_web_artifacts", [])
        if item.get("status") in {"UNREACHABLE", "STALE"}
    ]
    return [
        _target_row(
            target_ref="known_unknowns:unresolved",
            target_type="KNOWN_UNKNOWN",
            source_path=source_path,
            observation_status="ACTION_REQUIRED" if unknowns else "NO_MATERIAL_CHANGE",
            observed_value=str(len(unknowns)),
            observed_payload={
                "unresolved_count": len(unknowns),
                "unknown_ids": [item.get("unknown_id", "") for item in unknowns],
            },
            observed_at=observed_at,
        ),
        _target_row(
            target_ref="codex_web_artifacts:stale_or_unreachable",
            target_type="CODEX_WEB_ARTIFACT",
            source_path=source_path,
            observation_status="ACTION_REQUIRED" if codex_artifacts else "NO_MATERIAL_CHANGE",
            observed_value=str(len(codex_artifacts)),
            observed_payload={
                "artifact_count": len(codex_artifacts),
                "artifact_ids": [item.get("artifact_id", "") for item in codex_artifacts],
                "statuses": {item.get("artifact_id", ""): item.get("status", "") for item in codex_artifacts},
            },
            observed_at=observed_at,
        ),
    ]


def _live_arts_targets(
    payload: dict[str, Any],
    *,
    source_path: str,
    observed_at: str,
) -> list[dict[str, Any]]:
    bundle = payload.get("live_arts_md_bundle", {})
    pdf_package = _nested(bundle, "invoice_artifact", "pdf_export_package", default={}) or {}
    workflow_payload = {
        "client_ref": "live_arts_md",
        "workflow_ref": pdf_package.get("workflow_ref", "live_arts_md_invoice_workflow"),
        "bundle_status": bundle.get("status", ""),
        "candidate_selection_status": _nested(bundle, "candidate_selection_rail", "candidate_selection_status", default=""),
        "invoice_selection_status": _nested(bundle, "invoice_selection", "status", default=""),
        "selected_invoice_ids": _nested(bundle, "candidate_selection_rail", "selected_invoice_ids", default=[]),
        "selected_invoice_summary": _nested(bundle, "candidate_selection_rail", "selected_invoice_summary", default=""),
        "artifact_review_status": _nested(bundle, "invoice_artifact", "artifact_review_status", default=""),
        "attachment_ready": _nested(bundle, "invoice_artifact", "attachment_ready", default=False),
    }
    pdf_payload = {
        "client_ref": "live_arts_md",
        "workflow_ref": pdf_package.get("workflow_ref", "live_arts_md_invoice_workflow"),
        "status": pdf_package.get("status", ""),
        "job_ref": pdf_package.get("job_ref", ""),
        "request_payload_ready": pdf_package.get("request_payload_ready", False),
        "invoice_id": pdf_package.get("invoice_id", ""),
        "selected_sheet_label": pdf_package.get("selected_sheet_label", ""),
        "selected_print_areas": pdf_package.get("selected_print_areas", []),
        "result_intended_use": pdf_package.get("result_intended_use", ""),
    }
    payment_payload = {
        "client_ref": "live_arts_md",
        "workflow_ref": pdf_package.get("workflow_ref", "live_arts_md_invoice_workflow"),
        "payment_watch_status": _nested(
            bundle,
            "developer_end_to_end_card",
            "payment_watch_status",
            default="UNKNOWN",
        ),
    }
    return [
        _target_row(
            target_ref="workflow_state:live_arts_md_invoice_workflow",
            target_type="WORKFLOW_STATE",
            source_path=source_path,
            observation_status="NO_MATERIAL_CHANGE",
            observed_value=_fingerprint(workflow_payload),
            observed_payload=workflow_payload,
            observed_at=observed_at,
        ),
        _target_row(
            target_ref="pdf_export_package:live_arts_md_invoice_workflow",
            target_type="PDF_EXPORT_PACKAGE",
            source_path=source_path,
            observation_status="NO_MATERIAL_CHANGE",
            observed_value=str(pdf_payload.get("status", "")),
            observed_payload=pdf_payload,
            observed_at=observed_at,
        ),
        _target_row(
            target_ref="payment_watch:live_arts_md_invoice_workflow",
            target_type="PAYMENT_WATCH",
            source_path=source_path,
            observation_status="NO_MATERIAL_CHANGE",
            observed_value=str(payment_payload.get("payment_watch_status", "UNKNOWN")),
            observed_payload=payment_payload,
            observed_at=observed_at,
        ),
    ]


def _capital_hilton_targets(
    payload: dict[str, Any],
    *,
    source_path: str,
    observed_at: str,
) -> list[dict[str, Any]]:
    bundle = payload.get("capital_hilton_bundle", {})
    state = _nested(bundle, "state_machine", "state", default={}) or {}
    semantic = bundle.get("semantic_status", {}) if isinstance(bundle.get("semantic_status"), dict) else {}
    workflow_payload = {
        "client_ref": "capital_hilton",
        "workflow_ref": bundle.get("workflow_ref", "capital_hilton_invoice_workflow"),
        "bundle_status": bundle.get("status", ""),
        "invoice_record_selection_status": state.get("invoice_record_selection_status", ""),
        "invoice_period_status": state.get("invoice_period_status", ""),
        "generated_artifact_status": state.get("generated_artifact_status", ""),
        "supplier_portal_proof_status": state.get("supplier_portal_proof_status", ""),
        "recipient_review_status": state.get("recipient_review_status", ""),
        "semantic_status": semantic,
    }
    payment_payload = {
        "client_ref": "capital_hilton",
        "workflow_ref": bundle.get("workflow_ref", "capital_hilton_invoice_workflow"),
        "payment_watch_status": state.get("payment_watch_status")
        or semantic.get("payment_watch_status")
        or "UNKNOWN",
    }
    return [
        _target_row(
            target_ref="workflow_state:capital_hilton_invoice_workflow",
            target_type="WORKFLOW_STATE",
            source_path=source_path,
            observation_status="NO_MATERIAL_CHANGE",
            observed_value=_fingerprint(workflow_payload),
            observed_payload=workflow_payload,
            observed_at=observed_at,
        ),
        _target_row(
            target_ref="payment_watch:capital_hilton_invoice_workflow",
            target_type="PAYMENT_WATCH",
            source_path=source_path,
            observation_status="NO_MATERIAL_CHANGE",
            observed_value=str(payment_payload["payment_watch_status"]),
            observed_payload=payment_payload,
            observed_at=observed_at,
        ),
    ]


def _sync_health_targets(
    payload: dict[str, Any],
    *,
    source_path: str,
    observed_at: str,
) -> list[dict[str, Any]]:
    heartbeat = {
        "last_mac_heartbeat": payload.get("last_mac_heartbeat"),
        "last_mac_completion": payload.get("last_mac_completion"),
        "mirror_status": payload.get("mirror_status"),
        "trust_status": payload.get("trust_status"),
        "sync_lifecycle_state": payload.get("sync_lifecycle_state"),
        "missing_expected": payload.get("missing_expected"),
        "hash_mismatch": payload.get("hash_mismatch"),
    }
    status = "BRIDGE_STALE" if payload.get("trust_status") in {"stale_needs_mac_sync", "stale"} else "NO_MATERIAL_CHANGE"
    return [
        _target_row(
            target_ref="mac_heartbeat:sync_health",
            target_type="MAC_HEARTBEAT",
            source_path=source_path,
            observation_status=status,
            observed_value=str(payload.get("trust_status", "UNKNOWN")),
            observed_payload=heartbeat,
            observed_at=observed_at,
            unreachable_reason="" if payload.get("last_mac_heartbeat") else "Mac heartbeat missing",
        )
    ]


def read_systemd_service_snapshot(
    *,
    service_name: str = SERVICE_NAME,
    timeout_seconds: int = 5,
) -> dict[str, Any]:
    if shutil.which("systemctl") is None:
        return {
            "service_name": service_name,
            "available": False,
            "error": "systemctl not available",
        }
    command = [
        "systemctl",
        "--user",
        "show",
        service_name,
        "--property=ActiveState,SubState,NRestarts,ExecMainStatus,Result",
        "--no-pager",
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return {
            "service_name": service_name,
            "available": False,
            "error": "read-only systemd status query timed out",
        }
    values: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return {
        "service_name": service_name,
        "available": completed.returncode == 0,
        "returncode": completed.returncode,
        "error": completed.stderr.strip(),
        "active_state": values.get("ActiveState", ""),
        "sub_state": values.get("SubState", ""),
        "n_restarts": values.get("NRestarts", ""),
        "exec_main_status": values.get("ExecMainStatus", ""),
        "result": values.get("Result", ""),
    }


def _service_targets(
    systemd_snapshot: dict[str, Any] | None,
    *,
    observed_at: str,
) -> list[dict[str, Any]]:
    snapshot = dict(systemd_snapshot or {})
    if not snapshot:
        snapshot = {"service_name": SERVICE_NAME, "available": False, "error": "service snapshot unavailable"}
    service_name = str(snapshot.get("service_name") or SERVICE_NAME)
    restart_value = str(snapshot.get("n_restarts") or snapshot.get("NRestarts") or "")
    status_payload = {
        "service_name": service_name,
        "available": bool(snapshot.get("available", False)),
        "active_state": snapshot.get("active_state", snapshot.get("ActiveState", "")),
        "sub_state": snapshot.get("sub_state", snapshot.get("SubState", "")),
        "n_restarts": restart_value,
        "exec_main_status": snapshot.get("exec_main_status", snapshot.get("ExecMainStatus", "")),
        "result": snapshot.get("result", snapshot.get("Result", "")),
        "error": snapshot.get("error", ""),
    }
    status = "NO_MATERIAL_CHANGE" if snapshot.get("available") else "UNKNOWN"
    return [
        _target_row(
            target_ref=f"service_status:{service_name}",
            target_type="SERVICE",
            source_path="systemd:user:show",
            observation_status=status,
            observed_value=str(status_payload.get("active_state", "")),
            observed_payload=status_payload,
            observed_at=observed_at,
            unreachable_reason=str(snapshot.get("error", "")) if not snapshot.get("available") else "",
        ),
        _target_row(
            target_ref=f"service_restart_count:{service_name}",
            target_type="SERVICE",
            source_path="systemd:user:show",
            observation_status=status,
            observed_value=restart_value,
            observed_payload=status_payload,
            observed_at=observed_at,
            unreachable_reason=str(snapshot.get("error", "")) if not snapshot.get("available") else "",
        ),
    ]


def collect_observed_targets(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
    systemd_snapshot: dict[str, Any] | None = None,
    include_systemd: bool = True,
) -> list[dict[str, Any]]:
    observed_at = generated_at or utc_now()
    read_root = _rooted(read_model_root)
    payloads = _input_read_models(read_root)
    rows: list[dict[str, Any]] = []
    rows.extend(_input_presence_targets(payloads, read_model_root=read_root, observed_at=observed_at))
    rows.extend(
        _reference_resolver_targets(
            payloads["reference_resolver"],
            source_path=_display_path(read_root / INPUT_READ_MODELS["reference_resolver"]),
            observed_at=observed_at,
        )
    )
    rows.extend(
        _estate_targets(
            payloads["estate_topology"],
            source_path=_display_path(read_root / INPUT_READ_MODELS["estate_topology"]),
            observed_at=observed_at,
        )
    )
    rows.extend(
        _live_arts_targets(
            payloads["live_arts_bundle"],
            source_path=_display_path(read_root / INPUT_READ_MODELS["live_arts_bundle"]),
            observed_at=observed_at,
        )
    )
    rows.extend(
        _capital_hilton_targets(
            payloads["capital_hilton_bundle"],
            source_path=_display_path(read_root / INPUT_READ_MODELS["capital_hilton_bundle"]),
            observed_at=observed_at,
        )
    )
    if payloads["sync_health"]:
        rows.extend(
            _sync_health_targets(
                payloads["sync_health"],
                source_path=_display_path(read_root / INPUT_READ_MODELS["sync_health"]),
                observed_at=observed_at,
            )
        )
    if include_systemd:
        snapshot = systemd_snapshot if systemd_snapshot is not None else read_systemd_service_snapshot()
        rows.extend(_service_targets(snapshot, observed_at=observed_at))
    return rows


def _previous_targets(previous_snapshot: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not previous_snapshot:
        return {}
    return {
        str(row.get("target_ref", "")): dict(row)
        for row in previous_snapshot.get("observed_targets", [])
        if row.get("target_ref")
    }


def _change_status(current: dict[str, Any], previous: dict[str, Any]) -> str:
    target_type = current.get("target_type", "")
    target_ref = current.get("target_ref", "")
    if target_type == "GIT_BRANCH":
        return "REMOTE_REF_MOVED"
    if target_type == "REPO_STATE" and current.get("observed_value") == "DIRTY":
        return "REPO_DIRTY"
    if target_type == "READ_MODEL_MIRROR":
        if current.get("observation_status") == "DRIFT_DETECTED":
            return "DRIFT_DETECTED"
        if current.get("observation_status") == "BRIDGE_STALE":
            return "BRIDGE_STALE"
    if target_type == "SERVICE" and target_ref.startswith("service_restart_count:"):
        try:
            before = int(previous.get("observed_value") or 0)
            after = int(current.get("observed_value") or 0)
        except ValueError:
            return "UNKNOWN"
        if after > before:
            return "SERVICE_UNSTABLE"
    if target_type in {"WORKFLOW_STATE", "PDF_EXPORT_PACKAGE", "PAYMENT_WATCH"}:
        return "WORKFLOW_STATE_CHANGED"
    if target_type in {"KNOWN_UNKNOWN", "CODEX_WEB_ARTIFACT"}:
        try:
            before = int(previous.get("observed_value") or 0)
            after = int(current.get("observed_value") or 0)
        except ValueError:
            return "ACTION_REQUIRED"
        return "ACTION_REQUIRED" if after > before else "MATERIAL_CHANGE_DETECTED"
    if target_type == "MAC_HEARTBEAT":
        return "BRIDGE_STALE"
    return "MATERIAL_CHANGE_DETECTED"


def _change_row(
    *,
    current: dict[str, Any],
    previous: dict[str, Any],
    detected_at: str,
) -> dict[str, Any]:
    status = _change_status(current, previous)
    target_ref = current["target_ref"]
    return {
        "change_ref": f"change:{target_ref}",
        "target_ref": target_ref,
        "change_status": _require_status(status),
        "before_value": str(previous.get("observed_value", "")),
        "after_value": str(current.get("observed_value", "")),
        "before_fingerprint": str(previous.get("fingerprint", "")),
        "after_fingerprint": str(current.get("fingerprint", "")),
        "reason": f"{target_ref} changed from {previous.get('observed_value', '')!r} to {current.get('observed_value', '')!r}.",
        "detected_at": detected_at,
    }


def _ignore_non_material_fingerprint_change(
    current: dict[str, Any],
    previous: dict[str, Any],
) -> bool:
    target_type = current.get("target_type", "")
    if target_type == "SERVICE" and current.get("observation_status") == "UNKNOWN":
        return True
    if (
        target_type == "MAC_HEARTBEAT"
        and current.get("observed_value") == previous.get("observed_value")
        and current.get("observation_status") == previous.get("observation_status")
    ):
        return True
    return False


def compare_observations(
    current_targets: list[dict[str, Any]],
    previous_snapshot: dict[str, Any] | None,
    *,
    detected_at: str,
) -> list[dict[str, Any]]:
    previous_by_ref = _previous_targets(previous_snapshot)
    if not previous_by_ref:
        return []
    changes: list[dict[str, Any]] = []
    for current in current_targets:
        previous = previous_by_ref.get(current["target_ref"])
        if previous is None:
            continue
        if previous.get("fingerprint") != current.get("fingerprint"):
            if _ignore_non_material_fingerprint_change(current, previous):
                continue
            changes.append(_change_row(current=current, previous=previous, detected_at=detected_at))
    return changes


def _run_status(changes: list[dict[str, Any]]) -> str:
    if not changes:
        return "NO_MATERIAL_CHANGE"
    statuses = {change["change_status"] for change in changes}
    for status in CHANGE_STATUS_PRIORITY:
        if status in statuses:
            return status
    return "MATERIAL_CHANGE_DETECTED"


def _material_change_rows(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for change in changes:
        status = change["change_status"]
        severity = "HIGH" if status in {"SERVICE_UNSTABLE", "DRIFT_DETECTED"} else "MEDIUM"
        rows.append(
            {
                "material_ref": f"material:{change['target_ref']}",
                "change_ref": change["change_ref"],
                "material_status": status,
                "severity": severity,
                "operator_summary": change["reason"],
                "action_required": status
                in {
                    "SERVICE_UNSTABLE",
                    "DRIFT_DETECTED",
                    "BRIDGE_STALE",
                    "REPO_DIRTY",
                    "REMOTE_REF_MOVED",
                    "ACTION_REQUIRED",
                },
                "can_wait": status not in {"SERVICE_UNSTABLE", "DRIFT_DETECTED"},
            }
        )
    return rows


def _recommended_action_for_material(material: dict[str, Any]) -> dict[str, Any]:
    status = material["material_status"]
    if status == "SERVICE_UNSTABLE":
        title = "Inspect request-response service restart increase"
        validation = "systemctl --user show openclaw-request-response.service --property=NRestarts,ActiveState,SubState"
    elif status == "REMOTE_REF_MOVED":
        title = "Review moved remote branch ref and rerun dependent exports"
        validation = "python3 scripts/export_openclaw_reference_resolver.py --format summary"
    elif status == "REPO_DIRTY":
        title = "Review dirty working copy before relying on generated state"
        validation = "git status --short"
    elif status in {"DRIFT_DETECTED", "BRIDGE_STALE"}:
        title = "Review source/bridge read-model drift"
        validation = "python3 scripts/export_openclaw_reference_resolver.py --format summary"
    elif status == "WORKFLOW_STATE_CHANGED":
        title = "Review workflow read-model change"
        validation = "python3 scripts/export_openclaw_change_sentinel.py --format operator"
    else:
        title = "Review action-required sentinel change"
        validation = "python3 scripts/export_openclaw_change_sentinel.py --format summary"
    return {
        "action_ref": f"action:{material['material_ref']}",
        "material_ref": material["material_ref"],
        "action_title": title,
        "status": "ACTION_REQUIRED" if material["action_required"] else "NO_MATERIAL_CHANGE",
        "reason": material["operator_summary"],
        "can_wait": material["can_wait"],
        "validation_command": validation,
        "forbidden_actions_json": stable_json(
            [
                "Do not launch Chief.",
                "Do not start services.",
                "Do not push.",
                "Do not access email, Gmail, browser, Coupa, workbook, PDF, ledger, or production systems.",
            ]
        ).strip(),
    }


def _chief_candidate_for_material(material: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_ref": f"chief:{material['material_ref']}",
        "material_ref": material["material_ref"],
        "task_title": action["action_title"],
        "reason": action["reason"],
        "target_repo": "/home/openclaw",
        "recommended_model": "deterministic_or_codex_review_only",
        "urgency": "high" if material["severity"] == "HIGH" else "normal",
        "validation_command": action["validation_command"],
        "forbidden_actions_json": action["forbidden_actions_json"],
        "launch_chief": False,
    }


def _action_rows(material_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    actions = [_recommended_action_for_material(material) for material in material_rows]
    chief_candidates = [
        _chief_candidate_for_material(material, action)
        for material, action in zip(material_rows, actions, strict=True)
        if material["action_required"]
    ]
    return actions, chief_candidates


def _hermes_summary(
    *,
    run_ref: str,
    run_status: str,
    material_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if not material_rows:
        what_changed = "No material change since the previous sentinel snapshot."
        why_it_matters = "OpenClaw can keep using the current generated state."
        what_to_do_next = "No action required; rerun on the next 20-minute cadence or manually when needed."
        action_required = False
        can_wait = True
    else:
        summaries = [row["operator_summary"] for row in material_rows]
        what_changed = " ".join(summaries)
        why_it_matters = "A deterministic target moved, drifted, or became unstable."
        what_to_do_next = "Review the recommended actions before assigning any build or repair work."
        action_required = any(row["action_required"] for row in material_rows)
        can_wait = all(row["can_wait"] for row in material_rows)
    return {
        "summary_ref": "hermes_summary:latest",
        "run_ref": run_ref,
        "what_changed": what_changed,
        "why_it_matters": why_it_matters,
        "what_to_do_next": what_to_do_next,
        "action_required": action_required,
        "can_wait": can_wait,
        "lm_summary_candidate_json": stable_json(
            {
                "lm_call_performed": False,
                "future_use": "A later bounded diff summarizer may read material_changes only.",
                "input_scope": "observed_change and material_change rows from this run",
            }
        ).strip(),
    }


def _load_previous_snapshot(path: str | Path) -> dict[str, Any]:
    return _read_json_object(path)


def build_openclaw_change_sentinel(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    generated_at: str | None = None,
    previous_snapshot: dict[str, Any] | None = None,
    previous_snapshot_path: str | Path | None = None,
    systemd_snapshot: dict[str, Any] | None = None,
    include_systemd: bool = True,
) -> dict[str, Any]:
    generated = generated_at or utc_now()
    if previous_snapshot is None and previous_snapshot_path is not None:
        previous_snapshot = _load_previous_snapshot(previous_snapshot_path)
    observed_rows = collect_observed_targets(
        read_model_root=read_model_root,
        generated_at=generated,
        systemd_snapshot=systemd_snapshot,
        include_systemd=include_systemd,
    )
    changes = compare_observations(observed_rows, previous_snapshot, detected_at=generated)
    material_rows = _material_change_rows(changes)
    action_rows, chief_rows = _action_rows(material_rows)
    run_ref = "openclaw_change_sentinel_run"
    run_status = _run_status(changes)
    hermes_row = _hermes_summary(run_ref=run_ref, run_status=run_status, material_rows=material_rows)
    run_row = {
        "run_ref": run_ref,
        "generated_at": generated,
        "run_status": run_status,
        "baseline_available": bool(_previous_targets(previous_snapshot)),
        "observed_target_count": len(observed_rows),
        "observed_change_count": len(changes),
        "material_change_count": len(material_rows),
        "lm_called": False,
        "timer_installed": False,
        "chief_launched": False,
    }
    return {
        "schema_version": READ_MODEL_VERSION,
        "contract_schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated,
        "purpose": "Deterministically detect OpenClaw drift/change and write read-model state without LM calls.",
        "status_values": list(STATUS_VALUES),
        "required_sqlite_tables": list(REQUIRED_SQLITE_TABLES),
        "input_read_models": dict(INPUT_READ_MODELS),
        "run_status": run_status,
        "observed_target_count": len(observed_rows),
        "observed_change_count": len(changes),
        "material_change_count": len(material_rows),
        "chief_queue_candidate_count": len(chief_rows),
        "sentinel_runs": [run_row],
        "observed_targets": observed_rows,
        "observed_changes": changes,
        "material_changes": material_rows,
        "recommended_actions": action_rows,
        "chief_queue_candidates": chief_rows,
        "hermes_summaries": [hermes_row],
        "hermes_summary": hermes_row,
        "timer_proposal": {
            "install_performed": False,
            "start_performed": False,
            "proposed_user_service_path": PROPOSED_SERVICE_PATH,
            "proposed_user_timer_path": PROPOSED_TIMER_PATH,
            "cadence": "OnBootSec=2min; OnUnitActiveSec=20min",
            "manual_command": "cd /home/openclaw && python3 scripts/export_openclaw_change_sentinel.py --format summary",
        },
        "lm_summary_candidate": {
            "lm_call_performed": False,
            "future_use": "Optional later bounded diff summary only; not called by v0.",
            "input_scope": "material_changes",
        },
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def sqlite_schema_sql() -> str:
    statuses = ", ".join(f"'{status}'" for status in STATUS_VALUES)
    status_check = f"CHECK(run_status IN ({statuses}))"
    change_status_check = f"CHECK(change_status IN ({statuses}))"
    material_status_check = f"CHECK(material_status IN ({statuses}))"
    observation_status_check = f"CHECK(observation_status IN ({statuses}))"
    action_status_check = f"CHECK(status IN ({statuses}))"
    return f"""CREATE TABLE sentinel_run (
    run_ref TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    run_status TEXT NOT NULL {status_check},
    baseline_available INTEGER NOT NULL CHECK(baseline_available IN (0, 1)),
    observed_target_count INTEGER NOT NULL,
    observed_change_count INTEGER NOT NULL,
    material_change_count INTEGER NOT NULL,
    lm_called INTEGER NOT NULL CHECK(lm_called IN (0, 1)),
    timer_installed INTEGER NOT NULL CHECK(timer_installed IN (0, 1)),
    chief_launched INTEGER NOT NULL CHECK(chief_launched IN (0, 1))
);

CREATE TABLE observed_target (
    target_ref TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,
    source_path TEXT NOT NULL,
    observation_status TEXT NOT NULL {observation_status_check},
    observed_value TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    observed_json TEXT NOT NULL,
    unreachable_reason TEXT NOT NULL,
    observed_at TEXT NOT NULL
);

CREATE TABLE observed_change (
    change_ref TEXT PRIMARY KEY,
    target_ref TEXT NOT NULL REFERENCES observed_target(target_ref),
    change_status TEXT NOT NULL {change_status_check},
    before_value TEXT NOT NULL,
    after_value TEXT NOT NULL,
    before_fingerprint TEXT NOT NULL,
    after_fingerprint TEXT NOT NULL,
    reason TEXT NOT NULL,
    detected_at TEXT NOT NULL
);

CREATE TABLE material_change (
    material_ref TEXT PRIMARY KEY,
    change_ref TEXT NOT NULL REFERENCES observed_change(change_ref),
    material_status TEXT NOT NULL {material_status_check},
    severity TEXT NOT NULL,
    operator_summary TEXT NOT NULL,
    action_required INTEGER NOT NULL CHECK(action_required IN (0, 1)),
    can_wait INTEGER NOT NULL CHECK(can_wait IN (0, 1))
);

CREATE TABLE recommended_action (
    action_ref TEXT PRIMARY KEY,
    material_ref TEXT NOT NULL REFERENCES material_change(material_ref),
    action_title TEXT NOT NULL,
    status TEXT NOT NULL {action_status_check},
    reason TEXT NOT NULL,
    can_wait INTEGER NOT NULL CHECK(can_wait IN (0, 1)),
    validation_command TEXT NOT NULL,
    forbidden_actions_json TEXT NOT NULL
);

CREATE TABLE chief_queue_candidate (
    candidate_ref TEXT PRIMARY KEY,
    material_ref TEXT NOT NULL REFERENCES material_change(material_ref),
    task_title TEXT NOT NULL,
    reason TEXT NOT NULL,
    target_repo TEXT NOT NULL,
    recommended_model TEXT NOT NULL,
    urgency TEXT NOT NULL,
    validation_command TEXT NOT NULL,
    forbidden_actions_json TEXT NOT NULL,
    launch_chief INTEGER NOT NULL CHECK(launch_chief IN (0, 1))
);

CREATE TABLE hermes_summary (
    summary_ref TEXT PRIMARY KEY,
    run_ref TEXT NOT NULL REFERENCES sentinel_run(run_ref),
    what_changed TEXT NOT NULL,
    why_it_matters TEXT NOT NULL,
    what_to_do_next TEXT NOT NULL,
    action_required INTEGER NOT NULL CHECK(action_required IN (0, 1)),
    can_wait INTEGER NOT NULL CHECK(can_wait IN (0, 1)),
    lm_summary_candidate_json TEXT NOT NULL
);
"""


def _rows_for_sqlite(read_model: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        "sentinel_run": read_model["sentinel_runs"],
        "observed_target": read_model["observed_targets"],
        "observed_change": read_model["observed_changes"],
        "material_change": [
            {
                **row,
                "action_required": _bool(row["action_required"]),
                "can_wait": _bool(row["can_wait"]),
            }
            for row in read_model["material_changes"]
        ],
        "recommended_action": [
            {**row, "can_wait": _bool(row["can_wait"])}
            for row in read_model["recommended_actions"]
        ],
        "chief_queue_candidate": [
            {**row, "launch_chief": _bool(row["launch_chief"])}
            for row in read_model["chief_queue_candidates"]
        ],
        "hermes_summary": [
            {
                **row,
                "action_required": _bool(row["action_required"]),
                "can_wait": _bool(row["can_wait"]),
            }
            for row in read_model["hermes_summaries"]
        ],
    }


def _sqlite_run_rows(read_model: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            **row,
            "baseline_available": _bool(row["baseline_available"]),
            "lm_called": _bool(row["lm_called"]),
            "timer_installed": _bool(row["timer_installed"]),
            "chief_launched": _bool(row["chief_launched"]),
        }
        for row in read_model["sentinel_runs"]
    ]


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"


def sqlite_seed_sql(read_model: dict[str, Any]) -> str:
    rows_by_table = _rows_for_sqlite(read_model)
    rows_by_table["sentinel_run"] = _sqlite_run_rows(read_model)
    statements: list[str] = []
    for table in REQUIRED_SQLITE_TABLES:
        for row in rows_by_table[table]:
            columns = list(row)
            statements.append(
                f"INSERT INTO {table} ({', '.join(columns)}) "
                f"VALUES ({', '.join(_sql_literal(row[column]) for column in columns)});"
            )
    return "\n".join(statements) + "\n"


def create_sqlite_registry(read_model: dict[str, Any], sqlite_path: str | Path) -> None:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    rows_by_table = _rows_for_sqlite(read_model)
    rows_by_table["sentinel_run"] = _sqlite_run_rows(read_model)
    connection = sqlite3.connect(path)
    try:
        connection.executescript(sqlite_schema_sql())
        for table in REQUIRED_SQLITE_TABLES:
            for row in rows_by_table[table]:
                columns = list(row)
                placeholders = ", ".join("?" for _ in columns)
                connection.execute(
                    f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                    [row[column] for column in columns],
                )
        connection.commit()
    finally:
        connection.close()


def format_operator_read_model(read_model: dict[str, Any]) -> str:
    lines = [
        "# OpenClaw Change Sentinel",
        "",
        "Summary:",
        f"- Status: `{read_model['run_status']}`.",
        f"- Observed targets: {read_model['observed_target_count']}.",
        f"- Material changes: {read_model['material_change_count']}.",
        f"- Chief queue candidates: {read_model['chief_queue_candidate_count']} (not launched).",
        f"- LM called: `{read_model['lm_called']}`.",
        "",
        "Hermes Summary:",
        f"- What changed: {read_model['hermes_summary']['what_changed']}",
        f"- Why it matters: {read_model['hermes_summary']['why_it_matters']}",
        f"- Next: {read_model['hermes_summary']['what_to_do_next']}",
        "",
        "Observed Targets:",
    ]
    for target in read_model["observed_targets"]:
        lines.append(
            f"- `{target['target_ref']}` `{target['target_type']}` -> `{target['observation_status']}` `{target['observed_value']}`."
        )
    if read_model["material_changes"]:
        lines.extend(["", "Material Changes:"])
        for material in read_model["material_changes"]:
            lines.append(f"- `{material['material_status']}`: {material['operator_summary']}")
    lines.extend(
        [
            "",
            "Timer Proposal:",
            f"- Proposed timer path: `{read_model['timer_proposal']['proposed_user_timer_path']}`.",
            f"- Cadence: {read_model['timer_proposal']['cadence']}.",
            f"- Manual run: `{read_model['timer_proposal']['manual_command']}`.",
            "- Timer was not installed or started by this export.",
            "",
            "Boundary:",
            "- Deterministic read-model/status inspection only.",
            "- No LM, Chief launch, service start, timer install, push, browser, email, Coupa, workbook, PDF, ledger, or production mutation.",
            "",
        ]
    )
    return "\n".join(lines)


def export_openclaw_change_sentinel(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    system_knowledge_root: str | Path = DEFAULT_SYSTEM_KNOWLEDGE_ROOT,
    generated_at: str | None = None,
    previous_snapshot: dict[str, Any] | None = None,
    systemd_snapshot: dict[str, Any] | None = None,
    include_systemd: bool = True,
) -> ChangeSentinelExportResult:
    read_root = _rooted(read_model_root)
    system_root = _rooted(system_knowledge_root)
    read_root.mkdir(parents=True, exist_ok=True)
    system_root.mkdir(parents=True, exist_ok=True)
    json_path = read_root / JSON_EXPORT_NAME
    previous_path = json_path if json_path.exists() else None
    if previous_snapshot is None and previous_path is not None:
        previous_snapshot = _load_previous_snapshot(previous_path)
    read_model = build_openclaw_change_sentinel(
        read_model_root=read_root,
        generated_at=generated_at,
        previous_snapshot=previous_snapshot,
        systemd_snapshot=systemd_snapshot,
        include_systemd=include_systemd,
    )
    operator_path = read_root / OPERATOR_EXPORT_NAME
    sqlite_path = system_root / SQLITE_EXPORT_NAME
    schema_path = system_root / SCHEMA_EXPORT_NAME
    seed_path = system_root / SEED_EXPORT_NAME
    json_path.write_text(stable_json(read_model), encoding="utf-8")
    operator_path.write_text(format_operator_read_model(read_model), encoding="utf-8")
    schema_path.write_text(sqlite_schema_sql(), encoding="utf-8")
    seed_path.write_text(sqlite_seed_sql(read_model), encoding="utf-8")
    create_sqlite_registry(read_model, sqlite_path)
    return ChangeSentinelExportResult(
        schema_version=READ_MODEL_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        sqlite_path=_display_path(sqlite_path),
        schema_sql_path=_display_path(schema_path),
        seed_sql_path=_display_path(seed_path),
        observed_target_count=read_model["observed_target_count"],
        observed_change_count=read_model["observed_change_count"],
        material_change_count=read_model["material_change_count"],
        run_status=read_model["run_status"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export OpenClaw change sentinel read-model.")
    parser.add_argument("--read-model-root", default=str(DEFAULT_READ_MODEL_ROOT))
    parser.add_argument("--system-knowledge-root", default=str(DEFAULT_SYSTEM_KNOWLEDGE_ROOT))
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    parser.add_argument(
        "--no-systemd",
        action="store_true",
        help="Skip read-only systemd service status observation.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_openclaw_change_sentinel(
        read_model_root=args.read_model_root,
        system_knowledge_root=args.system_knowledge_root,
        include_systemd=not args.no_systemd,
    )
    if args.format == "json":
        payload = json.loads(_rooted(result.json_path).read_text(encoding="utf-8"))
        print(stable_json(payload), end="")
    elif args.format == "operator":
        print(_rooted(result.operator_path).read_text(encoding="utf-8"), end="")
    else:
        print(f"OpenClaw Change Sentinel: `{result.schema_version}`")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
        print(f"- SQLite: `{result.sqlite_path}`")
        print(f"- Status: {result.run_status}")
        print(f"- Observed targets: {result.observed_target_count}")
        print(f"- Observed changes: {result.observed_change_count}")
        print(f"- Material changes: {result.material_change_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Bridge Trust / Sync Truth read-model v0.

This companion read-model separates PC canonical read-model truth from Mac
local readability, shuttle completion proof, mount availability, and sync
marker state. It does not replace ``sync_health``; it uses sync_health as the
bounded proof source and adds operator-facing truth-state classification.

It does not run sync, remount shares, delete files, access credentials, call
models, activate agents, inspect raw private content, mutate Mission Control,
or write OpenClaw artifacts to C:.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger, record_receipt


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "bridge_trust_sync_truth_v0"
JSON_EXPORT_NAME = "bridge_trust_sync_truth.json"
OPERATOR_EXPORT_NAME = "bridge_trust_sync_truth_OPERATOR.md"

SYNC_HEALTH_JSON = "generated/read_models/sync_health.json"
SYNC_HEALTH_OPERATOR = "generated/read_models/sync_health_OPERATOR.md"
CHIEF_DIAGNOSTIC_JSON = "generated/read_models/chief_check_engine_diagnostic_package.json"
CHIEF_POSTURE_JSON = "generated/read_models/chief_check_engine_environment_posture.json"

BRIDGE_TRUST_STATES = (
    "trusted_current",
    "local_readback_only",
    "stale_pc_proof",
    "waiting_for_mac",
    "bridge_mount_missing",
    "blocked",
    "unknown",
)

SHUTTLE_MOUNT_STATUSES = ("available", "missing", "unknown")
SHUTTLE_COMPLETION_STATUSES = ("current", "stale", "missing", "unknown")
LOCAL_READBACK_STATUSES = ("current", "partial", "unknown")

OPERATOR_CONTEXT = {
    "mount_status": "missing",
    "mount_status_basis": "operator_reported",
    "expected_mac_mount": "/Volumes/openclaw_e",
    "expected_windows_source": "E:\\openclaw / WSL /mnt/e/openclaw",
    "pc_canonical_expected_recent": 196,
    "pc_observed_mac_proof_recent": 192,
    "mac_local_mirror_may_have_newer_files": True,
    "full_shuttle_completion_proof": "incomplete",
}

NO_AUTHORITY_FLAGS = {
    "read_model_only": True,
    "metadata_only": True,
    "sync_truth_split_only": True,
    "sqlite_receipt_metadata_only": True,
    "c_drive_write_allowed": False,
    "c_drive_artifact_written": False,
    "delete_authority_added": False,
    "cleanup_authority_added": False,
    "remount_authority_added": False,
    "credential_or_oauth_accessed": False,
    "credential_storage_added": False,
    "raw_private_content_inspected": False,
    "raw_logs_stored": False,
    "raw_file_bodies_stored": False,
    "broad_temp_listing_stored": False,
    "model_calls_made": False,
    "lm_called": False,
    "agents_activated": False,
    "browser_accessed": False,
    "gmail_calendar_coupa_accessed": False,
    "telegram_send_triggered": False,
    "send_or_submit_authority_added": False,
    "approval_authority_added": False,
    "backend_repair_authority_added": False,
    "execution_authority_added": False,
    "runtime_authority_added": False,
    "mission_control_app_changed": False,
    "repo_b_filesystem_inspected": False,
    "repo_b_code_executed": False,
}

FORBIDDEN_ACTIONS = (
    "write OpenClaw artifacts to C:",
    "delete files or caches",
    "remount /Volumes/openclaw_e",
    "request, handle, or store credentials",
    "manual-copy generated files as the primary fix",
    "mutate Mission Control app code",
    "run backend repair automation",
    "activate agents or call models",
    "open browser, OAuth, Gmail, calendar, Coupa, Telegram, send, submit, or approval flows",
    "inspect raw private logs, broad temp listings, or raw file bodies",
)


@dataclass(frozen=True)
class BridgeTrustSyncTruthExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    bridge_trust_state: str
    check_engine_should_light: bool
    sqlite_receipt_supported: bool
    c_drive_artifact_written: bool
    runtime_authority_added: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _rooted(path: str | Path, *, repo_root: str | Path = ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _read_json_if_present(path: str | Path, *, repo_root: str | Path = ROOT) -> dict[str, Any]:
    target = _rooted(path, repo_root=repo_root)
    if not target.exists():
        return {}
    payload = json.loads(target.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _hash_payload(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _find_evidence_ref(payload: dict[str, Any], ref_id: str) -> dict[str, Any]:
    for item in payload.get("evidence_references", []):
        if isinstance(item, dict) and item.get("ref_id") == ref_id:
            return item
    return {}


def _local_mac_readback(diagnostic: dict[str, Any], canonical_expected: int | None, pc_observed: int | None) -> dict[str, Any]:
    mac_ref = _find_evidence_ref(diagnostic, "operator_mac_bridge_report")
    fields = mac_ref.get("fields") if isinstance(mac_ref.get("fields"), dict) else {}
    local_count = _int_or_none(fields.get("mac_local_mirror_file_count_after_helper_pull"))
    if local_count is None:
        return {
            "local_mac_manifest_count": None,
            "local_readback_status": "unknown",
            "basis": "operator_reported_may_have_newer_files_no_current_local_count",
            "is_canonical_bridge_proof": False,
            "can_be_used_as_full_trust": False,
        }
    if canonical_expected is not None and local_count >= canonical_expected:
        status = "current"
    elif pc_observed is not None and local_count > pc_observed:
        status = "partial"
    else:
        status = "partial"
    return {
        "local_mac_manifest_count": local_count,
        "local_readback_status": status,
        "basis": "operator_reported_mac_local_helper_pull",
        "is_canonical_bridge_proof": False,
        "can_be_used_as_full_trust": False,
    }


def _shuttle_mount_status(diagnostic: dict[str, Any]) -> dict[str, Any]:
    mac_ref = _find_evidence_ref(diagnostic, "operator_mac_bridge_report")
    fields = mac_ref.get("fields") if isinstance(mac_ref.get("fields"), dict) else {}
    reported_status = str(fields.get("current_mount_status") or OPERATOR_CONTEXT["mount_status"])
    if reported_status in {"missing_on_mac", "missing"}:
        status = "missing"
    elif reported_status in {"available", "mounted"}:
        status = "available"
    else:
        status = "unknown"
    return {
        "shuttle_mount_status": status,
        "basis": "operator_reported",
        "expected_mac_mount": fields.get("expected_mac_mount") or OPERATOR_CONTEXT["expected_mac_mount"],
        "expected_windows_source": fields.get("expected_windows_source") or OPERATOR_CONTEXT["expected_windows_source"],
        "launch_agent_status_label": fields.get("launch_agent_status_label"),
    }


def _shuttle_completion_status(sync_health: dict[str, Any]) -> dict[str, Any]:
    missing = _int_or_none(sync_health.get("missing_expected"))
    mismatched = _int_or_none(sync_health.get("hash_mismatch"))
    completion = sync_health.get("last_mac_completion") if isinstance(sync_health.get("last_mac_completion"), dict) else {}
    if not sync_health:
        status = "unknown"
    elif not completion or not completion.get("status"):
        status = "missing"
    elif (missing and missing > 0) or (mismatched and mismatched > 0):
        status = "stale"
    else:
        status = "current"
    return {
        "shuttle_completion_status": status,
        "basis": "sync_health.last_mac_completion_plus_counts",
        "last_mac_completion": completion,
        "missing_expected": missing,
        "hash_mismatch": mismatched,
    }


def _sync_marker_state(sync_health: dict[str, Any]) -> dict[str, Any]:
    recommended = sync_health.get("recommended_fix") if isinstance(sync_health.get("recommended_fix"), dict) else {}
    return {
        "request_marker_path": recommended.get("request_marker_path"),
        "app_request_marker_path": recommended.get("app_request_marker_path"),
        "recommended_fix_kind": recommended.get("kind"),
        "next_expected_actor": sync_health.get("next_expected_actor"),
        "sync_lifecycle_state": sync_health.get("sync_lifecycle_state"),
        "operator_action_required": bool(sync_health.get("operator_action_required", False)),
        "can_request_fix_from_app": bool(recommended.get("can_request_fix_from_app", False)),
        "basis": "sync_health.recommended_fix",
    }


def _classify_bridge_state(
    *,
    sync_health: dict[str, Any],
    local_readback: dict[str, Any],
    mount: dict[str, Any],
    completion: dict[str, Any],
) -> dict[str, Any]:
    missing = _int_or_none(sync_health.get("missing_expected")) or 0
    mismatched = _int_or_none(sync_health.get("hash_mismatch")) or 0
    lifecycle = str(sync_health.get("sync_lifecycle_state") or "unknown")
    secondary_states: list[str] = []
    if local_readback.get("local_readback_status") in {"current", "partial"}:
        secondary_states.append("local_readback_only")
    if missing > 0 or mismatched > 0 or completion["shuttle_completion_status"] == "stale":
        secondary_states.append("stale_pc_proof")
    if lifecycle == "sync_requested_waiting_for_mac":
        secondary_states.append("waiting_for_mac")

    if not sync_health:
        state = "unknown"
    elif mount["shuttle_mount_status"] == "missing":
        state = "bridge_mount_missing"
    elif missing == 0 and mismatched == 0 and completion["shuttle_completion_status"] == "current":
        state = "trusted_current"
    elif lifecycle == "sync_requested_waiting_for_mac":
        state = "waiting_for_mac"
    elif missing > 0 or mismatched > 0:
        state = "stale_pc_proof"
    elif local_readback.get("local_readback_status") in {"current", "partial"}:
        state = "local_readback_only"
    else:
        state = "blocked" if lifecycle == "actionable_sync_failure" else "unknown"

    check_engine = state in {"bridge_mount_missing", "blocked"} or bool(missing or mismatched)
    return {
        "bridge_trust_state": state,
        "secondary_states": sorted(set(secondary_states)),
        "check_engine_should_light": check_engine,
        "system_condition_not_operator_interrupt": bool(check_engine and not sync_health.get("operator_action_required", False)),
        "operator_action_required": bool(sync_health.get("operator_action_required", False)),
    }


def build_bridge_trust_sync_truth(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    sync_health = _read_json_if_present(SYNC_HEALTH_JSON, repo_root=repo_root)
    diagnostic = _read_json_if_present(CHIEF_DIAGNOSTIC_JSON, repo_root=repo_root)
    posture = _read_json_if_present(CHIEF_POSTURE_JSON, repo_root=repo_root)

    canonical_expected = _int_or_none(sync_health.get("canonical_expected"))
    pc_observed = _int_or_none(sync_health.get("observed"))
    missing_expected = _int_or_none(sync_health.get("missing_expected"))
    local_readback = _local_mac_readback(diagnostic, canonical_expected, pc_observed)
    mount = _shuttle_mount_status(diagnostic)
    completion = _shuttle_completion_status(sync_health)
    marker_state = _sync_marker_state(sync_health)
    classification = _classify_bridge_state(
        sync_health=sync_health,
        local_readback=local_readback,
        mount=mount,
        completion=completion,
    )

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "read_model_id": "bridge_trust_sync_truth",
        "relationship_to_sync_health": {
            "extends_or_replaces": "companion_read_model",
            "sync_health_remains_backward_compatible": True,
            "purpose": "Split bridge trust truth states that sync_health summarizes as lifecycle and mirror posture.",
        },
        "pc_canonical_expected_set": {
            "canonical_expected_count": canonical_expected,
            "basis": "sync_health.canonical_expected",
            "source_path": SYNC_HEALTH_JSON,
        },
        "pc_observed_mac_proof": {
            "pc_observed_mac_count": pc_observed,
            "missing_expected_count": missing_expected,
            "hash_mismatch_count": _int_or_none(sync_health.get("hash_mismatch")),
            "missing_files": sync_health.get("missing_files", []),
            "basis": "sync_health manifest comparison",
            "source_path": SYNC_HEALTH_JSON,
            "is_full_bridge_trust": bool(
                sync_health
                and (missing_expected or 0) == 0
                and (_int_or_none(sync_health.get("hash_mismatch")) or 0) == 0
            ),
        },
        "mac_local_mirror_presence": local_readback,
        "shuttle_mount": mount,
        "shuttle_completion": completion,
        "sync_marker_request_state": marker_state,
        "truth_split": {
            "pc_canonical_truth": "Repo A generated/read_models expected file set.",
            "pc_observed_mac_proof": "Mac manifest/shuttle proof as imported or observed by PC.",
            "mac_local_readback": "Mac-local readable files reported by operator/helper; not full shuttle proof by itself.",
            "shuttle_completion_proof": "Mac completion marker and PC import proof.",
            "mount_availability": "Whether /Volumes/openclaw_e is available to Mac.",
            "operator_action_required": "Only true for actionable failures; routine blocked/stale lifecycle can still light Check Engine.",
        },
        "bridge_trust_state": classification["bridge_trust_state"],
        "secondary_bridge_states": classification["secondary_states"],
        "bridge_trust_state_model": list(BRIDGE_TRUST_STATES),
        "local_readback_status_model": list(LOCAL_READBACK_STATUSES),
        "shuttle_mount_status_model": list(SHUTTLE_MOUNT_STATUSES),
        "shuttle_completion_status_model": list(SHUTTLE_COMPLETION_STATUSES),
        "check_engine_should_light": classification["check_engine_should_light"],
        "operator_action_required": classification["operator_action_required"],
        "system_condition_not_operator_interrupt": classification["system_condition_not_operator_interrupt"],
        "current_classification_explanation": {
            "what_pc_knows": (
                f"PC canonical expected={canonical_expected}, observed Mac proof={pc_observed}, "
                f"missing={missing_expected}, hash_mismatch={sync_health.get('hash_mismatch')}."
            ),
            "what_mac_local_mirror_appears_to_know": (
                "Mac-local helper readback may have newer files, but it is not canonical shuttle proof."
                if local_readback["local_mac_manifest_count"] is None
                else f"Mac-local helper report saw {local_readback['local_mac_manifest_count']} files; this is {local_readback['local_readback_status']} local readback, not full bridge proof."
            ),
            "what_proof_is_missing": [
                "Mac mount availability proof for /Volumes/openclaw_e",
                "current Mac completion marker after the latest expected set",
                "PC import proof matching the latest Mac manifest",
                "all missing expected files mirrored with matching hashes",
            ],
            "why_this_is_check_engine": (
                "Bridge/mirror proof is stale or blocked while the Mac mount is operator-reported missing; this is system/workbench reliability, not domain lane attention."
            ),
            "what_can_be_trusted": [
                "PC canonical expected set count",
                "PC-observed Mac proof count from sync_health",
                "operator-reported Mac mount/mirror facts as operator_reported context",
            ],
            "what_cannot_be_trusted_yet": [
                "Mac-local file presence as full PC-Mac bridge proof",
                "Mirror Current status for the latest expected set",
                "Automatic remount or repair availability",
            ],
        },
        "safe_next_step": (
            "Keep Mission Control in Check Engine detail: show the truth split, wait for normal Mac sync proof, "
            "and ask Winship for manual Mac mount confirmation only if the mount remains unavailable."
        ),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "source_inputs": {
            "sync_health": {
                "path": SYNC_HEALTH_JSON,
                "present": bool(sync_health),
                "generated_at": sync_health.get("generated_at"),
                "trust_status": sync_health.get("trust_status"),
                "display_status": sync_health.get("display_status"),
            },
            "chief_diagnostic_package": {
                "path": CHIEF_DIAGNOSTIC_JSON,
                "present": bool(diagnostic),
                "schema_version": diagnostic.get("schema_version"),
                "check_engine_on": diagnostic.get("check_engine_on"),
            },
            "chief_environment_posture": {
                "path": CHIEF_POSTURE_JSON,
                "present": bool(posture),
                "schema_version": posture.get("schema_version"),
                "check_engine_on": posture.get("check_engine", {}).get("check_engine_on") if posture else None,
            },
            "operator_context": dict(OPERATOR_CONTEXT),
        },
        "sqlite_ledger_receipt_contract": {
            "supported_by_existing_pattern": True,
            "pattern": "business_ops_ledger.record_receipt",
            "receipt_type": "generated_status",
            "authority_status": "generated_status_only",
            "sqlite_meaning": "receipt_record_only",
            "metadata_only": True,
            "raw_logs_stored": False,
            "credentials_stored": False,
            "broad_temp_listing_stored": False,
            "raw_file_bodies_stored": False,
            "runtime_activation_recorded": False,
            "sqlite_schema_changed": False,
            "receipt_writer_function": "record_bridge_trust_sync_truth_receipt",
        },
        "storage_policy": {
            "do_not_write_openclaw_artifacts_to_pc_c_drive": True,
            "allowed_openclaw_artifact_roots": ["/home/openclaw", "/mnt/e/openclaw"],
            "c_drive_read_only_inspection_allowed_for_posture_evidence": True,
            "delete_anything_in_this_lane": False,
            "generated_output_root": "generated/read_models",
        },
        "next_recommended_lane": {
            "lane_name": "Mission Control Bridge Trust Readback v0",
            "goal": "Surface this split so the helm does not treat Mac local readability as full shuttle trust.",
            "non_live": True,
            "operator_action_required_now": False,
        },
        "receipt_hash": "",
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
    }
    payload.update(NO_AUTHORITY_FLAGS)
    payload["receipt_hash"] = _hash_payload(
        {
            "schema_version": payload["schema_version"],
            "pc_canonical_expected_set": payload["pc_canonical_expected_set"],
            "pc_observed_mac_proof": payload["pc_observed_mac_proof"],
            "mac_local_mirror_presence": payload["mac_local_mirror_presence"],
            "shuttle_mount": payload["shuttle_mount"],
            "shuttle_completion": payload["shuttle_completion"],
            "bridge_trust_state": payload["bridge_trust_state"],
            "secondary_bridge_states": payload["secondary_bridge_states"],
            "storage_policy": payload["storage_policy"],
        }
    )
    return payload


def format_bridge_trust_sync_truth(payload: dict[str, Any]) -> str:
    pc = payload["pc_canonical_expected_set"]
    observed = payload["pc_observed_mac_proof"]
    local = payload["mac_local_mirror_presence"]
    mount = payload["shuttle_mount"]
    completion = payload["shuttle_completion"]
    marker = payload["sync_marker_request_state"]
    explanation = payload["current_classification_explanation"]

    lines = [
        "Bridge Trust / Sync Truth v0",
        "",
        "State:",
        f"- Bridge trust state: `{payload['bridge_trust_state']}`",
        f"- Secondary states: `{', '.join(payload['secondary_bridge_states']) or 'none'}`",
        f"- Check Engine should light: `{str(payload['check_engine_should_light']).lower()}`",
        f"- Operator action required: `{str(payload['operator_action_required']).lower()}`",
        "",
        "What PC Knows:",
        f"- canonical_expected_count={pc['canonical_expected_count']}",
        f"- pc_observed_mac_count={observed['pc_observed_mac_count']}",
        f"- missing_expected_count={observed['missing_expected_count']}",
        f"- hash_mismatch_count={observed['hash_mismatch_count']}",
        "",
        "What Mac Local Mirror Appears To Know:",
        f"- local_mac_manifest_count={local['local_mac_manifest_count']}",
        f"- local_readback_status=`{local['local_readback_status']}`",
        f"- full bridge proof: `{str(local['is_canonical_bridge_proof']).lower()}`",
        "",
        "Bridge Proof:",
        f"- shuttle_mount_status=`{mount['shuttle_mount_status']}`",
        f"- shuttle_completion_status=`{completion['shuttle_completion_status']}`",
        f"- sync_lifecycle_state=`{marker['sync_lifecycle_state']}`",
        f"- request marker: `{marker['request_marker_path']}`",
        "",
        "What Proof Is Missing:",
    ]
    for item in explanation["what_proof_is_missing"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "What Can Be Trusted:",
        ]
    )
    for item in explanation["what_can_be_trusted"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "What Cannot Be Trusted Yet:",
        ]
    )
    for item in explanation["what_cannot_be_trusted_yet"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "Why Check Engine:",
            f"- {explanation['why_this_is_check_engine']}",
            "",
            "Safe Next Move:",
            f"- {payload['safe_next_step']}",
            "",
            "Must Not Do:",
        ]
    )
    for action in payload["forbidden_actions"]:
        lines.append(f"- {action}")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Companion read-model only; sync_health remains the low-level mirror proof contract.",
            "- No remount, delete, repair, credential, runtime, model, agent, browser, OAuth, Gmail, calendar, Coupa, Telegram, send, submit, or approval authority.",
            "- No OpenClaw artifacts are written to C:.",
            "",
        ]
    )
    return "\n".join(lines)


def export_bridge_trust_sync_truth(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> BridgeTrustSyncTruthExportResult:
    payload = build_bridge_trust_sync_truth(repo_root=repo_root, generated_at=generated_at)
    out_dir = _rooted(export_root, repo_root=repo_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_bridge_trust_sync_truth(payload), encoding="utf-8")
    return BridgeTrustSyncTruthExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        bridge_trust_state=payload["bridge_trust_state"],
        check_engine_should_light=payload["check_engine_should_light"],
        sqlite_receipt_supported=payload["sqlite_ledger_receipt_contract"]["supported_by_existing_pattern"],
        c_drive_artifact_written=payload["c_drive_artifact_written"],
        runtime_authority_added=payload["runtime_authority_added"],
    )


def _load_existing_receipt_payloads(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    path = Path(db_path or DEFAULT_DB_PATH)
    if not path.exists():
        return []
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                """
SELECT e.ts, p.packet_json_safe
FROM events e
JOIN packets p ON p.event_id = e.event_id
WHERE e.event_type = 'generated_status'
ORDER BY e.ts DESC
LIMIT 500
""".strip()
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return []

    payloads: list[dict[str, Any]] = []
    for ts, packet_json_safe in rows:
        try:
            packet = json.loads(packet_json_safe or "{}")
        except json.JSONDecodeError:
            continue
        packet["_event_ts"] = ts
        payloads.append(packet)
    return payloads


def _find_existing_bridge_truth_receipt(
    *,
    receipt_hash: str,
    commit_hash: str | None,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    for packet in _load_existing_receipt_payloads(db_path):
        payload_json = packet.get("payload_json")
        if not isinstance(payload_json, dict):
            continue
        if payload_json.get("contract_id") != SCHEMA_VERSION:
            continue
        if payload_json.get("receipt_hash") != receipt_hash:
            continue
        if commit_hash and packet.get("commit_hash") != commit_hash:
            continue
        return packet
    return None


def record_bridge_trust_sync_truth_receipt(
    *,
    repo_root: str | Path = ROOT,
    db_path: str | Path | None = None,
    commit_hash: str | None = None,
    generated_at: str | None = None,
    ensure: bool = True,
) -> str:
    """Record a metadata-only receipt for the bridge trust split."""
    payload = build_bridge_trust_sync_truth(repo_root=repo_root, generated_at=generated_at)
    receipt_hash = payload["receipt_hash"]
    if ensure:
        existing = _find_existing_bridge_truth_receipt(
            receipt_hash=receipt_hash,
            commit_hash=commit_hash,
            db_path=db_path,
        )
        if existing:
            return str(existing.get("receipt_id") or existing.get("packet_id") or "")

    init_business_ops_ledger(str(db_path) if db_path else None)
    receipt_payload = {
        "contract_id": SCHEMA_VERSION,
        "receipt_hash": receipt_hash,
        "generated_read_model_paths": [
            f"generated/read_models/{JSON_EXPORT_NAME}",
            f"generated/read_models/{OPERATOR_EXPORT_NAME}",
        ],
        "bridge_trust_state": payload["bridge_trust_state"],
        "secondary_bridge_states": payload["secondary_bridge_states"],
        "check_engine_should_light": payload["check_engine_should_light"],
        "metadata_only": True,
        "raw_logs_stored": False,
        "credentials_stored": False,
        "broad_temp_listing_stored": False,
        "raw_file_bodies_stored": False,
        "c_drive_artifact_written": False,
        "runtime_activation": False,
        "authority_flags": dict(NO_AUTHORITY_FLAGS),
    }
    return record_receipt(
        receipt_type="generated_status",
        payload=receipt_payload,
        commit_hash=commit_hash,
        artifact_type="bridge_trust_sync_truth",
        artifact_status="captured_metadata_only",
        authority_status="generated_status_only",
        runtime_activation=False,
        sqlite_meaning="receipt_record_only",
        source_basis=[
            SYNC_HEALTH_JSON,
            CHIEF_DIAGNOSTIC_JSON,
            "operator_prompt: Bridge Trust / Sync Truth Split v0",
        ],
        actor="bridge_trust_sync_truth_v0",
        created_at=generated_at,
        db_path=str(db_path) if db_path else None,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Bridge Trust / Sync Truth read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repo A root.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Generated read-model export root.")
    parser.add_argument("--format", choices=("json", "operator", "summary"), default="summary")
    parser.add_argument(
        "--record-receipt",
        action="store_true",
        help="Also record a metadata-only generated_status receipt in the existing ledger.",
    )
    parser.add_argument("--db", help="SQLite ledger path. Defaults to the Business Ops ledger.")
    parser.add_argument("--commit-hash", help="Optional commit hash to bind to the metadata receipt.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_bridge_trust_sync_truth(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    receipt_id = ""
    if args.record_receipt:
        receipt_id = record_bridge_trust_sync_truth_receipt(
            repo_root=args.repo_root,
            db_path=args.db,
            commit_hash=args.commit_hash,
            ensure=True,
        )

    root = _rooted(args.export_root, repo_root=args.repo_root)
    if args.format == "json":
        print((root / JSON_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    elif args.format == "operator":
        print((root / OPERATOR_EXPORT_NAME).read_text(encoding="utf-8"), end="")
    else:
        summary = result.__dict__.copy()
        if args.record_receipt:
            summary["sqlite_receipt_id"] = receipt_id
            summary["sqlite_receipt_recorded"] = bool(receipt_id)
        print(stable_json(summary), end="")
    return 0 if result.schema_version == SCHEMA_VERSION and (not args.record_receipt or receipt_id) else 1


__all__ = [
    "BRIDGE_TRUST_STATES",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "build_bridge_trust_sync_truth",
    "export_bridge_trust_sync_truth",
    "format_bridge_trust_sync_truth",
    "record_bridge_trust_sync_truth_receipt",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())

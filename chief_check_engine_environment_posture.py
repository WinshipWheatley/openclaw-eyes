"""Chief check-engine environment posture read-model v0.

This read-model captures system/workbench reliability signals for Mission
Control's Check Engine surface. It is a Chief-owned diagnostic package preview,
not a domain lane and not a repair path.

It does not delete files, remount shares, call models, activate agents, access
credentials, inspect raw private content, mutate the Mac app, send/submit
anything, or grant runtime authority. C: drive references are evidence labels
only; this module writes generated read-model files under Repo A export roots.
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

SCHEMA_VERSION = "chief_check_engine_environment_posture_v0"
JSON_EXPORT_NAME = "chief_check_engine_environment_posture.json"
OPERATOR_EXPORT_NAME = "chief_check_engine_environment_posture_OPERATOR.md"

SIGNAL_STATUSES = ("ok", "warning", "blocked", "unknown")
EVIDENCE_TYPES = ("operator_reported", "observed")

NO_AUTHORITY_FLAGS = {
    "read_model_only": True,
    "metadata_only": True,
    "diagnostic_package_preview_only": True,
    "chief_owned_check_engine_signal_only": True,
    "sqlite_receipt_metadata_only": True,
    "c_drive_write_allowed": False,
    "c_drive_artifact_written": False,
    "delete_authority_added": False,
    "cleanup_authority_added": False,
    "remount_authority_added": False,
    "credential_or_oauth_accessed": False,
    "raw_private_content_inspected": False,
    "raw_logs_stored": False,
    "broad_temp_listing_stored": False,
    "model_calls_made": False,
    "lm_called": False,
    "agents_activated": False,
    "browser_accessed": False,
    "gmail_calendar_coupa_accessed": False,
    "telegram_send_triggered": False,
    "send_or_submit_authority_added": False,
    "approval_authority_added": False,
    "execution_authority_added": False,
    "runtime_authority_added": False,
    "mission_control_app_changed": False,
    "repo_b_filesystem_inspected": False,
    "repo_b_code_executed": False,
}

FORBIDDEN_GLOBAL_ACTIONS = (
    "delete files or caches from this lane",
    "touch swap.vhdx",
    "delete NVIDIA, Ableton, StarCraft, broad Temp, or unknown app caches",
    "write OpenClaw artifacts to C:",
    "remount Mac shares or enter remount credentials",
    "mutate Mission Control app code",
    "activate agents, call models, wire plugins, or run live chats",
    "send or submit messages, approvals, email, Telegram, Gmail, calendar, or Coupa actions",
    "store raw private logs, credentials, broad temp listings, or raw private file bodies",
)

OPERATOR_REPORTED_STORAGE_FACTS = {
    "c_drive_free_before_cleanup": "~94.8 MB free",
    "cleanup_freed_decimal": "~22.99 GB",
    "cleanup_freed_gib": "~21.4 GiB",
    "main_culprit": "C:\\Users\\Open Claw\\AppData\\Local\\Temp\\DiagOutputDir\\RdClientAutoTrace",
    "main_culprit_size": "about 22 GB",
    "main_culprit_file_count": "5,131 ETL trace files",
    "likely_source": "Windows App / Remote Desktop-style Mac-to-PC workflow",
    "not_primary_source": "direct OpenClaw Repo A bloat",
    "recent_openclaw_sync_artifacts": "E: / /mnt/e/openclaw, not C:",
    "small_openclaw_c_paths": {
        "C:\\OpenClaw": "~207M",
        "C:\\OpenClawShared": "~81M",
        "C:\\Users\\Open Claw\\.codex": "~45M",
    },
    "left_untouched": ("swap.vhdx", "NVIDIA caches", "Ableton caches", "StarCraft caches"),
}

OPERATOR_REPORTED_MAC_BRIDGE_FACTS = {
    "expected_mac_mount": "/Volumes/openclaw_e",
    "expected_windows_source": "E:\\openclaw / WSL /mnt/e/openclaw",
    "current_mount_status": "missing_on_mac",
    "launch_agent": "com.openclaw.read-model-sync",
    "launch_agent_reported_state": "loaded_exits_0",
    "launch_agent_status_label": "share_missing",
    "mac_local_mirror_file_count_after_helper_pull": 194,
    "full_shuttle_completion_pc_import_proof": "incomplete",
}

OPERATOR_REPORTED_SYNC_FACTS = {
    "sync_health_trust_status": "sync_requested_waiting_for_mac",
    "canonical_expected": 194,
    "observed": 192,
    "missing_expected": 2,
    "meaning": "full shuttle completion / PC import proof incomplete at the time of operator observation",
}

OPERATOR_REPORTED_WORKBENCH_FACTS = {
    "mac_codex_desktop_work": "slow_and_hard_to_track",
    "moves": "take_a_long_time",
    "window_screenshot_app_launch_validation": "fragile",
    "classification": "system_workbench_reliability_degradation",
}


@dataclass(frozen=True)
class CheckEnginePostureExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    signal_count: int
    check_engine_on: bool
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


def _evidence(
    *,
    evidence_type: str,
    label: str,
    value: Any,
    source_path: str | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    if evidence_type not in EVIDENCE_TYPES:
        raise ValueError(f"unsupported evidence_type: {evidence_type}")
    return {
        "evidence_type": evidence_type,
        "label": label,
        "value": value,
        "source_path": source_path,
        "observed_at": observed_at,
        "raw_body_stored": False,
        "credentials_stored": False,
        "private_content_stored": False,
    }


def _signal(
    *,
    signal_id: str,
    status: str,
    plain_language_meaning: str,
    evidence: list[dict[str, Any]],
    why_it_matters: str,
    safe_next_diagnostic_step: str,
    forbidden_actions: tuple[str, ...],
    lights_check_engine: bool,
) -> dict[str, Any]:
    if status not in SIGNAL_STATUSES:
        raise ValueError(f"unsupported signal status: {status}")
    return {
        "signal_id": signal_id,
        "status": status,
        "what_it_means_plain_language": plain_language_meaning,
        "evidence": evidence,
        "why_it_matters": why_it_matters,
        "owner": "Chief",
        "safe_next_diagnostic_step": safe_next_diagnostic_step,
        "forbidden_actions": list(forbidden_actions),
        "should_light_check_engine": lights_check_engine,
    }


def _sync_status(sync_health: dict[str, Any]) -> str:
    return str(
        sync_health.get("sync_lifecycle_state")
        or sync_health.get("display_status")
        or sync_health.get("trust_status")
        or "unknown"
    )


#: Google access health arrives as an already-exported read-model, never as a
#: live probe from this lane. This module is contractually forbidden from
#: touching credentials or account mechanisms, and reading a health summary
#: somebody else observed keeps that true.
GOOGLE_CREDENTIAL_HEALTH_SOURCE = "google_credential_health.json"

_CREDENTIAL_STATUS_MAP = {
    "GOOGLE_ACCESS_OK": ("ok", False),
    # Blocked, not warning: an armed send that cannot fire is a stop, not a nag.
    "GOOGLE_ACCESS_EXPIRED_OR_REVOKED": ("blocked", True),
    "GOOGLE_ACCESS_NOT_CONFIGURED": ("blocked", True),
    "GOOGLE_ACCESS_DEPS_MISSING": ("warning", True),
    "GOOGLE_ACCESS_UNKNOWN": ("unknown", True),
}


def _credential_posture(credential_health: dict[str, Any]) -> tuple[str, bool, str]:
    """Map an observed Google-access health read-model onto a signal posture.

    An absent or unrecognised read-model is ``unknown`` and lights the lamp. It
    is never ``ok``: "nobody looked" and "all clear" must not render the same,
    which is the whole reason this signal exists.
    """

    if not credential_health:
        return (
            "unknown",
            True,
            "Google access health has not been observed, so nothing can be said about it.",
        )
    status = str(credential_health.get("status") or "")
    posture, lights = _CREDENTIAL_STATUS_MAP.get(status, ("unknown", True))
    if posture == "ok":
        meaning = "Google access answered a live read, so Gmail and Calendar capabilities are usable."
    elif status == "GOOGLE_ACCESS_DEPS_MISSING":
        meaning = (
            "The Google client libraries are absent from the interpreter that ran the check, "
            "so the probe could not reach the account layer."
        )
    else:
        meaning = (
            "Google access is down. Every capability behind the shared authorisation fails "
            "together: inbox reads, calendar reads, and outbound Gmail send."
        )
    return posture, lights, meaning


def _build_signals(
    *, sync_health: dict[str, Any], credential_health: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    generated_at = sync_health.get("generated_at")
    canonical_expected = sync_health.get("canonical_expected")
    observed = sync_health.get("observed")
    missing_expected = sync_health.get("missing_expected")
    sync_status = _sync_status(sync_health)
    sync_missing_files = sync_health.get("missing_files") if isinstance(sync_health.get("missing_files"), list) else []
    credential_health = credential_health or {}
    credential_status, credential_lights, credential_meaning = _credential_posture(credential_health)
    credential_downstream = [
        str(row.get("what") or "")
        for row in (credential_health.get("downstream_at_risk") or ())
        if isinstance(row, dict)
    ]

    return [
        _signal(
            signal_id="google_access_authorisation_health",
            status=credential_status,
            plain_language_meaning=credential_meaning,
            evidence=[
                _evidence(
                    evidence_type="observed",
                    label="google_access_status",
                    value=credential_health.get("status") or "not_observed",
                    source_path=f"generated/read_models/{GOOGLE_CREDENTIAL_HEALTH_SOURCE}",
                    observed_at=credential_health.get("checked_at"),
                ),
                _evidence(
                    evidence_type="observed",
                    label="downstream_at_risk",
                    value=credential_downstream,
                    source_path=f"generated/read_models/{GOOGLE_CREDENTIAL_HEALTH_SOURCE}",
                    observed_at=credential_health.get("checked_at"),
                ),
            ],
            why_it_matters=(
                "One shared authorisation sits under Gmail read, Calendar read, and Gmail send. "
                "When it lapses, an armed monthly auto-send still reports as armed and silently "
                "cannot fire, and inbound client mail stops being watched."
            ),
            safe_next_diagnostic_step=(
                "Chief should surface the observed status and the operator-only re-authorisation "
                "step. Re-authorising is interactive and belongs to the operator; no agent performs it."
            ),
            forbidden_actions=(
                "re-authorise or refresh the authorisation from this lane",
                "read, store, or move any authorisation material",
                "call Gmail, Calendar, or any account mechanism from this read-model",
            ),
            lights_check_engine=credential_lights,
        ),
        _signal(
            signal_id="c_drive_free_space_low",
            status="warning",
            plain_language_meaning=(
                "The PC C: drive recently reached critical free-space pressure before conservative cleanup."
            ),
            evidence=[
                _evidence(
                    evidence_type="operator_reported",
                    label="c_drive_before_cleanup",
                    value=OPERATOR_REPORTED_STORAGE_FACTS["c_drive_free_before_cleanup"],
                ),
                _evidence(
                    evidence_type="operator_reported",
                    label="cleanup_freed",
                    value={
                        "decimal": OPERATOR_REPORTED_STORAGE_FACTS["cleanup_freed_decimal"],
                        "gib": OPERATOR_REPORTED_STORAGE_FACTS["cleanup_freed_gib"],
                    },
                ),
            ],
            why_it_matters=(
                "Low C: free space can make WSL, Desktop, validation, and bridge work unreliable even when Repo A is not the source."
            ),
            safe_next_diagnostic_step=(
                "Chief should keep disk-pressure posture visible and compare future C: free-space readings against the no-C-artifact policy."
            ),
            forbidden_actions=(
                "delete more C: data from this lane",
                "touch swap.vhdx",
                "treat cleaned-up space as proof that the source cannot recur",
            ),
            lights_check_engine=True,
        ),
        _signal(
            signal_id="rd_client_trace_growth",
            status="warning",
            plain_language_meaning=(
                "The main recovered space came from Remote Desktop-style ETL trace growth, not from Repo A generated artifacts."
            ),
            evidence=[
                _evidence(
                    evidence_type="operator_reported",
                    label="rd_client_trace_dir",
                    value={
                        "path": OPERATOR_REPORTED_STORAGE_FACTS["main_culprit"],
                        "size": OPERATOR_REPORTED_STORAGE_FACTS["main_culprit_size"],
                        "file_count": OPERATOR_REPORTED_STORAGE_FACTS["main_culprit_file_count"],
                        "likely_source": OPERATOR_REPORTED_STORAGE_FACTS["likely_source"],
                    },
                )
            ],
            why_it_matters=(
                "A recurring trace source can refill C: without any OpenClaw repo bloat, degrading the workbench again."
            ),
            safe_next_diagnostic_step=(
                "Capture a bounded Chief diagnostic note that tracks this as an external Windows trace-growth clue."
            ),
            forbidden_actions=(
                "delete unknown Windows diagnostic caches",
                "disable Windows services from this lane",
                "store raw ETL logs or broad temp listings",
            ),
            lights_check_engine=True,
        ),
        _signal(
            signal_id="shuttle_mount_missing",
            status="blocked",
            plain_language_meaning=(
                "The expected Mac mount for the Windows E: OpenClaw shuttle is missing, so the normal Mac bridge cannot be treated as complete."
            ),
            evidence=[
                _evidence(
                    evidence_type="operator_reported",
                    label="mac_mount_status",
                    value={
                        "expected_mount": OPERATOR_REPORTED_MAC_BRIDGE_FACTS["expected_mac_mount"],
                        "expected_source": OPERATOR_REPORTED_MAC_BRIDGE_FACTS["expected_windows_source"],
                        "current_status": OPERATOR_REPORTED_MAC_BRIDGE_FACTS["current_mount_status"],
                    },
                ),
                _evidence(
                    evidence_type="operator_reported",
                    label="launch_agent_status",
                    value={
                        "agent": OPERATOR_REPORTED_MAC_BRIDGE_FACTS["launch_agent"],
                        "state": OPERATOR_REPORTED_MAC_BRIDGE_FACTS["launch_agent_reported_state"],
                        "status_label": OPERATOR_REPORTED_MAC_BRIDGE_FACTS["launch_agent_status_label"],
                    },
                ),
            ],
            why_it_matters=(
                "Mission Control can show stale or incomplete mirror state if the Mac share is absent while the agent reports routine exit."
            ),
            safe_next_diagnostic_step=(
                "Chief should assemble mount-status and sync-health proof for operator review without attempting remount."
            ),
            forbidden_actions=(
                "remount the share from this lane",
                "request or store credentials",
                "claim the Mac mirror is current without completion proof",
            ),
            lights_check_engine=True,
        ),
        _signal(
            signal_id="sync_completion_proof_stale",
            status="warning" if sync_health else "unknown",
            plain_language_meaning=(
                "Canonical sync health is not currently proving full Mac mirror completion for the latest expected read-model set."
            ),
            evidence=[
                _evidence(
                    evidence_type="operator_reported",
                    label="operator_reported_sync_health_posture",
                    value=OPERATOR_REPORTED_SYNC_FACTS,
                ),
                _evidence(
                    evidence_type="observed" if sync_health else "operator_reported",
                    label="current_observed_sync_health_posture",
                    value={
                        "sync_lifecycle_state": sync_status,
                        "trust_status": sync_health.get("trust_status"),
                        "canonical_expected": canonical_expected,
                        "observed": observed,
                        "missing_expected": missing_expected,
                        "missing_files": sync_missing_files,
                    },
                    source_path="generated/read_models/sync_health.json",
                    observed_at=generated_at,
                )
            ],
            why_it_matters=(
                "A stale self-report can make the helm look current while new read-model files are still missing from the Mac mirror."
            ),
            safe_next_diagnostic_step=(
                "Keep the sync lifecycle state visible as proof detail and wait for or inspect the normal Mac sync completion path."
            ),
            forbidden_actions=(
                "manually copy generated files as the primary fix",
                "mark Mirror Current from stale proof",
                "run remount or repair automation from this contract",
            ),
            lights_check_engine=bool(sync_health and (sync_health.get("trust_status") != "trusted_current" or missing_expected)),
        ),
        _signal(
            signal_id="mac_local_mirror_ahead_of_pc_proof",
            status="warning",
            plain_language_meaning=(
                "Operator report says the Mac local mirror had 194 files after a helper pull, while PC proof still observed fewer files."
            ),
            evidence=[
                _evidence(
                    evidence_type="operator_reported",
                    label="mac_local_mirror_count_after_helper_pull",
                    value=OPERATOR_REPORTED_MAC_BRIDGE_FACTS["mac_local_mirror_file_count_after_helper_pull"],
                ),
                _evidence(
                    evidence_type="observed" if sync_health else "operator_reported",
                    label="pc_sync_health_count",
                    value={"canonical_expected": canonical_expected, "observed": observed},
                    source_path="generated/read_models/sync_health.json",
                    observed_at=generated_at,
                ),
            ],
            why_it_matters=(
                "Mac-local visibility and PC-side completion proof can diverge; Mission Control should not quietly flatten that into current."
            ),
            safe_next_diagnostic_step=(
                "Chief should compare Mac mirror evidence, PC manifest evidence, and sync completion receipts in a diagnostic package."
            ),
            forbidden_actions=(
                "treat operator memory or local Mac count as canonical proof by itself",
                "overwrite manifests from this lane",
                "manual-copy as the primary fix",
            ),
            lights_check_engine=True,
        ),
        _signal(
            signal_id="codex_mac_latency_or_validation_friction",
            status="warning",
            plain_language_meaning=(
                "Mac Codex/Desktop work is slow and hard to track, making operator validation less reliable."
            ),
            evidence=[
                _evidence(
                    evidence_type="operator_reported",
                    label="mac_workbench_friction",
                    value={
                        "codex_desktop_work": OPERATOR_REPORTED_WORKBENCH_FACTS["mac_codex_desktop_work"],
                        "moves": OPERATOR_REPORTED_WORKBENCH_FACTS["moves"],
                    },
                )
            ],
            why_it_matters=(
                "Workbench latency can turn simple validation into a reliability problem even when code contracts are correct."
            ),
            safe_next_diagnostic_step=(
                "Chief should capture a bounded latency/friction diagnostic package before relying on fragile Mac-side validation."
            ),
            forbidden_actions=(
                "install tooling or change app code from this lane",
                "claim validation passed when operator friction prevented proof",
                "launch live agents to compensate",
            ),
            lights_check_engine=True,
        ),
        _signal(
            signal_id="launch_window_screenshot_fragility",
            status="warning",
            plain_language_meaning=(
                "Window, screenshot, and app-launch validation has been fragile enough to degrade proof gathering."
            ),
            evidence=[
                _evidence(
                    evidence_type="operator_reported",
                    label="validation_fragility",
                    value=OPERATOR_REPORTED_WORKBENCH_FACTS["window_screenshot_app_launch_validation"],
                )
            ],
            why_it_matters=(
                "Mission Control visual readback proof can be unreliable if the validation surface itself is fragile."
            ),
            safe_next_diagnostic_step=(
                "Chief should separate app correctness from workbench validation reliability in the diagnostic package."
            ),
            forbidden_actions=(
                "mutate Mission Control app code as a first response",
                "hide validation gaps behind green status",
                "run browser or screenshot automation from this contract",
            ),
            lights_check_engine=True,
        ),
        _signal(
            signal_id="no_c_drive_write_policy",
            status="ok",
            plain_language_meaning=(
                "OpenClaw artifacts should stay in Repo A and established E: shuttle paths, not on the PC C: drive."
            ),
            evidence=[
                _evidence(
                    evidence_type="operator_reported",
                    label="storage_policy",
                    value={
                        "do_not_write_openclaw_artifacts_to_c_drive": True,
                        "allowed_paths": ("/home/openclaw", "/mnt/e/openclaw"),
                        "recent_sync_artifacts": OPERATOR_REPORTED_STORAGE_FACTS["recent_openclaw_sync_artifacts"],
                        "small_c_openclaw_paths": OPERATOR_REPORTED_STORAGE_FACTS["small_openclaw_c_paths"],
                    },
                )
            ],
            why_it_matters=(
                "The no-C-write rule prevents OpenClaw from contributing to the storage-pressure failure mode."
            ),
            safe_next_diagnostic_step=(
                "Keep C: references as read-only evidence only; generated outputs remain under generated/read_models in Repo A."
            ),
            forbidden_actions=(
                "create caches, temp bundles, exports, generated outputs, or logs on C:",
                "use C: as a fallback for shuttle state",
                "treat C: paths as writable OpenClaw artifact targets",
            ),
            lights_check_engine=False,
        ),
    ]


def _check_engine_summary(signals: list[dict[str, Any]]) -> dict[str, Any]:
    lit = [signal for signal in signals if signal["should_light_check_engine"]]
    blocked = [signal for signal in lit if signal["status"] == "blocked"]
    warning = [signal for signal in lit if signal["status"] == "warning"]
    return {
        "check_engine_on": bool(lit),
        "status": "blocked" if blocked else "warning" if warning else "ok",
        "owner": "Chief",
        "why": [
            signal["what_it_means_plain_language"]
            for signal in lit
        ],
        "degraded": [
            "PC/WSL storage pressure risk",
            "Mac shuttle bridge proof",
            "Mac workbench validation reliability",
        ],
        "domain_lane_issue": False,
        "system_workbench_issue": True,
        "doctrine": {
            "lane_attention": "A domain/workflow needs attention, context, proof, classification, or build-out.",
            "check_engine": (
                "The OpenClaw system/workbench itself is degraded, stale, unsafe, blocked, internally inconsistent, "
                "or failing proof/trust."
            ),
            "chief_diagnostic_package_problem": True,
        },
    }


def _chief_package_preview(signals: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "package_id": "chief_environment_check_engine_diagnostic_package_preview_v0",
        "future_gated": True,
        "dispatchable_now": False,
        "actor_model": {
            "candidate": "unspecified_candidate_not_live",
            "candidate_label_only": True,
            "model_call_allowed": False,
            "unavailable_or_unknown_fails_closed": True,
        },
        "character": "Chief",
        "mission": "Diagnose environment, bridge, and tooling degradation without repair authority.",
        "context_included": [
            "disk pressure summary",
            "Remote Desktop ETL trace-growth clue",
            "Mac shuttle mount status",
            "canonical sync-health proof status",
            "Mac Codex/Desktop latency and validation friction",
        ],
        "context_excluded": [
            "credentials",
            "OAuth tokens",
            "raw private data",
            "raw logs unless explicitly approved",
            "broad Temp listings",
            "private file bodies",
        ],
        "capabilities": [
            "inspect-only diagnostics",
            "read-only posture comparison",
            "metadata-only package preview",
        ],
        "forbidden": list(FORBIDDEN_GLOBAL_ACTIONS),
        "stop_conditions": [
            "produce diagnosis",
            "state safe next step",
            "state required operator action if any",
            "preserve no-C-write and no-live-authority boundaries",
        ],
        "proof_receipt_requirements": [
            "cite generated/read_models/sync_health.json for PC-observed sync posture",
            "label operator reports as operator_reported rather than observed fact",
            "do not store raw logs or credentials",
            "record metadata-only receipt if ledger pattern is used",
        ],
        "signal_ids_included": [signal["signal_id"] for signal in signals],
    }


def build_chief_check_engine_environment_posture(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root)
    generated_at = generated_at or utc_now()
    sync_health = _read_json_if_present(DEFAULT_EXPORT_ROOT / "sync_health.json", repo_root=root)
    credential_health = _read_json_if_present(
        DEFAULT_EXPORT_ROOT / GOOGLE_CREDENTIAL_HEALTH_SOURCE, repo_root=root
    )
    signals = _build_signals(sync_health=sync_health, credential_health=credential_health)
    check_engine = _check_engine_summary(signals)
    package_preview = _chief_package_preview(signals)

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "posture_id": "chief_check_engine_environment_posture",
        "posture_status": "deterministic_check_engine_read_model_only",
        "owner": "Chief",
        "lane_type": "system_workbench_reliability_check_engine",
        "not_a_normal_domain_lane": True,
        "operator_eli5_summary": {
            "is_check_engine_on": "Yes.",
            "why": (
                "The problem is not a music, finance, or app-design lane asking for attention. "
                "The PC/Mac workbench and mirror proof are degraded enough that Chief should package the diagnosis."
            ),
            "what_is_degraded": (
                "C: drive pressure risk, Remote Desktop trace growth, Mac shuttle mount/proof, and Mac validation friction."
            ),
            "what_is_safe_next": (
                "Create or inspect a Chief diagnostic package with read-only evidence and operator-reported context."
            ),
            "what_should_not_be_done": (
                "Do not delete more files, remount shares, enter credentials, run agents/models, mutate the app, or write OpenClaw artifacts to C:."
            ),
        },
        "check_engine": check_engine,
        "signals": signals,
        "signal_count": len(signals),
        "signals_by_status": {
            status: sum(1 for signal in signals if signal["status"] == status)
            for status in SIGNAL_STATUSES
        },
        "signals_that_light_check_engine": [
            signal["signal_id"] for signal in signals if signal["should_light_check_engine"]
        ],
        "safe_next_diagnostic_step": (
            "Chief Check-Engine Diagnostic Packet: compare disk-pressure posture, RD trace-growth clue, "
            "Mac mount status, sync proof, and workbench validation friction without repair authority."
        ),
        "forbidden_actions": list(FORBIDDEN_GLOBAL_ACTIONS),
        "chief_package_preview": package_preview,
        "future_gated": {
            "repair_button": True,
            "delete_cleanup": True,
            "remount": True,
            "credential_entry": True,
            "runtime_execution": True,
            "live_agent": True,
            "model_call": True,
            "app_mutation": True,
            "send_submit_approval": True,
        },
        "storage_policy": {
            "do_not_write_openclaw_artifacts_to_pc_c_drive": True,
            "allowed_openclaw_artifact_roots": ["/home/openclaw", "/mnt/e/openclaw"],
            "c_drive_read_only_inspection_allowed_for_disk_posture": True,
            "delete_anything_in_this_lane": False,
            "generated_output_root": "generated/read_models",
        },
            "source_inputs": {
                "operator_reported_storage_facts": OPERATOR_REPORTED_STORAGE_FACTS,
                "operator_reported_mac_bridge_facts": OPERATOR_REPORTED_MAC_BRIDGE_FACTS,
                "operator_reported_sync_facts": OPERATOR_REPORTED_SYNC_FACTS,
                "operator_reported_workbench_facts": OPERATOR_REPORTED_WORKBENCH_FACTS,
                "observed_google_credential_health_source": {
                    "path": f"generated/read_models/{GOOGLE_CREDENTIAL_HEALTH_SOURCE}",
                    "evidence_type": "observed",
                    "probe_performed_by_this_lane": False,
                    "note": (
                        "Produced by google_credential_health.py. This lane reads the summary "
                        "only and never reaches the account layer itself."
                    ),
                },
                "observed_sync_health_source": {
                "path": "generated/read_models/sync_health.json",
                "present": bool(sync_health),
                "generated_at": sync_health.get("generated_at"),
                "trust_status": sync_health.get("trust_status"),
                "canonical_expected": sync_health.get("canonical_expected"),
                "observed": sync_health.get("observed"),
                "missing_expected": sync_health.get("missing_expected"),
            },
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
            "runtime_activation_recorded": False,
            "sqlite_schema_changed": False,
            "receipt_writer_function": "record_chief_check_engine_environment_posture_receipt",
        },
        "machine_proof": {
            "read_models": [
                {
                    "path": "generated/read_models/sync_health.json",
                    "role": "observed PC/WSL canonical sync posture",
                    "present": bool(sync_health),
                    "body_read": bool(sync_health),
                }
            ],
            "source_files": [
                "chief_check_engine_environment_posture.py",
                "scripts/export_chief_check_engine_environment_posture.py",
            ],
            "generated_outputs": [
                f"generated/read_models/{JSON_EXPORT_NAME}",
                f"generated/read_models/{OPERATOR_EXPORT_NAME}",
            ],
            "proof_limit": "operator reports are preserved as operator_reported and are not promoted to observed truth.",
        },
        "authority_boundary_confirmation": {
            "no_repair_authority_granted": True,
            "no_delete_authority_granted": True,
            "no_remount_authority_granted": True,
            "no_runtime_authority_granted": True,
            "no_model_or_agent_authority_granted": True,
            "no_c_drive_write_authority_granted": True,
        },
        "next_recommended_lane": {
            "lane_name": "Chief Check-Engine Diagnostic Package v0",
            "goal": (
                "Turn this posture into an inspect-only Chief diagnostic package that compares current PC/Mac proof, "
                "without cleanup, remount, credentials, app mutation, or runtime execution."
            ),
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
            "signals": payload["signals"],
            "check_engine": payload["check_engine"],
            "chief_package_preview": payload["chief_package_preview"],
            "storage_policy": payload["storage_policy"],
        }
    )
    return payload


def format_chief_check_engine_environment_posture(payload: dict[str, Any]) -> str:
    check = payload["check_engine"]
    signals = payload["signals"]
    package = payload["chief_package_preview"]

    lines = [
        "Chief Check-Engine Environment Posture v0",
        "",
        "Status:",
        f"- Check Engine: {'ON' if check['check_engine_on'] else 'OFF'}",
        f"- Overall posture: {check['status']}",
        "- Issue type: system/workbench reliability, not a normal domain lane.",
        "",
        "Why:",
    ]
    for reason in check["why"]:
        lines.append(f"- {reason}")

    lines.extend(
        [
            "",
            "Degraded:",
            "- PC/WSL storage pressure risk from recent C: free-space collapse.",
            "- Remote Desktop-style trace growth may recur outside Repo A.",
            "- Mac shuttle/mirror completion proof is stale or incomplete.",
            "- Mac Codex/Desktop validation is slow or fragile.",
            "",
            "Safe Next Step:",
            f"- {payload['safe_next_diagnostic_step']}",
            "",
            "Do Not:",
        ]
    )
    for action in payload["forbidden_actions"]:
        lines.append(f"- {action}")

    lines.extend(
        [
            "",
            "Signals:",
        ]
    )
    for signal in signals:
        light = "lights Check Engine" if signal["should_light_check_engine"] else "does not light Check Engine"
        lines.append(
            f"- {signal['signal_id']}: {signal['status']} - {signal['what_it_means_plain_language']} ({light})."
        )

    lines.extend(
        [
            "",
            "Chief Package Preview:",
            f"- Character: {package['character']}",
            f"- Actor/model: {package['actor_model']['candidate']}",
            f"- Mission: {package['mission']}",
            "- Capabilities: inspect-only/read-only diagnostics.",
            "- Dispatchable now: false.",
            "- Future-gated: true.",
            "",
            "Storage Boundary:",
            "- OpenClaw artifacts must not be written to C:.",
            "- Generated output remains under `generated/read_models/` in Repo A.",
            "- C: references here are evidence labels only, not artifact targets.",
            "",
            "SQLite Evidence Record:",
            "- Existing safe pattern: `business_ops_ledger.record_receipt`.",
            "- Receipt meaning: metadata-only `generated_status`, receipt-record-only, no runtime authority.",
            "- Raw logs, credentials, broad temp listings, and private file bodies are not stored.",
            "",
            "Future-Gated:",
            "- Delete/cleanup, remount, credentials, app mutation, live agents, model calls, sends/submits, and runtime execution.",
            "",
            "Next Lane:",
            f"- {payload['next_recommended_lane']['lane_name']}: {payload['next_recommended_lane']['goal']}",
            "",
        ]
    )
    return "\n".join(lines)


def export_chief_check_engine_environment_posture(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> CheckEnginePostureExportResult:
    payload = build_chief_check_engine_environment_posture(
        repo_root=repo_root,
        generated_at=generated_at,
    )
    out_dir = _rooted(export_root, repo_root=repo_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_chief_check_engine_environment_posture(payload), encoding="utf-8")
    return CheckEnginePostureExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        signal_count=payload["signal_count"],
        check_engine_on=payload["check_engine"]["check_engine_on"],
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


def _find_existing_posture_receipt(
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


def record_chief_check_engine_environment_posture_receipt(
    *,
    repo_root: str | Path = ROOT,
    db_path: str | Path | None = None,
    commit_hash: str | None = None,
    generated_at: str | None = None,
    ensure: bool = True,
) -> str:
    """Record a metadata-only check-engine posture receipt.

    The receipt stores bounded metadata, source labels, signal IDs, posture hash,
    generated paths, and no-authority flags. It stores no raw logs, private file
    bodies, credentials, broad temp listings, cleanup artifacts, or runtime
    activation.
    """
    payload = build_chief_check_engine_environment_posture(
        repo_root=repo_root,
        generated_at=generated_at,
    )
    receipt_hash = payload["receipt_hash"]
    if ensure:
        existing = _find_existing_posture_receipt(
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
        "signal_ids": [signal["signal_id"] for signal in payload["signals"]],
        "check_engine_on": payload["check_engine"]["check_engine_on"],
        "status": payload["check_engine"]["status"],
        "source_labels": [
            "operator_reported_storage_cleanup_summary",
            "operator_reported_mac_bridge_degradation",
            "operator_reported_mac_workbench_friction",
            "observed_generated_read_models_sync_health_json",
        ],
        "metadata_only": True,
        "raw_logs_stored": False,
        "credentials_stored": False,
        "broad_temp_listing_stored": False,
        "raw_private_content_stored": False,
        "c_drive_artifact_written": False,
        "runtime_activation": False,
        "authority_flags": dict(NO_AUTHORITY_FLAGS),
    }
    return record_receipt(
        receipt_type="generated_status",
        payload=receipt_payload,
        commit_hash=commit_hash,
        artifact_type="chief_check_engine_environment_posture",
        artifact_status="captured_metadata_only",
        authority_status="generated_status_only",
        runtime_activation=False,
        sqlite_meaning="receipt_record_only",
        source_basis=receipt_payload["source_labels"],
        actor="chief_check_engine_environment_posture_v0",
        created_at=generated_at,
        db_path=str(db_path) if db_path else None,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Chief check-engine environment posture read-model.")
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
    result = export_chief_check_engine_environment_posture(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    receipt_id = ""
    if args.record_receipt:
        receipt_id = record_chief_check_engine_environment_posture_receipt(
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
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "SIGNAL_STATUSES",
    "build_chief_check_engine_environment_posture",
    "export_chief_check_engine_environment_posture",
    "format_chief_check_engine_environment_posture",
    "record_chief_check_engine_environment_posture_receipt",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())

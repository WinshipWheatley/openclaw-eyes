"""Bridge Trust / Manual Mount Recovery Packet v0.

This read-model/operator packet makes the current Mac bridge blocker explicit:
the Mac cannot complete normal read-model sync while ``/Volumes/openclaw_e`` is
not mounted. The packet is manual-only and inspect-only. It records what
Winship should do and what proof should exist afterward; it does not remount,
delete, repair, handle credentials, run Mac commands, call models, activate
agents, or write OpenClaw artifacts to C:.
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

SCHEMA_VERSION = "bridge_manual_mount_recovery_packet_v0"
JSON_EXPORT_NAME = "bridge_manual_mount_recovery_packet.json"
OPERATOR_EXPORT_NAME = "bridge_manual_mount_recovery_packet_OPERATOR.md"

SYNC_HEALTH_JSON = "generated/read_models/sync_health.json"
BRIDGE_TRUST_JSON = "generated/read_models/bridge_trust_sync_truth.json"
CHIEF_DIAGNOSTIC_JSON = "generated/read_models/chief_check_engine_diagnostic_package.json"

EXPECTED_PATHS = {
    "windows_source": "E:\\openclaw",
    "wsl_source": "/mnt/e/openclaw",
    "mac_mount": "/Volumes/openclaw_e",
    "mac_sync_request_marker": "/Volumes/openclaw_e/shuttle/to_mac/read_model_sync_required.json",
    "wsl_sync_request_marker": "/mnt/e/openclaw/shuttle/to_mac/read_model_sync_required.json",
}

OPERATOR_CHECKPOINT_BEFORE_PACKET = {
    "canonical_expected": 198,
    "observed": 192,
    "missing_expected": 6,
    "hash_mismatch": 0,
    "basis": "operator_prompt_current_fact",
    "meaning": "Recent Repo A backend state after Chief diagnostic package, before this packet and later read-model additions.",
}

NO_AUTHORITY_FLAGS = {
    "read_model_only": True,
    "metadata_only": True,
    "manual_mount_recovery_packet_only": True,
    "inspect_only": True,
    "manual_packet_only": True,
    "sqlite_receipt_metadata_only": True,
    "c_drive_write_allowed": False,
    "c_drive_artifact_written": False,
    "delete_authority_added": False,
    "cleanup_authority_added": False,
    "remount_authority_added": False,
    "auto_remount_authority_added": False,
    "credential_or_oauth_accessed": False,
    "credential_storage_added": False,
    "raw_private_content_inspected": False,
    "raw_logs_stored": False,
    "raw_trace_contents_stored": False,
    "broad_temp_listing_stored": False,
    "raw_file_bodies_stored": False,
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
    "mac_commands_run_from_pc": False,
    "repo_b_filesystem_inspected": False,
    "repo_b_code_executed": False,
}

FORBIDDEN_ACTIONS = (
    "delete anything",
    "perform deletes",
    "remount /Volumes/openclaw_e automatically",
    "handle or store credentials",
    "create auto-remount authority",
    "run Mac commands from PC",
    "write OpenClaw artifacts to C:",
    "manual-copy generated read-model files as the primary fix",
    "mutate Mission Control app code",
    "repair backend services from this packet",
    "activate agents or call models",
    "open browser, OAuth, Gmail, calendar, Coupa, Telegram, send, submit, or approval flows",
    "inspect raw private logs, raw trace contents, broad temp listings, or raw file bodies",
)


@dataclass(frozen=True)
class BridgeManualMountRecoveryPacketExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    packet_id: str
    status: str
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


def _mac_report_fields(diagnostic: dict[str, Any]) -> dict[str, Any]:
    ref = _find_evidence_ref(diagnostic, "operator_mac_bridge_report")
    fields = ref.get("fields") if isinstance(ref.get("fields"), dict) else {}
    return dict(fields)


def _current_sync_health(sync_health: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_expected": _int_or_none(sync_health.get("canonical_expected")),
        "observed": _int_or_none(sync_health.get("observed")),
        "missing_expected": _int_or_none(sync_health.get("missing_expected")),
        "hash_mismatch": _int_or_none(sync_health.get("hash_mismatch")),
        "sync_lifecycle_state": sync_health.get("sync_lifecycle_state"),
        "operator_action_required": bool(sync_health.get("operator_action_required", False)),
        "missing_files": list(sync_health.get("missing_files", []) or []),
        "basis": "observed_generated_read_model" if sync_health else "missing_source_read_model",
        "source_path": SYNC_HEALTH_JSON,
    }


def _mac_fact(*, fact_id: str, summary: str, value: Any, basis: str = "operator_reported") -> dict[str, Any]:
    return {
        "fact_id": fact_id,
        "basis": basis,
        "value": value,
        "summary": summary,
        "promoted_to_canonical_truth": False,
    }


def _observed_mac_facts(diagnostic: dict[str, Any], bridge_truth: dict[str, Any]) -> list[dict[str, Any]]:
    fields = _mac_report_fields(diagnostic)
    local = bridge_truth.get("mac_local_mirror_presence") if isinstance(bridge_truth.get("mac_local_mirror_presence"), dict) else {}
    local_count = _int_or_none(fields.get("mac_local_mirror_file_count_after_helper_pull"))
    if local_count is None:
        local_count = _int_or_none(local.get("local_mac_manifest_count"))
    desktop_manifest_count = _int_or_none(fields.get("desktop_mac_manifest_path_records")) or local_count
    lane_count = _int_or_none(fields.get("nested_lane_spine_local_json_parsed_lane_count"))
    return [
        _mac_fact(
            fact_id="mac_mount_missing",
            value="missing",
            summary="/Volumes/openclaw_e is operator-reported missing on Mac.",
        ),
        _mac_fact(
            fact_id="no_obvious_alternate_volumes_mount",
            value=True,
            summary="Mac readback did not find the share under another obvious /Volumes name.",
        ),
        _mac_fact(
            fact_id="no_smb_share_active",
            value=True,
            summary="Mac readback reported no active SMB share for this bridge.",
        ),
        _mac_fact(
            fact_id="launch_agent_loaded",
            value="com.openclaw.read-model-sync installed_loaded",
            summary="The Mac LaunchAgent exists and is loaded, but the share is missing.",
        ),
        _mac_fact(
            fact_id="recent_sync_agent_result",
            value=fields.get("launch_agent_status_label") or "share_missing",
            summary="Recent Mac sync attempts fail closed with share_missing.",
        ),
        _mac_fact(
            fact_id="mac_local_mirror_file_count",
            value=local_count,
            summary="Mac local mirror file count after prior helper pull.",
        ),
        _mac_fact(
            fact_id="desktop_mac_manifest_path_records",
            value=desktop_manifest_count,
            summary="Desktop Mac manifest path-record count reported by Mac readback.",
        ),
        _mac_fact(
            fact_id="nested_lane_spine_local_readback",
            value=f"present_parsed_{lane_count}_lanes" if lane_count is not None else "present_parsed_14_lanes",
            summary="operator_nested_lane_mission_package_spine.json is present locally and parses.",
        ),
        _mac_fact(
            fact_id="chief_posture_local_readback",
            value="missing_locally",
            summary="Chief check-engine environment posture is not yet visible in the Mac local mirror.",
        ),
        _mac_fact(
            fact_id="chief_diagnostic_local_readback",
            value="missing_locally",
            summary="Chief diagnostic package is not yet visible in the Mac local mirror.",
        ),
        _mac_fact(
            fact_id="mac_sync_health_stale",
            value="canonical_expected=194 observed=192 missing_expected=2",
            summary="Mac local sync_health.json is stale relative to current Repo A state.",
        ),
        _mac_fact(
            fact_id="local_readback_is_full_bridge_proof",
            value=False,
            summary="Local Mac file presence is useful readback, not full PC-Mac shuttle completion proof.",
        ),
    ]


def _observed_pc_facts(sync_health: dict[str, Any], bridge_truth: dict[str, Any]) -> dict[str, Any]:
    return {
        "current_sync_health": _current_sync_health(sync_health),
        "bridge_trust": {
            "bridge_trust_state": bridge_truth.get("bridge_trust_state"),
            "secondary_bridge_states": list(bridge_truth.get("secondary_bridge_states", []) or []),
            "check_engine_should_light": bool(bridge_truth.get("check_engine_should_light", False)),
            "operator_action_required": bool(bridge_truth.get("operator_action_required", False)),
            "basis": "generated/read_models/bridge_trust_sync_truth.json",
        },
        "operator_checkpoint_before_packet": dict(OPERATOR_CHECKPOINT_BEFORE_PACKET),
    }


def _manual_operator_steps() -> list[dict[str, Any]]:
    return [
        {
            "step_id": "manual_mount_windows_e_share_on_mac",
            "actor": "Winship",
            "plain_language": "Mount Windows E:\\openclaw on the Mac so it appears exactly at /Volumes/openclaw_e.",
            "automatable_by_packet": False,
            "packet_runs_command": False,
            "requires_credentials_if_mac_requests_them": "manual_operator_only_not_stored",
        },
        {
            "step_id": "verify_mount_before_sync",
            "actor": "Winship_on_Mac",
            "plain_language": "Confirm the expected Mac mount path exists before kicking the existing sync service.",
            "automatable_by_packet": False,
            "packet_runs_command": False,
            "command_to_run_manually": "ls -la /Volumes/openclaw_e",
        },
        {
            "step_id": "verify_shuttle_marker_before_sync",
            "actor": "Winship_on_Mac",
            "plain_language": "Confirm the existing bounded sync request marker is visible through the mount.",
            "automatable_by_packet": False,
            "packet_runs_command": False,
            "command_to_run_manually": "ls -la /Volumes/openclaw_e/shuttle/to_mac/read_model_sync_required.json",
        },
        {
            "step_id": "kick_existing_loaded_sync_agent_after_mount",
            "actor": "Winship_on_Mac",
            "plain_language": "After both checks pass, kick the already installed LaunchAgent.",
            "automatable_by_packet": False,
            "packet_runs_command": False,
            "command_to_run_manually": "launchctl kickstart -k gui/$(id -u)/com.openclaw.read-model-sync",
        },
    ]


def _post_mount_verification_steps() -> list[dict[str, Any]]:
    return [
        {
            "step_id": "verify_mount_path",
            "actor": "Winship_on_Mac",
            "command": "ls -la /Volumes/openclaw_e",
            "packet_runs_command": False,
            "success_signal": "/Volumes/openclaw_e lists the Windows E:\\openclaw share.",
        },
        {
            "step_id": "verify_sync_request_marker",
            "actor": "Winship_on_Mac",
            "command": "ls -la /Volumes/openclaw_e/shuttle/to_mac/read_model_sync_required.json",
            "packet_runs_command": False,
            "success_signal": "The bounded sync request marker is visible from the Mac mount.",
        },
    ]


def _safe_existing_service_kick() -> dict[str, Any]:
    return {
        "actor": "Winship_on_Mac_after_manual_mount",
        "command": "launchctl kickstart -k gui/$(id -u)/com.openclaw.read-model-sync",
        "packet_runs_command": False,
        "future_gated": True,
        "requires_prior_successful_mount_verification": True,
        "why_safe_after_mount": "It kicks the already installed LaunchAgent; it does not add remount, credential, repair, or send authority.",
    }


def _partial_success_proof() -> list[dict[str, Any]]:
    return [
        {
            "state_id": "mac_local_mirror_updates_pc_proof_stale",
            "meaning": "The Mac local mirror receives files, but PC sync_health still has stale observed counts.",
            "safe_next_step": "Wait for normal PC import proof or inspect the existing import markers read-only.",
        },
        {
            "state_id": "mount_exists_completion_marker_missing",
            "meaning": "/Volumes/openclaw_e exists, but read_model_sync_completed.json does not update.",
            "safe_next_step": "Inspect LaunchAgent output/status read-only; do not add remount or repair automation.",
        },
        {
            "state_id": "completion_marker_updates_pc_import_pending",
            "meaning": "Mac completion marker updates, but PC import has not refreshed sync_health yet.",
            "safe_next_step": "Wait for the existing PC import lifecycle or capture a read-only Chief diagnostic follow-up.",
        },
        {
            "state_id": "expected_count_changed_while_pending",
            "meaning": "Repo A gained more generated read-models while the bridge was waiting.",
            "safe_next_step": "Refresh sync_health through the normal lifecycle and compare current expected counts.",
        },
    ]


def _failure_states() -> list[dict[str, Any]]:
    return [
        {
            "state_id": "mount_still_missing",
            "meaning": "/Volumes/openclaw_e still does not exist after manual mount attempt.",
            "safe_next_step": "Winship handles Mac/Windows share setup manually; OpenClaw remains fail-closed.",
        },
        {
            "state_id": "mounted_under_wrong_name",
            "meaning": "The share exists under a different /Volumes path, so scripts still cannot see /Volumes/openclaw_e.",
            "safe_next_step": "Mount to the expected path or update the bridge contract in a separate reviewed lane.",
        },
        {
            "state_id": "smb_or_share_unavailable",
            "meaning": "The Mac cannot see the Windows share.",
            "safe_next_step": "Manual network/share troubleshooting only; this packet does not handle credentials.",
        },
        {
            "state_id": "manual_credentials_needed",
            "meaning": "The Mac prompts Winship for credentials.",
            "safe_next_step": "Winship handles credentials manually; do not store them in OpenClaw.",
        },
        {
            "state_id": "agent_still_reports_share_missing",
            "meaning": "The LaunchAgent still reports share_missing after the mount appears present.",
            "safe_next_step": "Create a read-only Chief follow-up with mount path and marker visibility evidence.",
        },
        {
            "state_id": "expected_marker_missing_from_shuttle",
            "meaning": "The mount exists, but read_model_sync_required.json is not visible in the shuttle path.",
            "safe_next_step": "Inspect normal shuttle marker generation; do not manually copy read-model outputs.",
        },
        {
            "state_id": "pc_proof_remains_stale_after_mac_completion",
            "meaning": "Mac completion updates, but PC import/sync_health still does not agree.",
            "safe_next_step": "Inspect PC import proof read-only and keep Check Engine on.",
        },
    ]


def build_bridge_manual_mount_recovery_packet(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    sync_health = _read_json_if_present(SYNC_HEALTH_JSON, repo_root=repo_root)
    bridge_truth = _read_json_if_present(BRIDGE_TRUST_JSON, repo_root=repo_root)
    diagnostic = _read_json_if_present(CHIEF_DIAGNOSTIC_JSON, repo_root=repo_root)

    observed_pc_facts = _observed_pc_facts(sync_health, bridge_truth)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "packet_id": "bridge_manual_mount_recovery_packet_v0",
        "owner": {"primary": "Chief", "trust_surface": "Mirror Trust"},
        "status": "blocked_manual_mount_required",
        "packet_type": "bridge_manual_recovery_packet",
        "relationship_to_bridge_trust": {
            "extends_or_replaces": "companion_packet",
            "bridge_trust_remains_source_for_truth_state": True,
            "source_path": BRIDGE_TRUST_JSON,
            "purpose": "Make the manual /Volumes/openclaw_e mount requirement explicit and operator-safe.",
        },
        "bridge_mount_expected_paths": dict(EXPECTED_PATHS),
        "current_blocker": {
            "blocker_id": "mac_bridge_mount_missing",
            "status": "blocked_manual_mount_required",
            "plain_language": "Bridge sync cannot complete because /Volumes/openclaw_e is missing on Mac.",
            "why_it_matters": "The Mac sync agent cannot see the Windows E:\\openclaw shuttle, so full PC-Mac read-model proof cannot complete.",
            "basis": "operator_reported_mac_readback_plus_bridge_trust_sync_truth",
            "must_be_resolved_by": "Winship manual Mac/Windows mount action",
        },
        "observed_mac_facts": _observed_mac_facts(diagnostic, bridge_truth),
        "observed_pc_facts": observed_pc_facts,
        "manual_operator_steps": _manual_operator_steps(),
        "post_mount_verification_steps": _post_mount_verification_steps(),
        "safe_existing_service_kick": _safe_existing_service_kick(),
        "expected_success_proof": [
            "/Volumes/openclaw_e exists on Mac.",
            "Mac sync agent no longer reports share_missing.",
            "read_model_sync_completed.json updates.",
            "mac_generated_read_models_manifest.json updates.",
            "Mac local mirror receives Chief posture + Chief diagnostic package files.",
            "PC import/sync health eventually reaches missing_expected=0, hash_mismatch=0.",
            "PC canonical and observed counts agree, likely 198/198 or the current expected count at time of run.",
        ],
        "partial_success_proof": _partial_success_proof(),
        "failure_states": _failure_states(),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "authority_boundary": {
            "manual_packet_only": True,
            "read_model_only": True,
            "packet_runs_commands": False,
            "manual_mount_instructions_only": True,
            "no_delete_authority": True,
            "no_repair_authority": True,
            "remount_authority_added": False,
            "auto_remount_authority_added": False,
            "credential_or_oauth_accessed": False,
            "credential_storage_added": False,
            "runtime_authority_added": False,
            "execution_authority_added": False,
            "model_or_agent_authority_added": False,
            "send_submit_approval_authority_added": False,
        },
        "what_would_make_check_engine_quiet": [
            "/Volumes/openclaw_e is present on Mac.",
            "The sync request marker is visible through the Mac mount.",
            "The existing Mac sync LaunchAgent completes without share_missing.",
            "read_model_sync_completed.json and mac_generated_read_models_manifest.json update.",
            "PC sync_health reaches missing_expected=0 and hash_mismatch=0 for the current expected set.",
            "Bridge Trust / Sync Truth returns trusted_current or equivalent current proof.",
        ],
        "mission_control_should_show": {
            "check_engine": "on",
            "primary_message": "Bridge sync is blocked because /Volumes/openclaw_e is not mounted on Mac.",
            "secondary_message": "Winship must mount Windows E:\\openclaw as /Volumes/openclaw_e, then verify the shuttle marker and kick the existing Mac sync service.",
            "must_show_manual_mount_required": True,
            "must_not_show_as_mirror_current": True,
            "operator_action_required": "manual_mount_required_when_ready",
            "button_metadata": [
                {
                    "button_id": "inspect_manual_mount_required",
                    "label": "Inspect Manual Mount Required",
                    "visible_condition": "bridge_trust_state == bridge_mount_missing",
                    "what_it_should_show": "Expected paths, manual verification commands, proof states, and forbidden actions.",
                    "what_it_must_not_do": "It must not remount, run commands, handle credentials, repair, send, submit, or approve anything.",
                    "mode": "read_only",
                    "required_future_receipt_if_mutating": None,
                },
                {
                    "button_id": "show_post_mount_proof",
                    "label": "Show Post-Mount Proof",
                    "visible_condition": "status == blocked_manual_mount_required",
                    "what_it_should_show": "Expected success proof, partial success proof, and failure states.",
                    "what_it_must_not_do": "It must not claim Mirror Current until PC proof agrees.",
                    "mode": "read_only",
                    "required_future_receipt_if_mutating": None,
                },
                {
                    "button_id": "capture_manual_mount_result",
                    "label": "Capture Manual Mount Result",
                    "visible_condition": "future_capture_lane_enabled",
                    "what_it_should_show": "A future bounded form for mount-visible, marker-visible, and agent-result fields.",
                    "what_it_must_not_do": "It must not store credentials or raw private logs.",
                    "mode": "future_gated_capture_only",
                    "required_future_receipt_if_mutating": "bridge_manual_mount_result_receipt",
                },
            ],
        },
        "chief_package_preview": {
            "actor_model": "future_selected_model_unspecified_not_live",
            "character": "Chief",
            "mission": "Explain the blocked bridge, inspect proof states, and recommend the safest next manual diagnostic move.",
            "context_included": [
                "expected Windows/WSL/Mac bridge paths",
                "operator-reported Mac mount absence",
                "stale Mac sync health readback",
                "current PC sync_health counts",
                "Bridge Trust / Sync Truth state",
                "manual verification and success proof requirements",
            ],
            "context_excluded": [
                "credentials",
                "raw private data",
                "raw logs unless explicitly approved in a later lane",
                "raw trace contents",
                "Mission Control app mutation",
            ],
            "allowed_capabilities": ["inspect_only_read_only_diagnostics"],
            "forbidden": list(FORBIDDEN_ACTIONS),
            "stop_conditions": [
                "State whether the mount is still missing.",
                "State whether the shuttle marker is visible.",
                "State whether Mac completion and PC sync_health proof agree.",
                "Return the next safe manual or read-only diagnostic step.",
            ],
            "launch_posture": "future_gated_not_live",
        },
        "source_inputs": {
            "sync_health": {
                "path": SYNC_HEALTH_JSON,
                "present": bool(sync_health),
                "generated_at": sync_health.get("generated_at"),
                "trust_status": sync_health.get("trust_status"),
                "display_status": sync_health.get("display_status"),
            },
            "bridge_trust_sync_truth": {
                "path": BRIDGE_TRUST_JSON,
                "present": bool(bridge_truth),
                "schema_version": bridge_truth.get("schema_version"),
                "bridge_trust_state": bridge_truth.get("bridge_trust_state"),
            },
            "chief_diagnostic_package": {
                "path": CHIEF_DIAGNOSTIC_JSON,
                "present": bool(diagnostic),
                "schema_version": diagnostic.get("schema_version"),
                "check_engine_on": diagnostic.get("check_engine_on"),
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
            "raw_file_bodies_stored": False,
            "runtime_activation_recorded": False,
            "sqlite_schema_changed": False,
            "receipt_writer_function": "record_bridge_manual_mount_recovery_packet_receipt",
        },
        "storage_policy": {
            "do_not_write_openclaw_artifacts_to_pc_c_drive": True,
            "allowed_openclaw_artifact_roots": ["/home/openclaw", "/mnt/e/openclaw"],
            "c_drive_read_only_inspection_allowed_for_posture_evidence": True,
            "delete_anything_in_this_lane": False,
            "generated_output_root": "generated/read_models",
        },
        "next_recommended_lane": {
            "lane_name": "Manual Mount Result Readback v0",
            "goal": "After Winship manually mounts /Volumes/openclaw_e and kicks the existing service, capture whether success, partial success, or failure proof exists.",
            "non_live": True,
            "operator_action_required_now": True,
        },
        "receipt_hash": "",
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
    }
    payload.update(NO_AUTHORITY_FLAGS)
    payload["receipt_hash"] = _hash_payload(
        {
            "schema_version": payload["schema_version"],
            "status": payload["status"],
            "bridge_mount_expected_paths": payload["bridge_mount_expected_paths"],
            "current_blocker": payload["current_blocker"],
            "observed_pc_facts": payload["observed_pc_facts"],
            "observed_mac_facts": payload["observed_mac_facts"],
            "expected_success_proof": payload["expected_success_proof"],
            "partial_success_proof": payload["partial_success_proof"],
            "failure_states": payload["failure_states"],
            "authority_boundary": payload["authority_boundary"],
        }
    )
    return payload


def format_bridge_manual_mount_recovery_packet(payload: dict[str, Any]) -> str:
    paths = payload["bridge_mount_expected_paths"]
    current_sync = payload["observed_pc_facts"]["current_sync_health"]

    lines = [
        "Bridge Manual Mount Recovery Packet v0",
        "",
        "State:",
        f"- Status: `{payload['status']}`",
        f"- Owner: `{payload['owner']['primary']} / {payload['owner']['trust_surface']}`",
        "- Check Engine should remain on until bridge proof is current.",
        "",
        "Why Bridge Sync Is Blocked:",
        f"- {payload['current_blocker']['plain_language']}",
        f"- {payload['current_blocker']['why_it_matters']}",
        "",
        "Exact Manual Mount Needed:",
        f"- Windows source: `{paths['windows_source']}`",
        f"- WSL source: `{paths['wsl_source']}`",
        f"- Mac mount: `{paths['mac_mount']}`",
        "",
        "What Winship Should Verify After Mounting:",
    ]
    for step in payload["post_mount_verification_steps"]:
        lines.append(f"- `{step['command']}` -> {step['success_signal']}")
    lines.extend(
        [
            "",
            "Existing Safe Sync Kick After Mount:",
            f"- `{payload['safe_existing_service_kick']['command']}`",
            "- This is future-gated and manual; the packet does not run it.",
            "",
            "PC Proof Now:",
            f"- canonical_expected={current_sync['canonical_expected']}",
            f"- observed={current_sync['observed']}",
            f"- missing_expected={current_sync['missing_expected']}",
            f"- hash_mismatch={current_sync['hash_mismatch']}",
            "",
            "Expected Success Proof:",
        ]
    )
    for item in payload["expected_success_proof"]:
        lines.append(f"- {item}")
    lines.extend(["", "Partial Success Means:"])
    for state in payload["partial_success_proof"]:
        lines.append(f"- `{state['state_id']}`: {state['meaning']}")
    lines.extend(["", "Failure States:"])
    for state in payload["failure_states"]:
        lines.append(f"- `{state['state_id']}`: {state['meaning']}")
    lines.extend(
        [
            "",
            "What Mission Control Should Show:",
            f"- {payload['mission_control_should_show']['primary_message']}",
            f"- {payload['mission_control_should_show']['secondary_message']}",
            "- Do not show Mirror Current while this packet is still blocked.",
            "",
            "What Would Make Check Engine Quiet:",
        ]
    )
    for item in payload["what_would_make_check_engine_quiet"]:
        lines.append(f"- {item}")
    lines.extend(["", "What Must Not Be Done:"])
    for action in payload["forbidden_actions"]:
        lines.append(f"- {action}")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Manual recovery packet only; no remount, delete, repair, credential, runtime, model, agent, browser, OAuth, Gmail, calendar, Coupa, Telegram, send, submit, or approval authority.",
            "- The only safe service action described is the existing Mac LaunchAgent kick after Winship has manually verified the mount.",
            "- No OpenClaw artifacts are written to C:.",
            "",
        ]
    )
    return "\n".join(lines)


def export_bridge_manual_mount_recovery_packet(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> BridgeManualMountRecoveryPacketExportResult:
    payload = build_bridge_manual_mount_recovery_packet(repo_root=repo_root, generated_at=generated_at)
    out_dir = _rooted(export_root, repo_root=repo_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_bridge_manual_mount_recovery_packet(payload), encoding="utf-8")
    return BridgeManualMountRecoveryPacketExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        packet_id=payload["packet_id"],
        status=payload["status"],
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


def _find_existing_bridge_manual_mount_receipt(
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


def record_bridge_manual_mount_recovery_packet_receipt(
    *,
    repo_root: str | Path = ROOT,
    db_path: str | Path | None = None,
    commit_hash: str | None = None,
    generated_at: str | None = None,
    ensure: bool = True,
) -> str:
    """Record a metadata-only receipt for the manual mount recovery packet."""
    payload = build_bridge_manual_mount_recovery_packet(repo_root=repo_root, generated_at=generated_at)
    receipt_hash = payload["receipt_hash"]
    if ensure:
        existing = _find_existing_bridge_manual_mount_receipt(
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
        "status": payload["status"],
        "expected_mac_mount": EXPECTED_PATHS["mac_mount"],
        "manual_mount_required": True,
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
        artifact_type="bridge_manual_mount_recovery_packet",
        artifact_status="captured_metadata_only",
        authority_status="generated_status_only",
        runtime_activation=False,
        sqlite_meaning="receipt_record_only",
        source_basis=[
            SYNC_HEALTH_JSON,
            BRIDGE_TRUST_JSON,
            CHIEF_DIAGNOSTIC_JSON,
            "operator_prompt: Bridge Trust / Manual Mount Recovery Packet v0",
        ],
        actor="bridge_manual_mount_recovery_packet_v0",
        created_at=generated_at,
        db_path=str(db_path) if db_path else None,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Bridge Trust / Manual Mount Recovery Packet read-model.")
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
    result = export_bridge_manual_mount_recovery_packet(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    receipt_id = ""
    if args.record_receipt:
        receipt_id = record_bridge_manual_mount_recovery_packet_receipt(
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
    "build_bridge_manual_mount_recovery_packet",
    "export_bridge_manual_mount_recovery_packet",
    "format_bridge_manual_mount_recovery_packet",
    "record_bridge_manual_mount_recovery_packet_receipt",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())

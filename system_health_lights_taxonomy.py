"""System Health Lights taxonomy v0.

This read-model defines the Mission Control helm warning/status lights without
adding UI, repair, remount, credential, runtime, model, agent, browser, send,
submit, or approval authority.

Field observation captured here: fresh machine proof should beat stale
operator-reported bridge facts. Check Transmission owns PC/Mac bridge and
state-transfer proof; Check Engine should not remain a bridge catchall once the
transmission lane can explain the actual drivetrain state.
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
DEFAULT_PC_SHARE_ROOT = Path("/mnt/e/openclaw")
DEFAULT_PC_IMPORT_STATE_PATH = ROOT / ".openclaw" / "state" / "read_model_import_agent_state.json"

SCHEMA_VERSION = "system_health_lights_taxonomy_v0"
JSON_EXPORT_NAME = "system_health_lights_taxonomy.json"
OPERATOR_EXPORT_NAME = "system_health_lights_taxonomy_OPERATOR.md"

SYNC_HEALTH_JSON = "generated/read_models/sync_health.json"
BRIDGE_TRUST_JSON = "generated/read_models/bridge_trust_sync_truth.json"
CHIEF_POSTURE_JSON = "generated/read_models/chief_check_engine_environment_posture.json"
CHIEF_DIAGNOSTIC_JSON = "generated/read_models/chief_check_engine_diagnostic_package.json"

EXPECTED_BACKEND_HEAD = "3c7620c324edbf9883930ec465749f8ca99403f0"
SELF_TAXONOMY_EXPORT_FILES = frozenset({JSON_EXPORT_NAME, OPERATOR_EXPORT_NAME})

LIGHT_STATUS_OPTIONS = (
    "QUIET",
    "INFO",
    "WARNING",
    "ON",
    "ON_NORMAL",
    "UNKNOWN",
)

STEEL_THREAD_FLOW = (
    "ELI5/operator orientation",
    "machine contract/proof",
    "package/detour/fix path",
)

NO_AUTHORITY_FLAGS = {
    "read_model_only": True,
    "metadata_only": True,
    "taxonomy_only": True,
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
    "write OpenClaw artifacts to C:",
    "delete files or caches",
    "remount /Volumes/openclaw_e automatically",
    "handle or store credentials",
    "create auto-remount authority",
    "run Mac commands from PC",
    "manual-copy generated read-model files as the primary fix",
    "mutate Mission Control app code",
    "repair backend services from this taxonomy",
    "activate agents or call models",
    "open browser, OAuth, Gmail, calendar, Coupa, Telegram, send, submit, or approval flows",
    "inspect raw private logs, raw trace contents, broad temp listings, or raw file bodies",
)


@dataclass(frozen=True)
class SystemHealthLightsTaxonomyExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    check_transmission_status: str
    pc_proof_agrees_with_mac_sync_completion: bool
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


def _read_absolute_json_if_present(path: str | Path) -> dict[str, Any]:
    target = Path(path)
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


def _manifest_names(manifest: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for record in manifest.get("path_records", []) or []:
        if isinstance(record, dict) and isinstance(record.get("relative_path"), str):
            names.add(record["relative_path"])
    return names


def _manifest_count(manifest: dict[str, Any]) -> int | None:
    records = manifest.get("path_records")
    if isinstance(records, list):
        return len(records)
    return None


def _state_final_mirror_request(state: dict[str, Any]) -> dict[str, Any]:
    request = state.get("last_final_mac_mirror_request")
    return request if isinstance(request, dict) else {}


def _self_report_state(final_request: dict[str, Any]) -> dict[str, Any]:
    state = final_request.get("self_report_mirror_state")
    return state if isinstance(state, dict) else {}


def _pc_import_proof(
    *,
    sync_health: dict[str, Any],
    completion: dict[str, Any],
    manifest: dict[str, Any],
    import_state: dict[str, Any],
) -> dict[str, Any]:
    canonical_expected = _int_or_none(sync_health.get("canonical_expected"))
    observed = _int_or_none(sync_health.get("observed"))
    missing_expected = _int_or_none(sync_health.get("missing_expected"))
    hash_mismatch = _int_or_none(sync_health.get("hash_mismatch"))
    completion_count = _int_or_none(completion.get("copied_file_count"))
    manifest_count = _manifest_count(manifest)
    names = _manifest_names(manifest)
    required = {
        "chief_check_engine_environment_posture.json": "chief_check_engine_environment_posture.json" in names,
        "chief_check_engine_diagnostic_package.json": "chief_check_engine_diagnostic_package.json" in names,
        "bridge_manual_mount_recovery_packet.json": "bridge_manual_mount_recovery_packet.json" in names,
    }
    backend_head = completion.get("backend_head")
    pc_counts = import_state.get("last_mirror_counts") if isinstance(import_state.get("last_mirror_counts"), dict) else {}
    current_expected_set_agrees = bool(
        sync_health
        and completion.get("status") == "synced"
        and canonical_expected is not None
        and observed == canonical_expected
        and missing_expected == 0
        and hash_mismatch == 0
        and completion_count == observed
        and manifest_count == observed
        and all(required.values())
    )
    last_checkpoint_agrees = bool(
        completion.get("status") == "synced"
        and completion_count is not None
        and manifest_count == completion_count
        and _int_or_none(pc_counts.get("observed")) == completion_count
        and _int_or_none(pc_counts.get("canonical_expected")) == completion_count
        and _int_or_none(pc_counts.get("missing_expected")) == 0
        and _int_or_none(pc_counts.get("hash_mismatch")) == 0
        and all(required.values())
    )
    missing_files = list(sync_health.get("missing_files", []) or [])
    current_missing_only_self_taxonomy = bool(missing_files) and set(missing_files).issubset(
        SELF_TAXONOMY_EXPORT_FILES
    )
    return {
        "canonical_expected": canonical_expected,
        "observed": observed,
        "missing_expected": missing_expected,
        "hash_mismatch": hash_mismatch,
        "missing_files": missing_files,
        "matched_hash": _int_or_none(sync_health.get("matched_hash")),
        "sync_lifecycle_state": sync_health.get("sync_lifecycle_state"),
        "trust_status": sync_health.get("trust_status"),
        "mirror_status": sync_health.get("mirror_status"),
        "display_status": sync_health.get("display_status"),
        "operator_action_required": bool(sync_health.get("operator_action_required", False)),
        "last_pc_import_status": (sync_health.get("last_pc_import") or {}).get("status")
        if isinstance(sync_health.get("last_pc_import"), dict)
        else import_state.get("status"),
        "last_pc_import_time": (sync_health.get("last_pc_import") or {}).get("time")
        if isinstance(sync_health.get("last_pc_import"), dict)
        else import_state.get("last_imported_at"),
        "completion_status": completion.get("status"),
        "completion_generated_at": completion.get("generated_at"),
        "completion_copied_file_count": completion_count,
        "manifest_path_record_count": manifest_count,
        "backend_head": backend_head,
        "expected_backend_head": EXPECTED_BACKEND_HEAD,
        "backend_head_matches_expected": backend_head == EXPECTED_BACKEND_HEAD,
        "required_files_in_mac_manifest": required,
        "pc_import_state_last_counts": {
            "canonical_expected": _int_or_none(pc_counts.get("canonical_expected")),
            "observed": _int_or_none(pc_counts.get("observed")),
            "missing_expected": _int_or_none(pc_counts.get("missing_expected")),
            "hash_mismatch": _int_or_none(pc_counts.get("hash_mismatch")),
        },
        "current_expected_set_proof_current": current_expected_set_agrees,
        "last_import_checkpoint_agrees_with_mac_completion": last_checkpoint_agrees,
        "current_expected_set_missing_only_self_taxonomy": current_missing_only_self_taxonomy,
        "pc_proof_agrees_with_mac_sync_completion": bool(
            current_expected_set_agrees or last_checkpoint_agrees
        ),
    }


def _transmission_status(pc_proof: dict[str, Any], import_state: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    final_request = _state_final_mirror_request(import_state)
    self_report = _self_report_state(final_request)
    final_mirror_pending = bool(final_request.get("final_mac_mirror_marker_needed"))
    self_report_stale_files = list(self_report.get("stale_files", []) or [])
    final_self_report_pending = bool(self_report_stale_files)
    core_complete = bool(pc_proof["pc_proof_agrees_with_mac_sync_completion"])
    current_expected_current = bool(pc_proof.get("current_expected_set_proof_current"))
    missing_only_self_taxonomy = bool(pc_proof.get("current_expected_set_missing_only_self_taxonomy"))
    if not pc_proof.get("sync_lifecycle_state"):
        status = "UNKNOWN"
        reason = "PC sync health is unavailable, so transmission proof is unknown."
    elif not core_complete:
        status = "ON"
        reason = "PC proof does not yet agree with Mac completion or has missing/hash-mismatch files."
    elif not current_expected_current and missing_only_self_taxonomy:
        status = "WARNING"
        reason = "Core PC import proof is current; the newly generated health-light taxonomy is waiting for the normal Mac mirror cycle."
    elif final_self_report_pending:
        status = "WARNING"
        reason = "Core PC import proof is current, but the Mac-visible sync-health self-report mirror still needs the normal final echo."
    elif not current_expected_current:
        status = "ON"
        reason = "PC proof imported the prior Mac completion, but the current expected read-model set is not fully mirrored."
    else:
        status = "QUIET"
        reason = "PC proof agrees with Mac completion and no final Mac-visible self-report echo is pending."
    return status, reason, {
        "core_pc_import_proof_complete": core_complete,
        "current_expected_set_proof_current": current_expected_current,
        "current_expected_set_missing_only_self_taxonomy": missing_only_self_taxonomy,
        "current_missing_files": list(pc_proof.get("missing_files", []) or []),
        "final_mac_mirror_pending": final_mirror_pending,
        "final_mac_self_report_mirror_pending": final_self_report_pending,
        "self_report_stale_files": self_report_stale_files,
        "final_mac_mirror_marker_written": bool(final_request.get("final_mac_mirror_marker_written")),
        "self_report_status": self_report.get("status"),
    }


def _engine_status(*, chief_posture: dict[str, Any], transmission_status: str) -> tuple[str, str, dict[str, Any]]:
    posture_check = chief_posture.get("check_engine") if isinstance(chief_posture.get("check_engine"), dict) else {}
    legacy_on = bool(posture_check.get("check_engine_on"))
    if transmission_status == "ON":
        return (
            "WARNING",
            "A bridge/import issue exists, but Check Transmission owns that fault so Check Engine should not duplicate it as a catchall.",
            {
                "legacy_chief_posture_still_on": legacy_on,
                "bridge_fault_owned_by_check_transmission": True,
                "chief_posture_source_path": CHIEF_POSTURE_JSON,
            },
        )
    if legacy_on:
        return (
            "WARNING",
            "Chief posture still has older workbench warnings; bridge-specific signals should now be read through Check Transmission.",
            {
                "legacy_chief_posture_still_on": True,
                "bridge_fault_owned_by_check_transmission": True,
                "chief_posture_source_path": CHIEF_POSTURE_JSON,
            },
        )
    return (
        "QUIET",
        "No current Chief-owned core system/workbench fault is proven by this taxonomy.",
        {
            "legacy_chief_posture_still_on": False,
            "bridge_fault_owned_by_check_transmission": True,
            "chief_posture_source_path": CHIEF_POSTURE_JSON,
        },
    )


def _authority_boundary() -> dict[str, Any]:
    return {
        "read_model_only": True,
        "metadata_only": True,
        "runtime_authority_added": False,
        "execution_authority_added": False,
        "delete_authority_added": False,
        "remount_authority_added": False,
        "credential_authority_added": False,
        "send_submit_approval_authority_added": False,
    }


def _light(
    *,
    light_id: str,
    display_name: str,
    analogy: str,
    owner: str,
    meaning: str,
    when_on: list[str],
    when_quiet: list[str],
    opens_lane: str,
    evidence_inputs: list[str],
    safe_next_move: str,
    state_kind: str,
    current_status: str,
    current_reason: str,
    current_evidence: dict[str, Any],
    is_failure: bool,
) -> dict[str, Any]:
    if current_status not in LIGHT_STATUS_OPTIONS:
        raise ValueError(f"unsupported light status: {current_status}")
    return {
        "light_id": light_id,
        "display_name": display_name,
        "analogy": analogy,
        "owner": owner,
        "meaning": meaning,
        "when_on": when_on,
        "when_quiet": when_quiet,
        "severity_status_options": list(LIGHT_STATUS_OPTIONS),
        "opens_lane": opens_lane,
        "steel_thread_flow": list(STEEL_THREAD_FLOW),
        "evidence_inputs": evidence_inputs,
        "safe_next_move": safe_next_move,
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "authority_boundary": _authority_boundary(),
        "current_state_kind": state_kind,
        "current_status": current_status,
        "current_reason": current_reason,
        "current_evidence": current_evidence,
        "is_failure": is_failure,
    }


def _build_lights(
    *,
    pc_proof: dict[str, Any],
    import_state: dict[str, Any],
    chief_posture: dict[str, Any],
) -> list[dict[str, Any]]:
    transmission_status, transmission_reason, transmission_evidence = _transmission_status(pc_proof, import_state)
    engine_status, engine_reason, engine_evidence = _engine_status(
        chief_posture=chief_posture,
        transmission_status=transmission_status,
    )
    return [
        _light(
            light_id="check_engine",
            display_name="Check Engine",
            analogy="Core system/workbench fault",
            owner="Chief",
            meaning="Something in the reasoning, control, or workbench layer needs Chief inspection.",
            when_on=[
                "A core OpenClaw system/workbench fault is stale, unsafe, blocked, internally inconsistent, or failing proof/trust.",
                "A Chief diagnostic package is required for non-bridge system degradation.",
            ],
            when_quiet=[
                "Chief-owned system proof is current, no core workbench fault is active, and bridge faults are owned by Check Transmission.",
            ],
            opens_lane="Chief diagnostic/system health lane",
            evidence_inputs=[
                CHIEF_POSTURE_JSON,
                CHIEF_DIAGNOSTIC_JSON,
                BRIDGE_TRUST_JSON,
                SYNC_HEALTH_JSON,
            ],
            safe_next_move="Open Chief diagnostic/system health lane; do not run repair automatically.",
            state_kind="fault",
            current_status=engine_status,
            current_reason=engine_reason,
            current_evidence=engine_evidence,
            is_failure=engine_status in {"ON", "WARNING"},
        ),
        _light(
            light_id="check_transmission",
            display_name="Check Transmission",
            analogy="PC-Mac drivetrain / state-transfer fault",
            owner="Chief / Mirror Trust",
            meaning="The PC-Mac bridge, shuttle markers, mirror proof, or app-visible sync-health echo needs inspection.",
            when_on=[
                "PC proof disagrees with Mac completion.",
                "missing_expected > 0 or hash_mismatch > 0 for the current expected set.",
                "/Volumes/openclaw_e is missing or unverified.",
                "Shuttle completion proof is stale or blocked.",
            ],
            when_quiet=[
                "PC proof agrees with Mac completion, sync_health has missing_expected=0 and hash_mismatch=0, and no final app-visible sync-health echo is pending.",
            ],
            opens_lane="Bridge / mirror / sync trust lane",
            evidence_inputs=[
                SYNC_HEALTH_JSON,
                "scripts/pc_read_model_import_agent.py state",
                "/mnt/e/openclaw/shuttle/from_mac/read_model_sync_completed.json",
                "/mnt/e/openclaw/mac_generated_read_models_manifest.json",
            ],
            safe_next_move="If warning only, wait for the normal Mac mirror echo; if ON, inspect bridge proof without remount/delete/credential automation.",
            state_kind="transport_warning",
            current_status=transmission_status,
            current_reason=transmission_reason,
            current_evidence=transmission_evidence,
            is_failure=transmission_status == "ON",
        ),
        _light(
            light_id="low_fuel_low_battery",
            display_name="Low Fuel / Low Battery",
            analogy="Resource pressure",
            owner="Chief",
            meaning="Storage, credits/quota, compute, or required tool availability may limit work.",
            when_on=[
                "A required resource is below a safe operating threshold.",
                "Recent resource pressure is unresolved or not re-measured.",
            ],
            when_quiet=[
                "Resource pressure is measured healthy or no longer materially affects operator action.",
            ],
            opens_lane="Resource posture lane",
            evidence_inputs=[
                CHIEF_POSTURE_JSON,
                "operator_reported: C: was near full then cleaned to about 22GB free",
            ],
            safe_next_move="Keep resource pressure visible as monitor/warning until a bounded resource posture refresh proves it quiet.",
            state_kind="resource_warning",
            current_status="WARNING",
            current_reason="C: was recently near full and later cleaned to about 22GB free, but this lane did not perform a new live disk measurement.",
            current_evidence={
                "basis": "operator_reported",
                "c_drive_recently_near_full": True,
                "cleanup_reported_free_space_about_gb": 22,
                "live_measurement_in_this_lane": False,
            },
            is_failure=False,
        ),
        _light(
            light_id="oil_pressure_coolant",
            display_name="Oil Pressure / Coolant",
            analogy="Maintenance/environment degradation",
            owner="Chief",
            meaning="Recurring logs, traces, caches, latency, or validation friction could become a system failure.",
            when_on=[
                "Maintenance signals are growing or recurring enough to threaten reliability.",
                "Tool/workbench latency or validation friction makes progress unreliable.",
            ],
            when_quiet=[
                "Maintenance risk is measured stable, bounded, or resolved without recurring warnings.",
            ],
            opens_lane="Maintenance / environment degradation lane",
            evidence_inputs=[
                CHIEF_POSTURE_JSON,
                CHIEF_DIAGNOSTIC_JSON,
                "operator_reported: RD Client trace growth and Mac validation friction",
            ],
            safe_next_move="Open a read-only maintenance posture lane before any cleanup/remount/repair action.",
            state_kind="maintenance_warning",
            current_status="WARNING",
            current_reason="RD Client trace growth and Mac validation friction are maintenance risks even if the bridge import proof is now current.",
            current_evidence={
                "basis": "operator_reported_plus_chief_posture",
                "rd_client_trace_growth_reported": True,
                "mac_validation_friction_reported": True,
            },
            is_failure=False,
        ),
        _light(
            light_id="brake_parking_brake",
            display_name="Brake / Parking Brake",
            analogy="Authority intentionally locked",
            owner="Guardian / Chief",
            meaning="Execution, send, approval, credential, runtime, or destructive authority is blocked on purpose.",
            when_on=[
                "A capability is intentionally unavailable, parked, or requires explicit future authority.",
            ],
            when_quiet=[
                "No relevant authority boundary affects the current lane or package.",
            ],
            opens_lane="Authority boundary lane",
            evidence_inputs=[
                "authority_boundary flags across generated packages",
                "Guardian protected access gate specs",
                "operator action covenant",
            ],
            safe_next_move="Inspect why the authority is locked; do not treat this as a failure.",
            state_kind="intentional_lock",
            current_status="ON_NORMAL",
            current_reason="Runtime, send, approval, remount, credential, and repair authorities remain intentionally blocked in these contracts.",
            current_evidence={
                "is_intentional": True,
                "failure": False,
                "locked_authorities": [
                    "runtime",
                    "send_submit_approval",
                    "remount",
                    "credential_storage",
                    "delete_cleanup",
                    "model_agent_calls",
                ],
            },
            is_failure=False,
        ),
        _light(
            light_id="traction_control",
            display_name="Traction Control",
            analogy="Confidence / detour state",
            owner="Chief / domain owner",
            meaning="The system can proceed cautiously or needs more evidence before acting.",
            when_on=[
                "A package is below deterministic/full trust and action would benefit from a bounded detour.",
                "Confidence repair materially affects an operator decision.",
            ],
            when_quiet=[
                "Current package confidence is deterministic/full-trust or no package is being considered.",
            ],
            opens_lane="Confidence / detour lane",
            evidence_inputs=[
                "operator_awareness_agent_package_spine",
                "operator_nested_lane_mission_package_spine",
                "future package confidence inputs",
            ],
            safe_next_move="If visible, open the detour lane; if confidence is deterministic, keep the UI quiet.",
            state_kind="confidence_state",
            current_status="QUIET",
            current_reason="No current action package in this lane needs a confidence detour; deterministic confidence UI should stay quiet.",
            current_evidence={
                "active_package_requires_detour": False,
                "full_trust_display_should_be_quiet": True,
            },
            is_failure=False,
        ),
    ]


def build_system_health_lights_taxonomy(
    *,
    repo_root: str | Path = ROOT,
    pc_share_root: str | Path = DEFAULT_PC_SHARE_ROOT,
    pc_import_state_path: str | Path = DEFAULT_PC_IMPORT_STATE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    share = Path(pc_share_root)
    sync_health = _read_json_if_present(SYNC_HEALTH_JSON, repo_root=repo_root)
    bridge_truth = _read_json_if_present(BRIDGE_TRUST_JSON, repo_root=repo_root)
    chief_posture = _read_json_if_present(CHIEF_POSTURE_JSON, repo_root=repo_root)
    chief_diagnostic = _read_json_if_present(CHIEF_DIAGNOSTIC_JSON, repo_root=repo_root)
    completion = _read_absolute_json_if_present(share / "shuttle" / "from_mac" / "read_model_sync_completed.json")
    heartbeat = _read_absolute_json_if_present(share / "shuttle" / "from_mac" / "read_model_sync_agent_status.json")
    manifest = _read_absolute_json_if_present(share / "mac_generated_read_models_manifest.json")
    import_state = _read_absolute_json_if_present(pc_import_state_path)

    pc_proof = _pc_import_proof(
        sync_health=sync_health,
        completion=completion,
        manifest=manifest,
        import_state=import_state,
    )
    lights = _build_lights(pc_proof=pc_proof, import_state=import_state, chief_posture=chief_posture)
    current_light_states = {item["light_id"]: item["current_status"] for item in lights}
    transmission = next(item for item in lights if item["light_id"] == "check_transmission")

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "read_model_id": "system_health_lights_taxonomy",
        "purpose": "Define helm health lights, current states, source precedence, and steel-thread lane mappings.",
        "field_observation_upgrade": {
            "why": "The orchestrator prompt cannot see live local proof; this read-model lets Repo A classify lights from PC-side evidence.",
            "source_precedence_rule": "fresh machine proof should beat stale operator-reported bridge facts when deciding Check Transmission and Check Engine state",
            "split_rule": "PC-Mac bridge/sync/state-transfer belongs to Check Transmission; Check Engine should not duplicate it as a generic fault.",
            "christmas_tree_rule": "Lights appear only when something needs checking, is broken, intentionally locked, or materially affects operator action.",
        },
        "pc_import_proof": pc_proof,
        "mac_shuttle_inputs": {
            "pc_share_root": share.as_posix(),
            "completion_marker_path": share.joinpath("shuttle/from_mac/read_model_sync_completed.json").as_posix(),
            "completion_marker_present": bool(completion),
            "heartbeat_marker_path": share.joinpath("shuttle/from_mac/read_model_sync_agent_status.json").as_posix(),
            "heartbeat_status": heartbeat.get("status"),
            "manifest_path": share.joinpath("mac_generated_read_models_manifest.json").as_posix(),
            "manifest_present": bool(manifest),
            "request_marker_path": share.joinpath("shuttle/to_mac/read_model_sync_required.json").as_posix(),
        },
        "lights": lights,
        "current_light_states": current_light_states,
        "current_lights_on_or_visible": [
            item["light_id"]
            for item in lights
            if item["current_status"] in {"ON", "WARNING", "ON_NORMAL", "UNKNOWN"}
        ],
        "mac_to_e_drive_to_pc_sync_proof_complete": pc_proof["pc_proof_agrees_with_mac_sync_completion"],
        "check_transmission_summary": {
            "current_status": transmission["current_status"],
            "why": transmission["current_reason"],
            "pc_import_proof_complete": pc_proof["pc_proof_agrees_with_mac_sync_completion"],
            "final_mac_mirror_pending": transmission["current_evidence"]["final_mac_mirror_pending"],
            "final_mac_self_report_mirror_pending": transmission["current_evidence"][
                "final_mac_self_report_mirror_pending"
            ],
        },
        "operator_output_questions_answered": {
            "which_lights_exist": [item["display_name"] for item in lights],
            "which_lights_are_currently_on": [
                item["display_name"]
                for item in lights
                if item["current_status"] in {"ON", "WARNING", "ON_NORMAL", "UNKNOWN"}
            ],
            "is_mac_to_e_drive_to_pc_sync_proof_complete": pc_proof[
                "pc_proof_agrees_with_mac_sync_completion"
            ],
            "should_check_transmission_remain_visible": transmission["current_status"] != "QUIET",
            "why_check_transmission_visible": transmission["current_reason"],
        },
        "source_inputs": {
            "sync_health": {
                "path": SYNC_HEALTH_JSON,
                "present": bool(sync_health),
                "generated_at": sync_health.get("generated_at"),
                "trust_status": sync_health.get("trust_status"),
                "mirror_status": sync_health.get("mirror_status"),
                "display_status": sync_health.get("display_status"),
            },
            "bridge_trust_sync_truth": {
                "path": BRIDGE_TRUST_JSON,
                "present": bool(bridge_truth),
                "bridge_trust_state": bridge_truth.get("bridge_trust_state"),
            },
            "chief_environment_posture": {
                "path": CHIEF_POSTURE_JSON,
                "present": bool(chief_posture),
                "generated_at": chief_posture.get("generated_at"),
                "check_engine_on": (chief_posture.get("check_engine") or {}).get("check_engine_on")
                if isinstance(chief_posture.get("check_engine"), dict)
                else None,
            },
            "chief_diagnostic_package": {
                "path": CHIEF_DIAGNOSTIC_JSON,
                "present": bool(chief_diagnostic),
                "generated_at": chief_diagnostic.get("generated_at"),
            },
            "pc_import_state": {
                "path": Path(pc_import_state_path).as_posix(),
                "present": bool(import_state),
                "status": import_state.get("status"),
                "updated_at": import_state.get("updated_at"),
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
            "receipt_writer_function": "record_system_health_lights_taxonomy_receipt",
        },
        "storage_policy": {
            "do_not_write_openclaw_artifacts_to_pc_c_drive": True,
            "allowed_openclaw_artifact_roots": ["/home/openclaw", "/mnt/e/openclaw"],
            "delete_anything_in_this_lane": False,
            "generated_output_root": "generated/read_models",
        },
        "next_recommended_lane": {
            "lane_name": "Mission Control System Health Lights Readback v0",
            "goal": "Render the taxonomy without turning the helm into a permanent status wall.",
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
            "pc_import_proof": payload["pc_import_proof"],
            "current_light_states": payload["current_light_states"],
            "mac_to_e_drive_to_pc_sync_proof_complete": payload[
                "mac_to_e_drive_to_pc_sync_proof_complete"
            ],
            "storage_policy": payload["storage_policy"],
            "authority_flags": payload["no_authority_flags"],
        }
    )
    return payload


def format_system_health_lights_taxonomy(payload: dict[str, Any]) -> str:
    proof = payload["pc_import_proof"]
    lines = [
        "System Health Lights Taxonomy v0",
        "",
        "PC Import Proof:",
        f"- Mac-to-E-drive-to-PC sync proof complete: `{str(payload['mac_to_e_drive_to_pc_sync_proof_complete']).lower()}`",
        f"- canonical_expected={proof['canonical_expected']}",
        f"- observed={proof['observed']}",
        f"- missing_expected={proof['missing_expected']}",
        f"- hash_mismatch={proof['hash_mismatch']}",
        f"- backend_head={proof['backend_head']}",
        f"- backend_head_matches_expected=`{str(proof['backend_head_matches_expected']).lower()}`",
        f"- Core PC import proof is {'complete' if proof['pc_proof_agrees_with_mac_sync_completion'] else 'not complete'}.",
        "",
        "Current Lights:",
    ]
    for item in payload["lights"]:
        lines.extend(
            [
                f"- {item['display_name']}: `{item['current_status']}`",
                f"  - {item['current_reason']}",
                f"  - Opens: {item['opens_lane']}",
            ]
        )
    lines.extend(
        [
            "",
            "Steel Thread Flow:",
            "- Understand: ELI5/operator orientation.",
            "- Inspect: machine contract/proof.",
            "- Decide: package/detour/fix path.",
            "",
            "Check Transmission Detail:",
            f"- {payload['check_transmission_summary']['why']}",
            "",
            "What Makes Lights Quiet:",
        ]
    )
    for item in payload["lights"]:
        quiet = "; ".join(item["when_quiet"])
        lines.append(f"- {item['display_name']}: {quiet}")
    lines.extend(["", "What Must Not Be Done Automatically:"])
    for action in FORBIDDEN_ACTIONS:
        lines.append(f"- {action}")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Taxonomy/read-model only; no UI, repair, remount, delete, credential, runtime, model, agent, browser, OAuth, Gmail, calendar, Coupa, Telegram, send, submit, or approval authority.",
            "- Fresh machine proof beats stale operator-reported bridge facts for current light classification.",
            "- No OpenClaw artifacts are written to C:.",
            "",
        ]
    )
    return "\n".join(lines)


def export_system_health_lights_taxonomy(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    pc_share_root: str | Path = DEFAULT_PC_SHARE_ROOT,
    pc_import_state_path: str | Path = DEFAULT_PC_IMPORT_STATE_PATH,
    generated_at: str | None = None,
) -> SystemHealthLightsTaxonomyExportResult:
    payload = build_system_health_lights_taxonomy(
        repo_root=repo_root,
        pc_share_root=pc_share_root,
        pc_import_state_path=pc_import_state_path,
        generated_at=generated_at,
    )
    out_dir = _rooted(export_root, repo_root=repo_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_system_health_lights_taxonomy(payload), encoding="utf-8")
    return SystemHealthLightsTaxonomyExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        check_transmission_status=payload["current_light_states"]["check_transmission"],
        pc_proof_agrees_with_mac_sync_completion=payload["pc_import_proof"][
            "pc_proof_agrees_with_mac_sync_completion"
        ],
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


def _find_existing_taxonomy_receipt(
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


def record_system_health_lights_taxonomy_receipt(
    *,
    repo_root: str | Path = ROOT,
    pc_share_root: str | Path = DEFAULT_PC_SHARE_ROOT,
    pc_import_state_path: str | Path = DEFAULT_PC_IMPORT_STATE_PATH,
    db_path: str | Path | None = None,
    commit_hash: str | None = None,
    generated_at: str | None = None,
    ensure: bool = True,
) -> str:
    payload = build_system_health_lights_taxonomy(
        repo_root=repo_root,
        pc_share_root=pc_share_root,
        pc_import_state_path=pc_import_state_path,
        generated_at=generated_at,
    )
    receipt_hash = payload["receipt_hash"]
    if ensure:
        existing = _find_existing_taxonomy_receipt(
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
        "current_light_states": payload["current_light_states"],
        "pc_import_proof_complete": payload["mac_to_e_drive_to_pc_sync_proof_complete"],
        "check_transmission_status": payload["current_light_states"]["check_transmission"],
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
        artifact_type="system_health_lights_taxonomy",
        artifact_status="captured_metadata_only",
        authority_status="generated_status_only",
        runtime_activation=False,
        sqlite_meaning="receipt_record_only",
        source_basis=[
            SYNC_HEALTH_JSON,
            BRIDGE_TRUST_JSON,
            CHIEF_POSTURE_JSON,
            "operator_prompt: PC Import Proof + System Health Lights Taxonomy v0",
        ],
        actor="system_health_lights_taxonomy_v0",
        created_at=generated_at,
        db_path=str(db_path) if db_path else None,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export System Health Lights taxonomy read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repo A root.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Generated read-model export root.")
    parser.add_argument("--pc-share-root", default=str(DEFAULT_PC_SHARE_ROOT), help="PC-visible E-drive shuttle root.")
    parser.add_argument("--pc-import-state", default=str(DEFAULT_PC_IMPORT_STATE_PATH), help="PC import agent state path.")
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
    result = export_system_health_lights_taxonomy(
        repo_root=args.repo_root,
        export_root=args.export_root,
        pc_share_root=args.pc_share_root,
        pc_import_state_path=args.pc_import_state,
    )
    receipt_id = ""
    if args.record_receipt:
        receipt_id = record_system_health_lights_taxonomy_receipt(
            repo_root=args.repo_root,
            pc_share_root=args.pc_share_root,
            pc_import_state_path=args.pc_import_state,
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
    "LIGHT_STATUS_OPTIONS",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "build_system_health_lights_taxonomy",
    "export_system_health_lights_taxonomy",
    "format_system_health_lights_taxonomy",
    "record_system_health_lights_taxonomy_receipt",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())

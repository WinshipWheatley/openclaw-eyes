"""Chief check-engine diagnostic package v0.

This read-model is the inspect-only package behind Mission Control's Check
Engine posture. It packages current workbench/bridge degradation for Chief
without granting repair, cleanup, remount, credential, live-agent, model, app,
browser, send, submit, or approval authority.

C: drive references are evidence labels only. Generated outputs are written
only under the configured Repo A read-model export root.
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
from chief_check_engine_environment_posture import (
    FORBIDDEN_GLOBAL_ACTIONS as POSTURE_FORBIDDEN_ACTIONS,
    OPERATOR_REPORTED_MAC_BRIDGE_FACTS,
    OPERATOR_REPORTED_STORAGE_FACTS,
    OPERATOR_REPORTED_WORKBENCH_FACTS,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "chief_check_engine_diagnostic_package_v0"
JSON_EXPORT_NAME = "chief_check_engine_diagnostic_package.json"
OPERATOR_EXPORT_NAME = "chief_check_engine_diagnostic_package_OPERATOR.md"

POSTURE_JSON = "generated/read_models/chief_check_engine_environment_posture.json"
POSTURE_OPERATOR = "generated/read_models/chief_check_engine_environment_posture_OPERATOR.md"
SYNC_HEALTH_JSON = "generated/read_models/sync_health.json"
SYNC_HEALTH_OPERATOR = "generated/read_models/sync_health_OPERATOR.md"

CHECKPOINT_SYNC_FACTS = {
    "canonical_expected": 196,
    "observed": 192,
    "missing_expected": 4,
    "hash_mismatch": 0,
    "sync_lifecycle_state": "sync_requested_waiting_for_mac",
    "operator_action_required": False,
    "missing_files": [
        "chief_check_engine_environment_posture.json",
        "chief_check_engine_environment_posture_OPERATOR.md",
        "operator_nested_lane_mission_package_spine.json",
        "operator_nested_lane_mission_package_spine_OPERATOR.md",
    ],
    "basis": "operator_prompt: Chief Check-Engine Diagnostic Package v0",
}

CONFIDENCE_POSTURES = (
    "FULL_TRUST_DISPLAY_QUIET",
    "HIGH_TRUST",
    "MEDIUM_TRUST",
    "LOW_TRUST",
    "UNKNOWN_FAIL_CLOSED",
)

NO_AUTHORITY_FLAGS = {
    "read_model_only": True,
    "metadata_only": True,
    "diagnostic_package_only": True,
    "inspect_only": True,
    "no_repair_authority": True,
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
    "raw_trace_contents_stored": False,
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

FORBIDDEN_ACTIONS = tuple(
    dict.fromkeys(
        (
            *POSTURE_FORBIDDEN_ACTIONS,
            "repair backend services from this package",
            "auto-remount /Volumes/openclaw_e",
            "handle or store remount credentials",
            "inspect raw private logs, raw ETL trace contents, or broad Temp listings",
            "start browser, OAuth, Gmail, calendar, Coupa, Telegram, send, submit, or approval flows",
            "call models or activate agents",
        )
    )
)


@dataclass(frozen=True)
class CheckEngineDiagnosticPackageExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    package_id: str
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


def _evidence_ref(
    *,
    ref_id: str,
    evidence_type: str,
    source_path: str | None,
    summary: str,
    fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ref_id": ref_id,
        "evidence_type": evidence_type,
        "source_path": source_path,
        "summary": summary,
        "fields": fields or {},
        "raw_body_stored": False,
        "credentials_stored": False,
        "private_content_stored": False,
    }


def _posture_signal(posture: dict[str, Any], signal_id: str) -> dict[str, Any]:
    for signal in posture.get("signals", []):
        if isinstance(signal, dict) and signal.get("signal_id") == signal_id:
            return signal
    return {}


def _sync_counts(sync_health: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_expected": sync_health.get("canonical_expected"),
        "observed": sync_health.get("observed"),
        "missing_expected": sync_health.get("missing_expected"),
        "hash_mismatch": sync_health.get("hash_mismatch"),
        "sync_lifecycle_state": sync_health.get("sync_lifecycle_state"),
        "operator_action_required": sync_health.get("operator_action_required"),
        "missing_files": sync_health.get("missing_files", []),
    }


def _signal(
    *,
    signal_id: str,
    title: str,
    status: str,
    evidence_class: str,
    observed_facts: tuple[str, ...],
    operator_reported_facts: tuple[str, ...],
    inferred_likely_causes: tuple[str, ...],
    unknowns: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    confidence_posture: str,
    safe_diagnostic_steps: tuple[str, ...],
    forbidden_actions: tuple[str, ...],
    what_would_make_quiet: tuple[str, ...],
) -> dict[str, Any]:
    if confidence_posture not in CONFIDENCE_POSTURES:
        raise ValueError(f"unsupported confidence posture: {confidence_posture}")
    return {
        "signal_id": signal_id,
        "title": title,
        "status": status,
        "evidence_class": evidence_class,
        "observed_facts": list(observed_facts),
        "operator_reported_facts": list(operator_reported_facts),
        "inferred_likely_causes": list(inferred_likely_causes),
        "unknowns": list(unknowns),
        "evidence_refs": list(evidence_refs),
        "confidence_posture": confidence_posture,
        "confidence_is_deterministic_posture_not_probability": True,
        "safe_diagnostic_steps": list(safe_diagnostic_steps),
        "forbidden_actions": list(forbidden_actions),
        "what_would_make_quiet": list(what_would_make_quiet),
    }


def _build_diagnostic_signals(*, posture: dict[str, Any], sync_health: dict[str, Any]) -> list[dict[str, Any]]:
    current_sync = _sync_counts(sync_health)
    posture_signal_ids = {item.get("signal_id") for item in posture.get("signals", []) if isinstance(item, dict)}
    posture_has_storage = "c_drive_free_space_low" in posture_signal_ids
    posture_has_sync = "sync_completion_proof_stale" in posture_signal_ids
    sync_present = bool(sync_health)

    return [
        _signal(
            signal_id="c_drive_free_space_pressure",
            title="PC C: drive free-space pressure",
            status="warning",
            evidence_class="operator_reported_with_posture_reference",
            observed_facts=(
                "Current package did not perform a live C: measurement.",
                "Repo A source artifacts are under /home/openclaw.",
            ),
            operator_reported_facts=(
                "C: had about 94.8 MB free before conservative cleanup.",
                "Cleanup freed about 22.99 GB decimal / 21.4 GiB.",
                "C: free space was around 22 GB after cleanup.",
                "Recent OpenClaw sync artifacts were on E: / /mnt/e/openclaw, not C:.",
            ),
            inferred_likely_causes=(
                "The pressure was likely caused by RD Client trace output rather than Repo A bloat.",
            ),
            unknowns=(
                "Whether RD trace growth has stopped permanently.",
                "Current live C: free-space level was not re-measured by this package.",
            ),
            evidence_refs=("posture_json", "operator_storage_report"),
            confidence_posture="HIGH_TRUST" if posture_has_storage else "MEDIUM_TRUST",
            safe_diagnostic_steps=(
                "Compare future read-only disk posture against the no-C-write policy.",
                "Keep C: pressure as a Chief check-engine signal if it recurs.",
            ),
            forbidden_actions=(
                "delete additional C: data from this package",
                "write OpenClaw artifacts to C:",
                "touch swap.vhdx",
            ),
            what_would_make_quiet=(
                "C: remains safely above pressure thresholds across normal work.",
                "No new OpenClaw artifact target points at C:.",
            ),
        ),
        _signal(
            signal_id="rd_client_trace_growth",
            title="RD Client trace growth",
            status="warning",
            evidence_class="operator_reported_likely_cause_not_proven_loop",
            observed_facts=(
                "No Repo A code path is identified as writing RD Client trace files.",
            ),
            operator_reported_facts=(
                "RdClientAutoTrace reached about 22 GB.",
                "The trace directory contained about 5,131 ETL files.",
                "The source appears tied to Windows App / Remote Desktop Mac-to-PC workflow.",
            ),
            inferred_likely_causes=(
                "Remote Desktop-style tracing is the most likely culprit.",
            ),
            unknowns=(
                "Whether Windows App / Remote Desktop tracing is still configured to grow unbounded.",
                "Whether a Windows setting or external app update caused the trace burst.",
            ),
            evidence_refs=("posture_json", "operator_storage_report"),
            confidence_posture="MEDIUM_TRUST",
            safe_diagnostic_steps=(
                "Capture trace-growth clue as metadata only.",
                "If approved in a later lane, inspect Windows diagnostic settings read-only.",
            ),
            forbidden_actions=(
                "delete unknown Windows diagnostic caches",
                "disable Windows services from this package",
                "store raw ETL trace contents",
            ),
            what_would_make_quiet=(
                "Trace growth remains stable after normal Mac-to-PC workflow use.",
                "A bounded read-only diagnostic identifies the trace source or policy.",
            ),
        ),
        _signal(
            signal_id="shuttle_mount_missing",
            title="Mac shuttle mount missing",
            status="blocked",
            evidence_class="operator_reported_blocker_with_sync_context",
            observed_facts=(
                "PC-side proof still reports a waiting-for-Mac sync lifecycle.",
            ) if sync_present else (),
            operator_reported_facts=(
                "/Volumes/openclaw_e is missing on Mac.",
                "It should mount Windows E:\\openclaw / WSL /mnt/e/openclaw.",
                "Mac LaunchAgent com.openclaw.read-model-sync exits 0 but logs share_missing.",
            ),
            inferred_likely_causes=(
                "The Mac share path is unavailable, so normal shuttle completion cannot be trusted.",
            ),
            unknowns=(
                "Whether the Mac share is disconnected, renamed, permission-blocked, or delayed.",
                "No sanctioned auto-remount path is proven.",
            ),
            evidence_refs=("posture_json", "sync_health_json", "operator_mac_bridge_report"),
            confidence_posture="HIGH_TRUST" if sync_present else "MEDIUM_TRUST",
            safe_diagnostic_steps=(
                "Inspect Mac mount evidence and PC sync proof side by side.",
                "Ask Winship to confirm the Mac mount manually if needed.",
            ),
            forbidden_actions=(
                "auto-remount /Volumes/openclaw_e",
                "request or store remount credentials",
                "claim Mac mirror current without completion proof",
            ),
            what_would_make_quiet=(
                "/Volumes/openclaw_e is available again on Mac.",
                "Mac sync completion and PC import proof agree after the mount returns.",
            ),
        ),
        _signal(
            signal_id="sync_proof_stale",
            title="Sync proof stale",
            status="warning",
            evidence_class="observed_current_sync_health_plus_checkpoint_context",
            observed_facts=(
                f"Current PC sync health expected={current_sync['canonical_expected']} observed={current_sync['observed']} missing={current_sync['missing_expected']}.",
                f"Current sync lifecycle is {current_sync['sync_lifecycle_state']}.",
                f"Current hash mismatch count is {current_sync['hash_mismatch']}.",
            ) if sync_present else (
                "Current sync_health.json was not available to this package.",
            ),
            operator_reported_facts=(
                "Checkpoint before this diagnostic package expected 196 and observed 192.",
                "Checkpoint missing files were the two Chief posture files plus the two nested-lane spine files.",
                "Normal sync was waiting for Mac.",
            ),
            inferred_likely_causes=(
                "Mac sync has not yet completed the normal mirror leg for the newest generated files.",
            ),
            unknowns=(
                "Whether Mac-local files are ahead of PC proof.",
                "Whether the missing mount is the only blocker.",
            ),
            evidence_refs=("sync_health_json", "sync_health_operator", "operator_sync_checkpoint"),
            confidence_posture="HIGH_TRUST" if sync_present else "UNKNOWN_FAIL_CLOSED",
            safe_diagnostic_steps=(
                "Use sync_health.json as the current PC proof source.",
                "Wait for or inspect the normal Mac sync lifecycle; do not manually copy as the primary fix.",
            ),
            forbidden_actions=(
                "manual-copy generated files as the primary fix",
                "mark Mirror Current from stale proof",
                "run repair or remount automation from this package",
            ),
            what_would_make_quiet=(
                "canonical_expected equals observed.",
                "missing_expected=0 and hash_mismatch=0.",
                "sync_lifecycle_state is trusted_current or a clearly explained non-actionable lifecycle state.",
            ),
        ),
        _signal(
            signal_id="mac_local_mirror_vs_pc_proof_mismatch",
            title="Mac local mirror vs PC proof mismatch",
            status="warning",
            evidence_class="operator_reported_mac_local_state_not_canonical_truth",
            observed_facts=(
                f"PC proof currently observes {current_sync['observed']} files.",
            ) if sync_present else (),
            operator_reported_facts=(
                "Mac local helper previously pulled some newer mirror files locally.",
                "Full shuttle completion and PC import proof remain incomplete.",
            ),
            inferred_likely_causes=(
                "Mac-local visibility and PC-side proof are out of phase.",
            ),
            unknowns=(
                "Which Mac-local files are available to the app right now.",
                "Whether they came through the canonical shuttle or a helper path.",
            ),
            evidence_refs=("sync_health_json", "operator_mac_bridge_report"),
            confidence_posture="MEDIUM_TRUST",
            safe_diagnostic_steps=(
                "Compare Mac-local mirror evidence against PC manifest and completion receipts.",
                "Keep Mac-local file presence separate from canonical sync proof.",
            ),
            forbidden_actions=(
                "treat Mac-local helper results as canonical proof by themselves",
                "overwrite manifests from this package",
                "mutate Mission Control app paths from this package",
            ),
            what_would_make_quiet=(
                "Mac-visible files, Mac manifest, Mac completion, and PC import proof all agree.",
            ),
        ),
        _signal(
            signal_id="mac_codex_latency_validation_friction",
            title="Mac Codex latency and validation friction",
            status="warning",
            evidence_class="operator_reported_workbench_degradation",
            observed_facts=(
                "This package did not time Mac UI operations live.",
            ),
            operator_reported_facts=(
                "Mac Codex/Xcode UI lanes are slow and hard to track.",
                "A prior readability pass took about 54 minutes.",
                "Build, launch, and screenshot validation is valid but increasingly hard to track.",
            ),
            inferred_likely_causes=(
                "Workbench latency is degrading proof gathering, independent of app correctness.",
            ),
            unknowns=(
                "Whether slowdown is caused by Mac load, bridge latency, app tooling, Codex/Desktop state, or Xcode state.",
            ),
            evidence_refs=("posture_json", "operator_workbench_report"),
            confidence_posture="MEDIUM_TRUST",
            safe_diagnostic_steps=(
                "Separate app correctness from validation-friction diagnosis.",
                "Capture elapsed-time and window-state notes in a later inspect-only lane if needed.",
            ),
            forbidden_actions=(
                "install or change Mac tooling from this package",
                "mutate the Mission Control app as a first response",
                "launch agents or models to compensate for validation friction",
            ),
            what_would_make_quiet=(
                "Build, launch, and screenshot validation can be completed predictably and tracked clearly.",
            ),
        ),
        _signal(
            signal_id="screenshot_window_validation_fragility",
            title="Screenshot/window validation fragility",
            status="warning",
            evidence_class="operator_reported_validation_friction",
            observed_facts=(
                "This package did not run browser, screenshot, or app automation.",
            ),
            operator_reported_facts=(
                "Previous app validation had Mission Control/overview capture issues.",
                "window-state friction made validation harder to trust.",
            ),
            inferred_likely_causes=(
                "The visual validation surface is fragile enough to become a workbench reliability issue.",
            ),
            unknowns=(
                "Whether fragility is caused by app launch state, window focus, capture tooling, or operator workflow.",
            ),
            evidence_refs=("posture_json", "operator_workbench_report"),
            confidence_posture="MEDIUM_TRUST",
            safe_diagnostic_steps=(
                "Document validation gaps explicitly when proof capture is unreliable.",
                "Use deterministic read-model proof where possible until Mac visual proof stabilizes.",
            ),
            forbidden_actions=(
                "run browser or screenshot automation from this package",
                "hide validation gaps behind green status",
                "change Mission Control app code from this package",
            ),
            what_would_make_quiet=(
                "Mission Control launch and screenshot/readback proof are repeatable without window-state confusion.",
            ),
        ),
        _signal(
            signal_id="no_c_drive_write_policy",
            title="No C: drive write policy",
            status="ok",
            evidence_class="operator_policy_and_package_boundary",
            observed_facts=(
                "Generated package outputs are configured for generated/read_models under Repo A.",
            ),
            operator_reported_facts=(
                "No OpenClaw artifacts, caches, temp bundles, exports, generated outputs, or logs should be written to PC C:.",
                "Use /home/openclaw and established E: / /mnt/e/openclaw paths only.",
            ),
            inferred_likely_causes=(),
            unknowns=(
                "Whether all future lanes will preserve the policy without explicit tests.",
            ),
            evidence_refs=("posture_json", "operator_storage_policy"),
            confidence_posture="HIGH_TRUST",
            safe_diagnostic_steps=(
                "Keep C: paths as read-only evidence labels only.",
                "Static-check package code for generated writes limited to configured export roots.",
            ),
            forbidden_actions=(
                "create C: caches, temp bundles, exports, generated outputs, or logs",
                "use C: as fallback shuttle storage",
                "treat C: paths as OpenClaw artifact targets",
            ),
            what_would_make_quiet=(
                "Package and future check-engine lanes continue to avoid C: artifact writes.",
            ),
        ),
    ]


def _evidence_references(*, posture: dict[str, Any], sync_health: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _evidence_ref(
            ref_id="posture_json",
            evidence_type="observed",
            source_path=POSTURE_JSON,
            summary="Chief Check-Engine Environment Posture read-model.",
            fields={
                "present": bool(posture),
                "schema_version": posture.get("schema_version"),
                "check_engine_on": posture.get("check_engine", {}).get("check_engine_on"),
                "status": posture.get("check_engine", {}).get("status"),
                "signal_count": posture.get("signal_count"),
            },
        ),
        _evidence_ref(
            ref_id="posture_operator",
            evidence_type="observed_reference",
            source_path=POSTURE_OPERATOR,
            summary="Operator-readable posture output; body is not embedded in this package.",
        ),
        _evidence_ref(
            ref_id="sync_health_json",
            evidence_type="observed",
            source_path=SYNC_HEALTH_JSON,
            summary="Current PC/WSL canonical sync-health proof read-model.",
            fields={
                "present": bool(sync_health),
                **_sync_counts(sync_health),
            },
        ),
        _evidence_ref(
            ref_id="sync_health_operator",
            evidence_type="observed_reference",
            source_path=SYNC_HEALTH_OPERATOR,
            summary="Operator-readable sync-health output; body is not embedded in this package.",
        ),
        _evidence_ref(
            ref_id="operator_storage_report",
            evidence_type="operator_reported",
            source_path=None,
            summary="Operator-reported C: drive cleanup and RD trace culprit summary.",
            fields={
                "before_cleanup": OPERATOR_REPORTED_STORAGE_FACTS["c_drive_free_before_cleanup"],
                "freed": OPERATOR_REPORTED_STORAGE_FACTS["cleanup_freed_decimal"],
                "culprit": OPERATOR_REPORTED_STORAGE_FACTS["main_culprit"],
                "culprit_size": OPERATOR_REPORTED_STORAGE_FACTS["main_culprit_size"],
                "culprit_file_count": OPERATOR_REPORTED_STORAGE_FACTS["main_culprit_file_count"],
            },
        ),
        _evidence_ref(
            ref_id="operator_mac_bridge_report",
            evidence_type="operator_reported",
            source_path=None,
            summary="Operator-reported missing Mac shuttle mount and helper-pull context.",
            fields=dict(OPERATOR_REPORTED_MAC_BRIDGE_FACTS),
        ),
        _evidence_ref(
            ref_id="operator_sync_checkpoint",
            evidence_type="operator_reported",
            source_path=None,
            summary="Checkpoint sync facts before this diagnostic package added new generated files.",
            fields=dict(CHECKPOINT_SYNC_FACTS),
        ),
        _evidence_ref(
            ref_id="operator_workbench_report",
            evidence_type="operator_reported",
            source_path=None,
            summary="Operator-reported Mac Codex/Xcode/UI validation latency and fragility.",
            fields={
                **OPERATOR_REPORTED_WORKBENCH_FACTS,
                "readability_pass_example": "about 54 minutes",
            },
        ),
        _evidence_ref(
            ref_id="operator_storage_policy",
            evidence_type="operator_policy",
            source_path=None,
            summary="No OpenClaw artifacts should be written to PC C: in this workflow.",
            fields={
                "allowed_roots": ["/home/openclaw", "/mnt/e/openclaw"],
                "c_drive_artifact_writes_allowed": False,
            },
        ),
    ]


def _safe_diagnostic_steps() -> list[dict[str, Any]]:
    return [
        {
            "step_id": "inspect_current_read_models",
            "label": "Inspect current posture and sync read-models",
            "what_chief_can_inspect": [POSTURE_JSON, SYNC_HEALTH_JSON],
            "mode": "read_only_metadata",
            "must_not_do": ["mutate generated files by hand", "claim stale proof is current"],
        },
        {
            "step_id": "compare_operator_report_to_observed_proof",
            "label": "Compare operator-reported facts against observed PC proof",
            "what_chief_can_inspect": ["operator_reported fields", "sync_health counts", "posture signals"],
            "mode": "classification_only",
            "must_not_do": ["promote operator memory into observed fact", "hide unknowns"],
        },
        {
            "step_id": "separate_bridge_from_app_correctness",
            "label": "Separate Mac bridge/workbench failure from Mission Control app correctness",
            "what_chief_can_inspect": ["sync lifecycle", "mount blocker labels", "validation friction notes"],
            "mode": "diagnostic_reasoning_only",
            "must_not_do": ["change app code", "run screenshot/browser automation from this package"],
        },
        {
            "step_id": "identify_manual_operator_action",
            "label": "Identify whether Winship must manually restore/check the Mac mount",
            "what_chief_can_inspect": ["blocked mount signal", "sync lifecycle state"],
            "mode": "operator_question_only_if_needed",
            "must_not_do": ["auto-remount", "request credentials", "store credentials"],
        },
    ]


def _what_would_make_check_engine_quiet() -> list[str]:
    return [
        "C: drive remains safely above pressure thresholds and no OpenClaw artifact target writes to C:.",
        "RD Client trace growth is stable or has a bounded external explanation.",
        "/Volumes/openclaw_e is available on Mac or the missing mount has a documented non-actionable lifecycle state.",
        "sync_health reports missing_expected=0 and hash_mismatch=0 for the current expected set.",
        "Mac-local mirror, Mac manifest/completion, and PC import proof agree.",
        "Mac Codex/Xcode build/launch/screenshot validation becomes predictable enough to track.",
    ]


def build_chief_check_engine_diagnostic_package(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    posture = _read_json_if_present(POSTURE_JSON, repo_root=repo_root)
    sync_health = _read_json_if_present(SYNC_HEALTH_JSON, repo_root=repo_root)
    signals = _build_diagnostic_signals(posture=posture, sync_health=sync_health)
    evidence_refs = _evidence_references(posture=posture, sync_health=sync_health)
    current_sync = _sync_counts(sync_health)
    check_engine_on = bool(posture.get("check_engine", {}).get("check_engine_on", True))

    package_body = {
        "actor_model": "future_selected_model_not_live",
        "character": "Chief",
        "mission": "Diagnose workbench, bridge, and tooling degradation without repair authority.",
        "allowed_capability": "inspect_only_read_only_diagnostics",
        "forbidden": list(FORBIDDEN_ACTIONS),
        "stop_condition": "produce diagnosis, safe next step, and whether operator/manual action is required",
        "expected_output": [
            "plain-language diagnosis",
            "evidence table with observed/operator-reported/inferred/unknown distinctions",
            "blocked actions",
            "safe next diagnostic move",
            "manual operator action if required",
            "what would make Check Engine quiet",
        ],
    }

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "package_id": "chief_check_engine_diagnostic_package_v0",
        "owner": "Chief",
        "package_type": "check_engine_diagnostic",
        "authority": "inspect_only_no_repair_authority",
        "trigger": "check_engine_on",
        "check_engine_on": check_engine_on,
        "current_status": "blocked_needs_chief_diagnostic_package" if check_engine_on else "quiet_no_package_needed",
        "diagnostic_mission": package_body["mission"],
        "included_context": [
            "Chief check-engine environment posture summary",
            "current sync health counts and lifecycle state",
            "operator-reported C: cleanup and RD trace clue",
            "operator-reported Mac shuttle mount state",
            "operator-reported Mac Codex/Xcode validation friction",
            "no-C-drive-write policy",
        ],
        "excluded_context": [
            "credentials",
            "OAuth tokens",
            "raw private data",
            "raw logs unless explicitly approved in a later lane",
            "raw ETL trace contents",
            "broad Temp listings",
            "private file bodies",
        ],
        "evidence_references": evidence_refs,
        "degraded_signals": signals,
        "signal_count": len(signals),
        "likely_causes": [
            {
                "cause_id": "rd_client_trace_growth_external_to_repo_a",
                "confidence_posture": "MEDIUM_TRUST",
                "basis": "operator_reported trace directory size and file count",
                "not_proven": "not proven as an OpenClaw code loop",
            },
            {
                "cause_id": "mac_shuttle_mount_unavailable",
                "confidence_posture": "HIGH_TRUST" if sync_health else "MEDIUM_TRUST",
                "basis": "operator_reported missing /Volumes/openclaw_e plus observed waiting-for-Mac sync lifecycle",
                "not_proven": "root cause of missing Mac mount is not known",
            },
            {
                "cause_id": "mac_workbench_validation_friction",
                "confidence_posture": "MEDIUM_TRUST",
                "basis": "operator_reported slow UI lanes and fragile screenshot/window validation",
                "not_proven": "specific Mac tooling bottleneck is not isolated",
            },
        ],
        "unknowns": [
            "current live C: free space was not re-measured by this package",
            "whether RD Client trace growth will recur",
            "why /Volumes/openclaw_e is missing on Mac",
            "whether Mac-local helper files match canonical shuttle proof",
            "which Mac-side component causes validation latency or window-state fragility",
        ],
        "safe_diagnostic_steps": _safe_diagnostic_steps(),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "stop_conditions": [
            "produce diagnosis",
            "state safe next step",
            "state whether Winship/manual action is required",
            "preserve no-C-write and no-live-authority boundaries",
            "fail closed if proof is missing or contradictory",
        ],
        "operator_questions_if_needed": [
            {
                "question_id": "mac_mount_manual_status",
                "ask_only_if": "/Volumes/openclaw_e remains unavailable and PC proof still waits for Mac",
                "question": "Can Winship manually confirm whether /Volumes/openclaw_e is mounted or intentionally unavailable on Mac?",
                "operator_memory_is_not_truth": True,
            },
            {
                "question_id": "rd_trace_recurrence",
                "ask_only_if": "C: free-space pressure recurs",
                "question": "Has Windows App / Remote Desktop been used since cleanup, and did C: free space drop again?",
                "operator_memory_is_not_truth": True,
            },
        ],
        "future_gated_repair_cleanup_remount_posture": {
            "repair_lane_required": True,
            "cleanup_lane_required": True,
            "remount_lane_required": True,
            "credentials_required_for_remount": "unknown_fail_closed",
            "this_package_may_execute_repair": False,
            "this_package_may_delete": False,
            "this_package_may_remount": False,
            "this_package_may_handle_credentials": False,
        },
        "expected_output_if_handed_to_chief_later": package_body["expected_output"],
        "chief_package_body_preview": package_body,
        "what_chief_should_inspect_first": [
            "sync_proof_stale",
            "shuttle_mount_missing",
            "mac_local_mirror_vs_pc_proof_mismatch",
            "c_drive_free_space_pressure",
        ],
        "winship_manual_action": {
            "required_now_by_this_package": False,
            "may_be_needed_if": "/Volumes/openclaw_e remains unavailable or Mac sync proof does not advance",
            "likely_manual_action": "manually check or restore the Mac E: shuttle mount outside this package",
        },
        "what_would_make_check_engine_quiet": _what_would_make_check_engine_quiet(),
        "current_sync_health_posture": {
            "checkpoint_before_package": dict(CHECKPOINT_SYNC_FACTS),
            "observed_current": current_sync,
            "source_path": SYNC_HEALTH_JSON,
        },
        "storage_policy": {
            "do_not_write_openclaw_artifacts_to_pc_c_drive": True,
            "allowed_openclaw_artifact_roots": ["/home/openclaw", "/mnt/e/openclaw"],
            "c_drive_read_only_inspection_allowed_for_posture_evidence": True,
            "delete_anything_in_this_lane": False,
            "generated_output_root": "generated/read_models",
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
            "raw_trace_contents_stored": False,
            "runtime_activation_recorded": False,
            "sqlite_schema_changed": False,
            "receipt_writer_function": "record_chief_check_engine_diagnostic_package_receipt",
        },
        "machine_proof": {
            "source_read_models": [POSTURE_JSON, SYNC_HEALTH_JSON],
            "source_files": [
                "chief_check_engine_diagnostic_package.py",
                "chief_check_engine_environment_posture.py",
                "scripts/export_chief_check_engine_diagnostic_package.py",
            ],
            "generated_outputs": [
                f"generated/read_models/{JSON_EXPORT_NAME}",
                f"generated/read_models/{OPERATOR_EXPORT_NAME}",
            ],
            "proof_limit": "Operator reports are labeled as operator_reported and not promoted to observed truth.",
        },
        "next_recommended_lane": {
            "lane_name": "Chief Check-Engine Readback and Manual Mount Decision v0",
            "goal": "Show this package in Mission Control and decide whether a separate manual Mac mount diagnostic is needed.",
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
            "package_id": payload["package_id"],
            "degraded_signals": payload["degraded_signals"],
            "current_sync_health_posture": payload["current_sync_health_posture"],
            "storage_policy": payload["storage_policy"],
            "chief_package_body_preview": payload["chief_package_body_preview"],
        }
    )
    return payload


def format_chief_check_engine_diagnostic_package(payload: dict[str, Any]) -> str:
    lines = [
        "Chief Check-Engine Diagnostic Package v0",
        "",
        "Status:",
        f"- Check Engine: {'ON' if payload['check_engine_on'] else 'OFF'}",
        f"- Current status: `{payload['current_status']}`",
        "- Package authority: inspect-only, no repair authority.",
        "",
        "Why Check Engine Is On:",
        "- Workbench/bridge proof is degraded enough to need a Chief diagnostic package.",
        "- The current issue is system/workbench reliability, not normal domain lane attention.",
        "",
        "What Degraded:",
    ]
    for signal in payload["degraded_signals"]:
        lines.append(f"- {signal['signal_id']}: {signal['title']} ({signal['status']}, {signal['confidence_posture']})")

    lines.extend(
        [
            "",
            "Evidence:",
        ]
    )
    for ref in payload["evidence_references"]:
        lines.append(f"- {ref['ref_id']}: {ref['evidence_type']} - {ref['summary']}")

    lines.extend(
        [
            "",
            "Likely Vs Unknown:",
        ]
    )
    for cause in payload["likely_causes"]:
        lines.append(f"- Likely: {cause['cause_id']} ({cause['confidence_posture']}); not proven: {cause['not_proven']}.")
    for unknown in payload["unknowns"]:
        lines.append(f"- Unknown: {unknown}.")

    lines.extend(
        [
            "",
            "Inspect First:",
        ]
    )
    for item in payload["what_chief_should_inspect_first"]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "Safe Diagnostic Steps:",
        ]
    )
    for step in payload["safe_diagnostic_steps"]:
        lines.append(f"- {step['step_id']}: {step['label']} ({step['mode']}).")

    lines.extend(
        [
            "",
            "Must Not Do:",
        ]
    )
    for action in payload["forbidden_actions"]:
        lines.append(f"- {action}")

    lines.extend(
        [
            "",
            "Winship Manual Action:",
            f"- Required now by this package: `{str(payload['winship_manual_action']['required_now_by_this_package']).lower()}`",
            f"- May be needed if: {payload['winship_manual_action']['may_be_needed_if']}",
            "",
            "What Would Make Check Engine Quiet:",
        ]
    )
    for item in payload["what_would_make_check_engine_quiet"]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "Future-Gated:",
            "- Repair, cleanup, remount, credential handling, app mutation, runtime execution, model calls, agents, browser/OAuth, Gmail/calendar/Coupa/Telegram, send/submit/approval.",
            "",
            "Storage Boundary:",
            "- OpenClaw artifacts must not be written to C:.",
            "- Generated output remains under `generated/read_models/` in Repo A.",
            "- C: references here are evidence labels only, not artifact targets.",
            "",
            "Expected Chief Output Later:",
        ]
    )
    for item in payload["expected_output_if_handed_to_chief_later"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def export_chief_check_engine_diagnostic_package(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> CheckEngineDiagnosticPackageExportResult:
    payload = build_chief_check_engine_diagnostic_package(
        repo_root=repo_root,
        generated_at=generated_at,
    )
    out_dir = _rooted(export_root, repo_root=repo_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_chief_check_engine_diagnostic_package(payload), encoding="utf-8")
    return CheckEngineDiagnosticPackageExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        package_id=payload["package_id"],
        signal_count=payload["signal_count"],
        check_engine_on=payload["check_engine_on"],
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


def _find_existing_diagnostic_package_receipt(
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


def record_chief_check_engine_diagnostic_package_receipt(
    *,
    repo_root: str | Path = ROOT,
    db_path: str | Path | None = None,
    commit_hash: str | None = None,
    generated_at: str | None = None,
    ensure: bool = True,
) -> str:
    """Record a metadata-only receipt for this diagnostic package."""
    payload = build_chief_check_engine_diagnostic_package(
        repo_root=repo_root,
        generated_at=generated_at,
    )
    receipt_hash = payload["receipt_hash"]
    if ensure:
        existing = _find_existing_diagnostic_package_receipt(
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
        "package_id": payload["package_id"],
        "signal_ids": [signal["signal_id"] for signal in payload["degraded_signals"]],
        "check_engine_on": payload["check_engine_on"],
        "metadata_only": True,
        "raw_logs_stored": False,
        "raw_trace_contents_stored": False,
        "credentials_stored": False,
        "broad_temp_listing_stored": False,
        "raw_private_content_stored": False,
        "cleanup_proof_stored": False,
        "c_drive_artifact_written": False,
        "runtime_activation": False,
        "authority_flags": dict(NO_AUTHORITY_FLAGS),
    }
    return record_receipt(
        receipt_type="generated_status",
        payload=receipt_payload,
        commit_hash=commit_hash,
        artifact_type="chief_check_engine_diagnostic_package",
        artifact_status="captured_metadata_only",
        authority_status="generated_status_only",
        runtime_activation=False,
        sqlite_meaning="receipt_record_only",
        source_basis=[
            POSTURE_JSON,
            SYNC_HEALTH_JSON,
            "operator_prompt: Chief Check-Engine Diagnostic Package v0",
        ],
        actor="chief_check_engine_diagnostic_package_v0",
        created_at=generated_at,
        db_path=str(db_path) if db_path else None,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Chief check-engine diagnostic package read-model.")
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
    result = export_chief_check_engine_diagnostic_package(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    receipt_id = ""
    if args.record_receipt:
        receipt_id = record_chief_check_engine_diagnostic_package_receipt(
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
    "CHECKPOINT_SYNC_FACTS",
    "CONFIDENCE_POSTURES",
    "JSON_EXPORT_NAME",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "SCHEMA_VERSION",
    "build_chief_check_engine_diagnostic_package",
    "export_chief_check_engine_diagnostic_package",
    "format_chief_check_engine_diagnostic_package",
    "record_chief_check_engine_diagnostic_package_receipt",
    "stable_json",
]


if __name__ == "__main__":
    raise SystemExit(main())

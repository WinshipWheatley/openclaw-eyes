"""Sync Health v0 for OpenClaw read-model mirror trust.

This module records and exports a bounded health snapshot for the Mac/PC
generated read-model mirror. It reads manifest/marker/state/log metadata only.
It does not run sync, control another machine, delete files, move files, or
modify Mission Control.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger
from generated_read_model_files import (
    VOLATILE_SELF_REPORT_READ_MODEL_FILES,
    canonical_generated_read_model_records,
)


ROOT = Path(__file__).resolve().parent
SYNC_HEALTH_VERSION = "sync_health_v0"
READ_MODEL_VERSION = "sync_health_read_model_v0"
DEFAULT_READ_MODEL_ROOT = Path("generated/read_models")
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
JSON_EXPORT_NAME = "sync_health.json"
OPERATOR_EXPORT_NAME = "sync_health_OPERATOR.md"
SELF_EXPORT_FILES = frozenset(VOLATILE_SELF_REPORT_READ_MODEL_FILES)
OPERATOR_INTERRUPT_POLICY = (
    "routine sync lifecycle states stay in proof/detail; only unresolved "
    "actionable failures should interrupt the operator"
)
ROUTINE_SYNC_LIFECYCLE_STATES = frozenset(
    {
        "trusted_current",
        "sync_requested_waiting_for_mac",
        "mac_synced_waiting_for_pc_import",
        "pc_imported_waiting_for_health_export",
        "health_exported_waiting_for_mac_mirror",
    }
)
ACTIONABLE_SYNC_LIFECYCLE_STATES = frozenset({"actionable_sync_failure"})

DEFAULT_PC_SHARE_ROOT = Path("/mnt/e/openclaw")
DEFAULT_MANIFEST_PATH = DEFAULT_PC_SHARE_ROOT / "mac_generated_read_models_manifest.json"
DEFAULT_REQUEST_MARKER_PATH = DEFAULT_PC_SHARE_ROOT / "shuttle" / "to_mac" / "read_model_sync_required.json"
DEFAULT_APP_REQUEST_MARKER_PATH = "/Volumes/openclaw_e/shuttle/to_mac/read_model_sync_required.json"
DEFAULT_MAC_STATUS_PATH = DEFAULT_PC_SHARE_ROOT / "shuttle" / "from_mac" / "read_model_sync_agent_status.json"
DEFAULT_MAC_COMPLETION_PATH = DEFAULT_PC_SHARE_ROOT / "shuttle" / "from_mac" / "read_model_sync_completed.json"
DEFAULT_PC_IMPORT_STATE_PATH = ROOT / ".openclaw" / "state" / "read_model_import_agent_state.json"
DEFAULT_PC_TASK_LOG_PATH = ROOT / ".openclaw" / "logs" / "windows_task_read_model_import.log"
DEFAULT_WINDOWS_TASK_LOG_PATH = DEFAULT_PC_SHARE_ROOT / "windows_tasks" / "logs" / "OpenClawReadModelImport.log"
DEFAULT_MAP_SYNC_REQUEST_MARKER_PATH = DEFAULT_PC_SHARE_ROOT / "shuttle" / "to_mac" / "openclaw_map_sync_required.json"
DEFAULT_MAP_RECEIPT_PATH = DEFAULT_PC_SHARE_ROOT / "shuttle" / "from_mac" / "openclaw_map_receipt.json"
DEFAULT_APP_MAP_RECEIPT_PATH = "/Users/hwinshipwheatley/openclaw_generated_read_models/openclaw_map_receipt.json"
DEFAULT_MAC_LOCAL_MAP_ROOT = "/Users/hwinshipwheatley/openclaw_generated_read_models"

STABLE_MAP_REQUIRED_FILES = (
    "openclaw_map_snapshot.json",
    "openclaw_map_manifest.json",
    "openclaw_map_OPERATOR.md",
)
STABLE_MAP_OPTIONAL_RECEIPT_FILE = "openclaw_map_receipt.json"
STABLE_MAP_STATUS_VALUES = (
    "map_current",
    "map_generation_pending_mac_import",
    "map_imported_waiting_pc_readback",
    "map_missing_from_mac",
    "map_hash_mismatch",
    "map_receipt_missing",
    "unknown_fail_closed",
)
STABLE_MAP_SCHEMA_VERSION = "openclaw_map_manifest_v0"
STABLE_MAP_RECEIPT_SCHEMA_VERSION = "openclaw_map_receipt_v0"
ACCEPTED_PARTIAL_MAP_RECEIPT_STATUSES = frozenset(
    {
        "PARTIAL_TOP_LEVEL_AGENT_DOSSIER_CARDS_PATH_MISMATCH",
    }
)

NO_AUTHORITY_FLAGS = {
    "app_direct_execution_allowed": False,
    "arbitrary_command_allowed": False,
    "remote_control_allowed": False,
    "ssh_scp_rsync_allowed": False,
    "docker_ollama_allowed": False,
    "runtime_activation_allowed": False,
    "agent_activation_allowed": False,
    "file_delete_allowed": False,
    "file_move_allowed": False,
}

MAP_SYNC_NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "agent_activation_allowed": False,
    "model_execution_allowed": False,
    "tool_plugin_execution_allowed": False,
    "browser_oauth_account_access_allowed": False,
    "gmail_calendar_coupa_telegram_allowed": False,
    "credential_handling_allowed": False,
    "network_authority": False,
    "send_submit_approval_allowed": False,
    "file_delete_allowed": False,
    "file_move_allowed": False,
    "cleanup_remount_repair_allowed": False,
    "pc_c_drive_artifact_write_allowed": False,
}


@dataclass(frozen=True)
class SyncHealthBuildResult:
    run_id: str
    snapshot_id: str
    trust_status: str
    mirror_status: str
    recommended_fix_kind: str
    sync_lifecycle_state: str
    operator_action_required: bool
    db_path: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:20]}"


def _display_path(path: str | Path, *, repo_root: str | Path = ROOT) -> str:
    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(Path(repo_root).resolve()).as_posix()
    except (OSError, ValueError):
        return path_obj.as_posix()


def _sql_statements() -> tuple[str, ...]:
    return (
        """
CREATE TABLE IF NOT EXISTS sync_health_runs (
  run_id TEXT PRIMARY KEY,
  sync_health_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  trust_status TEXT NOT NULL,
  mirror_status TEXT NOT NULL,
  recommended_fix_kind TEXT NOT NULL,
  app_direct_execution_allowed INTEGER NOT NULL DEFAULT 0,
  arbitrary_command_allowed INTEGER NOT NULL DEFAULT 0,
  remote_control_allowed INTEGER NOT NULL DEFAULT 0,
  ssh_scp_rsync_allowed INTEGER NOT NULL DEFAULT 0,
  docker_ollama_allowed INTEGER NOT NULL DEFAULT 0,
  runtime_activation_allowed INTEGER NOT NULL DEFAULT 0,
  agent_activation_allowed INTEGER NOT NULL DEFAULT 0,
  file_delete_allowed INTEGER NOT NULL DEFAULT 0,
  file_move_allowed INTEGER NOT NULL DEFAULT 0
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS sync_health_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  trust_status TEXT NOT NULL,
  mirror_status TEXT NOT NULL,
  canonical_expected INTEGER NOT NULL DEFAULT 0,
  observed INTEGER NOT NULL DEFAULT 0,
  missing_expected INTEGER NOT NULL DEFAULT 0,
  extra INTEGER NOT NULL DEFAULT 0,
  hash_mismatch INTEGER NOT NULL DEFAULT 0,
  matched_hash INTEGER NOT NULL DEFAULT 0,
  stale_files_json TEXT NOT NULL,
  missing_files_json TEXT NOT NULL,
  extra_files_json TEXT NOT NULL,
  mac_heartbeat_status TEXT,
  mac_heartbeat_time TEXT,
  mac_marker_seen INTEGER NOT NULL DEFAULT 0,
  mac_manifest_written INTEGER NOT NULL DEFAULT 0,
  mac_completion_status TEXT,
  mac_completion_time TEXT,
  pc_import_status TEXT,
  pc_import_time TEXT,
  pc_manifest_hash TEXT,
  windows_task_log_present INTEGER NOT NULL DEFAULT 0,
  pc_scheduler_known INTEGER NOT NULL DEFAULT 0,
  display_status TEXT NOT NULL DEFAULT 'unknown_review',
  sync_lifecycle_state TEXT NOT NULL DEFAULT 'unknown_review',
  operator_action_required INTEGER NOT NULL DEFAULT 0,
  operator_interrupt_policy TEXT NOT NULL DEFAULT 'actionable_failures_only',
  next_expected_actor TEXT NOT NULL DEFAULT 'operator_review',
  next_safe_move TEXT NOT NULL,
  recommended_fix_kind TEXT NOT NULL,
  can_request_fix_from_app INTEGER NOT NULL DEFAULT 0,
  request_marker_path TEXT NOT NULL,
  app_request_marker_path TEXT NOT NULL,
  no_authority_json TEXT NOT NULL,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (run_id) REFERENCES sync_health_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS sync_health_sources (
  source_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  source_path TEXT NOT NULL,
  present INTEGER NOT NULL DEFAULT 0,
  observed_at TEXT NOT NULL,
  source_status TEXT,
  source_time TEXT,
  source_hash TEXT,
  raw_body_stored INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (run_id) REFERENCES sync_health_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS sync_health_recommendations (
  recommendation_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  recommended_fix_kind TEXT NOT NULL,
  next_safe_move TEXT NOT NULL,
  next_expected_actor TEXT NOT NULL DEFAULT 'operator_review',
  can_request_fix_from_app INTEGER NOT NULL DEFAULT 0,
  request_marker_path TEXT NOT NULL,
  app_request_marker_path TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES sync_health_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        """
CREATE TABLE IF NOT EXISTS sync_health_receipts (
  receipt_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  receipt_kind TEXT NOT NULL,
  summary TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES sync_health_runs(run_id) ON DELETE CASCADE
)
""".strip(),
        "CREATE INDEX IF NOT EXISTS idx_sync_health_snapshots_generated ON sync_health_snapshots(generated_at)",
        "CREATE INDEX IF NOT EXISTS idx_sync_health_snapshots_trust ON sync_health_snapshots(trust_status)",
    )


def _ensure_sync_health_columns(conn: sqlite3.Connection) -> None:
    table_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(sync_health_snapshots)").fetchall()
    }
    if "display_status" not in table_columns:
        conn.execute("ALTER TABLE sync_health_snapshots ADD COLUMN display_status TEXT NOT NULL DEFAULT 'unknown_review'")
    if "next_expected_actor" not in table_columns:
        conn.execute("ALTER TABLE sync_health_snapshots ADD COLUMN next_expected_actor TEXT NOT NULL DEFAULT 'operator_review'")
    if "sync_lifecycle_state" not in table_columns:
        conn.execute("ALTER TABLE sync_health_snapshots ADD COLUMN sync_lifecycle_state TEXT NOT NULL DEFAULT 'unknown_review'")
    if "operator_action_required" not in table_columns:
        conn.execute("ALTER TABLE sync_health_snapshots ADD COLUMN operator_action_required INTEGER NOT NULL DEFAULT 0")
    if "operator_interrupt_policy" not in table_columns:
        conn.execute("ALTER TABLE sync_health_snapshots ADD COLUMN operator_interrupt_policy TEXT NOT NULL DEFAULT 'actionable_failures_only'")

    recommendation_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(sync_health_recommendations)").fetchall()
    }
    if "next_expected_actor" not in recommendation_columns:
        conn.execute("ALTER TABLE sync_health_recommendations ADD COLUMN next_expected_actor TEXT NOT NULL DEFAULT 'operator_review'")


def init_sync_health_schema(db_path: str | Path | None = None) -> str:
    path = str(db_path or DEFAULT_DB_PATH)
    parent = Path(path).parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
    init_business_ops_ledger(path)
    conn = sqlite3.connect(path)
    try:
        for statement in _sql_statements():
            conn.execute(statement)
        _ensure_sync_health_columns(conn)
        conn.commit()
    finally:
        conn.close()
    return path


def sync_health_table_names(db_path: str | Path | None = None) -> tuple[str, ...]:
    path = init_sync_health_schema(db_path)
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
SELECT name
FROM sqlite_master
WHERE type = 'table' AND name LIKE 'sync_health%'
ORDER BY name
""".strip()
        ).fetchall()
        return tuple(row[0] for row in rows)
    finally:
        conn.close()


def _read_json_object(path: str | Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _manifest_relative_paths(path: str | Path) -> set[str]:
    payload = _read_json_object(path) or {}
    records = payload.get("path_records") or []
    return {
        record.get("relative_path")
        for record in records
        if isinstance(record, dict) and isinstance(record.get("relative_path"), str)
    }


def _sha256_prefixed(path: str | Path) -> str | None:
    digest = sha256_file(path)
    return f"sha256:{digest}" if digest else None


def _map_manifest_payload(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
) -> dict[str, Any]:
    path = Path(read_model_root) / "openclaw_map_manifest.json"
    return _read_json_object(path) or {}


def _map_snapshot_surface_status(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
) -> dict[str, Any]:
    snapshot = _read_json_object(Path(read_model_root) / "openclaw_map_snapshot.json") or {}
    security_audit = (
        snapshot.get("security_audit_readiness")
        if isinstance(snapshot.get("security_audit_readiness"), dict)
        else {}
    )
    security_pass = (
        snapshot.get("security_pass")
        if isinstance(snapshot.get("security_pass"), dict)
        else {}
    )
    post_security_governance_batch = (
        snapshot.get("post_security_governance_batch")
        if isinstance(snapshot.get("post_security_governance_batch"), dict)
        else {}
    )
    parked_capital_experiment = (
        snapshot.get("parked_autonomous_capital_pipeline_experiment")
        if isinstance(snapshot.get("parked_autonomous_capital_pipeline_experiment"), dict)
        else {}
    )
    security_delta_review = (
        snapshot.get("security_delta_review")
        if isinstance(snapshot.get("security_delta_review"), dict)
        else {}
    )
    operator_attention_promotion = (
        snapshot.get("operator_attention_promotion")
        if isinstance(snapshot.get("operator_attention_promotion"), dict)
        else {}
    )
    chief_test_harness_cross_off = (
        snapshot.get("chief_test_harness_cross_off")
        if isinstance(snapshot.get("chief_test_harness_cross_off"), dict)
        else {}
    )
    post_security_governance_authority = (
        post_security_governance_batch.get("authority_boundary")
        if isinstance(post_security_governance_batch.get("authority_boundary"), dict)
        else {}
    )
    worker_orphan_summary = (
        security_pass.get("worker_output_orphaned_capability_summary")
        if isinstance(security_pass.get("worker_output_orphaned_capability_summary"), dict)
        else {}
    )
    chief_hermes_summary = (
        security_pass.get("chief_hermes_trust_summary")
        if isinstance(security_pass.get("chief_hermes_trust_summary"), dict)
        else {}
    )
    coverage_gap_summary = (
        security_audit.get("coverage_gap_summary")
        if isinstance(security_audit.get("coverage_gap_summary"), dict)
        else {}
    )
    parked_breadcrumb_summary = (
        security_audit.get("parked_breadcrumb_summary")
        if isinstance(security_audit.get("parked_breadcrumb_summary"), dict)
        else {}
    )
    package_surface = snapshot.get("package_preview_receipts") if isinstance(snapshot.get("package_preview_receipts"), dict) else {}
    package_cards = package_surface.get("package_preview_cards") if isinstance(package_surface.get("package_preview_cards"), list) else []
    package_ids = {
        card.get("package_id")
        for card in package_cards
        if isinstance(card, dict) and isinstance(card.get("package_id"), str)
    }
    tool_surface = snapshot.get("tool_adapter_receipts") if isinstance(snapshot.get("tool_adapter_receipts"), dict) else {}
    adapter_cards = tool_surface.get("adapter_receipt_cards") if isinstance(tool_surface.get("adapter_receipt_cards"), list) else []
    adapter_ids = {
        card.get("adapter_id")
        for card in adapter_cards
        if isinstance(card, dict) and isinstance(card.get("adapter_id"), str)
    }
    agent_council = snapshot.get("agent_council") if isinstance(snapshot.get("agent_council"), dict) else {}
    agent_cards = agent_council.get("agent_dossier_cards") if isinstance(agent_council.get("agent_dossier_cards"), list) else []
    agent_ids = {
        card.get("agent_id")
        for card in agent_cards
        if isinstance(card, dict) and isinstance(card.get("agent_id"), str)
    }
    threshold = snapshot.get("threshold_map") if isinstance(snapshot.get("threshold_map"), dict) else {}
    authority = snapshot.get("authority_boundary") if isinstance(snapshot.get("authority_boundary"), dict) else {}
    capital_hilton = (
        snapshot.get("capital_hilton_proof_metadata")
        if isinstance(snapshot.get("capital_hilton_proof_metadata"), dict)
        else {}
    )
    capital_hilton_proof_intake = (
        snapshot.get("capital_hilton_protected_proof_intake")
        if isinstance(snapshot.get("capital_hilton_protected_proof_intake"), dict)
        else {}
    )
    capital_authority = (
        capital_hilton.get("authority_boundary")
        if isinstance(capital_hilton.get("authority_boundary"), dict)
        else {}
    )
    capital_facts = (
        capital_hilton.get("candidate_facts")
        if isinstance(capital_hilton.get("candidate_facts"), list)
        else []
    )
    proof_intake_items = (
        capital_hilton_proof_intake.get("proof_item_summaries")
        if isinstance(capital_hilton_proof_intake.get("proof_item_summaries"), list)
        else []
    )
    proof_intake_authority_flags_false = bool(
        not capital_hilton_proof_intake
        or (
            capital_hilton_proof_intake.get("action_authority_granted") is False
            and capital_hilton_proof_intake.get("invoice_generation_allowed") is False
            and capital_hilton_proof_intake.get("coupa_access_allowed") is False
            and capital_hilton_proof_intake.get("browser_oauth_account_access_allowed") is False
            and capital_hilton_proof_intake.get("gmail_calendar_email_access_allowed") is False
            and capital_hilton_proof_intake.get("credential_handling_allowed") is False
            and capital_hilton_proof_intake.get("send_submit_approval_allowed") is False
        )
    )
    no_live_execution_authority = bool(
        authority.get("live_package_dispatch_allowed") is False
        and authority.get("model_actor_execution_allowed") is False
        and authority.get("plugin_tool_execution_allowed") is False
        and authority.get("agent_activation_allowed") is False
        and authority.get("runtime_activation_allowed") is False
        and authority.get("send_submit_approval_allowed") is False
        and capital_authority.get("runtime_dispatch_allowed", False) is False
        and capital_authority.get("tool_execution_allowed", False) is False
        and capital_authority.get("agent_activation_allowed", False) is False
        and capital_authority.get("model_call_allowed", False) is False
        and capital_authority.get("send_submit_approval_allowed", False) is False
        and proof_intake_authority_flags_false
    )
    no_credentials_or_secrets = bool(
        snapshot.get("credentials_included") is False
        and snapshot.get("secrets_included") is False
        and capital_hilton.get("credential_or_secret_included", False) is False
        and capital_hilton_proof_intake.get("credential_handling_allowed", False) is False
    )
    raw_private_absent = bool(
        snapshot.get("raw_private_bodies_included") is False
        and capital_hilton.get("raw_finance_body_included", False) is False
        and capital_hilton_proof_intake.get("raw_finance_body_ingestion_allowed", False) is False
        and capital_hilton_proof_intake.get("raw_private_body_ingestion_allowed", False) is False
    )
    return {
        "snapshot_surface_parse_passed": bool(snapshot),
        "package_preview_summary_present": bool(package_surface.get("present") is True or package_surface),
        "package_preview_example_count": int(
            package_surface.get("example_package_previews_count") or len(package_cards) or 0
        ),
        "cassandra_capital_hilton_preview_present": "package_cassandra_capital_hilton_invoice_review" in package_ids,
        "chief_check_engine_preview_present": "package_chief_check_engine_diagnostic" in package_ids,
        "agentic_loop_classification_preview_present": "package_agentic_loop_classification" in package_ids,
        "tool_adapter_receipt_summary_present": bool(tool_surface.get("present") is True or tool_surface),
        "tool_adapter_receipt_example_count": int(
            tool_surface.get("adapter_examples_count") or len(adapter_cards) or 0
        ),
        "stable_map_reader_adapter_present": "stable_map_bundle_reader" in adapter_ids,
        "cassandra_capital_hilton_adapter_present": "cassandra_capital_hilton_invoice_proof_adapter" in adapter_ids,
        "browser_oauth_blocked_adapter_present": "browser_oauth_adapter" in adapter_ids,
        "gmail_calendar_blocked_adapter_present": "gmail_calendar_adapter" in adapter_ids,
        "coupa_blocked_adapter_present": "coupa_adapter" in adapter_ids,
        "telegram_blocked_adapter_present": "telegram_adapter" in adapter_ids,
        "agent_council_present": bool(agent_council.get("present") is True or agent_council),
        "agent_dossier_cards_count": int(agent_council.get("agent_dossier_cards_count") or len(agent_cards) or 0),
        "cassandra_card_present": "cassandra" in agent_ids,
        "system_loop_cards_present": {
            "agentic_loop",
            "cue_parser_brain_dump_parser",
            "repo_b_planner_builder_orchestrator",
            "package_compiler",
            "model_router",
            "tool_plugin_registry",
        } <= agent_ids,
        "no_image_body_embedded": bool(agent_council.get("image_body_embedded") is False),
        "capital_hilton_summary_present": bool(capital_hilton.get("present") is True or capital_hilton),
        "capital_hilton_current_phase": capital_hilton.get("current_phase"),
        "capital_hilton_target_world": capital_hilton.get("target_world"),
        "capital_hilton_lane_destiny": capital_hilton.get("lane_destiny"),
        "capital_hilton_missing_proof_count": int(capital_hilton.get("missing_proof_count") or 0),
        "capital_hilton_protected_proof_required": bool(capital_hilton.get("protected_proof_required") is True),
        "capital_hilton_candidate_facts_marked_not_proven": bool(
            capital_hilton.get("all_candidate_facts_marked_not_proven") is True
            or (
                bool(capital_facts)
                and all(
                    isinstance(item, dict) and item.get("machine_proven") is False
                    for item in capital_facts
                )
            )
        ),
        "capital_hilton_operator_questions_count": len(
            capital_hilton.get("operator_memory_questions")
            if isinstance(capital_hilton.get("operator_memory_questions"), list)
            else []
        ),
        "capital_hilton_authority_flags_false": bool(
            capital_hilton.get("live_execution_authority") is False
            and all(value is False for value in capital_authority.values())
        ),
        "capital_hilton_protected_proof_intake_present": bool(
            capital_hilton_proof_intake.get("present") is True or capital_hilton_proof_intake
        ),
        "capital_hilton_protected_proof_intake_proof_items_count": int(
            capital_hilton_proof_intake.get("proof_items_count") or len(proof_intake_items) or 0
        ),
        "capital_hilton_protected_proof_intake_missing_proof_count": int(
            capital_hilton_proof_intake.get("missing_proof_count") or 0
        ),
        "capital_hilton_protected_proof_intake_protected_proof_required": bool(
            capital_hilton_proof_intake.get("protected_proof_required") is True
        ),
        "capital_hilton_protected_proof_intake_candidate_facts_proven": bool(
            capital_hilton_proof_intake.get("candidate_facts_proven") is True
        ),
        "capital_hilton_protected_proof_intake_action_authority_granted": bool(
            capital_hilton_proof_intake.get("action_authority_granted") is True
        ),
        "capital_hilton_protected_proof_intake_guardian_gates_present": bool(
            int(capital_hilton_proof_intake.get("guardian_gates_count") or 0) > 0
        ),
        "capital_hilton_protected_proof_intake_operator_answer_candidates_present": bool(
            int(capital_hilton_proof_intake.get("operator_answer_candidates_count") or 0) > 0
        ),
        "capital_hilton_protected_proof_intake_protected_evidence_requirements_present": bool(
            int(capital_hilton_proof_intake.get("protected_evidence_requirements_count") or 0) > 0
        ),
        "capital_hilton_protected_proof_intake_authority_flags_false": proof_intake_authority_flags_false,
        "capital_hilton_finance_present": bool(
            capital_hilton.get("target_world") == "Finance"
            or (isinstance(threshold.get("capital_hilton_finance_destiny"), dict)
                and threshold["capital_hilton_finance_destiny"].get("target_world") == "Finance")
        ),
        "system_awareness_discovery_present": bool(threshold.get("system_awareness_discovery_steel_thread")),
        "future_gated_cue_autonomy_present": bool(
            authority.get("future_gated_cue_autonomy") is True
            or threshold.get("cue_autonomy_placement")
        ),
        "operator_memory_not_proof": bool(
            snapshot.get("operator_memory_not_proof") is True
            or capital_hilton.get("operator_answers_become_memory_candidate_receipts_not_proof") is True
            or threshold.get("operator_memory_rule") == "operator_memory_becomes_candidate_context_not_machine_proof"
        ),
        "no_live_execution_authority": no_live_execution_authority,
        "raw_private_body_absent": raw_private_absent,
        "no_credentials_secrets_embedded": no_credentials_or_secrets,
        "security_audit_readiness_present": bool(security_audit.get("present") is True or security_audit),
        "ready_for_security_pass": bool(security_audit.get("ready_for_security_pass") is True),
        "security_approval_granted": bool(security_audit.get("security_approval_granted") is True),
        "action_authority_granted": bool(security_audit.get("action_authority_granted") is True),
        "coverage_gap_records_count": int(coverage_gap_summary.get("coverage_gap_records_count") or 0),
        "parked_breadcrumb_count": int(parked_breadcrumb_summary.get("parked_breadcrumb_count") or 0),
        "capital_hilton_security_readiness_present": bool(
            security_audit.get("capital_hilton_security_readiness_present") is True
        ),
        "security_all_authority_flags_false": bool(
            security_audit.get("all_authority_flags_false") is True
            and security_audit.get("zero_execution_authority_leaked") is True
            and security_audit.get("security_approval_granted") is False
            and security_audit.get("action_authority_granted") is False
        ),
        "security_pass_present": bool(security_pass.get("present") is True or security_pass),
        "security_pass_completed": bool(security_pass.get("security_pass_completed") is True),
        "read_only_surfaces_approved": bool(security_pass.get("read_only_surfaces_approved") is True),
        "preview_surfaces_approved": bool(security_pass.get("preview_surfaces_approved") is True),
        "security_pass_action_authority_granted": bool(
            security_pass.get("action_authority_granted") is True
        ),
        "worker_output_intake_summary_present": bool(
            worker_orphan_summary.get("worker_output_intake_metadata_approved") is True
        ),
        "orphaned_capability_summary_present": bool(
            worker_orphan_summary.get("orphaned_capability_detection_approved") is True
        ),
        "chief_hermes_trust_summary_present": bool(
            chief_hermes_summary.get("chief_reconciliation_metadata_approved") is True
            and chief_hermes_summary.get("hermes_architecture_review_metadata_approved") is True
            and chief_hermes_summary.get("trust_clearance_modeling_approved") is True
        ),
        "post_security_governance_batch_present": bool(
            post_security_governance_batch.get("present") is True or post_security_governance_batch
        ),
        "parked_capital_experiment_present": bool(
            parked_capital_experiment.get("present") is True or parked_capital_experiment
        ),
        "security_delta_review_present": bool(
            security_delta_review.get("present") is True or security_delta_review
        ),
        "operator_attention_promotion_present": bool(
            operator_attention_promotion.get("present") is True or operator_attention_promotion
        ),
        "chief_test_harness_cross_off_present": bool(
            chief_test_harness_cross_off.get("present") is True or chief_test_harness_cross_off
        ),
        "post_security_governance_all_live_authority_flags_false": bool(
            post_security_governance_batch
            and parked_capital_experiment
            and security_delta_review
            and operator_attention_promotion
            and chief_test_harness_cross_off
            and post_security_governance_batch.get("action_authority_granted") is False
            and post_security_governance_authority.get("all_live_authority_false") is True
            and post_security_governance_authority.get("live_execution_allowed") is False
            and post_security_governance_authority.get("model_api_execution_allowed") is False
            and post_security_governance_authority.get("tool_execution_allowed") is False
            and post_security_governance_authority.get("actor_agent_activation_allowed") is False
            and post_security_governance_authority.get("queue_autonomy_allowed") is False
            and post_security_governance_authority.get("account_payment_financial_allowed") is False
            and post_security_governance_authority.get("send_submit_approval_allowed") is False
            and post_security_governance_authority.get("network_operation_allowed") is False
            and parked_capital_experiment.get("action_authority_granted") is False
            and parked_capital_experiment.get("capital_spend_allowed") is False
            and parked_capital_experiment.get("network_operation_allowed") is False
            and security_delta_review.get("action_authority_granted") is False
            and security_delta_review.get("execution_authority_granted") is False
            and operator_attention_promotion.get("action_authority_granted") is False
            and operator_attention_promotion.get("cue_candidates_executable") is False
            and operator_attention_promotion.get("holding_cell_queued") is False
            and chief_test_harness_cross_off.get("action_authority_granted") is False
            and chief_test_harness_cross_off.get("source_mutation_allowed") is False
            and chief_test_harness_cross_off.get("delete_source_allowed") is False
        ),
        "security_pass_all_live_authority_flags_false": bool(
            security_pass.get("all_live_authority_false") is True
            and security_pass.get("action_authority_granted") is False
            and security_pass.get("runtime_execution_authority_granted") is False
            and security_pass.get("model_execution_authority_granted") is False
            and security_pass.get("tool_execution_authority_granted") is False
            and security_pass.get("queue_execution_authority_granted") is False
            and security_pass.get("account_authority_granted") is False
            and security_pass.get("send_submit_approval_authority_granted") is False
        ),
    }


def _map_file_presence(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
) -> dict[str, Any]:
    root = Path(read_model_root)
    manifest_names = _manifest_relative_paths(manifest_path)
    return {
        "snapshot_present_on_pc": (root / "openclaw_map_snapshot.json").is_file(),
        "manifest_present_on_pc": (root / "openclaw_map_manifest.json").is_file(),
        "operator_digest_present_on_pc": (root / "openclaw_map_OPERATOR.md").is_file(),
        "mac_snapshot_present": "openclaw_map_snapshot.json" in manifest_names,
        "mac_manifest_present": "openclaw_map_manifest.json" in manifest_names,
        "mac_operator_digest_present": "openclaw_map_OPERATOR.md" in manifest_names,
        "mac_receipt_present_in_manifest": STABLE_MAP_OPTIONAL_RECEIPT_FILE in manifest_names,
    }


def _agent_dossier_receipt_status(receipt: dict[str, Any]) -> dict[str, Any]:
    validation_details = (
        receipt.get("validation_details")
        if isinstance(receipt.get("validation_details"), dict)
        else {}
    )
    observed = receipt.get("observed") if isinstance(receipt.get("observed"), dict) else {}
    has_agent_dossier_fields = any(
        key in receipt or key in observed or key in validation_details
        for key in {
            "agent_council_present",
            "agent_dossier_cards_present",
            "agent_dossier_cards_count",
            "agent_council_card_count",
            "agent_dossier_cards_observed_path",
            "agent_dossier_cards_top_level_present",
            "cassandra_card_present",
            "missing_system_loop_cards",
            "no_image_body_embedded",
            "live_activation_flags_false",
            "all_live_authority_flags_false",
        }
    )
    has_agent_dossier_live_authority_fields = any(
        key in receipt or key in observed or key in validation_details
        for key in {
            "live_activation_flags_false",
            "live_authority_flags_false",
            "no_live_execution_authority",
            "all_live_authority_flags_false",
            "live_agent_activation_false",
            "live_chat_launch_false",
            "model_launch_false",
            "tool_execution_false",
        }
    )
    top_level_present = receipt.get("agent_dossier_cards_top_level_present") is True
    observed_path = receipt.get("agent_dossier_cards_observed_path")
    nested_present = bool(
        (
            receipt.get("agent_dossier_cards_present") is True
            and observed_path == "agent_council.agent_dossier_cards"
        )
        or receipt.get("agent_council_present") is True
        or observed.get("agent_council_present") is True
        or validation_details.get("agent_council_present") is True
    )
    if nested_present:
        accepted_path = "agent_council.agent_dossier_cards"
        path_status = "accepted_canonical_nested_path"
    elif top_level_present:
        accepted_path = "agent_dossier_cards"
        path_status = "accepted_top_level_path"
    else:
        accepted_path = observed_path
        path_status = "missing_or_unknown_path" if has_agent_dossier_fields else "not_reported"
    try:
        card_count = int(
            receipt.get("agent_dossier_cards_count")
            or receipt.get("agent_council_card_count")
            or observed.get("agent_dossier_cards_count")
            or observed.get("agent_council_card_count")
            or validation_details.get("agent_dossier_cards_count")
            or validation_details.get("agent_council_card_count")
            or 0
        )
    except (TypeError, ValueError):
        card_count = 0
    missing_system_loop_cards = receipt.get("missing_system_loop_cards")
    system_loop_cards_present = (
        isinstance(missing_system_loop_cards, list) and not missing_system_loop_cards
    )
    if receipt.get("agent_council_present") is True and card_count == 12 and not isinstance(missing_system_loop_cards, list):
        system_loop_cards_present = True
    live_activation_flags_false = bool(
        receipt.get("live_activation_flags_false") is True
        or receipt.get("live_authority_flags_false") is True
        or receipt.get("no_live_execution_authority") is True
        or receipt.get("all_live_authority_flags_false") is True
        or observed.get("all_live_authority_flags_false") is True
        or observed.get("no_live_execution_authority") is True
        or validation_details.get("live_authority_flags_false") is True
        or validation_details.get("all_live_authority_flags_false") is True
        or (
            receipt.get("live_agent_activation_false") is True
            and receipt.get("live_chat_launch_false") is True
            and receipt.get("model_launch_false") is True
            and receipt.get("tool_execution_false") is True
        )
    )
    no_image_body_embedded = bool(
        receipt.get("no_image_body_embedded") is True
        or receipt.get("raw_private_body_absent") is True
        or observed.get("no_image_body_embedded") is True
        or observed.get("raw_private_body_absent") is True
        or validation_details.get("raw_private_body_absent") is True
    )
    cassandra_card_present = bool(
        receipt.get("cassandra_card_present") is True
        or observed.get("cassandra_card_present") is True
        or validation_details.get("cassandra_card_present") is True
    )
    cassandra_card_requirement_met = bool(
        cassandra_card_present
        or (
            "cassandra_card_present" not in receipt
            and "cassandra_card_present" not in validation_details
        )
    )
    agent_cards_present = bool(
        receipt.get("agent_dossier_cards_present") is True
        or receipt.get("agent_council_present") is True
        or observed.get("agent_council_present") is True
        or validation_details.get("agent_council_present") is True
    )
    no_image_requirement_met = bool(
        no_image_body_embedded
        or (
            "no_image_body_embedded" not in receipt
            and "raw_private_body_absent" not in receipt
            and "raw_private_body_absent" not in validation_details
        )
    )
    live_authority_requirement_met = bool(
        live_activation_flags_false or not has_agent_dossier_live_authority_fields
    )
    validation_passed = bool(
        not has_agent_dossier_fields
        or (
            agent_cards_present
            and path_status in {"accepted_canonical_nested_path", "accepted_top_level_path"}
            and card_count == 12
            and cassandra_card_requirement_met
            and system_loop_cards_present
            and no_image_requirement_met
            and live_authority_requirement_met
        )
    )
    return {
        "agent_council_present": bool(
            receipt.get("agent_council_present") is True
            or observed.get("agent_council_present") is True
            or validation_details.get("agent_council_present") is True
        ),
        "agent_dossier_cards_present": agent_cards_present,
        "agent_dossier_cards_top_level_present": top_level_present,
        "agent_dossier_cards_nested_present": nested_present,
        "agent_dossier_cards_count": card_count,
        "agent_dossier_cards_path": accepted_path,
        "agent_dossier_cards_path_status": path_status,
        "cassandra_card_present": cassandra_card_present,
        "system_loop_cards_present": system_loop_cards_present,
        "missing_system_loop_cards": missing_system_loop_cards if isinstance(missing_system_loop_cards, list) else [],
        "no_image_body_embedded": no_image_body_embedded,
        "cassandra_visual_archetype_metadata_only": bool(
            receipt.get("cassandra_visual_archetype_metadata_only") is True
        ),
        "live_activation_flags_false": live_activation_flags_false,
        "agent_dossier_receipt_fields_present": has_agent_dossier_fields,
        "agent_dossier_receipt_validation_passed": validation_passed,
    }


def _receipt_surface_status(receipt: dict[str, Any]) -> dict[str, Any]:
    validation_details = (
        receipt.get("validation_details")
        if isinstance(receipt.get("validation_details"), dict)
        else {}
    )
    observed = receipt.get("observed") if isinstance(receipt.get("observed"), dict) else {}

    def _int_field(*names: str) -> int:
        for name in names:
            for source in (receipt, validation_details, observed):
                try:
                    value = int(source.get(name) or 0)
                except (TypeError, ValueError):
                    value = 0
                if value:
                    return value
        return 0

    def _bool_field(*names: str) -> bool:
        return any(source.get(name) is True for name in names for source in (receipt, validation_details, observed))

    def _validation_bool(name: str) -> bool:
        return validation_details.get(name) is True or observed.get(name) is True

    def _has_any(*names: str) -> bool:
        return any(name in source for name in names for source in (receipt, validation_details, observed))

    def _not_explicitly_false(*names: str) -> bool:
        return all(receipt.get(name) is not False for name in names) and all(
            validation_details.get(name) is not False for name in names
        ) and all(
            observed.get(name) is not False for name in names
        )

    def _compat_direct_or_validation(*names: str) -> bool:
        return any(
            receipt.get(name) is True or validation_details.get(name) is True or observed.get(name) is True
            for name in names
        )

    def _compat_detail_present(name: str, *, default: bool) -> bool:
        if name in validation_details:
            return validation_details.get(name) is True
        if name in observed:
            return observed.get(name) is True
        return default

    package_count = _int_field("package_preview_example_count", "package_preview_cards_count")
    tool_count = _int_field("tool_adapter_receipt_example_count", "tool_adapter_receipt_cards_count")
    has_package_tool_fields = any(
        key in receipt or key in validation_details or key in observed
        for key in {
            "package_preview_summary_present",
            "package_preview_example_count",
            "package_preview_cards_count",
            "tool_adapter_receipt_summary_present",
            "tool_adapter_receipt_example_count",
            "tool_adapter_receipt_cards_count",
        }
    )
    package_count_reported = _has_any("package_preview_example_count", "package_preview_cards_count")
    tool_count_reported = _has_any("tool_adapter_receipt_example_count", "tool_adapter_receipt_cards_count")
    package_preview_summary_present = bool(
        _bool_field("package_preview_summary_present")
        or _validation_bool("package_preview_summary_present")
    )
    tool_adapter_receipt_summary_present = bool(
        _bool_field("tool_adapter_receipt_summary_present")
        or _validation_bool("tool_adapter_receipt_summary_present")
    )
    package_preview_validation_passed = bool(
        not has_package_tool_fields
        or (
            package_preview_summary_present
            and (not package_count_reported or package_count == 8)
            and _compat_detail_present(
                "package_preview_example_count_ok",
                default=(not package_count_reported or package_count == 8),
            )
            and _compat_detail_present("cassandra_capital_hilton_package_preview_present", default=True)
            and _compat_detail_present("chief_check_engine_package_preview_present", default=True)
            and _compat_detail_present("agentic_loop_classification_package_preview_present", default=True)
        )
    )
    tool_adapter_receipt_validation_passed = bool(
        not has_package_tool_fields
        or (
            tool_adapter_receipt_summary_present
            and (not tool_count_reported or tool_count == 12)
            and _compat_detail_present(
                "tool_adapter_receipt_example_count_ok",
                default=(not tool_count_reported or tool_count == 12),
            )
            and _compat_detail_present("stable_map_reader_tool_adapter_present", default=True)
            and _compat_detail_present("cassandra_capital_hilton_tool_adapter_present", default=True)
            and _compat_detail_present("browser_oauth_blocked_adapter_present", default=True)
            and _compat_detail_present("gmail_calendar_blocked_adapter_present", default=True)
            and _compat_detail_present("coupa_blocked_adapter_present", default=True)
            and _compat_detail_present("telegram_blocked_adapter_present", default=True)
        )
    )
    raw_private_body_absent = bool(
        _compat_direct_or_validation("raw_private_body_absent")
        or _not_explicitly_false("raw_private_body_absent")
    )
    no_credentials_secrets_embedded = bool(
        _compat_direct_or_validation("no_credentials_secrets_embedded")
        or _not_explicitly_false("no_credentials_secrets_embedded")
    )
    live_authority_flags_false = bool(
        receipt.get("live_authority_flags_false") is True
        or receipt.get("no_live_execution_authority") is True
        or receipt.get("all_live_authority_flags_false") is True
        or observed.get("all_live_authority_flags_false") is True
        or observed.get("no_live_execution_authority") is True
        or validation_details.get("live_authority_flags_false") is True
        or validation_details.get("all_live_authority_flags_false") is True
        or not has_package_tool_fields
    )
    return {
        "package_preview_summary_present": package_preview_summary_present,
        "package_preview_example_count": package_count,
        "cassandra_capital_hilton_preview_present": bool(
            validation_details.get("cassandra_capital_hilton_package_preview_present") is True
        ),
        "chief_check_engine_preview_present": bool(
            validation_details.get("chief_check_engine_package_preview_present") is True
        ),
        "agentic_loop_classification_preview_present": bool(
            validation_details.get("agentic_loop_classification_package_preview_present") is True
        ),
        "tool_adapter_receipt_summary_present": tool_adapter_receipt_summary_present,
        "tool_adapter_receipt_example_count": tool_count,
        "stable_map_reader_adapter_present": bool(
            validation_details.get("stable_map_reader_tool_adapter_present") is True
        ),
        "cassandra_capital_hilton_adapter_present": bool(
            validation_details.get("cassandra_capital_hilton_tool_adapter_present") is True
        ),
        "browser_oauth_blocked_adapter_present": bool(
            validation_details.get("browser_oauth_blocked_adapter_present") is True
        ),
        "gmail_calendar_blocked_adapter_present": bool(
            validation_details.get("gmail_calendar_blocked_adapter_present") is True
        ),
        "coupa_blocked_adapter_present": bool(
            validation_details.get("coupa_blocked_adapter_present") is True
        ),
        "telegram_blocked_adapter_present": bool(
            validation_details.get("telegram_blocked_adapter_present") is True
        ),
        "raw_private_body_absent": raw_private_body_absent,
        "no_credentials_secrets_embedded": no_credentials_secrets_embedded,
        "live_authority_flags_false": live_authority_flags_false,
        "package_tool_receipt_fields_present": has_package_tool_fields,
        "package_preview_receipt_validation_passed": package_preview_validation_passed,
        "tool_adapter_receipt_validation_passed": tool_adapter_receipt_validation_passed,
        "package_tool_receipt_validation_passed": bool(
            package_preview_validation_passed
            and tool_adapter_receipt_validation_passed
            and raw_private_body_absent
            and no_credentials_secrets_embedded
            and live_authority_flags_false
        ),
    }


def _capital_hilton_receipt_status(receipt: dict[str, Any]) -> dict[str, Any]:
    validation_details = (
        receipt.get("validation_details")
        if isinstance(receipt.get("validation_details"), dict)
        else {}
    )

    def _int_field(name: str) -> int:
        try:
            return int(receipt.get(name) or validation_details.get(name) or 0)
        except (TypeError, ValueError):
            return 0

    def _bool_field(name: str) -> bool:
        return receipt.get(name) is True or validation_details.get(name) is True

    current_phase = receipt.get("capital_hilton_current_phase") or validation_details.get(
        "capital_hilton_current_phase"
    )
    target_world = receipt.get("capital_hilton_target_world") or validation_details.get(
        "capital_hilton_target_world"
    )
    lane_destiny = receipt.get("capital_hilton_lane_destiny") or validation_details.get(
        "capital_hilton_lane_destiny"
    )
    missing_proof_count = _int_field("capital_hilton_missing_proof_count")
    protected_proof_required = _bool_field("capital_hilton_protected_proof_required")
    candidate_facts_marked_not_proven = _bool_field(
        "capital_hilton_candidate_facts_marked_not_proven"
    )
    operator_questions_count = _int_field("capital_hilton_operator_questions_count")
    authority_flags_false = _bool_field("capital_hilton_authority_flags_false")
    summary_present = _bool_field("capital_hilton_summary_present")
    detailed_capital_hilton_fields = {
            "capital_hilton_current_phase",
            "capital_hilton_target_world",
            "capital_hilton_lane_destiny",
            "capital_hilton_missing_proof_count",
            "capital_hilton_protected_proof_required",
            "capital_hilton_candidate_facts_marked_not_proven",
            "capital_hilton_operator_questions_count",
            "capital_hilton_authority_flags_false",
        }
    receipt_sources = (receipt, validation_details)
    has_capital_hilton_fields = any(
        key in source
        for source in receipt_sources
        for key in {"capital_hilton_summary_present", *detailed_capital_hilton_fields}
    )
    has_detailed_capital_hilton_fields = any(
        key in source
        for source in receipt_sources
        for key in detailed_capital_hilton_fields
    )
    validation_passed = bool(
        not has_capital_hilton_fields
        or (summary_present and not has_detailed_capital_hilton_fields)
        or (
            summary_present
            and current_phase == "HELM_THRESHOLD_LANE"
            and target_world == "Finance"
            and lane_destiny == "MOVE_TO_WORLD_ACTION"
            and missing_proof_count == 10
            and protected_proof_required
            and candidate_facts_marked_not_proven
            and operator_questions_count == 7
            and authority_flags_false
        )
    )
    return {
        "capital_hilton_summary_present": summary_present,
        "capital_hilton_current_phase": current_phase,
        "capital_hilton_target_world": target_world,
        "capital_hilton_lane_destiny": lane_destiny,
        "capital_hilton_missing_proof_count": missing_proof_count,
        "capital_hilton_protected_proof_required": protected_proof_required,
        "capital_hilton_candidate_facts_marked_not_proven": candidate_facts_marked_not_proven,
        "capital_hilton_operator_questions_count": operator_questions_count,
        "capital_hilton_authority_flags_false": authority_flags_false,
        "capital_hilton_receipt_fields_present": has_capital_hilton_fields,
        "capital_hilton_receipt_validation_passed": validation_passed,
    }


def _security_audit_receipt_status(receipt: dict[str, Any]) -> dict[str, Any]:
    validation_details = (
        receipt.get("validation_details")
        if isinstance(receipt.get("validation_details"), dict)
        else {}
    )
    observed = receipt.get("observed") if isinstance(receipt.get("observed"), dict) else {}

    def _int_field(name: str) -> int:
        for source in (receipt, validation_details, observed):
            try:
                value = int(source.get(name) or 0)
            except (TypeError, ValueError):
                value = 0
            if value:
                return value
        return 0

    def _bool_true(*names: str) -> bool:
        return any(source.get(name) is True for name in names for source in (receipt, validation_details, observed))

    def _bool_false(name: str) -> bool:
        return any(source.get(name) is False for source in (receipt, validation_details, observed))

    detailed_security_fields = {
        "ready_for_security_pass",
        "coverage_gap_records_count",
        "parked_breadcrumb_count",
        "capital_hilton_security_readiness_present",
    }
    has_security_fields = any(
        key in source
        for source in (receipt, validation_details, observed)
        for key in {
            "security_audit_readiness_present",
            "ready_for_security_pass",
            "coverage_gap_records_count",
            "parked_breadcrumb_count",
            "capital_hilton_security_readiness_present",
        }
    )
    has_detailed_security_fields = any(
        key in source
        for source in (receipt, validation_details, observed)
        for key in detailed_security_fields
    )
    security_present = _bool_true("security_audit_readiness_present")
    ready_for_security_pass = _bool_true("ready_for_security_pass")
    security_approval_granted = _bool_true("security_approval_granted")
    action_authority_granted = _bool_true("action_authority_granted")
    coverage_gap_records_count = _int_field("coverage_gap_records_count")
    parked_breadcrumb_count = _int_field("parked_breadcrumb_count")
    capital_hilton_security_readiness_present = _bool_true(
        "capital_hilton_security_readiness_present"
    )
    all_live_authority_flags_false = _bool_true(
        "all_live_authority_flags_false",
        "live_authority_flags_false",
        "no_live_execution_authority",
    )
    validation_passed = bool(
        not has_security_fields
        or (
            security_present
            and not has_detailed_security_fields
            and _bool_false("action_authority_granted")
            and not action_authority_granted
            and all_live_authority_flags_false
        )
        or (
            security_present
            and ready_for_security_pass
            and _bool_false("security_approval_granted")
            and not security_approval_granted
            and _bool_false("action_authority_granted")
            and not action_authority_granted
            and coverage_gap_records_count == 5
            and parked_breadcrumb_count == 15
            and capital_hilton_security_readiness_present
            and all_live_authority_flags_false
        )
    )
    return {
        "security_audit_readiness_present": security_present,
        "ready_for_security_pass": ready_for_security_pass,
        "security_approval_granted": security_approval_granted,
        "action_authority_granted": action_authority_granted,
        "coverage_gap_records_count": coverage_gap_records_count,
        "parked_breadcrumb_count": parked_breadcrumb_count,
        "capital_hilton_security_readiness_present": capital_hilton_security_readiness_present,
        "all_live_authority_flags_false": all_live_authority_flags_false,
        "security_audit_receipt_fields_present": has_security_fields,
        "security_audit_receipt_validation_passed": validation_passed,
    }


def _security_pass_receipt_status(receipt: dict[str, Any]) -> dict[str, Any]:
    validation_details = (
        receipt.get("validation_details")
        if isinstance(receipt.get("validation_details"), dict)
        else {}
    )
    observed = receipt.get("observed") if isinstance(receipt.get("observed"), dict) else {}
    sources = (receipt, validation_details, observed)

    def _bool_true(*names: str) -> bool:
        return any(source.get(name) is True for name in names for source in sources)

    def _bool_false(name: str) -> bool:
        return any(source.get(name) is False for source in sources)

    has_security_pass_fields = any(
        key in source
        for source in sources
        for key in {
            "security_pass_present",
            "security_pass_completed",
            "read_only_surfaces_approved",
            "preview_surfaces_approved",
            "worker_output_intake_summary_present",
            "orphaned_capability_summary_present",
            "chief_hermes_trust_summary_present",
        }
    )
    has_detailed_security_pass_fields = any(
        key in source
        for source in sources
        for key in {
            "security_pass_completed",
            "read_only_surfaces_approved",
            "preview_surfaces_approved",
            "worker_output_intake_summary_present",
            "orphaned_capability_summary_present",
            "chief_hermes_trust_summary_present",
        }
    )
    security_pass_present = _bool_true("security_pass_present")
    security_pass_completed = _bool_true("security_pass_completed")
    read_only_surfaces_approved = _bool_true("read_only_surfaces_approved")
    preview_surfaces_approved = _bool_true("preview_surfaces_approved")
    action_authority_granted = _bool_true("action_authority_granted")
    worker_output_intake_summary_present = _bool_true("worker_output_intake_summary_present")
    orphaned_capability_summary_present = _bool_true("orphaned_capability_summary_present")
    chief_hermes_trust_summary_present = _bool_true("chief_hermes_trust_summary_present")
    all_live_authority_flags_false = _bool_true(
        "all_live_authority_flags_false",
        "live_authority_flags_false",
        "no_live_execution_authority",
    )
    runtime_execution_authority_granted = _bool_true("runtime_execution_authority_granted")
    model_execution_authority_granted = _bool_true("model_execution_authority_granted")
    tool_execution_authority_granted = _bool_true("tool_execution_authority_granted")
    queue_execution_authority_granted = _bool_true("queue_execution_authority_granted")
    account_authority_granted = _bool_true("account_authority_granted")
    send_submit_approval_authority_granted = _bool_true("send_submit_approval_authority_granted")
    validation_passed = bool(
        not has_security_pass_fields
        or (
            security_pass_present
            and not has_detailed_security_pass_fields
            and not action_authority_granted
        )
        or (
            security_pass_present
            and security_pass_completed
            and read_only_surfaces_approved
            and preview_surfaces_approved
            and _bool_false("action_authority_granted")
            and not action_authority_granted
            and worker_output_intake_summary_present
            and orphaned_capability_summary_present
            and chief_hermes_trust_summary_present
            and all_live_authority_flags_false
            and not runtime_execution_authority_granted
            and not model_execution_authority_granted
            and not tool_execution_authority_granted
            and not queue_execution_authority_granted
            and not account_authority_granted
            and not send_submit_approval_authority_granted
        )
    )
    return {
        "security_pass_present": security_pass_present,
        "security_pass_completed": security_pass_completed,
        "read_only_surfaces_approved": read_only_surfaces_approved,
        "preview_surfaces_approved": preview_surfaces_approved,
        "security_pass_action_authority_granted": action_authority_granted,
        "worker_output_intake_summary_present": worker_output_intake_summary_present,
        "orphaned_capability_summary_present": orphaned_capability_summary_present,
        "chief_hermes_trust_summary_present": chief_hermes_trust_summary_present,
        "security_pass_all_live_authority_flags_false": all_live_authority_flags_false,
        "security_pass_receipt_fields_present": has_security_pass_fields,
        "security_pass_receipt_validation_passed": validation_passed,
    }


def _post_security_governance_receipt_status(receipt: dict[str, Any]) -> dict[str, Any]:
    validation_details = (
        receipt.get("validation_details")
        if isinstance(receipt.get("validation_details"), dict)
        else {}
    )
    observed = receipt.get("observed") if isinstance(receipt.get("observed"), dict) else {}
    sources = (receipt, validation_details, observed)

    def _bool_true(*names: str) -> bool:
        return any(source.get(name) is True for name in names for source in sources)

    has_governance_fields = any(
        key in source
        for source in sources
        for key in {
            "post_security_governance_batch_present",
            "parked_capital_experiment_present",
            "security_delta_review_present",
            "operator_attention_promotion_present",
            "chief_test_harness_cross_off_present",
        }
    )
    detailed_governance_fields = {
        "parked_capital_experiment_present",
        "security_delta_review_present",
        "operator_attention_promotion_present",
        "chief_test_harness_cross_off_present",
    }
    has_detailed_governance_fields = any(
        key in source
        for source in sources
        for key in detailed_governance_fields
    )
    post_security_governance_batch_present = _bool_true("post_security_governance_batch_present")
    parked_capital_experiment_present = _bool_true("parked_capital_experiment_present")
    security_delta_review_present = _bool_true("security_delta_review_present")
    operator_attention_promotion_present = _bool_true("operator_attention_promotion_present")
    chief_test_harness_cross_off_present = _bool_true("chief_test_harness_cross_off_present")
    security_pass_present = _bool_true("security_pass_present")
    agent_council_present = _bool_true("agent_council_present")
    explicitly_granted_authority = any(
        source.get(name) is True
        for source in sources
        for name in {
            "action_authority_granted",
            "runtime_execution_authority_granted",
            "model_execution_authority_granted",
            "tool_execution_authority_granted",
            "queue_execution_authority_granted",
            "account_authority_granted",
            "send_submit_approval_authority_granted",
            "execution_authority_granted",
            "network_operation_allowed",
            "credential_handling_allowed",
        }
    )
    authority_flags_false = bool(
        _bool_true(
            "all_live_authority_flags_false",
            "live_authority_flags_false",
            "no_live_execution_authority",
        )
        or not explicitly_granted_authority
    )
    validation_passed = bool(
        not has_governance_fields
        or (
            post_security_governance_batch_present
            and not has_detailed_governance_fields
            and authority_flags_false
        )
        or (
            post_security_governance_batch_present
            and parked_capital_experiment_present
            and security_delta_review_present
            and operator_attention_promotion_present
            and chief_test_harness_cross_off_present
            and security_pass_present
            and agent_council_present
            and authority_flags_false
        )
    )
    return {
        "post_security_governance_batch_present": post_security_governance_batch_present,
        "parked_capital_experiment_present": parked_capital_experiment_present,
        "security_delta_review_present": security_delta_review_present,
        "operator_attention_promotion_present": operator_attention_promotion_present,
        "chief_test_harness_cross_off_present": chief_test_harness_cross_off_present,
        "post_security_governance_authority_flags_false": authority_flags_false,
        "post_security_governance_receipt_fields_present": has_governance_fields,
        "post_security_governance_receipt_validation_passed": validation_passed,
    }


def _capital_hilton_protected_proof_intake_receipt_status(receipt: dict[str, Any]) -> dict[str, Any]:
    validation_details = (
        receipt.get("validation_details")
        if isinstance(receipt.get("validation_details"), dict)
        else {}
    )
    observed = receipt.get("observed") if isinstance(receipt.get("observed"), dict) else {}
    sources = (receipt, validation_details, observed)

    def _bool_true(*names: str) -> bool:
        return any(source.get(name) is True for name in names for source in sources)

    def _bool_false(*names: str) -> bool:
        return any(source.get(name) is False for name in names for source in sources)

    def _int_field(name: str) -> int:
        for source in sources:
            try:
                value = int(source.get(name) or 0)
            except (TypeError, ValueError):
                value = 0
            if value:
                return value
        return 0

    proof_intake_fields = {
        "capital_hilton_protected_proof_intake_present",
        "proof_items_count",
        "missing_proof_count",
        "protected_proof_required",
        "candidate_facts_proven",
        "guardian_gates_present",
        "operator_answer_candidates_present",
        "protected_evidence_requirements_present",
    }
    blocked_authority_fields = {
        "action_authority_granted",
        "invoice_generation_allowed",
        "coupa_access_allowed",
        "browser_oauth_account_access_allowed",
        "gmail_calendar_email_access_allowed",
        "credential_handling_allowed",
        "send_submit_approval_allowed",
    }
    has_proof_intake_fields = any(
        key in source
        for source in sources
        for key in proof_intake_fields
    )
    present = _bool_true("capital_hilton_protected_proof_intake_present")
    proof_items_count = _int_field("proof_items_count")
    missing_proof_count = _int_field("missing_proof_count")
    protected_proof_required = _bool_true("protected_proof_required")
    candidate_facts_proven = _bool_true("candidate_facts_proven")
    action_authority_granted = _bool_true("action_authority_granted")
    guardian_gates_present = _bool_true("guardian_gates_present")
    operator_answer_candidates_present = _bool_true("operator_answer_candidates_present")
    protected_evidence_requirements_present = _bool_true("protected_evidence_requirements_present")
    all_live_authority_flags_false = _bool_true(
        "all_live_authority_flags_false",
        "live_authority_flags_false",
        "no_live_execution_authority",
    )
    blocked_authority_false = bool(
        _bool_false("action_authority_granted")
        and _bool_false("invoice_generation_allowed")
        and _bool_false("coupa_access_allowed")
        and _bool_false("browser_oauth_account_access_allowed")
        and _bool_false("gmail_calendar_email_access_allowed")
        and _bool_false("credential_handling_allowed")
        and _bool_false("send_submit_approval_allowed")
    )
    validation_passed = bool(
        not has_proof_intake_fields
        or (
            present
            and proof_items_count == 10
            and missing_proof_count == 10
            and protected_proof_required
            and not candidate_facts_proven
            and not action_authority_granted
            and guardian_gates_present
            and operator_answer_candidates_present
            and protected_evidence_requirements_present
            and (all_live_authority_flags_false or blocked_authority_false)
        )
    )
    return {
        "capital_hilton_protected_proof_intake_present": present,
        "capital_hilton_protected_proof_intake_proof_items_count": proof_items_count,
        "capital_hilton_protected_proof_intake_missing_proof_count": missing_proof_count,
        "capital_hilton_protected_proof_intake_protected_proof_required": protected_proof_required,
        "capital_hilton_protected_proof_intake_candidate_facts_proven": candidate_facts_proven,
        "capital_hilton_protected_proof_intake_action_authority_granted": action_authority_granted,
        "capital_hilton_protected_proof_intake_guardian_gates_present": guardian_gates_present,
        "capital_hilton_protected_proof_intake_operator_answer_candidates_present": (
            operator_answer_candidates_present
        ),
        "capital_hilton_protected_proof_intake_protected_evidence_requirements_present": (
            protected_evidence_requirements_present
        ),
        "capital_hilton_protected_proof_intake_authority_flags_false": bool(
            all_live_authority_flags_false or blocked_authority_false
        ),
        "capital_hilton_protected_proof_intake_receipt_fields_present": has_proof_intake_fields,
        "capital_hilton_protected_proof_intake_receipt_validation_passed": validation_passed,
    }


def build_receipt_status(
    *,
    map_manifest: dict[str, Any],
    map_receipt_path: str | Path = DEFAULT_MAP_RECEIPT_PATH,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
) -> dict[str, Any]:
    receipt_path = Path(map_receipt_path)
    receipt = _read_json_object(receipt_path) or {}
    manifest_names = _manifest_relative_paths(manifest_path)
    expected_generation = map_manifest.get("map_generation_id")
    expected_hash = map_manifest.get("bundle_hash")
    receipt_generation = receipt.get("map_generation_id") or receipt.get("observed_map_generation_id")
    receipt_hash = receipt.get("bundle_hash") or receipt.get("observed_bundle_hash")
    explicit_parse_passed = receipt.get("parse_passed")
    per_file_parse_passed = bool(
        receipt.get("snapshot_present") is True
        and receipt.get("manifest_present") is True
        and receipt.get("operator_digest_present") is True
        and receipt.get("snapshot_parse_passed") is True
        and receipt.get("manifest_parse_passed") is True
        and receipt.get("operator_digest_non_empty") is True
    )
    receipt_parse_passed = bool(explicit_parse_passed is True or per_file_parse_passed)
    missing_files = receipt.get("missing_files")
    missing_files_blocking = bool(missing_files) if isinstance(missing_files, list) else missing_files not in (None, False)
    hash_mismatch = receipt.get("hash_mismatch")
    hash_mismatch_blocking = bool(hash_mismatch) if isinstance(hash_mismatch, list) else hash_mismatch not in (None, False)
    schema_version = receipt.get("schema_version")
    schema_compatible = schema_version in (None, STABLE_MAP_RECEIPT_SCHEMA_VERSION)
    receipt_status_value = receipt.get("receipt_status")
    agent_dossier = _agent_dossier_receipt_status(receipt)
    receipt_surfaces = _receipt_surface_status(receipt)
    capital_hilton = _capital_hilton_receipt_status(receipt)
    security_audit = _security_audit_receipt_status(receipt)
    security_pass = _security_pass_receipt_status(receipt)
    post_security_governance = _post_security_governance_receipt_status(receipt)
    capital_hilton_proof_intake = _capital_hilton_protected_proof_intake_receipt_status(receipt)
    status_imported = receipt_status_value in (
        None,
        "imported",
        "synced",
        "SUCCESS",
        "imported_validated_pc_readback_required",
        *ACCEPTED_PARTIAL_MAP_RECEIPT_STATUSES,
    )
    receipt_matches = bool(
        receipt
        and schema_compatible
        and status_imported
        and receipt_generation == expected_generation
        and receipt_hash == expected_hash
        and receipt_parse_passed
        and not missing_files_blocking
        and not hash_mismatch_blocking
        and agent_dossier["agent_dossier_receipt_validation_passed"]
        and receipt_surfaces["package_tool_receipt_validation_passed"]
        and capital_hilton["capital_hilton_receipt_validation_passed"]
        and security_audit["security_audit_receipt_validation_passed"]
        and security_pass["security_pass_receipt_validation_passed"]
        and post_security_governance["post_security_governance_receipt_validation_passed"]
        and capital_hilton_proof_intake["capital_hilton_protected_proof_intake_receipt_validation_passed"]
    )
    return {
        "mac_completion_marker_present": Path(DEFAULT_MAC_COMPLETION_PATH).is_file(),
        "map_receipt_present": receipt_path.is_file(),
        "map_receipt_present_in_mac_manifest": STABLE_MAP_OPTIONAL_RECEIPT_FILE in manifest_names,
        "receipt_schema_version": schema_version,
        "receipt_schema_compatible": schema_compatible,
        "receipt_status": receipt_status_value,
        "receipt_status_accepted": status_imported,
        "receipt_status_accepted_reason": (
            "agent_dossier_cards_nested_path_is_canonical"
            if receipt_status_value in ACCEPTED_PARTIAL_MAP_RECEIPT_STATUSES
            else None
        ),
        "receipt_app_visible_candidate": bool(receipt.get("app_visible_candidate")),
        "receipt_app_visible_normalized": receipt_matches,
        "receipt_generation_id": receipt_generation,
        "receipt_bundle_hash": receipt_hash,
        "receipt_observed_generation_id": receipt.get("observed_map_generation_id"),
        "receipt_observed_bundle_hash": receipt.get("observed_bundle_hash"),
        "receipt_parse_passed": receipt_parse_passed,
        "receipt_missing_files": missing_files if isinstance(missing_files, list) else [],
        "receipt_hash_mismatch": hash_mismatch if isinstance(hash_mismatch, list) else bool(hash_mismatch),
        "receipt_matches_pc_bundle": receipt_matches,
        "pc_readback_imported": receipt_matches,
        "receipt_path": receipt_path.as_posix(),
        "expected_generation_id": expected_generation,
        "expected_bundle_hash": expected_hash,
        **agent_dossier,
        **receipt_surfaces,
        **capital_hilton,
        **security_audit,
        **security_pass,
        **post_security_governance,
        **capital_hilton_proof_intake,
    }


def build_raw_read_model_mirror_status(manifest_health: dict[str, Any]) -> dict[str, Any]:
    counts = manifest_health.get("counts", {})
    missing_files = list(manifest_health.get("missing_expected_files") or [])
    mismatched_files = list(manifest_health.get("hash_mismatch_files") or [])
    if not manifest_health.get("manifest_present"):
        status = "raw_manifest_missing"
    elif missing_files or mismatched_files:
        status = "raw_mirror_stale_or_mismatched"
    elif manifest_health.get("extra_files"):
        status = "raw_mirror_extra_files_need_review"
    else:
        status = "raw_mirror_current"
    stable_map_files = set(STABLE_MAP_REQUIRED_FILES)
    raw_blocks_map = bool(stable_map_files & (set(missing_files) | set(mismatched_files)))
    return {
        "canonical_expected": int(counts.get("canonical_expected") or 0),
        "observed": int(counts.get("observed") or 0),
        "missing_expected": int(counts.get("missing_expected") or 0),
        "hash_mismatch": int(counts.get("hash_mismatch") or 0),
        "missing_files": missing_files,
        "mismatched_files": mismatched_files,
        "extra_files": list(manifest_health.get("extra_files") or []),
        "raw_mirror_status": status,
        "raw_mirror_blocks_app_visible_map": raw_blocks_map,
    }


def build_app_visible_map_status(
    *,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    map_receipt_path: str | Path = DEFAULT_MAP_RECEIPT_PATH,
    map_sync_request_path: str | Path = DEFAULT_MAP_SYNC_REQUEST_MARKER_PATH,
) -> dict[str, Any]:
    manifest = _map_manifest_payload(read_model_root=read_model_root)
    pc_surface = _map_snapshot_surface_status(read_model_root=read_model_root)
    presence = _map_file_presence(read_model_root=read_model_root, manifest_path=manifest_path)
    receipt = build_receipt_status(
        map_manifest=manifest,
        map_receipt_path=map_receipt_path,
        manifest_path=manifest_path,
    )
    pc_has_required = bool(
        presence["snapshot_present_on_pc"]
        and presence["manifest_present_on_pc"]
        and presence["operator_digest_present_on_pc"]
        and manifest.get("map_generation_id")
        and manifest.get("bundle_hash")
    )
    mac_has_required = bool(
        presence["mac_snapshot_present"]
        and presence["mac_manifest_present"]
        and presence["mac_operator_digest_present"]
    )
    request_marker = Path(map_sync_request_path)
    request_present = request_marker.is_file()

    if not pc_has_required:
        map_status = "unknown_fail_closed"
        next_actor = "pc_sync_health_worker"
        recommended_fix = "generate stable map bundle on PC before requesting Mac import"
    elif receipt["receipt_matches_pc_bundle"]:
        map_status = "map_current"
        next_actor = "none"
        recommended_fix = "none"
    elif mac_has_required and receipt["map_receipt_present"]:
        map_status = "map_hash_mismatch"
        next_actor = "mac_map_import_agent"
        recommended_fix = "re-import stable map bundle through the normal map sync lifecycle"
    elif mac_has_required:
        map_status = "map_receipt_missing"
        next_actor = "mac_map_import_agent"
        recommended_fix = "Mac has stable map files, but PC lacks a matching map receipt"
    elif request_present:
        map_status = "map_generation_pending_mac_import"
        next_actor = "mac_map_import_agent"
        recommended_fix = "Map generated on PC; waiting for Mac import receipt"
    else:
        map_status = "map_missing_from_mac"
        next_actor = "mac_map_import_agent"
        recommended_fix = "Write bounded map sync request marker for normal Mac import"

    return {
        "map_status": map_status,
        "map_generation_id": manifest.get("map_generation_id"),
        "bundle_hash": manifest.get("bundle_hash"),
        **presence,
        "mac_receipt_present": bool(receipt["map_receipt_present"]),
        "mac_receipt_present_in_manifest": bool(receipt["map_receipt_present_in_mac_manifest"]),
        "receipt_matches_pc_bundle": bool(receipt["receipt_matches_pc_bundle"]),
        "agent_dossier_cards_present": bool(receipt["agent_dossier_cards_present"] or pc_surface["agent_council_present"]),
        "agent_dossier_cards_count": max(receipt["agent_dossier_cards_count"], pc_surface["agent_dossier_cards_count"]),
        "agent_dossier_cards_path": receipt["agent_dossier_cards_path"],
        "agent_dossier_cards_path_status": receipt["agent_dossier_cards_path_status"],
        "cassandra_card_present": bool(receipt["cassandra_card_present"] or pc_surface["cassandra_card_present"]),
        "system_loop_cards_present": bool(receipt["system_loop_cards_present"] or pc_surface["system_loop_cards_present"]),
        "no_image_body_embedded": bool(receipt["no_image_body_embedded"] or pc_surface["no_image_body_embedded"]),
        "agent_council_present": bool(receipt["agent_council_present"] or pc_surface["agent_council_present"]),
        "package_preview_summary_present": bool(
            receipt["package_preview_summary_present"] or pc_surface["package_preview_summary_present"]
        ),
        "package_preview_example_count": max(
            receipt["package_preview_example_count"], pc_surface["package_preview_example_count"]
        ),
        "cassandra_capital_hilton_preview_present": bool(
            receipt["cassandra_capital_hilton_preview_present"]
            or pc_surface["cassandra_capital_hilton_preview_present"]
        ),
        "chief_check_engine_preview_present": bool(
            receipt["chief_check_engine_preview_present"] or pc_surface["chief_check_engine_preview_present"]
        ),
        "agentic_loop_classification_preview_present": bool(
            receipt["agentic_loop_classification_preview_present"]
            or pc_surface["agentic_loop_classification_preview_present"]
        ),
        "tool_adapter_receipt_summary_present": bool(
            receipt["tool_adapter_receipt_summary_present"] or pc_surface["tool_adapter_receipt_summary_present"]
        ),
        "tool_adapter_receipt_example_count": max(
            receipt["tool_adapter_receipt_example_count"], pc_surface["tool_adapter_receipt_example_count"]
        ),
        "stable_map_reader_adapter_present": bool(
            receipt["stable_map_reader_adapter_present"] or pc_surface["stable_map_reader_adapter_present"]
        ),
        "cassandra_capital_hilton_adapter_present": bool(
            receipt["cassandra_capital_hilton_adapter_present"]
            or pc_surface["cassandra_capital_hilton_adapter_present"]
        ),
        "browser_oauth_blocked_adapter_present": bool(
            receipt["browser_oauth_blocked_adapter_present"] or pc_surface["browser_oauth_blocked_adapter_present"]
        ),
        "gmail_calendar_blocked_adapter_present": bool(
            receipt["gmail_calendar_blocked_adapter_present"] or pc_surface["gmail_calendar_blocked_adapter_present"]
        ),
        "coupa_blocked_adapter_present": bool(
            receipt["coupa_blocked_adapter_present"] or pc_surface["coupa_blocked_adapter_present"]
        ),
        "telegram_blocked_adapter_present": bool(
            receipt["telegram_blocked_adapter_present"] or pc_surface["telegram_blocked_adapter_present"]
        ),
        "capital_hilton_summary_present": bool(
            receipt["capital_hilton_summary_present"] or pc_surface["capital_hilton_summary_present"]
        ),
        "capital_hilton_current_phase": receipt["capital_hilton_current_phase"] or pc_surface["capital_hilton_current_phase"],
        "capital_hilton_target_world": receipt["capital_hilton_target_world"] or pc_surface["capital_hilton_target_world"],
        "capital_hilton_lane_destiny": receipt["capital_hilton_lane_destiny"] or pc_surface["capital_hilton_lane_destiny"],
        "capital_hilton_missing_proof_count": max(
            receipt["capital_hilton_missing_proof_count"], pc_surface["capital_hilton_missing_proof_count"]
        ),
        "capital_hilton_protected_proof_required": bool(
            receipt["capital_hilton_protected_proof_required"]
            or pc_surface["capital_hilton_protected_proof_required"]
        ),
        "capital_hilton_candidate_facts_marked_not_proven": bool(
            receipt["capital_hilton_candidate_facts_marked_not_proven"]
            or pc_surface["capital_hilton_candidate_facts_marked_not_proven"]
        ),
        "capital_hilton_operator_questions_count": max(
            receipt["capital_hilton_operator_questions_count"], pc_surface["capital_hilton_operator_questions_count"]
        ),
        "capital_hilton_authority_flags_false": bool(
            receipt["capital_hilton_authority_flags_false"] or pc_surface["capital_hilton_authority_flags_false"]
        ),
        "capital_hilton_protected_proof_intake_present": bool(
            receipt["capital_hilton_protected_proof_intake_present"]
            or pc_surface["capital_hilton_protected_proof_intake_present"]
        ),
        "proof_items_count": max(
            receipt["capital_hilton_protected_proof_intake_proof_items_count"],
            pc_surface["capital_hilton_protected_proof_intake_proof_items_count"],
        ),
        "missing_proof_count": max(
            receipt["capital_hilton_protected_proof_intake_missing_proof_count"],
            pc_surface["capital_hilton_protected_proof_intake_missing_proof_count"],
        ),
        "protected_proof_required": bool(
            receipt["capital_hilton_protected_proof_intake_protected_proof_required"]
            or pc_surface["capital_hilton_protected_proof_intake_protected_proof_required"]
        ),
        "candidate_facts_proven": bool(
            receipt["capital_hilton_protected_proof_intake_candidate_facts_proven"]
            or pc_surface["capital_hilton_protected_proof_intake_candidate_facts_proven"]
        ),
        "guardian_gates_present": bool(
            receipt["capital_hilton_protected_proof_intake_guardian_gates_present"]
            or pc_surface["capital_hilton_protected_proof_intake_guardian_gates_present"]
        ),
        "operator_answer_candidates_present": bool(
            receipt["capital_hilton_protected_proof_intake_operator_answer_candidates_present"]
            or pc_surface["capital_hilton_protected_proof_intake_operator_answer_candidates_present"]
        ),
        "protected_evidence_requirements_present": bool(
            receipt["capital_hilton_protected_proof_intake_protected_evidence_requirements_present"]
            or pc_surface["capital_hilton_protected_proof_intake_protected_evidence_requirements_present"]
        ),
        "capital_hilton_protected_proof_intake_authority_flags_false": bool(
            receipt["capital_hilton_protected_proof_intake_authority_flags_false"]
            or pc_surface["capital_hilton_protected_proof_intake_authority_flags_false"]
        ),
        "capital_hilton_finance_present": bool(pc_surface["capital_hilton_finance_present"]),
        "system_awareness_discovery_present": bool(pc_surface["system_awareness_discovery_present"]),
        "future_gated_cue_autonomy_present": bool(pc_surface["future_gated_cue_autonomy_present"]),
        "operator_memory_not_proof": bool(pc_surface["operator_memory_not_proof"]),
        "no_live_execution_authority": bool(pc_surface["no_live_execution_authority"]),
        "raw_private_body_absent": bool(receipt["raw_private_body_absent"] or pc_surface["raw_private_body_absent"]),
        "no_credentials_secrets_embedded": bool(
            receipt["no_credentials_secrets_embedded"] or pc_surface["no_credentials_secrets_embedded"]
        ),
        "live_activation_flags_false": bool(
            receipt["live_activation_flags_false"] or pc_surface["no_live_execution_authority"]
        ),
        "security_audit_readiness_present": bool(
            receipt["security_audit_readiness_present"] or pc_surface["security_audit_readiness_present"]
        ),
        "ready_for_security_pass": bool(
            receipt["ready_for_security_pass"] or pc_surface["ready_for_security_pass"]
        ),
        "security_approval_granted": bool(
            receipt["security_approval_granted"] or pc_surface["security_approval_granted"]
        ),
        "action_authority_granted": bool(
            receipt["action_authority_granted"] or pc_surface["action_authority_granted"]
        ),
        "coverage_gap_records_count": max(
            receipt["coverage_gap_records_count"], pc_surface["coverage_gap_records_count"]
        ),
        "parked_breadcrumb_count": max(
            receipt["parked_breadcrumb_count"], pc_surface["parked_breadcrumb_count"]
        ),
        "capital_hilton_security_readiness_present": bool(
            receipt["capital_hilton_security_readiness_present"]
            or pc_surface["capital_hilton_security_readiness_present"]
        ),
        "security_pass_present": bool(
            receipt["security_pass_present"] or pc_surface["security_pass_present"]
        ),
        "security_pass_completed": bool(
            receipt["security_pass_completed"] or pc_surface["security_pass_completed"]
        ),
        "read_only_surfaces_approved": bool(
            receipt["read_only_surfaces_approved"] or pc_surface["read_only_surfaces_approved"]
        ),
        "preview_surfaces_approved": bool(
            receipt["preview_surfaces_approved"] or pc_surface["preview_surfaces_approved"]
        ),
        "security_pass_action_authority_granted": bool(
            receipt["security_pass_action_authority_granted"]
            or pc_surface["security_pass_action_authority_granted"]
        ),
        "worker_output_intake_summary_present": bool(
            receipt["worker_output_intake_summary_present"]
            or pc_surface["worker_output_intake_summary_present"]
        ),
        "orphaned_capability_summary_present": bool(
            receipt["orphaned_capability_summary_present"]
            or pc_surface["orphaned_capability_summary_present"]
        ),
        "chief_hermes_trust_summary_present": bool(
            receipt["chief_hermes_trust_summary_present"]
            or pc_surface["chief_hermes_trust_summary_present"]
        ),
        "post_security_governance_batch_present": bool(
            receipt["post_security_governance_batch_present"]
            or pc_surface["post_security_governance_batch_present"]
        ),
        "parked_capital_experiment_present": bool(
            receipt["parked_capital_experiment_present"]
            or pc_surface["parked_capital_experiment_present"]
        ),
        "security_delta_review_present": bool(
            receipt["security_delta_review_present"] or pc_surface["security_delta_review_present"]
        ),
        "operator_attention_promotion_present": bool(
            receipt["operator_attention_promotion_present"]
            or pc_surface["operator_attention_promotion_present"]
        ),
        "chief_test_harness_cross_off_present": bool(
            receipt["chief_test_harness_cross_off_present"]
            or pc_surface["chief_test_harness_cross_off_present"]
        ),
        "all_live_authority_flags_false": bool(
            receipt["all_live_authority_flags_false"]
            or receipt["security_pass_all_live_authority_flags_false"]
            or receipt["post_security_governance_authority_flags_false"]
            or pc_surface["post_security_governance_all_live_authority_flags_false"]
            or pc_surface["security_pass_all_live_authority_flags_false"]
            or pc_surface["security_all_authority_flags_false"]
            or pc_surface["no_live_execution_authority"]
        ),
        "app_visible": map_status == "map_current",
        "next_expected_actor": next_actor,
        "operator_action_required": False,
        "recommended_fix": recommended_fix,
        "map_sync_request_marker_path": Path(map_sync_request_path).as_posix(),
        "map_sync_request_marker_present": request_present,
        "target_mac_local_mirror_path": DEFAULT_MAC_LOCAL_MAP_ROOT,
        "required_files": list(STABLE_MAP_REQUIRED_FILES),
        "optional_future_receipt": STABLE_MAP_OPTIONAL_RECEIPT_FILE,
    }


def build_check_transmission_display(
    *,
    app_visible_map_status: dict[str, Any],
    raw_read_model_mirror_status: dict[str, Any],
    receipt_status: dict[str, Any],
) -> dict[str, Any]:
    map_status = app_visible_map_status["map_status"]
    if map_status == "map_current":
        lamp_state = "QUIET"
        headline = "Stable map bundle current"
        operator_summary = "Mission Control can trust the app-facing map bundle; raw read-model differences stay in proof/detail."
        primary_cause = "map_generation_and_receipt_match"
    elif map_status == "map_generation_pending_mac_import":
        lamp_state = "WARNING"
        headline = "Stable map bundle pending"
        operator_summary = "Map generated on PC; waiting for Mac import receipt."
        primary_cause = "pc_map_generated_waiting_for_mac_import"
    elif map_status == "map_receipt_missing":
        lamp_state = "WARNING"
        headline = "Stable map receipt missing"
        operator_summary = "Mac appears to have stable map files, but PC has not received a matching receipt."
        primary_cause = "map_receipt_missing"
    elif map_status == "map_missing_from_mac":
        lamp_state = "WARNING"
        headline = "Stable map bundle pending"
        operator_summary = "Stable map files are generated on PC but absent from the Mac mirror proof."
        primary_cause = "stable_map_files_missing_from_mac_manifest"
    elif map_status == "map_hash_mismatch":
        lamp_state = "ON"
        headline = "Stable map bundle hash mismatch"
        operator_summary = "Mac map receipt or files do not match the current PC bundle hash."
        primary_cause = "map_hash_or_receipt_mismatch"
    else:
        lamp_state = "ON"
        headline = "Stable map status unknown"
        operator_summary = "Stable map proof is not sufficient; fail closed."
        primary_cause = "unknown_fail_closed"

    raw_detail = (
        f"raw_status={raw_read_model_mirror_status['raw_mirror_status']}; "
        f"missing={raw_read_model_mirror_status['missing_expected']}; "
        f"hash_mismatch={raw_read_model_mirror_status['hash_mismatch']}"
    )
    return {
        "lamp_state": lamp_state,
        "headline": headline,
        "operator_summary": operator_summary,
        "proof_summary": {
            "map_status": map_status,
            "map_generation_id": app_visible_map_status.get("map_generation_id"),
            "bundle_hash": app_visible_map_status.get("bundle_hash"),
            "receipt_matches_pc_bundle": receipt_status.get("receipt_matches_pc_bundle"),
        },
        "primary_cause": primary_cause,
        "secondary_raw_mirror_detail": raw_detail,
        "next_safe_move": app_visible_map_status["recommended_fix"],
    }


def build_sync_health_map_raw_split(
    *,
    manifest_health: dict[str, Any] | None = None,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    repo_root: str | Path = ROOT,
    map_receipt_path: str | Path = DEFAULT_MAP_RECEIPT_PATH,
    map_sync_request_path: str | Path = DEFAULT_MAP_SYNC_REQUEST_MARKER_PATH,
) -> dict[str, Any]:
    resolved_manifest_health = manifest_health or compare_manifest_to_backend(
        manifest_path=manifest_path,
        read_model_root=read_model_root,
        repo_root=repo_root,
    )
    map_manifest = _map_manifest_payload(read_model_root=read_model_root)
    app_status = build_app_visible_map_status(
        read_model_root=read_model_root,
        manifest_path=manifest_path,
        map_receipt_path=map_receipt_path,
        map_sync_request_path=map_sync_request_path,
    )
    raw_status = build_raw_read_model_mirror_status(resolved_manifest_health)
    receipt_status = build_receipt_status(
        map_manifest=map_manifest,
        map_receipt_path=map_receipt_path,
        manifest_path=manifest_path,
    )
    if app_status.get("map_status") == "map_current":
        raw_status = {
            **raw_status,
            "raw_mirror_blocks_app_visible_map": False,
            "raw_mirror_app_visible_block_cleared_by_receipt": True,
            "raw_mirror_detail_only_reason": (
                "Mac stable-map receipt matches the PC map generation and bundle hash; "
                "raw generated read-model mismatches remain proof/detail."
            ),
        }
    transmission = build_check_transmission_display(
        app_visible_map_status=app_status,
        raw_read_model_mirror_status=raw_status,
        receipt_status=receipt_status,
    )
    return {
        "app_visible_map_status": app_status,
        "raw_read_model_mirror_status": raw_status,
        "receipt_status": receipt_status,
        "check_transmission_display": transmission,
    }


def _write_stable_map_bundle_generation(
    *,
    read_model_root: str | Path,
    marker_path: str | Path,
    map_generation_id: str,
) -> dict[str, Any]:
    root = Path(read_model_root)
    generation_root = Path(marker_path).parent / "map_bundle" / map_generation_id
    generation_root.mkdir(parents=True, exist_ok=True)
    written_files: list[dict[str, Any]] = []
    for name in STABLE_MAP_REQUIRED_FILES:
        source = root / name
        target = generation_root / name
        target.write_bytes(source.read_bytes())
        written_files.append(
            {
                "relative_path": name,
                "source_path": source.as_posix(),
                "bundle_source_path": target.as_posix(),
                "sha256": sha256_file(target),
                "hash_algorithm": "sha256",
            }
        )
    return {
        "bundle_generation_path": generation_root.as_posix(),
        "bundle_files_written": written_files,
    }


def write_openclaw_map_sync_required_marker_if_needed(
    *,
    app_visible_map_status: dict[str, Any],
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    marker_path: str | Path = DEFAULT_MAP_SYNC_REQUEST_MARKER_PATH,
    target_mac_local_mirror_path: str = DEFAULT_MAC_LOCAL_MAP_ROOT,
) -> dict[str, Any]:
    if app_visible_map_status.get("map_status") == "map_current":
        return {
            "map_sync_marker_needed": False,
            "map_sync_marker_written": False,
            "reason": "stable map bundle is already current",
            "marker_path": Path(marker_path).as_posix(),
        }
    if not (
        app_visible_map_status.get("snapshot_present_on_pc")
        and app_visible_map_status.get("manifest_present_on_pc")
        and app_visible_map_status.get("operator_digest_present_on_pc")
    ):
        return {
            "map_sync_marker_needed": False,
            "map_sync_marker_written": False,
            "reason": "stable map bundle files are not all present on PC",
            "marker_path": Path(marker_path).as_posix(),
        }

    marker = Path(marker_path)
    marker.parent.mkdir(parents=True, exist_ok=True)
    root = Path(read_model_root)
    map_generation_id = str(app_visible_map_status.get("map_generation_id") or "unknown_fail_closed")
    bundle_write = _write_stable_map_bundle_generation(
        read_model_root=root,
        marker_path=marker,
        map_generation_id=map_generation_id,
    )
    bundle_root = Path(bundle_write["bundle_generation_path"])
    required_files = [
        {
            "relative_path": name,
            "source_path": (bundle_root / name).as_posix(),
            "canonical_source_path": (root / name).as_posix(),
            "target_path": f"{target_mac_local_mirror_path}/{name}",
            "sha256": sha256_file(bundle_root / name),
            "hash_algorithm": "sha256",
        }
        for name in STABLE_MAP_REQUIRED_FILES
    ]
    payload = {
        "schema_version": "openclaw_map_sync_required_v0",
        "created_at": utc_now(),
        "map_generation_id": app_visible_map_status.get("map_generation_id"),
        "bundle_hash": app_visible_map_status.get("bundle_hash"),
        "required_files": required_files,
        "bundle_generation_path": bundle_write["bundle_generation_path"],
        "bundle_files_written": bundle_write["bundle_files_written"],
        "optional_future_receipt": {
            "relative_path": STABLE_MAP_OPTIONAL_RECEIPT_FILE,
            "target_path": f"{target_mac_local_mirror_path}/{STABLE_MAP_OPTIONAL_RECEIPT_FILE}",
            "schema_version": STABLE_MAP_RECEIPT_SCHEMA_VERSION,
        },
        "source_path": bundle_write["bundle_generation_path"],
        "canonical_source_path": root.as_posix(),
        "target_mac_local_mirror_path": target_mac_local_mirror_path,
        "expected_next_actor": "mac_map_import_agent",
        "next_expected_actor": "mac_map_import_agent",
        "fallback_actor": "mac_read_model_sync_agent",
        "do_not_fake_completion": True,
        "no_execution_no_credential_no_network_boundary": {
            "execution_authority": False,
            "credential_handling_allowed": False,
            "network_authority": False,
        },
        "no_authority_flags": dict(MAP_SYNC_NO_AUTHORITY_FLAGS),
        **MAP_SYNC_NO_AUTHORITY_FLAGS,
    }
    marker.write_text(stable_json(payload), encoding="utf-8")
    return {
        "map_sync_marker_needed": True,
        "map_sync_marker_written": True,
        "marker_path": marker.as_posix(),
        "map_generation_id": app_visible_map_status.get("map_generation_id"),
        "bundle_hash": app_visible_map_status.get("bundle_hash"),
        "required_files": list(STABLE_MAP_REQUIRED_FILES),
        "bundle_generation_path": bundle_write["bundle_generation_path"],
        "expected_next_actor": "mac_map_import_agent",
    }


def _mtime_iso(path: str | Path) -> str | None:
    try:
        return datetime.fromtimestamp(Path(path).stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat()
    except OSError:
        return None


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _json_list(values: list[str]) -> str:
    return stable_json(values)


def compare_manifest_to_backend(
    *,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    repo_root: str | Path = ROOT,
) -> dict[str, Any]:
    manifest = Path(manifest_path)
    records = canonical_generated_read_model_records(
        source_root=read_model_root,
        repo_root=repo_root,
        include_hash=True,
    )
    expected_records = {item["relative_path"]: item for item in records}
    expected = set(expected_records)
    if not manifest.is_file():
        return {
            "manifest_present": False,
            "manifest_path": manifest.as_posix(),
            "manifest_sha256": None,
            "counts": {
                "canonical_expected": len(expected),
                "observed": 0,
                "missing_expected": len(expected),
                "extra": 0,
                "hash_mismatch": 0,
                "matched_hash": 0,
            },
            "missing_expected_files": sorted(expected),
            "extra_files": [],
            "hash_mismatch_files": [],
        }
    payload = _read_json_object(manifest) or {}
    path_records = payload.get("path_records") or []
    observed_records = {
        record.get("relative_path"): record
        for record in path_records
        if isinstance(record, dict) and isinstance(record.get("relative_path"), str)
    }
    observed = set(observed_records)
    matched: list[str] = []
    mismatched: list[str] = []
    for relative_path in sorted(expected & observed):
        expected_hash = expected_records[relative_path].get("sha256")
        observed_hash = observed_records[relative_path].get("content_hash")
        if relative_path in SELF_EXPORT_FILES and observed_hash:
            matched.append(relative_path)
        elif expected_hash and observed_hash and expected_hash == observed_hash:
            matched.append(relative_path)
        elif expected_hash and observed_hash and expected_hash != observed_hash:
            mismatched.append(relative_path)
    return {
        "manifest_present": True,
        "manifest_path": manifest.as_posix(),
        "manifest_sha256": sha256_file(manifest),
        "counts": {
            "canonical_expected": len(expected),
            "observed": len(observed),
            "missing_expected": len(expected - observed),
            "extra": len(observed - expected),
            "hash_mismatch": len(mismatched),
            "matched_hash": len(matched),
        },
        "missing_expected_files": sorted(expected - observed),
        "extra_files": sorted(observed - expected),
        "hash_mismatch_files": mismatched,
    }


def _status_marker(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path) or {}
    return {
        "present": path.is_file(),
        "status": payload.get("status") if isinstance(payload.get("status"), str) else None,
        "time": payload.get("generated_at") if isinstance(payload.get("generated_at"), str) else _mtime_iso(path),
        "marker_seen": bool(payload.get("marker_seen")) if payload else False,
        "manifest_written": bool(payload.get("manifest_written")) if payload else False,
        "hash": sha256_file(path) if path.is_file() else None,
    }


def _completion_marker(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path) or {}
    return {
        "present": path.is_file(),
        "status": payload.get("status") if isinstance(payload.get("status"), str) else None,
        "time": payload.get("generated_at") if isinstance(payload.get("generated_at"), str) else _mtime_iso(path),
        "manifest_written": bool(payload.get("manifest_sha256") or payload.get("manifest_path")) if payload else False,
        "hash": sha256_file(path) if path.is_file() else None,
    }


def _pc_import_state(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path) or {}
    return {
        "present": path.is_file(),
        "status": payload.get("status") if isinstance(payload.get("status"), str) else None,
        "time": (
            payload.get("last_imported_at")
            if isinstance(payload.get("last_imported_at"), str)
            else payload.get("updated_at")
            if isinstance(payload.get("updated_at"), str)
            else _mtime_iso(path)
        ),
        "manifest_hash": (
            payload.get("last_successful_manifest_sha256")
            if isinstance(payload.get("last_successful_manifest_sha256"), str)
            else None
        ),
        "hash": sha256_file(path) if path.is_file() else None,
    }


def _request_marker_state(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path) or {}
    return {
        "present": path.is_file(),
        "status": payload.get("status") if isinstance(payload.get("status"), str) else None,
        "time": payload.get("generated_at") if isinstance(payload.get("generated_at"), str) else _mtime_iso(path),
        "next_expected_responder": (
            payload.get("next_expected_responder")
            if isinstance(payload.get("next_expected_responder"), str)
            else None
        ),
        "hash": sha256_file(path) if path.is_file() else None,
    }


def _self_report_state(read_model_root: str | Path, manifest_path: str | Path) -> dict[str, Any]:
    root = Path(read_model_root)
    manifest_time = _parse_time(_mtime_iso(manifest_path))
    present_files: list[str] = []
    newer_files: list[str] = []
    for relative_path in sorted(SELF_EXPORT_FILES):
        path = root / relative_path
        if not path.is_file():
            continue
        present_files.append(relative_path)
        file_time = _parse_time(_mtime_iso(path))
        if manifest_time and file_time and file_time > manifest_time:
            newer_files.append(relative_path)
    return {
        "present": bool(present_files),
        "present_files": present_files,
        "newer_than_manifest": bool(newer_files),
        "newer_files": newer_files,
    }


def _classification(
    *,
    trust_status: str,
    mirror_status: str,
    display_status: str,
    recommended_fix_kind: str,
    next_safe_move: str,
    next_expected_actor: str,
    can_request_fix_from_app: bool,
    sync_lifecycle_state: str,
    operator_action_required: bool | None = None,
) -> dict[str, Any]:
    if operator_action_required is None:
        operator_action_required = sync_lifecycle_state in ACTIONABLE_SYNC_LIFECYCLE_STATES
    return {
        "trust_status": trust_status,
        "mirror_status": mirror_status,
        "display_status": display_status,
        "recommended_fix_kind": recommended_fix_kind,
        "next_safe_move": next_safe_move,
        "next_expected_actor": next_expected_actor,
        "can_request_fix_from_app": can_request_fix_from_app,
        "sync_lifecycle_state": sync_lifecycle_state,
        "operator_action_required": operator_action_required,
        "operator_interrupt_policy": OPERATOR_INTERRUPT_POLICY,
    }


def classify_sync_health(
    *,
    manifest_health: dict[str, Any],
    mac_status: dict[str, Any],
    mac_completion: dict[str, Any],
    pc_state: dict[str, Any],
    request_marker: dict[str, Any],
    self_report: dict[str, Any],
    windows_task_log_present: bool,
) -> dict[str, Any]:
    counts = manifest_health["counts"]
    missing = int(counts.get("missing_expected") or 0)
    extra = int(counts.get("extra") or 0)
    mismatched = int(counts.get("hash_mismatch") or 0)
    if not manifest_health.get("manifest_present"):
        return _classification(
            trust_status="unknown_review",
            mirror_status="unknown",
            display_status="manifest_missing",
            recommended_fix_kind="inspect_automation",
            next_safe_move="Mac manifest is missing; inspect the Mac sync service and shared E-drive mount.",
            next_expected_actor="operator_review",
            can_request_fix_from_app=False,
            sync_lifecycle_state="actionable_sync_failure",
        )
    if missing > 0 or mismatched > 0:
        request_time = _parse_time(request_marker.get("time"))
        completion_time = _parse_time(mac_completion.get("time"))
        if request_marker.get("present") and not (request_time and completion_time and completion_time > request_time):
            return _classification(
                trust_status="stale_needs_mac_sync",
                mirror_status="needs_mac_sync",
                display_status="sync_requested_waiting_for_mac",
                recommended_fix_kind="wait_for_mac_sync",
                next_safe_move="Mac sync has already been requested; waiting for the normal Mac sync agent cycle.",
                next_expected_actor="mac_sync_agent",
                can_request_fix_from_app=False,
                sync_lifecycle_state="sync_requested_waiting_for_mac",
                operator_action_required=False,
            )
        return _classification(
            trust_status="stale_needs_mac_sync",
            mirror_status="needs_mac_sync",
            display_status="needs_mac_sync",
            recommended_fix_kind="request_mac_sync",
            next_safe_move="Request Mac sync through the shared marker and let the Mac LaunchAgent refresh the mirror.",
            next_expected_actor="mac_sync_agent",
            can_request_fix_from_app=True,
            sync_lifecycle_state="actionable_sync_failure",
        )
    if extra > 0:
        return _classification(
            trust_status="mismatch",
            mirror_status="error",
            display_status="manual_review",
            recommended_fix_kind="manual_review",
            next_safe_move="Review extra Mac mirror files before treating the mirror as trusted.",
            next_expected_actor="operator_review",
            can_request_fix_from_app=False,
            sync_lifecycle_state="actionable_sync_failure",
        )
    manifest_hash = manifest_health.get("manifest_sha256")
    completion_time = _parse_time(mac_completion.get("time"))
    import_time = _parse_time(pc_state.get("time"))
    state_hash = pc_state.get("manifest_hash")
    if pc_state.get("present") and manifest_hash and state_hash and state_hash != manifest_hash:
        return _classification(
            trust_status="stale_needs_pc_import",
            mirror_status="needs_pc_import",
            display_status="waiting_for_pc_import",
            recommended_fix_kind="wait_for_pc_import",
            next_safe_move="Mac sync appears complete. Waiting for PC import task.",
            next_expected_actor="pc_import_task",
            can_request_fix_from_app=False,
            sync_lifecycle_state="mac_synced_waiting_for_pc_import",
            operator_action_required=False,
        )
    if completion_time and import_time and completion_time > import_time:
        return _classification(
            trust_status="stale_needs_pc_import",
            mirror_status="needs_pc_import",
            display_status="waiting_for_pc_import",
            recommended_fix_kind="wait_for_pc_import",
            next_safe_move="Mac sync appears complete. Waiting for PC import task.",
            next_expected_actor="pc_import_task",
            can_request_fix_from_app=False,
            sync_lifecycle_state="mac_synced_waiting_for_pc_import",
            operator_action_required=False,
        )
    proof_present = bool(
        (mac_status.get("present") or mac_completion.get("present"))
        and (pc_state.get("present") or windows_task_log_present)
    )
    if proof_present:
        if self_report.get("newer_than_manifest"):
            return _classification(
                trust_status="trusted",
                mirror_status="ok",
                display_status="current",
                recommended_fix_kind="none",
                next_safe_move="Sync health is current on PC and waiting for the normal Mac mirror cycle to pick up the latest health read-model.",
                next_expected_actor="mac_sync_agent",
                can_request_fix_from_app=False,
                sync_lifecycle_state="health_exported_waiting_for_mac_mirror",
                operator_action_required=False,
            )
        return _classification(
            trust_status="trusted",
            mirror_status="ok",
            display_status="current",
            recommended_fix_kind="none",
            next_safe_move="No sync repair is needed.",
            next_expected_actor="none",
            can_request_fix_from_app=False,
            sync_lifecycle_state="trusted_current",
            operator_action_required=False,
        )
    return _classification(
        trust_status="degraded",
        mirror_status="ok",
        display_status="degraded",
        recommended_fix_kind="inspect_automation",
        next_safe_move="Mirror content matches, but automation proof files are missing or incomplete.",
        next_expected_actor="operator_review",
        can_request_fix_from_app=False,
        sync_lifecycle_state="actionable_sync_failure",
    )

def _source_rows(
    *,
    run_id: str,
    generated_at: str,
    manifest_path: Path,
    mac_status_path: Path,
    mac_completion_path: Path,
    pc_state_path: Path,
    pc_task_log_path: Path,
    windows_task_log_path: Path,
    request_marker_path: Path,
    read_model_root_path: Path,
    mac_status: dict[str, Any],
    mac_completion: dict[str, Any],
    pc_state: dict[str, Any],
    request_marker: dict[str, Any],
    self_report: dict[str, Any],
) -> list[dict[str, Any]]:
    observed = [
        ("mac_manifest", manifest_path, manifest_path.is_file(), None, _mtime_iso(manifest_path), sha256_file(manifest_path) if manifest_path.is_file() else None),
        ("mac_heartbeat", mac_status_path, mac_status["present"], mac_status.get("status"), mac_status.get("time"), mac_status.get("hash")),
        ("mac_completion", mac_completion_path, mac_completion["present"], mac_completion.get("status"), mac_completion.get("time"), mac_completion.get("hash")),
        ("pc_import_state", pc_state_path, pc_state["present"], pc_state.get("status"), pc_state.get("time"), pc_state.get("hash")),
        ("read_model_sync_request_marker", request_marker_path, request_marker["present"], request_marker.get("status"), request_marker.get("time"), request_marker.get("hash")),
        ("sync_health_self_report", read_model_root_path, self_report["present"], "newer_than_manifest" if self_report.get("newer_than_manifest") else "not_newer", None, None),
        ("pc_task_log", pc_task_log_path, pc_task_log_path.is_file(), "present" if pc_task_log_path.is_file() else None, _mtime_iso(pc_task_log_path), None),
        ("windows_task_log", windows_task_log_path, windows_task_log_path.is_file(), "present" if windows_task_log_path.is_file() else None, _mtime_iso(windows_task_log_path), None),
    ]
    return [
        {
            "source_id": _row_id("synchealthsrc", run_id, source_kind, source_path.as_posix()),
            "run_id": run_id,
            "source_kind": source_kind,
            "source_path": source_path.as_posix(),
            "present": present,
            "observed_at": generated_at,
            "source_status": status,
            "source_time": source_time,
            "source_hash": source_hash,
        }
        for source_kind, source_path, present, status, source_time, source_hash in observed
    ]


def build_sync_health_snapshot(
    *,
    db_path: str | Path | None = None,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    repo_root: str | Path = ROOT,
    mac_status_path: str | Path = DEFAULT_MAC_STATUS_PATH,
    mac_completion_path: str | Path = DEFAULT_MAC_COMPLETION_PATH,
    pc_import_state_path: str | Path = DEFAULT_PC_IMPORT_STATE_PATH,
    pc_task_log_path: str | Path = DEFAULT_PC_TASK_LOG_PATH,
    windows_task_log_path: str | Path = DEFAULT_WINDOWS_TASK_LOG_PATH,
    request_marker_path: str | Path = DEFAULT_REQUEST_MARKER_PATH,
    app_request_marker_path: str = DEFAULT_APP_REQUEST_MARKER_PATH,
    run_id: str | None = None,
) -> SyncHealthBuildResult:
    path = init_sync_health_schema(db_path)
    generated_at = utc_now()
    resolved_run_id = run_id or _row_id("synchealthrun", generated_at)
    snapshot_id = _row_id("synchealthsnap", resolved_run_id, generated_at)

    manifest = Path(manifest_path)
    mac_status_file = Path(mac_status_path)
    mac_completion_file = Path(mac_completion_path)
    pc_state_file = Path(pc_import_state_path)
    pc_log_file = Path(pc_task_log_path)
    windows_log_file = Path(windows_task_log_path)
    request_marker = Path(request_marker_path)

    manifest_health = compare_manifest_to_backend(
        manifest_path=manifest,
        read_model_root=read_model_root,
        repo_root=repo_root,
    )
    mac_status = _status_marker(mac_status_file)
    mac_completion = _completion_marker(mac_completion_file)
    pc_state = _pc_import_state(pc_state_file)
    request_marker_state = _request_marker_state(request_marker)
    self_report = _self_report_state(read_model_root, manifest)
    windows_log_present = windows_log_file.is_file()
    pc_scheduler_known = bool(windows_log_present or pc_log_file.is_file() or pc_state["present"])
    classification = classify_sync_health(
        manifest_health=manifest_health,
        mac_status=mac_status,
        mac_completion=mac_completion,
        pc_state=pc_state,
        request_marker=request_marker_state,
        self_report=self_report,
        windows_task_log_present=windows_log_present,
    )
    counts = manifest_health["counts"]
    missing_files = list(manifest_health["missing_expected_files"])
    hash_mismatch_files = list(manifest_health["hash_mismatch_files"])
    stale_files = sorted(set(missing_files) | set(hash_mismatch_files))
    extra_files = list(manifest_health["extra_files"])

    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
INSERT INTO sync_health_runs (
  run_id, sync_health_version, created_at, completed_at,
  trust_status, mirror_status, recommended_fix_kind,
  app_direct_execution_allowed, arbitrary_command_allowed, remote_control_allowed,
  ssh_scp_rsync_allowed, docker_ollama_allowed, runtime_activation_allowed,
  agent_activation_allowed, file_delete_allowed, file_move_allowed
) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0)
ON CONFLICT(run_id) DO UPDATE SET
  completed_at = excluded.completed_at,
  trust_status = excluded.trust_status,
  mirror_status = excluded.mirror_status,
  recommended_fix_kind = excluded.recommended_fix_kind
""".strip(),
            (
                resolved_run_id,
                SYNC_HEALTH_VERSION,
                generated_at,
                generated_at,
                classification["trust_status"],
                classification["mirror_status"],
                classification["recommended_fix_kind"],
            ),
        )
        conn.execute("DELETE FROM sync_health_sources WHERE run_id = ?", (resolved_run_id,))
        conn.execute("DELETE FROM sync_health_recommendations WHERE run_id = ?", (resolved_run_id,))
        conn.execute("DELETE FROM sync_health_receipts WHERE run_id = ?", (resolved_run_id,))
        conn.execute(
            """
INSERT OR REPLACE INTO sync_health_snapshots (
  snapshot_id, run_id, generated_at, trust_status, mirror_status,
  canonical_expected, observed, missing_expected, extra, hash_mismatch,
  matched_hash, stale_files_json, missing_files_json, extra_files_json,
  mac_heartbeat_status, mac_heartbeat_time, mac_marker_seen,
  mac_manifest_written, mac_completion_status, mac_completion_time,
  pc_import_status, pc_import_time, pc_manifest_hash,
  windows_task_log_present, pc_scheduler_known, display_status,
  sync_lifecycle_state, operator_action_required, operator_interrupt_policy,
  next_expected_actor, next_safe_move, recommended_fix_kind,
  can_request_fix_from_app, request_marker_path,
  app_request_marker_path, no_authority_json, raw_body_stored
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
""".strip(),
            (
                snapshot_id,
                resolved_run_id,
                generated_at,
                classification["trust_status"],
                classification["mirror_status"],
                int(counts.get("canonical_expected") or 0),
                int(counts.get("observed") or 0),
                int(counts.get("missing_expected") or 0),
                int(counts.get("extra") or 0),
                int(counts.get("hash_mismatch") or 0),
                int(counts.get("matched_hash") or 0),
                _json_list(stale_files),
                _json_list(missing_files),
                _json_list(extra_files),
                mac_status.get("status"),
                mac_status.get("time"),
                1 if mac_status.get("marker_seen") else 0,
                1 if (mac_status.get("manifest_written") or mac_completion.get("manifest_written")) else 0,
                mac_completion.get("status"),
                mac_completion.get("time"),
                pc_state.get("status"),
                pc_state.get("time"),
                pc_state.get("manifest_hash"),
                1 if windows_log_present else 0,
                1 if pc_scheduler_known else 0,
                classification["display_status"],
                classification["sync_lifecycle_state"],
                1 if classification["operator_action_required"] else 0,
                classification["operator_interrupt_policy"],
                classification["next_expected_actor"],
                classification["next_safe_move"],
                classification["recommended_fix_kind"],
                1
                if (
                    classification["recommended_fix_kind"] == "request_mac_sync"
                    and classification["can_request_fix_from_app"]
                    and request_marker.as_posix().startswith("/mnt/e/openclaw/")
                )
                else 0,
                request_marker.as_posix(),
                app_request_marker_path,
                stable_json(NO_AUTHORITY_FLAGS),
            ),
        )
        for source in _source_rows(
            run_id=resolved_run_id,
            generated_at=generated_at,
            manifest_path=manifest,
            mac_status_path=mac_status_file,
            mac_completion_path=mac_completion_file,
            pc_state_path=pc_state_file,
            pc_task_log_path=pc_log_file,
            windows_task_log_path=windows_log_file,
            request_marker_path=request_marker,
            read_model_root_path=Path(read_model_root),
            mac_status=mac_status,
            mac_completion=mac_completion,
            pc_state=pc_state,
            request_marker=request_marker_state,
            self_report=self_report,
        ):
            conn.execute(
                """
INSERT INTO sync_health_sources (
  source_id, run_id, source_kind, source_path, present, observed_at,
  source_status, source_time, source_hash, raw_body_stored
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
""".strip(),
                (
                    source["source_id"],
                    source["run_id"],
                    source["source_kind"],
                    source["source_path"],
                    1 if source["present"] else 0,
                    source["observed_at"],
                    source["source_status"],
                    source["source_time"],
                    source["source_hash"],
                ),
            )
        conn.execute(
            """
INSERT INTO sync_health_recommendations (
  recommendation_id, run_id, snapshot_id, recommended_fix_kind,
  next_safe_move, next_expected_actor, can_request_fix_from_app, request_marker_path,
  app_request_marker_path, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""".strip(),
            (
                _row_id("synchealthrec", resolved_run_id, classification["recommended_fix_kind"]),
                resolved_run_id,
                snapshot_id,
                classification["recommended_fix_kind"],
                classification["next_safe_move"],
                classification["next_expected_actor"],
                1 if classification["recommended_fix_kind"] == "request_mac_sync" and classification["can_request_fix_from_app"] else 0,
                request_marker.as_posix(),
                app_request_marker_path,
                generated_at,
            ),
        )
        receipt_payload = {
            "run_id": resolved_run_id,
            "snapshot_id": snapshot_id,
            "trust_status": classification["trust_status"],
            "mirror_status": classification["mirror_status"],
            "recommended_fix_kind": classification["recommended_fix_kind"],
            "sync_lifecycle_state": classification["sync_lifecycle_state"],
            "operator_action_required": classification["operator_action_required"],
            "counts": counts,
            "stale_files": stale_files,
            **NO_AUTHORITY_FLAGS,
        }
        conn.execute(
            """
INSERT INTO sync_health_receipts (
  receipt_id, run_id, snapshot_id, receipt_kind, summary, payload_json, created_at
) VALUES (?, ?, ?, 'sync_health_snapshot', ?, ?, ?)
""".strip(),
            (
                _row_id("synchealthreceipt", resolved_run_id, snapshot_id),
                resolved_run_id,
                snapshot_id,
                f"Recorded sync health snapshot: {classification['trust_status']}.",
                stable_json(receipt_payload),
                generated_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return SyncHealthBuildResult(
        run_id=resolved_run_id,
        snapshot_id=snapshot_id,
        trust_status=classification["trust_status"],
        mirror_status=classification["mirror_status"],
        recommended_fix_kind=classification["recommended_fix_kind"],
        sync_lifecycle_state=classification["sync_lifecycle_state"],
        operator_action_required=classification["operator_action_required"],
        db_path=path,
    )


def _latest_snapshot(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        """
SELECT *
FROM sync_health_snapshots
ORDER BY generated_at DESC, snapshot_id DESC
LIMIT 1
""".strip()
    ).fetchone()


def _snapshot_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "snapshot_id": row["snapshot_id"],
        "run_id": row["run_id"],
        "generated_at": row["generated_at"],
        "trust_status": row["trust_status"],
        "mirror_status": row["mirror_status"],
        "canonical_expected": row["canonical_expected"],
        "observed": row["observed"],
        "missing_expected": row["missing_expected"],
        "extra": row["extra"],
        "hash_mismatch": row["hash_mismatch"],
        "matched_hash": row["matched_hash"],
        "stale_files": json.loads(row["stale_files_json"]),
        "missing_files": json.loads(row["missing_files_json"]),
        "extra_files": json.loads(row["extra_files_json"]),
        "mac_heartbeat_status": row["mac_heartbeat_status"],
        "mac_heartbeat_time": row["mac_heartbeat_time"],
        "mac_marker_seen": bool(row["mac_marker_seen"]),
        "mac_manifest_written": bool(row["mac_manifest_written"]),
        "mac_completion_status": row["mac_completion_status"],
        "mac_completion_time": row["mac_completion_time"],
        "pc_import_status": row["pc_import_status"],
        "pc_import_time": row["pc_import_time"],
        "pc_manifest_hash": row["pc_manifest_hash"],
        "windows_task_log_present": bool(row["windows_task_log_present"]),
        "pc_scheduler_known": bool(row["pc_scheduler_known"]),
        "display_status": row["display_status"],
        "sync_lifecycle_state": row["sync_lifecycle_state"],
        "operator_action_required": bool(row["operator_action_required"]),
        "operator_interrupt_policy": row["operator_interrupt_policy"],
        "next_expected_actor": row["next_expected_actor"],
        "next_safe_move": row["next_safe_move"],
        "recommended_fix_kind": row["recommended_fix_kind"],
        "can_request_fix_from_app": bool(row["can_request_fix_from_app"]),
        "request_marker_path": row["request_marker_path"],
        "app_request_marker_path": row["app_request_marker_path"],
        "no_authority_flags": json.loads(row["no_authority_json"]),
    }


REPORT_SECTIONS = {"summary", "proof"}


def build_sync_health_report(
    *,
    db_path: str | Path | None = None,
    report: str = "summary",
) -> dict[str, Any]:
    if report not in REPORT_SECTIONS:
        raise ValueError(f"unknown sync health report: {report}")
    path = init_sync_health_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        snapshot = _snapshot_dict(_latest_snapshot(conn))
        sources = []
        if report == "proof" and snapshot:
            sources = [
                dict(row)
                for row in conn.execute(
                    """
SELECT source_kind, source_path, present, source_status, source_time, source_hash
FROM sync_health_sources
WHERE run_id = ?
ORDER BY source_kind
""".strip(),
                    (snapshot["run_id"],),
                ).fetchall()
            ]
        return {
            "status": "ok" if snapshot else "empty",
            "report": report,
            "db_path": str(path),
            "latest_snapshot": snapshot,
            "sources": sources,
            "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        }
    finally:
        conn.close()


def build_sync_health_read_model(
    db_path: str | Path | None = None,
    *,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    repo_root: str | Path = ROOT,
    map_receipt_path: str | Path = DEFAULT_MAP_RECEIPT_PATH,
    map_sync_request_path: str | Path = DEFAULT_MAP_SYNC_REQUEST_MARKER_PATH,
) -> dict[str, Any]:
    report = build_sync_health_report(db_path=db_path, report="proof")
    snapshot = report["latest_snapshot"] or {}
    manifest_health = compare_manifest_to_backend(
        manifest_path=manifest_path,
        read_model_root=read_model_root,
        repo_root=repo_root,
    )
    map_raw_split = build_sync_health_map_raw_split(
        manifest_health=manifest_health,
        manifest_path=manifest_path,
        read_model_root=read_model_root,
        repo_root=repo_root,
        map_receipt_path=map_receipt_path,
        map_sync_request_path=map_sync_request_path,
    )
    return {
        "schema_version": READ_MODEL_VERSION,
        "generated_at": utc_now(),
        "source_ledger_path": str(db_path or DEFAULT_DB_PATH),
        "trust_status": snapshot.get("trust_status", "unknown_review"),
        "mirror_status": snapshot.get("mirror_status", "unknown"),
        "display_status": snapshot.get("display_status", "unknown_review"),
        "sync_lifecycle_state": snapshot.get("sync_lifecycle_state", "unknown_review"),
        "operator_action_required": snapshot.get("operator_action_required", False),
        "operator_interrupt_policy": snapshot.get("operator_interrupt_policy", OPERATOR_INTERRUPT_POLICY),
        "next_expected_actor": snapshot.get("next_expected_actor", "operator_review"),
        "canonical_expected": snapshot.get("canonical_expected", 0),
        "observed": snapshot.get("observed", 0),
        "missing_expected": snapshot.get("missing_expected", 0),
        "extra": snapshot.get("extra", 0),
        "hash_mismatch": snapshot.get("hash_mismatch", 0),
        "matched_hash": snapshot.get("matched_hash", 0),
        "stale_files": snapshot.get("stale_files", []),
        "missing_files": snapshot.get("missing_files", []),
        "extra_files": snapshot.get("extra_files", []),
        "last_mac_heartbeat": {
            "status": snapshot.get("mac_heartbeat_status"),
            "time": snapshot.get("mac_heartbeat_time"),
            "marker_seen": snapshot.get("mac_marker_seen", False),
            "manifest_written": snapshot.get("mac_manifest_written", False),
        },
        "last_mac_completion": {
            "status": snapshot.get("mac_completion_status"),
            "time": snapshot.get("mac_completion_time"),
        },
        "last_pc_import": {
            "status": snapshot.get("pc_import_status"),
            "time": snapshot.get("pc_import_time"),
            "manifest_hash": snapshot.get("pc_manifest_hash"),
            "windows_task_log_present": snapshot.get("windows_task_log_present", False),
            "pc_scheduler_known": snapshot.get("pc_scheduler_known", False),
        },
        "recommended_fix": {
            "kind": snapshot.get("recommended_fix_kind", "manual_review"),
            "display_status": snapshot.get("display_status", "unknown_review"),
            "next_expected_actor": snapshot.get("next_expected_actor", "operator_review"),
            "sync_lifecycle_state": snapshot.get("sync_lifecycle_state", "unknown_review"),
            "operator_action_required": snapshot.get("operator_action_required", False),
            "next_safe_move": snapshot.get("next_safe_move", "Build sync health before relying on this read-model."),
            "can_request_fix_from_app": snapshot.get("can_request_fix_from_app", False),
            "request_marker_path": snapshot.get("request_marker_path", DEFAULT_REQUEST_MARKER_PATH.as_posix()),
            "app_request_marker_path": snapshot.get("app_request_marker_path", DEFAULT_APP_REQUEST_MARKER_PATH),
        },
        "app_visible_map_status": map_raw_split["app_visible_map_status"],
        "raw_read_model_mirror_status": map_raw_split["raw_read_model_mirror_status"],
        "receipt_status": map_raw_split["receipt_status"],
        "check_transmission_display": map_raw_split["check_transmission_display"],
        "proof_sources": report["sources"],
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def _operator_markdown(payload: dict[str, Any]) -> str:
    recommended = payload["recommended_fix"]
    map_status = payload["app_visible_map_status"]
    raw_status = payload["raw_read_model_mirror_status"]
    transmission = payload["check_transmission_display"]
    lines = [
        "# OpenClaw Sync Health",
        "",
        f"Trust status: `{payload['trust_status']}`",
        f"Mirror status: `{payload['mirror_status']}`",
        f"Display status: `{payload['display_status']}`",
        f"Lifecycle state: `{payload['sync_lifecycle_state']}`",
        f"Operator action required: `{str(payload['operator_action_required']).lower()}`",
        f"Next expected actor: `{payload['next_expected_actor']}`",
        "",
        "Mirror counts:",
        f"- canonical_expected={payload['canonical_expected']}",
        f"- observed={payload['observed']}",
        f"- missing_expected={payload['missing_expected']}",
        f"- extra={payload['extra']}",
        f"- hash_mismatch={payload['hash_mismatch']}",
        f"- matched_hash={payload['matched_hash']}",
        "",
        "App-visible stable map:",
        f"- map_status: `{map_status['map_status']}`",
        f"- map_generation_id: `{map_status['map_generation_id']}`",
        f"- bundle_hash: `{map_status['bundle_hash']}`",
        f"- app_visible: `{str(map_status['app_visible']).lower()}`",
        f"- receipt_matches_pc_bundle: `{str(map_status.get('receipt_matches_pc_bundle')).lower()}`",
        f"- agent_dossier_cards: `{map_status.get('agent_dossier_cards_count')}` at `{map_status.get('agent_dossier_cards_path')}`",
        f"- agent_dossier_cards_path_status: `{map_status.get('agent_dossier_cards_path_status')}`",
        f"- package_preview_summary: `{str(map_status.get('package_preview_summary_present')).lower()}` count=`{map_status.get('package_preview_example_count')}`",
        f"- tool_adapter_receipt_summary: `{str(map_status.get('tool_adapter_receipt_summary_present')).lower()}` count=`{map_status.get('tool_adapter_receipt_example_count')}`",
        f"- capital_hilton_summary: `{str(map_status.get('capital_hilton_summary_present')).lower()}` missing_proof=`{map_status.get('capital_hilton_missing_proof_count')}` protected_proof=`{str(map_status.get('capital_hilton_protected_proof_required')).lower()}`",
        f"- capital_hilton_protected_proof_intake: `{str(map_status.get('capital_hilton_protected_proof_intake_present')).lower()}` proof_items=`{map_status.get('proof_items_count')}` missing_proof=`{map_status.get('missing_proof_count')}` protected_proof=`{str(map_status.get('protected_proof_required')).lower()}` candidate_facts_proven=`{str(map_status.get('candidate_facts_proven')).lower()}`",
        f"- capital_hilton_authority_flags_false: `{str(map_status.get('capital_hilton_authority_flags_false')).lower()}`",
        f"- security_audit_readiness: `{str(map_status.get('security_audit_readiness_present')).lower()}` ready_for_pass=`{str(map_status.get('ready_for_security_pass')).lower()}` approval=`{str(map_status.get('security_approval_granted')).lower()}` action_authority=`{str(map_status.get('action_authority_granted')).lower()}`",
        f"- security_coverage_gaps: `{map_status.get('coverage_gap_records_count')}` parked_breadcrumbs=`{map_status.get('parked_breadcrumb_count')}`",
        f"- security_pass: `{str(map_status.get('security_pass_present')).lower()}` completed=`{str(map_status.get('security_pass_completed')).lower()}` read_only=`{str(map_status.get('read_only_surfaces_approved')).lower()}` preview=`{str(map_status.get('preview_surfaces_approved')).lower()}` action_authority=`{str(map_status.get('security_pass_action_authority_granted')).lower()}`",
        f"- security_pass_worker_orphan_chief_hermes: worker=`{str(map_status.get('worker_output_intake_summary_present')).lower()}` orphaned=`{str(map_status.get('orphaned_capability_summary_present')).lower()}` chief_hermes=`{str(map_status.get('chief_hermes_trust_summary_present')).lower()}`",
        f"- post_security_governance_batch: `{str(map_status.get('post_security_governance_batch_present')).lower()}` parked_capital=`{str(map_status.get('parked_capital_experiment_present')).lower()}` security_delta=`{str(map_status.get('security_delta_review_present')).lower()}` attention_promotion=`{str(map_status.get('operator_attention_promotion_present')).lower()}` chief_cross_off=`{str(map_status.get('chief_test_harness_cross_off_present')).lower()}`",
        f"- front-door operator action required: `{str(map_status['operator_action_required']).lower()}`",
        f"- next expected actor: `{map_status['next_expected_actor']}`",
        f"- next: {map_status['recommended_fix']}",
        "",
        "Raw read-model mirror detail:",
        f"- raw_mirror_status: `{raw_status['raw_mirror_status']}`",
        f"- raw_mirror_blocks_app_visible_map: `{str(raw_status['raw_mirror_blocks_app_visible_map']).lower()}`",
        "",
        "Check Transmission display:",
        f"- lamp_state: `{transmission['lamp_state']}`",
        f"- headline: {transmission['headline']}",
        f"- summary: {transmission['operator_summary']}",
        "",
        (
            "Raw read-model mirror proof/detail recommendation:"
            if map_status["map_status"] == "map_current"
            else "Recommended fix:"
        ),
        f"- kind: `{recommended['kind']}`",
        f"- display status: `{recommended['display_status']}`",
        f"- next expected actor: `{recommended['next_expected_actor']}`",
        f"- lifecycle state: `{recommended['sync_lifecycle_state']}`",
        f"- operator action required: `{str(recommended['operator_action_required']).lower()}`",
        f"- next: {recommended['next_safe_move']}",
        f"- app can request bounded Mac sync marker: `{str(recommended['can_request_fix_from_app']).lower()}`",
        "",
        "Proof:",
        f"- Mac heartbeat: `{payload['last_mac_heartbeat']['status']}` at `{payload['last_mac_heartbeat']['time']}`",
        f"- Mac completion: `{payload['last_mac_completion']['status']}` at `{payload['last_mac_completion']['time']}`",
        f"- PC import: `{payload['last_pc_import']['status']}` at `{payload['last_pc_import']['time']}`",
        f"- Windows task log present: `{str(payload['last_pc_import']['windows_task_log_present']).lower()}`",
    ]
    if payload["stale_files"]:
        lines.extend(["", "Stale files:"])
        lines.extend(f"- `{item}`" for item in payload["stale_files"])
    if payload["extra_files"]:
        lines.extend(["", "Extra files:"])
        lines.extend(f"- `{item}`" for item in payload["extra_files"])
    lines.extend(
        [
            "",
            "No-authority posture:",
        ]
    )
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(
        [
            "",
            "Boundary:",
            "- Sync Health is a read-model and ledger snapshot only.",
            "- It does not remote-control Mac or Windows, run arbitrary commands, modify Mission Control, or broaden sync authority.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def export_sync_health_read_model(
    *,
    db_path: str | Path | None = None,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    repo_root: str | Path = ROOT,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    map_receipt_path: str | Path = DEFAULT_MAP_RECEIPT_PATH,
    map_sync_request_path: str | Path = DEFAULT_MAP_SYNC_REQUEST_MARKER_PATH,
) -> dict[str, Any]:
    payload = build_sync_health_read_model(
        db_path=db_path,
        manifest_path=manifest_path,
        read_model_root=read_model_root,
        repo_root=repo_root,
        map_receipt_path=map_receipt_path,
        map_sync_request_path=map_sync_request_path,
    )
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(_operator_markdown(payload), encoding="utf-8")
    return {
        "json_path": _display_path(json_path, repo_root=repo_root),
        "operator_path": _display_path(operator_path, repo_root=repo_root),
        "trust_status": payload["trust_status"],
        "mirror_status": payload["mirror_status"],
        "display_status": payload["display_status"],
        "sync_lifecycle_state": payload["sync_lifecycle_state"],
        "operator_action_required": payload["operator_action_required"],
        "next_expected_actor": payload["next_expected_actor"],
        "recommended_fix_kind": payload["recommended_fix"]["kind"],
        "missing_expected": payload["missing_expected"],
        "extra": payload["extra"],
        "hash_mismatch": payload["hash_mismatch"],
        "map_status": payload["app_visible_map_status"]["map_status"],
        "check_transmission_lamp_state": payload["check_transmission_display"]["lamp_state"],
    }


def refresh_sync_health_from_manifest(
    *,
    db_path: str | Path | None = None,
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    read_model_root: str | Path = DEFAULT_READ_MODEL_ROOT,
    repo_root: str | Path = ROOT,
    mac_status_path: str | Path = DEFAULT_MAC_STATUS_PATH,
    mac_completion_path: str | Path = DEFAULT_MAC_COMPLETION_PATH,
    pc_import_state_path: str | Path = DEFAULT_PC_IMPORT_STATE_PATH,
    pc_task_log_path: str | Path = DEFAULT_PC_TASK_LOG_PATH,
    windows_task_log_path: str | Path = DEFAULT_WINDOWS_TASK_LOG_PATH,
    request_marker_path: str | Path = DEFAULT_REQUEST_MARKER_PATH,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    map_receipt_path: str | Path = DEFAULT_MAP_RECEIPT_PATH,
    map_sync_request_path: str | Path = DEFAULT_MAP_SYNC_REQUEST_MARKER_PATH,
) -> dict[str, Any]:
    """Record and export sync health from the latest mirror manifest.

    This is the durable PC-side bridge between a successful manifest import and
    the operator-facing read-model files Mission Control consumes. It reads
    metadata/proof files only and writes the sync_health read-model outputs.
    """

    build = build_sync_health_snapshot(
        db_path=db_path,
        manifest_path=manifest_path,
        read_model_root=read_model_root,
        repo_root=repo_root,
        mac_status_path=mac_status_path,
        mac_completion_path=mac_completion_path,
        pc_import_state_path=pc_import_state_path,
        pc_task_log_path=pc_task_log_path,
        windows_task_log_path=windows_task_log_path,
        request_marker_path=request_marker_path,
    )
    pre_export_split = build_sync_health_map_raw_split(
        manifest_path=manifest_path,
        read_model_root=read_model_root,
        repo_root=repo_root,
        map_receipt_path=map_receipt_path,
        map_sync_request_path=map_sync_request_path,
    )
    map_sync_request = write_openclaw_map_sync_required_marker_if_needed(
        app_visible_map_status=pre_export_split["app_visible_map_status"],
        read_model_root=read_model_root,
        marker_path=map_sync_request_path,
    )
    export = export_sync_health_read_model(
        db_path=db_path,
        export_root=export_root,
        repo_root=repo_root,
        manifest_path=manifest_path,
        read_model_root=read_model_root,
        map_receipt_path=map_receipt_path,
        map_sync_request_path=map_sync_request_path,
    )
    payload = build_sync_health_read_model(
        db_path=db_path,
        manifest_path=manifest_path,
        read_model_root=read_model_root,
        repo_root=repo_root,
        map_receipt_path=map_receipt_path,
        map_sync_request_path=map_sync_request_path,
    )
    return {
        "sync_health_refreshed": True,
        "run_id": build.run_id,
        "snapshot_id": build.snapshot_id,
        "json_path": export["json_path"],
        "operator_path": export["operator_path"],
        "trust_status": payload["trust_status"],
        "mirror_status": payload["mirror_status"],
        "display_status": payload["display_status"],
        "sync_lifecycle_state": payload["sync_lifecycle_state"],
        "operator_action_required": payload["operator_action_required"],
        "canonical_expected": payload["canonical_expected"],
        "observed": payload["observed"],
        "missing_expected": payload["missing_expected"],
        "extra": payload["extra"],
        "hash_mismatch": payload["hash_mismatch"],
        "matched_hash": payload["matched_hash"],
        "app_visible_map_status": payload["app_visible_map_status"],
        "raw_read_model_mirror_status": payload["raw_read_model_mirror_status"],
        "receipt_status": payload["receipt_status"],
        "check_transmission_display": payload["check_transmission_display"],
        "map_sync_request": map_sync_request,
        **NO_AUTHORITY_FLAGS,
    }


def format_sync_health_report(payload: dict[str, Any]) -> str:
    snapshot = payload.get("latest_snapshot")
    lines = ["OpenClaw Sync Health v0", ""]
    if not snapshot:
        lines.extend(["Status: `empty`", "No sync health snapshot has been built yet."])
    else:
        lines.extend(
            [
                f"Trust status: `{snapshot['trust_status']}`",
                f"Mirror status: `{snapshot['mirror_status']}`",
                f"Display status: `{snapshot['display_status']}`",
                f"Lifecycle state: `{snapshot['sync_lifecycle_state']}`",
                f"Operator action required: `{str(snapshot['operator_action_required']).lower()}`",
                f"Next expected actor: `{snapshot['next_expected_actor']}`",
                "",
                "Mirror counts:",
                f"- canonical_expected={snapshot['canonical_expected']}",
                f"- observed={snapshot['observed']}",
                f"- missing_expected={snapshot['missing_expected']}",
                f"- extra={snapshot['extra']}",
                f"- hash_mismatch={snapshot['hash_mismatch']}",
                f"- matched_hash={snapshot['matched_hash']}",
                "",
                f"Recommended fix: `{snapshot['recommended_fix_kind']}`",
                f"Next safe move: {snapshot['next_safe_move']}",
                f"App request changes repair path: `{str(snapshot['can_request_fix_from_app']).lower()}`",
            ]
        )
        if payload.get("report") == "proof":
            lines.extend(["", "Proof sources:"])
            for source in payload.get("sources", []):
                lines.append(
                    f"- {source['source_kind']}: present={bool(source['present'])} "
                    f"status={source['source_status']} time={source['source_time']}"
                )
    lines.extend(
        [
            "",
            "Boundary:",
            "- Read-model only; no arbitrary command, remote control, SSH/SCP/rsync, Docker/Ollama, runtime, agent, deletion, or move authority.",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "NO_AUTHORITY_FLAGS",
    "build_sync_health_read_model",
    "build_sync_health_map_raw_split",
    "build_sync_health_report",
    "build_sync_health_snapshot",
    "build_app_visible_map_status",
    "build_raw_read_model_mirror_status",
    "build_receipt_status",
    "build_check_transmission_display",
    "classify_sync_health",
    "compare_manifest_to_backend",
    "export_sync_health_read_model",
    "format_sync_health_report",
    "init_sync_health_schema",
    "refresh_sync_health_from_manifest",
    "sync_health_table_names",
    "write_openclaw_map_sync_required_marker_if_needed",
]

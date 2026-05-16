"""Guardian/HITL authority reconciliation read-model v0.

This module is metadata-only. It does not import live Guardian, Telegram,
Chief, HITL, or Repo B runtime modules, and it does not read approval state
files. The goal is to make current and legacy approval authority visible before
any memory import, remote-builder bridge, or external-action workflow expands.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
SCHEMA_VERSION = "guardian_hitl_authority_reconciliation_v0"
PROMPT_2_PACKET_VERSION = "guardian_hitl_authority_reconciliation_prompt_2_ready_packet_v0"
JSON_EXPORT_NAME = "guardian_hitl_authority_reconciliation.json"
OPERATOR_EXPORT_NAME = "guardian_hitl_authority_reconciliation_OPERATOR.md"
PROMPT_2_READY_PACKET_PATH = Path(
    "docs/operations/GUARDIAN_HITL_AUTHORITY_RECONCILIATION_PROMPT_2_READY_PACKET.json"
)

CLASSIFICATIONS = {
    "active_runtime_path",
    "active_special_case",
    "legacy_reference",
    "mixed_or_conflicting",
    "test_only",
    "docs_only",
    "unknown",
}

NO_AUTHORITY_FLAGS = {
    "runtime_authority_changed": False,
    "old_hitl_deleted": False,
    "repo_b_execution_allowed": False,
    "telegram_send_added": False,
    "gmail_send_added": False,
    "email_send_added": False,
    "agent_activation_added": False,
    "runtime_service_modified": False,
    "approval_bypass_allowed": False,
    "freeform_shell_approval_allowed": False,
    "raw_command_text_allowed": False,
    "raw_private_data_read": False,
    "safe_to_import_cassandra_chief_memory": False,
    "safe_to_enable_remote_builder": False,
    "safe_to_expand_send_paths": False,
}


@dataclass(frozen=True)
class AuthoritySurface:
    surface_id: str
    surface: str
    file_path: str
    caller_callee: str
    state_store: str
    approval_object: str
    ttl_idempotency: str
    current_classification: str
    risk: str
    next_action: str
    evidence: str
    authority_conflict: bool = False

    def __post_init__(self) -> None:
        if self.current_classification not in CLASSIFICATIONS:
            raise ValueError(f"invalid HITL classification: {self.current_classification}")


SURFACES: tuple[AuthoritySurface, ...] = (
    AuthoritySurface(
        surface_id="operator_action_path",
        surface="Operator Action Path",
        file_path="operator_action.py",
        caller_callee=(
            "scripts/request_operator_action.py -> request_operator_action -> "
            "approve_operator_action -> execute_operator_action"
        ),
        state_store="SQLite business_ops ledger: operator_action_* tables",
        approval_object="operator_action_requests plus operator_action_approvals and receipts",
        ttl_idempotency=(
            "No TTL in v0; action_id is unique, commands are allowlisted argv arrays, "
            "and execution requires explicit approval."
        ),
        current_classification="active_runtime_path",
        risk="Narrow and governed, but only covers a small allowlisted local action set.",
        next_action="Use as the preferred future target for bounded local action approval.",
        evidence="operator_action.py schema/functions and tests/test_operator_action.py",
    ),
    AuthoritySurface(
        surface_id="operator_action_inbox",
        surface="Operator Action Inbox",
        file_path="operator_action_inbox.py",
        caller_callee=(
            "strict request JSON file -> import_operator_action_request_file -> "
            "request_operator_action"
        ),
        state_store=(
            "SQLite operator_action_inbox_* tables plus operator_action_requests; "
            "request files live in shared inbox/archive/rejected roots."
        ),
        approval_object="operator_action_request_v0 JSON normalized into a pending Operator Action record",
        ttl_idempotency="No TTL in v0; request_id maps to deterministic action_id and cannot execute on import.",
        current_classification="active_runtime_path",
        risk="Safe as intake metadata, but not a general remote builder bridge.",
        next_action="Keep as import-only request intake; do not add execution or auto-approval.",
        evidence="operator_action_inbox.py and tests/test_operator_action_inbox.py",
    ),
    AuthoritySurface(
        surface_id="chief_approval_brain",
        surface="Chief tiered approval gate",
        file_path="chief_approval_brain.py",
        caller_callee=(
            "request_approval -> chief_approval_policy.classify -> "
            "chief_guardian_sender.send_approval -> record_decision"
        ),
        state_store="Windows-side approval_pending.json plus vault Approval Log.md",
        approval_object="approval id, action text, requester, status, decision, HMAC hash, optional context",
        ttl_idempotency="24 hour timeout; one pending slot; short id/code; HMAC binds action/id/timestamp when configured.",
        current_classification="active_runtime_path",
        risk=(
            "Current active authority uses old JSON/Markdown state and Telegram delivery; "
            "cannot be called obsolete or casually replaced yet."
        ),
        next_action="Reconcile into a receipt-backed SQLite contract before expanding action classes.",
        evidence="chief_approval_brain.py, chief_router.py, tests/test_chief_approval_brain.py",
        authority_conflict=True,
    ),
    AuthoritySurface(
        surface_id="chief_guardian_listener",
        surface="Guardian approval listener",
        file_path="chief_guardian_listener.py",
        caller_callee=(
            "Telegram callback/message -> approval id binding -> "
            "chief_approval_brain.record_decision; HITL callbacks route to hitl_notification_service"
        ),
        state_store="approval_pending.json and hitl_pending_state.json via delegated calls",
        approval_object="callback_data decision:approval_id or typed CODE DECISION; HITL signed token callbacks",
        ttl_idempotency="Uses active pending approval TTL/code binding or HITL token TTL.",
        current_classification="active_runtime_path",
        risk="External Telegram-facing approval intake; safe to map, not safe to expand in this lane.",
        next_action="Keep role-separated as approval-only; route future action receipts through a unified contract.",
        evidence="chief_guardian_listener.py imports record_telegram_listener_update_safe and decision handlers",
        authority_conflict=True,
    ),
    AuthoritySurface(
        surface_id="chief_guardian_sender",
        surface="Guardian approval sender",
        file_path="chief_guardian_sender.py",
        caller_callee="chief_approval_brain and hitl_notification_service -> send_approval",
        state_store="No local approval state; sends Telegram request through configured bot token and chat id",
        approval_object="Telegram message with optional inline approval keyboard",
        ttl_idempotency="No local TTL; TTL belongs to pending approval or HITL token.",
        current_classification="active_runtime_path",
        risk="External send-capable path; must not be broadened or used outside existing gates.",
        next_action="Retain fail-closed button behavior; no new send paths until contract consolidation.",
        evidence="chief_guardian_sender.py and tests/test_chief_approval_brain.py",
        authority_conflict=True,
    ),
    AuthoritySurface(
        surface_id="chief_router_approval_reply",
        surface="Chief router approval reply path",
        file_path="chief_router.py",
        caller_callee=(
            "route_message -> has_pending_approval/get_pending_info/parse_reply_code -> "
            "record_decision; /hitl_approve and /hitl_deny -> hitl_notification_service"
        ),
        state_store="approval_pending.json and HITL JSON store via delegated functions",
        approval_object="typed approval code decision or signed HITL command token",
        ttl_idempotency="Pending id/code binding for Chief approval; token TTL for HITL commands.",
        current_classification="active_runtime_path",
        risk="Fallback approval route is active and can overlap with Guardian listener semantics.",
        next_action="Document as current fallback; reconcile with Guardian listener before removing old JSON.",
        evidence="chief_router.py approval_response and hitl_decision paths",
        authority_conflict=True,
    ),
    AuthoritySurface(
        surface_id="chief_watcher_approval_replay",
        surface="Chief watcher approval replay",
        file_path="chief_watcher_brain.py",
        caller_callee="check_once -> chief_approval_brain.py --resend-pending",
        state_store="approval_pending.json plus chief_watcher_state.json replay counters",
        approval_object="Existing pending approval only; no new approval decision",
        ttl_idempotency="Replay after 120 seconds, 600 second cooldown, max 3 replays per approval id.",
        current_classification="active_special_case",
        risk="Uses subprocess to resend a current approval; does not decide, but is runtime side-effectful.",
        next_action="Keep bounded; future contract should model replay as notification receipt only.",
        evidence="chief_watcher_brain.py evaluate_pending_replay/check_once",
        authority_conflict=True,
    ),
    AuthoritySurface(
        surface_id="google_access_broker_approval_hook",
        surface="Google access broker approval hook",
        file_path="google_access_broker.py",
        caller_callee="_request_approval -> chief_approval_brain.request_approval for Class B/C capabilities",
        state_store="Delegates to approval_pending.json and broker audit JSONL",
        approval_object="Google broker action label plus optional approval context",
        ttl_idempotency="Uses Chief approval TTL; no separate idempotency in the broker hook.",
        current_classification="active_runtime_path",
        risk="External API action gating depends on the mixed Chief JSON approval path.",
        next_action="Do not expand Gmail/calendar send/write until approval authority is consolidated.",
        evidence="google_access_broker.py _request_approval and Class B/C gate calls",
        authority_conflict=True,
    ),
    AuthoritySurface(
        surface_id="hitl_pending_store",
        surface="Cassandra HITL pending store",
        file_path="hitl_pending_store.py",
        caller_callee="cassandra_brain._hitl_propose -> hitl_pending_store.propose_action",
        state_store="Windows-side hitl_pending_state.json and hitl_audit.jsonl",
        approval_object="pending action record with payload, status, review state, amount guard, approval fields",
        ttl_idempotency="Default 24 hour TTL; optional idempotency_key; auto-expire on reads.",
        current_classification="mixed_or_conflicting",
        risk=(
            "Current Repo A code path, but authority is JSON-backed and HITL-disabled default "
            "can return proceed for non-limit-gated actions."
        ),
        next_action="Quarantine as mixed authority until unified with Operator Action/Guardian contract.",
        evidence="hitl_pending_store.py and cassandra_brain.py import of propose_action",
        authority_conflict=True,
    ),
    AuthoritySurface(
        surface_id="hitl_action_service",
        surface="HITL action service wrapper",
        file_path="hitl_action_service.py",
        caller_callee="create_pending_action/approve_action/deny_action -> hitl_pending_store",
        state_store="Delegates to hitl_pending_state.json and hitl_audit.jsonl",
        approval_object="HITL action id with validation/idempotency; approve_action stamps approved_by",
        ttl_idempotency="Default 24 hour TTL; deterministic derived idempotency key if caller omits one.",
        current_classification="mixed_or_conflicting",
        risk="Approval hook is currently a no-op print, so it is not a proven safe executor boundary.",
        next_action="Treat as service candidate only; do not connect to execution until receipts are defined.",
        evidence="hitl_action_service.py public API and _on_action_approved",
        authority_conflict=True,
    ),
    AuthoritySurface(
        surface_id="hitl_notification_service",
        surface="HITL notification/token service",
        file_path="hitl_notification_service.py",
        caller_callee="send_pending_notification/process_callback -> hitl_action_service",
        state_store="hitl_pending_state.json, hitl_audit.jsonl, hitl_notifications.jsonl",
        approval_object="HMAC signed short-lived approve/deny token bound to action_id",
        ttl_idempotency="24 hour token TTL; HMAC over action_id:decision:expiry.",
        current_classification="mixed_or_conflicting",
        risk="Send-capable Guardian notification path over JSON-backed action authority.",
        next_action="Keep mapped but not expanded; move to unified approval receipt contract first.",
        evidence="hitl_notification_service.py",
        authority_conflict=True,
    ),
    AuthoritySurface(
        surface_id="chief_approval_bridge",
        surface="Chief workflow choice bridge",
        file_path="chief_approval_bridge.py",
        caller_callee="Chief workflow send_choice -> chief_notify; chief_listener/chief_router -> bridge_handle",
        state_store="Windows-side choice_pending.json",
        approval_object="choice prompt with options and answer; not execution approval",
        ttl_idempotency="30 minute choice timeout; no action-payload binding or execution receipt.",
        current_classification="mixed_or_conflicting",
        risk="Uses approval language for workflow choices and can be confused with action approval.",
        next_action="Keep separate from Guardian action approval; rename/reframe in later lane if needed.",
        evidence="chief_approval_bridge.py, chief_listener.py, chief_router.py",
        authority_conflict=True,
    ),
    AuthoritySurface(
        surface_id="hitl_pending_action_legacy",
        surface="Older HITL pending action store",
        file_path="hitl_pending_action.py",
        caller_callee="No current non-test Repo A caller found by static search",
        state_store="Windows-side hitl_pending_actions.json and hitl_audit.jsonl",
        approval_object="older pending action list record with status transition audit",
        ttl_idempotency="24 hour expiry; no idempotency key in this older path.",
        current_classification="legacy_reference",
        risk="Parallel old HITL store can confuse authority if committed as live truth.",
        next_action="Do not delete yet; reconcile and prove no runtime caller before deprecation.",
        evidence="Repo A static rg found file/docs/tests, but no current runtime importer outside references.",
        authority_conflict=True,
    ),
    AuthoritySurface(
        surface_id="agent_presence_cassandra_recovery",
        surface="Cassandra recovery clearance",
        file_path="agent_presence.py; scripts/request_cassandra_recovery_guardian_approval.py; scripts/recover_agent.py",
        caller_callee=(
            "request_agent_recovery_clearance -> request_approval/Guardian -> "
            "approve_agent_recovery_clearance -> recover_agent --execute"
        ),
        state_store="SQLite agent_recovery_* tables in the business_ops ledger",
        approval_object="agent_recovery_clearance scoped to cassandra_systemd_user_start",
        ttl_idempotency="30 minute clearance TTL, single-use max_attempts=1, fixed argv, receipt required.",
        current_classification="active_special_case",
        risk="Narrow and receipt-backed, but limited to Cassandra recovery only; not general action approval.",
        next_action="Keep as fixed-scope special case; do not generalize without unified contract.",
        evidence="agent_presence.py recovery clearance functions and tests/test_agent_presence.py",
    ),
    AuthoritySurface(
        surface_id="guardian_schema_harness",
        surface="Guardian schema harness",
        file_path="guardian_schema_harness.py",
        caller_callee="fixture replay patches chief_approval_brain.PENDING_FILE to staging path",
        state_store="staging/guardian_schema_harness only",
        approval_object="synthetic pending approval fixture",
        ttl_idempotency="Fixture-defined; asserts live approval_pending.json not touched.",
        current_classification="test_only",
        risk="Safe validation harness; must stay staging-only.",
        next_action="Keep as test evidence, not runtime authority.",
        evidence="guardian_schema_harness.py",
    ),
    AuthoritySurface(
        surface_id="hitl_flowchart_gen",
        surface="HITL flowchart generator",
        file_path="hitl_flowchart_gen.py",
        caller_callee="script imports policy metadata to render Mermaid docs",
        state_store="No approval state store",
        approval_object="diagram metadata only",
        ttl_idempotency="Not applicable.",
        current_classification="docs_only",
        risk="Can describe old architecture but does not prove current runtime authority.",
        next_action="Use as reference-only documentation input.",
        evidence="hitl_flowchart_gen.py",
    ),
    AuthoritySurface(
        surface_id="repo_b_approval_tree",
        surface="Repo B approval/HITL tree",
        file_path="/home/openclaw_external/openclaw-runtime/chief_approval*.py and chief_guardian*.py",
        caller_callee="Reference-only pre-split capability tree; not imported or executed",
        state_store="Repo B legacy JSON/Telegram/vault patterns by source reference only",
        approval_object="pre-split approval concepts",
        ttl_idempotency="Reference-only; not evaluated as current runtime.",
        current_classification="legacy_reference",
        risk="Useful design evidence but unsafe as runtime authority.",
        next_action="Keep Repo B reference-only; port concepts only after Repo A contract is defined.",
        evidence="read-only file inspection; repo_b_execution_allowed=false",
    ),
    AuthoritySurface(
        surface_id="live_service_usage",
        surface="Which approval paths are live in current services",
        file_path="systemd/user/*.service.in; runtime status/logs not inspected in this lane",
        caller_callee="Unknown without safe service/log validation",
        state_store="Unknown live process state",
        approval_object="Unknown",
        ttl_idempotency="Unknown",
        current_classification="unknown",
        risk="Static code proves possible paths, not which paths are active at this moment.",
        next_action="Future lane may inspect redacted service status only; do not infer live authority from docs.",
        evidence="No runtime activation or raw logs inspected by this lane.",
    ),
)

APPROVAL_STATE_FILES = (
    {
        "state_id": "approval_pending_json",
        "path": "/mnt/c/OpenClaw/logs/approval_pending.json",
        "used_by_current_repo_a": True,
        "classification": "authority_conflict_reconcile_first",
        "raw_content_read": False,
        "notes": "Current Chief approval gate reads/writes this JSON; not obsolete until replacement is proven.",
    },
    {
        "state_id": "approval_log_md",
        "path": "/mnt/c/OpenClawShared/openclaw-vault/System/Approval Log.md",
        "used_by_current_repo_a": True,
        "classification": "mixed_or_conflicting",
        "raw_content_read": False,
        "notes": "Chief approval log sink; Markdown is not a complete receipt-backed authority store.",
    },
    {
        "state_id": "hitl_pending_state_json",
        "path": "/mnt/c/OpenClaw/logs/hitl_pending_state.json",
        "used_by_current_repo_a": True,
        "classification": "authority_conflict_reconcile_first",
        "raw_content_read": False,
        "notes": "Current HITL pending store path.",
    },
    {
        "state_id": "hitl_pending_actions_json",
        "path": "/mnt/c/OpenClaw/logs/hitl_pending_actions.json",
        "used_by_current_repo_a": "unknown_runtime_use",
        "classification": "authority_conflict_reconcile_first",
        "raw_content_read": False,
        "notes": "Older parallel HITL store; prove no current runtime caller before deprecating.",
    },
    {
        "state_id": "hitl_audit_jsonl",
        "path": "/mnt/c/OpenClaw/logs/hitl_audit.jsonl",
        "used_by_current_repo_a": True,
        "classification": "authority_conflict_reconcile_first",
        "raw_content_read": False,
        "notes": "Shared HITL audit log for JSON-backed pending action stores.",
    },
    {
        "state_id": "hitl_notifications_jsonl",
        "path": "/mnt/c/OpenClaw/logs/hitl_notifications.jsonl",
        "used_by_current_repo_a": True,
        "classification": "mixed_or_conflicting",
        "raw_content_read": False,
        "notes": "HITL notification send/callback audit path.",
    },
    {
        "state_id": "choice_pending_json",
        "path": "/mnt/c/OpenClawShared/album/choice_pending.json",
        "used_by_current_repo_a": True,
        "classification": "mixed_or_conflicting",
        "raw_content_read": False,
        "notes": "Workflow choice state, not action approval authority.",
    },
    {
        "state_id": "operator_action_sqlite_tables",
        "path": "SQLite business_ops ledger: operator_action_*",
        "used_by_current_repo_a": True,
        "classification": "active_runtime_path",
        "raw_content_read": False,
        "notes": "Best current governed action record/approval/receipt path for allowlisted local actions.",
    },
    {
        "state_id": "agent_recovery_sqlite_tables",
        "path": "SQLite business_ops ledger: agent_recovery_*",
        "used_by_current_repo_a": True,
        "classification": "active_special_case",
        "raw_content_read": False,
        "notes": "Fixed-scope Cassandra recovery clearance and receipt path.",
    },
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _export_root_path(export_root: str | Path) -> Path:
    path = Path(export_root)
    if path.is_absolute():
        return path
    return ROOT / path


def _surface_dict(surface: AuthoritySurface) -> dict[str, Any]:
    return asdict(surface)


def _surface_summary(surface: AuthoritySurface) -> dict[str, Any]:
    return {
        "surface_id": surface.surface_id,
        "surface": surface.surface,
        "file_path": surface.file_path,
        "state_store": surface.state_store,
        "current_classification": surface.current_classification,
        "risk": surface.risk,
        "next_action": surface.next_action,
        "authority_conflict": surface.authority_conflict,
    }


def _surfaces_by_classification(classification: str) -> list[dict[str, Any]]:
    return [
        _surface_summary(surface)
        for surface in SURFACES
        if surface.current_classification == classification
    ]


def _mixed_surfaces() -> list[dict[str, Any]]:
    return [
        _surface_summary(surface)
        for surface in SURFACES
        if surface.current_classification == "mixed_or_conflicting" or surface.authority_conflict
    ]


def _approval_flow_summaries() -> list[dict[str, Any]]:
    return [
        {
            "flow_id": "operator_action_path",
            "summary": "SQLite request -> explicit approval -> allowlisted execution -> receipt.",
            "current_status": "usable_for_narrow_local_allowlisted_actions",
            "authority_gap": "Does not yet replace Chief/Guardian JSON approval or Cassandra HITL queues.",
        },
        {
            "flow_id": "chief_guardian_tiered_approval",
            "summary": "Action text -> policy tier -> approval_pending.json -> Guardian send/listener or Chief code fallback -> decision.",
            "current_status": "active_runtime_path",
            "authority_gap": "Active but old JSON/Markdown-backed; needs SQLite receipt-backed replacement before expansion.",
        },
        {
            "flow_id": "cassandra_hitl_pending_action",
            "summary": "Cassandra proposes action -> HITL JSON store -> optional Guardian notification/token -> approve/deny state.",
            "current_status": "mixed_or_conflicting",
            "authority_gap": "JSON-backed and not unified with Operator Action receipts; HITL disabled default can allow non-limit actions.",
        },
        {
            "flow_id": "cassandra_recovery_clearance",
            "summary": "Request fixed Cassandra recovery clearance -> Guardian approval -> SQLite clearance -> separate recover_agent execute -> receipt.",
            "current_status": "active_special_case",
            "authority_gap": "Narrow fixed-scope recovery only; not a general action approval contract.",
        },
        {
            "flow_id": "chief_workflow_choice_bridge",
            "summary": "Chief sends a numbered workflow choice prompt -> choice_pending.json -> router/listener records answer.",
            "current_status": "mixed_or_conflicting",
            "authority_gap": "Choice prompt is not an action approval or execution receipt.",
        },
        {
            "flow_id": "google_broker_protected_actions",
            "summary": "Google broker Class B/C capability -> chief_approval_brain.request_approval -> external API action if approved.",
            "current_status": "active_runtime_path_depends_on_mixed_chief_json",
            "authority_gap": "External action approval depends on the same old JSON-backed Chief gate.",
        },
    ]


def _cassandra_recovery_trace() -> dict[str, Any]:
    return {
        "classification": "active_special_case",
        "fixed_scope": True,
        "agent_id": "cassandra",
        "recovery_action_id": "cassandra_systemd_user_start",
        "request": {
            "surface": "scripts/request_agent_recovery_clearance.py",
            "state_written": "SQLite agent_recovery_clearances status=requested",
            "execution_occurs": False,
            "status": "proven_by_code_and_tests",
        },
        "guardian_approval": {
            "surface": "scripts/request_cassandra_recovery_guardian_approval.py",
            "approval_gate": "chief_approval_brain.request_approval explicit_tier=2",
            "approval_record": "business_ops_ledger.record_approval_request_record",
            "if_approved": "approve_agent_recovery_clearance marks exact clearance approved",
            "if_denied": "reject_agent_recovery_clearance marks no recovery authority granted",
            "execution_occurs": False,
            "status": "proven_by_code_and_tests",
        },
        "clearance_record": {
            "surface": "agent_presence.py",
            "scope": "exact Cassandra fixed systemd user start action only",
            "ttl_minutes": 30,
            "max_attempts": 1,
            "raw_command_text_allowed": False,
            "status": "proven_by_code_and_tests",
        },
        "execution_attempt": {
            "surface": "scripts/recover_agent.py --execute -> agent_presence.recover_agent",
            "argv_binding": "fixed command_argv from seeded recovery action, not caller-supplied shell",
            "receipt_required": True,
            "live_execution_observed_in_this_lane": False,
            "status": "static_code_trace_only",
        },
        "receipt_read_model": {
            "surfaces": "agent_recovery_attempts, agent_recovery_receipts, agent_presence read-model",
            "current_caveat": "agent_presence generated read-model snapshots are dirty residue and were not committed by this lane.",
            "status": "receipt_path_proven_by_tests; current live state not re-proven here",
        },
        "missing_without_raw_logs_or_runtime": [
            "whether a live Cassandra recovery was actually attempted recently",
            "whether systemd service status changed after a recovery attempt",
            "whether dirty generated agent_presence snapshots reflect current runtime truth",
        ],
    }


def _future_approval_contract() -> dict[str, Any]:
    return {
        "contract_id": "guardian_hitl_future_approval_contract_v0",
        "immutable_payload_required": True,
        "idempotency_key_required": True,
        "ttl_required": True,
        "operator_or_guardian_approval_required": True,
        "exact_action_binding_required": True,
        "receipt_required": True,
        "state_store_target": "SQLite/Operator Action or successor Guardian approval tables",
        "raw_command_text_allowed": False,
        "freeform_shell_approval_allowed": False,
        "approval_of_unparsed_text_allowed": False,
        "approval_bypass_allowed": False,
        "send_deploy_runtime_action_requires_explicit_authorized_packet": True,
        "must_bind": [
            "action_type",
            "actor",
            "target",
            "payload_hash",
            "source_intent_ref",
            "approval_id",
            "idempotency_key",
            "expires_at",
        ],
        "must_record": [
            "request receipt",
            "approval or denial receipt",
            "execution attempt receipt if execution is separately allowed",
            "result/failure receipt",
        ],
        "forbidden": [
            "raw shell strings",
            "freeform command approvals",
            "approval that changes action after approval",
            "send/deploy/runtime action without explicit authorized packet",
            "old HITL JSON as standalone current authority",
        ],
    }


def build_guardian_hitl_authority_reconciliation(
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Return the deterministic Guardian/HITL reconciliation read-model."""
    records = [_surface_dict(surface) for surface in SURFACES]
    decision_table = [
        {
            "surface": surface.surface,
            "file_path": surface.file_path,
            "caller_callee": surface.caller_callee,
            "state_store": surface.state_store,
            "approval_object": surface.approval_object,
            "ttl_idempotency": surface.ttl_idempotency,
            "current_classification": surface.current_classification,
            "risk": surface.risk,
            "next_action": surface.next_action,
        }
        for surface in SURFACES
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or utc_now(),
        "runtime_authority_changed": False,
        "old_hitl_deleted": False,
        "old_hitl_classification": "authority_conflict_reconcile_first",
        "old_hitl_obsolete": False,
        "repo_b_execution_allowed": False,
        "active_authority_surfaces": _surfaces_by_classification("active_runtime_path")
        + _surfaces_by_classification("active_special_case"),
        "mixed_authority_surfaces": _mixed_surfaces(),
        "legacy_reference_surfaces": _surfaces_by_classification("legacy_reference"),
        "test_only_surfaces": _surfaces_by_classification("test_only"),
        "docs_only_surfaces": _surfaces_by_classification("docs_only"),
        "blocked_surfaces": [],
        "unknown_surfaces": _surfaces_by_classification("unknown"),
        "approval_state_files": list(APPROVAL_STATE_FILES),
        "approval_flow_summaries": _approval_flow_summaries(),
        "authority_decision_table": decision_table,
        "cassandra_recovery_trace": _cassandra_recovery_trace(),
        "future_approval_contract": _future_approval_contract(),
        "boundaries": {
            **NO_AUTHORITY_FLAGS,
            "old_hitl_json_jsonl_may_not_be_labeled_obsolete": True,
            "old_hitl_json_jsonl_delete_allowed": False,
            "old_hitl_json_jsonl_migration_allowed": False,
            "old_hitl_json_jsonl_active_authority_expansion_allowed": False,
            "raw_state_file_contents_read": False,
            "static_reference_map_only": True,
        },
        "all_surfaces": records,
        "next_safe_move": "Define a Guardian HITL SQLite authority contract and migration plan before memory import, remote builder, or send-path expansion.",
    }


def format_guardian_hitl_authority_reconciliation(payload: dict[str, Any]) -> str:
    """Render a concise operator-facing Markdown read-model."""
    lines = [
        "# Guardian/HITL Authority Reconciliation v0",
        "",
        "## Bottom Line",
        "",
        "OpenClaw currently has more than one approval shape in play. The safest governed local path is the SQLite Operator Action Path, but Chief/Guardian approvals still actively use old JSON state, and Cassandra HITL has a separate JSON-backed queue. Old HITL JSON cannot be deleted or labeled obsolete yet.",
        "",
        "## What Is Safe Now",
        "",
        "- Use Operator Action only for its existing allowlisted local actions.",
        "- Treat Cassandra recovery clearance as a fixed-scope special case only.",
        "- Keep Guardian/Chief approval paths running as-is; this lane changed no runtime authority.",
        "",
        "## Mixed Or Unclear",
        "",
    ]
    for surface in payload["mixed_authority_surfaces"][:8]:
        lines.append(
            f"- `{surface['surface_id']}`: {surface['surface']} - {surface['next_action']}"
        )
    lines.extend(
        [
        "",
        "## Why Old HITL Cannot Be Blocked Yet",
        "",
        "Old HITL cannot be deleted or labeled obsolete yet.",
        "",
        "`approval_pending.json`, `hitl_pending_state.json`, `hitl_audit.jsonl`, and related files are still referenced by current Repo A code paths. They are not clean authority, but they are also not proven obsolete.",
            "",
            "## Cassandra Recovery Trace",
            "",
            "- Request creates a SQLite clearance record; no recovery command runs.",
            "- Guardian approval can approve or reject that exact clearance; still no recovery command runs.",
            "- `recover_agent.py --execute` is a separate step and may use only the fixed Cassandra systemd start action.",
            "- Receipts are recorded through `agent_recovery_*` tables when execution is attempted.",
            "",
            "## Must Wait",
            "",
            "- Cassandra/Chief memory import is not safe yet.",
            "- Remote-builder bridge is not safe yet.",
            "- New send paths are not safe yet.",
            "- Old HITL JSON/JSONL must not be deleted or migrated as truth.",
            "",
            "## Next Safe Move",
            "",
            payload["next_safe_move"],
            "",
        ]
    )
    return "\n".join(lines)


def build_guardian_hitl_prompt_2_ready_packet() -> dict[str, Any]:
    return {
        "schema_version": PROMPT_2_PACKET_VERSION,
        "prompt_2_ready": True,
        "reason": (
            "Static Repo A evidence maps current, mixed, legacy, test, docs, and unknown approval "
            "surfaces without raw state, secrets, runtime changes, sends, or Repo B execution. "
            "The next lane should define the SQLite Guardian authority contract before touching memory import or bridges."
        ),
        "recommended_lane": "Guardian HITL SQLite Authority Contract v0",
        "old_hitl_classification": "authority_conflict_reconcile_first",
        "runtime_authority_changed": False,
        "old_hitl_deleted": False,
        "safe_to_import_cassandra_chief_memory": False,
        "safe_to_enable_remote_builder": False,
        "safe_to_expand_send_paths": False,
        "exact_files_to_inspect_next": [
            "operator_action.py",
            "operator_action_inbox.py",
            "chief_approval_brain.py",
            "chief_guardian_listener.py",
            "chief_guardian_sender.py",
            "chief_router.py",
            "hitl_pending_store.py",
            "hitl_action_service.py",
            "hitl_notification_service.py",
            "agent_presence.py",
            "business_ops_ledger.py",
            "docs/operations/GUARDIAN_HITL_AUTHORITY_RECONCILIATION_V0.md",
        ],
        "exact_files_to_create_or_update_next": [
            "docs/operations/GUARDIAN_HITL_SQLITE_AUTHORITY_CONTRACT_V0.md",
            "docs/operations/GUARDIAN_HITL_SQLITE_AUTHORITY_CONTRACT_READY_PACKET.json",
            "tests/test_guardian_hitl_authority_contract.py",
        ],
        "validation_commands": [
            "PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_guardian_hitl_authority_reconciliation.py tests/test_operator_action.py tests/test_operator_action_inbox.py tests/test_chief_approval_brain.py tests/test_agent_presence.py -q",
            "python3 -m json.tool generated/read_models/guardian_hitl_authority_reconciliation.json >/dev/null",
            "python3 -m json.tool docs/operations/GUARDIAN_HITL_AUTHORITY_RECONCILIATION_PROMPT_2_READY_PACKET.json >/dev/null",
            "git diff --check",
            "git diff --cached --check",
            "git status -sb --untracked-files=all",
        ],
        "stop_conditions": [
            "raw approval_pending.json, hitl_pending_state.json, hitl_audit.jsonl, Telegram logs, env files, secrets, or private data would need to be read",
            "runtime services would need to be modified, restarted, enabled, or disabled",
            "Repo B code would need to be imported or executed",
            "the lane would delete, migrate, or mutate old HITL state",
            "the lane would add Telegram/Gmail/email send paths",
            "the lane would enable remote builder or arbitrary shell approval",
            "the lane would treat old HITL JSON/JSONL as proof of current approval truth",
        ],
        "must_not_do": [
            "do not disable existing HITL paths",
            "do not delete old HITL JSON/JSONL",
            "do not migrate approval state",
            "do not modify runtime services",
            "do not run Repo B code",
            "do not send Telegram/Gmail/email",
            "do not inspect secrets, env files, raw logs, or private data",
            "do not commit dirty agent_presence generated files",
            "do not approve freeform shell or raw command text",
        ],
    }


def export_guardian_hitl_authority_reconciliation(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    root = _export_root_path(export_root)
    root.mkdir(parents=True, exist_ok=True)
    payload = build_guardian_hitl_authority_reconciliation(generated_at=generated_at)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(
        format_guardian_hitl_authority_reconciliation(payload),
        encoding="utf-8",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "json_path": str(json_path),
        "operator_path": str(operator_path),
        "surface_count": len(payload["all_surfaces"]),
        "mixed_surface_count": len(payload["mixed_authority_surfaces"]),
        "old_hitl_classification": payload["old_hitl_classification"],
        "runtime_authority_changed": payload["runtime_authority_changed"],
        "old_hitl_deleted": payload["old_hitl_deleted"],
        "safe_to_import_cassandra_chief_memory": payload["boundaries"][
            "safe_to_import_cassandra_chief_memory"
        ],
    }


__all__ = [
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "PROMPT_2_READY_PACKET_PATH",
    "SCHEMA_VERSION",
    "build_guardian_hitl_authority_reconciliation",
    "build_guardian_hitl_prompt_2_ready_packet",
    "export_guardian_hitl_authority_reconciliation",
    "format_guardian_hitl_authority_reconciliation",
    "stable_json",
]

"""Guardian/HITL surface disposition audit v0.

This module is a metadata-only disposition table for current approval/HITL
surfaces. It does not wire adapters, read old HITL JSON contents, import Repo B
code, send messages, mutate runtime services, or grant authority.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
SCHEMA_VERSION = "guardian_hitl_surface_disposition_v0"
READY_PACKET_VERSION = "guardian_hitl_surface_disposition_ready_packet_v0"
JSON_EXPORT_NAME = "guardian_hitl_surface_disposition.json"
OPERATOR_EXPORT_NAME = "guardian_hitl_surface_disposition_OPERATOR.md"

DISPOSITIONS = {
    "keep_canonical",
    "keep_compatibility_shim",
    "replace_with_sqlite_operator_action",
    "retire_after_migration",
    "block_no_go",
    "unknown_operator_decision",
}

NO_AUTHORITY_FLAGS = {
    "runtime_authority_changed": False,
    "old_hitl_deleted": False,
    "repo_b_execution_allowed": False,
    "telegram_send_added": False,
    "gmail_send_added": False,
    "email_send_added": False,
    "runtime_service_modified": False,
    "agent_activation_added": False,
    "approval_bypass_allowed": False,
    "safe_to_import_cassandra_chief_memory": False,
    "safe_to_enable_remote_builder": False,
}


@dataclass(frozen=True)
class DispositionSurface:
    surface_id: str
    surface: str
    file_path: str
    current_role: str
    current_state_store: str
    approval_object_shape: str
    actively_referenced: str
    safe: str
    depends_on: str
    disposition: str
    reason: str
    risk_if_kept: str
    risk_if_removed: str
    recommended_next_action: str

    def __post_init__(self) -> None:
        if self.disposition not in DISPOSITIONS:
            raise ValueError(f"invalid HITL surface disposition: {self.disposition}")


SURFACES: tuple[DispositionSurface, ...] = (
    DispositionSurface(
        surface_id="operator_action_path",
        surface="Operator Action path",
        file_path="operator_action.py",
        current_role="SQLite-backed request, approval, allowlisted local execution, and receipt path.",
        current_state_store="SQLite business_ops ledger: operator_action_* tables",
        approval_object_shape="action_id, action_type, requested_by, approval row, allowlisted argv, execution receipt",
        actively_referenced="yes: scripts/tests and Operator Action read-model tooling",
        safe="safe for existing narrow allowlisted local actions only",
        depends_on="business_ops_ledger.py and existing allowlisted command definitions",
        disposition="keep_canonical",
        reason="It is the cleanest current SQLite-backed approval/receipt model.",
        risk_if_kept="Low if scope remains narrow; medium if mistaken for general remote or send authority.",
        risk_if_removed="Would remove the strongest current canonical action spine.",
        recommended_next_action="Keep as canonical foundation; reuse concepts in Guardian/HITL contract adapters.",
    ),
    DispositionSurface(
        surface_id="operator_action_inbox",
        surface="Operator Action Inbox",
        file_path="operator_action_inbox.py",
        current_role="Strict JSON request intake into Operator Action; never approves or executes.",
        current_state_store="SQLite operator_action_inbox_* tables plus operator_action_requests",
        approval_object_shape="operator_action_request_v0 normalized into pending Operator Action request",
        actively_referenced="yes: scripts/tests and shared-drop request intake docs",
        safe="safe as import-only intake metadata",
        depends_on="operator_action.py allowlist and source validation",
        disposition="keep_canonical",
        reason="It preserves the right separation between request intake and approval/execution.",
        risk_if_kept="Low if it remains import-only; high if later treated as auto-execution.",
        risk_if_removed="Would lose a governed intake pattern for future bounded request packets.",
        recommended_next_action="Keep canonical for request intake; do not broaden into remote builder.",
    ),
    DispositionSurface(
        surface_id="guardian_sqlite_contract",
        surface="Guardian HITL SQLite authority contract",
        file_path="guardian_hitl_sqlite_authority_contract.py; docs/operations/GUARDIAN_HITL_SQLITE_AUTHORITY_CONTRACT_V0.md",
        current_role="Defined contract/read-model for future canonical Guardian/HITL approval object.",
        current_state_store="Generated read-models only; no runtime DB migration applied",
        approval_object_shape="immutable payload hash, idempotency key, TTL, exact action binding, decision and receipt fields",
        actively_referenced="yes: tests/read-models; not runtime-wired",
        safe="safe as specification/read-model only",
        depends_on="Operator Action concepts and reconciliation evidence",
        disposition="keep_canonical",
        reason="It defines the target authority shape without changing live runtime behavior.",
        risk_if_kept="Low; risk is only if readers mistake contract definition for live wiring.",
        risk_if_removed="Would remove the agreed target for adapter planning.",
        recommended_next_action="Keep canonical contract; require adapter planning before wiring.",
    ),
    DispositionSurface(
        surface_id="cassandra_recovery_clearance",
        surface="Cassandra recovery clearance path",
        file_path="agent_presence.py; scripts/request_cassandra_recovery_guardian_approval.py; scripts/recover_agent.py",
        current_role="Fixed-scope SQLite clearance for one Cassandra systemd user start action.",
        current_state_store="SQLite agent_recovery_* tables",
        approval_object_shape="clearance_id scoped to cassandra_systemd_user_start, TTL, max_attempts=1, receipt",
        actively_referenced="yes: agent presence/recovery scripts and tests",
        safe="safe only as fixed-scope recovery special case",
        depends_on="agent_presence.py policy and fixed seeded recovery action",
        disposition="keep_canonical",
        reason="It is already SQLite/receipt-backed and deliberately not general approval authority.",
        risk_if_kept="Medium if generalized beyond Cassandra recovery.",
        risk_if_removed="Would lose the current governed recovery clearance path.",
        recommended_next_action="Keep fixed-scope; explicitly exclude from general HITL adapter semantics.",
    ),
    DispositionSurface(
        surface_id="chief_approval_brain",
        surface="Chief tiered approval gate",
        file_path="chief_approval_brain.py",
        current_role="Active Tier 0/1/2 approval gate and blocking Guardian approval poll.",
        current_state_store="/mnt/c/OpenClaw/logs/approval_pending.json plus vault Approval Log.md",
        approval_object_shape="action text, approval id, requester, requested_at, status, decision, optional HMAC/context",
        actively_referenced="yes: Chief, Guardian listener/router, Google broker, Cassandra recovery approval flow",
        safe="necessary current compatibility path, not canonical long-term authority",
        depends_on="chief_approval_policy.py, chief_guardian_sender.py, approval_pending.json",
        disposition="keep_compatibility_shim",
        reason="Current callers still depend on it, but the old JSON authority shape should be replaced by SQLite contract adapters.",
        risk_if_kept="JSON authority drift, single pending slot limits, action text rather than immutable payload contract.",
        risk_if_removed="Would break current Guardian approval and protected external-action gates.",
        recommended_next_action="Keep as compatibility shim while planning SQLite request/decision mirror.",
    ),
    DispositionSurface(
        surface_id="chief_approval_policy",
        surface="Chief approval policy classifier",
        file_path="chief_approval_policy.py",
        current_role="Classifies actions into approval tiers and hard Tier 2 rules.",
        current_state_store="Code constants/rules, no approval state store",
        approval_object_shape="policy result, not approval record",
        actively_referenced="yes: chief_approval_brain.py",
        safe="useful as policy logic, not authority store",
        depends_on="Chief approval gate callers",
        disposition="keep_compatibility_shim",
        reason="Policy logic may be reused, but authority must move to SQLite approval objects.",
        risk_if_kept="Medium if string classifier becomes the only guard for new action classes.",
        risk_if_removed="Would weaken current approval tiering before replacement exists.",
        recommended_next_action="Keep policy logic; future adapter should bind policy result into contract fields.",
    ),
    DispositionSurface(
        surface_id="chief_guardian_listener",
        surface="Guardian approval listener",
        file_path="chief_guardian_listener.py",
        current_role="Telegram approval intake for button taps, typed codes, and HITL tokens.",
        current_state_store="Delegates to approval_pending.json and HITL JSON state",
        approval_object_shape="callback decision/id binding or signed HITL token",
        actively_referenced="yes: current Guardian listener service surface",
        safe="safe only as current transport role; not canonical authority",
        depends_on="Telegram bot configuration, chief_approval_brain.py, hitl_notification_service.py",
        disposition="keep_compatibility_shim",
        reason="Guardian transport should survive, but SQLite must own authority and receipts.",
        risk_if_kept="External listener can keep old JSON authority alive indefinitely.",
        risk_if_removed="Would remove current phone/Telegram approval response path.",
        recommended_next_action="Keep as approval-only transport shim; future adapter reads/writes SQLite contract.",
    ),
    DispositionSurface(
        surface_id="chief_guardian_sender",
        surface="Guardian approval sender",
        file_path="chief_guardian_sender.py",
        current_role="Sends approval requests through Guardian bot, with fail-closed button behavior.",
        current_state_store="No local state; external Telegram send transport",
        approval_object_shape="Telegram message with optional inline keyboard",
        actively_referenced="yes: Chief approval and HITL notification paths",
        safe="safe only inside existing gates; do not broaden",
        depends_on="Telegram environment configuration and requests.post",
        disposition="keep_compatibility_shim",
        reason="Transport is useful, but not the authority store.",
        risk_if_kept="Send-capable transport can be misused if adapter boundaries are loose.",
        risk_if_removed="Would break current Guardian approval delivery before replacement exists.",
        recommended_next_action="Keep transport shim; future contract records notification receipts separately.",
    ),
    DispositionSurface(
        surface_id="chief_router_approval_reply",
        surface="Chief router approval reply path",
        file_path="chief_router.py",
        current_role="Typed approval code fallback and HITL command routing.",
        current_state_store="Delegates to approval_pending.json and HITL JSON state",
        approval_object_shape="approval code decision or signed HITL command token",
        actively_referenced="yes: Chief message routing",
        safe="compatibility fallback only",
        depends_on="chief_approval_brain.py and hitl_notification_service.py",
        disposition="keep_compatibility_shim",
        reason="It protects stale approval replies today but should not remain a separate authority path long-term.",
        risk_if_kept="Overlapping listener/router semantics can diverge.",
        risk_if_removed="Would remove fallback approval UX and may break current Chief route handling.",
        recommended_next_action="Keep until Guardian listener and SQLite contract cover the same cases.",
    ),
    DispositionSurface(
        surface_id="chief_watcher_approval_replay",
        surface="Chief watcher approval replay",
        file_path="chief_watcher_brain.py",
        current_role="Re-sends a currently pending approval on bounded cooldown.",
        current_state_store="approval_pending.json plus chief_watcher_state.json",
        approval_object_shape="existing pending approval id only; no decision object",
        actively_referenced="yes: watcher code path, live service status not proven here",
        safe="compatibility notification side effect only",
        depends_on="chief_approval_brain.py --resend-pending",
        disposition="keep_compatibility_shim",
        reason="It does not decide approvals, but it is coupled to legacy JSON pending state.",
        risk_if_kept="Can perpetuate old approval_pending.json as runtime center.",
        risk_if_removed="May reduce operator visibility for stuck current approvals.",
        recommended_next_action="Model future replay as notification receipt, not approval authority.",
    ),
    DispositionSurface(
        surface_id="approval_pending_json",
        surface="Chief pending approval JSON state",
        file_path="/mnt/c/OpenClaw/logs/approval_pending.json",
        current_role="Active Chief/Guardian pending approval state.",
        current_state_store="Windows-side JSON file",
        approval_object_shape="single pending approval dict with id/action/requester/status/decision/hash/context",
        actively_referenced="yes: current Repo A code reads/writes it",
        safe="not safe as canonical long-term authority; must not delete yet",
        depends_on="chief_approval_brain.py, chief_router.py, chief_guardian_listener.py, chief_watcher_brain.py",
        disposition="keep_compatibility_shim",
        reason="Current active path still depends on it, but it should become compatibility-only during SQLite transition.",
        risk_if_kept="Stale or mutable JSON remains active authority.",
        risk_if_removed="Would break current approvals and may lose active pending state.",
        recommended_next_action="Catalog as legacy authority ref; mirror to SQLite only in a later adapter lane.",
    ),
    DispositionSurface(
        surface_id="hitl_pending_store",
        surface="Cassandra HITL pending store",
        file_path="hitl_pending_store.py",
        current_role="JSON-backed pending action store and transaction guard for Cassandra proposals.",
        current_state_store="/mnt/c/OpenClaw/logs/hitl_pending_state.json and hitl_audit.jsonl",
        approval_object_shape="action_id, source_agent, action_type, payload, status, review metadata, TTL",
        actively_referenced="yes: cassandra_brain imports propose_action",
        safe="not safe as canonical authority",
        depends_on="HITL_ENABLED/env or flag file, Windows JSON state, Cassandra brain",
        disposition="replace_with_sqlite_operator_action",
        reason="The action proposal concept is useful, but authority must be moved to SQLite contract records.",
        risk_if_kept="HITL-disabled default can return proceed for non-limit actions; JSON state can drift.",
        risk_if_removed="Would break current Cassandra HITL proposal compatibility before replacement.",
        recommended_next_action="Plan adapter that writes canonical SQLite request/decision/receipt records before retiring JSON.",
    ),
    DispositionSurface(
        surface_id="hitl_action_service",
        surface="HITL action service wrapper",
        file_path="hitl_action_service.py",
        current_role="Validation/idempotency wrapper over HITL pending store.",
        current_state_store="Delegates to hitl_pending_store.py JSON/JSONL",
        approval_object_shape="HITL action id, action type, payload, idempotency key, approved_by",
        actively_referenced="yes: HITL notification service and tests; broader runtime use mixed",
        safe="not safe as executor boundary",
        depends_on="hitl_pending_store.py",
        disposition="replace_with_sqlite_operator_action",
        reason="Validation/idempotency logic is useful, but the store and approval decision must move to SQLite.",
        risk_if_kept="Approval hook prints and can be mistaken for a real execution handoff.",
        risk_if_removed="Would remove current service wrapper before the SQLite adapter exists.",
        recommended_next_action="Retain API shape as adapter candidate; replace backing store with contract in future lane.",
    ),
    DispositionSurface(
        surface_id="hitl_notification_service",
        surface="HITL notification/token service",
        file_path="hitl_notification_service.py",
        current_role="Formats and sends HITL approval notifications and validates signed callbacks.",
        current_state_store="hitl_pending_state.json, hitl_audit.jsonl, hitl_notifications.jsonl",
        approval_object_shape="HMAC token bound to action_id, decision, and expiry",
        actively_referenced="yes: Guardian listener/router HITL command paths",
        safe="transport compatibility only; not canonical authority",
        depends_on="hitl_action_service.py, chief_guardian_sender.py, token secret/env fallback",
        disposition="keep_compatibility_shim",
        reason="Token/notification concept can survive as transport, but SQLite must own decisions and receipts.",
        risk_if_kept="Send-capable JSON-backed action authority persists.",
        risk_if_removed="Would break current HITL callback/notification compatibility.",
        recommended_next_action="Keep as shim until it records notification and decision receipts in SQLite.",
    ),
    DispositionSurface(
        surface_id="hitl_pending_state_json",
        surface="Cassandra HITL pending JSON state",
        file_path="/mnt/c/OpenClaw/logs/hitl_pending_state.json",
        current_role="Current JSON store for HITL pending actions.",
        current_state_store="Windows-side JSON file",
        approval_object_shape="map of action_id to pending action record",
        actively_referenced="yes: hitl_pending_store.py",
        safe="not safe as canonical authority; must not delete yet",
        depends_on="hitl_pending_store.py and hitl_action_service.py",
        disposition="keep_compatibility_shim",
        reason="It is active transition state, but future authority must move to SQLite.",
        risk_if_kept="Old pending action state can be mistaken for canonical truth.",
        risk_if_removed="Would break current HITL queue compatibility and may lose pending context.",
        recommended_next_action="Keep untouched; later adapter should supersede with SQLite and prove no active use before retirement.",
    ),
    DispositionSurface(
        surface_id="hitl_audit_jsonl",
        surface="HITL audit JSONL",
        file_path="/mnt/c/OpenClaw/logs/hitl_audit.jsonl",
        current_role="JSONL transition audit for HITL state changes.",
        current_state_store="Windows-side JSONL file",
        approval_object_shape="append-only transition event records",
        actively_referenced="yes: hitl_pending_store.py and hitl_pending_action.py write it",
        safe="evidence-only, not canonical approval authority",
        depends_on="HITL JSON stores",
        disposition="keep_compatibility_shim",
        reason="It may contain useful audit evidence, but should be replaced by SQLite receipts.",
        risk_if_kept="JSONL logs may be treated as complete receipt authority when they are not.",
        risk_if_removed="Would lose potential transition evidence.",
        recommended_next_action="Keep as compatibility/evidence ref; future SQLite receipts should replace it.",
    ),
    DispositionSurface(
        surface_id="hitl_notifications_jsonl",
        surface="HITL notification JSONL",
        file_path="/mnt/c/OpenClaw/logs/hitl_notifications.jsonl",
        current_role="Notification send/callback audit path.",
        current_state_store="Windows-side JSONL file",
        approval_object_shape="notification event records",
        actively_referenced="yes: hitl_notification_service.py",
        safe="evidence-only, not approval authority",
        depends_on="hitl_notification_service.py",
        disposition="retire_after_migration",
        reason="Future notification receipts should live in SQLite; old JSONL can remain evidence until transition completes.",
        risk_if_kept="Can drift from canonical receipts.",
        risk_if_removed="Could lose notification troubleshooting evidence.",
        recommended_next_action="Retire only after SQLite notification receipts exist and operator confirms.",
    ),
    DispositionSurface(
        surface_id="hitl_pending_action_legacy",
        surface="Older HITL pending action store",
        file_path="hitl_pending_action.py; /mnt/c/OpenClaw/logs/hitl_pending_actions.json",
        current_role="Older parallel pending action queue.",
        current_state_store="hitl_pending_actions.json and hitl_audit.jsonl",
        approval_object_shape="older pending action list with status transitions",
        actively_referenced="not proven outside tests/docs by current static search",
        safe="not safe as live authority",
        depends_on="chief_file_io.py and Windows JSON state",
        disposition="retire_after_migration",
        reason="It is a parallel old store and should not survive as a second approval system.",
        risk_if_kept="Duplicate HITL authority path can confuse callers and operators.",
        risk_if_removed="Unknown if a dormant caller still expects it; prove first.",
        recommended_next_action="Prove unused outside tests/docs, then retire after SQLite contract covers required behavior.",
    ),
    DispositionSurface(
        surface_id="approval_log_md",
        surface="Vault Approval Log Markdown",
        file_path="/mnt/c/OpenClawShared/openclaw-vault/System/Approval Log.md",
        current_role="Human-readable approval log sink for Chief approval decisions.",
        current_state_store="Markdown in Obsidian vault path",
        approval_object_shape="append-only-ish Markdown decision entry",
        actively_referenced="yes: chief_approval_brain.py writes it",
        safe="not safe as authority; useful as human log",
        depends_on="chief_approval_brain.py",
        disposition="retire_after_migration",
        reason="SQLite receipts should become canonical; Markdown can remain human-facing export later.",
        risk_if_kept="Markdown log may drift or be mistaken for complete authority.",
        risk_if_removed="Would remove a human audit trail before receipts/export are ready.",
        recommended_next_action="Replace with SQLite receipts plus generated operator read-model; retire direct writes later.",
    ),
    DispositionSurface(
        surface_id="choice_pending_json_bridge",
        surface="Chief workflow choice bridge",
        file_path="chief_approval_bridge.py; /mnt/c/OpenClawShared/album/choice_pending.json",
        current_role="Non-blocking workflow choice prompt, not action approval.",
        current_state_store="choice_pending.json",
        approval_object_shape="choice prompt/options/answer, no action payload hash or execution receipt",
        actively_referenced="yes: Chief listener/router workflow choice code",
        safe="safe only if framed as workflow choice, not approval authority",
        depends_on="Chief workflow routing and Telegram notify",
        disposition="unknown_operator_decision",
        reason="It may be useful UX, but operator should decide whether it belongs in HITL authority or a separate workflow-choice substrate.",
        risk_if_kept="Approval language can blur action approval with simple choices.",
        risk_if_removed="May disrupt album/workflow prompts.",
        recommended_next_action="Keep out of Guardian HITL adapter scope until operator chooses workflow-choice fate.",
    ),
    DispositionSurface(
        surface_id="google_access_broker_approval_hook",
        surface="Google broker approval hook",
        file_path="google_access_broker.py",
        current_role="Class B/C Google actions call chief_approval_brain.request_approval before external API action.",
        current_state_store="Delegates to approval_pending.json plus broker audit JSONL",
        approval_object_shape="action label/context approved through Chief gate",
        actively_referenced="yes: broker dispatcher calls _request_approval",
        safe="not safe to expand; current path depends on mixed Chief JSON authority",
        depends_on="chief_approval_brain.py and Google broker capability classes",
        disposition="replace_with_sqlite_operator_action",
        reason="External-action approval must bind to canonical packet and receipts before any expansion.",
        risk_if_kept="External API writes remain tied to old JSON action-text approvals.",
        risk_if_removed="Would break existing broker protection before replacement.",
        recommended_next_action="Future adapter should require explicit approved packet and SQLite decision receipt.",
    ),
    DispositionSurface(
        surface_id="repo_b_approval_tree",
        surface="Repo B approval/HITL runtime tree",
        file_path="/home/openclaw_external/openclaw-runtime/chief_approval*.py; chief_guardian*.py; hitl task files",
        current_role="Pre-split reference implementation and planning evidence.",
        current_state_store="Repo B legacy JSON/Telegram/vault patterns by source reference only",
        approval_object_shape="legacy concepts, not current authority",
        actively_referenced="reference-only; not imported or executed",
        safe="safe as read-only reference only",
        depends_on="none in Repo A runtime by this lane",
        disposition="block_no_go",
        reason="Repo B runtime must not be used as current approval authority.",
        risk_if_kept="Reference code can tempt direct execution or bulk porting.",
        risk_if_removed="Would lose useful pre-split design evidence.",
        recommended_next_action="Keep reference-only; port concepts only through Repo A contract/tests.",
    ),
    DispositionSurface(
        surface_id="raw_command_or_freeform_shell_approval",
        surface="Raw command/freeform shell approval pattern",
        file_path="no canonical file; forbidden payload pattern",
        current_role="Forbidden approval shape.",
        current_state_store="none allowed",
        approval_object_shape="raw command text, shell string, or arbitrary subprocess request",
        actively_referenced="blocked by contract and Operator Action validation",
        safe="unsafe",
        depends_on="none",
        disposition="block_no_go",
        reason="Approving raw commands would create arbitrary execution authority.",
        risk_if_kept="Critical: arbitrary command execution or approval bypass.",
        risk_if_removed="No downside; this must stay forbidden.",
        recommended_next_action="Keep blocked in tests and contract validators.",
    ),
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


def _surface_dict(surface: DispositionSurface) -> dict[str, Any]:
    return asdict(surface)


def _by_disposition(disposition: str) -> list[dict[str, Any]]:
    return [
        _surface_dict(surface)
        for surface in SURFACES
        if surface.disposition == disposition
    ]


def build_guardian_hitl_surface_disposition(
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Return the deterministic Guardian/HITL surface disposition read-model."""
    surfaces = [_surface_dict(surface) for surface in SURFACES]
    counts = Counter(surface.disposition for surface in SURFACES)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or utc_now(),
        "runtime_authority_changed": False,
        "old_hitl_deleted": False,
        "repo_b_execution_allowed": False,
        "surfaces": surfaces,
        "surface_count": len(surfaces),
        "disposition_counts": dict(sorted(counts.items())),
        "canonical_surfaces": _by_disposition("keep_canonical"),
        "compatibility_surfaces": _by_disposition("keep_compatibility_shim"),
        "replace_surfaces": _by_disposition("replace_with_sqlite_operator_action"),
        "retire_later_surfaces": _by_disposition("retire_after_migration"),
        "blocked_surfaces": _by_disposition("block_no_go"),
        "unknown_operator_decision_surfaces": _by_disposition("unknown_operator_decision"),
        "answers": {
            "what_should_be_canonical": [
                "operator_action_path",
                "operator_action_inbox",
                "guardian_sqlite_contract",
                "cassandra_recovery_clearance_fixed_scope_only",
            ],
            "what_should_be_compatibility_only": [
                "chief_approval_brain",
                "chief_guardian_listener",
                "chief_guardian_sender",
                "chief_router approval fallback",
                "chief_watcher approval replay",
                "approval_pending.json",
                "hitl_pending_state.json",
                "hitl_audit.jsonl while transition evidence is needed",
            ],
            "what_should_be_replaced": [
                "Cassandra HITL pending store backing state",
                "HITL action service backing store",
                "Google broker approval hook's dependency on Chief JSON approval",
            ],
            "what_should_be_retired_later": [
                "older hitl_pending_action.py / hitl_pending_actions.json",
                "direct Markdown Approval Log authority",
                "HITL notification JSONL once SQLite notification receipts exist",
            ],
            "what_should_be_blocked": [
                "Repo B approval runtime execution",
                "raw command/freeform shell approval",
            ],
            "what_needs_operator_decision": [
                "whether Chief workflow choice bridge belongs in HITL authority or a separate workflow-choice substrate",
            ],
            "minimum_safe_path": [
                "keep Operator Action canonical",
                "keep old JSON-backed paths as compatibility only",
                "write an adapter plan before wiring",
                "do not import Cassandra/Chief memory as authority",
                "do not enable remote builder or new send paths",
            ],
        },
        "safe_to_plan_adapters": True,
        "safe_to_import_cassandra_chief_memory": False,
        "safe_to_enable_remote_builder": False,
        "boundaries": dict(NO_AUTHORITY_FLAGS),
        "next_safe_move": "Plan the Guardian HITL SQLite compatibility adapters without wiring runtime behavior yet.",
    }


def format_guardian_hitl_surface_disposition(payload: dict[str, Any]) -> str:
    """Render a concise operator-facing disposition packet."""
    lines = [
        "# Guardian/HITL Surface Disposition v0",
        "",
        "## Bottom Line",
        "",
        "Operator Action stays canonical. Chief/Guardian JSON approval and Cassandra HITL JSON remain compatibility-only or replacement targets. Old JSON cannot be deleted yet. Memory import and remote-builder work remain unsafe.",
        "",
        "## What Stays Canonical",
        "",
    ]
    for surface in payload["canonical_surfaces"]:
        lines.append(f"- `{surface['surface_id']}`: {surface['surface']}")
    lines.extend(["", "## Compatibility Only", ""])
    for surface in payload["compatibility_surfaces"][:10]:
        lines.append(f"- `{surface['surface_id']}`: {surface['recommended_next_action']}")
    lines.extend(["", "## Replace With SQLite Operator Action / Guardian Contract", ""])
    for surface in payload["replace_surfaces"]:
        lines.append(f"- `{surface['surface_id']}`: {surface['reason']}")
    lines.extend(["", "## Retire Later", ""])
    for surface in payload["retire_later_surfaces"]:
        lines.append(f"- `{surface['surface_id']}`: {surface['recommended_next_action']}")
    lines.extend(["", "## Dangerous / Blocked", ""])
    for surface in payload["blocked_surfaces"]:
        lines.append(f"- `{surface['surface_id']}`: {surface['reason']}")
    lines.extend(["", "## Cannot Touch Yet", ""])
    lines.extend(
        [
            "- Do not delete `approval_pending.json`, `hitl_pending_state.json`, or HITL JSONL logs.",
            "- Do not disable Chief/Guardian approval paths before compatibility adapters exist.",
            "- Do not import Cassandra/Chief memory as authority.",
            "- Do not enable remote-builder or new send paths.",
        ]
    )
    if payload["unknown_operator_decision_surfaces"]:
        lines.extend(["", "## Needs Operator Decision", ""])
        for surface in payload["unknown_operator_decision_surfaces"]:
            lines.append(f"- `{surface['surface_id']}`: {surface['recommended_next_action']}")
    lines.extend(
        [
            "",
            "## Next Safe Move",
            "",
            payload["next_safe_move"],
            "",
        ]
    )
    return "\n".join(lines)


def build_guardian_hitl_surface_disposition_ready_packet() -> dict[str, Any]:
    return {
        "schema_version": READY_PACKET_VERSION,
        "prompt_2_ready": True,
        "recommended_lane": "Guardian HITL SQLite Compatibility Adapter Plan v0",
        "safe_to_plan_adapters": True,
        "safe_to_import_cassandra_chief_memory": False,
        "safe_to_enable_remote_builder": False,
        "runtime_authority_changed": False,
        "old_hitl_deleted": False,
        "exact_files_to_inspect_next": [
            "guardian_hitl_surface_disposition.py",
            "guardian_hitl_sqlite_authority_contract.py",
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
            "generated/read_models/guardian_hitl_surface_disposition.json",
        ],
        "exact_files_to_create_or_update_next": [
            "docs/operations/GUARDIAN_HITL_SQLITE_COMPATIBILITY_ADAPTER_PLAN_V0.md",
            "tests/test_guardian_hitl_sqlite_compatibility_adapter_plan.py",
        ],
        "validation_commands": [
            "PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_guardian_hitl_surface_disposition.py -q",
            "python3 -m json.tool generated/read_models/guardian_hitl_surface_disposition.json >/dev/null",
            "python3 -m json.tool docs/operations/GUARDIAN_HITL_SURFACE_DISPOSITION_READY_PACKET.json >/dev/null",
            "git diff --check",
            "git diff --cached --check",
            "git status -sb --untracked-files=all",
        ],
        "stop_conditions": [
            "adapter planning would require reading old HITL JSON/JSONL contents",
            "adapter planning would require runtime service changes",
            "adapter planning would require Telegram/Gmail/email sends",
            "adapter planning would require Repo B import/execution",
            "adapter planning would treat old JSON as canonical truth",
            "adapter planning would grant remote-builder or send authority",
        ],
        "must_not_do": [
            "do not wire adapters yet",
            "do not modify runtime behavior",
            "do not delete old HITL JSON/JSONL",
            "do not disable approval paths",
            "do not import data",
            "do not enable agents",
            "do not send Telegram/Gmail/email",
            "do not run Repo B code",
            "do not commit dirty agent_presence generated files",
        ],
    }


def export_guardian_hitl_surface_disposition(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    export_path = _export_root_path(export_root)
    export_path.mkdir(parents=True, exist_ok=True)
    payload = build_guardian_hitl_surface_disposition(generated_at=generated_at)
    operator_payload = format_guardian_hitl_surface_disposition(payload)

    json_path = export_path / JSON_EXPORT_NAME
    operator_path = export_path / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(operator_payload, encoding="utf-8")

    return {
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "surface_count": payload["surface_count"],
        "runtime_authority_changed": payload["runtime_authority_changed"],
        "old_hitl_deleted": payload["old_hitl_deleted"],
        "safe_to_plan_adapters": payload["safe_to_plan_adapters"],
        "safe_to_import_cassandra_chief_memory": payload["safe_to_import_cassandra_chief_memory"],
        "safe_to_enable_remote_builder": payload["safe_to_enable_remote_builder"],
    }


__all__ = [
    "DISPOSITIONS",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "READY_PACKET_VERSION",
    "SCHEMA_VERSION",
    "SURFACES",
    "build_guardian_hitl_surface_disposition",
    "build_guardian_hitl_surface_disposition_ready_packet",
    "export_guardian_hitl_surface_disposition",
    "format_guardian_hitl_surface_disposition",
    "stable_json",
]

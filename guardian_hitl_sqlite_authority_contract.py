"""Guardian/HITL SQLite authority contract v0.

This module defines the canonical approval contract OpenClaw should converge
on before Cassandra/Chief memory import, remote-builder bridges, or new
external-action workflows expand. It is metadata/read-model code only: it does
not modify runtime services, read old HITL JSON contents, execute Repo B code,
send messages, or grant runtime authority.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")
SCHEMA_VERSION = "guardian_hitl_sqlite_authority_contract_v0"
READY_PACKET_VERSION = "guardian_hitl_sqlite_authority_contract_ready_packet_v0"
JSON_EXPORT_NAME = "guardian_hitl_sqlite_authority_contract.json"
OPERATOR_EXPORT_NAME = "guardian_hitl_sqlite_authority_contract_OPERATOR.md"

OLD_HITL_CLASSIFICATION = "authority_conflict_reconcile_first"

NO_AUTHORITY_FLAGS = {
    "runtime_authority_changed": False,
    "old_hitl_deleted": False,
    "legacy_json_still_active": True,
    "repo_b_execution_allowed": False,
    "telegram_send_added": False,
    "gmail_send_added": False,
    "email_send_added": False,
    "runtime_service_modified": False,
    "agent_activation_added": False,
    "approval_bypass_allowed": False,
    "freeform_shell_approval_allowed": False,
    "raw_command_text_allowed": False,
    "safe_to_import_cassandra_chief_memory": False,
    "safe_to_enable_remote_builder": False,
    "safe_to_expand_send_paths": False,
}

CANONICAL_PAYLOAD_REQUIRED_FIELDS = (
    "approval_id",
    "action_type",
    "actor",
    "target",
    "payload_hash",
    "payload_schema_version",
    "source_intent_ref",
    "idempotency_key",
    "requested_at",
    "expires_at",
    "ttl_seconds",
    "authority_scope",
    "risk_tier",
)

CANONICAL_DECISION_REQUIRED_FIELDS = (
    "approval_id",
    "decision",
    "decided_by",
    "decided_at",
    "decision_receipt_id",
    "approved_payload_hash",
)

CANONICAL_RECEIPT_REQUIRED_FIELDS = (
    "receipt_id",
    "approval_id",
    "receipt_type",
    "status",
    "summary",
    "created_at",
)

FORBIDDEN_PAYLOAD_KEYS = {
    "argv",
    "cmd",
    "command",
    "command_args",
    "command_string",
    "command_text",
    "exec",
    "execute_raw",
    "freeform_shell",
    "raw_command",
    "raw_command_text",
    "shell",
    "shell_command",
    "subprocess",
}

EXPLICIT_PACKET_REQUIRED_ACTION_CLASSES = {
    "send",
    "deploy",
    "runtime_activation",
    "remote_builder",
    "external_api_write",
    "email_send",
    "telegram_send",
    "gmail_send",
}


@dataclass(frozen=True)
class ContractTable:
    table_name: str
    purpose: str
    authority_role: str
    required_columns: tuple[str, ...]
    default_flags: dict[str, bool]
    status: str


@dataclass(frozen=True)
class TransitionPath:
    surface_id: str
    current_surface: str
    current_store: str
    contract_role: str
    transition_rule: str
    current_classification: str


CONTRACT_TABLES: tuple[ContractTable, ...] = (
    ContractTable(
        table_name="guardian_hitl_approval_requests",
        purpose="Canonical immutable approval request record for action-capable workflows.",
        authority_role="future_canonical_request_store",
        required_columns=(
            "approval_id",
            "action_type",
            "actor",
            "target",
            "payload_hash",
            "payload_schema_version",
            "source_intent_ref",
            "idempotency_key",
            "requested_at",
            "expires_at",
            "ttl_seconds",
            "authority_scope",
            "risk_tier",
            "status",
            "request_receipt_id",
            "legacy_json_ref",
            "created_at",
            "updated_at",
        ),
        default_flags={
            "approval_required": True,
            "runtime_authority_granted": False,
            "send_authority_granted": False,
            "freeform_shell_approval_allowed": False,
            "raw_command_text_allowed": False,
            "legacy_json_is_truth": False,
        },
        status="contract_defined_not_runtime_wired",
    ),
    ContractTable(
        table_name="guardian_hitl_approval_decisions",
        purpose="Canonical approval, denial, expiry, or revocation decision bound to the exact request payload hash.",
        authority_role="future_canonical_decision_store",
        required_columns=(
            "decision_id",
            "approval_id",
            "decision",
            "decided_by",
            "decided_at",
            "decision_receipt_id",
            "approved_payload_hash",
            "decision_basis",
            "created_at",
        ),
        default_flags={
            "execution_started": False,
            "decision_mutates_payload": False,
            "freeform_shell_approval_allowed": False,
            "raw_command_text_allowed": False,
        },
        status="contract_defined_not_runtime_wired",
    ),
    ContractTable(
        table_name="guardian_hitl_approval_receipts",
        purpose="Request, decision, notification, execution-attempt, and result receipts for the approval lifecycle.",
        authority_role="future_canonical_receipt_store",
        required_columns=(
            "receipt_id",
            "approval_id",
            "receipt_type",
            "status",
            "summary",
            "created_at",
            "payload_hash",
            "source_surface",
        ),
        default_flags={
            "raw_private_data_stored": False,
            "runtime_authority_granted": False,
            "send_authority_granted": False,
            "repo_b_execution_allowed": False,
        },
        status="contract_defined_not_runtime_wired",
    ),
    ContractTable(
        table_name="guardian_hitl_legacy_authority_refs",
        purpose="Metadata-only catalog of old JSON/JSONL approval stores during transition.",
        authority_role="transition_catalog_not_truth",
        required_columns=(
            "legacy_ref_id",
            "source_ref",
            "source_type",
            "used_by_current_repo_a",
            "classification",
            "raw_content_read",
            "deprecation_proof_required",
            "created_at",
        ),
        default_flags={
            "old_files_are_truth": False,
            "raw_content_read": False,
            "delete_allowed": False,
            "migration_allowed_without_reconciliation": False,
        },
        status="contract_defined_not_runtime_wired",
    ),
)

TRANSITION_PATHS: tuple[TransitionPath, ...] = (
    TransitionPath(
        surface_id="operator_action_path",
        current_surface="operator_action.py",
        current_store="SQLite operator_action_* tables",
        contract_role="current clean SQLite foundation for narrow allowlisted local actions",
        transition_rule="Preserve as existing governed path; future Guardian contract should reuse its request/approval/receipt spine rather than duplicate it.",
        current_classification="active_runtime_path",
    ),
    TransitionPath(
        surface_id="chief_approval_brain",
        current_surface="chief_approval_brain.py",
        current_store="approval_pending.json plus Approval Log.md",
        contract_role="transition adapter candidate",
        transition_rule="Do not delete or disable. First add a SQLite request/decision mirror, then prove every active caller reads the contract before deprecation.",
        current_classification=OLD_HITL_CLASSIFICATION,
    ),
    TransitionPath(
        surface_id="hitl_pending_store",
        current_surface="hitl_pending_store.py",
        current_store="hitl_pending_state.json plus hitl_audit.jsonl",
        contract_role="transition adapter candidate for Cassandra action proposals",
        transition_rule="Do not treat approved JSON records as execution authority until exact payload hash, TTL, idempotency, and receipt fields land in SQLite.",
        current_classification=OLD_HITL_CLASSIFICATION,
    ),
    TransitionPath(
        surface_id="hitl_action_service",
        current_surface="hitl_action_service.py",
        current_store="delegates to hitl_pending_store.py",
        contract_role="service wrapper candidate",
        transition_rule="Keep as non-executing wrapper until approval decisions are bound to canonical SQLite receipts.",
        current_classification="mixed_or_conflicting",
    ),
    TransitionPath(
        surface_id="guardian_listener_sender",
        current_surface="chief_guardian_listener.py and chief_guardian_sender.py",
        current_store="Telegram-facing approval transport over Chief/HITL state",
        contract_role="transport adapter only",
        transition_rule="Guardian can carry decisions, but SQLite contract must own authority and receipts.",
        current_classification=OLD_HITL_CLASSIFICATION,
    ),
    TransitionPath(
        surface_id="cassandra_recovery_clearance",
        current_surface="agent_presence.py recovery clearance functions",
        current_store="SQLite agent_recovery_* tables",
        contract_role="fixed-scope special case",
        transition_rule="Keep separate and fixed to Cassandra recovery; do not generalize into runtime action approval.",
        current_classification="active_special_case",
    ),
)

LEGACY_JSON_STATE_REFS = (
    {
        "state_id": "approval_pending_json",
        "source_ref": "/mnt/c/OpenClaw/logs/approval_pending.json",
        "used_by_current_repo_a": True,
        "classification": OLD_HITL_CLASSIFICATION,
        "raw_content_read": False,
        "deprecation_proof_required": "No current non-test Repo A path reads or writes it, and equivalent SQLite request/decision/receipt paths are proven.",
    },
    {
        "state_id": "hitl_pending_state_json",
        "source_ref": "/mnt/c/OpenClaw/logs/hitl_pending_state.json",
        "used_by_current_repo_a": True,
        "classification": OLD_HITL_CLASSIFICATION,
        "raw_content_read": False,
        "deprecation_proof_required": "Cassandra HITL proposal, approval, denial, expiry, and notification state is mirrored and then owned by SQLite.",
    },
    {
        "state_id": "hitl_audit_jsonl",
        "source_ref": "/mnt/c/OpenClaw/logs/hitl_audit.jsonl",
        "used_by_current_repo_a": True,
        "classification": OLD_HITL_CLASSIFICATION,
        "raw_content_read": False,
        "deprecation_proof_required": "Audit events are represented as canonical receipts or metadata-only legacy references.",
    },
    {
        "state_id": "hitl_pending_actions_json",
        "source_ref": "/mnt/c/OpenClaw/logs/hitl_pending_actions.json",
        "used_by_current_repo_a": "unknown_runtime_use",
        "classification": OLD_HITL_CLASSIFICATION,
        "raw_content_read": False,
        "deprecation_proof_required": "Static search and safe runtime-status review prove no non-test caller remains.",
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


def _nested_forbidden_keys(payload: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            key_text = str(key)
            dotted = f"{prefix}.{key_text}" if prefix else key_text
            if key_text in FORBIDDEN_PAYLOAD_KEYS:
                found.append(dotted)
            found.extend(_nested_forbidden_keys(value, dotted))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            found.extend(_nested_forbidden_keys(value, f"{prefix}[{index}]"))
    return found


def validate_canonical_approval_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the shape of a future canonical approval payload.

    The validator does not persist data or approve anything. It only checks the
    contract needed before any action-capable workflow can rely on a packet.
    """
    errors: list[str] = []
    missing = [
        field
        for field in CANONICAL_PAYLOAD_REQUIRED_FIELDS
        if not str(payload.get(field, "")).strip()
    ]
    if missing:
        errors.append("missing_required_fields:" + ",".join(missing))

    forbidden_keys = _nested_forbidden_keys(payload)
    if forbidden_keys:
        errors.append("forbidden_payload_keys:" + ",".join(sorted(forbidden_keys)))

    ttl = payload.get("ttl_seconds")
    if not isinstance(ttl, int) or ttl <= 0:
        errors.append("ttl_seconds_must_be_positive_integer")

    if payload.get("payload_mutable_after_approval") is True:
        errors.append("payload_must_be_immutable_after_approval")

    action_class = str(payload.get("action_class", "")).strip()
    if action_class in EXPLICIT_PACKET_REQUIRED_ACTION_CLASSES and not str(
        payload.get("explicit_authorized_packet_ref", "")
    ).strip():
        errors.append("explicit_authorized_packet_ref_required_for_action_class")

    return {
        "valid": not errors,
        "errors": errors,
        "required_fields": list(CANONICAL_PAYLOAD_REQUIRED_FIELDS),
        "forbidden_keys": sorted(FORBIDDEN_PAYLOAD_KEYS),
    }


def _contract_criteria() -> dict[str, bool]:
    return {
        "contract_defined": True,
        "sqlite_state_store_defined": True,
        "runtime_paths_wired_to_contract": False,
        "old_json_no_longer_active": False,
        "legacy_hitl_adapters_written": False,
        "operator_action_external_action_coverage_proven": False,
        "cassandra_chief_import_gate_satisfied": False,
        "remote_builder_gate_satisfied": False,
        "send_path_gate_satisfied": False,
    }


def _future_approval_contract() -> dict[str, Any]:
    return {
        "contract_id": SCHEMA_VERSION,
        "canonical_state_store": "SQLite business_ops ledger, reusing Operator Action concepts and adding Guardian/HITL contract tables only in a future wiring lane.",
        "canonical_approval_object": {
            "required_request_fields": list(CANONICAL_PAYLOAD_REQUIRED_FIELDS),
            "required_decision_fields": list(CANONICAL_DECISION_REQUIRED_FIELDS),
            "required_receipt_fields": list(CANONICAL_RECEIPT_REQUIRED_FIELDS),
            "immutable_payload_required": True,
            "payload_hash_required": True,
            "idempotency_key_required": True,
            "ttl_required": True,
            "exact_action_binding_required": True,
            "receipt_required": True,
            "raw_command_text_allowed": False,
            "freeform_shell_approval_allowed": False,
            "send_deploy_runtime_requires_explicit_approved_packet": True,
        },
        "idempotency_key_rules": [
            "The same actor, action_type, target, payload_hash, and source_intent_ref must map to one active request.",
            "A duplicate request with the same idempotency key must return the existing active approval record, not create a second authority record.",
            "Expired, denied, or completed records may be referenced by receipt but must not be silently reactivated.",
        ],
        "ttl_rules": [
            "Every approval request must carry expires_at and ttl_seconds.",
            "An expired request cannot be approved without a new request and new payload hash.",
            "TTL is part of the approval object and cannot be extended by mutating the approved payload.",
        ],
        "receipt_rules": [
            "Request receipt records the immutable payload hash and source intent.",
            "Decision receipt records approve, deny, expire, or revoke against the same payload hash.",
            "Execution/result receipt is required only when a separately authorized executor exists.",
        ],
        "forbidden": [
            "raw command text",
            "freeform shell approvals",
            "approval of unparsed text",
            "payload mutation after approval",
            "send/deploy/runtime action without explicit approved packet",
            "old HITL JSON as canonical truth",
        ],
    }


def build_guardian_hitl_sqlite_authority_contract(
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Return the deterministic Guardian/HITL SQLite authority contract read-model."""
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or utc_now(),
        "runtime_authority_changed": False,
        "old_hitl_deleted": False,
        "legacy_json_still_active": True,
        "old_hitl_classification": OLD_HITL_CLASSIFICATION,
        "contract_defined": True,
        "sqlite_schema_applied_to_runtime_db": False,
        "repo_b_execution_allowed": False,
        "canonical_state_store": "SQLite business_ops ledger",
        "canonical_approval_object": _future_approval_contract()["canonical_approval_object"],
        "contract_tables": [asdict(table) for table in CONTRACT_TABLES],
        "transition_paths": [asdict(path) for path in TRANSITION_PATHS],
        "legacy_json_state_refs": list(LEGACY_JSON_STATE_REFS),
        "contract_criteria": _contract_criteria(),
        "safe_to_import_cassandra_chief_memory": False,
        "safe_to_enable_remote_builder": False,
        "safe_to_expand_send_paths": False,
        "cassandra_recovery_clearance": {
            "classification": "active_special_case",
            "fixed_scope": True,
            "general_runtime_authority": False,
            "recovery_action_id": "cassandra_systemd_user_start",
            "contract_rule": "Do not generalize Cassandra recovery clearance into arbitrary runtime approval.",
        },
        "operator_action_relationship": {
            "current_status": "cleanest existing SQLite-backed action approval path",
            "contract_role": "foundation_to_reuse",
            "limitation": "covers narrow allowlisted local actions only; it has not replaced Chief/Guardian JSON or Cassandra HITL JSON.",
        },
        "hitl_pending_store_relationship": {
            "current_status": "mixed_or_conflicting_json_backed_path",
            "contract_role": "future_adapter_candidate",
            "limitation": "must not grant execution authority until it writes canonical SQLite request/decision/receipt rows.",
        },
        "legacy_json_transition_rule": {
            "classification": OLD_HITL_CLASSIFICATION,
            "delete_allowed": False,
            "deprecate_allowed_now": False,
            "must_prove_before_deprecation": [
                "all current non-test callers moved to SQLite contract",
                "old JSON no longer read or written outside tests/docs",
                "request, decision, expiry, notification, and result receipts exist",
                "operator review confirms no useful pending authority is lost",
            ],
        },
        "boundaries": dict(NO_AUTHORITY_FLAGS),
        "future_approval_contract": _future_approval_contract(),
        "next_safe_move": "Implement a non-runtime Guardian/HITL SQLite contract schema adapter plan before wiring Chief/Guardian or Cassandra HITL callers.",
    }


def format_guardian_hitl_sqlite_authority_contract(payload: dict[str, Any]) -> str:
    """Render a concise operator-facing Markdown read-model."""
    lines = [
        "# Guardian/HITL SQLite Authority Contract v0",
        "",
        "## Bottom Line",
        "",
        "The canonical approval contract is now defined, but it is not wired into live runtime paths. Operator Action remains the cleanest SQLite-backed foundation. Chief/Guardian and Cassandra HITL still actively depend on legacy JSON-backed approval state.",
        "",
        "## Contract Rules",
        "",
        "- Approval requests need immutable action identity, payload hash, idempotency key, TTL, exact action binding, and receipts.",
        "- Raw command text and freeform shell approval are forbidden.",
        "- Send, deploy, remote-builder, and runtime actions require an explicit approved packet before they can ever execute.",
        "- Old HITL JSON/JSONL is transition evidence, not canonical truth.",
        "",
        "## Current Status",
        "",
        f"- Runtime authority changed: `{str(payload['runtime_authority_changed']).lower()}`",
        f"- Old HITL deleted: `{str(payload['old_hitl_deleted']).lower()}`",
        f"- Legacy JSON still active: `{str(payload['legacy_json_still_active']).lower()}`",
        f"- Cassandra/Chief memory import safe now: `{str(payload['safe_to_import_cassandra_chief_memory']).lower()}`",
        f"- Remote-builder bridge safe now: `{str(payload['safe_to_enable_remote_builder']).lower()}`",
        f"- Send-path expansion safe now: `{str(payload['safe_to_expand_send_paths']).lower()}`",
        "",
        "## Transition Shape",
        "",
    ]
    for path in payload["transition_paths"]:
        lines.append(
            f"- `{path['surface_id']}`: {path['contract_role']} - {path['transition_rule']}"
        )
    lines.extend(
        [
            "",
            "## Must Wait",
            "",
            "- Do not import Cassandra/Chief memory as authority yet.",
            "- Do not enable a remote-builder bridge yet.",
            "- Do not expand Telegram/Gmail/email send paths yet.",
            "- Do not delete or deprecate old HITL JSON until the active callers have moved.",
            "",
            "## Next Safe Move",
            "",
            payload["next_safe_move"],
            "",
        ]
    )
    return "\n".join(lines)


def build_guardian_hitl_sqlite_contract_ready_packet() -> dict[str, Any]:
    return {
        "schema_version": READY_PACKET_VERSION,
        "contract_defined": True,
        "runtime_authority_changed": False,
        "old_hitl_deleted": False,
        "legacy_json_still_active": True,
        "safe_to_import_cassandra_chief_memory": False,
        "safe_to_enable_remote_builder": False,
        "safe_to_expand_send_paths": False,
        "recommended_next_lane": "Guardian HITL SQLite Contract Adapter Plan v0",
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
            "guardian_hitl_sqlite_authority_contract.py",
            "generated/read_models/guardian_hitl_sqlite_authority_contract.json",
        ],
        "exact_files_to_create_or_update_next": [
            "docs/operations/GUARDIAN_HITL_SQLITE_CONTRACT_ADAPTER_PLAN_V0.md",
            "tests/test_guardian_hitl_sqlite_contract_adapter_plan.py",
        ],
        "validation_commands": [
            "PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_guardian_hitl_sqlite_authority_contract.py -q",
            "python3 -m json.tool generated/read_models/guardian_hitl_sqlite_authority_contract.json >/dev/null",
            "python3 -m json.tool docs/operations/GUARDIAN_HITL_SQLITE_AUTHORITY_CONTRACT_READY_PACKET.json >/dev/null",
            "git diff --check",
            "git diff --cached --check",
            "git status -sb --untracked-files=all",
        ],
        "stop_conditions": [
            "a live runtime caller would need to be modified before adapter design is complete",
            "old HITL JSON/JSONL contents would need to be read",
            "Telegram, Gmail, email, deployment, or remote-builder send paths would need to be enabled",
            "Repo B code would need to be imported or executed",
            "freeform shell or raw command approval would be required",
            "Cassandra recovery clearance would need to become general runtime authority",
        ],
        "must_not_do": [
            "do not delete old HITL JSON/JSONL",
            "do not disable existing approval paths",
            "do not modify runtime services",
            "do not enable agents",
            "do not send Telegram/Gmail/email",
            "do not inspect secrets, env files, raw logs, or private data",
            "do not commit dirty agent_presence generated files",
            "do not create general runtime execution authority",
        ],
    }


def export_guardian_hitl_sqlite_authority_contract(
    *,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    export_path = _export_root_path(export_root)
    export_path.mkdir(parents=True, exist_ok=True)
    payload = build_guardian_hitl_sqlite_authority_contract(generated_at=generated_at)
    operator_payload = format_guardian_hitl_sqlite_authority_contract(payload)

    json_path = export_path / JSON_EXPORT_NAME
    operator_path = export_path / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(operator_payload, encoding="utf-8")

    return {
        "json_path": json_path.as_posix(),
        "operator_path": operator_path.as_posix(),
        "contract_defined": payload["contract_defined"],
        "runtime_authority_changed": payload["runtime_authority_changed"],
        "old_hitl_deleted": payload["old_hitl_deleted"],
        "legacy_json_still_active": payload["legacy_json_still_active"],
        "safe_to_import_cassandra_chief_memory": payload["safe_to_import_cassandra_chief_memory"],
        "safe_to_enable_remote_builder": payload["safe_to_enable_remote_builder"],
        "safe_to_expand_send_paths": payload["safe_to_expand_send_paths"],
    }


__all__ = [
    "CANONICAL_DECISION_REQUIRED_FIELDS",
    "CANONICAL_PAYLOAD_REQUIRED_FIELDS",
    "CANONICAL_RECEIPT_REQUIRED_FIELDS",
    "CONTRACT_TABLES",
    "FORBIDDEN_PAYLOAD_KEYS",
    "JSON_EXPORT_NAME",
    "OPERATOR_EXPORT_NAME",
    "READY_PACKET_VERSION",
    "SCHEMA_VERSION",
    "build_guardian_hitl_sqlite_authority_contract",
    "build_guardian_hitl_sqlite_contract_ready_packet",
    "export_guardian_hitl_sqlite_authority_contract",
    "format_guardian_hitl_sqlite_authority_contract",
    "stable_json",
    "validate_canonical_approval_payload",
]

"""Authority envelopes, credential handles, leases, unattended runs, and gates.

This is a non-executing contract and provenance layer. It stores scoped
authority objects and credential references only. It never stores raw secrets,
opens Gmail/Coupa/browser, sends, submits, marks paid, mutates ledgers, runs
models, or treats raw chat text as trusted authority.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/authority_secret_custody.sqlite")

AUTHORITY_ENVELOPE_SCHEMA = "AUTHORITY_ENVELOPE_V0"
CREDENTIAL_HANDLE_SCHEMA = "CREDENTIAL_HANDLE_V0"
CREDENTIAL_LEASE_SCHEMA = "CREDENTIAL_LEASE_V0"
UNATTENDED_RUN_ENVELOPE_SCHEMA = "UNATTENDED_RUN_ENVELOPE_V0"
POLICY_GATE_SCHEMA = "POLICY_GATE_V0"

DEFAULT_DENIED_ACTIONS = (
    "ambient_mailbox_scan",
    "compose_email",
    "send_email",
    "create_email_draft",
    "delete_email",
    "archive_email",
    "mark_email_read",
    "modify_email_labels",
    "contacts_read",
    "calendar_access",
    "calendar_mutation",
    "mutate_contacts",
    "promote_contact_memory",
    "open_browser",
    "open_gmail_ui",
    "coupa_submit",
    "mark_paid",
    "mutate_ledger",
    "mutate_workbook",
    "export_pdf",
    "run_excel",
    "trust_raw_authority_granted",
)

GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID = "credential.google_workspace_broker.current"
GOOGLE_WORKSPACE_BROKER_CAPABILITY_ID = "openclaw.google_workspace_broker"
READ_ONLY_EMAIL_LOOKUP_CAPABILITY_ID = "openclaw.read_only_email_lookup"

GOOGLE_WORKSPACE_BROKER_ALLOWED_CAPABILITY_IDS = (
    GOOGLE_WORKSPACE_BROKER_CAPABILITY_ID,
    "openclaw.gmail_metadata_read",
    "openclaw.gmail_body_read",
    "openclaw.gmail_draft_generator",
    "openclaw.gmail_send_mail",
    "openclaw.contacts_readonly_lookup",
    "openclaw.calendar_event_manager",
    READ_ONLY_EMAIL_LOOKUP_CAPABILITY_ID,
)

GOOGLE_WORKSPACE_BROKER_DENIED_ACTIONS = (
    "ambient_mailbox_scan",
    "google_workspace_broker_ambient_use",
    "gmail_send_without_send_authority",
    "gmail_draft_creation_without_draft_authority",
    "compose_email",
    "send_email",
    "create_email_draft",
    "delete_email",
    "archive_email",
    "mark_email_read",
    "modify_email_labels",
    "contacts_read",
    "contact_mutation",
    "mutate_contacts",
    "contact_memory_promotion",
    "promote_contact_memory",
    "calendar_access",
    "calendar_mutation",
    "calendar_mutation_without_calendar_authority",
    "calendar_write_without_action_authority",
    "calendar_delete_without_action_authority",
    "paid_marking",
    "mark_paid",
    "ledger_mutation",
    "mutate_ledger",
    "coupa_submit",
    "open_browser",
    "open_gmail_ui",
    "trust_raw_authority_granted",
)

GOOGLE_WORKSPACE_BROKER_READONLY_ALLOWED_USE = (
    "scoped_gmail_search",
    "scoped_gmail_read",
    "scoped_gmail_metadata_read",
    "receipt_creation",
    "redacted_summary",
)

GOOGLE_WORKSPACE_BROKER_READONLY_DENIED_USE = (
    "compose_email",
    "send_email",
    "create_email_draft",
    "delete_email",
    "archive_email",
    "mark_email_read",
    "modify_email_labels",
    "contacts_read",
    "calendar_access",
    "mutate_contacts",
    "promote_contact_memory",
    "mark_paid",
    "mutate_ledger",
    "coupa_submit",
)

SECRET_FIELD_NAMES = {
    "password",
    "passcode",
    "token",
    "secret",
    "api_key",
    "oauth_token",
    "refresh_token",
    "private_key",
    "cookie",
    "session_cookie",
    "credential_value",
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rooted(path: Path | str) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def _short_hash(*parts: Any, length: int = 16) -> str:
    digest = hashlib.sha256()
    for part in parts:
        value = json.dumps(part, sort_keys=True, ensure_ascii=True) if isinstance(part, (dict, list, tuple)) else str(part)
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:length]


def _json(value: Any) -> str:
    return stable_json(value).strip()


def _loads(value: Any) -> Any:
    if value in (None, ""):
        return None
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return None


def _dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value)
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _walk_keys(payload: Any):
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield str(key)
            yield from _walk_keys(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_keys(value)


def contains_raw_secret_field(payload: Mapping[str, Any]) -> list[str]:
    return sorted({key for key in _walk_keys(payload) if key.lower() in SECRET_FIELD_NAMES})


def connect(sqlite_path: Path = DEFAULT_SQLITE_PATH) -> sqlite3.Connection:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS authority_envelopes (
          envelope_id TEXT PRIMARY KEY,
          operator_id TEXT NOT NULL,
          device_id TEXT NOT NULL,
          confirmation_method TEXT NOT NULL,
          confirmation_receipt_ref TEXT NOT NULL,
          requested_objective TEXT NOT NULL,
          capability_ids TEXT NOT NULL,
          allowed_actions TEXT NOT NULL,
          denied_actions TEXT NOT NULL,
          credential_handles_allowed TEXT NOT NULL,
          live_data_access_allowed INTEGER NOT NULL DEFAULT 0,
          production_action_allowed INTEGER NOT NULL DEFAULT 0,
          external_service_access_allowed INTEGER NOT NULL DEFAULT 0,
          unattended_allowed INTEGER NOT NULL DEFAULT 0,
          one_time_or_reusable TEXT NOT NULL,
          max_scope TEXT NOT NULL,
          expires_at TEXT NOT NULL,
          interrupt_conditions TEXT NOT NULL,
          receipt_requirements TEXT NOT NULL,
          created_at TEXT NOT NULL,
          status TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS credential_handles (
          credential_handle_id TEXT PRIMARY KEY,
          credential_label TEXT NOT NULL,
          credential_kind TEXT NOT NULL,
          vault_provider TEXT NOT NULL,
          vault_ref TEXT NOT NULL,
          allowed_capability_ids TEXT NOT NULL,
          allowed_actions TEXT NOT NULL,
          denied_actions TEXT NOT NULL,
          rotation_policy TEXT NOT NULL,
          last_verified_at TEXT,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS credential_leases (
          lease_id TEXT PRIMARY KEY,
          credential_handle_id TEXT NOT NULL,
          authority_envelope_id TEXT NOT NULL,
          capability_id TEXT NOT NULL,
          allowed_use TEXT NOT NULL,
          denied_use TEXT NOT NULL,
          issued_at TEXT NOT NULL,
          expires_at TEXT NOT NULL,
          adapter_ref TEXT NOT NULL,
          receipt_requirements TEXT NOT NULL,
          status TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS unattended_run_envelopes (
          run_envelope_id TEXT PRIMARY KEY,
          schedule_ref TEXT NOT NULL,
          requested_objective TEXT NOT NULL,
          capability_ids TEXT NOT NULL,
          authority_envelope_refs TEXT NOT NULL,
          allowed_actions TEXT NOT NULL,
          denied_actions TEXT NOT NULL,
          credential_handles_allowed TEXT NOT NULL,
          live_data_access_allowed INTEGER NOT NULL DEFAULT 0,
          production_action_allowed INTEGER NOT NULL DEFAULT 0,
          external_service_access_allowed INTEGER NOT NULL DEFAULT 0,
          max_runtime TEXT NOT NULL,
          max_retries INTEGER NOT NULL,
          run_window TEXT NOT NULL,
          expires_at TEXT NOT NULL,
          interrupt_conditions TEXT NOT NULL,
          notification_policy TEXT NOT NULL,
          receipt_requirements TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS policy_gates (
          gate_id TEXT PRIMARY KEY,
          gate_label TEXT NOT NULL,
          blocked_actions TEXT NOT NULL,
          reason TEXT NOT NULL,
          unlock_requirements TEXT NOT NULL,
          allowed_alternatives TEXT NOT NULL,
          permanently_denied INTEGER NOT NULL DEFAULT 0,
          authority_required TEXT NOT NULL,
          verifier_required TEXT NOT NULL,
          receipt_required TEXT NOT NULL,
          operator_message TEXT NOT NULL,
          details_message TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS authority_events (
          event_id TEXT PRIMARY KEY,
          event_kind TEXT NOT NULL,
          object_schema_version TEXT NOT NULL,
          object_id TEXT NOT NULL,
          reason TEXT NOT NULL,
          event_payload TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """
    )


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    for key in (
        "capability_ids",
        "allowed_actions",
        "denied_actions",
        "credential_handles_allowed",
        "max_scope",
        "interrupt_conditions",
        "receipt_requirements",
        "allowed_capability_ids",
        "allowed_use",
        "denied_use",
        "authority_envelope_refs",
        "run_window",
        "notification_policy",
        "blocked_actions",
        "unlock_requirements",
        "allowed_alternatives",
        "event_payload",
    ):
        if key in result:
            result[key] = _loads(result[key]) or ([] if key != "event_payload" else {})
    for key in ("live_data_access_allowed", "production_action_allowed", "external_service_access_allowed", "unattended_allowed", "permanently_denied"):
        if key in result:
            result[key] = bool(result[key])
    return result


def validate_authority_envelope(envelope: Mapping[str, Any]) -> list[str]:
    required = (
        "schema_version",
        "envelope_id",
        "operator_id",
        "device_id",
        "confirmation_method",
        "confirmation_receipt_ref",
        "requested_objective",
        "capability_ids",
        "allowed_actions",
        "denied_actions",
        "credential_handles_allowed",
        "expires_at",
        "interrupt_conditions",
        "receipt_requirements",
        "created_at",
        "status",
    )
    errors = [f"missing required field: {field}" for field in required if field not in envelope]
    if envelope.get("schema_version") != AUTHORITY_ENVELOPE_SCHEMA:
        errors.append("schema_version must be AUTHORITY_ENVELOPE_V0")
    if not envelope.get("denied_actions"):
        errors.append("denied_actions required")
    if not envelope.get("receipt_requirements"):
        errors.append("receipt_requirements required")
    if not envelope.get("expires_at") and envelope.get("confirmation_method") != "fixture_test":
        errors.append("expires_at required outside fixture_test")
    return errors


def create_authority_envelope(
    *,
    operator_id: str,
    device_id: str,
    confirmation_method: str,
    confirmation_receipt_ref: str,
    requested_objective: str,
    capability_ids: Sequence[str],
    allowed_actions: Sequence[str] = (),
    denied_actions: Sequence[str] = DEFAULT_DENIED_ACTIONS,
    credential_handles_allowed: Sequence[str] = (),
    live_data_access_allowed: bool = False,
    production_action_allowed: bool = False,
    external_service_access_allowed: bool = False,
    unattended_allowed: bool = False,
    one_time_or_reusable: str = "one_time",
    max_scope: Mapping[str, Any] | None = None,
    expires_at: str = "fixture_test",
    interrupt_conditions: Sequence[str] = ("scope_expands", "verifier_fails", "credential_challenge", "stale_proof"),
    receipt_requirements: Sequence[str] = ("confirmation_receipt_ref", "action_receipt"),
    status: str = "draft_pending_confirmation",
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    envelope = {
        "schema_version": AUTHORITY_ENVELOPE_SCHEMA,
        "envelope_id": f"authority_envelope:{_short_hash(operator_id, device_id, requested_objective, capability_ids, generated_at)}",
        "operator_id": operator_id,
        "device_id": device_id,
        "confirmation_method": confirmation_method,
        "confirmation_receipt_ref": confirmation_receipt_ref,
        "requested_objective": requested_objective,
        "capability_ids": list(capability_ids),
        "allowed_actions": list(allowed_actions),
        "denied_actions": list(denied_actions),
        "credential_handles_allowed": list(credential_handles_allowed),
        "live_data_access_allowed": bool(live_data_access_allowed),
        "production_action_allowed": bool(production_action_allowed),
        "external_service_access_allowed": bool(external_service_access_allowed),
        "unattended_allowed": bool(unattended_allowed),
        "one_time_or_reusable": one_time_or_reusable,
        "max_scope": dict(max_scope or {}),
        "expires_at": expires_at,
        "interrupt_conditions": list(interrupt_conditions),
        "receipt_requirements": list(receipt_requirements),
        "created_at": generated_at,
        "status": status,
        "raw_authority_granted_trusted": False,
    }
    errors = validate_authority_envelope(envelope)
    if errors:
        envelope["status"] = "invalid"
        envelope["validation_errors"] = errors
    return envelope


def authority_from_raw_text(text: str, *, generated_at: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": AUTHORITY_ENVELOPE_SCHEMA,
        "authority_envelope_created": False,
        "reason": "raw chat text is not trusted authority",
        "operator_text_hash": f"sha256:{hashlib.sha256(str(text or '').encode('utf-8')).hexdigest()}",
        "raw_authority_granted_trusted": False,
        "created_at": generated_at or utc_now(),
    }


def live_read_authority_from_text(text: str, *, generated_at: str | None = None) -> dict[str, Any]:
    lowered = str(text or "").lower()
    explicit_scope = all(term in lowered for term in ("annette", "capital hilton")) and "read-only" in lowered
    if not explicit_scope:
        return {
            "schema_version": AUTHORITY_ENVELOPE_SCHEMA,
            "authority_envelope_created": False,
            "reason": "live read authority requires explicit person/project/task scope",
            "operator_message": "Approve read-only lookup for which person, project, and task?",
            "created_at": generated_at or utc_now(),
        }
    envelope = create_authority_envelope(
        operator_id="operator:winship",
        device_id="device:pending_confirmed_device",
        confirmation_method="manual_review",
        confirmation_receipt_ref="pending_biometric_or_device_confirmation_receipt",
        requested_objective="Read-only email lookup for Annette at Capital Hilton payment follow-up.",
        capability_ids=["openclaw.read_only_email_lookup"],
        allowed_actions=["search_relevant_email_evidence", "read_relevant_email_evidence"],
        denied_actions=DEFAULT_DENIED_ACTIONS,
        live_data_access_allowed=True,
        production_action_allowed=False,
        external_service_access_allowed=False,
        unattended_allowed=False,
        max_scope={"person": "Annette", "project": "Capital Hilton", "task": "payment follow-up"},
        expires_at="pending_confirmation_short_expiry",
        status="draft_pending_confirmation",
        generated_at=generated_at,
    )
    envelope["authority_envelope_created"] = True
    return envelope


def validate_credential_handle(handle: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if handle.get("schema_version") != CREDENTIAL_HANDLE_SCHEMA:
        errors.append("schema_version must be CREDENTIAL_HANDLE_V0")
    for field in ("credential_handle_id", "credential_label", "credential_kind", "vault_provider", "vault_ref", "allowed_capability_ids", "allowed_actions", "denied_actions", "rotation_policy", "status"):
        if field not in handle:
            errors.append(f"missing required field: {field}")
    secret_fields = contains_raw_secret_field(handle)
    if secret_fields:
        errors.append(f"raw secret fields forbidden: {', '.join(secret_fields)}")
    if not handle.get("denied_actions"):
        errors.append("denied_actions required")
    return errors


def create_credential_handle(
    *,
    credential_handle_id: str,
    credential_label: str,
    credential_kind: str,
    vault_provider: str,
    vault_ref: str,
    allowed_capability_ids: Sequence[str],
    allowed_actions: Sequence[str],
    denied_actions: Sequence[str] = DEFAULT_DENIED_ACTIONS,
    rotation_policy: str = "rotate_outside_openclaw",
    last_verified_at: str | None = None,
    status: str = "configured_handle_only",
    generated_at: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    handle = {
        "schema_version": CREDENTIAL_HANDLE_SCHEMA,
        "credential_handle_id": credential_handle_id,
        "credential_label": credential_label,
        "credential_kind": credential_kind,
        "vault_provider": vault_provider,
        "vault_ref": vault_ref,
        "allowed_capability_ids": list(allowed_capability_ids),
        "allowed_actions": list(allowed_actions),
        "denied_actions": list(denied_actions),
        "rotation_policy": rotation_policy,
        "last_verified_at": last_verified_at,
        "status": status,
        "created_at": generated_at or utc_now(),
    }
    handle.update(extra)
    errors = validate_credential_handle(handle)
    if errors:
        handle["status"] = "invalid"
        handle["validation_errors"] = errors
    return handle


def google_workspace_broker_credential_handle(*, generated_at: str | None = None) -> dict[str, Any]:
    """Return the registered broad Google Workspace broker handle.

    This is metadata only. It records the private runtime reference and candidate
    capabilities, while keeping all action authority behind envelopes, leases,
    policy gates, and verifier receipts.
    """
    denied = _dedupe((*DEFAULT_DENIED_ACTIONS, *GOOGLE_WORKSPACE_BROKER_DENIED_ACTIONS))
    return create_credential_handle(
        credential_handle_id=GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID,
        credential_label="Google Workspace broker credential",
        credential_kind="google_workspace_oauth",
        vault_provider="private_runtime_ref",
        vault_ref="private_runtime_ref:redacted/google_workspace_broker/current",
        allowed_capability_ids=GOOGLE_WORKSPACE_BROKER_ALLOWED_CAPABILITY_IDS,
        allowed_actions=[
            "request_task_specific_authority_envelope",
            "request_scoped_credential_lease",
            "verify_policy_gate_receipts",
            "emit_redacted_receipt",
        ],
        denied_actions=denied,
        rotation_policy="preserve_existing_broker_material_rotate_outside_openclaw",
        status="registered_handle_only_policy_gated",
        generated_at=generated_at,
        credential_secret_material_included=False,
        credential_handle_existence_implies_use_authority=False,
        capability_use_constraints={
            GOOGLE_WORKSPACE_BROKER_CAPABILITY_ID: "task_specific_authority_envelope_and_credential_lease_required",
            READ_ONLY_EMAIL_LOOKUP_CAPABILITY_ID: "scoped_read_only_credential_lease_required",
            "openclaw.gmail_metadata_read": "query_scope_and_credential_lease_required",
            "openclaw.gmail_body_read": "stronger_body_read_authority_and_credential_lease_required",
            "openclaw.gmail_draft_generator": "draft_authority_required_send_denied",
            "openclaw.gmail_send_mail": "class_c_style_send_authority_required_disabled_by_default",
            "openclaw.contacts_readonly_lookup": "contact_read_authority_required_promotion_denied",
            "openclaw.calendar_event_manager": "calendar_action_split_authority_required",
        },
        live_execution_authorized=False,
    )


def google_workspace_broker_policy_gates(*, generated_at: str | None = None) -> list[dict[str, Any]]:
    common_unlock = ["authority_envelope", "credential_lease", "verifier_receipt"]
    return [
        create_policy_gate(
            gate_id="policy.google_workspace_broker_no_ambient_use",
            gate_label="Google Workspace broker no ambient use",
            blocked_actions=["google_workspace_broker_ambient_use", "ambient_mailbox_scan", "ambient_calendar_or_contact_access"],
            reason="The broad broker credential cannot be used without task-specific authority and a scoped lease.",
            unlock_requirements=common_unlock,
            allowed_alternatives=["Review scoped lease request", "Use pasted operator-provided evidence"],
            permanently_denied=False,
            authority_required=AUTHORITY_ENVELOPE_SCHEMA,
            verifier_required="google_workspace_broker_scope_verifier",
            receipt_required="google_workspace_broker_lease_receipt",
            operator_message="Review a scoped Google Workspace broker lease before any use.",
            details_message="OAuth scope presence is only credential capability, not action authority.",
            generated_at=generated_at,
        ),
        create_policy_gate(
            gate_id="policy.gmail_compose_scope_does_not_imply_send",
            gate_label="Gmail compose scope does not imply send",
            blocked_actions=["send_email", "gmail_send_without_send_authority"],
            reason="OAuth compose scope is insufficient for send authority.",
            unlock_requirements=common_unlock,
            allowed_alternatives=["Create a draft under draft authority", "Request Class C-style send authority"],
            permanently_denied=False,
            authority_required=AUTHORITY_ENVELOPE_SCHEMA,
            verifier_required="gmail_compose_send_split_verifier",
            receipt_required="gmail_send_authority_receipt",
            operator_message="Compose scope is not send permission.",
            details_message="Send remains separated from compose/draft authority and disabled by default.",
            generated_at=generated_at,
        ),
        create_policy_gate(
            gate_id="policy.gmail_draft_does_not_imply_send",
            gate_label="Gmail draft does not imply send",
            blocked_actions=["send_email", "gmail_send_without_send_authority"],
            reason="Draft creation authority does not authorize dispatch.",
            unlock_requirements=common_unlock,
            allowed_alternatives=["Leave draft for review", "Request separate send authority"],
            permanently_denied=False,
            authority_required=AUTHORITY_ENVELOPE_SCHEMA,
            verifier_required="gmail_draft_send_split_verifier",
            receipt_required="gmail_draft_or_send_split_receipt",
            operator_message="Draft authority stops at draft creation.",
            details_message="Sending requires a separate high-authority envelope and receipt.",
            generated_at=generated_at,
        ),
        create_policy_gate(
            gate_id="policy.contacts_read_does_not_imply_memory_promotion",
            gate_label="Contacts read does not imply memory promotion",
            blocked_actions=["promote_contact_memory", "contact_memory_promotion", "mutate_contacts"],
            reason="Contact read authority cannot mutate contacts or promote memory.",
            unlock_requirements=common_unlock,
            allowed_alternatives=["Return redacted contact lookup receipt", "Request separate memory promotion approval"],
            permanently_denied=False,
            authority_required=AUTHORITY_ENVELOPE_SCHEMA,
            verifier_required="contacts_read_memory_promotion_split_verifier",
            receipt_required="contacts_readonly_receipt",
            operator_message="Contacts read is not contact memory promotion.",
            details_message="Contact mutation and memory promotion remain denied without separate explicit authority.",
            generated_at=generated_at,
        ),
        create_policy_gate(
            gate_id="policy.calendar_events_scope_requires_action_split",
            gate_label="Calendar events scope requires action split",
            blocked_actions=[
                "calendar_write_without_action_authority",
                "calendar_delete_without_action_authority",
                "calendar_mutation_without_calendar_authority",
            ],
            reason="Calendar read, write, and delete authority must be split by action.",
            unlock_requirements=common_unlock,
            allowed_alternatives=["Request calendar read-only authority", "Request explicit calendar mutation authority"],
            permanently_denied=False,
            authority_required=AUTHORITY_ENVELOPE_SCHEMA,
            verifier_required="calendar_action_split_verifier",
            receipt_required="calendar_action_split_receipt",
            operator_message="Calendar actions need separate read/write/delete authority.",
            details_message="Calendar mutation is denied unless the requested action is explicitly authorized.",
            generated_at=generated_at,
        ),
        create_policy_gate(
            gate_id="policy.gmail_readonly_lookup_requires_scoped_lease",
            gate_label="Gmail read-only lookup requires scoped lease",
            blocked_actions=["read_only_email_lookup_without_scoped_lease", "ambient_mailbox_scan"],
            reason="Read-only lookup may use the broker only through an adapter-enforced scoped lease.",
            unlock_requirements=common_unlock,
            allowed_alternatives=["Review scoped read-only Gmail lookup lease", "Use a future dedicated read-only credential"],
            permanently_denied=False,
            authority_required=AUTHORITY_ENVELOPE_SCHEMA,
            verifier_required="google_workspace_broker_readonly_lease_verifier",
            receipt_required="gmail_readonly_lookup_lease_receipt",
            operator_message="Review the scoped read-only Gmail lease before lookup.",
            details_message="The lease must name objective scope, expiry, receipts, and denied actions.",
            generated_at=generated_at,
        ),
    ]


def create_google_workspace_broker_readonly_lease(
    *,
    credential_handle: Mapping[str, Any],
    authority_envelope: Mapping[str, Any],
    objective_scope: Mapping[str, Any],
    allow_bounded_body_read: bool = False,
    expires_at: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    allowed_use = list(GOOGLE_WORKSPACE_BROKER_READONLY_ALLOWED_USE)
    if allow_bounded_body_read:
        allowed_use.append("bounded_gmail_body_read")
    lease = create_credential_lease(
        credential_handle=credential_handle,
        authority_envelope=authority_envelope,
        capability_id=READ_ONLY_EMAIL_LOOKUP_CAPABILITY_ID,
        allowed_use=_dedupe(allowed_use),
        denied_use=GOOGLE_WORKSPACE_BROKER_READONLY_DENIED_USE,
        adapter_ref="adapter:google_workspace_broker.readonly_lease_verifier",
        expires_at=expires_at,
        receipt_requirements=[
            "credential_use_receipt",
            "authority_envelope_ref",
            "lease_verifier_receipt",
            "redacted_email_lookup_summary",
        ],
        generated_at=generated_at,
    )
    if lease.get("lease_created") is True:
        lease.update(
            {
                "objective_scope": dict(objective_scope),
                "task_scope": dict(objective_scope),
                "allowed_scope": "scoped Gmail search/read only for named objective",
                "lease_verifier_ref": "google_workspace_broker_readonly_lease_verifier",
                "live_execution_authorized": False,
                "no_execution_performed": True,
            }
        )
    return lease


def verify_google_workspace_broker_readonly_lease(
    lease: Mapping[str, Any],
    *,
    credential_handle: Mapping[str, Any] | None,
    authority_envelope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    errors: list[str] = []
    if not lease or lease.get("schema_version") != CREDENTIAL_LEASE_SCHEMA or lease.get("lease_created") is not True:
        errors.append("valid_credential_lease_required")
    if not credential_handle or credential_handle.get("credential_handle_id") != GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID:
        errors.append("broker_credential_handle_required")
    if credential_handle and credential_handle.get("credential_handle_existence_implies_use_authority") is not False:
        errors.append("handle_must_not_imply_use_authority")
    if not authority_envelope:
        errors.append("authority_envelope_required")
    elif authority_envelope.get("schema_version") != AUTHORITY_ENVELOPE_SCHEMA:
        errors.append("authority_envelope_required")
    else:
        if lease.get("authority_envelope_id") != authority_envelope.get("envelope_id"):
            errors.append("authority_envelope_id_mismatch")
        if READ_ONLY_EMAIL_LOOKUP_CAPABILITY_ID not in (authority_envelope.get("capability_ids") or []):
            errors.append("read_only_lookup_authority_required")
        if GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID not in (authority_envelope.get("credential_handles_allowed") or []):
            errors.append("broker_credential_handle_not_allowed_by_envelope")
        if not authority_envelope.get("receipt_requirements"):
            errors.append("authority_receipt_requirements_required")
    if lease.get("credential_handle_id") != GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID:
        errors.append("credential_handle_id_mismatch")
    if lease.get("capability_id") != READ_ONLY_EMAIL_LOOKUP_CAPABILITY_ID:
        errors.append("capability_id_must_be_read_only_email_lookup")
    if not lease.get("expires_at"):
        errors.append("expiry_required")
    if not lease.get("receipt_requirements"):
        errors.append("receipt_requirements_required")
    if not lease.get("objective_scope") and not lease.get("task_scope"):
        errors.append("task_lane_objective_scope_required")

    allowed_use = set(lease.get("allowed_use") or [])
    denied_use = set(lease.get("denied_use") or [])
    required_allowed = {"scoped_gmail_search", "scoped_gmail_metadata_read", "receipt_creation", "redacted_summary"}
    missing_allowed = sorted(required_allowed - allowed_use)
    if missing_allowed:
        errors.append(f"allowed_use_missing:{','.join(missing_allowed)}")
    forbidden_allowed = sorted(allowed_use & set(GOOGLE_WORKSPACE_BROKER_READONLY_DENIED_USE))
    if forbidden_allowed:
        errors.append(f"forbidden_allowed_use:{','.join(forbidden_allowed)}")
    missing_denied = sorted(set(GOOGLE_WORKSPACE_BROKER_READONLY_DENIED_USE) - denied_use)
    if missing_denied:
        errors.append(f"denied_use_missing:{','.join(missing_denied)}")

    return {
        "schema_version": "GOOGLE_WORKSPACE_BROKER_READONLY_LEASE_VERDICT_V0",
        "valid": not errors,
        "validation_errors": errors,
        "verified_credential_handle_id": lease.get("credential_handle_id"),
        "verified_capability_id": lease.get("capability_id"),
        "allowed_use": sorted(allowed_use),
        "denied_use": sorted(denied_use),
        "live_execution_authorized": False,
        "no_execution_performed": True,
    }


def seed_google_workspace_broker_credential(
    *,
    sqlite_path: Path = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    handle = google_workspace_broker_credential_handle(generated_at=generated_at)
    gate_refs = []
    persist_object(handle, sqlite_path=sqlite_path, reason="seed_google_workspace_broker_credential_handle")
    for gate in google_workspace_broker_policy_gates(generated_at=generated_at):
        persist_object(gate, sqlite_path=sqlite_path, reason="seed_google_workspace_broker_policy_gate")
        gate_refs.append(gate["gate_id"])
    return {
        "seeded": True,
        "credential_handle_id": handle["credential_handle_id"],
        "policy_gate_ids": gate_refs,
        "secret_material_included": False,
        "created_at": generated_at or utc_now(),
    }


def create_credential_lease(
    *,
    credential_handle: Mapping[str, Any] | None,
    authority_envelope: Mapping[str, Any] | None,
    capability_id: str,
    allowed_use: Sequence[str],
    denied_use: Sequence[str] = DEFAULT_DENIED_ACTIONS,
    adapter_ref: str,
    expires_at: str,
    receipt_requirements: Sequence[str] = ("credential_use_receipt", "authority_envelope_ref"),
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    if not credential_handle or credential_handle.get("schema_version") != CREDENTIAL_HANDLE_SCHEMA or credential_handle.get("status") == "invalid":
        return {"schema_version": CREDENTIAL_LEASE_SCHEMA, "lease_created": False, "reason": "valid credential handle required", "status": "blocked"}
    if not authority_envelope or authority_envelope.get("schema_version") != AUTHORITY_ENVELOPE_SCHEMA or authority_envelope.get("status") == "expired":
        return {"schema_version": CREDENTIAL_LEASE_SCHEMA, "lease_created": False, "reason": "valid authority envelope required", "status": "blocked"}
    if not denied_use:
        return {"schema_version": CREDENTIAL_LEASE_SCHEMA, "lease_created": False, "reason": "denied_use required", "status": "blocked"}
    lease = {
        "schema_version": CREDENTIAL_LEASE_SCHEMA,
        "lease_id": f"credential_lease:{_short_hash(credential_handle['credential_handle_id'], authority_envelope['envelope_id'], capability_id, generated_at)}",
        "credential_handle_id": credential_handle["credential_handle_id"],
        "authority_envelope_id": authority_envelope["envelope_id"],
        "capability_id": capability_id,
        "allowed_use": list(allowed_use),
        "denied_use": list(denied_use),
        "issued_at": generated_at,
        "expires_at": expires_at,
        "adapter_ref": adapter_ref,
        "receipt_requirements": list(receipt_requirements),
        "status": "draft_pending_adapter_receipt",
        "lease_created": True,
    }
    return lease


def create_unattended_run_envelope(
    *,
    schedule_ref: str,
    requested_objective: str,
    capability_ids: Sequence[str],
    authority_envelope_refs: Sequence[str] = (),
    allowed_actions: Sequence[str] = (),
    denied_actions: Sequence[str] = DEFAULT_DENIED_ACTIONS,
    credential_handles_allowed: Sequence[str] = (),
    live_data_access_allowed: bool = False,
    production_action_allowed: bool = False,
    external_service_access_allowed: bool = False,
    max_runtime: str = "10m",
    max_retries: int = 0,
    run_window: Mapping[str, Any] | None = None,
    expires_at: str = "pending_operator_expiry",
    interrupt_conditions: Sequence[str] = ("verifier_fails", "stale_proof", "credential_challenge", "mfa_required", "scope_expands"),
    notification_policy: Mapping[str, Any] | None = None,
    receipt_requirements: Sequence[str] = ("run_start_receipt", "run_stop_receipt", "verifier_receipt"),
    status: str = "draft_pending_confirmation",
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    return {
        "schema_version": UNATTENDED_RUN_ENVELOPE_SCHEMA,
        "run_envelope_id": f"unattended_run_envelope:{_short_hash(schedule_ref, requested_objective, capability_ids, generated_at)}",
        "schedule_ref": schedule_ref,
        "requested_objective": requested_objective,
        "capability_ids": list(capability_ids),
        "authority_envelope_refs": list(authority_envelope_refs),
        "allowed_actions": list(allowed_actions),
        "denied_actions": list(denied_actions),
        "credential_handles_allowed": list(credential_handles_allowed),
        "live_data_access_allowed": bool(live_data_access_allowed),
        "production_action_allowed": bool(production_action_allowed),
        "external_service_access_allowed": bool(external_service_access_allowed),
        "max_runtime": max_runtime,
        "max_retries": int(max_retries),
        "run_window": dict(run_window or {"kind": "operator_defined_window_required"}),
        "expires_at": expires_at,
        "interrupt_conditions": list(interrupt_conditions),
        "notification_policy": dict(notification_policy or {"notify_operator_on": ["start", "interrupt", "completion"]}),
        "receipt_requirements": list(receipt_requirements),
        "status": status,
        "created_at": generated_at,
    }


def create_policy_gate(
    *,
    gate_id: str,
    gate_label: str,
    blocked_actions: Sequence[str],
    reason: str,
    unlock_requirements: Sequence[str],
    allowed_alternatives: Sequence[str],
    permanently_denied: bool,
    authority_required: str,
    verifier_required: str,
    receipt_required: str,
    operator_message: str,
    details_message: str,
    status: str = "active",
    generated_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": POLICY_GATE_SCHEMA,
        "gate_id": gate_id,
        "gate_label": gate_label,
        "blocked_actions": list(blocked_actions),
        "reason": reason,
        "unlock_requirements": list(unlock_requirements),
        "allowed_alternatives": list(allowed_alternatives),
        "permanently_denied": bool(permanently_denied),
        "authority_required": authority_required,
        "verifier_required": verifier_required,
        "receipt_required": receipt_required,
        "operator_message": operator_message,
        "details_message": details_message,
        "status": status,
        "created_at": generated_at or utc_now(),
    }


def can_unlock_policy_gate(gate: Mapping[str, Any], envelope: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if gate.get("permanently_denied") is True:
        return {"unlock_allowed": False, "reason": "permanently_denied"}
    if not envelope:
        return {"unlock_allowed": False, "reason": "authority_envelope_required"}
    return {"unlock_allowed": True, "reason": "authority_envelope_present_verifier_and_receipt_still_required"}


def persist_object(payload: Mapping[str, Any], *, sqlite_path: Path = DEFAULT_SQLITE_PATH, event_kind: str = "created", reason: str = "stored") -> dict[str, Any]:
    schema = str(payload.get("schema_version") or "")
    with connect(sqlite_path) as conn:
        if schema == AUTHORITY_ENVELOPE_SCHEMA and payload.get("envelope_id"):
            conn.execute(
                """
                INSERT OR REPLACE INTO authority_envelopes
                  (envelope_id, operator_id, device_id, confirmation_method, confirmation_receipt_ref,
                   requested_objective, capability_ids, allowed_actions, denied_actions, credential_handles_allowed,
                   live_data_access_allowed, production_action_allowed, external_service_access_allowed, unattended_allowed,
                   one_time_or_reusable, max_scope, expires_at, interrupt_conditions, receipt_requirements, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["envelope_id"], payload["operator_id"], payload["device_id"], payload["confirmation_method"],
                    payload["confirmation_receipt_ref"], payload["requested_objective"], _json(payload["capability_ids"]),
                    _json(payload["allowed_actions"]), _json(payload["denied_actions"]), _json(payload["credential_handles_allowed"]),
                    1 if payload.get("live_data_access_allowed") is True else 0,
                    1 if payload.get("production_action_allowed") is True else 0,
                    1 if payload.get("external_service_access_allowed") is True else 0,
                    1 if payload.get("unattended_allowed") is True else 0,
                    payload["one_time_or_reusable"], _json(payload["max_scope"]), payload["expires_at"],
                    _json(payload["interrupt_conditions"]), _json(payload["receipt_requirements"]), payload["created_at"], payload["status"],
                ),
            )
            object_id = str(payload["envelope_id"])
        elif schema == CREDENTIAL_HANDLE_SCHEMA and payload.get("credential_handle_id"):
            if contains_raw_secret_field(payload):
                raise ValueError("raw secret fields cannot be persisted")
            conn.execute(
                """
                INSERT OR REPLACE INTO credential_handles
                  (credential_handle_id, credential_label, credential_kind, vault_provider, vault_ref,
                   allowed_capability_ids, allowed_actions, denied_actions, rotation_policy, last_verified_at, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["credential_handle_id"], payload["credential_label"], payload["credential_kind"], payload["vault_provider"],
                    payload["vault_ref"], _json(payload["allowed_capability_ids"]), _json(payload["allowed_actions"]),
                    _json(payload["denied_actions"]), payload["rotation_policy"], payload.get("last_verified_at"), payload["status"], payload["created_at"],
                ),
            )
            object_id = str(payload["credential_handle_id"])
        elif schema == CREDENTIAL_LEASE_SCHEMA and payload.get("lease_id"):
            conn.execute(
                """
                INSERT OR REPLACE INTO credential_leases
                  (lease_id, credential_handle_id, authority_envelope_id, capability_id, allowed_use, denied_use,
                   issued_at, expires_at, adapter_ref, receipt_requirements, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["lease_id"], payload["credential_handle_id"], payload["authority_envelope_id"], payload["capability_id"],
                    _json(payload["allowed_use"]), _json(payload["denied_use"]), payload["issued_at"], payload["expires_at"],
                    payload["adapter_ref"], _json(payload["receipt_requirements"]), payload["status"],
                ),
            )
            object_id = str(payload["lease_id"])
        elif schema == UNATTENDED_RUN_ENVELOPE_SCHEMA and payload.get("run_envelope_id"):
            conn.execute(
                """
                INSERT OR REPLACE INTO unattended_run_envelopes
                  (run_envelope_id, schedule_ref, requested_objective, capability_ids, authority_envelope_refs,
                   allowed_actions, denied_actions, credential_handles_allowed, live_data_access_allowed,
                   production_action_allowed, external_service_access_allowed, max_runtime, max_retries, run_window,
                   expires_at, interrupt_conditions, notification_policy, receipt_requirements, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["run_envelope_id"], payload["schedule_ref"], payload["requested_objective"], _json(payload["capability_ids"]),
                    _json(payload["authority_envelope_refs"]), _json(payload["allowed_actions"]), _json(payload["denied_actions"]),
                    _json(payload["credential_handles_allowed"]), 1 if payload.get("live_data_access_allowed") is True else 0,
                    1 if payload.get("production_action_allowed") is True else 0,
                    1 if payload.get("external_service_access_allowed") is True else 0,
                    payload["max_runtime"], payload["max_retries"], _json(payload["run_window"]), payload["expires_at"],
                    _json(payload["interrupt_conditions"]), _json(payload["notification_policy"]), _json(payload["receipt_requirements"]),
                    payload["status"], payload["created_at"],
                ),
            )
            object_id = str(payload["run_envelope_id"])
        elif schema == POLICY_GATE_SCHEMA and payload.get("gate_id"):
            conn.execute(
                """
                INSERT OR REPLACE INTO policy_gates
                  (gate_id, gate_label, blocked_actions, reason, unlock_requirements, allowed_alternatives,
                   permanently_denied, authority_required, verifier_required, receipt_required, operator_message,
                   details_message, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["gate_id"], payload["gate_label"], _json(payload["blocked_actions"]), payload["reason"],
                    _json(payload["unlock_requirements"]), _json(payload["allowed_alternatives"]), 1 if payload.get("permanently_denied") is True else 0,
                    payload["authority_required"], payload["verifier_required"], payload["receipt_required"], payload["operator_message"],
                    payload["details_message"], payload["status"], payload["created_at"],
                ),
            )
            object_id = str(payload["gate_id"])
        else:
            raise ValueError(f"unsupported payload for persistence: {schema}")
        event_id = f"authority_event:{_short_hash(schema, object_id, event_kind, reason, payload.get('created_at') or utc_now())}"
        conn.execute(
            "INSERT OR REPLACE INTO authority_events VALUES (?, ?, ?, ?, ?, ?, ?)",
            (event_id, event_kind, schema, object_id, reason, _json(dict(payload)), payload.get("created_at") or utc_now()),
        )
    return {"stored": True, "object_schema_version": schema, "object_id": object_id, "event_kind": event_kind}


def list_table(table: str, *, sqlite_path: Path = DEFAULT_SQLITE_PATH) -> list[dict[str, Any]]:
    allowed = {"authority_envelopes", "credential_handles", "credential_leases", "unattended_run_envelopes", "policy_gates", "authority_events"}
    if table not in allowed:
        raise ValueError(f"unsupported table: {table}")
    with connect(sqlite_path) as conn:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        return [_row_dict(row) for row in rows]

"""Accounts Receivable counterparty/contact operations substrate V0.

This module records AR account/contact policy context and produces deterministic
plans. It does not call Gmail, Apple Mail, Calendar, Contacts, Coupa, ledgers,
models, or any live external surface.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_SQLITE_PATH = Path("generated/system_knowledge/ar_counterparty_contact_operations.sqlite")
DEFAULT_CAPITAL_HILTON_METADATA_RECEIPT = Path(
    "/tmp/openclaw-mission-control/annette_capital_hilton_lookup_2026_06_10_async_ttl_v0/lookup_receipt.json"
)

AR_COUNTERPARTY_ACCOUNT_SCHEMA = "AR_COUNTERPARTY_ACCOUNT_V0"
AR_CONTACT_PROFILE_SCHEMA = "AR_CONTACT_PROFILE_V0"
AR_COMMUNICATION_POLICY_SCHEMA = "AR_COMMUNICATION_POLICY_V0"
AR_EMAIL_WATCH_POLICY_SCHEMA = "AR_EMAIL_WATCH_POLICY_V0"
AR_INVOICE_SEND_POLICY_SCHEMA = "AR_INVOICE_SEND_POLICY_V0"
AR_CAPABILITY_PACKAGE_PLAN_SCHEMA = "AR_CAPABILITY_PACKAGE_PLAN_V0"
AR_COUNTERPARTY_ACTION_PLAN_SCHEMA = "AR_COUNTERPARTY_ACTION_PLAN_V0"
AR_TEXT_ONLY_DRAFT_SCHEMA = "AR_TEXT_ONLY_DRAFT_PREVIEW_V0"

GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID = "credential.google_workspace_broker.current"

DENIED_ACTIONS = (
    "send_without_exact_authority",
    "body_read_without_authority",
    "invoice_send_without_artifact",
    "broad_mailbox_scan",
    "gmail_send_without_authority",
    "gmail_draft_creation_without_authority",
    "gmail_body_read_without_authority",
    "delete_archive_mark_read",
    "calendar_access_without_authority",
    "contacts_access_without_authority",
    "contact_mutation",
    "contact_memory_promotion_outside_ar_registry",
    "calendar_mutation",
    "paid_marking",
    "ledger_mutation",
    "coupa_action",
    "trust_raw_authority_granted",
)

MACHINE_PROOF = {
    "gmail_lookup_performed": False,
    "gmail_body_read_performed": False,
    "gmail_draft_created": False,
    "email_send_performed": False,
    "email_watch_started": False,
    "calendar_api_called": False,
    "contacts_api_called": False,
    "paid_marking_allowed": False,
    "ledger_mutation_allowed": False,
    "coupa_access_allowed": False,
    "token_exposed": False,
    "secret_exposed": False,
    "raw_authority_granted_trusted": False,
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
        value = stable_json(part) if isinstance(part, (dict, list, tuple)) else str(part)
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:length]


def _slug(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", str(value or "").lower())).strip("_")


def _dedupe(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value)
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _connect(sqlite_path: Path | str = DEFAULT_SQLITE_PATH) -> sqlite3.Connection:
    path = _rooted(sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS ar_counterparty_accounts (
          account_id TEXT PRIMARY KEY,
          account_label TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          account_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ar_contact_profiles (
          contact_id TEXT PRIMARY KEY,
          account_id TEXT NOT NULL,
          display_name TEXT NOT NULL,
          relationship_status_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          contact_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ar_communication_policies (
          policy_id TEXT PRIMARY KEY,
          account_id TEXT NOT NULL,
          contact_id TEXT NOT NULL,
          communication_context TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          policy_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ar_email_watch_policies (
          watch_policy_id TEXT PRIMARY KEY,
          account_id TEXT NOT NULL,
          contact_id TEXT NOT NULL,
          status TEXT NOT NULL,
          policy_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ar_invoice_send_policies (
          policy_id TEXT PRIMARY KEY,
          account_id TEXT NOT NULL,
          contact_id TEXT NOT NULL,
          status TEXT NOT NULL,
          policy_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ar_contact_events (
          event_id TEXT PRIMARY KEY,
          account_id TEXT NOT NULL,
          contact_id TEXT NOT NULL,
          event_type TEXT NOT NULL,
          source_ref TEXT NOT NULL,
          created_at TEXT NOT NULL,
          event_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ar_evidence_registry (
          evidence_id TEXT PRIMARY KEY,
          account_id TEXT NOT NULL REFERENCES ar_counterparty_accounts(account_id),
          source_system TEXT NOT NULL,
          source_event TEXT NOT NULL,
          source_locator TEXT NOT NULL,
          evidence_hash TEXT NOT NULL,
          governed_artifact_path TEXT NOT NULL,
          mime_type TEXT,
          byte_size INTEGER,
          world TEXT NOT NULL,
          privacy_classification TEXT,
          governance_status TEXT NOT NULL CHECK(governance_status IN ('active', 'quarantined', 'revoked')),
          processing_status TEXT NOT NULL CHECK(processing_status IN ('pending', 'extracted', 'failed')),
          availability TEXT NOT NULL CHECK(availability IN ('available', 'missing')),
          first_seen_timestamp TEXT NOT NULL,
          source_modified_timestamp TEXT,
          ingestion_timestamp TEXT NOT NULL,
          extractor_version TEXT NOT NULL,
          schema_version TEXT NOT NULL,
          supersedes_evidence_id TEXT REFERENCES ar_evidence_registry(evidence_id),
          source_reference TEXT NOT NULL,
          UNIQUE(source_system, source_event, source_locator, evidence_hash)
        );

        CREATE TABLE IF NOT EXISTS ar_materialization_runs (
          run_id TEXT PRIMARY KEY,
          generator_id TEXT NOT NULL,
          generator_version TEXT NOT NULL,
          schema_version TEXT NOT NULL,
          run_start_timestamp TEXT NOT NULL,
          run_completion_timestamp TEXT,
          freshness_cutoff TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('preparing', 'published', 'failed', 'aborted')),
          error_code TEXT,
          error_details TEXT,
          stable_payload_hash TEXT,
          published_artifact_path TEXT,
          published_artifact_hash TEXT
        );

        CREATE TABLE IF NOT EXISTS ar_materialization_run_evidence (
          run_id TEXT NOT NULL REFERENCES ar_materialization_runs(run_id),
          evidence_id TEXT NOT NULL REFERENCES ar_evidence_registry(evidence_id),
          inclusion_status TEXT NOT NULL CHECK(inclusion_status IN ('used', 'excluded')),
          PRIMARY KEY (run_id, evidence_id)
        );

        CREATE TABLE IF NOT EXISTS ar_published_read_models (
          read_model_domain TEXT PRIMARY KEY,
          current_run_id TEXT NOT NULL REFERENCES ar_materialization_runs(run_id),
          updated_at TEXT NOT NULL
        );

        CREATE TRIGGER IF NOT EXISTS enforce_published_read_model
        BEFORE INSERT ON ar_published_read_models
        FOR EACH ROW
        BEGIN
            SELECT RAISE(ABORT, 'Cannot publish a run that is not in published status')
            WHERE (SELECT status FROM ar_materialization_runs WHERE run_id = NEW.current_run_id) != 'published';
        END;

        CREATE TRIGGER IF NOT EXISTS enforce_published_read_model_update
        BEFORE UPDATE ON ar_published_read_models
        FOR EACH ROW
        BEGIN
            SELECT RAISE(ABORT, 'Cannot publish a run that is not in published status')
            WHERE (SELECT status FROM ar_materialization_runs WHERE run_id = NEW.current_run_id) != 'published';
        END;

        CREATE TRIGGER IF NOT EXISTS enforce_run_publication_completeness
        BEFORE UPDATE ON ar_materialization_runs
        FOR EACH ROW
        WHEN NEW.status = 'published'
        BEGIN
            SELECT RAISE(ABORT, 'Cannot mark run published: run_completion_timestamp is required')
            WHERE NEW.run_completion_timestamp IS NULL;
            SELECT RAISE(ABORT, 'Cannot mark run published: stable_payload_hash is required')
            WHERE NEW.stable_payload_hash IS NULL;
            SELECT RAISE(ABORT, 'Cannot mark run published: published_artifact_path is required')
            WHERE NEW.published_artifact_path IS NULL;
            SELECT RAISE(ABORT, 'Cannot mark run published: published_artifact_hash is required')
            WHERE NEW.published_artifact_hash IS NULL;
        END;
        """
    )



def governed_artifact_path(
    relative_path: str,
    governed_root: Path | str,
) -> Path:
    """Validate and return an absolute path inside the governed artifact root.

    Policy (in evaluation order):
    1. **Absolute-path injection** — ``relative_path`` must not be absolute.
    2. **Parent traversal** — ``relative_path`` must not contain ``..`` segments.
    3. **Path containment** — the resolved path must start with the resolved root.
    4. **Symlink escape** — uses ``Path.resolve()`` on the joined path; if the
       real path falls outside the root (via symlink), the call is rejected.

    Returns the fully resolved ``Path`` inside the governed root.
    Raises ``ValueError`` for any policy violation.  Never raises ``OSError``
    for a missing path — the path is validated, not stat-checked.
    """
    if not relative_path or relative_path.strip() == "":
        raise ValueError("governed_artifact_path: relative_path must not be empty")

    # Rule 1 — reject absolute paths
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise ValueError(
            f"governed_artifact_path: absolute path injection rejected: {relative_path!r}"
        )

    # Rule 2 — reject traversal components before joining (pre-check)
    for part in candidate.parts:
        if part == "..":
            raise ValueError(
                f"governed_artifact_path: parent-traversal rejected: {relative_path!r}"
            )

    root = Path(governed_root).resolve()
    # Rule 3 & 4 — resolve joined path and verify containment (defeats symlinks)
    # We use strict=False so the path need not exist yet (evidence not yet written).
    joined = (root / candidate).resolve()
    try:
        joined.relative_to(root)
    except ValueError:
        raise ValueError(
            f"governed_artifact_path: path escapes governed root "
            f"({joined!r} not under {root!r}): {relative_path!r}"
        )

    return joined


def _read_json(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _first_metadata_evidence(receipt: Mapping[str, Any]) -> dict[str, Any] | None:
    if not receipt or int(receipt.get("matching_message_count") or 0) < 1:
        return None
    evidence = receipt.get("metadata_evidence")
    if isinstance(evidence, list) and evidence and isinstance(evidence[0], Mapping):
        return dict(evidence[0])
    return None


def _event(
    *,
    account_id: str,
    contact_id: str,
    event_type: str,
    source_ref: str,
    generated_at: str,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "event_id": "ar_contact_event:" + _short_hash(account_id, contact_id, event_type, source_ref, generated_at),
        "account_id": account_id,
        "contact_id": contact_id,
        "event_type": event_type,
        "source_ref": source_ref,
        "created_at": generated_at,
        "no_live_action_performed": True,
    }
    payload.update(dict(extra or {}))
    return payload


def _store_event(conn: sqlite3.Connection, event: Mapping[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO ar_contact_events
          (event_id, account_id, contact_id, event_type, source_ref, created_at, event_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event["event_id"],
            event["account_id"],
            event["contact_id"],
            event["event_type"],
            event["source_ref"],
            event["created_at"],
            stable_json(event),
        ),
    )


def _account_record(
    *,
    account_id: str,
    account_label: str,
    aliases: Sequence[str],
    payment_context_summary: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": AR_COUNTERPARTY_ACCOUNT_SCHEMA,
        "account_id": account_id,
        "account_label": account_label,
        "aliases": _dedupe([account_label, *aliases]),
        "lane_context_refs": ["finance", account_id],
        "payment_context_summary": payment_context_summary,
        "status": "active",
        "created_at": generated_at,
        "updated_at": generated_at,
    }


def _contact_record(
    *,
    account_id: str,
    display_name: str,
    email_address: str,
    role_labels: Sequence[str],
    relationship_status: Sequence[str],
    source_refs: Sequence[str],
    confidence: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": AR_CONTACT_PROFILE_SCHEMA,
        "contact_id": f"contact:{account_id}:{_slug(display_name)}",
        "account_id": account_id,
        "display_name": display_name,
        "email_addresses": [email_address],
        "role_labels": _dedupe(role_labels),
        "relationship_status": _dedupe(relationship_status),
        "source_refs": _dedupe(source_refs),
        "confidence": confidence,
        "allowed_use_contexts": [
            "payment_followup",
            "invoice_delivery",
            "metadata_watch",
            "body_read_authority_request",
            "text_only_draft_review",
        ],
        "denied_use_contexts": [
            "send_without_exact_authority",
            "memory_promotion_outside_ar_registry",
            "broad_mailbox_scan",
            "body_read_without_authority",
            "ledger_or_paid_mutation",
        ],
        "created_at": generated_at,
        "updated_at": generated_at,
    }


def _communication_policy(
    *,
    account_id: str,
    contact_id: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": AR_COMMUNICATION_POLICY_SCHEMA,
        "policy_id": f"ar_communication_policy:{account_id}:{_slug(contact_id)}:payment_followup",
        "account_id": account_id,
        "contact_id": contact_id,
        "communication_context": "payment_followup",
        "preferred_channel": "email",
        "allowed_actions": [
            "resolve_contact_profile",
            "request_scoped_metadata_lookup",
            "request_single_message_body_read_authority",
            "create_text_only_draft_for_review",
            "create_receipt",
        ],
        "denied_actions": list(DENIED_ACTIONS),
        "default_next_step": "request_scoped_metadata_lookup_or_body_read_authority",
        "required_authority": [
            "scoped_metadata_lookup_authority",
            "single_message_body_read_authority_when_metadata_exists",
            "exact_send_authority_before_send",
        ],
        "required_proof": [
            "metadata_lookup_receipt",
            "single_message_body_read_receipt_if_needed",
            "operator_review_receipt",
        ],
        "receipt_requirements": ["redacted_summary", "capability_id", "authority_envelope_id", "credential_lease_id"],
        "review_before_send": True,
        "unattended_allowed": False,
        "created_at": generated_at,
        "updated_at": generated_at,
    }


def _watch_policy(
    *,
    account_id: str,
    contact: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": AR_EMAIL_WATCH_POLICY_SCHEMA,
        "watch_policy_id": f"ar_email_watch_policy:{account_id}:{_slug(str(contact['contact_id']))}",
        "account_id": account_id,
        "contact_id": contact["contact_id"],
        "mailbox_surface": "google_workspace_broker",
        "query_scope": {
            "account_id": account_id,
            "contact_id": contact["contact_id"],
            "email_addresses": list(contact.get("email_addresses") or []),
            "communication_context": "payment_followup",
        },
        "date_window_policy": "bounded_window_required_per_watch_or_unattended_envelope",
        "allowed_metadata_fields": ["date", "sender", "subject", "message_id_hash", "thread_id_hash"],
        "body_read_policy": "body_read_requires_separate_authority",
        "denied_actions": list(DENIED_ACTIONS),
        "authority_required": "scoped_metadata_watch_authority",
        "unattended_envelope_required": True,
        "receipt_requirements": ["watch_scope", "metadata_only", "no_body_read", "denied_actions_confirmed"],
        "status": "available_as_policy_only_no_live_watch",
        "created_at": generated_at,
        "updated_at": generated_at,
    }


def _invoice_send_policy(
    *,
    account_id: str,
    contact_id: str,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": AR_INVOICE_SEND_POLICY_SCHEMA,
        "policy_id": f"ar_invoice_send_policy:{account_id}:{_slug(contact_id)}",
        "account_id": account_id,
        "contact_id": contact_id,
        "invoice_artifact_requirements": [
            "invoice_artifact_ref",
            "artifact_hash",
            "recipient",
            "subject",
            "body",
            "payload_hash",
        ],
        "allowed_send_conditions": [
            "invoice_artifact_present",
            "recipient_matches_contact_policy",
            "exact_payload_authority_active",
            "operator_review_complete",
            "send_receipt_required",
        ],
        "denied_send_conditions": [
            "missing_invoice_artifact",
            "missing_exact_send_authority",
            "payload_changed_after_authority",
            "recipient_changed_after_authority",
            "body_changed_after_authority",
            "authority_expired",
        ],
        "review_required": True,
        "exact_payload_required": True,
        "authority_required": "exact_invoice_send_authority",
        "receipt_requirements": ["payload_hash", "authority_envelope_id", "credential_lease_id", "send_or_blocker_receipt"],
        "status": "send_locked_by_default",
        "created_at": generated_at,
        "updated_at": generated_at,
    }


def _store_seed(
    *,
    sqlite_path: Path | str,
    account: Mapping[str, Any],
    contact: Mapping[str, Any],
    communication_policy: Mapping[str, Any],
    email_watch_policy: Mapping[str, Any],
    invoice_send_policy: Mapping[str, Any],
    generated_at: str,
    source_refs: Sequence[str],
) -> dict[str, Any]:
    with _connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO ar_counterparty_accounts
              (account_id, account_label, status, created_at, updated_at, account_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                account["account_id"],
                account["account_label"],
                account["status"],
                account["created_at"],
                account["updated_at"],
                stable_json(account),
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO ar_contact_profiles
              (contact_id, account_id, display_name, relationship_status_json, created_at, updated_at, contact_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                contact["contact_id"],
                contact["account_id"],
                contact["display_name"],
                stable_json(contact["relationship_status"]),
                contact["created_at"],
                contact["updated_at"],
                stable_json(contact),
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO ar_communication_policies
              (policy_id, account_id, contact_id, communication_context, created_at, updated_at, policy_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                communication_policy["policy_id"],
                communication_policy["account_id"],
                communication_policy["contact_id"],
                communication_policy["communication_context"],
                communication_policy["created_at"],
                communication_policy["updated_at"],
                stable_json(communication_policy),
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO ar_email_watch_policies
              (watch_policy_id, account_id, contact_id, status, policy_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                email_watch_policy["watch_policy_id"],
                email_watch_policy["account_id"],
                email_watch_policy["contact_id"],
                email_watch_policy["status"],
                stable_json(email_watch_policy),
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO ar_invoice_send_policies
              (policy_id, account_id, contact_id, status, policy_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                invoice_send_policy["policy_id"],
                invoice_send_policy["account_id"],
                invoice_send_policy["contact_id"],
                invoice_send_policy["status"],
                stable_json(invoice_send_policy),
            ),
        )
        events = [
            _event(
                account_id=str(account["account_id"]),
                contact_id=str(contact["contact_id"]),
                event_type="account_created_or_updated",
                source_ref=str(source_refs[0] if source_refs else "seed"),
                generated_at=generated_at,
            ),
            _event(
                account_id=str(account["account_id"]),
                contact_id=str(contact["contact_id"]),
                event_type="contact_profile_created_or_updated",
                source_ref=str(source_refs[0] if source_refs else "seed"),
                generated_at=generated_at,
            ),
            _event(
                account_id=str(account["account_id"]),
                contact_id=str(contact["contact_id"]),
                event_type="relationship_assertion_recorded",
                source_ref="operator_assertion",
                generated_at=generated_at,
            ),
            _event(
                account_id=str(account["account_id"]),
                contact_id=str(contact["contact_id"]),
                event_type="communication_policy_created_or_updated",
                source_ref=str(communication_policy["policy_id"]),
                generated_at=generated_at,
            ),
            _event(
                account_id=str(account["account_id"]),
                contact_id=str(contact["contact_id"]),
                event_type="watch_policy_created_or_updated",
                source_ref=str(email_watch_policy["watch_policy_id"]),
                generated_at=generated_at,
            ),
            _event(
                account_id=str(account["account_id"]),
                contact_id=str(contact["contact_id"]),
                event_type="invoice_send_policy_created_or_updated",
                source_ref=str(invoice_send_policy["policy_id"]),
                generated_at=generated_at,
            ),
        ]
        for source_ref in source_refs:
            events.append(
                _event(
                    account_id=str(account["account_id"]),
                    contact_id=str(contact["contact_id"]),
                    event_type="source_ref_linked",
                    source_ref=source_ref,
                    generated_at=generated_at,
                )
            )
        for event in events:
            _store_event(conn, event)
        conn.commit()
    return {
        "account": dict(account),
        "contact": dict(contact),
        "communication_policy": dict(communication_policy),
        "email_watch_policy": dict(email_watch_policy),
        "invoice_send_policy": dict(invoice_send_policy),
        "events_recorded": len(events),
    }


def seed_capital_hilton_annette_fixture(
    *,
    sqlite_path: Path | str = DEFAULT_SQLITE_PATH,
    metadata_receipt_path: Path | str = DEFAULT_CAPITAL_HILTON_METADATA_RECEIPT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    receipt_path = Path(metadata_receipt_path)
    receipt = _read_json(receipt_path)
    matched_metadata = _first_metadata_evidence(receipt)
    account = _account_record(
        account_id="capital_hilton",
        account_label="Capital Hilton",
        aliases=["Capital Hilton", "Hilton", "Capital Hilton payment"],
        payment_context_summary=(
            "Operator-provided relationship context says Annette is the person who gets the "
            "operator paid at Capital Hilton; metadata confirms a May 6 message about an invoice."
        ),
        generated_at=generated_at,
    )
    source_refs = [
        "operator_assertion:annette_payment_contact_current_handoff",
        receipt_path.as_posix(),
    ]
    contact = _contact_record(
        account_id="capital_hilton",
        display_name="Annette Sunga",
        email_address="Annette.Sunga@hilton.com",
        role_labels=["payment_contact", "invoice_followup_contact"],
        relationship_status=["operator_asserted", "metadata_confirmed"],
        source_refs=source_refs,
        confidence="working_context",
        generated_at=generated_at,
    )
    if matched_metadata:
        contact["metadata_receipt_path"] = receipt_path.as_posix()
        contact["matched_metadata"] = matched_metadata
        contact["metadata_evidence_status"] = "metadata_confirmed_body_unread"
    communication_policy = _communication_policy(
        account_id=str(account["account_id"]),
        contact_id=str(contact["contact_id"]),
        generated_at=generated_at,
    )
    email_watch_policy = _watch_policy(account_id=str(account["account_id"]), contact=contact, generated_at=generated_at)
    invoice_send_policy = _invoice_send_policy(
        account_id=str(account["account_id"]),
        contact_id=str(contact["contact_id"]),
        generated_at=generated_at,
    )
    return _store_seed(
        sqlite_path=sqlite_path,
        account=account,
        contact=contact,
        communication_policy=communication_policy,
        email_watch_policy=email_watch_policy,
        invoice_send_policy=invoice_send_policy,
        generated_at=generated_at,
        source_refs=source_refs,
    )


def seed_ar_fixture_account(
    *,
    sqlite_path: Path | str = DEFAULT_SQLITE_PATH,
    account_id: str,
    account_label: str,
    aliases: Sequence[str],
    contact_display_name: str,
    email_address: str,
    role_labels: Sequence[str],
    metadata_receipt_ref: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    source_refs = ["operator_assertion:ar_fixture_contact"]
    if metadata_receipt_ref:
        source_refs.append(str(metadata_receipt_ref))
    account = _account_record(
        account_id=account_id,
        account_label=account_label,
        aliases=aliases,
        payment_context_summary=f"Reusable AR fixture account for {account_label}.",
        generated_at=generated_at,
    )
    contact = _contact_record(
        account_id=account_id,
        display_name=contact_display_name,
        email_address=email_address,
        role_labels=role_labels,
        relationship_status=["operator_asserted"],
        source_refs=source_refs,
        confidence="working_context",
        generated_at=generated_at,
    )
    communication_policy = _communication_policy(account_id=account_id, contact_id=str(contact["contact_id"]), generated_at=generated_at)
    email_watch_policy = _watch_policy(account_id=account_id, contact=contact, generated_at=generated_at)
    invoice_send_policy = _invoice_send_policy(account_id=account_id, contact_id=str(contact["contact_id"]), generated_at=generated_at)
    return _store_seed(
        sqlite_path=sqlite_path,
        account=account,
        contact=contact,
        communication_policy=communication_policy,
        email_watch_policy=email_watch_policy,
        invoice_send_policy=invoice_send_policy,
        generated_at=generated_at,
        source_refs=source_refs,
    )


def _load_table(conn: sqlite3.Connection, table: str, json_column: str) -> list[dict[str, Any]]:
    rows = conn.execute(f"SELECT {json_column} FROM {table}").fetchall()
    return [json.loads(row[json_column]) for row in rows]


def _load_registry(sqlite_path: Path | str) -> dict[str, list[dict[str, Any]]]:
    with _connect(sqlite_path) as conn:
        return {
            "accounts": _load_table(conn, "ar_counterparty_accounts", "account_json"),
            "contacts": _load_table(conn, "ar_contact_profiles", "contact_json"),
            "communication_policies": _load_table(conn, "ar_communication_policies", "policy_json"),
            "email_watch_policies": _load_table(conn, "ar_email_watch_policies", "policy_json"),
            "invoice_send_policies": _load_table(conn, "ar_invoice_send_policies", "policy_json"),
        }


def _auto_seed_defaults_if_needed(sqlite_path: Path | str, text: str, generated_at: str) -> None:
    lowered = str(text or "").lower()
    if not any(term in lowered for term in ("capital hilton", "annette")):
        return
    registry = _load_registry(sqlite_path)
    if any(account.get("account_id") == "capital_hilton" for account in registry["accounts"]):
        return
    seed_capital_hilton_annette_fixture(sqlite_path=sqlite_path, generated_at=generated_at)


def _resolve_account_contact(registry: Mapping[str, list[dict[str, Any]]], text: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    lowered = str(text or "").lower()
    accounts = registry["accounts"]
    contacts = registry["contacts"]
    account: dict[str, Any] | None = None
    contact: dict[str, Any] | None = None
    for candidate in accounts:
        labels = [candidate.get("account_label", ""), *(candidate.get("aliases") or [])]
        if any(str(label).lower() in lowered for label in labels if label):
            account = candidate
            break
    for candidate in contacts:
        names = [candidate.get("display_name", ""), *(candidate.get("email_addresses") or [])]
        name_parts = str(candidate.get("display_name") or "").split()
        names.extend(name_parts)
        if any(str(name).lower() in lowered for name in names if name):
            contact = candidate
            break
    if contact and not account:
        account = next((item for item in accounts if item.get("account_id") == contact.get("account_id")), None)
    if account and not contact:
        account_contacts = [item for item in contacts if item.get("account_id") == account.get("account_id")]
        contact = account_contacts[0] if len(account_contacts) == 1 else None
    return account, contact


def _policy_for(
    policies: Sequence[dict[str, Any]],
    *,
    account_id: str,
    contact_id: str,
    context: str | None = None,
) -> dict[str, Any]:
    for policy in policies:
        if policy.get("account_id") != account_id or policy.get("contact_id") != contact_id:
            continue
        if context and policy.get("communication_context") != context:
            continue
        return dict(policy)
    return {}


def _detect_intent(text: str) -> str:
    lowered = str(text or "").lower()
    if "watch" in lowered and any(term in lowered for term in ("email", "emails", "mail")):
        return "email_watch"
    if "send" in lowered and "invoice" in lowered:
        return "invoice_send"
    if "email" in lowered and "invoice" in lowered:
        return "email_followup"
    if "payment" in lowered or "follow-up" in lowered or "follow up" in lowered or "followup" in lowered:
        return "payment_followup"
    return "unknown"


def detects_ar_counterparty_intent(text: str) -> bool:
    lowered = str(text or "").lower()
    has_ar_action = (
        any(term in lowered for term in ("payment follow-up", "payment follow up", "payment followup"))
        or ("handle" in lowered and "payment" in lowered)
        or ("email" in lowered and "invoice" in lowered)
        or ("send" in lowered and "invoice" in lowered)
        or (
            "watch" in lowered
            and any(term in lowered for term in ("email", "emails", "mail"))
        )
    )
    has_counterparty_hint = any(term in lowered for term in ("capital hilton", "annette", "payment", "invoice"))
    return has_ar_action and has_counterparty_hint


def _text_only_draft(account: Mapping[str, Any], contact: Mapping[str, Any]) -> dict[str, Any]:
    recipient = f"{contact.get('display_name')} <{(contact.get('email_addresses') or [''])[0]}>"
    return {
        "schema_version": AR_TEXT_ONLY_DRAFT_SCHEMA,
        "draft_medium": "text_only_review",
        "recipient": recipient,
        "subject": f"Following up on {account.get('account_label')} invoice",
        "body_preview": (
            f"Hi {str(contact.get('display_name') or '').split()[0]}, I wanted to follow up on the invoice "
            f"for {account.get('account_label')}. Could you let me know the current payment status?"
        ),
        "gmail_draft_created": False,
        "email_send_performed": False,
        "review_required": True,
    }


def _package_plan(
    *,
    account: Mapping[str, Any],
    contact: Mapping[str, Any],
    intent: str,
    next_safe_step: str,
    metadata_exists: bool,
) -> dict[str, Any]:
    required = [
        "ar_contact_profile_resolution",
        "openclaw.gmail_metadata_read",
        "openclaw.gmail_body_read",
        "openclaw.gmail_draft_generator",
    ]
    if intent == "invoice_send":
        required.extend(["ar_invoice_artifact_resolver", "openclaw.gmail_send_mail"])
    if intent == "email_watch":
        required.extend(["ar_email_watch_policy", "UNATTENDED_RUN_ENVELOPE_V0"])
    return {
        "schema_version": AR_CAPABILITY_PACKAGE_PLAN_SCHEMA,
        "required_capabilities": _dedupe(required),
        "known_context": {
            "account": account.get("account_label"),
            "primary_payment_contact": contact.get("display_name"),
            "metadata_evidence_exists": metadata_exists,
            "relationship_basis": list(contact.get("relationship_status") or []),
        },
        "available_credential_candidate": GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID,
        "next_safe_step": next_safe_step,
        "denied_actions": [
            "send_without_exact_authority",
            "body_read_without_authority",
            "invoice_send_without_artifact",
            "ledger_coupa_paid_mutation",
        ],
        "no_execution_occurred": True,
    }


def _unknown_plan(text: str, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": AR_COUNTERPARTY_ACTION_PLAN_SCHEMA,
        "recognized": False,
        "intent": "unknown",
        "original_text_excerpt": " ".join(str(text or "").split())[:180],
        "next_safe_step": "Provide the AR account or contact to resolve.",
        "created_at": generated_at,
        "machine_proof": dict(MACHINE_PROOF),
    }


def plan_ar_counterparty_action(
    text: str,
    *,
    sqlite_path: Path | str = DEFAULT_SQLITE_PATH,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    _auto_seed_defaults_if_needed(sqlite_path, text, generated_at)
    registry = _load_registry(sqlite_path)
    account, contact = _resolve_account_contact(registry, text)
    intent = _detect_intent(text)
    if not account or not contact or intent == "unknown":
        return _unknown_plan(text, generated_at)

    account_id = str(account["account_id"])
    contact_id = str(contact["contact_id"])
    communication_policy = _policy_for(
        registry["communication_policies"],
        account_id=account_id,
        contact_id=contact_id,
        context="payment_followup",
    )
    email_watch_policy = _policy_for(registry["email_watch_policies"], account_id=account_id, contact_id=contact_id)
    invoice_send_policy = _policy_for(registry["invoice_send_policies"], account_id=account_id, contact_id=contact_id)
    matched_metadata = contact.get("matched_metadata") if isinstance(contact.get("matched_metadata"), Mapping) else None
    metadata_exists = bool(matched_metadata)
    required_authority = "scoped_metadata_lookup_authority"
    missing_requirements: list[str] = []
    text_only_draft: dict[str, Any] | None = None

    if intent == "payment_followup":
        if metadata_exists:
            next_safe_step = "Request body-read authority for the matched Annette email."
            required_authority = "single_message_body_read_authority"
        else:
            next_safe_step = f"Request scoped metadata lookup for {contact['display_name']} / {account['account_label']}."
    elif intent == "email_followup":
        next_safe_step = "Review the text-only follow-up draft."
        required_authority = "operator_draft_review"
        text_only_draft = _text_only_draft(account, contact)
    elif intent == "invoice_send":
        next_safe_step = "Provide invoice artifact and review exact send authority request."
        required_authority = "exact_invoice_send_authority"
        missing_requirements = ["invoice_artifact_ref", "exact_send_authority"]
    elif intent == "email_watch":
        next_safe_step = "Review scoped metadata watch authority and unattended envelope."
        required_authority = "scoped_metadata_watch_authority"
    else:
        return _unknown_plan(text, generated_at)

    plan = {
        "schema_version": AR_COUNTERPARTY_ACTION_PLAN_SCHEMA,
        "recognized": True,
        "intent": intent,
        "account": account,
        "contact": contact,
        "communication_policy": communication_policy,
        "email_watch_policy": email_watch_policy,
        "invoice_send_policy": invoice_send_policy,
        "metadata_receipt_path": contact.get("metadata_receipt_path"),
        "matched_metadata": matched_metadata,
        "required_authority": required_authority,
        "required_credential": GOOGLE_WORKSPACE_BROKER_CREDENTIAL_HANDLE_ID,
        "next_safe_step": next_safe_step,
        "denied_actions": list(DENIED_ACTIONS),
        "send_locked": True,
        "requires_invoice_artifact": intent == "invoice_send",
        "requires_exact_send_authority": intent == "invoice_send",
        "missing_requirements": missing_requirements,
        "body_read_requires_authority": True,
        "contact_role_does_not_imply_send_authority": True,
        "watch_policy_does_not_imply_mailbox_scan": True,
        "invoice_policy_does_not_imply_invoice_send": True,
        "created_at": generated_at,
        "machine_proof": dict(MACHINE_PROOF),
    }
    if text_only_draft:
        plan["text_only_draft"] = text_only_draft
    plan["package_plan"] = _package_plan(
        account=account,
        contact=contact,
        intent=intent,
        next_safe_step=next_safe_step,
        metadata_exists=metadata_exists,
    )
    return plan

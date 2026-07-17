"""Immutable invoice-send class waist and canonical PREPARED transaction store.

This module composes and validates client copy, binds it to deterministic invoice
facts and an exact artifact, and records a semantic transaction. It cannot create
a provider draft, grant approval, send email, move money, or mutate a workbook.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from agent_voice_profiles import (
    VoiceConformanceError,
    loop_closing_ask_for_workflow,
    require_clara_copy_conformance,
)


ENVELOPE_SCHEMA_VERSION = "invoice_send_envelope_v1"
COPY_SCHEMA_VERSION = "invoice_copy_candidate_v1"
TRANSACTION_SCHEMA_VERSION = "invoice_send_transaction_v1"
CANONICAL_SENDER = "winshiplive@gmail.com"
PREPARED = "PREPARED"
SUPERSEDED = "SUPERSEDED"
LIFECYCLE_STATES = (
    PREPARED,
    SUPERSEDED,
    "VERIFIED",
    "DRAFT_CREATED",
    "DRAFT_VERIFIED",
    "APPROVAL_PENDING",
    "IN_FLIGHT",
    "SENT_PENDING_VERIFY",
    "SENT_VERIFIED",
    "RECONCILE_REQUIRED",
    "FAILED",
)

_SEMANTIC_MARKER_RE = re.compile(r"\b(?:DRAFT|TBD)\b", re.IGNORECASE)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_Composer = Callable[[str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]


class InvoiceEnvelopeError(ValueError):
    """Raised before persistence when envelope facts are incomplete or conflict."""


class InvoiceCopyConformanceError(InvoiceEnvelopeError):
    """Raised when composed copy changes truth, authority, voice, or workflow ask."""


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _required(mapping: Mapping[str, Any], field: str) -> Any:
    value = mapping.get(field)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise InvoiceEnvelopeError(f"missing required field: {field}")
    return value


def _email_list(value: Any, *, field: str, required: bool = False) -> tuple[str, ...]:
    values = value if isinstance(value, (list, tuple)) else (() if value in (None, "") else (value,))
    emails = tuple(_clean(item) for item in values if _clean(item))
    if required and not emails:
        raise InvoiceEnvelopeError(f"missing required recipient list: {field}")
    for email in emails:
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            raise InvoiceEnvelopeError(f"invalid {field} recipient")
    return emails


def _amount_text(amount_minor_units: int, currency: str) -> str:
    if currency.upper() != "USD":
        return f"{currency.upper()} {amount_minor_units / 100:.2f}"
    return f"${amount_minor_units / 100:,.2f}"


def _deterministic_copy(
    packet: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    client = _clean(_required(packet, "client_display_name"))
    invoice_number = _clean(_required(packet, "invoice_number"))
    service_period = _clean(_required(packet, "service_period"))
    currency = _clean(_required(packet, "currency")).upper()
    amount_minor_units = int(_required(packet, "amount_minor_units"))
    amount = _amount_text(amount_minor_units, currency)
    ask = _clean(_required(contract, "human_closing_ask"))
    why = _clean(_required(contract, "ask_why"))
    return {
        "subject": f"{client} invoice {invoice_number} - {service_period}",
        "body": (
            f"Hi there,\n\nI've attached invoice {invoice_number} for {client}, covering "
            f"{service_period}, for {amount}.\n\n{ask} {why}\n\nWarmly,\nClara Reid"
        ),
        "packet_critique": {
            "source": "deterministic_local",
            "packet_used_as_aid": True,
            "grounded_fact_count": 4,
            "authority_granted": False,
        },
    }


def _safe_packet_critique(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    allowed = {
        "source",
        "score",
        "reason_codes",
        "grounded",
        "current",
        "useful",
        "packet_used_as_aid",
        "grounded_fact_count",
        "authority_granted",
    }
    return {str(key): item for key, item in value.items() if str(key) in allowed}


def _validate_copy(
    *,
    packet: Mapping[str, Any],
    contract: Mapping[str, Any],
    subject: str,
    body: str,
) -> dict[str, Any]:
    speaker = _clean(_required(contract, "voice_speaker")).lower()
    if speaker != "clara":
        raise InvoiceCopyConformanceError("invoice client copy must use the Clara speaker profile")

    workflow_ref = _clean(_required(contract, "workflow_ref"))
    client_ref = _clean(_required(packet, "client_ref"))
    closure = loop_closing_ask_for_workflow(workflow_ref, client_ref=client_ref)
    if _clean(contract.get("human_closing_ask")) != _clean(closure["ask_text"]):
        raise InvoiceCopyConformanceError("human closing ask does not match the workflow milestone")
    if _clean(contract.get("ask_why")) != _clean(closure["why_text"]):
        raise InvoiceCopyConformanceError("human closing reason does not match the workflow milestone")
    if _clean(contract.get("next_verification_milestone")) != _clean(closure["milestone_ref"]):
        raise InvoiceCopyConformanceError("next verification milestone does not match the workflow")

    combined = f"{subject}\n{body}"
    if _SEMANTIC_MARKER_RE.search(combined):
        raise InvoiceCopyConformanceError("external copy contains a forbidden semantic marker")
    if not _clean(_required(packet, "service_period")):
        raise InvoiceCopyConformanceError("external copy requires a service period")

    amount = _amount_text(int(_required(packet, "amount_minor_units")), _clean(_required(packet, "currency")))
    required_facts = {
        "client_display_name": _clean(_required(packet, "client_display_name")),
        "invoice_number": _clean(_required(packet, "invoice_number")),
        "service_period": _clean(_required(packet, "service_period")),
        "amount_minor_units": amount,
    }
    folded = combined.casefold()
    missing = [name for name, value in required_facts.items() if value.casefold() not in folded]
    if missing:
        raise InvoiceCopyConformanceError("candidate copy omitted immutable facts: " + ", ".join(missing))
    for claim in contract.get("forbidden_claims") or ():
        if _clean(claim).casefold() in folded:
            raise InvoiceCopyConformanceError(f"candidate copy invented forbidden claim: {_clean(claim)}")

    try:
        clara = require_clara_copy_conformance(body, workflow_ref=workflow_ref, client_ref=client_ref)
    except VoiceConformanceError as exc:
        raise InvoiceCopyConformanceError("candidate copy failed Clara voice or loop-closing conformance") from exc
    return clara


def compose_invoice_copy(
    raw_operator_ask: str,
    deterministic_packet_aid: Mapping[str, Any],
    immutable_copy_contract: Mapping[str, Any],
    *,
    composer: _Composer | None = None,
) -> dict[str, Any]:
    """Compose candidate copy through a narrow router-compatible, no-authority seam."""

    if not _clean(raw_operator_ask):
        raise InvoiceCopyConformanceError("raw operator ask is required")
    packet = dict(deterministic_packet_aid)
    contract = dict(immutable_copy_contract)
    candidate = dict(
        composer(raw_operator_ask, packet, contract)
        if composer is not None
        else _deterministic_copy(packet, contract)
    )
    subject = _clean(candidate.get("candidate_subject") or candidate.get("subject"))
    body = str(candidate.get("candidate_body") or candidate.get("body") or "").strip()
    if not subject or not body:
        raise InvoiceCopyConformanceError("composer must return a subject and body")
    clara = _validate_copy(packet=packet, contract=contract, subject=subject, body=body)

    fact_names = ("client_ref", "client_display_name", "invoice_number", "service_period", "currency", "amount_minor_units")
    citations = [
        {
            "fact": field,
            "source": f"deterministic_packet_aid.{field}",
            "value_sha256": _sha256_text(_stable_json(packet[field])),
        }
        for field in fact_names
    ]
    return {
        "schema_version": COPY_SCHEMA_VERSION,
        "candidate_subject": subject,
        "candidate_body": body,
        "packet_critique": _safe_packet_critique(candidate.get("packet_critique")),
        "copy_fact_citations": citations,
        "composer_source": "router_composer" if composer is not None else "deterministic_local",
        "immutable_input_hashes": {
            "raw_operator_ask": _sha256_text(raw_operator_ask),
            "deterministic_packet_aid": _sha256_text(_stable_json(packet)),
            "immutable_copy_contract": _sha256_text(_stable_json(contract)),
            "candidate_subject": _sha256_text(subject),
            "candidate_body": _sha256_text(body),
        },
        "truth_conformance": {"passed": True, "required_fact_count": len(citations)},
        "voice_conformance": clara["voice_conformance"],
        "loop_closing_ask_conformance": clara["loop_closing_ask"],
        "authority_granted": False,
        "provider_draft_created": False,
        "email_send_performed": False,
    }


@dataclass(frozen=True, slots=True)
class InvoiceSendEnvelope:
    """Frozen canonical envelope bytes plus the hashes used by the transaction store."""

    transaction_id: str
    semantic_idempotency_key: str
    envelope_hash: str
    canonical_payload_json: str

    def to_dict(self) -> dict[str, Any]:
        payload = json.loads(self.canonical_payload_json)
        payload["envelope_hash"] = self.envelope_hash
        return payload


def _verified_artifact(receipt: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(_clean(_required(receipt, "path")))
    path_text = str(path)
    if any(marker in path_text.casefold() for marker in ("legalprivate", "financeprivate", "musiclawprivate")):
        raise InvoiceEnvelopeError("artifact path crosses a private-vault boundary")
    if not path.is_file():
        raise InvoiceEnvelopeError("artifact path is not a readable file")
    content = path.read_bytes()
    observed_sha = _sha256_bytes(content)
    expected_sha = _clean(_required(receipt, "sha256")).lower()
    if observed_sha != expected_sha:
        raise InvoiceEnvelopeError("artifact sha256 does not match the verified file")
    observed_size = len(content)
    if observed_size != int(_required(receipt, "size_bytes")):
        raise InvoiceEnvelopeError("artifact size does not match the verified file")
    return {
        "path": path_text,
        "mime_type": _clean(_required(receipt, "mime_type")),
        "size_bytes": observed_size,
        "sha256": observed_sha,
        "artifact_verification_receipt_id": _clean(_required(receipt, "artifact_verification_receipt_id")),
        "formula_freshness_receipt_id": _clean(_required(receipt, "formula_freshness_receipt_id")),
    }


def assemble_invoice_send_envelope(
    *,
    raw_operator_ask: str,
    deterministic_packet_aid: Mapping[str, Any],
    immutable_copy_contract: Mapping[str, Any],
    copy_result: Mapping[str, Any],
    artifact_receipt: Mapping[str, Any],
    generated_at: str | None = None,
) -> InvoiceSendEnvelope:
    packet = dict(deterministic_packet_aid)
    contract = dict(immutable_copy_contract)
    artifact = _verified_artifact(artifact_receipt)
    generated_at = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    client_ref = _clean(_required(packet, "client_ref"))
    invoice_number = _clean(_required(packet, "invoice_number"))
    service_period = _clean(_required(packet, "service_period"))
    currency = _clean(_required(packet, "currency")).upper()
    amount_minor_units = int(_required(packet, "amount_minor_units"))
    source_workbook = dict(_required(packet, "source_workbook"))
    for field in ("path", "version", "sha256"):
        _required(source_workbook, field)
    if not _SHA256_RE.fullmatch(_clean(source_workbook["sha256"]).lower()):
        raise InvoiceEnvelopeError("source workbook sha256 is invalid")

    sender = _clean(_required(contract, "sender"))
    if sender.casefold() != CANONICAL_SENDER.casefold():
        raise InvoiceEnvelopeError("envelope sender must be the canonical Gmail account")
    to = _email_list(contract.get("to"), field="to", required=True)
    cc = _email_list(contract.get("cc"), field="cc")
    bcc = _email_list(contract.get("bcc"), field="bcc")
    subject = _clean(_required(copy_result, "candidate_subject"))
    body = str(_required(copy_result, "candidate_body")).strip()
    _validate_copy(packet=packet, contract=contract, subject=subject, body=body)

    semantic_material = [client_ref, invoice_number, service_period, artifact["sha256"]]
    semantic_key = "invoice-send:" + hashlib.sha256(_stable_json(semantic_material).encode("utf-8")).hexdigest()
    transaction_id = "invoice-send-tx:" + semantic_key.rsplit(":", 1)[-1][:24]
    payload = {
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "transaction_id": transaction_id,
        "semantic_idempotency_key": semantic_key,
        "assembled_at": generated_at,
        "client_ref": client_ref,
        "client_display_name": _clean(_required(packet, "client_display_name")),
        "invoice_number": invoice_number,
        "service_period": service_period,
        "currency": currency,
        "amount_minor_units": amount_minor_units,
        "source_workbook": source_workbook,
        "source_fact_version": _clean(source_workbook["version"]),
        "source_fact_sha256": _clean(source_workbook["sha256"]).lower(),
        "artifact": artifact,
        "sender": sender,
        "to": list(to),
        "cc": list(cc),
        "bcc": list(bcc),
        "copy": {
            "speaker_ref": "clara",
            "voice_profile_ref": str((copy_result.get("voice_conformance") or {}).get("voice_profile_ref") or ""),
            "subject": subject,
            "subject_sha256": _sha256_text(subject),
            "body": body,
            "body_sha256": _sha256_text(body),
            "copy_fact_citations": list(copy_result.get("copy_fact_citations") or ()),
            "raw_operator_ask_sha256": _sha256_text(raw_operator_ask),
            "packet_aid_sha256": str((copy_result.get("immutable_input_hashes") or {}).get("deterministic_packet_aid") or ""),
            "copy_contract_sha256": str((copy_result.get("immutable_input_hashes") or {}).get("immutable_copy_contract") or ""),
            "packet_critique": dict(copy_result.get("packet_critique") or {}),
        },
        "semantic_marker_findings": [],
        "semantic_marker_waiver": None,
        "next_verification_milestone": _clean(_required(contract, "next_verification_milestone")),
        "human_closing_ask": _clean(_required(contract, "human_closing_ask")),
        "ask_why": _clean(_required(contract, "ask_why")),
        "provider_draft": {"draft_id": None, "draft_hash": None, "readback_receipt_id": None},
        "approval": {
            "authority_granted": False,
            "scope": None,
            "expires_at": None,
            "bounded_use_count": 0,
            "guardian_action_id": None,
        },
        "lifecycle_state": PREPARED,
        "authority_boundary": {
            "gmail_lookup_performed": False,
            "gmail_body_read_performed": False,
            "gmail_draft_created": False,
            "email_send_performed": False,
            "money_moved": False,
            "workbook_mutated": False,
            "provider_called": False,
            "external_action_performed": False,
        },
    }
    canonical = _stable_json(payload)
    envelope_hash = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return InvoiceSendEnvelope(transaction_id, semantic_key, envelope_hash, canonical)


def ensure_invoice_transaction_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS invoice_send_transactions (
          transaction_id TEXT PRIMARY KEY,
          semantic_idempotency_key TEXT NOT NULL UNIQUE,
          client_ref TEXT NOT NULL,
          invoice_number TEXT NOT NULL,
          service_period TEXT NOT NULL,
          attachment_sha256 TEXT NOT NULL,
          envelope_hash TEXT NOT NULL,
          lifecycle_state TEXT NOT NULL,
          next_verification_milestone TEXT NOT NULL,
          human_closing_ask TEXT NOT NULL,
          ask_why TEXT NOT NULL,
          envelope_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(client_ref, invoice_number, service_period, attachment_sha256)
        );
        CREATE INDEX IF NOT EXISTS idx_invoice_send_transactions_state
          ON invoice_send_transactions(lifecycle_state, client_ref);
        CREATE TABLE IF NOT EXISTS invoice_send_transaction_decisions (
          decision_id TEXT PRIMARY KEY,
          transaction_id TEXT NOT NULL,
          prior_lifecycle_state TEXT NOT NULL,
          lifecycle_state TEXT NOT NULL,
          superseded_by_transaction_id TEXT NOT NULL,
          reason TEXT NOT NULL,
          decided_at TEXT NOT NULL,
          decision_json TEXT NOT NULL,
          UNIQUE(transaction_id, lifecycle_state, superseded_by_transaction_id)
        );
        CREATE TRIGGER IF NOT EXISTS invoice_send_transaction_decisions_no_update
        BEFORE UPDATE ON invoice_send_transaction_decisions
        BEGIN
          SELECT RAISE(ABORT, 'invoice send transaction decisions are append-only');
        END;
        CREATE TRIGGER IF NOT EXISTS invoice_send_transaction_decisions_no_delete
        BEFORE DELETE ON invoice_send_transaction_decisions
        BEGIN
          SELECT RAISE(ABORT, 'invoice send transaction decisions are append-only');
        END;
        """
    )


def _obligation_identity(row: sqlite3.Row) -> dict[str, Any]:
    try:
        payload = json.loads(str(row["envelope_json"]))
        identity = {
            "client_ref": _clean(payload["client_ref"]),
            "service_period": _clean(payload["service_period"]),
            "currency": _clean(payload["currency"]).upper(),
            "amount_minor_units": int(payload["amount_minor_units"]),
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise InvoiceEnvelopeError("transaction has no valid invoice obligation identity") from exc
    if identity["client_ref"] != _clean(row["client_ref"]):
        raise InvoiceEnvelopeError("transaction client identity does not match its immutable envelope")
    if identity["service_period"] != _clean(row["service_period"]):
        raise InvoiceEnvelopeError("transaction service period does not match its immutable envelope")
    return identity


def supersede_prepared_transaction(
    *,
    db_path: str | Path,
    transaction_id: str,
    superseded_by_transaction_id: str,
    reason: str,
    decided_at: str | None = None,
) -> dict[str, Any]:
    path = Path(db_path)
    prior_id = _clean(transaction_id)
    successor_id = _clean(superseded_by_transaction_id)
    clean_reason = _clean(reason)
    if not prior_id or not successor_id or not clean_reason:
        raise InvoiceEnvelopeError("supersession requires both transaction ids and a reason")
    if prior_id == successor_id:
        raise InvoiceEnvelopeError("a transaction cannot supersede itself")
    timestamp = _clean(decided_at) or datetime.now(timezone.utc).isoformat()
    decision_id = "invoice-send-decision:" + hashlib.sha256(
        f"{prior_id}|{SUPERSEDED}|{successor_id}".encode("utf-8")
    ).hexdigest()[:24]

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_invoice_transaction_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        prior = conn.execute(
            "SELECT * FROM invoice_send_transactions WHERE transaction_id = ?",
            (prior_id,),
        ).fetchone()
        successor = conn.execute(
            "SELECT * FROM invoice_send_transactions WHERE transaction_id = ?",
            (successor_id,),
        ).fetchone()
        if prior is None or successor is None:
            raise InvoiceEnvelopeError("supersession requires two existing invoice transactions")

        existing = conn.execute(
            "SELECT decision_json FROM invoice_send_transaction_decisions WHERE decision_id = ?",
            (decision_id,),
        ).fetchone()
        if prior["lifecycle_state"] == SUPERSEDED:
            if existing is None:
                raise InvoiceEnvelopeError("superseded transaction is missing its append-only decision")
            decision = json.loads(existing["decision_json"])
            if decision["reason"] != clean_reason:
                raise InvoiceEnvelopeError("supersession replay changed the immutable reason")
            conn.commit()
            return {**decision, "idempotent_replay": True}
        if prior["lifecycle_state"] != PREPARED:
            raise InvoiceEnvelopeError("only a PREPARED transaction can be superseded")
        if successor["lifecycle_state"] != PREPARED:
            raise InvoiceEnvelopeError("superseding transaction must remain PREPARED")

        prior_obligation = _obligation_identity(prior)
        successor_obligation = _obligation_identity(successor)
        if prior_obligation != successor_obligation:
            raise InvoiceEnvelopeError("transactions do not represent the same invoice obligation")

        authority_boundary = {
            "provider_called": False,
            "gmail_draft_created": False,
            "email_send_performed": False,
            "money_moved": False,
            "workbook_mutated": False,
            "ledger_posted": False,
        }
        decision = {
            "schema_version": "invoice_send_transaction_decision_v1",
            "decision_id": decision_id,
            "transaction_id": prior_id,
            "prior_lifecycle_state": PREPARED,
            "lifecycle_state": SUPERSEDED,
            "superseded_by_transaction_id": successor_id,
            "reason": clean_reason,
            "decided_at": timestamp,
            "obligation": prior_obligation,
            "authority_boundary": authority_boundary,
        }
        changed = conn.execute(
            """
            UPDATE invoice_send_transactions
               SET lifecycle_state = ?, updated_at = ?
             WHERE transaction_id = ? AND lifecycle_state = ?
            """,
            (SUPERSEDED, timestamp, prior_id, PREPARED),
        ).rowcount
        if changed != 1:
            raise InvoiceEnvelopeError("prepared transaction changed during supersession")
        conn.execute(
            """
            INSERT INTO invoice_send_transaction_decisions (
              decision_id, transaction_id, prior_lifecycle_state, lifecycle_state,
              superseded_by_transaction_id, reason, decided_at, decision_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                prior_id,
                PREPARED,
                SUPERSEDED,
                successor_id,
                clean_reason,
                timestamp,
                _stable_json(decision),
            ),
        )
        conn.commit()
        return {**decision, "idempotent_replay": False}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def record_prepared_transaction(
    envelope: InvoiceSendEnvelope,
    *,
    db_path: str | Path,
) -> dict[str, Any]:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_invoice_transaction_schema(conn)
        payload = envelope.to_dict()
        existing = conn.execute(
            "SELECT * FROM invoice_send_transactions WHERE semantic_idempotency_key = ?",
            (envelope.semantic_idempotency_key,),
        ).fetchone()
        if existing is not None:
            if existing["envelope_hash"] != envelope.envelope_hash:
                raise InvoiceEnvelopeError("semantic transaction collision: immutable envelope changed")
            return {
                "transaction_id": existing["transaction_id"],
                "semantic_idempotency_key": existing["semantic_idempotency_key"],
                "envelope_hash": existing["envelope_hash"],
                "lifecycle_state": existing["lifecycle_state"],
                "created": False,
                "idempotent_replay": True,
            }
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            INSERT INTO invoice_send_transactions (
              transaction_id, semantic_idempotency_key, client_ref, invoice_number,
              service_period, attachment_sha256, envelope_hash, lifecycle_state,
              next_verification_milestone, human_closing_ask, ask_why, envelope_json,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                envelope.transaction_id,
                envelope.semantic_idempotency_key,
                payload["client_ref"],
                payload["invoice_number"],
                payload["service_period"],
                payload["artifact"]["sha256"],
                envelope.envelope_hash,
                PREPARED,
                payload["next_verification_milestone"],
                payload["human_closing_ask"],
                payload["ask_why"],
                envelope.canonical_payload_json,
                payload["assembled_at"],
                payload["assembled_at"],
            ),
        )
        conn.commit()
        return {
            "transaction_id": envelope.transaction_id,
            "semantic_idempotency_key": envelope.semantic_idempotency_key,
            "envelope_hash": envelope.envelope_hash,
            "lifecycle_state": PREPARED,
            "created": True,
            "idempotent_replay": False,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def prepare_invoice_send(
    *,
    raw_operator_ask: str,
    deterministic_packet_aid: Mapping[str, Any],
    immutable_copy_contract: Mapping[str, Any],
    artifact_receipt: Mapping[str, Any],
    db_path: str | Path,
    generated_at: str | None = None,
    composer: _Composer | None = None,
) -> dict[str, Any]:
    copy = compose_invoice_copy(
        raw_operator_ask,
        deterministic_packet_aid,
        immutable_copy_contract,
        composer=composer,
    )
    envelope = assemble_invoice_send_envelope(
        raw_operator_ask=raw_operator_ask,
        deterministic_packet_aid=deterministic_packet_aid,
        immutable_copy_contract=immutable_copy_contract,
        copy_result=copy,
        artifact_receipt=artifact_receipt,
        generated_at=generated_at,
    )
    transaction = record_prepared_transaction(envelope, db_path=db_path)
    return {
        "schema_version": TRANSACTION_SCHEMA_VERSION,
        "transaction": transaction,
        "envelope": envelope.to_dict(),
        "copy_result": copy,
        "machine_proof": {
            "immutable_envelope_persisted": True,
            "semantic_transaction_lock_persisted": True,
            "gmail_draft_created": False,
            "email_send_performed": False,
            "provider_called": False,
            "money_moved": False,
            "workbook_mutated": False,
        },
    }


__all__ = [
    "CANONICAL_SENDER",
    "COPY_SCHEMA_VERSION",
    "ENVELOPE_SCHEMA_VERSION",
    "InvoiceCopyConformanceError",
    "InvoiceEnvelopeError",
    "InvoiceSendEnvelope",
    "LIFECYCLE_STATES",
    "PREPARED",
    "assemble_invoice_send_envelope",
    "compose_invoice_copy",
    "ensure_invoice_transaction_schema",
    "prepare_invoice_send",
    "record_prepared_transaction",
]

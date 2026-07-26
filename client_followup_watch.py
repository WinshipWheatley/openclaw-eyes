"""Client follow-up watch store.

Tracks sent client correspondence and proposes a follow-up draft when no reply
has been observed after the configured window. It never sends email; proposals
are gated through the existing Operator Action / Guardian shape.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from agent_voice_profiles import (
    loop_closing_ask_for_workflow,
    render_loop_closing_ask,
    require_clara_copy_conformance,
    voice_copy_rules_for_speaker,
)
from hitl_action_service import ACTION_TYPE_EXACT_GMAIL_SEND, build_operator_action_approval_payload


DEFAULT_FOLLOWUP_DB_PATH = "/home/openclaw/state/client_followups/client_followups.sqlite3"
FOLLOWUP_WATCH_SCHEMA_VERSION = "client_followup_watch_v1"
FOLLOWUP_PROPOSAL_SCHEMA_VERSION = "client_followup_proposal_v0"

AUTHORITY_BOUNDARY_PROPOSAL = {
    "send_performed": False,
    "email_send_performed": False,
    "gmail_send_performed": False,
    "draft_only": True,
    "send_hold_required": True,
    "guardian_required": True,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_aware_iso(value: str) -> datetime:
    text = str(value or "").replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _short_hash(payload: Any, length: int = 20) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()[:length]


def _expires_at(requested_at_utc: str) -> str:
    return (_parse_aware_iso(requested_at_utc) + timedelta(hours=24)).isoformat(timespec="seconds")


class ClientFollowupWatchStore:
    """SQLite-backed client follow-up watch store."""

    def __init__(self, db_path: str = DEFAULT_FOLLOWUP_DB_PATH) -> None:
        self.db_path = str(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS client_followup_watches (
                    watch_id             TEXT PRIMARY KEY,
                    client_ref           TEXT NOT NULL,
                    client_name          TEXT NOT NULL,
                    recipient            TEXT NOT NULL,
                    subject              TEXT NOT NULL,
                    invoice_ref          TEXT NOT NULL,
                    delivery_confirmation_status TEXT NULL,
                    payment_received_status TEXT NULL,
                    sent_at_utc_iso      TEXT NOT NULL,
                    days_without_reply   INTEGER NOT NULL,
                    due_at_utc_iso       TEXT NOT NULL,
                    status               TEXT NOT NULL,
                    created_at_utc_iso   TEXT NOT NULL,
                    reply_seen_at_utc_iso TEXT NULL,
                    reply_ref            TEXT NOT NULL DEFAULT ''
                )
                """
            )
            columns = {
                str(row[1])
                for row in conn.execute("PRAGMA table_info(client_followup_watches)")
            }
            if "delivery_confirmation_status" not in columns:
                conn.execute(
                    "ALTER TABLE client_followup_watches "
                    "ADD COLUMN delivery_confirmation_status "
                    "TEXT NULL"
                )
            if "payment_received_status" not in columns:
                conn.execute(
                    "ALTER TABLE client_followup_watches "
                    "ADD COLUMN payment_received_status "
                    "TEXT NULL"
                )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_client_followup_due
                ON client_followup_watches (status, due_at_utc_iso)
                """
            )
        finally:
            conn.close()

    def add_watch(
        self,
        *,
        client_ref: str,
        client_name: str,
        recipient: str,
        subject: str,
        sent_at_utc_iso: str,
        invoice_ref: str = "",
        days_without_reply: int = 3,
        created_at_utc_iso: str | None = None,
    ) -> dict[str, Any]:
        sent_at = _parse_aware_iso(sent_at_utc_iso)
        days = int(days_without_reply)
        if days < 0:
            raise ValueError("days_without_reply must be non-negative")
        due_at = sent_at + timedelta(days=days + 1)
        created_at = _parse_aware_iso(created_at_utc_iso).isoformat(timespec="seconds") if created_at_utc_iso else _utc_now_iso()
        payload = {
            "client_ref": str(client_ref or "").strip(),
            "recipient": str(recipient or "").strip(),
            "subject": str(subject or "").strip(),
            "sent_at_utc_iso": sent_at.isoformat(timespec="seconds"),
            "invoice_ref": str(invoice_ref or "").strip(),
        }
        if not payload["client_ref"] or not payload["recipient"] or not payload["subject"]:
            raise ValueError("client_ref, recipient, and subject are required")
        watch_id = "client_followup_watch:" + _short_hash(payload)
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO client_followup_watches (
                    watch_id, client_ref, client_name, recipient, subject, invoice_ref,
                    delivery_confirmation_status, payment_received_status,
                    sent_at_utc_iso, days_without_reply, due_at_utc_iso, status,
                    created_at_utc_iso, reply_seen_at_utc_iso, reply_ref
                )
                VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL, ?, ?, ?, 'active', ?, NULL, '')
                """,
                (
                    watch_id,
                    payload["client_ref"],
                    str(client_name or "").strip() or payload["client_ref"],
                    payload["recipient"],
                    payload["subject"],
                    payload["invoice_ref"],
                    payload["sent_at_utc_iso"],
                    days,
                    due_at.isoformat(timespec="seconds"),
                    created_at,
                ),
            )
            return self.get_watch(watch_id) or {}
        finally:
            conn.close()

    def get_watch(self, watch_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM client_followup_watches WHERE watch_id = ?",
                (watch_id,),
            ).fetchone()
            return self._public_watch(row) if row else None
        finally:
            conn.close()

    def record_reply_seen(
        self,
        watch_id: str,
        *,
        reply_seen_at_utc_iso: str | None = None,
        reply_ref: str = "",
    ) -> dict[str, Any]:
        seen_at = _parse_aware_iso(reply_seen_at_utc_iso).isoformat(timespec="seconds") if reply_seen_at_utc_iso else _utc_now_iso()
        conn = self._connect()
        try:
            current = conn.execute(
                "SELECT watch_id FROM client_followup_watches WHERE watch_id = ?",
                (watch_id,),
            ).fetchone()
            if current is None:
                raise ValueError(f"Unknown follow-up watch: {watch_id}")
            conn.execute(
                """
                UPDATE client_followup_watches
                SET status = 'closed_reply_seen',
                    delivery_confirmation_status = 'closed',
                    reply_seen_at_utc_iso = ?,
                    reply_ref = ?
                WHERE watch_id = ?
                """,
                (seen_at, str(reply_ref or ""), watch_id),
            )
            row = conn.execute(
                "SELECT * FROM client_followup_watches WHERE watch_id = ?",
                (watch_id,),
            ).fetchone()
            return self._public_watch(row)
        finally:
            conn.close()

    def record_reply_seen_for_invoice(
        self,
        *,
        client_ref: str,
        invoice_ref: str,
        reply_seen_at_utc_iso: str | None = None,
        reply_ref: str = "",
    ) -> list[dict[str, Any]]:
        client = str(client_ref or "").strip()
        invoice = str(invoice_ref or "").strip()
        if not client or not invoice:
            raise ValueError("client_ref and invoice_ref are required")
        seen_at = (
            _parse_aware_iso(reply_seen_at_utc_iso).isoformat(timespec="seconds")
            if reply_seen_at_utc_iso
            else _utc_now_iso()
        )
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE client_followup_watches
                SET status = 'closed_reply_seen',
                    delivery_confirmation_status = 'closed',
                    reply_seen_at_utc_iso = ?,
                    reply_ref = ?
                WHERE client_ref = ?
                  AND invoice_ref = ?
                """,
                (seen_at, str(reply_ref or ""), client, invoice),
            )
            rows = conn.execute(
                """
                SELECT *
                FROM client_followup_watches
                WHERE client_ref = ?
                  AND invoice_ref = ?
                ORDER BY sent_at_utc_iso ASC, watch_id ASC
                """,
                (client, invoice),
            ).fetchall()
            return [self._public_watch(row) for row in rows]
        finally:
            conn.close()

    def record_delivery_confirmation_and_preserve_payment_watch(
        self,
        *,
        watch_id: str,
        client_ref: str,
        invoice_ref: str,
        reply_seen_at_utc_iso: str,
        reply_ref: str,
    ) -> dict[str, Any]:
        """Close delivery confirmation while leaving payment receipt pending.

        Both loop states live on the existing invoice watch. No second watch,
        outbound proposal, or payment cadence is invented by this transition.
        """
        target_watch_id = str(watch_id or "").strip()
        client = str(client_ref or "").strip()
        invoice = str(invoice_ref or "").strip()
        evidence_ref = str(reply_ref or "").strip()
        if not target_watch_id or not client or not invoice or not evidence_ref:
            raise ValueError("watch_id, client_ref, invoice_ref, and reply_ref are required")
        seen_at = _parse_aware_iso(reply_seen_at_utc_iso).isoformat(timespec="seconds")
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT *
                FROM client_followup_watches
                WHERE watch_id = ?
                  AND client_ref = ?
                  AND invoice_ref = ?
                """,
                (target_watch_id, client, invoice),
            ).fetchone()
            if row is None:
                raise ValueError("delivery_confirmation_watch_not_found")
            if row["status"] == "closed_reply_seen":
                if (
                    row["delivery_confirmation_status"] == "closed"
                    and row["payment_received_status"] == "pending"
                    and row["reply_seen_at_utc_iso"] == seen_at
                    and row["reply_ref"] == evidence_ref
                ):
                    conn.execute("COMMIT")
                    public = self._public_watch(row)
                    return {
                        "evidence_ref": evidence_ref,
                        "watch": self._loop_state_only(public),
                        "followup_loops": public["followup_loops"],
                    }
                raise ValueError("delivery_confirmation_evidence_conflict")
            if (
                row["status"] != "active"
                or row["reply_seen_at_utc_iso"] is not None
                or str(row["reply_ref"] or "")
                or row["delivery_confirmation_status"] not in {None, "pending"}
                or row["payment_received_status"] not in {None, "pending"}
            ):
                raise ValueError("delivery_confirmation_watch_not_pristine")
            cursor = conn.execute(
                """
                UPDATE client_followup_watches
                SET status = 'closed_reply_seen',
                    delivery_confirmation_status = 'closed',
                    payment_received_status = 'pending',
                    reply_seen_at_utc_iso = ?,
                    reply_ref = ?
                WHERE watch_id = ?
                  AND client_ref = ?
                  AND invoice_ref = ?
                  AND status = 'active'
                  AND reply_seen_at_utc_iso IS NULL
                  AND reply_ref = ''
                  AND (delivery_confirmation_status IS NULL
                       OR delivery_confirmation_status = 'pending')
                  AND (payment_received_status IS NULL
                       OR payment_received_status = 'pending')
                """,
                (seen_at, evidence_ref, target_watch_id, client, invoice),
            )
            if cursor.rowcount != 1:
                raise ValueError("delivery_confirmation_guarded_update_failed")
            updated = conn.execute(
                """
                SELECT * FROM client_followup_watches
                WHERE watch_id = ? AND client_ref = ? AND invoice_ref = ?
                """,
                (target_watch_id, client, invoice),
            ).fetchone()
            conn.execute("COMMIT")
            public = self._public_watch(updated)
            return {
                "evidence_ref": evidence_ref,
                "watch": self._loop_state_only(public),
                "followup_loops": public["followup_loops"],
            }
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def due_followup_proposals(self, now_utc_iso: str) -> list[dict[str, Any]]:
        now = _parse_aware_iso(now_utc_iso).isoformat(timespec="seconds")
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT *
                FROM client_followup_watches
                WHERE status = 'active'
                  AND due_at_utc_iso <= ?
                ORDER BY due_at_utc_iso ASC, watch_id ASC
                """,
                (now,),
            ).fetchall()
            return [self._proposal_for_watch(self._public_watch(row), requested_at_utc=now) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def _public_watch(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "watch_id": row["watch_id"],
            "schema_version": FOLLOWUP_WATCH_SCHEMA_VERSION,
            "client_ref": row["client_ref"],
            "client_name": row["client_name"],
            "recipient": row["recipient"],
            "subject": row["subject"],
            "invoice_ref": row["invoice_ref"],
            "followup_loops": {
                "delivery_confirmation": row["delivery_confirmation_status"] or "unknown",
                "payment_received": row["payment_received_status"] or "unknown",
            },
            "sent_at_utc_iso": row["sent_at_utc_iso"],
            "days_without_reply": row["days_without_reply"],
            "due_at_utc_iso": row["due_at_utc_iso"],
            "status": row["status"],
            "created_at_utc_iso": row["created_at_utc_iso"],
            "reply_seen_at_utc_iso": row["reply_seen_at_utc_iso"],
            "reply_ref": row["reply_ref"],
        }

    @staticmethod
    def _loop_state_only(watch: Mapping[str, Any]) -> dict[str, Any]:
        """Return the non-PII state needed by business-truth receipts."""
        return {
            "watch_id": watch["watch_id"],
            "schema_version": watch["schema_version"],
            "client_ref": watch["client_ref"],
            "invoice_ref": watch["invoice_ref"],
            "status": watch["status"],
            "followup_loops": dict(watch["followup_loops"]),
            "reply_seen_at_utc_iso": watch["reply_seen_at_utc_iso"],
            "reply_ref": watch["reply_ref"],
        }

    def _proposal_for_watch(self, watch: Mapping[str, Any], *, requested_at_utc: str) -> dict[str, Any]:
        invoice_ref = str(watch.get("invoice_ref") or watch.get("subject") or "").strip()
        client_name = str(watch.get("client_name") or watch.get("client_ref") or "there").strip()
        copy_rules = voice_copy_rules_for_speaker("clara")
        workflow_ref = f"client_followup_watch:{watch['watch_id']}"
        closure = loop_closing_ask_for_workflow(
            workflow_ref,
            client_ref=str(watch.get("client_ref") or ""),
        )
        body = (
            "Hello,\n\n"
            + f"A quick check on invoice {invoice_ref}: I want to make sure it reached the right person."
            + "\n\n"
            + render_loop_closing_ask(closure)
            + "\n\n"
            + str(copy_rules["signoff"])
        )
        clara_conformance = require_clara_copy_conformance(
            body,
            workflow_ref=workflow_ref,
            client_ref=str(watch.get("client_ref") or ""),
        )
        voice_conformance = clara_conformance["voice_conformance"]
        draft = {
            "to": watch["recipient"],
            "subject": "Following up: " + str(watch["subject"]),
            "body": body,
        }
        proposal_id = "client_followup_proposal:" + _short_hash(
            {"watch_id": watch["watch_id"], "draft": draft}
        )
        approval_request = build_operator_action_approval_payload(
            action_type=ACTION_TYPE_EXACT_GMAIL_SEND,
            owner_agent="cassandra",
            owner_objective_id=proposal_id,
            request_id=f"operator_action:{proposal_id}",
            summary=f"Approve follow-up draft to {client_name}.",
            payload={
                **draft,
                "watch_id": watch["watch_id"],
                "voice_profile_ref": voice_conformance["voice_profile_ref"],
                "voice_conformance": voice_conformance,
                "loop_closing_ask_conformance": clara_conformance["loop_closing_ask"],
                "quiet_luxury_critic": clara_conformance["quiet_luxury_critic"],
                "authority_boundary": dict(AUTHORITY_BOUNDARY_PROPOSAL),
            },
            risk_warning="Follow-up draft is proposal-only. SEND_HOLD and Guardian/operator approval are required before any send.",
            expires_at=_expires_at(requested_at_utc),
            route_back={
                "module": "email_send_executor",
                "function": "execute_email_send_packet",
                "proposal_id": proposal_id,
            },
            authority_refs=("OPENCLAW_RUNTIME.md#send-hold",),
            risk_tier="high",
        )
        return {
            "schema_version": FOLLOWUP_PROPOSAL_SCHEMA_VERSION,
            "status": "FOLLOW_UP_PROPOSAL_READY",
            "proposal_id": proposal_id,
            "watch_id": watch["watch_id"],
            "client_ref": watch["client_ref"],
            "client_name": watch["client_name"],
            "due_at_utc_iso": watch["due_at_utc_iso"],
            "draft": draft,
            "voice_profile_ref": voice_conformance["voice_profile_ref"],
            "voice_conformance": voice_conformance,
            "loop_closing_ask_conformance": clara_conformance["loop_closing_ask"],
            "quiet_luxury_critic": clara_conformance["quiet_luxury_critic"],
            "approval_request": approval_request,
            "gated": True,
            "send_performed": False,
            "authority_boundary": dict(AUTHORITY_BOUNDARY_PROPOSAL),
        }


__all__ = [
    "AUTHORITY_BOUNDARY_PROPOSAL",
    "ClientFollowupWatchStore",
    "DEFAULT_FOLLOWUP_DB_PATH",
    "FOLLOWUP_PROPOSAL_SCHEMA_VERSION",
    "FOLLOWUP_WATCH_SCHEMA_VERSION",
]

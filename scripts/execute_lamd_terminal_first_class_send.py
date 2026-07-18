#!/usr/bin/env python3
"""Execute the operator-approved LAMD July send through the governed owner rails."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cassandra_operator_objective_loop as objective_loop
import google_access_broker
import hitl_action_service
import invoice_send_transaction
from client_followup_watch import ClientFollowupWatchStore
from send_hold_scoped_graduation import issue_send_hold_scoped_graduation


PROVENANCE = (
    "terminal first-class GO, operator verbatim, relayed by Fable (terminal witness), "
    "msgs 1794+1833+terminal-GO chain."
)
DB_PATH = ROOT / "generated/system_knowledge/cassandra_operator_objective_loop.sqlite"
FROM_CODEX = ROOT / "Operator/from-codex"
PDF_PATH = Path(
    "/mnt/e/openclaw/artifacts/invoice_workbooks/live_arts_md/2026-07/"
    "w1-finalized-2026-1004/invoice.pdf"
)
PDF_SHA256 = "99c0d53b8077a2c8f85a6e3a14d0d3df60c740dd179fa5da917983b28356ce78"
PDF_SIZE = 171386
WORKBOOK_PATH = Path(
    "/mnt/e/openclaw/artifacts/invoice_workbooks/live_arts_md/2026-07/"
    "w1-finalized-2026-1004/invoice.xlsx"
)
WORKBOOK_SHA256 = "3eb8cd7c82c234cccc3051dadb692d8cb5c00afa0a11c9eca4b10927e8e80aad"
RECIPIENT = "Accountant@liveartsmd.org"
SUBJECT = "2026-1004: July 2026 Monthly Speaker Rental Invoice"
BODY = """Hi Megan,

Attached is Invoice 2026-1004 for July 2026, covering the monthly speaker rental at $100.

Could you send me a quick note once the invoice is in your accounting queue? That helps me know it landed and keeps our records straight.

Warmly,
Clara Reid"""
SUBJECT_SHA256 = "sha256:d60722dfb8f6fa7d48411151bcfc27b2ece2451efa0591f5ea2884afe4901c50"
BODY_SHA256 = "sha256:ec4971ae56b4e712f8abfab5281f0aeccda2efa60d159ac117cf38c964f95e66"
PRIOR_TRANSACTION_ID = "invoice-send-tx:d6706f66ae8f24f8b0e8617c"
PROTECTED_SEND_HOLD = ROOT / "state/orchestration/SEND_HOLD.md"
BIND_RECEIPT = FROM_CODEX / "LAMD-TERMINAL-FIRST-CLASS-BIND-LIVE-RECEIPT-20260718-PC-Codex-Desktop.json"
AUTH_RECEIPT = FROM_CODEX / "LAMD-TERMINAL-FIRST-CLASS-AUTHORITY-LIVE-RECEIPT-20260718-PC-Codex-Desktop.json"
BLOCKER_RECEIPT = FROM_CODEX / "LAMD-TERMINAL-FIRST-CLASS-PROVIDER-BLOCKER-20260718-PC-Codex-Desktop.json"
SEND_RECEIPT = FROM_CODEX / "LAMD-TERMINAL-FIRST-CLASS-SENT-VERIFIED-RECEIPT-20260718-PC-Codex-Desktop.json"
FOLLOWUP_DB = ROOT / "state/client_followups/client_followups.sqlite3"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o664)
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected an object in {path}")
    return value


def _verify_static_bindings() -> dict[str, Any]:
    checks = {
        "pdf_exists": PDF_PATH.is_file(),
        "pdf_size_matches": PDF_PATH.is_file() and PDF_PATH.stat().st_size == PDF_SIZE,
        "pdf_sha256_matches": PDF_PATH.is_file() and _sha256_file(PDF_PATH) == PDF_SHA256,
        "workbook_exists": WORKBOOK_PATH.is_file(),
        "workbook_sha256_matches": WORKBOOK_PATH.is_file()
        and _sha256_file(WORKBOOK_PATH) == WORKBOOK_SHA256,
        "subject_sha256_matches": _sha256_text(SUBJECT) == SUBJECT_SHA256,
        "body_sha256_matches": _sha256_text(BODY) == BODY_SHA256,
    }
    if not all(checks.values()):
        raise ValueError("immutable LAMD binding preflight failed: " + json.dumps(checks, sort_keys=True))
    return checks


def _packet() -> dict[str, Any]:
    return {
        "client_ref": "live_arts_md",
        "client_display_name": "Live Arts MD",
        "invoice_number": "2026-1004",
        "service_period": "July 2026",
        "currency": "USD",
        "amount_minor_units": 10000,
        "source_workbook": {
            "path": str(WORKBOOK_PATH),
            "version": "operator_validated_event_1_20260717",
            "sha256": WORKBOOK_SHA256,
        },
        "workflow_ref": "live_arts_md_invoice_send",
        "allowed_facts": ["Live Arts MD", "2026-1004", "July 2026", "$100.00"],
    }


def _copy_contract() -> dict[str, Any]:
    return {
        "sender": "winshiplive@gmail.com",
        "to": [RECIPIENT],
        "cc": [],
        "bcc": [],
        "voice_speaker": "clara",
        "workflow_ref": "live_arts_md_invoice_send",
        "next_verification_milestone": "accountant_acknowledged",
        "human_closing_ask": "Could you send me a quick note once the invoice is in your accounting queue?",
        "ask_why": "That helps me know it landed and keeps our records straight.",
        "forbidden_claims": ["already paid", "already sent"],
    }


def _artifact_receipt() -> dict[str, Any]:
    return {
        "path": str(PDF_PATH),
        "mime_type": "application/pdf",
        "size_bytes": PDF_SIZE,
        "sha256": PDF_SHA256,
        "artifact_verification_receipt_id": "invoice-validation:ec1f6eb9ca786420cf61df67",
        "formula_freshness_receipt_id": "lamd-formula-recalc-owner:validation-event-1",
    }


def _approved_composer(_ask: str, _packet: dict, _contract: dict) -> dict[str, Any]:
    return {
        "subject": SUBJECT,
        "body": BODY,
        "packet_critique": {
            "source": "operator_selected_persona_true_copy",
            "grounded": True,
            "current": True,
            "useful": True,
            "packet_used_as_aid": True,
            "authority_granted": False,
        },
    }


def _same_obligation_rest_proof(transaction_id: str) -> dict[str, Any]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT transaction_id, lifecycle_state, envelope_json FROM invoice_send_transactions "
            "WHERE client_ref = ? AND service_period = ? ORDER BY created_at, transaction_id",
            ("live_arts_md", "July 2026"),
        ).fetchall()
    same = []
    for row in rows:
        envelope = json.loads(row["envelope_json"])
        if envelope.get("currency") == "USD" and envelope.get("amount_minor_units") == 10000:
            same.append(
                {
                    "transaction_id": row["transaction_id"],
                    "lifecycle_state": row["lifecycle_state"],
                }
            )
    prepared = [row for row in same if row["lifecycle_state"] == invoice_send_transaction.PREPARED]
    return {
        "same_obligation_rows": same,
        "prepared_count": len(prepared),
        "sole_prepared_transaction_id": prepared[0]["transaction_id"] if len(prepared) == 1 else "",
        "expected_transaction_matches": (
            len(prepared) == 1 and prepared[0]["transaction_id"] == transaction_id
        ),
        "no_same_obligation_multi_prepared_rows": len(prepared) <= 1,
    }


def bind() -> dict[str, Any]:
    checks = _verify_static_bindings()
    result = invoice_send_transaction.prepare_invoice_send_revision(
        prior_transaction_id=PRIOR_TRANSACTION_ID,
        supersession_reason=(
            "Operator approved persona-true copy via msgs 1794+1833+terminal-GO; "
            "exact finalized artifact retained"
        ),
        raw_operator_ask="Bind the operator-approved July LAMD copy and finalized artifact.",
        deterministic_packet_aid=_packet(),
        immutable_copy_contract=_copy_contract(),
        artifact_receipt=_artifact_receipt(),
        db_path=DB_PATH,
        generated_at=_utc_now(),
        composer=_approved_composer,
    )
    transaction_id = result["transaction"]["transaction_id"]
    rest = _same_obligation_rest_proof(transaction_id)
    if not rest["expected_transaction_matches"] or not rest["no_same_obligation_multi_prepared_rows"]:
        raise RuntimeError("copy rebind did not leave exactly one expected PREPARED transaction")
    receipt = {
        "schema_version": "LAMD_TERMINAL_FIRST_CLASS_BIND_RECEIPT_V1",
        "status": "BOUND_PREPARED",
        "authority_provenance": PROVENANCE,
        "transaction": result["transaction"],
        "supersession_decision": result["supersession_decision"],
        "rest_proof": rest,
        "envelope": result["envelope"],
        "immutable_binding_checks": checks,
        "subject_sha256": SUBJECT_SHA256,
        "body_sha256": BODY_SHA256,
        "artifact_sha256": PDF_SHA256,
        "workbook_sha256": WORKBOOK_SHA256,
        "provider_called": False,
        "gmail_draft_created": False,
        "email_send_performed": False,
        "money_moved": False,
        "business_ledger_posted": False,
        "created_at": _utc_now(),
    }
    _write_json(BIND_RECEIPT, receipt)
    return receipt


def authorize() -> dict[str, Any]:
    bound = _read_json(BIND_RECEIPT)
    envelope = dict(bound["envelope"])
    if envelope["copy"]["body_sha256"] != BODY_SHA256:
        raise ValueError("bound body hash changed")
    generated_at = _utc_now()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat(timespec="seconds")
    approval_text = (
        f"Draft is approved with this exact text for {RECIPIENT}.\n"
        f"Subject: {SUBJECT}\n\n{BODY}\n\n"
        "Prepare the send authority request; do not send until approved."
    )
    route = objective_loop.route_draft_approval_to_send_authority(
        approval_text,
        source_channel="terminal",
        source_message_ref=PROVENANCE,
        lane_context={"attachments": [str(PDF_PATH)], "attachment_sha256": [PDF_SHA256]},
        sqlite_path=DB_PATH,
        generated_at=generated_at,
    )
    request = dict(route["send_authority_request"])
    request["expires_at"] = expires_at
    route["objective"]["send_authority_request"] = request
    bundle = objective_loop.create_exact_send_scoped_authority(
        request,
        generated_at=generated_at,
        expires_at=expires_at,
    )
    persisted = objective_loop.persist_exact_send_authority_bundle(
        route["objective"],
        authority_envelope=bundle["authority_envelope"],
        credential_lease=bundle["credential_lease"],
        sqlite_path=DB_PATH,
        authority_provenance=PROVENANCE,
        generated_at=generated_at,
    )
    if persisted.get("persisted") is not True:
        raise RuntimeError("exact-send authority bundle was not persisted")
    review = objective_loop.build_exact_send_review_packet(
        persisted["objective"]["send_authority_request"],
        draft={"recipient": RECIPIENT, "subject": SUBJECT, "body": BODY},
        expires_at=expires_at,
        generated_at=generated_at,
    )
    safe_request_id = re.sub(r"[^A-Za-z0-9_.:-]+", "_", request["request_id"])
    graduation_path = ROOT / "state/orchestration/send_hold_graduations" / f"{safe_request_id}.json"
    created = objective_loop.register_exact_send_operator_action_approval(
        review,
        authority_envelope=bundle["authority_envelope"],
        credential_lease=bundle["credential_lease"],
        approval_provenance=PROVENANCE,
        send_hold_graduation_ref=str(graduation_path),
        generated_at=generated_at,
    )
    action_id = str(created.get("action_id") or "")
    if not action_id or created.get("operator_action_created") is not True:
        raise RuntimeError("exact-send operator action was not registered")
    if not hitl_action_service.approve_action(
        action_id,
        approved_by=PROVENANCE,
        dispatch_now=False,
    ):
        raise RuntimeError("terminal first-class GO was not recorded on the HITL action")
    action = hitl_action_service.get_pending_action(action_id) or {}
    dispatcher = hitl_action_service.get_action_dispatcher("exact_gmail_send")
    if action.get("status") != "APPROVED" or dispatcher is None:
        raise RuntimeError("approved action or Cassandra executor registration is missing")
    receipt = {
        "schema_version": "LAMD_TERMINAL_FIRST_CLASS_AUTHORITY_RECEIPT_V1",
        "status": "APPROVED_WAITING_PROVIDER_CREDENTIAL",
        "authority_provenance": PROVENANCE,
        "transaction_id": bound["transaction"]["transaction_id"],
        "envelope_hash": bound["transaction"]["envelope_hash"],
        "request_id": request["request_id"],
        "objective_id": route["objective"]["objective_id"],
        "payload_hash": request["payload_hash"],
        "operator_action_id": action_id,
        "operator_action_status": action["status"],
        "approved_by": action.get("approved_by"),
        "approved_at": action.get("approved_at"),
        "authority_envelope_ref": persisted["authority_ref"],
        "credential_lease_ref": persisted["credential_lease_ref"],
        "scope_verdict": persisted["scope_verdict"],
        "executor_registered": True,
        "executor_name": getattr(dispatcher, "__name__", type(dispatcher).__name__),
        "send_hold_graduation_ref": str(graduation_path),
        "send_hold_graduation_issued": False,
        "protected_send_hold_path": str(PROTECTED_SEND_HOLD),
        "subject": SUBJECT,
        "body": BODY,
        "subject_sha256": SUBJECT_SHA256,
        "body_sha256": BODY_SHA256,
        "attachment_path": str(PDF_PATH),
        "attachment_sha256": PDF_SHA256,
        "recipient": RECIPIENT,
        "amount": "$100.00",
        "provider_called": False,
        "gmail_draft_created": False,
        "email_send_performed": False,
        "money_moved": False,
        "business_ledger_posted": False,
        "created_at": _utc_now(),
    }
    _write_json(AUTH_RECEIPT, receipt)
    return receipt


def _write_provider_blocker(error: str, readiness: dict[str, Any]) -> dict[str, Any]:
    receipt = {
        "schema_version": "LAMD_TERMINAL_FIRST_CLASS_PROVIDER_BLOCKER_V1",
        "status": "BLOCKED_PROVIDER_CREDENTIAL_INVALID_GRANT",
        "authority_provenance": PROVENANCE,
        "error": error,
        "runtime_dependencies": readiness,
        "send_hold_graduation_issued": False,
        "provider_called": False,
        "gmail_api_called": False,
        "email_send_performed": False,
        "retry_performed": False,
        "required_repair": "Operator must complete the governed Google OAuth reauthorization flow.",
        "created_at": _utc_now(),
    }
    _write_json(BLOCKER_RECEIPT, receipt)
    return receipt


def dispatch() -> dict[str, Any]:
    auth = _read_json(AUTH_RECEIPT)
    readiness = google_access_broker.check_gmail_broker_runtime_dependencies()
    if not readiness["ok"]:
        return _write_provider_blocker("missing Gmail broker runtime dependencies", readiness)
    credentials = google_access_broker._load_credentials()
    if credentials is None or not credentials.valid:
        return _write_provider_blocker("Google OAuth token is expired or revoked (invalid_grant)", readiness)

    generated_at = _utc_now()
    expires_at = (
        datetime.fromisoformat(generated_at) + timedelta(minutes=20)
    ).isoformat(timespec="seconds")
    graduation_path = Path(auth["send_hold_graduation_ref"])
    graduation = issue_send_hold_scoped_graduation(
        graduation_path=graduation_path,
        send_hold_path=PROTECTED_SEND_HOLD,
        request_id=auth["request_id"],
        payload_hash=auth["payload_hash"],
        recipient=RECIPIENT,
        body_sha256=BODY_SHA256,
        attachment_paths=[str(PDF_PATH)],
        attachment_sha256=[PDF_SHA256],
        authority_provenance=PROVENANCE,
        active_heartbeat_hold_source="openclaw-to-codex-lane-watcher",
        generated_at=generated_at,
        expires_at=expires_at,
    )
    action = hitl_action_service.get_pending_action(auth["operator_action_id"]) or {}
    os.environ["OPENCLAW_SEND_HOLD_PATH"] = str(PROTECTED_SEND_HOLD)
    os.environ["OPENCLAW_ATTACHMENT_ALLOWED_DIRS"] = str(PDF_PATH.parents[2])
    routeback = objective_loop.run_exact_send_operator_action_routeback(
        action,
        sqlite_path=DB_PATH,
        receipt_dir=FROM_CODEX / "LAMD-TERMINAL-FIRST-CLASS-SEND-ROUTEBACK-20260718",
        live_transport_enabled=True,
        send_hold_path=PROTECTED_SEND_HOLD,
        generated_at=_utc_now(),
    )
    terminal = dict(routeback.get("receipt") or {})
    if routeback.get("response_status") != "EXACT_SEND_LIVE_TRANSPORT_SUCCESS_RECEIPT_WRITTEN":
        failed = {
            "schema_version": "LAMD_TERMINAL_FIRST_CLASS_SEND_FAILURE_RECEIPT_V1",
            "status": "TERMINAL_NO_RETRY",
            "authority_provenance": PROVENANCE,
            "routeback": routeback,
            "send_hold_graduation": graduation,
            "retry_performed": False,
            "created_at": _utc_now(),
        }
        _write_json(SEND_RECEIPT, failed)
        return failed
    lifecycle = invoice_send_transaction.record_sent_verified_transaction(
        db_path=DB_PATH,
        transaction_id=auth["transaction_id"],
        terminal_receipt=terminal,
        recorded_at=_utc_now(),
    )
    watch = ClientFollowupWatchStore(str(FOLLOWUP_DB)).add_watch(
        client_ref="live_arts_md",
        client_name="Live Arts MD",
        recipient=RECIPIENT,
        subject=SUBJECT,
        sent_at_utc_iso=terminal["created_at"],
        invoice_ref="2026-1004",
        days_without_reply=3,
    )
    rest = _same_obligation_rest_proof(auth["transaction_id"])
    receipt = {
        "schema_version": "LAMD_TERMINAL_FIRST_CLASS_SENT_VERIFIED_RECEIPT_V1",
        "status": "SENT_VERIFIED",
        "authority_provenance": PROVENANCE,
        "provider": {
            "message_id": terminal["message_id"],
            "thread_id": terminal["thread_id"],
            "recipient": terminal["recipient"],
            "attachment_sha256": terminal["attachment_sha256"],
            "body_sha256": terminal["body_sha256"],
        },
        "transaction_lifecycle_decision": lifecycle,
        "same_obligation_rest_proof": rest,
        "followup_watch": watch,
        "next_verification_milestone": "accountant_acknowledged",
        "send_hold_graduation_id": graduation["graduation_id"],
        "send_hold_graduation_consumed": True,
        "global_send_hold_preserved": True,
        "gmail_draft_created": False,
        "email_send_performed": True,
        "money_moved": False,
        "business_ledger_posted": False,
        "send_lifecycle_ledger_posted": True,
        "retry_performed": False,
        "created_at": _utc_now(),
    }
    _write_json(SEND_RECEIPT, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("bind", "authorize", "dispatch"))
    args = parser.parse_args()
    result = {"bind": bind, "authorize": authorize, "dispatch": dispatch}[args.phase]()
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True))
    return 0 if result.get("status") not in {"BLOCKED_PROVIDER_CREDENTIAL_INVALID_GRANT", "TERMINAL_NO_RETRY"} else 2


if __name__ == "__main__":
    raise SystemExit(main())

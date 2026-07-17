#!/usr/bin/env python3
"""Execute LAMD validation event 1 through exact-byte promotion and signed HITL."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cassandra_operator_objective_loop
import hitl_action_service
import hitl_notification_service
import invoice_send_transaction
import invoice_validation_promotion


def _stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_receipt(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    temporary.write_text(_stable_json(payload), encoding="utf-8")
    os.replace(temporary, path)


def _transaction_rest_proof(db_path: Path, transaction_id: str) -> dict[str, Any]:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT transaction_id, attachment_sha256, lifecycle_state
              FROM invoice_send_transactions
             WHERE client_ref = ? AND invoice_number = ?
             ORDER BY created_at
            """,
            ("live_arts_md", "2026-1004"),
        ).fetchall()
        prepared = [dict(row) for row in rows if row["lifecycle_state"] == invoice_send_transaction.PREPARED]
        decision_count = conn.execute(
            "SELECT count(*) FROM invoice_send_transaction_decisions WHERE superseded_by_transaction_id = ?",
            (transaction_id,),
        ).fetchone()[0]
    if len(prepared) != 1 or prepared[0]["transaction_id"] != transaction_id:
        raise RuntimeError("same-obligation transaction store does not have exactly one successor PREPARED row")
    return {
        "same_obligation_rows": [dict(row) for row in rows],
        "prepared_count": len(prepared),
        "sole_prepared_transaction_id": transaction_id,
        "successor_decision_count": decision_count,
    }


def _prepare_fresh_transaction(
    *,
    db_path: Path,
    candidate_workbook: Path,
    package_dir: Path,
    validation: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    artifact = package_dir / "invoice.pdf"
    packet = {
        "client_ref": "live_arts_md",
        "client_display_name": "Live Arts MD",
        "invoice_number": "2026-1004",
        "service_period": "July 2026",
        "currency": "USD",
        "amount_minor_units": 10000,
        "source_workbook": {
            "path": candidate_workbook.as_posix(),
            "version": "operator_validated_event_1_20260717",
            "sha256": _sha256(candidate_workbook),
        },
        "workflow_ref": "live_arts_md_invoice_send",
        "allowed_facts": ["Live Arts MD", "2026-1004", "July 2026", "$100.00"],
    }
    contract = {
        "sender": "winshiplive@gmail.com",
        "to": ["Accountant@liveartsmd.org"],
        "cc": [],
        "bcc": [],
        "voice_speaker": "clara",
        "workflow_ref": "live_arts_md_invoice_send",
        "next_verification_milestone": "accountant_acknowledged",
        "human_closing_ask": "Could you send me a quick note once the invoice is in your accounting queue?",
        "ask_why": "That helps me know it landed and keeps our records straight.",
        "forbidden_claims": ["already paid", "already sent"],
    }
    artifact_receipt = {
        "path": artifact.as_posix(),
        "mime_type": "application/pdf",
        "size_bytes": artifact.stat().st_size,
        "sha256": validation["artifact_sha256"],
        "artifact_verification_receipt_id": validation["event_id"],
        "formula_freshness_receipt_id": "w1-prior-balance-formula-fixed-real-excel-20260717",
    }
    return cassandra_operator_objective_loop.route_cassandra_objective_message(
        "Prepare the exact operator-validated July Live Arts invoice envelope. Do not send anything.",
        source_channel="validation_event",
        source_message_ref=validation["operator_message_ref"],
        lane_context={
            "target_world_ref": "finance",
            "target_thread_ref": "live_arts_md",
            "deterministic_invoice_packet": packet,
            "immutable_copy_contract": contract,
            "artifact_receipt": artifact_receipt,
        },
        sqlite_path=db_path,
        generated_at=generated_at,
    )


def _create_send_approval(
    *,
    route: dict[str, Any],
    validation: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    transaction = route["invoice_prepare"]["transaction"]
    envelope = route["invoice_prepare"]["envelope"]
    objective_id = route["objective"]["objective_id"]
    transaction_id = transaction["transaction_id"]
    request_id = "exact_send_authority_request:" + transaction_id.rsplit(":", 1)[-1]
    expires_at = (datetime.fromisoformat(generated_at) + timedelta(hours=24)).isoformat()
    operator_eli5 = (
        "July Live Arts invoice 2026-1004, $100, to Accountant@liveartsmd.org - "
        "the exact version you just approved. Tap approve to send."
    )
    action = hitl_action_service.create_operator_action_approval_request(
        action_type=hitl_action_service.ACTION_TYPE_EXACT_GMAIL_SEND,
        owner_agent="guardian",
        owner_objective_id=objective_id,
        request_id=request_id,
        summary=operator_eli5,
        payload={
            "recipient": "Accountant@liveartsmd.org",
            "amount": "$100.00",
            "invoice_number": "2026-1004",
            "transaction_id": transaction_id,
            "subject": envelope["copy"]["subject"],
            "payload_hash": transaction["envelope_hash"],
            "request_id": request_id,
            "objective_id": objective_id,
            "expires_at": expires_at,
            "artifact_sha256": validation["artifact_sha256"],
            "validation_event_id": validation["event_id"],
            "operator_eli5": operator_eli5,
            "body_stored_in_hitl_queue": False,
            "send_hold_required": True,
        },
        risk_warning="Approval authorizes one exact invoice send; SEND_HOLD remains an independent hard stop.",
        expires_at=expires_at,
        route_back={
            "type": "cassandra_exact_send_executor",
            "objective_id": objective_id,
            "request_id": request_id,
            "transaction_id": transaction_id,
            "executor_must_use_reviewed_gate": True,
            "guardian_calls_gmail_or_broker_directly": False,
        },
        authority_refs=[validation["event_id"], transaction["envelope_hash"]],
        risk_tier="high",
        ttl_seconds=24 * 60 * 60,
    )
    return action


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-pdf", type=Path, required=True)
    parser.add_argument("--candidate-workbook", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--prior-transaction-id", required=True)
    parser.add_argument("--validation-receipt", type=Path, required=True)
    parser.add_argument("--promotion-receipt", type=Path, required=True)
    parser.add_argument("--chain-receipt", type=Path, required=True)
    parser.add_argument("--validated-at", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--notify", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if not args.confirm:
        parser.error("--confirm is required")
    if _sha256(args.candidate_pdf) != args.expected_sha256.lower():
        raise RuntimeError("candidate PDF differs from the operator-validated SHA-256")

    validation = invoice_validation_promotion.record_invoice_validation_event(
        db_path=args.db,
        client_ref="live_arts_md",
        service_period="2026-07",
        invoice_number="2026-1004",
        artifact_sha256=args.expected_sha256,
        operator_message_ref="telegram:operator_maestro_chat:1794",
        operator_message_text="That looks perfect.",
        surface_ref="operator_maestro_chat",
        validated_at=args.validated_at,
    )
    _write_receipt(args.validation_receipt, validation)

    promotion = invoice_validation_promotion.publish_validated_invoice_package(
        candidate_pdf=args.candidate_pdf,
        candidate_workbook=args.candidate_workbook,
        package_dir=args.package_dir,
        registry_path=args.registry,
        validation_receipt=validation,
        published_at=args.generated_at,
    )
    _write_receipt(args.promotion_receipt, promotion)

    route = _prepare_fresh_transaction(
        db_path=args.db,
        candidate_workbook=args.candidate_workbook,
        package_dir=args.package_dir,
        validation=validation,
        generated_at=args.generated_at,
    )
    if route.get("response_status") != "CASSANDRA_INVOICE_ENVELOPE_PREPARED":
        raise RuntimeError("Cassandra did not prepare the fresh validated envelope")
    successor_id = route["invoice_prepare"]["transaction"]["transaction_id"]
    decision = invoice_send_transaction.supersede_prepared_transaction(
        db_path=args.db,
        transaction_id=args.prior_transaction_id,
        superseded_by_transaction_id=successor_id,
        reason="Operator validation event 1 promotes the exact prior-balance-fixed artifact",
        decided_at=args.generated_at,
    )
    rest_proof = _transaction_rest_proof(args.db, successor_id)
    action = _create_send_approval(route=route, validation=validation, generated_at=args.generated_at)
    guardian_delivered = False
    if args.notify and action.get("created") is True:
        guardian_delivered = hitl_notification_service.send_pending_notification(action["action_id"])

    chain = {
        "schema_version": "lamd_validation_event_1_chain_receipt_v1",
        "status": "VALIDATED_FINALIZED_ENVELOPE_PREPARED_GUARDIAN_PENDING",
        "generated_at": args.generated_at,
        "validation": validation,
        "promotion": promotion,
        "fresh_transaction": route["invoice_prepare"]["transaction"],
        "supersession_decision": decision,
        "transaction_rest_proof": rest_proof,
        "guardian_action": action,
        "guardian_delivered": guardian_delivered,
        "send_hold_present": Path("/mnt/e/openclaw/orchestration/SEND_HOLD.md").is_file(),
        "provider_draft_created": False,
        "business_send_performed": False,
        "money_moved": False,
        "business_ledger_posted": False,
    }
    _write_receipt(args.chain_receipt, chain)
    print(_stable_json(chain), end="")
    return 0 if guardian_delivered or not args.notify else 1


if __name__ == "__main__":
    raise SystemExit(main())

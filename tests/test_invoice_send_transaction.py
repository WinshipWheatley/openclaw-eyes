from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import invoice_send_transaction as waist


FIXED_NOW = "2026-07-17T16:00:00+00:00"


def _inputs(tmp_path: Path) -> tuple[dict, dict, dict]:
    artifact = tmp_path / "lamd-july-canary.pdf"
    artifact.write_bytes(b"%PDF-1.4\nW0 no-send canary\n")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    packet = {
        "client_ref": "live_arts_md",
        "client_display_name": "Live Arts MD",
        "invoice_number": "LAMD-W0-CANARY",
        "service_period": "July 2026",
        "currency": "USD",
        "amount_minor_units": 10000,
        "source_workbook": {
            "path": "/mnt/c/OpenClawFinance/Invoice Live Arts MD.xlsx",
            "version": "operator_truth_20260717",
            "sha256": "a" * 64,
        },
        "workflow_ref": "live_arts_md_invoice_send",
        "allowed_facts": ["Live Arts MD", "LAMD-W0-CANARY", "July 2026", "$100.00"],
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
        "path": str(artifact),
        "mime_type": "application/pdf",
        "size_bytes": artifact.stat().st_size,
        "sha256": digest,
        "artifact_verification_receipt_id": "w0-canary-artifact-verified",
        "formula_freshness_receipt_id": "w0-canary-formula-not-applicable",
    }
    return packet, contract, artifact_receipt


def test_immutable_envelope_and_transaction_are_idempotent_and_no_send(tmp_path: Path) -> None:
    packet, contract, artifact = _inputs(tmp_path)
    copy = waist.compose_invoice_copy(
        "Prepare the July Live Arts invoice envelope without sending anything.", packet, contract
    )
    envelope = waist.assemble_invoice_send_envelope(
        raw_operator_ask="Prepare the July Live Arts invoice envelope without sending anything.",
        deterministic_packet_aid=packet,
        immutable_copy_contract=contract,
        copy_result=copy,
        artifact_receipt=artifact,
        generated_at=FIXED_NOW,
    )

    with pytest.raises(FrozenInstanceError):
        envelope.envelope_hash = "changed"  # type: ignore[misc]

    first = waist.record_prepared_transaction(envelope, db_path=tmp_path / "objectives.sqlite")
    second = waist.record_prepared_transaction(envelope, db_path=tmp_path / "objectives.sqlite")

    assert first["lifecycle_state"] == "PREPARED"
    assert first["created"] is True
    assert second["created"] is False
    assert second["idempotent_replay"] is True
    payload = envelope.to_dict()
    assert payload["authority_boundary"]["email_send_performed"] is False
    assert payload["authority_boundary"]["gmail_draft_created"] is False
    assert payload["approval"]["authority_granted"] is False
    assert payload["provider_draft"]["draft_id"] is None
    assert payload["copy"]["body_sha256"] == copy["immutable_input_hashes"]["candidate_body"]

    with sqlite3.connect(tmp_path / "objectives.sqlite") as conn:
        assert conn.execute("SELECT count(*) FROM invoice_send_transactions").fetchone()[0] == 1


def test_semantic_collision_with_changed_recipient_fails_closed(tmp_path: Path) -> None:
    packet, contract, artifact = _inputs(tmp_path)
    first = waist.prepare_invoice_send(
        raw_operator_ask="Prepare this invoice without sending.",
        deterministic_packet_aid=packet,
        immutable_copy_contract=contract,
        artifact_receipt=artifact,
        db_path=tmp_path / "objectives.sqlite",
        generated_at=FIXED_NOW,
    )
    changed_contract = {**contract, "to": ["someone-else@example.com"]}

    with pytest.raises(waist.InvoiceEnvelopeError, match="semantic transaction collision"):
        waist.prepare_invoice_send(
            raw_operator_ask="Prepare this invoice without sending.",
            deterministic_packet_aid=packet,
            immutable_copy_contract=changed_contract,
            artifact_receipt=artifact,
            db_path=tmp_path / "objectives.sqlite",
            generated_at=FIXED_NOW,
        )
    assert first["transaction"]["created"] is True


def test_router_composer_must_preserve_truth_voice_and_human_closing_ask(tmp_path: Path) -> None:
    packet, contract, _ = _inputs(tmp_path)

    def bad_composer(_ask, _packet, _contract):
        return {
            "subject": "DRAFT Live Arts MD invoice LAMD-W0-CANARY",
            "body": "Live Arts MD already paid $900.00. Workflow milestone complete.",
            "packet_critique": {"score": 99},
        }

    with pytest.raises(waist.InvoiceCopyConformanceError):
        waist.compose_invoice_copy("Prepare the invoice.", packet, contract, composer=bad_composer)

    wrong_speaker = {**contract, "voice_speaker": "openclaw"}
    with pytest.raises(waist.InvoiceCopyConformanceError, match="Clara"):
        waist.compose_invoice_copy("Prepare the invoice.", packet, wrong_speaker)


def test_artifact_hash_mismatch_fails_before_transaction_write(tmp_path: Path) -> None:
    packet, contract, artifact = _inputs(tmp_path)
    artifact["sha256"] = "0" * 64

    with pytest.raises(waist.InvoiceEnvelopeError, match="artifact sha256"):
        waist.prepare_invoice_send(
            raw_operator_ask="Prepare without sending.",
            deterministic_packet_aid=packet,
            immutable_copy_contract=contract,
            artifact_receipt=artifact,
            db_path=tmp_path / "objectives.sqlite",
            generated_at=FIXED_NOW,
        )
    assert not (tmp_path / "objectives.sqlite").exists()

import json
import sqlite3
from pathlib import Path

import pytest

import st_annes_invoice_status as status


FIXED_NOW = "2026-06-01T21:30:00+00:00"


def _write_pdf(path: Path) -> str:
    content = b"%PDF-1.4\n% fake one-page pdf for hash-only tests\n"
    path.write_bytes(content)
    return status.sha256_file(path)


def _receipt_payload(pdf_sha: str) -> dict:
    return {
        "artifact_kind": "operator_provided_pdf_invoice",
        "client_ref": "st_annes",
        "email_send_allowed": False,
        "generated_at": "2026-06-01T21:12:57+00:00",
        "invoice_period": "2026-05",
        "ledger_posting_allowed": False,
        "line_item_checks": {
            "may_10_adult_forum": True,
            "may_16_wedding": True,
            "may_25_funeral": True,
            "may_31_church_service": True,
            "may_services_due_500": True,
            "rate_125": True,
        },
        "line_items_verified": True,
        "manual_send_out_of_band_known": True,
        "may_service_subtotal_observed": True,
        "page_count": 1,
        "paid": False,
        "pdf_export_performed_by_openclaw": False,
        "prior_balance_observed": True,
        "provider_decision": "local_only",
        "sent_by_openclaw": False,
        "sha256": pdf_sha,
        "source_sha256": pdf_sha,
        "source_workbook_mutated_by_openclaw": False,
        "status": "MANUAL_SEND_OUT_OF_BAND_RECORDED",
        "total_outstanding_observed": True,
    }


def _corrected_receipt_payload(source_path: Path, source_sha: str) -> dict:
    return {
        "schema_version": "st_annes_external_agent_corrected_send_receipt_v1",
        "receipt_ref": "external-agent-send:gmail:19f7054d2e151aa4",
        "client_ref": "st_annes",
        "invoice_period": "2026-06",
        "service_period": "2026-06",
        "invoice_ref": "ST-ANNES-2026-06-INVOICE-3",
        "invoice_number": "3",
        "amount": 875,
        "service_count": 7,
        "status": "SENT",
        "generated_at": "2026-07-17T13:47:14+00:00",
        "sent_at_utc_iso": "2026-07-17T13:47:14+00:00",
        "provenance": "external_agent_send",
        "operator_authorized": True,
        "to": ["draper.carter@gmail.com"],
        "cc": ["winshiplive@gmail.com"],
        "bcc": [],
        "subject": "Corrected: St. Anne's Invoice - June 2026 Services",
        "gmail_message_id": "19f7054d2e151aa4",
        "gmail_thread_id": "19f7053211a51f52",
        "artifact_kind": "operator_provided_pdf_invoice",
        "attachment": {
            "filename": "invoice_final_20260717.pdf",
            "path": "/Users/hwinshipwheatley/Documents/Invoices/invoice_final_20260717.pdf",
            "size_bytes": 107683,
            "sha256": "1f2ebb6b77e7ddfe095b8a449d5c3eaf12ea61f74730b0a901fe800b3c81140e",
            "local_artifact_available": False,
        },
        "page_count": 1,
        "sha256": "1f2ebb6b77e7ddfe095b8a449d5c3eaf12ea61f74730b0a901fe800b3c81140e",
        "manual_send_out_of_band_known": True,
        "sent_by_openclaw": False,
        "email_send_allowed": False,
        "ledger_posting_allowed": False,
        "paid": False,
        "authoritative_source": {
            "path": str(source_path),
            "sha256": source_sha,
            "gmail_sent_readback_confirmed": True,
            "attachment_metadata_confirmed": True,
        },
        "superseded_send": {
            "disposition": "SUPERSEDED",
            "gmail_message_id": "19f6e50b5dc44aa6",
            "sent_at_utc_iso": "2026-07-17T04:23:30+00:00",
            "subject": "St. Anne's Invoice - June 2026 Services",
            "attachment_filename": "invoice_format_fixed_20260716.pdf",
            "attachment_sha256": "a32fa83cde025d237531a3360108f6f9c4e3afa87e8f857fe05912c3d994ee1b",
        },
        "workbook_finalization": {
            "final_sha256": "a986c19c50542efb9890085c656590cccff1f0233513420c5eb64178c27e411e",
            "backup_sha256": "626f89587d7fa8976dc7f99d55fd2f622c7433b7eac3c175dcb4fecab2165ea1",
            "semantic_diff_passed": True,
            "changed_cells": ["June 2026!G2", "June 2026!G4"],
        },
        "loop_closure": {
            "milestone_ref": "glenn_acknowledged",
            "expected_evidence": "reply_or_note_from_glenn",
            "watch_scope": "gmail_thread_plus_any_glenn_reply",
        },
        "downstream": {
            "draper_forwarded_to_glenn": {"status": "UNKNOWN", "state": "pending"},
            "glenn_acknowledged": {"status": "UNKNOWN", "state": "pending"},
            "check_received": {"status": "UNKNOWN", "state": "pending"},
            "invoice_paid": {"status": "UNKNOWN", "state": "pending"},
        },
    }


def test_build_status_payload_records_manual_send_without_openclaw_authority(tmp_path, monkeypatch):
    pdf_path = tmp_path / "Invoice_St_Annes_May_2026_OPERATOR_SENT.pdf"
    pdf_sha = _write_pdf(pdf_path)
    receipt_path = tmp_path / "st_annes_manual_invoice_sent_receipt_20260601T211257Z.json"
    receipt_path.write_text(json.dumps(_receipt_payload(pdf_sha)), encoding="utf-8")
    monkeypatch.setattr(status, "pdf_page_count", lambda path: 1)

    payload = status.build_status_payload(receipt_path=receipt_path, pdf_path=pdf_path, generated_at=FIXED_NOW)

    assert payload["schema_version"] == status.SCHEMA_VERSION
    assert payload["read_model_id"] == status.READ_MODEL_ID
    assert payload["invoice_status"] == "MANUAL_SEND_OUT_OF_BAND_RECORDED"
    assert payload["openclaw_send_performed"] is False
    assert payload["paid"] is False
    assert payload["ledger_posting_allowed"] is False
    assert payload["email_send_allowed"] is False
    assert payload["source_pdf_sha256"] == pdf_sha
    assert payload["artifact_kind"] == "operator_provided_pdf_invoice"
    assert payload["month"] == "2026-05"
    assert payload["machine_proof"]["pdf_page_count_is_one"] is True
    assert all(value is False for value in payload["safety_flags"].values())


def test_build_status_payload_records_operator_authorized_external_agent_send(
    tmp_path,
    monkeypatch,
):
    pdf_path = tmp_path / "invoice_format_fixed_20260716.pdf"
    pdf_sha = _write_pdf(pdf_path)
    receipt = _receipt_payload(pdf_sha)
    receipt.update(
        {
            "schema_version": "st_annes_external_agent_send_receipt_v0",
            "status": "SENT",
            "invoice_period": "2026-06",
            "service_period": "2026-06",
            "generated_at": "2026-07-17T04:23:30+00:00",
            "sent_at_utc_iso": "2026-07-17T04:23:30+00:00",
            "provenance": "external_agent_send",
            "operator_authorized": True,
            "to": ["draper.carter@gmail.com"],
            "cc": ["winshiplive@gmail.com"],
            "bcc": [],
            "subject": "St. Anne's Invoice - June 2026 Services",
            "gmail_message_id": "19f6e50b5dc44aa6",
            "invoice_number": "3",
            "amount": 875,
            "service_count": 7,
            "attachment": {
                "filename": pdf_path.name,
                "path": str(pdf_path),
                "sha256": pdf_sha,
            },
            "downstream": {
                "draper_forwarded_to_glenn": {"status": "UNKNOWN", "state": "pending"},
                "glenn_acknowledged": {"status": "UNKNOWN", "state": "pending"},
                "check_received": {"status": "UNKNOWN", "state": "pending"},
                "invoice_paid": {"status": "UNKNOWN", "state": "pending"},
            },
        }
    )
    receipt_path = tmp_path / "st_annes_external_agent_send_receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.setattr(status, "pdf_page_count", lambda path: 1)

    payload = status.build_status_payload(
        receipt_path=receipt_path,
        pdf_path=pdf_path,
        generated_at="2026-07-17T13:00:00+00:00",
    )

    assert payload["invoice_status"] == "SENT"
    assert payload["invoice_period"] == "2026-06"
    assert payload["recipient"] == "draper.carter@gmail.com"
    assert payload["send_provenance"] == "external_agent_send"
    assert payload["operator_authorized"] is True
    assert payload["gmail_message_id"] == "19f6e50b5dc44aa6"
    assert payload["amount"] == 875
    assert payload["paid"] is False
    assert payload["downstream"]["invoice_paid"] == {
        "status": "UNKNOWN", "state": "pending"
    }
    assert payload["machine_proof"]["reconciliation_record_only"] is True
    assert payload["openclaw_send_performed"] is False


def test_corrected_send_becomes_operative_and_preserves_superseded_send(
    tmp_path,
):
    authoritative = tmp_path / "ST-ANNES-INVOICE-FINAL-CORRECTION-SENT-20260717.md"
    authoritative.write_text("authoritative corrected send receipt\n", encoding="utf-8")
    source_sha = status.sha256_file(authoritative)
    receipt = _corrected_receipt_payload(authoritative, source_sha)
    receipt_path = tmp_path / "st_annes_corrected_send_receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    payload = status.build_status_payload(
        receipt_path=receipt_path,
        pdf_path=tmp_path / "missing-local-final.pdf",
        generated_at="2026-07-17T14:00:00+00:00",
    )

    assert payload["invoice_status"] == "SENT"
    assert payload["gmail_message_id"] == "19f7054d2e151aa4"
    assert payload["gmail_thread_id"] == "19f7053211a51f52"
    assert payload["subject"].startswith("Corrected:")
    assert payload["source_pdf_sha256"] == receipt["sha256"]
    assert payload["source_pdf_file_size_bytes"] == 107683
    assert payload["source_pdf_local_available"] is False
    assert payload["validation"]["artifact_validation_mode"] == "authoritative_sent_readback"
    assert payload["validation"]["pdf_sha256_matches_receipt"] is False
    assert payload["validation"]["attachment_sha256_receipt_consistent"] is True
    assert payload["machine_proof"]["local_pdf_inspected"] is False
    assert payload["send_history"][0]["disposition"] == "SUPERSEDED"
    assert payload["send_history"][0]["gmail_message_id"] == "19f6e50b5dc44aa6"
    assert payload["send_history"][1]["disposition"] == "OPERATIVE"
    assert payload["send_history"][1]["gmail_message_id"] == "19f7054d2e151aa4"
    assert payload["workbook_finalization"]["changed_cells"] == [
        "June 2026!G2", "June 2026!G4"
    ]
    assert payload["loop_closure"]["milestone_ref"] == "glenn_acknowledged"
    assert payload["loop_closure"]["expected_evidence"] == "reply_or_note_from_glenn"
    assert all(item["status"] == "UNKNOWN" for item in payload["downstream"].values())
    assert payload["openclaw_send_performed"] is False
    assert payload["ledger_mutation_performed"] is False
    assert payload["paid"] is False


def test_corrected_send_rejects_drifted_authoritative_source(tmp_path):
    authoritative = tmp_path / "ST-ANNES-INVOICE-FINAL-CORRECTION-SENT-20260717.md"
    authoritative.write_text("authoritative corrected send receipt\n", encoding="utf-8")
    receipt = _corrected_receipt_payload(authoritative, "0" * 64)
    receipt_path = tmp_path / "st_annes_corrected_send_receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(ValueError, match="authoritative source sha256"):
        status.build_status_payload(
            receipt_path=receipt_path,
            pdf_path=tmp_path / "missing-local-final.pdf",
            generated_at="2026-07-17T14:00:00+00:00",
        )


def test_sqlite_preserves_original_and_corrected_send_rows(tmp_path, monkeypatch):
    original_pdf = tmp_path / "invoice_format_fixed_20260716.pdf"
    original_sha = _write_pdf(original_pdf)
    original = _receipt_payload(original_sha)
    original.update(
        {
            "schema_version": "st_annes_external_agent_send_receipt_v0",
            "status": "SENT",
            "invoice_period": "2026-06",
            "service_period": "2026-06",
            "sent_at_utc_iso": "2026-07-17T04:23:30+00:00",
            "provenance": "external_agent_send",
            "operator_authorized": True,
            "to": ["draper.carter@gmail.com"],
            "cc": ["winshiplive@gmail.com"],
            "bcc": [],
            "subject": "St. Anne's Invoice - June 2026 Services",
            "gmail_message_id": "19f6e50b5dc44aa6",
            "invoice_number": "3",
            "amount": 875,
            "service_count": 7,
            "attachment": {
                "filename": original_pdf.name,
                "path": str(original_pdf),
                "sha256": original_sha,
            },
            "downstream": {
                "draper_forwarded_to_glenn": {"status": "UNKNOWN", "state": "pending"},
                "glenn_acknowledged": {"status": "UNKNOWN", "state": "pending"},
                "check_received": {"status": "UNKNOWN", "state": "pending"},
                "invoice_paid": {"status": "UNKNOWN", "state": "pending"},
            },
        }
    )
    original_path = tmp_path / "original.json"
    original_path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(status, "pdf_page_count", lambda path: 1)
    original_payload = status.build_status_payload(
        receipt_path=original_path,
        pdf_path=original_pdf,
        generated_at="2026-07-17T13:25:09+00:00",
    )

    authoritative = tmp_path / "ST-ANNES-INVOICE-FINAL-CORRECTION-SENT-20260717.md"
    authoritative.write_text("authoritative corrected send receipt\n", encoding="utf-8")
    corrected = _corrected_receipt_payload(authoritative, status.sha256_file(authoritative))
    corrected_path = tmp_path / "corrected.json"
    corrected_path.write_text(json.dumps(corrected), encoding="utf-8")
    corrected_payload = status.build_status_payload(
        receipt_path=corrected_path,
        pdf_path=tmp_path / "missing-local-final.pdf",
        generated_at="2026-07-17T14:00:00+00:00",
    )

    sqlite_path = tmp_path / "status.sqlite"
    status.record_sqlite_receipt(original_payload, sqlite_path)
    status.record_sqlite_receipt(corrected_payload, sqlite_path)
    conn = sqlite3.connect(sqlite_path)
    try:
        rows = conn.execute(
            "SELECT payload_json FROM st_annes_invoice_status_receipt ORDER BY generated_at"
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 2
    assert json.loads(rows[0][0])["gmail_message_id"] == "19f6e50b5dc44aa6"
    assert json.loads(rows[1][0])["gmail_message_id"] == "19f7054d2e151aa4"


def test_build_status_payload_rejects_unsafe_receipt(tmp_path, monkeypatch):
    pdf_path = tmp_path / "Invoice_St_Annes_May_2026_OPERATOR_SENT.pdf"
    pdf_sha = _write_pdf(pdf_path)
    payload = _receipt_payload(pdf_sha)
    payload["email_send_allowed"] = True
    receipt_path = tmp_path / "st_annes_manual_invoice_sent_receipt_20260601T211257Z.json"
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(status, "pdf_page_count", lambda path: 1)

    with pytest.raises(ValueError, match="email_send_allowed"):
        status.build_status_payload(receipt_path=receipt_path, pdf_path=pdf_path, generated_at=FIXED_NOW)


def test_record_sqlite_receipt_writes_evidence_only_row(tmp_path, monkeypatch):
    pdf_path = tmp_path / "Invoice_St_Annes_May_2026_OPERATOR_SENT.pdf"
    pdf_sha = _write_pdf(pdf_path)
    receipt_path = tmp_path / "st_annes_manual_invoice_sent_receipt_20260601T211257Z.json"
    receipt_path.write_text(json.dumps(_receipt_payload(pdf_sha)), encoding="utf-8")
    monkeypatch.setattr(status, "pdf_page_count", lambda path: 1)
    payload = status.build_status_payload(receipt_path=receipt_path, pdf_path=pdf_path, generated_at=FIXED_NOW)

    sqlite_path = tmp_path / "st_annes_invoice_status.sqlite"
    status.record_sqlite_receipt(payload, sqlite_path)

    conn = sqlite3.connect(sqlite_path)
    try:
        row = conn.execute(
            "SELECT invoice_status, openclaw_send_performed, email_send_allowed, ledger_posting_allowed, paid "
            "FROM st_annes_invoice_status_receipt"
        ).fetchone()
    finally:
        conn.close()
    assert row == ("MANUAL_SEND_OUT_OF_BAND_RECORDED", 0, 0, 0, 0)


def test_export_writes_local_and_bridge_read_models(tmp_path, monkeypatch):
    pdf_path = tmp_path / "Invoice_St_Annes_May_2026_OPERATOR_SENT.pdf"
    pdf_sha = _write_pdf(pdf_path)
    receipt_path = tmp_path / "st_annes_manual_invoice_sent_receipt_20260601T211257Z.json"
    receipt_path.write_text(json.dumps(_receipt_payload(pdf_sha)), encoding="utf-8")
    monkeypatch.setattr(status, "pdf_page_count", lambda path: 1)

    result = status.export_st_annes_invoice_status(
        receipt_path=receipt_path,
        pdf_path=pdf_path,
        export_root=tmp_path / "local_read_models",
        bridge_export_root=tmp_path / "bridge_read_models",
        sqlite_path=tmp_path / "system_knowledge" / "st_annes_invoice_status.sqlite",
        generated_at=FIXED_NOW,
    )

    local_payload = json.loads(Path(result.read_model_path).read_text(encoding="utf-8"))
    bridge_payload = json.loads(Path(result.bridge_read_model_path).read_text(encoding="utf-8"))
    assert local_payload == bridge_payload
    assert local_payload["source_pdf_sha256"] == pdf_sha
    assert Path(result.sqlite_path).exists()

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

import invoice_validation_promotion as promotion
import hitl_notification_service


FIXED_NOW = "2026-07-17T22:30:00+00:00"
PDF_BYTES = b"%PDF-1.4\nvalidated candidate bytes\n"
WORKBOOK_BYTES = b"validated workbook bytes"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validation_input() -> dict:
    return {
        "client_ref": "live_arts_md",
        "service_period": "2026-07",
        "invoice_number": "2026-1004",
        "artifact_sha256": _sha(PDF_BYTES),
        "operator_message_ref": "telegram:operator_maestro_chat:1794",
        "operator_message_text": "That looks perfect.",
        "surface_ref": "operator_maestro_chat",
        "validated_at": FIXED_NOW,
    }


def test_validation_event_is_append_only_and_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "objective.sqlite"
    first = promotion.record_invoice_validation_event(db_path=db_path, **_validation_input())
    replay = promotion.record_invoice_validation_event(db_path=db_path, **_validation_input())

    assert first["created"] is True
    assert replay["created"] is False
    assert replay["event_id"] == first["event_id"]
    assert first["artifact_sha256"] == _sha(PDF_BYTES)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("select count(*) from invoice_artifact_validation_events").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("update invoice_artifact_validation_events set surface_ref='changed'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("delete from invoice_artifact_validation_events")


def test_exact_validated_bytes_publish_and_registry_close_are_one_owner_operation(tmp_path: Path) -> None:
    candidate_pdf = tmp_path / "candidate.pdf"
    candidate_pdf.write_bytes(PDF_BYTES)
    candidate_workbook = tmp_path / "candidate.xlsx"
    candidate_workbook.write_bytes(WORKBOOK_BYTES)
    package = tmp_path / "canonical" / "w1-finalized-2026-1004"
    package.mkdir(parents=True)
    (package / "invoice.pdf").write_bytes(b"old pdf")
    (package / "invoice.xlsx").write_bytes(b"old workbook")
    (package / "invoice_manifest.json").write_text(
        json.dumps({"schema": "openclaw_invoice_manifest_v1"}), encoding="utf-8"
    )
    registry = tmp_path / "invoice_candidate_artifact_registry.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": "invoice_candidate_artifact_registry_v0",
                "generated_at": "earlier",
                "candidates": [
                    {
                        "artifact_id": "candidate:B-prior-balance-formula-fixed",
                        "client_ref": "live_arts_md",
                        "service_period": "2026-07",
                        "invoice_number": "2026-1004",
                        "status": "verified_review_candidate",
                        "active_for_review": True,
                        "finalized": False,
                        "validation_received": False,
                        "pdf_path": str(candidate_pdf),
                        "pdf_sha256": _sha(PDF_BYTES),
                        "rendered_image_path": str(tmp_path / "preview.png"),
                        "rendered_image_sha256": "a" * 64,
                        "source_receipt_ref": "candidate-receipt",
                    }
                ],
                "authority_boundary": {"business_send_allowed": False},
            }
        ),
        encoding="utf-8",
    )
    validation = promotion.record_invoice_validation_event(
        db_path=tmp_path / "objective.sqlite", **_validation_input()
    )

    result = promotion.publish_validated_invoice_package(
        candidate_pdf=candidate_pdf,
        candidate_workbook=candidate_workbook,
        package_dir=package,
        registry_path=registry,
        validation_receipt=validation,
        published_at=FIXED_NOW,
    )

    assert result["status"] == "PUBLISHED_VALIDATED"
    assert result["validated_sha256"] == _sha(PDF_BYTES)
    assert result["finalized_sha256"] == _sha(PDF_BYTES)
    assert (package / "invoice.pdf").read_bytes() == PDF_BYTES
    assert (package / "invoice.xlsx").read_bytes() == WORKBOOK_BYTES
    manifest = json.loads((package / "invoice_manifest.json").read_text())
    assert manifest["current_pdf_sha256"] == _sha(PDF_BYTES)
    assert manifest["validation_event_id"] == validation["event_id"]
    assert manifest["status"] == "finalized_validated"
    row = json.loads(registry.read_text())["candidates"][0]
    assert row["active_for_review"] is False
    assert row["finalized"] is True
    assert row["validation_received"] is True
    assert row["finalized_pdf_sha256"] == _sha(PDF_BYTES)
    assert result["superseded_package_archive"].endswith("w1-finalized-2026-1004")
    archive = Path(result["superseded_package_archive"])
    assert archive.is_dir()
    assert not (archive / "invoice_manifest.json").exists()
    assert (archive / "invoice_manifest.superseded.json").is_file()


def test_publish_refuses_any_candidate_hash_change_before_mutation(tmp_path: Path) -> None:
    candidate_pdf = tmp_path / "candidate.pdf"
    candidate_pdf.write_bytes(PDF_BYTES + b"changed")
    candidate_workbook = tmp_path / "candidate.xlsx"
    candidate_workbook.write_bytes(WORKBOOK_BYTES)
    package = tmp_path / "package"
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"schema_version": "invoice_candidate_artifact_registry_v0", "candidates": []}))
    validation = promotion.record_invoice_validation_event(
        db_path=tmp_path / "objective.sqlite", **_validation_input()
    )

    with pytest.raises(promotion.InvoiceValidationError, match="validated artifact hash"):
        promotion.publish_validated_invoice_package(
            candidate_pdf=candidate_pdf,
            candidate_workbook=candidate_workbook,
            package_dir=package,
            registry_path=registry,
            validation_receipt=validation,
            published_at=FIXED_NOW,
        )

    assert not package.exists()


def test_exact_send_notification_uses_reusable_operator_eli5_copy() -> None:
    action = {
        "action_id": "A1B2C3D4",
        "action_type": "exact_gmail_send",
        "source_agent": "guardian",
        "expires_at": "2026-07-18T22:30:00+00:00",
        "payload": {
            "schema_version": "OPERATOR_ACTION_APPROVAL_REQUEST_V0",
            "typed_fallback_reply_code": "A1B2",
            "payload": {
                "operator_eli5": (
                    "July Live Arts invoice 2026-1004, $100, to Accountant@liveartsmd.org - "
                    "the exact version you just approved. Tap approve to send."
                )
            },
        },
    }

    rendered = hitl_notification_service.format_notification(action)

    assert rendered.startswith("July Live Arts invoice 2026-1004")
    assert "Tap approve to send." in rendered
    assert "Payload hash" not in rendered
    assert "Credential lease" not in rendered
    assert "A1B2 1 to approve" in rendered

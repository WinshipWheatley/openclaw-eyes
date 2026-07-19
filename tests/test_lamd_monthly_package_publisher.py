from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from lamd_monthly_autosend import validate_package
from lamd_monthly_package_publisher import (
    PackagePublicationError,
    publish_monthly_package,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validated_package(root: Path, *, invoice_number: str = "2026-1005", **changes) -> Path:
    month_dir = root / "2026-08"
    package_dir = month_dir / f"w1-finalized-{invoice_number}"
    package_dir.mkdir(parents=True)
    workbook = package_dir / "invoice.xlsx"
    pdf = package_dir / "invoice.pdf"
    workbook.write_bytes(b"validated speaker-rental workbook")
    pdf.write_bytes(b"%PDF-1.4 validated speaker-rental invoice")
    manifest = {
        "schema": "openclaw_invoice_manifest_v1",
        "status": "finalized_validated",
        "client_slug": "live-arts-md",
        "stream": "speaker_rental",
        "invoice_key": f"2026-08_live_arts_md_{invoice_number}",
        "invoice_number": invoice_number,
        "service_period_start": "2026-08-01",
        "service_period_end": "2026-08-31",
        "source_sheet": "August 2026",
        "amount": 100.0,
        "package_workbook_sha256": _sha(workbook),
        "current_pdf_sha256": _sha(pdf),
        "validated_artifact_sha256": _sha(pdf),
        "validation_event_id": "invoice-validation:august",
        "artifact_verification_receipt_id": "invoice-validation:august",
        "authority_boundary": {
            "provider_draft_created": False,
            "external_send_performed": False,
            "money_moved": False,
            "ledger_posted": False,
        },
    }
    manifest.update(changes)
    (package_dir / "invoice_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return month_dir


def test_publisher_emits_one_hash_bound_monthly_package(tmp_path: Path) -> None:
    month_dir = _validated_package(tmp_path)
    output = month_dir / "lamd_monthly_autosend_package.json"

    result = publish_monthly_package(month_dir, output_path=output)

    assert result["status"] == "PUBLISHED"
    package = validate_package(json.loads(output.read_text(encoding="utf-8")))
    assert package["source_stream"] == "speaker_rental"
    assert package["source_sheet"] == "August 2026"
    assert package["source_workbook_path"].endswith("/w1-finalized-2026-1005/invoice.xlsx")
    assert package["pdf_path"].endswith("/w1-finalized-2026-1005/invoice.pdf")
    assert result["provider_called"] is False
    assert result["ledger_posted"] is False


@pytest.mark.parametrize(
    "change",
    (
        {"stream": "av_tech"},
        {"amount": 100.01},
        {"status": "finalized_verified"},
        {"client_slug": "other-client"},
        {"validated_artifact_sha256": "0" * 64},
        {"validation_event_id": ""},
    ),
)
def test_publisher_refuses_untrusted_manifest_fields(tmp_path: Path, change: dict) -> None:
    month_dir = _validated_package(tmp_path, **change)
    output = month_dir / "lamd_monthly_autosend_package.json"

    with pytest.raises(PackagePublicationError):
        publish_monthly_package(month_dir, output_path=output)

    assert not output.exists()


def test_publisher_refuses_multiple_validated_candidates(tmp_path: Path) -> None:
    month_dir = _validated_package(tmp_path, invoice_number="2026-1005")
    _validated_package(tmp_path, invoice_number="2026-1006")

    with pytest.raises(PackagePublicationError, match="exactly one"):
        publish_monthly_package(month_dir)


def test_publisher_is_idempotent_but_refuses_changed_existing_output(tmp_path: Path) -> None:
    month_dir = _validated_package(tmp_path)
    output = month_dir / "lamd_monthly_autosend_package.json"
    first = publish_monthly_package(month_dir, output_path=output)
    second = publish_monthly_package(month_dir, output_path=output)
    assert first["status"] == "PUBLISHED"
    assert second["status"] == "IDEMPOTENT_REPLAY"

    output.write_text("{}\n", encoding="utf-8")
    with pytest.raises(PackagePublicationError, match="existing output changed"):
        publish_monthly_package(month_dir, output_path=output)

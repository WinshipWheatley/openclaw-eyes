from __future__ import annotations

import hashlib
import json
from pathlib import Path

from invoice_cockpit_ops import RealCockpitOps


def _write_real_receipt(incoming_dir: Path, *, amount_units: str = "dollars") -> Path:
    incoming_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = incoming_dir / "st_annes.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nreal codex mac invoice\n%%EOF\n")
    if amount_units == "dollars":
        line_amount = 125
        total = 250
    else:
        line_amount = 12500
        total = 25000
    receipt_path = incoming_dir / "st_annes.json"
    receipt_path.write_text(
        json.dumps(
            {
                "schema_version": "ST_ANNES_JUNE_INVOICE_V0",
                "client_ref": "st_annes",
                "client_name": "St. Anne's",
                "client_email": "draper.carter@gmail.com",
                "invoice_number": "ST-ANNES-REAL-2026-06",
                "issue_date": "2026-07-01",
                "net_terms": "Due on Receipt",
                "amount_units": amount_units,
                "total": total,
                "rendered_pdf_path": str(pdf_path),
                "line_items": [
                    {
                        "description": "Wedding",
                        "service_date": "2026-06-27",
                        "amount": line_amount,
                    },
                    {
                        "description": "Church service (10:00)",
                        "service_date": "2026-06-28",
                        "amount": line_amount,
                    },
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return receipt_path


def test_prepare_invoice_prefers_real_codex_mac_receipt(tmp_path: Path, monkeypatch) -> None:
    incoming_dir = tmp_path / "incoming"
    receipt_path = _write_real_receipt(incoming_dir)
    pdf_path = incoming_dir / "st_annes.pdf"
    monkeypatch.setenv("OPENCLAW_INVOICE_COCKPIT_INCOMING_DIR", str(incoming_dir))
    monkeypatch.setenv("OPENCLAW_INVOICES_DIR", str(tmp_path / "fallback_invoices"))
    monkeypatch.setenv("OPENCLAW_INVOICE_TRACKER_DIR", str(tmp_path / "fallback_tracker"))

    data, returned_pdf, digest = RealCockpitOps().prepare_invoice("St Anne's")

    assert returned_pdf == str(pdf_path)
    assert digest == hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    assert data["invoice_number"] == "ST-ANNES-REAL-2026-06"
    assert data["real_invoice_receipt_path"] == str(receipt_path)
    assert data["line_item_source"] == "codex_mac_invoice_receipt"
    assert data["amount_total"] == 250
    assert data["balance_due"] == 250
    assert data["line_items"][0]["amount"] == 125
    assert data["attachment_filename"] == "st_annes.pdf"


def test_prepare_invoice_falls_back_without_real_receipt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENCLAW_INVOICE_COCKPIT_INCOMING_DIR", str(tmp_path / "empty_incoming"))
    monkeypatch.setenv("OPENCLAW_INVOICES_DIR", str(tmp_path / "fallback_invoices"))
    monkeypatch.setenv("OPENCLAW_INVOICE_TRACKER_DIR", str(tmp_path / "fallback_tracker"))

    data, returned_pdf, digest = RealCockpitOps().prepare_invoice("St Anne's")

    assert data["invoice_number"].startswith("WL-")
    assert data["line_item_source"] in {"st_annes_work_log", "default_st_annes_events"}
    assert Path(returned_pdf).exists()
    assert Path(returned_pdf).parent == tmp_path / "fallback_invoices"
    assert digest == hashlib.sha256(Path(returned_pdf).read_bytes()).hexdigest()


def test_real_receipt_amount_units_dollars_are_not_promoted_to_cents(
    tmp_path: Path,
    monkeypatch,
) -> None:
    incoming_dir = tmp_path / "incoming"
    _write_real_receipt(incoming_dir, amount_units="dollars")
    monkeypatch.setenv("OPENCLAW_INVOICE_COCKPIT_INCOMING_DIR", str(incoming_dir))

    data, _returned_pdf, _digest = RealCockpitOps().prepare_invoice("St. Anne's")

    assert data["amount_units"] == "dollars"
    assert data["amount_total"] == 250
    assert data["balance_due"] == 250
    assert [item["amount"] for item in data["line_items"]] == [125, 125]
    assert data["amount_total"] != 25000

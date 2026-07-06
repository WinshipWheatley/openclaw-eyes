from __future__ import annotations

import hashlib
import json
from pathlib import Path

from contacts_registry import ContactSeed, ContactsRegistry
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


def _st_annes_invoice_data(**overrides) -> dict:
    data = {
        "client_ref": "st_annes",
        "client_name": "St. Anne's",
        "client_email": "draper.carter@gmail.com",
        "invoice_number": "WL-DRAFT-ST-ANNES",
        "issue_date": "2026-07-03",
        "net_terms": "Due on Receipt",
        "project_desc": "Wedding; Church service",
        "service_date": "2026-06-27",
        "amount_total": 25000,
        "deposit_paid": 0,
        "balance_due": 25000,
        "attachment_filename": "WL-DRAFT-ST-ANNES__St_Annes.pdf",
        "line_items": [
            {"description": "Wedding", "service_date": "2026-06-27", "amount": 12500},
            {"description": "Church service", "service_date": "2026-06-28", "amount": 12500},
        ],
    }
    data.update(overrides)
    return data


def test_clara_draft_resolves_st_annes_registry_contact_for_greeting(tmp_path: Path) -> None:
    contacts_db = tmp_path / "contacts.sqlite3"
    ContactsRegistry(str(contacts_db), seed=True)
    messages: list[str] = []

    ops = RealCockpitOps(contacts_db_path=str(contacts_db))
    ops.telegram_message = lambda text: messages.append(text) or {"ok": True}  # type: ignore[method-assign]

    result = ops.clara_draft_and_guardian(
        {"client_ref": "st_annes", "display_name": "St. Anne's"},
        _st_annes_invoice_data(),
        "/tmp/i.pdf",
    )

    assert result["ok"] is True
    assert "Hi Draper," in messages[0]
    assert "forwarded it to Glenn" in messages[0]
    assert "copy me (winshiplive@gmail.com)" in messages[0]
    assert "There's nothing needed on your end right now" not in messages[0]


def test_recipient_resolution_enriches_intermediary_with_forward_target(tmp_path: Path) -> None:
    contacts_db = tmp_path / "contacts.sqlite3"
    ContactsRegistry(str(contacts_db), seed=True)

    recipient = RealCockpitOps(contacts_db_path=str(contacts_db))._recipient_for_invoice(
        client={"client_ref": "st_annes", "display_name": "St. Anne's"},
        invoice_data=_st_annes_invoice_data(),
    )

    assert recipient["name"] == "Draper Carter"
    assert recipient["role"] == "intermediary"
    assert recipient["forward_to"] == "Glenn"


def test_clara_draft_contact_greeting_is_registry_driven_for_swapped_client(tmp_path: Path) -> None:
    contacts_db = tmp_path / "contacts.sqlite3"
    ContactsRegistry(
        str(contacts_db),
        seed=True,
        seed_records=(
            ContactSeed(
                id="morgan-lee",
                name="Morgan Lee",
                emails=("morgan@example.com",),
                connected_clients=("green-room",),
                role="primary_invoice_contact",
                aliases=("Morgan",),
            ),
        ),
    )
    messages: list[str] = []

    ops = RealCockpitOps(contacts_db_path=str(contacts_db))
    ops.telegram_message = lambda text: messages.append(text) or {"ok": True}  # type: ignore[method-assign]

    result = ops.clara_draft_and_guardian(
        {"client_ref": "green_room", "display_name": "Green Room"},
        _st_annes_invoice_data(
            client_ref="green_room",
            client_name="Green Room",
            client_email="morgan@example.com",
        ),
        "/tmp/i.pdf",
    )

    assert result["ok"] is True
    assert "Hi Morgan," in messages[0]
    assert "Hi Draper," not in messages[0]


def test_send_email_test_mode_uses_registry_contact_body(tmp_path: Path, monkeypatch) -> None:
    contacts_db = tmp_path / "contacts.sqlite3"
    ContactsRegistry(str(contacts_db), seed=True)
    calls: list[tuple[str, str, dict]] = []

    monkeypatch.setattr("global_run_mode_context.handle_run_mode_set_request", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(
        "google_access_broker.call",
        lambda actor, capability, params: calls.append((actor, capability, params)) or {"ok": True},
    )
    attachment = tmp_path / "draft.pdf"
    attachment.write_bytes(b"%PDF-1.4\nDRAFT\n%%EOF\n")

    result = RealCockpitOps(contacts_db_path=str(contacts_db)).send_email(
        to="draper.carter@gmail.com",
        attachment=str(attachment),
        attachment_sha256=hashlib.sha256(attachment.read_bytes()).hexdigest(),
        invoice_data=_st_annes_invoice_data(),
        mode="test",
    )

    assert result["ok"] is True
    assert "Hi Draper," in calls[0][2]["body"]
    assert "forwarded it to Glenn" in calls[0][2]["body"]
    assert "copy me (winshiplive@gmail.com)" in calls[0][2]["body"]
    assert "There's nothing needed on your end right now" not in calls[0][2]["body"]
    assert calls[0][2]["attachments"] == [str(attachment)]


def test_finalized_review_attachment_regenerates_issued_non_draft_pdf(
    tmp_path: Path,
    monkeypatch,
) -> None:
    draft_pdf = tmp_path / "WL-DRAFT-ST-ANNES__St_Annes.pdf"
    draft_pdf.write_bytes(b"%PDF-1.4\nDRAFT\n%%EOF\n")
    monkeypatch.setenv("OPENCLAW_INVOICES_DIR", str(tmp_path / "issued"))
    monkeypatch.setenv("OPENCLAW_INVOICE_TRACKER_DIR", str(tmp_path / "tracker"))

    data, pdf_path, digest = RealCockpitOps().finalized_review_attachment(
        attachment=str(draft_pdf),
        attachment_sha256=hashlib.sha256(draft_pdf.read_bytes()).hexdigest(),
        invoice_data=_st_annes_invoice_data(),
    )

    issued_pdf = Path(pdf_path)
    assert issued_pdf.exists()
    assert issued_pdf != draft_pdf
    assert "DRAFT" not in issued_pdf.name
    assert data["invoice_status"] == "issued"
    assert data["lifecycle_state"] == "issued"
    assert "DRAFT" not in data["invoice_number"]
    assert digest == hashlib.sha256(issued_pdf.read_bytes()).hexdigest()


def test_send_email_real_mode_finalizes_draft_invoice_and_regenerates_clean_pdf(
    tmp_path: Path,
    monkeypatch,
) -> None:
    contacts_db = tmp_path / "contacts.sqlite3"
    ContactsRegistry(str(contacts_db), seed=True)
    draft_pdf = tmp_path / "WL-DRAFT-ST-ANNES__St_Annes.pdf"
    draft_pdf.write_bytes(b"%PDF-1.4\nDRAFT\n%%EOF\n")
    monkeypatch.setenv("OPENCLAW_SEND_HOLD_PATH", str(tmp_path / "send_hold_off"))
    monkeypatch.setenv("OPENCLAW_INVOICES_DIR", str(tmp_path / "issued"))
    monkeypatch.setenv("OPENCLAW_INVOICE_TRACKER_DIR", str(tmp_path / "tracker"))
    calls: list[tuple[str, str, dict]] = []
    invoice_data = _st_annes_invoice_data()

    monkeypatch.setattr(
        "google_access_broker.call",
        lambda actor, capability, params: calls.append((actor, capability, params)) or {"ok": True},
    )

    result = RealCockpitOps(contacts_db_path=str(contacts_db)).send_email(
        to="draper.carter@gmail.com",
        attachment=str(draft_pdf),
        attachment_sha256=hashlib.sha256(draft_pdf.read_bytes()).hexdigest(),
        invoice_data=invoice_data,
        mode="real",
    )

    assert result["ok"] is True
    sent_params = calls[0][2]
    sent_pdf = Path(sent_params["attachments"][0])
    assert sent_pdf.exists()
    assert "DRAFT" not in sent_pdf.name
    assert sent_pdf != draft_pdf
    assert sent_params["attachment_sha256"] == [hashlib.sha256(sent_pdf.read_bytes()).hexdigest()]
    assert invoice_data["invoice_status"] == "issued"
    assert invoice_data["lifecycle_state"] == "issued"
    assert "DRAFT" not in invoice_data["invoice_number"]

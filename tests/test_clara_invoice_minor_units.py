"""The Clara invoice draft must render minor-unit (cents) amounts correctly — a live test-mode
send once showed $25,000 for a $250 invoice because the drafter read cents as dollars."""

from clara_invoice_email_draft_package import (
    body_contains_backend_status_language,
    build_clara_invoice_email_draft_package,
    build_general_client_invoice_body,
)


def _st_annes_data():
    return {
        "client_name": "St. Anne's", "client_email": "draper.carter@gmail.com",
        "attachment_filename": "St_Annes.pdf",
        "line_items": [
            {"description": "Wedding", "service_date": "2026-06-27", "amount": 12500},
            {"description": "Church service (10:00)", "service_date": "2026-06-28", "amount": 12500},
        ],
        "amount_total": 25000,
    }


def test_minor_units_amounts_render_as_dollars():
    body = build_general_client_invoice_body(_st_annes_data(), {"name": "Draper Carter"})
    assert "$125.00" in body            # each event, not $12,500
    assert "$250.00" in body            # total, not $25,000
    assert "$12,500" not in body and "$25,000" not in body
    assert "I hope this note finds you well." in body
    assert "Winship's invoice for St. Anne's is attached (St_Annes.pdf)" in body
    assert "coming to $250.00" in body
    assert "There's nothing needed on your end right now" in body
    assert "Warmly,\nClara Reid" in body
    assert "The total due is" not in body
    assert "Please let us know if anything else is needed for processing." not in body
    assert body_contains_backend_status_language(body) is False


def test_dollar_amounts_unchanged():
    # non-minor (already-dollar) amounts (< 1000, or floats) are NOT divided by 100
    data = {"client_name": "X", "line_items": [{"description": "Gig", "date": "2026-07-01", "amount": 500.0}]}
    body = build_general_client_invoice_body(data, None)
    assert "$500.00" in body and "$5.00" not in body


def test_attachment_not_ready_uses_warm_on_its_way_copy_without_attached_claim():
    data = {
        "client_name": "Live Arts MD",
        "attachment_ready": False,
        "line_items": [
            {"description": "Tech rehearsal", "date": "2026-07-01", "amount": 500.0},
        ],
        "amount_total": 500.0,
    }

    body = build_general_client_invoice_body(data, {"name": "Dane"})

    assert "Hi Dane," in body
    assert (
        "Winship's invoice for Live Arts MD, covering Tech rehearsal on 2026-07-01 ($500.00), "
        "is on its way to you."
    ) in body
    assert "($500.00) ($500.00)" not in body
    assert "is attached" not in body
    assert body_contains_backend_status_language(body) is False


def test_attachment_ready_without_filename_omits_parenthetical():
    data = {
        "client_name": "Harbor Light",
        "line_items": [
            {"description": "Sound support", "date": "2026-07-02", "amount": 350.0},
        ],
        "amount_total": 350.0,
    }

    body = build_general_client_invoice_body(data, {"name": "Mira"})

    assert "is attached (" not in body
    assert "Winship's invoice for Harbor Light is attached" in body
    assert "coming to $350.00" in body


def _draft_package(client_ref, client_display_name, **overrides):
    args = {
        "client_ref": client_ref,
        "workflow_ref": f"{client_ref}_invoice_workflow",
        "client_display_name": client_display_name,
        "recipient_package": {},
        "attachment_ready": True,
        "attachment_refs": ("invoice.pdf",),
        "invoice_period_label": "June 2026",
        "invoice_dates_covered": ("2026-06-27", "2026-06-28"),
        "present_receipts": ("clara_email_draft_receipt",),
    }
    args.update(overrides)
    return build_clara_invoice_email_draft_package(**args)


def test_new_client_registry_entry_drives_recipients_and_warm_body():
    package = _draft_package(
        "harbor_light",
        "Harbor Light",
        client_registry={
            "harbor_light": {
                "client_ref": "harbor_light",
                "client_display_name": "Harbor Light",
                "recipient_confirmation_status": "CONFIRMED_BY_RECEIPT",
                "recipients": (
                    {
                        "display_name": "Mira Patel",
                        "role": "primary_invoice_contact",
                        "lane": "to",
                        "email": "mira@example.test",
                    },
                ),
            }
        },
    )

    assert package["to_recipients"][0]["display_name"] == "Mira Patel"
    assert package["to_recipients"][0]["email"] == "mira@example.test"
    assert "Hi Mira," in package["body"]
    assert "I hope this note finds you well." in package["body"]
    assert "Winship's invoice for Harbor Light is attached" in package["body"]
    assert "Warmly,\nClara Reid" in package["body"]


def test_default_registry_drives_existing_client_invoice_drafts():
    capital = _draft_package(
        "capital_hilton",
        "Capital Hilton",
        supplier_portal_provider="COUPA",
        portal_submission_status="SUBMITTED_RECEIPT_CONFIRMED",
    )
    live_arts = _draft_package("live_arts_md", "Live Arts MD")
    st_annes = _draft_package("st_annes", "St. Anne's")

    assert capital["to_recipients"][0]["display_name"] == "Annette"
    assert "Hi Annette" in capital["body"]
    assert "Winship's invoice for Capital Hilton is attached" in capital["body"]
    assert "Coupa supplier portal" in capital["body"]

    assert live_arts["to_recipients"][0]["display_name"] == "Dane"
    assert "Hi Dane" in live_arts["body"]
    assert "Winship's invoice for Live Arts MD is attached" in live_arts["body"]

    assert st_annes["to_recipients"][0]["display_name"] == "Draper Carter"
    assert "Hi Draper" in st_annes["body"]
    assert "St. Anne's" in st_annes["body"]


def test_registry_draft_respects_simple_greeting_policy():
    package = _draft_package(
        "capital_hilton",
        "Capital Hilton",
        first_contact_intro_required=False,
    )

    assert package["body"].startswith("Hi Annette,\n")
    assert "helping Winship keep" not in package["body"]

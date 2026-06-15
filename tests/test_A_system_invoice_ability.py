import pytest

from invoice_ability_model import build_system_invoice_model, select_template_profile


def _base_business_identity():
    return {
        "display_name": "Winship Wheatley",
        "legal_or_payable_name": "Winship Wheatley",
        "address_line1": "1009 Smithville Street",
        "city_state_zip": "Annapolis, MD 21401",
        "phone": "443.758.4913",
        "email": "winshiplive@gmail.com",
    }


def _reynolds_simple_gig_facts():
    return {
        "invoice_request_id": "invoice_request_reynolds_2026_0627",
        "source_type": "fresh_gig_intake",
        "business_identity": _base_business_identity(),
        "client": {
            "name": "Reynolds Tavern",
            "billing_address_line1": "7 Church Circle",
            "billing_city_state_zip": "Annapolis, MD",
            "contact_name": "Sally",
            "contact_role": "owner",
            "contact_email": "reservations@reynoldstavern.com",
            "phone": None,
        },
        "job": {
            "archetype": "simple_gig",
            "title": "Live music performance",
            "venue_address_line1": "7 Church Circle",
            "venue_city_state": "Annapolis, MD",
            "service_start_date": "2026-06-27",
            "service_end_date": "2026-06-27",
            "service_time": "19:00-22:00",
            "notes": "Covering Mike Heuer's Friday slot.",
        },
        "invoice": {
            "invoice_number": "2026-0627-RT",
            "invoice_date": "2026-06-15",
            "payment_terms": "Due upon receipt",
            "currency": "USD",
            "tax_rate": 0,
            "prior_balance": 0,
            "payments_or_credits": 0,
            "deposit_received": 0,
        },
        "line_items": [
            {
                "item_number": 1,
                "description": "Live music performance",
                "period_start": "2026-06-27",
                "period_end": "2026-06-27",
                "quantity": 1,
                "unit": "event",
                "unit_price": 250,
                "discount": 0,
                "line_type": "charge",
                "equipment_name": None,
            }
        ],
        "render_policy": {
            "client_facing": True,
            "include_payment_instructions": True,
            "include_internal_reconciliation_notes": False,
            "requires_visual_review": True,
            "send_ready": False,
        },
    }


def _capital_hilton_monthly_facts():
    line_items = []
    for item_number in range(1, 7):
        line_items.append(
            {
                "item_number": item_number,
                "description": f"Statler Events: Capitol Hilton performance {item_number}",
                "period_start": None,
                "period_end": None,
                "quantity": 1,
                "unit": "each",
                "unit_price": 400,
                "discount": 0,
                "line_type": "charge",
                "equipment_name": None,
            }
        )
    line_items.append(
        {
            "item_number": 7,
            "description": "Courtesy credit",
            "period_start": None,
            "period_end": None,
            "quantity": 1,
            "unit": "each",
            "unit_price": -400,
            "discount": 0,
            "line_type": "credit",
            "equipment_name": None,
        }
    )
    return {
        "invoice_request_id": "invoice_request_capital_hilton_2026_1005",
        "source_type": "existing_known_invoice",
        "business_identity": {
            **_base_business_identity(),
            "display_name": "Winship Live",
            "legal_or_payable_name": "Winship Wheatley",
            "email": "winshiplive@icloud.com",
        },
        "client": {
            "name": "Hilton Center of Excellence",
            "billing_address_line1": "755 Crossover Lane",
            "billing_city_state_zip": "Memphis, TN 38117",
            "contact_name": None,
            "contact_role": None,
            "contact_email": None,
            "phone": "XX",
        },
        "job": {
            "archetype": "monthly_multiline",
            "title": "Statler Events: Capitol Hilton",
            "venue_address_line1": "16th and K Streets, NW",
            "venue_city_state": "Washington, D.C",
            "service_start_date": None,
            "service_end_date": None,
            "service_time": None,
            "notes": "Existing known invoice validation facts.",
        },
        "invoice": {
            "invoice_number": "2026-1005",
            "invoice_date": "2026-06-15",
            "payment_terms": "Due upon receipt",
            "currency": "USD",
            "tax_rate": 0,
            "prior_balance": 0,
            "payments_or_credits": 0,
            "deposit_received": 0,
        },
        "line_items": line_items,
        "render_policy": {
            "client_facing": True,
            "include_payment_instructions": True,
            "include_internal_reconciliation_notes": False,
            "requires_visual_review": True,
            "send_ready": False,
        },
    }


def test_simple_gig_facts_select_reynolds_st_annes_profile_and_totals():
    model = build_system_invoice_model(_reynolds_simple_gig_facts())

    assert model["template_profile"]["profile_id"] == "reynolds_st_annes_simple_gig_v1"
    assert model["template_profile"]["selected_sheet_name"] == "April 2026"
    assert model["template_profile"]["field_map"]["header"]["invoice_number"] == "G3"
    assert model["template_profile"]["field_map"]["bill_to"]["bill_to_contact_email"] == "G13"
    assert model["field_bindings"]["bill_to"]["bill_to_contact_name_role"] == "Sally, owner"
    assert model["field_bindings"]["line_items"][0]["line_amount"] == "250.00"
    assert model["field_bindings"]["totals"]["subtotal"] == "250.00"
    assert model["field_bindings"]["totals"]["total_due"] == "250.00"
    assert model["artifact_registration"]["send_ready"] is False


def test_monthly_multiline_selects_capital_hilton_profile_and_credit_totals():
    model = build_system_invoice_model(_capital_hilton_monthly_facts())

    profile = model["template_profile"]
    assert profile["profile_id"] == "capital_hilton_monthly_multiline_v1"
    assert profile["line_table_name"] == "SimpleInvoice"
    assert profile["line_item_rows"] == "B16:G22"
    assert profile["supports_negative_credit_lines"] is True
    assert profile["field_map"]["bill_to"]["bill_to_phone"] == "G12"
    assert profile["field_map"]["bill_to"]["bill_to_contact_email"] is None
    assert model["field_bindings"]["line_items"][-1]["line_amount"] == "-400.00"
    assert model["field_bindings"]["totals"]["subtotal"] == "2000.00"
    assert model["field_bindings"]["totals"]["total_due"] == "2000.00"


def test_render_dependency_is_explicit_and_not_faked():
    model = build_system_invoice_model(_reynolds_simple_gig_facts())

    assert model["render_dependency"]["status"] == "RENDER_DEPENDENCY_NOT_IMPLEMENTED"
    assert model["render_dependency"]["pdf_rendered"] is False
    assert model["render_dependency"]["workbook_written"] is False
    assert model["render_dependency"]["renderer_options"] == (
        "headless_libreoffice",
        "purpose_built_templating_renderer",
    )
    assert model["artifact_registration"]["artifact_pdf_path"] is None
    assert model["safety"]["email_send_performed"] is False
    assert model["safety"]["square_send_performed"] is False
    assert model["safety"]["send_hold_modified"] is False


def test_missing_required_fact_fails_closed():
    facts = _reynolds_simple_gig_facts()
    facts["client"]["name"] = ""

    with pytest.raises(ValueError, match="client.name"):
        select_template_profile(facts)

"""The Clara invoice draft must render minor-unit (cents) amounts correctly — a live test-mode
send once showed $25,000 for a $250 invoice because the drafter read cents as dollars."""

from clara_invoice_email_draft_package import build_general_client_invoice_body


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


def test_dollar_amounts_unchanged():
    # non-minor (already-dollar) amounts (< 1000, or floats) are NOT divided by 100
    data = {"client_name": "X", "line_items": [{"description": "Gig", "date": "2026-07-01", "amount": 500.0}]}
    body = build_general_client_invoice_body(data, None)
    assert "$500.00" in body and "$5.00" not in body

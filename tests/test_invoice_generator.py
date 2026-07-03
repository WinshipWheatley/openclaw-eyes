import importlib
import json


def _invoice_data(**overrides):
    data = {
        "invoice_number": "WL-2026-0001",
        "client_name": "St. Anne's",
        "client_email": "draper.carter@gmail.com",
        "project_desc": "Church services",
        "service_date": "2026-06-27",
        "issue_date": "2026-07-03",
        "net_terms": "Due on Receipt",
        "amount_total": 300.0,
        "deposit_paid": 0.0,
        "balance_due": 300.0,
    }
    data.update(overrides)
    return data


def _reload_invoice_generator():
    import invoice_generator

    return importlib.reload(invoice_generator)


def test_output_path_honors_openclaw_invoices_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLAW_INVOICES_DIR", str(tmp_path))

    invoice_generator = _reload_invoice_generator()

    assert invoice_generator.INVOICES_DIR == tmp_path


def test_generate_invoice_pdf_writes_multiple_line_items_and_sums_total(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENCLAW_INVOICES_DIR", raising=False)
    invoice_generator = _reload_invoice_generator()
    monkeypatch.setattr(invoice_generator, "INVOICES_DIR", tmp_path)
    data = _invoice_data(
        amount_total=0,
        balance_due=0,
        line_items=[
            {
                "description": "Wedding",
                "service_date": "2026-06-27",
                "amount": 12500,
            },
            {
                "description": "Church service (10:00)",
                "service_date": "2026-06-28",
                "amount": 12500,
            },
        ],
    )

    pdf_path = invoice_generator.generate_invoice_pdf(data)

    assert pdf_path.parent == tmp_path
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0
    assert data["amount_total"] == 25000
    assert data["balance_due"] == 25000


def test_generate_invoice_pdf_preserves_single_row_path(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENCLAW_INVOICES_DIR", raising=False)
    invoice_generator = _reload_invoice_generator()
    monkeypatch.setattr(invoice_generator, "INVOICES_DIR", tmp_path)
    data = _invoice_data(
        project_desc="Solo sound support",
        service_date="2026-06-29",
        amount_total=300.0,
        deposit_paid=50.0,
        balance_due=250.0,
    )

    pdf_path = invoice_generator.generate_invoice_pdf(data)

    assert pdf_path.parent == tmp_path
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0
    assert data["amount_total"] == 300.0
    assert data["balance_due"] == 250.0
    assert "line_items" not in data


def test_build_st_annes_invoice_data_defaults_to_two_events():
    invoice_generator = _reload_invoice_generator()

    data = invoice_generator.build_st_annes_invoice_data([])

    assert data["client_name"] == "St. Anne's"
    assert data["client_email"] == "draper.carter@gmail.com"
    assert data["amount_total"] == 25000
    assert data["balance_due"] == 25000
    assert data["line_items"] == [
        {"description": "Wedding", "service_date": "2026-06-27", "amount": 12500},
        {
            "description": "Church service (10:00)",
            "service_date": "2026-06-28",
            "amount": 12500,
        },
    ]


def test_build_st_annes_invoice_data_prefers_two_ready_work_log_events(
    tmp_path, monkeypatch
):
    invoice_generator = _reload_invoice_generator()
    events_path = tmp_path / "st_annes_work_log_events.json"
    events_path.write_text(
        json.dumps(
            {
                "staged_events": [
                    {
                        "description": "Wedding Mass",
                        "service_date": "2026-06-27",
                        "invoice_inclusion_status": "READY_FOR_MONTHLY_ROLLUP",
                        "operator_confirmed": True,
                    },
                    {
                        "service_label": "Sunday service",
                        "service_date": "2026-06-28",
                        "invoice_inclusion_status": "READY_FOR_MONTHLY_ROLLUP",
                        "operator_confirmed": True,
                    },
                    {
                        "description": "Smoke",
                        "service_date": "2026-06-01",
                        "invoice_inclusion_status": "NOT_INCLUDED_SMOKE_EVENT",
                        "operator_confirmed": False,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(invoice_generator, "ST_ANNES_WORK_LOG_EVENTS_PATH", events_path)

    data = invoice_generator.build_st_annes_invoice_data(None)

    assert data["line_item_source"] == "st_annes_work_log"
    assert data["line_items"] == [
        {"description": "Wedding Mass", "service_date": "2026-06-27", "amount": 12500},
        {"description": "Sunday service", "service_date": "2026-06-28", "amount": 12500},
    ]


def test_parse_invoice_details_extracts_multiple_line_items():
    from cassandra_brain import _parse_invoice_details

    parsed = _parse_invoice_details(
        "Create invoice for St. Anne's: Wedding on 2026-06-27 $125; "
        "Church service (10:00) on 2026-06-28 $125."
    )

    assert parsed == {
        "client_name": "St. Anne's",
        "project_desc": "Wedding; Church service (10:00)",
        "amount_total": 250.0,
        "deposit_paid": 0.0,
        "service_date": "2026-06-27",
        "line_items": [
            {"description": "Wedding", "service_date": "2026-06-27", "amount": 125.0},
            {
                "description": "Church service (10:00)",
                "service_date": "2026-06-28",
                "amount": 125.0,
            },
        ],
    }

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


def test_build_st_annes_invoice_data_draft_stage_is_default_and_unchanged():
    """Task 134 ACCEPTANCE: draft artifact unchanged -- the default stage (no arg passed)
    behaves byte-identically to before stage-awareness existed."""
    invoice_generator = _reload_invoice_generator()

    data = invoice_generator.build_st_annes_invoice_data([])

    assert data["invoice_number"] == "WL-DRAFT-ST-ANNES"
    assert data["invoice_stage"] == "draft"


def test_build_st_annes_invoice_data_finalized_stage_uses_real_sequential_number(
    tmp_path, monkeypatch
):
    invoice_generator = _reload_invoice_generator()
    monkeypatch.setattr(invoice_generator, "TRACKER_DIR", tmp_path)

    data = invoice_generator.build_st_annes_invoice_data([], stage="finalized")

    assert data["invoice_stage"] == "finalized"
    assert "draft" not in data["invoice_number"].lower()
    assert data["invoice_number"].startswith("WL-")
    counter_files = list(tmp_path.glob("invoice_counter_*.txt"))
    assert len(counter_files) == 1
    assert counter_files[0].read_text().strip() == "1"


def test_build_st_annes_invoice_data_finalized_stage_consumes_counter_each_call(
    tmp_path, monkeypatch
):
    """A real send must never reuse a number -- each finalized call advances the counter."""
    invoice_generator = _reload_invoice_generator()
    monkeypatch.setattr(invoice_generator, "TRACKER_DIR", tmp_path)

    first = invoice_generator.build_st_annes_invoice_data([], stage="finalized")
    second = invoice_generator.build_st_annes_invoice_data([], stage="finalized")

    assert first["invoice_number"] != second["invoice_number"]


def test_build_st_annes_invoice_data_test_stage_previews_without_consuming_counter(
    tmp_path, monkeypatch
):
    """Task 134: workflow-test-mode must never burn a real invoice number."""
    invoice_generator = _reload_invoice_generator()
    monkeypatch.setattr(invoice_generator, "TRACKER_DIR", tmp_path)

    first = invoice_generator.build_st_annes_invoice_data([], stage="test")
    second = invoice_generator.build_st_annes_invoice_data([], stage="test")

    assert first["invoice_stage"] == "test"
    assert "draft" not in first["invoice_number"].lower()
    assert first["invoice_number"].startswith("WL-")
    assert first["invoice_number"] == second["invoice_number"], "test stage must not consume the counter"
    assert not list(tmp_path.glob("invoice_counter_*.txt")), "test stage must not write the counter file"


def test_build_st_annes_invoice_data_rejects_unknown_stage():
    invoice_generator = _reload_invoice_generator()

    try:
        invoice_generator.build_st_annes_invoice_data([], stage="bogus")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_generate_invoice_pdf_finalized_scrubs_draft_wording_from_all_text_fields(
    tmp_path, monkeypatch
):
    """Task 134 ACCEPTANCE: finalized artifact contains zero case-insensitive 'draft'
    occurrences, even when the source data (e.g. an external invoice receipt) carries the
    word somewhere other than invoice_number."""
    monkeypatch.delenv("OPENCLAW_INVOICES_DIR", raising=False)
    invoice_generator = _reload_invoice_generator()
    monkeypatch.setattr(invoice_generator, "INVOICES_DIR", tmp_path)
    data = _invoice_data(
        invoice_number="DRAFT — WL-2026-0099",
        client_name="St. Anne's (DRAFT)",
        project_desc="Church services -- draft copy for review",
        line_items=[{"description": "Wedding (Draft)", "service_date": "2026-06-27", "amount": 12500}],
        invoice_stage="finalized",
    )

    pdf_path = invoice_generator.generate_invoice_pdf(data)

    assert pdf_path.exists()
    assert "draft" not in pdf_path.name.lower()


def test_generate_invoice_pdf_draft_stage_leaves_draft_wording_alone(tmp_path, monkeypatch):
    """Draft marking is CORRECT pre-approval -- scrubbing must not apply to draft stage."""
    monkeypatch.delenv("OPENCLAW_INVOICES_DIR", raising=False)
    invoice_generator = _reload_invoice_generator()
    monkeypatch.setattr(invoice_generator, "INVOICES_DIR", tmp_path)
    data = _invoice_data(invoice_number="WL-DRAFT-ST-ANNES", invoice_stage="draft")

    pdf_path = invoice_generator.generate_invoice_pdf(data)

    assert "draft" in pdf_path.name.lower()


def test_generate_invoice_pdf_test_stage_renders_successfully_with_watermark(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENCLAW_INVOICES_DIR", raising=False)
    invoice_generator = _reload_invoice_generator()
    monkeypatch.setattr(invoice_generator, "INVOICES_DIR", tmp_path)
    data = _invoice_data(invoice_number="WL-2026-0099", invoice_stage="test")

    pdf_path = invoice_generator.generate_invoice_pdf(data)

    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0
    assert "draft" not in pdf_path.name.lower()


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

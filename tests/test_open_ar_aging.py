from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import open_ar_aging as aging


def _money_source(tmp_path: Path) -> Path:
    payload = {
        "read_model_id": "receivables_month_bounded",
        "generated_at": "2026-09-01T23:00:00+00:00",
        "rows": [
            {
                "client_ref": "capital_hilton", "client_display_name": "Capital Hilton", "month": "2026-06",
                "currency_iso": "USD", "amount_known": False, "open_minor_units": None,
                "payment_status": "open_amount_unknown", "needs_reconcile": True, "settled_past_no_compound": False,
                "source_refs": ["canonical_business_fact:capital_hilton:2026-06:check_unverified"],
            },
            {
                "client_ref": "live_arts_md", "client_display_name": "Live Arts MD", "month": "2026-06",
                "currency_iso": "USD", "amount_known": True, "open_minor_units": 0, "paid_minor_units": 100000,
                "payment_status": "settled", "needs_reconcile": False, "settled_past_no_compound": True, "source_refs": [],
            },
            {
                "client_ref": "st_annes", "client_display_name": "St. Anne's", "month": "2026-08",
                "currency_iso": "USD", "amount_known": True, "open_minor_units": 25000,
                "payment_status": "open", "needs_reconcile": False, "settled_past_no_compound": False, "source_refs": [],
            },
            {
                "client_ref": "live_arts_md", "client_display_name": "Live Arts MD", "month": "2026-07",
                "currency_iso": "USD", "amount_known": True, "open_minor_units": 10000,
                "payment_status": "open", "needs_reconcile": False, "settled_past_no_compound": False, "source_refs": [],
            },
        ],
    }
    path = tmp_path / "receivables_month_bounded.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_buckets_actions_and_ordering(tmp_path: Path) -> None:
    payload = aging.build_open_ar_aging(money_source_path=_money_source(tmp_path), today=date(2026, 9, 2), generated_at="2026-09-02T07:35:00+00:00")
    rows = {(r["client_ref"], r["month"]): r for r in payload["rows"]}

    assert ("live_arts_md", "2026-06") not in rows  # settled never appears
    hilton = rows[("capital_hilton", "2026-06")]
    assert hilton["due_date_iso"] == "2026-07-30" and hilton["days_past_due"] == 34
    assert hilton["bucket"] == "30" and hilton["next_action"] == "request_or_confirm_po" and hilton["attention_priority"] == 1
    assert hilton["open_minor_units"] is None

    lamd = rows[("live_arts_md", "2026-07")]
    assert lamd["due_date_iso"] == "2026-08-30" and lamd["days_past_due"] == 3
    assert lamd["bucket"] == "current" and lamd["next_action"] == "watch"

    annes = rows[("st_annes", "2026-08")]
    assert annes["due_date_iso"] == "2026-09-30" and annes["days_past_due"] == 0
    assert annes["bucket"] == "not_due" and annes["next_action"] == "wait"

    assert [r["client_ref"] for r in payload["rows"]] == ["capital_hilton", "live_arts_md", "st_annes"]
    assert payload["summary"]["open_minor_units_total_known"] == 35000
    assert payload["summary"]["unknown_amount_row_count"] == 1
    assert payload["summary"]["oldest_days_past_due"] == 34
    assert payload["money_source_generated_at"] == "2026-09-01T23:00:00+00:00"


def test_every_bucket_and_follow_up_threshold(tmp_path: Path) -> None:
    src = _money_source(tmp_path)
    def lamd(today: date) -> dict:
        payload = aging.build_open_ar_aging(money_source_path=src, today=today)
        return next(r for r in payload["rows"] if r["client_ref"] == "live_arts_md")
    assert lamd(date(2026, 8, 30))["bucket"] == "not_due"
    assert lamd(date(2026, 9, 6))["next_action"] == "follow_up_draft" and lamd(date(2026, 9, 6))["days_past_due"] == 7
    assert lamd(date(2026, 9, 29))["bucket"] == "30" and lamd(date(2026, 9, 29))["attention_priority"] == 2
    assert lamd(date(2026, 10, 29))["bucket"] == "60"
    assert lamd(date(2026, 11, 28))["bucket"] == "90_plus" and lamd(date(2026, 11, 28))["attention_priority"] == 1


def test_missing_money_source_is_honest_and_empty(tmp_path: Path) -> None:
    payload = aging.build_open_ar_aging(money_source_path=tmp_path / "missing.json", today=date(2026, 9, 2))
    assert payload["money_source_present"] is False
    assert payload["rows"] == [] and payload["summary"]["open_row_count"] == 0


def test_export_is_deterministic_and_readable(tmp_path: Path) -> None:
    src = _money_source(tmp_path)
    first = aging.export_open_ar_aging(money_source_path=src, export_root=tmp_path / "rm", today=date(2026, 9, 2), generated_at="2026-09-02T07:35:00+00:00")
    a = (tmp_path / "rm" / "open_ar_aging.json").read_bytes()
    aging.export_open_ar_aging(money_source_path=src, export_root=tmp_path / "rm", today=date(2026, 9, 2), generated_at="2026-09-02T07:35:00+00:00")
    assert (tmp_path / "rm" / "open_ar_aging.json").read_bytes() == a
    operator = (tmp_path / "rm" / "open_ar_aging_OPERATOR.md").read_text(encoding="utf-8")
    assert "- Capital Hilton · Jun 2026 · amount unknown · 34 days past due · request or confirm PO" in operator
    assert "- St. Anne's · Aug 2026 · $250 · due 2026-09-30 · not due" in operator
    assert "Boundary: read-only" in operator
    assert first["open_row_count"] == 3
    payload = json.loads(a)
    assert all(value is False for value in payload["authority_boundary"].values())

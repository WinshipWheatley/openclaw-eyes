from __future__ import annotations

from datetime import date
from pathlib import Path

from recurrence_rule_intake import capture_recurrence_rule_statement
from recurrence_rule_store import RecurrenceRuleStore
import receivables_month_bounded as rmb


def test_no_rule_ever_stated_is_zero_behavior_change(tmp_path):
    """No rule = no derivation -- never guess schedules."""
    payload = rmb.build_receivables_month_bounded(
        g2c_db_path=tmp_path / "no_g2c.sqlite3",
        facts_path=tmp_path / "no_facts.json",
        recurrence_rule_db_path=tmp_path / "never_created.sqlite3",
        generated_at="2026-07-20T00:00:00+00:00",
    )
    assert payload["source_status"]["recurrence_rule_derived_fact_count"] == 0


def test_scheduled_day_passed_with_no_send_evidence_derives_overdue_line(tmp_path):
    rule_db = tmp_path / "rules.sqlite3"
    with RecurrenceRuleStore(rule_db) as store:
        capture_recurrence_rule_statement(
            "I send St Anne's a new invoice on the first of every month",
            store=store,
            now_iso="2026-06-01T12:00:00+00:00",
        )

    payload = rmb.build_receivables_month_bounded(
        g2c_db_path=tmp_path / "no_g2c.sqlite3",
        facts_path=tmp_path / "no_facts.json",
        recurrence_rule_db_path=rule_db,
        generated_at="2026-07-20T00:00:00+00:00",
    )

    assert payload["source_status"]["recurrence_rule_derived_fact_count"] == 1
    rows = [row for row in payload["rows"] if row["client_ref"] == "st_annes" and row["month"] == "2026-07"]
    assert len(rows) == 1
    assert rows[0]["payment_status"] == "expected_uninvoiced"
    assert "recurrence_rule:" in rows[0]["source_refs"][0]


def test_scheduled_day_not_yet_arrived_this_month_does_not_derive(tmp_path):
    rule_db = tmp_path / "rules.sqlite3"
    with RecurrenceRuleStore(rule_db) as store:
        capture_recurrence_rule_statement(
            "I send St Anne's a new invoice on the 15th of every month",
            store=store,
            now_iso="2026-06-01T12:00:00+00:00",
        )

    payload = rmb.build_receivables_month_bounded(
        g2c_db_path=tmp_path / "no_g2c.sqlite3",
        facts_path=tmp_path / "no_facts.json",
        recurrence_rule_db_path=rule_db,
        generated_at="2026-07-10T00:00:00+00:00",
    )

    # today (mocked below via a fixed "current" period would be needed for real accuracy,
    # but build_receivables_month_bounded uses real utcnow() for "today" -- this test proves
    # the intended semantics via _recurrence_rule_derived_facts directly instead.
    buckets: dict = {}
    derived = rmb._recurrence_rule_derived_facts(
        buckets, rule_db_path=rule_db, today=date(2026, 7, 10)
    )
    assert derived == []


def test_existing_send_evidence_suppresses_derivation_for_that_period(tmp_path):
    """After a (test-mode) send event lands, the derivation clears for that month WITHOUT
    any fact edit -- proven here via a canonical fact standing in for send evidence."""
    rule_db = tmp_path / "rules.sqlite3"
    with RecurrenceRuleStore(rule_db) as store:
        capture_recurrence_rule_statement(
            "I send St Anne's a new invoice on the first of every month",
            store=store,
            now_iso="2026-06-01T12:00:00+00:00",
        )

    buckets = {("st_annes", "2026-07", "USD"): {}}
    derived = rmb._recurrence_rule_derived_facts(
        buckets, rule_db_path=rule_db, today=date(2026, 7, 20)
    )
    assert derived == [], "send evidence for the period must suppress derivation, no rule edit needed"


def test_derivation_never_renders_client_as_fully_settled(tmp_path):
    """End-to-end: 'who owes me money' derives the overdue-to-send line citing the rule."""
    from maestro_context_packet import _receivable_answer_topic_facts

    rule_db = tmp_path / "rules.sqlite3"
    with RecurrenceRuleStore(rule_db) as store:
        capture_recurrence_rule_statement(
            "I send St Anne's a new invoice on the first of every month",
            store=store,
            now_iso="2026-06-01T12:00:00+00:00",
        )

    payload = rmb.build_receivables_month_bounded(
        g2c_db_path=tmp_path / "no_g2c.sqlite3",
        facts_path=tmp_path / "no_facts.json",
        recurrence_rule_db_path=rule_db,
        generated_at="2026-07-20T00:00:00+00:00",
    )
    facts = [
        {
            "topic": "receivable_month_bounded",
            "structured_fact": True,
            **row,
        }
        for row in payload["rows"]
        if row["client_ref"] == "st_annes"
    ]
    answer_facts, _proof = _receivable_answer_topic_facts(facts)

    assert answer_facts
    value = str(answer_facts[0]["value"])
    assert "St Anne's" in value or "St. Anne's" in value
    assert "fully settled" not in value.lower()

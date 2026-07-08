from __future__ import annotations

from recurrence_rule_intake import (
    capture_recurrence_rule_statement,
    detect_recurrence_rule_statement,
)
from recurrence_rule_store import RecurrenceRuleStore


def test_detect_matches_explicit_client_named_statement():
    detected = detect_recurrence_rule_statement(
        "I send St Anne's a new invoice on the first of every month"
    )
    assert detected == {"client_text": "St Anne's", "schedule_day": 1}


def test_detect_matches_every_month_on_the_nth_phrasing():
    detected = detect_recurrence_rule_statement("I send Live Arts an invoice every month on the 15th")
    assert detected == {"client_text": "Live Arts", "schedule_day": 15}


def test_detect_returns_none_for_ordinary_questions_and_instructions():
    assert detect_recurrence_rule_statement("did St Anne's pay us?") is None
    assert detect_recurrence_rule_statement("who owes me money right now?") is None
    assert detect_recurrence_rule_statement("pay the St Anne's invoice now") is None


def test_detect_returns_none_when_no_client_named_in_sentence():
    """'send out' -- 'out' is part of the verb phrase, not a client. No explicit client in
    the same sentence needs conversation-context resolution (136b+), not a guess."""
    assert detect_recurrence_rule_statement("I send out a new invoice on the first of every month") is None


def test_capture_persists_rule_and_confirms_plainly(tmp_path):
    with RecurrenceRuleStore(tmp_path / "rules.sqlite3") as store:
        result = capture_recurrence_rule_statement(
            "I send St Anne's a new invoice on the first of every month",
            store=store,
            now_iso="2026-07-07T20:00:00+00:00",
        )
        persisted = store.latest_unsuperseded_for_client("st_annes", "invoice_send")

    assert result["status"] == "captured"
    assert result["reply"] == "Got it — St. Anne's invoices go out on the first monthly. I'll track it."
    assert persisted is not None
    assert persisted.client_ref == "st_annes"
    assert persisted.schedule_day == 1
    assert persisted.truth_status == "operator_directive"
    assert persisted.provenance_raw == "I send St Anne's a new invoice on the first of every month"


def test_capture_returns_none_for_non_rule_text(tmp_path):
    with RecurrenceRuleStore(tmp_path / "rules.sqlite3") as store:
        result = capture_recurrence_rule_statement("did St Anne's pay us?", store=store)
    assert result is None


def test_capture_unknown_client_asks_one_clarifying_question_never_guesses(tmp_path):
    with RecurrenceRuleStore(tmp_path / "rules.sqlite3") as store:
        result = capture_recurrence_rule_statement(
            "I send Acme Corp a new invoice on the first of every month",
            store=store,
        )
        # Nothing was persisted -- an unresolved client must never silently create a rule.
        assert store.active_rules() == []

    assert result["status"] == "needs_operator_review"
    assert "Acme Corp" in result["reply"]


def test_capture_correction_supersedes_and_readback_includes_old_and_new(tmp_path):
    """Restating the SAME deterministic shape with a different day is a correction --
    prose corrections ('actually the 15th now') are 136b/d's semantic-recognizer territory;
    this deterministic fast-path still supersedes correctly whenever it detects a second
    statement for the same client."""
    with RecurrenceRuleStore(tmp_path / "rules.sqlite3") as store:
        capture_recurrence_rule_statement(
            "I send St Anne's a new invoice on the first of every month",
            store=store,
            now_iso="2026-06-01T12:00:00+00:00",
        )
        result = capture_recurrence_rule_statement(
            "I send St Anne's a new invoice on the 15th of every month",
            store=store,
            now_iso="2026-08-15T09:00:00+00:00",
        )
        latest = store.latest_unsuperseded_for_client("st_annes", "invoice_send")
        history = store.all_versions_for_client("st_annes")

    assert result["status"] == "captured"
    assert "was:" in result["reply"]
    assert "the first" in result["reply"]
    assert "15th" in result["reply"] or "fifteenth" in result["reply"]
    assert latest.schedule_day == 15
    assert len(history) == 2, "correction must supersede, not overwrite -- both versions retained"


def test_capture_correction_after_simulated_gap_behaves_identically_to_five_minutes(tmp_path):
    """Corrections bind to the durable rule store, never to session/conversation age -- a
    60-day gap and a 5-minute gap behave identically."""
    with RecurrenceRuleStore(tmp_path / "rules.sqlite3") as store:
        capture_recurrence_rule_statement(
            "I send St Anne's a new invoice on the first of every month",
            store=store,
            now_iso="2026-06-01T12:00:00+00:00",
        )
        # 60 days later, a different call, same durable store -- no session/conversation state
        # threaded through, proving time-gap-free behavior.
        result = capture_recurrence_rule_statement(
            "I send St Anne's a new invoice on the 15th of every month",
            store=store,
            now_iso="2026-07-31T12:00:00+00:00",
        )
        latest = store.latest_unsuperseded_for_client("st_annes", "invoice_send")

    assert result["status"] == "captured"
    assert latest.schedule_day == 15

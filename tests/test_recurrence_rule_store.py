from __future__ import annotations

import pytest

from recurrence_rule_record import create_recurrence_rule
from recurrence_rule_store import RecurrenceRuleStore


def _rule(**overrides):
    defaults = dict(
        client_ref="st_annes",
        event_type="invoice_send",
        schedule_kind="monthly_day",
        schedule_day=1,
        stated_as_of="2026-07-07T20:00:00+00:00",
        provenance_raw="I send St Anne's a new invoice on the first of every month",
        source_ref="operator_maestro_chat:test",
    )
    defaults.update(overrides)
    return create_recurrence_rule(**defaults)


def test_latest_unsuperseded_returns_none_when_never_stated(tmp_path):
    with RecurrenceRuleStore(tmp_path / "rules.sqlite3") as store:
        assert store.latest_unsuperseded_for_client("st_annes", "invoice_send") is None


def test_append_then_latest_unsuperseded_returns_the_rule(tmp_path):
    record = _rule()
    with RecurrenceRuleStore(tmp_path / "rules.sqlite3") as store:
        store.append(record)
        latest = store.latest_unsuperseded_for_client("st_annes", "invoice_send")

    assert latest is not None
    assert latest.rule_version_id == record.rule_version_id
    assert latest.schedule_day == 1


def test_correction_supersedes_old_version_never_mutates_it(tmp_path):
    v1 = _rule(schedule_day=1)
    with RecurrenceRuleStore(tmp_path / "rules.sqlite3") as store:
        store.append(v1)
        v2 = _rule(
            rule_id=v1.rule_id,
            schedule_day=15,
            provenance_raw="actually the 15th now",
            supersedes_rule_version_id=v1.rule_version_id,
        )
        store.append(v2)

        latest = store.latest_unsuperseded_for_client("st_annes", "invoice_send")
        history = store.all_versions_for_client("st_annes")

    assert latest.rule_version_id == v2.rule_version_id
    assert latest.schedule_day == 15
    # v1 remains in history untouched, in provenance -- never edited or deleted.
    assert len(history) == 2
    v1_in_history = next(r for r in history if r.rule_version_id == v1.rule_version_id)
    assert v1_in_history.schedule_day == 1
    assert v1_in_history.provenance_raw == v1.provenance_raw


def test_termination_clears_the_active_rule(tmp_path):
    v1 = _rule()
    with RecurrenceRuleStore(tmp_path / "rules.sqlite3") as store:
        store.append(v1)
        v2 = _rule(
            rule_id=v1.rule_id,
            provenance_raw="stop invoicing them monthly",
            supersedes_rule_version_id=v1.rule_version_id,
            terminated=True,
        )
        store.append(v2)

        latest = store.latest_unsuperseded_for_client("st_annes", "invoice_send")
        history = store.all_versions_for_client("st_annes")

    assert latest is None, "a terminated rule must not derive anything"
    assert len(history) == 2, "termination is still a version, history retained"


def test_undo_restores_prior_content_as_a_new_version(tmp_path):
    """Undo = a NEW version restoring the prior content, never mutation (supersession both
    ways)."""
    v1 = _rule(schedule_day=1)
    with RecurrenceRuleStore(tmp_path / "rules.sqlite3") as store:
        store.append(v1)
        v2 = _rule(rule_id=v1.rule_id, schedule_day=15, supersedes_rule_version_id=v1.rule_version_id)
        store.append(v2)
        v3_undo = _rule(
            rule_id=v1.rule_id,
            schedule_day=v1.schedule_day,
            provenance_raw="scrap that, go back to the old way",
            supersedes_rule_version_id=v2.rule_version_id,
        )
        store.append(v3_undo)

        latest = store.latest_unsuperseded_for_client("st_annes", "invoice_send")
        history = store.all_versions_for_client("st_annes")

    assert latest.rule_version_id == v3_undo.rule_version_id
    assert latest.schedule_day == 1
    assert len(history) == 3


def test_active_rules_lists_every_client_latest_unsuperseded(tmp_path):
    with RecurrenceRuleStore(tmp_path / "rules.sqlite3") as store:
        store.append(_rule(client_ref="st_annes", schedule_day=1))
        store.append(_rule(client_ref="live_arts_md", schedule_day=5, rule_id="rule:live-arts"))

        active = store.active_rules(event_type="invoice_send")

    client_refs = {r.client_ref for r in active}
    assert client_refs == {"st_annes", "live_arts_md"}


def test_invalid_schedule_day_rejected():
    with pytest.raises(ValueError):
        _rule(schedule_day=29)
    with pytest.raises(ValueError):
        _rule(schedule_day=0)


def test_unknown_event_type_rejected():
    with pytest.raises(ValueError):
        _rule(event_type="bogus")

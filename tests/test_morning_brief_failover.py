import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from business_ops_ledger import init_business_ops_ledger
from morning_brief_failover import (
    DETERMINISTIC_PROVIDER,
    PROVIDER_ORDER,
    MorningBriefFacts,
    build_deterministic_morning_brief,
    cadence_dispatcher_stub,
    load_morning_brief_facts,
    run_morning_brief_failover,
    validate_morning_brief,
)


FIXED_NOW = datetime(2026, 6, 15, 8, 0, 0)


def _facts() -> MorningBriefFacts:
    return MorningBriefFacts(
        generated_at=FIXED_NOW.isoformat(timespec="seconds"),
        ledger_path="/tmp/test-ledger.sqlite",
        latest_event_summary="The ledger shows one review packet ready for operator attention.",
        pending_approval_packets=1,
        pending_side_effects=0,
        open_packet_count=2,
        canonical_fact_count=3,
        source_notes=("test_fixture",),
    )


def _valid_provider(name: str):
    def _provider(_facts: MorningBriefFacts) -> str:
        return (
            f"{name.title()} morning brief. The ledger shows one review packet ready for operator attention. "
            "No external send was attempted. Next safe move: inspect pending approvals and keep the day bounded."
        )

    return _provider


def _timeout_provider(_facts: MorningBriefFacts) -> str:
    raise TimeoutError("provider timed out")


def test_first_valid_provider_wins_and_does_not_call_later_links():
    called: list[str] = []

    def cassandra(_facts: MorningBriefFacts) -> str:
        called.append("cassandra")
        return _valid_provider("cassandra")(_facts)

    def chief(_facts: MorningBriefFacts) -> str:
        called.append("chief")
        raise AssertionError("later provider should not be called")

    result = run_morning_brief_failover(
        providers={"cassandra": cassandra, "chief": chief},
        facts=_facts(),
    )

    assert result.provider == "cassandra"
    assert result.text.startswith("Cassandra morning brief.")
    assert [attempt.provider for attempt in result.attempts] == ["cassandra"]
    assert result.attempts[0].ok is True
    assert result.sent is False
    assert called == ["cassandra"]


@pytest.mark.parametrize(
    ("failed_links", "winner"),
    [
        (("cassandra",), "chief"),
        (("cassandra", "chief"), "hermes"),
        (("cassandra", "chief", "hermes"), "guardian"),
    ],
)
def test_each_failed_link_falls_through_to_next_provider(failed_links, winner):
    providers = {}
    for name in PROVIDER_ORDER:
        providers[name] = _timeout_provider if name in failed_links else _valid_provider(name)

    result = run_morning_brief_failover(
        providers=providers,
        facts=_facts(),
    )

    assert result.provider == winner
    assert result.deterministic is False
    assert result.attempts[-1].provider == winner
    assert result.attempts[-1].ok is True
    for attempt in result.attempts[:-1]:
        assert attempt.ok is False
        assert attempt.reason == "timeout"


def test_all_upstream_failures_return_deterministic_template_from_ledger(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    _seed_ledger(db_path)
    providers = {name: _timeout_provider for name in PROVIDER_ORDER}

    result = run_morning_brief_failover(
        providers=providers,
        db_path=db_path,
        now=FIXED_NOW,
    )

    assert result.provider == DETERMINISTIC_PROVIDER
    assert result.deterministic is True
    assert result.sent is False
    assert result.text.startswith("Morning brief safe mode.")
    assert "Open approval packets: 1" in result.text
    assert "Pending side effects: 1" in result.text
    assert "Canonical facts recorded: 1" in result.text
    assert "Capital Hilton packet is waiting for review" in result.text
    assert result.attempts[-1].provider == DETERMINISTIC_PROVIDER
    assert result.attempts[-1].ok is True


def test_missing_ledger_still_returns_clean_deterministic_brief(tmp_path):
    missing = tmp_path / "missing.sqlite"
    result = run_morning_brief_failover(
        providers={name: lambda _facts: "null" for name in PROVIDER_ORDER},
        db_path=missing,
        now=FIXED_NOW,
    )

    assert result.provider == DETERMINISTIC_PROVIDER
    assert result.deterministic is True
    assert "ledger_missing" in result.text
    assert "No external send" in result.text


def test_deterministic_template_never_raises_on_bad_fact_shape():
    text = build_deterministic_morning_brief(object())  # type: ignore[arg-type]

    assert text.startswith("Morning brief safe mode.")
    assert "ledger facts were unavailable" in text


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("Traceback: KeyError: broken", "empty_or_too_short"),
        ("Niles morning brief says everything is probably fine.", "wrong_author_niles_insulated"),
        ("You are Cassandra. Current context: prompt echo", "garbage_or_prompt_echo"),
    ],
)
def test_validator_rejects_garbage_prompt_echo_and_wrong_author(text, reason):
    ok, actual_reason = validate_morning_brief(text)

    assert ok is False
    assert actual_reason == reason


def test_load_morning_brief_facts_reads_bounded_ledger_snapshot(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    _seed_ledger(db_path)

    facts = load_morning_brief_facts(db_path=db_path, now=FIXED_NOW)

    assert facts.generated_at == "2026-06-15T08:00:00"
    assert facts.pending_approval_packets == 1
    assert facts.pending_side_effects == 1
    assert facts.open_packet_count == 1
    assert facts.canonical_fact_count == 1
    assert facts.latest_event_summary == "Capital Hilton packet is waiting for review."
    assert facts.source_notes == ("ledger_read",)


def test_cadence_dispatcher_stub_is_no_runtime_authority():
    stub = cadence_dispatcher_stub()

    assert stub["status"] == "stub_no_runtime_scheduling"
    assert stub["send_authority"] is False
    assert stub["service_restart_authority"] is False
    assert stub["cadence"][0]["failover"] == list(PROVIDER_ORDER) + [DETERMINISTIC_PROVIDER]
    assert "chief_watcher_brain.py" in stub["wire_candidates"]
    assert "chief_end_of_day_review.py" in stub["wire_candidates"]


def _seed_ledger(db_path: Path) -> None:
    init_business_ops_ledger(str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO events (
                event_id, ts, event_type, actor, operator_visible_summary,
                raw_sensitive_data_stored, replay_safe
            )
            VALUES (?, ?, ?, ?, ?, 0, 1)
            """,
            (
                "evt-brief",
                "2026-06-15T07:55:00",
                "overnight_packet",
                "codex",
                "Capital Hilton packet is waiting for review.",
            ),
        )
        conn.execute(
            """
            INSERT INTO packets (
                packet_id, event_id, intent_name, request_category, actor_name,
                execution_authority, approval_required, approval_tier,
                action_status, packet_json_safe
            )
            VALUES (?, ?, ?, ?, ?, 0, 1, ?, ?, ?)
            """,
            (
                "packet-brief",
                "evt-brief",
                "morning_review",
                "operator_review",
                "codex",
                "operator_final_send",
                "pending_approval",
                "{}",
            ),
        )
        conn.execute(
            """
            INSERT INTO side_effects (
                packet_id, effect_type, status, approval_required,
                approval_tier, replay_safe, external_ref
            )
            VALUES (?, ?, ?, 1, ?, 0, NULL)
            """,
            (
                "packet-brief",
                "email_draft_candidate",
                "pending_approval",
                "operator_final_send",
            ),
        )
        conn.execute(
            """
            INSERT INTO canonical_facts (
                fact_id, source_file, section_heading, source_commit,
                content_hash, fact_text, sensitivity_class, allowed_actors
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "fact-brief",
                "overnight.md",
                "Queue",
                "test",
                "sha256:test",
                "Morning brief failover exists.",
                "internal",
                "codex,claude",
            ),
        )
        conn.commit()

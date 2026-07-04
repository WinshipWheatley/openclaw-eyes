from datetime import date, datetime
import re

from cassandra_context_packet import format_cassandra_context_packet
from fleet_temporal_anchor import temporal_anchor_text
from guardian_context_packet import format_guardian_context_packet
from hermes_context_packet import format_hermes_context_packet
from maestro_context_packet import format_maestro_context_packet


def _minimal_packet(packet_id: str) -> dict:
    return {
        "packet_id": packet_id,
        "generated_at": "2026-07-08T12:00:00+00:00",
        "facts": [
            {
                "topic": "test",
                "label": "Known fact",
                "value": "Packet formatter test fact.",
                "source_ref": "tests/fixture",
                "provenance": "test",
                "pii_tier": "PUBLIC",
            }
        ],
        "bounds": {},
    }


def _date_after(label: str, text: str) -> date:
    match = re.search(rf"{re.escape(label)}:?\s+(\d{{4}}-\d{{2}}-\d{{2}})", text)
    assert match, f"missing {label} date in:\n{text}"
    return date.fromisoformat(match.group(1))


def _assert_anchor_in_formatter_output(output: str) -> None:
    lines = output.splitlines()
    generated_index = next(i for i, line in enumerate(lines) if line.startswith("Generated:"))
    grounded_index = next(i for i, line in enumerate(lines) if line.startswith("Grounded facts"))
    assert lines[generated_index + 1].startswith("TEMPORAL ANCHOR")
    assert generated_index < grounded_index
    assert "TEMPORAL ANCHOR" in output
    assert "Today is" in output
    assert "system clock" in output
    assert "NOT the ledger" in output


def test_temporal_anchor_resolves_weekday_anchors_from_injected_now():
    today = date(2026, 7, 8)
    text = temporal_anchor_text(now=datetime(2026, 7, 8, 9, 30))

    assert "Today is 2026-07-08 (Wednesday)." in text
    assert "system clock" in text
    assert "NOT the ledger" in text

    saturday = _date_after("Saturday", text)
    sunday = _date_after("Sunday", text)
    friday = _date_after("Most recent Friday", text)

    assert saturday.weekday() == 5
    assert sunday.weekday() == 6
    assert friday.weekday() == 4
    assert saturday <= today
    assert sunday <= today
    assert friday <= today


def test_maestro_formatter_includes_temporal_anchor():
    output = format_maestro_context_packet(_minimal_packet("maestro:test"))
    _assert_anchor_in_formatter_output(output)


def test_cassandra_formatter_includes_temporal_anchor():
    output = format_cassandra_context_packet(_minimal_packet("cassandra:test"))
    _assert_anchor_in_formatter_output(output)


def test_hermes_formatter_includes_temporal_anchor():
    output = format_hermes_context_packet(_minimal_packet("hermes:test"))
    _assert_anchor_in_formatter_output(output)


def test_guardian_formatter_includes_temporal_anchor():
    output = format_guardian_context_packet(_minimal_packet("guardian:test"))
    _assert_anchor_in_formatter_output(output)

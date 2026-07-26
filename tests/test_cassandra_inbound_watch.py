"""Cassandra notices on her own — and only when she should."""

from __future__ import annotations

import json
from pathlib import Path

import cassandra_inbound_watch as watch
import client_repair_escalation as escalation


MEGAN = {
    "message_id": "m1",
    "from_email": "megan@livearts.example",
    "subject": "Invoice again",
    "snippet": "This is the third time the invoice has been late and it's unacceptable.",
}
HAPPY = {
    "message_id": "m2",
    "from_email": "megan@livearts.example",
    "subject": "Thanks",
    "snippet": "Got it, thanks so much - looks great.",
}
ROBOT = {
    "message_id": "m3",
    "from_email": "noreply@stripe.example",
    "subject": "Payment failed",
    "snippet": "Your payment failed and is still waiting. This is unacceptable.",
}
OPERATOR = {
    "message_id": "m4",
    "from_email": "winshiplive@gmail.com",
    "subject": "note to self",
    "snippet": "this is the third time it's unacceptable",
}
STRANGER = {
    "message_id": "m5",
    "from_email": "someone@nowhere.example",
    "subject": "you people",
    "snippet": "This is the third time and it's unacceptable.",
}


def _broker(messages):
    def _call(agent, capability, params):
        assert agent == "cassandra"
        assert capability == watch.METADATA_CAPABILITY, "an unattended scan must stay Class A"
        return {"ok": True, "data": list(messages), "error": ""}

    return _call


def _known(from_email):
    return {"name": "Megan Rivas", "client_slug": "live_arts_md"} if "livearts" in from_email else None


def _scan(messages, tmp_path, **kw):
    return watch.scan_inbound(
        broker_call=_broker(messages),
        resolve_contact=_known,
        state_path=tmp_path / "seen.json",
        queue_path=tmp_path / "queue.jsonl",
        **kw,
    )


def test_an_unhappy_known_client_is_filed_without_being_asked(tmp_path: Path) -> None:
    result = _scan([MEGAN], tmp_path)

    assert result["status"] == "INBOUND_SCAN_COMPLETE"
    assert len(result["filed"]) == 1
    item = result["filed"][0]
    assert item["client_ref"] == "live_arts_md"
    assert item["owner"] == "chief"
    assert item["severity"] == "trust_damage"
    assert "unacceptable" in item["client_verbatim"]


def test_the_quote_is_a_real_substring_of_what_the_client_wrote(tmp_path: Path) -> None:
    """The verbatim rule survives the scan path, not just the manual one."""

    result = _scan([MEGAN], tmp_path)
    item = result["filed"][0]

    assert escalation.is_verbatim(
        item["client_verbatim"], f"{MEGAN['subject']}. {MEGAN['snippet']}"
    )
    assert item["quote_source"] == "gmail_snippet", "a preview must not pass as the whole letter"


def test_a_happy_client_opens_nothing(tmp_path: Path) -> None:
    result = _scan([HAPPY], tmp_path)

    assert result["filed"] == []


def test_machinery_is_not_a_client(tmp_path: Path) -> None:
    """A failed-payment robot is not a counterparty losing patience."""

    result = _scan([ROBOT], tmp_path)

    assert result["filed"] == []
    assert any(row["reason"] == "automated_sender" for row in result["skipped"])


def test_the_operator_is_the_captain_not_a_client(tmp_path: Path) -> None:
    result = _scan([OPERATOR], tmp_path)

    assert result["filed"] == []
    assert any(row["reason"] == "operator_or_unknown_sender" for row in result["skipped"])


def test_an_unrecognised_sender_is_surfaced_not_silently_dropped(tmp_path: Path) -> None:
    """Precision over recall — but the miss has to be visible."""

    result = _scan([STRANGER], tmp_path)

    assert result["filed"] == []
    assert len(result["unrecognised"]) == 1
    assert result["unrecognised"][0]["from_email"] == "someone@nowhere.example"


def test_the_same_message_is_never_filed_twice(tmp_path: Path) -> None:
    """A scheduled scan re-reads the same inbox. It must not re-open the ticket."""

    first = _scan([MEGAN], tmp_path)
    second = _scan([MEGAN], tmp_path)

    assert len(first["filed"]) == 1
    assert second["filed"] == [], "a second scan re-filed an already-filed complaint"
    assert len(escalation.load_queue(tmp_path / "queue.jsonl")) == 1


def test_a_dry_run_files_nothing_and_remembers_nothing(tmp_path: Path) -> None:
    result = _scan([MEGAN], tmp_path, dry_run=True)

    assert result["filed"][0]["dry_run"] is True
    assert not (tmp_path / "queue.jsonl").exists()
    # and the message is still unseen, so arming it for real still catches it
    live = _scan([MEGAN], tmp_path)
    assert len(live["filed"]) == 1


def test_a_broken_inbox_read_says_so_instead_of_reporting_all_clear(tmp_path: Path) -> None:
    """"Nothing found" and "could not look" must never be the same answer."""

    def _fails(agent, capability, params):
        return {"ok": False, "data": None, "error": "token expired"}

    result = watch.scan_inbound(
        broker_call=_fails,
        resolve_contact=_known,
        state_path=tmp_path / "seen.json",
        queue_path=tmp_path / "queue.jsonl",
    )

    assert result["status"] == "INBOUND_SCAN_FAILED"
    assert "token expired" in result["detail"]
    assert result["filed"] == []


def test_the_scan_never_reaches_for_the_gated_body_capability(tmp_path: Path) -> None:
    """Reading bodies is Class B. An unattended scan must not trip that gate."""

    used: list[str] = []

    def _record(agent, capability, params):
        used.append(capability)
        return {"ok": True, "data": [MEGAN], "error": ""}

    watch.scan_inbound(
        broker_call=_record,
        resolve_contact=_known,
        state_path=tmp_path / "seen.json",
        queue_path=tmp_path / "queue.jsonl",
    )

    assert used == [watch.METADATA_CAPABILITY]
    assert "google.gmail.read.body" not in used


def test_the_read_model_admits_it_only_saw_the_snippet(tmp_path: Path) -> None:
    model = watch.build_read_model(_scan([MEGAN], tmp_path))

    assert model["body_read"] is False
    assert model["quote_source"] == "gmail_snippet"
    assert model["filed_count"] == 1


def test_a_mixed_inbox_sorts_itself_out(tmp_path: Path) -> None:
    result = _scan([MEGAN, HAPPY, ROBOT, OPERATOR, STRANGER], tmp_path)

    assert result["examined"] == 5
    assert len(result["filed"]) == 1
    assert len(result["unrecognised"]) == 1
    assert len(result["skipped"]) == 3

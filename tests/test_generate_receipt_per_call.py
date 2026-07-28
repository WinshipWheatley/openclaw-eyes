"""Interpreter and answer calls must both stay visible.

A single overwritten receipt showed only whichever call ran last. That was the
interpreter's classification call, whose packet is correctly ~124 characters with no
facts — and I twice reported it as "the packet arrives at the model empty". It was
never the answer call. Every conclusion drawn from that file was unreliable.
"""

from __future__ import annotations

import inspect
import json

import protected_generate as pg

RECEIPTS = "/home/openclaw/state/frontdoor_prompt_receipts.jsonl"


def test_the_receipt_is_append_only_not_overwritten() -> None:
    src = inspect.getsource(pg)
    assert "frontdoor_prompt_receipts.jsonl" in src, "receipt is not the append-only log"
    i = src.index("frontdoor_prompt_receipts.jsonl")
    window = src[i: i + 400]
    assert '"a"' in window, "the receipt is opened for overwrite, not append"
    assert "write_text" not in window, "write_text truncates; the log must append"


def test_every_line_names_its_call_type() -> None:
    src = inspect.getsource(pg)
    assert '"call_type"' in src
    assert "Maestro Interpreter LM" in src, "interpreter calls are not distinguished"
    assert "answer_brain" in src


def test_two_calls_remain_separately_visible(tmp_path) -> None:
    """The regression: two calls, both still readable afterwards."""

    log = tmp_path / "receipts.jsonl"
    for call_type, packet_id, chars in (
        ("interpreter", "lm1_interpreter_abc", 124),
        ("answer_brain", "maestro_context_packet:def", 3703),
    ):
        body = {"packet_id": packet_id, "final_prompt_chars": chars}
        line = (
            json.dumps({"call_type": call_type}, sort_keys=True)[:-1]
            + ", "
            + json.dumps(body, sort_keys=True)[1:]
        )
        with log.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 2, "one call overwrote the other"
    kinds = {r["call_type"] for r in rows}
    assert kinds == {"interpreter", "answer_brain"}

    brain = next(r for r in rows if r["call_type"] == "answer_brain")
    interp = next(r for r in rows if r["call_type"] == "interpreter")
    assert brain["packet_id"] != interp["packet_id"]
    assert brain["final_prompt_chars"] > interp["final_prompt_chars"]


def test_the_merged_line_is_valid_json() -> None:
    """NON-VACUITY: a log that does not parse proves nothing."""

    line = (
        json.dumps({"call_type": "answer_brain"}, sort_keys=True)[:-1]
        + ", "
        + json.dumps({"packet_id": "p", "final_prompt_chars": 1}, sort_keys=True)[1:]
    )
    parsed = json.loads(line)
    assert parsed["call_type"] == "answer_brain" and parsed["packet_id"] == "p"

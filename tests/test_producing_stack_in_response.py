"""The producing stack rides in the response, not in a side receipt.

A separate receipt file failed in exactly the way that matters: the marker sat in a
function the live turn never executed, captured nothing, and that absence read as
"no writer" rather than "wrong spot". This function's return value IS what gets
written, so stamping the frames here cannot be lost to whichever function performs
the write.
"""

from __future__ import annotations

import inspect

import openclaw_request_processor as orp

FIELD = "_diagnostic_producing_stack"


def _stamp(payload=None, path="openclaw_response_for_mac_test.json"):
    return orp.stamp_proof_to_response_source_response_path(
        payload if payload is not None else {"one_line_answer": "x"},
        source_response_path=path,
    )


def test_the_field_is_present_on_every_stamped_response() -> None:
    assert FIELD in _stamp()


def test_it_records_real_frames_not_a_constant() -> None:
    """NON-VACUITY: the frames must name the actual caller."""

    def caller_marker():
        return _stamp()

    stack = caller_marker()[FIELD]
    assert stack["frames"], "no frames captured"
    assert any("caller_marker" in f for f in stack["frames"])


def test_frames_carry_only_basename_line_and_function() -> None:
    for frame in _stamp()[FIELD]["frames"]:
        assert frame.count(":") >= 2
        assert "/" not in frame.split(":")[0], "a full path leaked into the stack"


def test_the_correlation_is_the_response_basename() -> None:
    stack = _stamp(path="/mnt/e/openclaw/x/openclaw_response_for_mac_maestro_telegram_42.json")[FIELD]
    assert stack["correlation"] == "openclaw_response_for_mac_maestro_telegram_42.json"
    assert "/mnt/e" not in stack["correlation"], "a path leaked into the correlation"


def test_no_content_locals_or_args_are_recorded() -> None:
    import json

    payload = {"one_line_answer": "SENSITIVE-ANSWER-TEXT", "packet_text": "SECRET-PACKET"}
    stack = _stamp(payload)[FIELD]
    blob = json.dumps(stack)
    for forbidden in ("SENSITIVE-ANSWER-TEXT", "SECRET-PACKET"):
        assert forbidden not in blob, f"{forbidden} leaked into the diagnostic"

    # Structural, not a substring scan: a frame is exactly basename:line:function,
    # so there is nowhere for a local or an argument to hide. Scanning for the words
    # "locals"/"args" fails on pytest's own internal frame names — the same
    # crude-substring trap that has produced two false failures tonight.
    for frame in stack["frames"]:
        parts = frame.split(":")
        assert len(parts) == 3, f"unexpected frame shape: {frame}"
        assert parts[0].endswith(".py") and parts[1].isdigit()
    assert set(stack) == {"correlation", "at", "frames"}, "the diagnostic grew a field"


def test_the_original_payload_is_otherwise_unchanged() -> None:
    """Additive only: the stamp adds one key and rewrites nothing else."""

    payload = {"one_line_answer": "x", "source_refs": ["a.json"]}
    out = _stamp(payload)
    assert out["one_line_answer"] == "x"
    assert out["source_refs"] == ["a.json"]
    assert set(out) - set(payload) == {FIELD}


def test_it_writes_no_production_state() -> None:
    """Nothing on disk: the diagnostic travels in the response only."""

    from pathlib import Path

    before = Path("/home/openclaw/state").exists() and set(
        p.name for p in Path("/home/openclaw/state").glob("*")
    ) or set()
    _stamp()
    after = Path("/home/openclaw/state").exists() and set(
        p.name for p in Path("/home/openclaw/state").glob("*")
    ) or set()
    assert before == after, "the stamp authored production state"


def test_the_stamp_is_wired_at_the_write_path() -> None:
    src = inspect.getsource(orp.stamp_proof_to_response_source_response_path)
    assert FIELD in src
    assert "return payload" in src.split(FIELD)[1], "stamp happens after the return"

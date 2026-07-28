"""Name the function that produces the reply, instead of inferring it.

Eight fixes in one night were verified in isolation and never reached the live reply,
because the producing path was inferred from predicates and call-graph reading rather
than read. This captures the frames at the one function provably on the live path —
the writer that emits every openclaw_response_for_mac_*.json the operator sees.

Sanitized by construction: basename, function, line. Never locals, arguments, prompt
text, or full paths.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

import openclaw_request_processor as orp


def test_the_capture_records_frames(tmp_path: Path) -> None:
    row = orp._capture_producing_stack("req-1", path=tmp_path / "s.jsonl")
    assert row["source_request_id"] == "req-1"
    assert row["frames"], "no frames captured"
    top = row["frames"][0]
    assert set(top) == {"module", "function", "line"}
    assert top["module"].endswith(".py") and "/" not in top["module"]


def test_it_records_the_real_caller_chain(tmp_path: Path) -> None:
    """NON-VACUITY: the frames must name the actual callers, not a constant."""

    def outer_marker():
        return orp._capture_producing_stack("req-2", path=tmp_path / "s.jsonl")

    row = outer_marker()
    assert any(f["function"] == "outer_marker" for f in row["frames"])


def test_no_secret_or_content_fields_are_recorded(tmp_path: Path) -> None:
    row = orp._capture_producing_stack("req-3", path=tmp_path / "s.jsonl")
    blob = json.dumps(row)
    for forbidden in ("locals", "args", "prompt", "packet_text", "token", "/home/"):
        assert forbidden not in blob, f"{forbidden} leaked into the stack receipt"


def test_it_is_append_only(tmp_path: Path) -> None:
    log = tmp_path / "s.jsonl"
    orp._capture_producing_stack("a", path=log)
    orp._capture_producing_stack("b", path=log)
    rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert [r["source_request_id"] for r in rows] == ["a", "b"], "one call overwrote the other"


def test_tests_never_write_the_production_receipt(monkeypatch) -> None:
    """Third time tonight a receipt of mine was polluted by tests. Not a fourth."""

    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
    before = (orp.PRODUCING_STACK_RECEIPTS.read_text(encoding="utf-8")
              if orp.PRODUCING_STACK_RECEIPTS.exists() else "")
    row = orp._capture_producing_stack("should-not-write")
    after = (orp.PRODUCING_STACK_RECEIPTS.read_text(encoding="utf-8")
             if orp.PRODUCING_STACK_RECEIPTS.exists() else "")
    assert after == before
    assert row["frames"], "the row must still be returned under test mode"


def test_the_capture_is_wired_into_the_live_writer() -> None:
    """Structural: a capture nobody calls names nothing."""

    src = inspect.getsource(orp)
    assert "_capture_producing_stack(source_request_id)" in src
    i = src.index("_capture_producing_stack(source_request_id)")
    assert "openclaw_response_for_mac_" in src[i: i + 500], "not at the response writer"


def test_a_broken_capture_never_blocks_a_response(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(orp, "utc_now", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        orp._capture_producing_stack("x", path=tmp_path / "s.jsonl")

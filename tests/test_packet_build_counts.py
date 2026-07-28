"""Where do the product facts disappear? Count at three stages.

The product-fact loader is already wired into build_maestro_context_packet and its
output is not reaching the brain. Three possibilities are indistinguishable from
outside: the build raises and a stub is used; fact_selection filters them out; or they
survive the builder and something later drops them. Counts at each stage separate
them in one turn.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import maestro_context_packet as mcp

PRODUCT = {"topic": "product_artifact", "label": "t", "value": "v"}
OTHER = {"topic": "read_model", "label": "t", "value": "v"}


def test_it_counts_all_three_stages(tmp_path: Path) -> None:
    row = mcp._record_packet_build_counts(
        question="q",
        counts={"facts_before_selection": 41, "product_facts_before_selection": 3},
        facts_after_selection=[PRODUCT, OTHER, OTHER],
        packet={"facts": [PRODUCT, OTHER]},
        build_succeeded=True,
        path=tmp_path / "c.jsonl",
    )
    assert row["facts_before_selection"] == 41
    assert row["product_facts_before_selection"] == 3
    assert row["facts_after_selection"] == 3
    assert row["product_facts_after_selection"] == 1
    assert row["facts_in_returned_packet"] == 2
    assert row["product_facts_in_returned_packet"] == 1


def test_a_failed_build_is_recorded_with_its_type(tmp_path: Path) -> None:
    """NON-VACUITY: absence of a row must not be the only signal of failure."""

    row = mcp._record_packet_build_counts(
        question="q", counts={}, packet=None, build_succeeded=False,
        error_type="MaestroContextPacketError", path=tmp_path / "c.jsonl",
    )
    assert row["build_succeeded"] is False
    assert row["error_type"] == "MaestroContextPacketError"


def test_no_fact_text_is_recorded(tmp_path: Path) -> None:
    secret = {"topic": "product_artifact", "label": "SECRET-LABEL", "value": "SECRET-VALUE"}
    row = mcp._record_packet_build_counts(
        question="SENSITIVE-QUESTION-TEXT-THAT-IS-LONG", counts={},
        facts_after_selection=[secret], packet={"facts": [secret]},
        build_succeeded=True, path=tmp_path / "c.jsonl",
    )
    blob = json.dumps(row)
    for forbidden in ("SECRET-LABEL", "SECRET-VALUE"):
        assert forbidden not in blob
    assert len(row["question_sha256"]) == 24


def test_it_is_append_only(tmp_path: Path) -> None:
    log = tmp_path / "c.jsonl"
    mcp._record_packet_build_counts(question="a", counts={}, build_succeeded=True, path=log)
    mcp._record_packet_build_counts(question="b", counts={}, build_succeeded=False, path=log)
    rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 2 and rows[0]["build_succeeded"] != rows[1]["build_succeeded"]


def test_tests_never_write_production_state(monkeypatch) -> None:
    monkeypatch.setenv("OPENCLAW_TEST_MODE", "1")
    before = (mcp.PACKET_BUILD_COUNT_RECEIPTS.read_text(encoding="utf-8")
              if mcp.PACKET_BUILD_COUNT_RECEIPTS.exists() else "")
    row = mcp._record_packet_build_counts(question="q", counts={}, build_succeeded=True)
    after = (mcp.PACKET_BUILD_COUNT_RECEIPTS.read_text(encoding="utf-8")
             if mcp.PACKET_BUILD_COUNT_RECEIPTS.exists() else "")
    assert after == before
    assert row["build_succeeded"] is True


def test_bad_shapes_never_break_a_build(tmp_path: Path) -> None:
    for bad in (None, "text", 42):
        row = mcp._record_packet_build_counts(
            question="q", counts={}, facts_after_selection=bad, packet=bad,
            build_succeeded=True, path=tmp_path / "c.jsonl",
        )
        assert row["facts_after_selection"] == 0


def test_both_call_sites_are_wired() -> None:
    import inspect

    src = inspect.getsource(mcp.build_maestro_context_packet)
    assert src.count("_record_packet_build_counts(") == 2, "success and failure paths both needed"
    assert "build_succeeded=False" in src and "build_succeeded=True" in src

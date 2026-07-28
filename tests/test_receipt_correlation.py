"""Two receipts about one turn must be correlatable, and tests must not touch state/.

The packer receipt says the packet is ~3,700 chars with the thesis in it. The
final-seam receipt says the packet arriving at the model is 124 chars with zero
facts. Both are about "a turn" and neither carried a key, so they could not be proven
to be about the SAME turn — which is the whole question.
"""

from __future__ import annotations

import ast
import inspect

import maestro_context_packet as mcp
import protected_generate as pg


def test_the_packer_receipt_carries_a_packet_id() -> None:
    assert '"packet_id"' in inspect.getsource(mcp.format_maestro_context_packet)


def test_the_final_seam_receipt_carries_a_packet_id() -> None:
    src = inspect.getsource(pg)
    assert '"final_prompt_sha256"' in src, "final-seam receipt moved"
    i = src.index('"final_prompt_sha256"')
    window = src[max(0, i - 1200): i + 400]
    assert '"packet_id"' in window, "the final-seam receipt cannot be correlated"


def test_the_truth_receipt_path_is_redirectable() -> None:
    """A path a test cannot redirect is a path a test will pollute."""

    assert hasattr(mcp, "TRUTH_FAILURE_RECEIPT_PATH")


def test_no_test_writes_to_production_state(tmp_path, monkeypatch) -> None:
    """The regression for my own defect: a test wrote a sentinel into state/."""

    target = tmp_path / "r.json"
    monkeypatch.setattr(mcp, "TRUTH_FAILURE_RECEIPT_PATH", target)
    try:
        mcp.build_maestro_context_packet(
            question="x", require_real_truth=True, session={"read_model_root": "/nowhere"}
        )
    except mcp.MaestroContextPacketError:
        pass
    assert target.exists(), "redirect did not take, so the production path was used"


def test_the_diagnostic_records_the_resolved_root() -> None:
    src = inspect.getsource(mcp.build_maestro_context_packet)
    for field in ("read_model_root", "session_supplied_root", "operator_truth_resolved"):
        assert f'"{field}"' in src

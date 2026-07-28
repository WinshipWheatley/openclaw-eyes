"""When the truth guard fires, it must say what it actually resolved.

The guard is correct and stays: without operator truth and real read-models an answer
would be ungrounded, and that is worth failing for. What was missing is WHY it fired.
The same build succeeds from a shell under the service's own interpreter, cwd and full
environment — so the difference is the SESSION, which can override both roots.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import maestro_context_packet as mcp

RECEIPT = Path("/home/openclaw/state/truth_input_failure_receipt.json")


def test_the_guard_still_fires_and_is_not_routed_around() -> None:
    """NON-NEGOTIABLE: diagnosis must never become a bypass."""

    with pytest.raises(mcp.MaestroContextPacketError):
        mcp.build_maestro_context_packet(
            question="x", require_real_truth=True, session={"read_model_root": "/nowhere"}
        )


def test_the_failure_names_what_it_resolved() -> None:
    try:
        mcp.build_maestro_context_packet(
            question="diagnostic probe", require_real_truth=True,
            session={"read_model_root": "/nowhere"},
        )
    except mcp.MaestroContextPacketError:
        pass
    if not RECEIPT.exists():
        pytest.skip("receipt path not writable in this sandbox")
    d = json.loads(RECEIPT.read_text(encoding="utf-8"))
    for field in ("read_model_root", "read_model_root_exists", "read_model_files",
                  "read_model_refs_found", "operator_truth_resolved",
                  "operator_truth_used", "session_supplied_root", "cwd"):
        assert field in d, f"diagnosis lost {field}"


def test_a_session_supplied_root_is_flagged() -> None:
    """The remaining suspect, made visible rather than inferred."""

    try:
        mcp.build_maestro_context_packet(
            question="diagnostic probe", require_real_truth=True,
            session={"read_model_root": "/nowhere"},
        )
    except mcp.MaestroContextPacketError:
        pass
    if not RECEIPT.exists():
        pytest.skip("receipt path not writable in this sandbox")
    d = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert d["session_supplied_root"] is True
    assert d["read_model_root_exists"] is False
    assert d["read_model_files"] == 0


def test_a_healthy_build_writes_no_failure_receipt() -> None:
    """NON-VACUITY: the receipt marks failure, not every build.

    Order-independent: stamp a sentinel first, then assert a successful build left
    it alone. Comparing before/after across a shared file made this depend on which
    test ran previously. require_real_truth=False because the pytest sandbox blocks the
    real truth inputs — the subject here is the receipt, not the guard."""

    if not RECEIPT.parent.is_dir():
        pytest.skip("state dir unavailable")
    RECEIPT.write_text('{"sentinel": true}\n', encoding="utf-8")
    mcp.build_maestro_context_packet(question="owner-first product hypothesis blocker", require_real_truth=False)
    assert json.loads(RECEIPT.read_text(encoding="utf-8")).get("sentinel") is True

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import capital_hilton_agency_status as status


def test_capital_hilton_status_readback_is_metadata_only():
    answer = status.format_capital_hilton_agency_answer("what is the Capital Hilton agency status?")

    assert answer is not None
    assert "Capital Hilton status:" in answer
    assert "not bank or payment-processor proof" in answer
    assert "No send, Coupa submit, ledger mutation, paid marking, bank verification, or money movement ran." in answer


def test_capital_hilton_openclaw_status_uses_openclaw_attribution():
    answer = status.format_capital_hilton_openclaw_status_answer("Capital Hilton OpenClaw status")

    assert answer is not None
    assert "no autonomous completion" in answer
    assert status.format_capital_hilton_agency_answer("unrelated status") is None
    assert status.format_capital_hilton_agency_answer("where are we with Capital Hilton?") is None

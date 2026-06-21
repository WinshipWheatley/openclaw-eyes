import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chief_validator_brain import check_severity_softening


def test_severity_keyword_replaced_by_pending_is_blocked():
    reason = check_severity_softening(
        source_text="payment failed",
        output_text="payment is pending",
    )

    assert reason is not None
    assert "severity_softening_detected" in reason
    assert "failed" in reason
    assert "pending" in reason


def test_severity_keyword_preserved_in_calm_output_passes():
    reason = check_severity_softening(
        source_text="payment failed",
        output_text="payment failed; blocked at gateway",
    )

    assert reason is None


def test_soft_prefix_before_risk_is_blocked():
    reason = check_severity_softening(
        source_text="security risk",
        output_text="soft risk ahead",
    )

    assert reason is not None
    assert "severity_softening_detected" in reason
    assert "risk" in reason


def test_legitimate_calm_denial_phrase_is_not_blocked():
    reason = check_severity_softening(
        source_text="The system correctly denies sends and money moves.",
        output_text="The system correctly denies sends and money moves.",
    )

    assert reason is None


def test_no_severity_keyword_in_source_passes():
    reason = check_severity_softening(
        source_text="What is the status of the invoice?",
        output_text="The invoice is ready for review.",
    )

    assert reason is None


def test_overdue_dropped_from_output_is_blocked():
    reason = check_severity_softening(
        source_text="invoice is overdue",
        output_text="invoice is in progress",
    )

    assert reason is not None
    assert "overdue" in reason

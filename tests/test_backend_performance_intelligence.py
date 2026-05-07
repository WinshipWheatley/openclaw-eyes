import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend_storage_intelligence import (
    PerformanceReadinessSnapshot,
    StorageRiskFinding,
    evaluate_performance_action_risks,
    performance_readiness_snapshot_as_dict,
)

def sample_performance_readiness_snapshot(
    session_id: str = "session-1",
    action_tier: str = "visual_safe",
    confidence: str = "high",
    manual_override: int = 0,
    session_status: str = "active",
) -> PerformanceReadinessSnapshot:
    return PerformanceReadinessSnapshot(
        performance_session_id=session_id,
        tenant_id="tenant-1",
        setlist_id="setlist-1",
        current_setlist_item_id="item-1",
        current_song_cue_id="cue-1",
        current_section_cue_id="section-1",
        session_status=session_status,
        action_type="cue_trigger",
        action_target="lighting",
        action_tier=action_tier,
        confidence_label=confidence,
        manual_override_active=manual_override,
        operator_approval_ref="receipt-1" if action_tier == "requires_confirmation" else "",
    )

def test_performance_readiness_snapshot_as_dict():
    snapshot = sample_performance_readiness_snapshot()
    data = performance_readiness_snapshot_as_dict(snapshot)
    assert data["performance_session_id"] == "session-1"
    assert data["action_target"] == "lighting"

def test_evaluate_performance_action_risks_finds_low_confidence():
    snapshot = sample_performance_readiness_snapshot(confidence="low")
    findings = evaluate_performance_action_risks(snapshot)
    assert len(findings) == 1
    assert findings[0].finding_kind == "low_confidence_fallback_required"
    assert findings[0].severity == "high"

def test_evaluate_performance_action_risks_finds_requires_confirmation():
    # Missing approval
    snapshot = sample_performance_readiness_snapshot(action_tier="requires_confirmation")
    # override operator_approval_ref from sample default
    snapshot = PerformanceReadinessSnapshot(
        **{**snapshot.__dict__, "operator_approval_ref": ""}
    )
    findings = evaluate_performance_action_risks(snapshot)
    assert any(f.finding_kind == "action_tier_requires_confirmation" for f in findings)

def test_evaluate_performance_action_risks_finds_blocked_high_risk():
    snapshot = sample_performance_readiness_snapshot(action_tier="blocked_high_risk")
    findings = evaluate_performance_action_risks(snapshot)
    assert any(f.finding_kind == "high_risk_action_blocked" for f in findings)

def test_evaluate_performance_action_risks_finds_manual_override():
    snapshot = sample_performance_readiness_snapshot(manual_override=1)
    findings = evaluate_performance_action_risks(snapshot)
    assert any(f.finding_kind == "manual_override_active" for f in findings)
    # Manual override shouldn't require operator approval to exist as a finding (it IS the operator)
    assert not next(f for f in findings if f.finding_kind == "manual_override_active").requires_operator_approval

def test_evaluate_performance_action_risks_finds_inactive_session():
    snapshot = sample_performance_readiness_snapshot(session_status="paused")
    findings = evaluate_performance_action_risks(snapshot)
    assert any(f.finding_kind == "performance_session_not_active" for f in findings)

def test_evaluate_performance_action_risks_preserves_component_findings():
    component_finding = StorageRiskFinding(
        finding_id="comp-1:cap-1:degraded",
        finding_kind="degraded_component",
        severity="medium",
        message="component is degraded",
        requires_operator_approval=False,
    )
    snapshot = PerformanceReadinessSnapshot(
        **{**sample_performance_readiness_snapshot().__dict__, "component_health_findings": (component_finding,)}
    )
    findings = evaluate_performance_action_risks(snapshot)
    assert component_finding in findings

def test_performance_readiness_snapshot_validation():
    with pytest.raises(ValueError):
        evaluate_performance_action_risks(sample_performance_readiness_snapshot(action_tier="unknown"))
    with pytest.raises(ValueError):
        evaluate_performance_action_risks(sample_performance_readiness_snapshot(manual_override=2))

from __future__ import annotations

import json
from pathlib import Path

import external_brain_router as router
from protected_generate import HIGH, LIGHT, MAX, MED, PUBLIC, _metadata_for_tier


ROOT = Path(__file__).resolve().parents[1]


def test_difficulty_router_returns_lane_ids_only() -> None:
    assert router.select_difficulty_lane(task_type="quick friendly summary") == "easy_lane"
    assert router.select_difficulty_lane(task_type="code implementation with tests") == "mid_lane"
    assert router.select_difficulty_lane(task_type="architecture policy synthesis") == "hard_lane"
    assert router.select_difficulty_lane(task_type="routine operator question") == "mid_lane"


def test_high_risk_or_large_context_forces_hard_lane() -> None:
    assert router.select_difficulty_lane(task_type="summary", risk_tier="high") == "hard_lane"
    assert router.select_difficulty_lane(task_type="summary", context_size="large") == "hard_lane"


def test_router_source_contains_no_concrete_model_ids() -> None:
    source = (ROOT / "external_brain_router.py").read_text(encoding="utf-8").lower()
    assert "gpt-5.6" not in source
    assert "qwen3:" not in source


def test_bindings_are_separate_and_complete() -> None:
    bindings = json.loads((ROOT / "model_lane_bindings.json").read_text(encoding="utf-8"))

    assert bindings == {
        "schema_version": "model_lane_bindings_v1",
        "lanes": {
            "easy_lane": {
                "transport": "codex_app_server",
                "model": "gpt-5.6-luna",
                "default_effort": "low",
            },
            "mid_lane": {
                "transport": "codex_app_server",
                "model": "gpt-5.6-terra",
                "default_effort": "medium",
            },
            "hard_lane": {
                "transport": "codex_app_server",
                "model": "gpt-5.6-sol",
                "default_effort": "high",
            },
            "local_safe_lane": {
                "transport": "ollama",
                "model": "qwen3:8b-q4_K_M",
                "default_effort": "medium",
            },
        },
    }


def test_route_selects_binding_default_effort_without_exposing_model() -> None:
    easy = router.select_route(task_type="quick friendly summary")
    mid = router.select_route(task_type="code implementation with tests")
    hard = router.select_route(task_type="architecture policy synthesis")

    assert (easy.lane_id, easy.effort_level, easy.effort_reason) == (
        "easy_lane",
        "low",
        "binding_default",
    )
    assert (mid.lane_id, mid.effort_level) == ("mid_lane", "medium")
    assert (hard.lane_id, hard.effort_level) == ("hard_lane", "high")
    assert not hasattr(easy, "model")


def test_effort_override_is_independent_from_lane_selection() -> None:
    easy_xhigh = router.select_route(
        task_type="quick summary",
        effort_override="xhigh",
    )
    hard_low = router.select_route(
        task_type="architecture policy synthesis",
        effort_override="low",
    )

    assert (easy_xhigh.lane_id, easy_xhigh.effort_level) == ("easy_lane", "xhigh")
    assert (hard_low.lane_id, hard_low.effort_level) == ("hard_lane", "low")
    assert easy_xhigh.effort_reason == "explicit_override"
    assert hard_low.effort_reason == "explicit_override"


def test_critical_or_huge_task_signal_selects_xhigh_effort() -> None:
    critical = router.select_route(task_type="routine summary", risk_tier="critical")
    huge = router.select_route(task_type="routine summary", context_size="huge")

    assert critical.effort_level == "xhigh"
    assert critical.effort_reason == "critical_risk"
    assert huge.effort_level == "xhigh"
    assert huge.effort_reason == "huge_context"


def test_external_route_reuses_model_policy_after_privacy_packaging(monkeypatch) -> None:
    captured: dict = {}

    def fake_select(request):
        captured.update(request)
        return {
            "selected_model_class": router.model_router_policy.STRONG_EXTERNAL_ROLE_MODEL,
            "selection_reason": "external role model is policy eligible",
            "blocked_reasons": [],
        }

    monkeypatch.setattr(router.model_router_policy, "select_model_class", fake_select)
    decision = router.route_external_brain_request(
        raw_operator_prompt="Verbatim private operator words must never enter the route receipt.",
        task_type="code implementation with tests",
        chain_lane="LM2_ROLE_RESPONSE",
        risk_tier="medium",
        context_size="small",
        privacy_metadata={
            "classification": "sanitized",
            "original_pii_tier": "HIGH",
            "cloud_allowed": True,
            "local_required": False,
            "tokenization_applied": True,
            "package_minimized": True,
            "raw_values_included": False,
            "secrets_present": False,
        },
        activation_enabled=False,
    )

    assert captured["tokenization_applied"] is True
    assert captured["package_minimized"] is True
    assert captured["raw_values_included"] is False
    assert captured["external_lm_allowed"] is True
    assert "Verbatim private operator words" not in json.dumps(captured)
    assert decision.candidate_lane_id == "mid_lane"
    assert decision.effective_lane_id == "local_safe_lane"
    assert decision.fallback_reason == "external_router_default_off"


def test_external_route_activates_candidate_only_when_policy_and_gate_allow(monkeypatch) -> None:
    monkeypatch.setattr(
        router.model_router_policy,
        "select_model_class",
        lambda _request: {
            "selected_model_class": router.model_router_policy.FAST_EXTERNAL_INTENT_MODEL,
            "selection_reason": "eligible",
            "blocked_reasons": [],
        },
    )
    decision = router.route_external_brain_request(
        raw_operator_prompt="Public quick task",
        task_type="quick summary",
        chain_lane="LM1_INTENT_PROPOSAL",
        privacy_metadata={
            "classification": "public",
            "original_pii_tier": "PUBLIC",
            "cloud_allowed": True,
            "local_required": False,
            "tokenization_applied": False,
            "package_minimized": True,
            "raw_values_included": False,
            "secrets_present": False,
        },
        activation_enabled=True,
    )

    assert decision.candidate_lane_id == "easy_lane"
    assert decision.effective_lane_id == "easy_lane"
    assert decision.fallback_reason == ""


def test_policy_local_or_unsafe_decision_fails_to_local_lane(monkeypatch) -> None:
    monkeypatch.setattr(
        router.model_router_policy,
        "select_model_class",
        lambda _request: {
            "selected_model_class": router.model_router_policy.LOCAL_FALLBACK_MODEL,
            "selection_reason": "private package",
            "blocked_reasons": ["PRIVATE"],
        },
    )
    decision = router.route_external_brain_request(
        raw_operator_prompt="contains protected material",
        task_type="architecture review",
        privacy_metadata={
            "classification": "private",
            "original_pii_tier": "MAX",
            "cloud_allowed": False,
            "local_required": True,
            "tokenization_applied": False,
            "package_minimized": False,
            "raw_values_included": True,
            "secrets_present": False,
        },
        activation_enabled=True,
    )

    assert decision.candidate_lane_id == "local_safe_lane"
    assert decision.effective_lane_id == "local_safe_lane"
    assert decision.fallback_reason == "model_policy_selected_local"


def test_safe_route_receipt_contains_no_prompt_or_concrete_model() -> None:
    decision = router.ExternalRouteDecision(
        request_hash="sha256:test",
        candidate_lane_id="hard_lane",
        effective_lane_id="local_safe_lane",
        effort_level="high",
        effort_reason="binding_default",
        policy_model_class="STRONG_EXTERNAL_ROLE_MODEL",
        policy_reason="eligible",
        pii_verdict="sanitized",
        difficulty_evidence=("risk=high", "context=large"),
        fallback_reason="external_router_default_off",
        activation_enabled=False,
    )

    receipt = router.build_safe_route_receipt(decision)

    assert receipt["request_hash"] == "sha256:test"
    assert receipt["selected_effort"] == "high"
    assert receipt["effort_reason"] == "binding_default"
    encoded = json.dumps(receipt)
    assert "raw_operator_prompt" not in encoded
    assert "gpt-" not in encoded.lower()


def test_binding_loader_rejects_missing_required_lane(tmp_path: Path) -> None:
    path = tmp_path / "bindings.json"
    path.write_text('{"schema_version":"model_lane_bindings_v1","lanes":{}}', encoding="utf-8")

    try:
        router.load_model_lane_bindings(path)
    except router.ModelLaneBindingError as exc:
        assert "missing required lanes" in str(exc)
    else:
        raise AssertionError("incomplete bindings must fail closed")


def test_public_metadata_is_external_eligible_without_tokenization() -> None:
    metadata = _metadata_for_tier(PUBLIC, 0, package_minimized=True)
    assert metadata["cloud_allowed"] is True
    assert metadata["local_required"] is False
    assert metadata["tokenization_applied"] is False


def test_light_through_high_require_tokenization_and_minimization() -> None:
    for tier in (LIGHT, MED, HIGH):
        eligible = _metadata_for_tier(tier, 1, package_minimized=True)
        assert eligible["cloud_allowed"] is True
        assert eligible["local_required"] is False

        not_tokenized = _metadata_for_tier(tier, 0, package_minimized=True)
        assert not_tokenized["cloud_allowed"] is False
        assert not_tokenized["local_required"] is True

        not_minimized = _metadata_for_tier(tier, 1, package_minimized=False)
        assert not_minimized["cloud_allowed"] is False
        assert not_minimized["local_required"] is True


def test_legal_metadata_requires_explicit_full_tokenization_proof() -> None:
    unproven = _metadata_for_tier(
        MAX,
        4,
        package_minimized=True,
        legal_fully_tokenized=False,
    )
    proven = _metadata_for_tier(
        MAX,
        0,
        package_minimized=True,
        legal_fully_tokenized=True,
    )
    assert unproven["cloud_allowed"] is False
    assert unproven["local_required"] is True
    assert proven["cloud_allowed"] is True
    assert proven["local_required"] is False


def test_raw_unresolved_or_secret_metadata_always_stays_local() -> None:
    for flags in (
        {"raw_values_included": True},
        {"unresolved_sensitive_values": True},
        {"secrets_present": True},
    ):
        metadata = _metadata_for_tier(HIGH, 3, package_minimized=True, **flags)
        assert metadata["cloud_allowed"] is False
        assert metadata["local_required"] is True

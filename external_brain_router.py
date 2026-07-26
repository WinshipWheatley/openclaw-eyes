"""Model-agnostic policy router for external brain requests."""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from model_work_package_router import CODE_TASK_TERMS, DEEP_REASONING_TERMS, FAST_TASK_TERMS
import model_router_policy


EASY_LANE = "easy_lane"
MID_LANE = "mid_lane"
HARD_LANE = "hard_lane"
LOCAL_SAFE_LANE = "local_safe_lane"
REQUIRED_LANES = frozenset({EASY_LANE, MID_LANE, HARD_LANE, LOCAL_SAFE_LANE})
REQUIRED_AGENTS = frozenset({"maestro", "chief", "cassandra", "niles", "guardian", "hermes"})
VALID_EFFORT_LEVELS = frozenset({"low", "medium", "high", "xhigh"})
DEFAULT_BINDINGS_PATH = Path(__file__).with_name("model_lane_bindings.json")

_MID_PROFILE_TERMS = ("surgical", "standard")
_HARD_PROFILE_TERMS = ("architect", "deep reasoning", "large context")


class ModelLaneBindingError(ValueError):
    """Raised when concrete lane bindings are incomplete or malformed."""


@dataclass(frozen=True)
class RouteSelection:
    lane_id: str
    effort_level: str
    effort_reason: str


@dataclass(frozen=True)
class ExternalRouteDecision:
    request_hash: str
    nominal_lane_id: str
    candidate_lane_id: str
    effective_lane_id: str
    effort_level: str
    effort_reason: str
    policy_model_class: str
    policy_reason: str
    pii_verdict: str
    difficulty_evidence: tuple[str, ...]
    fallback_reason: str
    activation_enabled: bool
    graduation_headroom_applied: bool
    agent_id: str = ""
    agent_binding_status: str = "unbound"
    agent_allowed_lanes: tuple[str, ...] = ()
    comparison_lane_requested: str = ""
    comparison_trial: bool = False


def _normalized(value: object) -> str:
    return " ".join(str(value or "").lower().replace("_", " ").replace("-", " ").split())


def _request_hash(raw_operator_prompt: str) -> str:
    digest = hashlib.sha256(str(raw_operator_prompt or "").encode("utf-8")).hexdigest()
    return f"sha256:{digest[:16]}"


def _policy_sensitivity(metadata: Mapping[str, Any]) -> str:
    tier = str(metadata.get("original_pii_tier") or "PUBLIC").upper()
    return {
        "PUBLIC": "low",
        "LIGHT": "low",
        "MED": "medium",
        "HIGH": "high",
        "MAX": "protected",
    }.get(tier, "protected")


def select_difficulty_lane(
    *,
    task_type: str,
    risk_tier: str = "low",
    context_size: str = "small",
) -> str:
    """Return a difficulty lane without resolving a provider or concrete model."""

    task = _normalized(task_type)
    risk = _normalized(risk_tier)
    context = _normalized(context_size)
    if risk in {"high", "critical"} or context in {"large", "huge"}:
        return HARD_LANE
    if any(term in task for term in (*DEEP_REASONING_TERMS, *_HARD_PROFILE_TERMS)):
        return HARD_LANE
    if any(term in task for term in (*CODE_TASK_TERMS, *_MID_PROFILE_TERMS)):
        return MID_LANE
    if any(term in task for term in ("easy", *FAST_TASK_TERMS)):
        return EASY_LANE
    return MID_LANE


def load_model_lane_bindings(path: str | Path = DEFAULT_BINDINGS_PATH) -> dict[str, Any]:
    """Load concrete bindings from config and fail closed on incomplete data."""

    binding_path = Path(path)
    try:
        payload = json.loads(binding_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelLaneBindingError(f"unreadable lane bindings: {binding_path}") from exc
    if payload.get("schema_version") != "model_lane_bindings_v1":
        raise ModelLaneBindingError("unsupported lane binding schema")
    lanes = payload.get("lanes")
    if not isinstance(lanes, Mapping):
        raise ModelLaneBindingError("lane bindings must contain a lanes object")
    missing = sorted(REQUIRED_LANES.difference(lanes))
    if missing:
        raise ModelLaneBindingError(f"missing required lanes: {', '.join(missing)}")
    for lane in REQUIRED_LANES:
        binding = lanes.get(lane)
        if not isinstance(binding, Mapping):
            raise ModelLaneBindingError(f"invalid binding for lane: {lane}")
        if not str(binding.get("transport") or "").strip() or not str(binding.get("model") or "").strip():
            raise ModelLaneBindingError(f"incomplete binding for lane: {lane}")
        if str(binding.get("default_effort") or "") not in VALID_EFFORT_LEVELS:
            raise ModelLaneBindingError(f"invalid default effort for lane: {lane}")
    agent_bindings = payload.get("agent_bindings")
    if agent_bindings is not None:
        if not isinstance(agent_bindings, Mapping):
            raise ModelLaneBindingError("agent_bindings must be an object")
        missing_agents = sorted(REQUIRED_AGENTS.difference(agent_bindings))
        if missing_agents:
            raise ModelLaneBindingError(
                f"missing required agent bindings: {', '.join(missing_agents)}"
            )
        for agent_id in REQUIRED_AGENTS:
            binding = agent_bindings.get(agent_id)
            allowed = binding.get("allowed_lanes") if isinstance(binding, Mapping) else None
            if not isinstance(allowed, list) or not allowed:
                raise ModelLaneBindingError(f"invalid agent binding: {agent_id}")
            if any(str(lane) not in REQUIRED_LANES - {LOCAL_SAFE_LANE} for lane in allowed):
                raise ModelLaneBindingError(f"unsupported lane in agent binding: {agent_id}")
    return dict(payload)


def select_route(
    *,
    task_type: str,
    risk_tier: str = "low",
    context_size: str = "small",
    effort_override: str | None = None,
    bindings_path: str | Path = DEFAULT_BINDINGS_PATH,
) -> RouteSelection:
    """Select independent lane and effort dimensions without resolving a model."""

    lane_id = select_difficulty_lane(
        task_type=task_type,
        risk_tier=risk_tier,
        context_size=context_size,
    )
    bindings = load_model_lane_bindings(bindings_path)
    effort_level = str(bindings["lanes"][lane_id]["default_effort"])
    effort_reason = "binding_default"

    if effort_override is not None:
        normalized_override = _normalized(effort_override).replace(" ", "")
        if normalized_override not in VALID_EFFORT_LEVELS:
            raise ValueError(f"unsupported effort override: {effort_override}")
        effort_level = normalized_override
        effort_reason = "explicit_override"
    elif _normalized(risk_tier) == "critical":
        effort_level = "xhigh"
        effort_reason = "critical_risk"
    elif _normalized(context_size) == "huge":
        effort_level = "xhigh"
        effort_reason = "huge_context"

    return RouteSelection(
        lane_id=lane_id,
        effort_level=effort_level,
        effort_reason=effort_reason,
    )


def route_external_brain_request(
    *,
    raw_operator_prompt: str,
    task_type: str,
    privacy_metadata: Mapping[str, Any],
    chain_lane: str = "LM2_ROLE_RESPONSE",
    role: str = "advisory_response",
    risk_tier: str = "low",
    context_size: str = "small",
    effort_override: str | None = None,
    activation_enabled: bool = False,
    comparison_lane_id: str | None = None,
    bindings_path: str | Path = DEFAULT_BINDINGS_PATH,
) -> ExternalRouteDecision:
    """Apply the existing model-class policy, then select a lane and effort.

    The policy request contains only post-packaging metadata and a request hash.
    Raw operator text is never copied into a routing decision or receipt.
    """

    request_hash = _request_hash(raw_operator_prompt)
    difficulty_route = select_route(
        task_type=task_type,
        risk_tier=risk_tier,
        context_size=context_size,
        effort_override=effort_override,
        bindings_path=bindings_path,
    )
    nominal_lane_id = difficulty_route.lane_id
    bindings_payload = load_model_lane_bindings(bindings_path)
    agent_id = _normalized(role).replace(" ", "_")
    raw_agent_binding = (bindings_payload.get("agent_bindings") or {}).get(agent_id)
    agent_allowed_lanes = tuple(
        str(lane)
        for lane in (
            raw_agent_binding.get("allowed_lanes", ())
            if isinstance(raw_agent_binding, Mapping)
            else ()
        )
        if str(lane)
    )
    agent_binding_status = "bound" if agent_allowed_lanes else "unbound"
    comparison_lane_requested = str(comparison_lane_id or "").strip()
    comparison_trial = bool(
        comparison_lane_requested
        and str(chain_lane or "").strip().upper() == "MODEL_GRADUATION_COMPARISON"
        and comparison_lane_requested in REQUIRED_LANES - {LOCAL_SAFE_LANE}
        and comparison_lane_requested in agent_allowed_lanes
    )
    work_lane_id = {
        EASY_LANE: MID_LANE,
        MID_LANE: HARD_LANE,
        HARD_LANE: HARD_LANE,
    }.get(nominal_lane_id, nominal_lane_id)
    effort_level = difficulty_route.effort_level
    effort_reason = difficulty_route.effort_reason
    if work_lane_id != nominal_lane_id and effort_reason == "binding_default":
        bindings = load_model_lane_bindings(bindings_path)
        effort_level = str(bindings["lanes"][work_lane_id]["default_effort"])
        effort_reason = "graduated_binding_default"
    if comparison_trial:
        work_lane_id = comparison_lane_requested
        if effort_override is None:
            effort_level = str(bindings_payload["lanes"][work_lane_id]["default_effort"])
            effort_reason = "comparison_lane_binding_default"

    policy_chain_lane = "LM2_ROLE_RESPONSE" if comparison_trial else chain_lane
    policy_request = {
        "request_id": request_hash,
        "chain_lane": policy_chain_lane,
        "task_type": _normalized(task_type),
        "role": _normalized(role),
        "risk_level": _normalized(risk_tier) or "low",
        "sensitivity_level": _policy_sensitivity(privacy_metadata),
        "context_size": _normalized(context_size) or "small",
        "requires_structured_output": True,
        "creative_posture_allowed": False,
        "tokenization_applied": bool(privacy_metadata.get("tokenization_applied")),
        "raw_values_included": bool(privacy_metadata.get("raw_values_included")),
        "requested_live_authority": False,
        "external_lm_allowed": bool(privacy_metadata.get("cloud_allowed")),
        "local_lm_required": bool(privacy_metadata.get("local_required")),
        "offline_mode": False,
        "strict_private_mode_active": False,
        "credentials_or_secrets_present": bool(privacy_metadata.get("secrets_present")),
        "package_minimized": bool(privacy_metadata.get("package_minimized")),
        "baseline_external_passed": True,
        "downgrade_testing_requested": False,
    }
    try:
        policy_decision = model_router_policy.select_model_class(policy_request)
    except Exception as exc:
        policy_decision = {
            "selected_model_class": model_router_policy.NO_SAFE_MODEL,
            "selection_reason": f"model_policy_error:{type(exc).__name__}",
            "blocked_reasons": ["MODEL_POLICY_ERROR"],
        }

    policy_model_class = str(policy_decision.get("selected_model_class") or model_router_policy.NO_SAFE_MODEL)
    policy_reason = str(policy_decision.get("selection_reason") or "")
    external_policy_classes = {
        model_router_policy.FAST_EXTERNAL_INTENT_MODEL,
        model_router_policy.STRONG_EXTERNAL_ROLE_MODEL,
        model_router_policy.FAST_STRUCTURED_INTENT_SMALL,
        model_router_policy.STRONG_STRUCTURED_ROLE_REASONER,
        model_router_policy.CONSERVATIVE_SENSITIVE_STRUCTURED,
    }
    policy_allows_external = bool(
        policy_model_class in external_policy_classes
        and privacy_metadata.get("cloud_allowed") is True
        and privacy_metadata.get("local_required") is not True
    )
    if comparison_lane_requested and not comparison_trial:
        policy_allows_external = False
        policy_reason = "comparison_lane_not_authorized"
    candidate_lane_id = work_lane_id if policy_allows_external else LOCAL_SAFE_LANE
    if (
        policy_allows_external
        and agent_binding_status == "bound"
        and candidate_lane_id not in agent_allowed_lanes
    ):
        policy_allows_external = False
        candidate_lane_id = LOCAL_SAFE_LANE
        policy_reason = "agent_lane_not_allowed"
    if not policy_allows_external:
        effective_lane_id = LOCAL_SAFE_LANE
        fallback_reason = (
            "comparison_lane_not_authorized"
            if comparison_lane_requested and not comparison_trial
            else "model_policy_selected_local"
        )
    elif not activation_enabled:
        effective_lane_id = LOCAL_SAFE_LANE
        fallback_reason = "external_router_default_off"
    else:
        effective_lane_id = candidate_lane_id
        fallback_reason = ""

    return ExternalRouteDecision(
        request_hash=request_hash,
        nominal_lane_id=nominal_lane_id,
        candidate_lane_id=candidate_lane_id,
        effective_lane_id=effective_lane_id,
        effort_level=effort_level,
        effort_reason=effort_reason,
        policy_model_class=policy_model_class,
        policy_reason=policy_reason,
        pii_verdict=str(privacy_metadata.get("classification") or "unknown"),
        difficulty_evidence=(
            f"nominal_lane={nominal_lane_id}",
            f"work_lane={work_lane_id}",
            f"risk={_normalized(risk_tier) or 'low'}",
            f"context={_normalized(context_size) or 'small'}",
        ),
        fallback_reason=fallback_reason,
        activation_enabled=bool(activation_enabled),
        graduation_headroom_applied=(
            not comparison_trial and work_lane_id != nominal_lane_id
        ),
        agent_id=agent_id,
        agent_binding_status=agent_binding_status,
        agent_allowed_lanes=agent_allowed_lanes,
        comparison_lane_requested=comparison_lane_requested,
        comparison_trial=comparison_trial,
    )


def build_safe_route_receipt(decision: ExternalRouteDecision) -> dict[str, Any]:
    """Return prompt-free routing metadata suitable for durable receipts."""

    return {
        "schema_version": "external_brain_route_receipt_v1",
        "request_hash": decision.request_hash,
        "nominal_lane_id": decision.nominal_lane_id,
        "candidate_lane_id": decision.candidate_lane_id,
        "effective_lane_id": decision.effective_lane_id,
        "selected_effort": decision.effort_level,
        "effort_reason": decision.effort_reason,
        "policy_model_class": decision.policy_model_class,
        "policy_reason": decision.policy_reason,
        "pii_verdict": decision.pii_verdict,
        "difficulty_evidence": list(decision.difficulty_evidence),
        "fallback_reason": decision.fallback_reason,
        "activation_enabled": decision.activation_enabled,
        "graduation_headroom_applied": decision.graduation_headroom_applied,
        "agent_id": decision.agent_id,
        "agent_binding_status": decision.agent_binding_status,
        "agent_allowed_lanes": list(decision.agent_allowed_lanes),
        "comparison_lane_requested": decision.comparison_lane_requested,
        "comparison_trial": decision.comparison_trial,
    }

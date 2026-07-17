"""Model-agnostic policy router for external brain requests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from model_work_package_router import CODE_TASK_TERMS, DEEP_REASONING_TERMS, FAST_TASK_TERMS


EASY_LANE = "easy_lane"
MID_LANE = "mid_lane"
HARD_LANE = "hard_lane"
LOCAL_SAFE_LANE = "local_safe_lane"
REQUIRED_LANES = frozenset({EASY_LANE, MID_LANE, HARD_LANE, LOCAL_SAFE_LANE})
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


def _normalized(value: object) -> str:
    return " ".join(str(value or "").lower().replace("_", " ").replace("-", " ").split())


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

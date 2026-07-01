"""Capability/availability router primitive for local-first build decisions.

This module is deliberately side-effect light: it does not launch a build, call
cloud tools, or unload models. It centralizes the policy decision and records the
reason, so callers can route, defer, or preempt without silently stalling.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polish_loop.builder_output_validator import validate
from polish_loop.gpu_arbiter import GPUArbiter


DEFAULT_LOCAL_MODEL = "chief-fast:latest"


def _parse_iso(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _active_gpu_signal(lease_db_path: str | Path | None, now: datetime | None = None) -> dict[str, Any]:
    if lease_db_path is None:
        return {"gpu": "unknown", "gpu_reason": "lease_db_not_configured"}
    now = (now or datetime.now(UTC)).astimezone(UTC)
    try:
        lease = GPUArbiter(lease_db_path).current()
    except Exception as exc:
        return {"gpu": "unknown", "gpu_reason": f"lease_probe_error:{exc}"}
    if not lease:
        return {"gpu": "idle"}
    expires_at = _parse_iso(lease.get("expires_at"))
    if expires_at is not None and expires_at <= now:
        return {
            "gpu": "expired_lease",
            "gpu_holder_type": lease.get("holder_type"),
            "gpu_holder_id": lease.get("holder_id"),
        }
    return {
        "gpu": f"{lease.get('holder_type')}_active",
        "gpu_holder_type": lease.get("holder_type"),
        "gpu_holder_id": lease.get("holder_id"),
        "gpu_expires_at": lease.get("expires_at"),
    }


def _classify_previous_output(previous_runner_output: str | Path | None) -> str:
    if previous_runner_output is None:
        return "none"
    ok, reason = validate(previous_runner_output)
    return "ok" if ok else reason


def _cloud_signal(
    *,
    requested: bool,
    allowed: bool,
    headroom: dict[str, Any] | None,
    previous_runner_reason: str,
) -> str:
    if not requested:
        return "not_requested"
    if not allowed:
        return "blocked_not_explicitly_allowed"
    if previous_runner_reason == "quota_message":
        return "quota_unavailable"
    if not headroom:
        return "headroom_unknown_fail_closed"
    if not bool(headroom.get("codex", {}).get("available", False)):
        return "quota_unavailable"
    return "available"


def route_build_capability(
    task_text: str,
    *,
    lease_db_path: str | Path | None,
    local_model: tuple[str | None, str] | None = None,
    cloud_requested: bool = False,
    cloud_allowed: bool = False,
    cloud_headroom: dict[str, Any] | None = None,
    previous_runner_output: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return an explicit routing decision for a polish-loop build.

    Policy:
    - local-first when a local model is available and the GPU is not held by an
      interactive agent;
    - defer while an interactive lease is active;
    - never route to cloud unless the task is explicitly cloud-safe and headroom
      is known available;
    - quota/rate-limit output routes to local if local can run, otherwise defers
      honestly.
    """
    del task_text  # Reserved for later skill matching / decomposer integration.

    selected_model, local_reason = local_model or (DEFAULT_LOCAL_MODEL, "default_local_builder")
    output_reason = _classify_previous_output(previous_runner_output)
    gpu = _active_gpu_signal(lease_db_path, now=now)
    cloud = _cloud_signal(
        requested=cloud_requested,
        allowed=cloud_allowed,
        headroom=cloud_headroom,
        previous_runner_reason=output_reason,
    )
    signals: dict[str, Any] = {
        **gpu,
        "local_model_reason": local_reason,
        "previous_runner_output": output_reason,
        "cloud": cloud,
    }

    if gpu.get("gpu") == "interactive_active":
        return {
            "status": "defer",
            "decision_reason": "interactive_gpu_lease_active",
            "defer_until": "interactive_idle",
            "executor": None,
            "runner": None,
            "model": None,
            "signals": signals,
            "explanation": "Interactive agent holds the local GPU lease; builder waits until the session is idle.",
        }

    if selected_model:
        reason = (
            "cloud_quota_message_local_fallback"
            if output_reason == "quota_message" and cloud_requested
            else "local_builder_available"
        )
        return {
            "status": "route",
            "decision_reason": reason,
            "executor": "local_builder",
            "runner": "ollama",
            "model": selected_model,
            "signals": signals,
            "explanation": "Route to the local builder; local is available and avoids credit/provider risk.",
        }

    if cloud == "available":
        return {
            "status": "route",
            "decision_reason": "cloud_available_no_local_model",
            "executor": "cloud_builder",
            "runner": "codex",
            "model": "default",
            "signals": signals,
            "explanation": "Local model is unavailable; cloud is explicitly allowed and headroom is available.",
        }

    return {
        "status": "defer",
        "decision_reason": "no_available_capability",
        "defer_until": "capability_returns",
        "executor": None,
        "runner": None,
        "model": None,
        "signals": signals,
        "explanation": "No local model can run and cloud is unavailable or not safely allowed; defer honestly.",
    }


__all__ = ["route_build_capability", "DEFAULT_LOCAL_MODEL"]

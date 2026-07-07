"""Adaptive local model-call retry layer for listener-facing agents."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from chief_llm import ollama_call, resolve_local_model, select_frontdoor_model
from frontdoor_resource_probe import probe_frontdoor_resources


RouteLogger = Callable[..., None]
OllamaCallFn = Callable[..., str]
ResolveModelFn = Callable[..., tuple[str, str]]
SelectModelFn = Callable[..., tuple[str | None, str]]
ResourceProbeFn = Callable[[], Any]


def _call_ollama_once(
    ollama_call_fn: OllamaCallFn,
    prompt: str,
    *,
    timeout: int,
    model: str,
    task_class: str,
) -> str:
    kwargs = {
        "timeout": timeout,
        "model": model,
        "task_class": task_class,
        "attempts": 1,
    }
    try:
        signature = inspect.signature(ollama_call_fn)
    except (TypeError, ValueError):
        call_kwargs = kwargs
    else:
        parameters = signature.parameters
        has_kwargs = any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values())
        if has_kwargs:
            call_kwargs = kwargs
        else:
            allowed = {
                name
                for name, parameter in parameters.items()
                if parameter.kind
                in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
            }
            call_kwargs = {key: value for key, value in kwargs.items() if key in allowed}
    return str(ollama_call_fn(prompt, **call_kwargs) or "")


def _snapshot_kwargs(snapshot: Any) -> dict[str, Any]:
    resident = {}
    resident_fn = getattr(snapshot, "resident_vram_by_model_gb", None)
    if callable(resident_fn):
        try:
            resident = dict(resident_fn())
        except Exception:
            resident = {}
    return {
        "available_vram_gb": getattr(snapshot, "available_vram_gb", None),
        "available_ram_gb": getattr(snapshot, "available_ram_gb", None),
        "resident_vram_by_model_gb": resident,
        "system_load_1m": getattr(snapshot, "system_load_1m", None),
        "cpu_count": getattr(snapshot, "cpu_count", None),
    }


def _choose_retry_model(
    *,
    primary_model: str,
    select_model_fn: SelectModelFn,
    resource_probe_fn: ResourceProbeFn,
) -> tuple[str | None, str]:
    try:
        snapshot = resource_probe_fn()
        selected, reason = select_model_fn(**_snapshot_kwargs(snapshot))
    except Exception as exc:
        return None, f"adaptive_retry_probe_error:{type(exc).__name__}"
    selected = str(selected or "").strip()
    if not selected:
        return None, reason or "adaptive_retry_no_model"
    if selected == primary_model:
        return selected, reason or "adaptive_retry_same_model"
    return selected, reason or "adaptive_retry_downshift"


def adaptive_model_call(
    prompt: str,
    *,
    task_class: str,
    timeout: int,
    primary_model: str | None = None,
    primary_lane: str | None = None,
    lane: str | None = None,
    validation_outcome: str | None = None,
    ollama_call_fn: OllamaCallFn | None = None,
    resolve_model_fn: ResolveModelFn | None = None,
    select_model_fn: SelectModelFn | None = None,
    resource_probe_fn: ResourceProbeFn | None = None,
    route_logger: RouteLogger | None = None,
    retry: bool = True,
) -> str:
    """Call a local model once, then one adaptive retry on empty output.

    The first attempt preserves the caller's resolved task-class model and
    timeout. The retry reuses the front-door resource-aware allowlist so a cold
    or contended large model can downshift to a small proven local model before
    the caller emits its honest degraded fallback.
    """

    ollama_call_fn = ollama_call_fn or ollama_call
    resolve_model_fn = resolve_model_fn or resolve_local_model
    select_model_fn = select_model_fn or select_frontdoor_model
    resource_probe_fn = resource_probe_fn or probe_frontdoor_resources

    if primary_model is None or primary_lane is None:
        primary_model, primary_lane = resolve_model_fn(prompt, lane=lane, task_class=task_class)
    if route_logger is not None:
        route_logger(
            task_class=task_class,
            preferred_lane=primary_lane,
            chosen_lane=primary_lane,
            reason=f"adaptive primary route via shared local router for {task_class}",
            escalation=False,
            validation_outcome=validation_outcome,
            model=primary_model,
        )
    result = _call_ollama_once(
        ollama_call_fn,
        prompt,
        timeout=timeout,
        model=primary_model,
        task_class=task_class,
    )
    if result or not retry:
        return result

    retry_model, retry_reason = _choose_retry_model(
        primary_model=primary_model,
        select_model_fn=select_model_fn,
        resource_probe_fn=resource_probe_fn,
    )
    if not retry_model:
        return ""
    if route_logger is not None:
        route_logger(
            task_class=task_class,
            preferred_lane=primary_lane,
            chosen_lane="adaptive_retry",
            reason=f"adaptive retry after empty response: {retry_reason}",
            escalation=True,
            validation_outcome="empty_response",
            model=retry_model,
        )
    return _call_ollama_once(
        ollama_call_fn,
        prompt,
        timeout=timeout,
        model=retry_model,
        task_class=task_class,
    )

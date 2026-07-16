"""Adaptive local model-call retry layer for listener-facing agents."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import chief_llm
from frontdoor_resource_probe import probe_frontdoor_resources
from model_slot_lease import (
    DEFAULT_MODEL_SLOT_ACK_THRESHOLD_SECONDS,
    DEFAULT_MODEL_SLOT_MAX_WAIT_SECONDS,
    ModelSlotTimeoutError,
    acquire_model_slot,
)


resolve_local_model = chief_llm.resolve_local_model
select_frontdoor_model = chief_llm.select_frontdoor_model

RouteLogger = Callable[..., None]
OllamaCallFn = Callable[..., str]
ResolveModelFn = Callable[..., tuple[str, str]]
SelectModelFn = Callable[..., tuple[str | None, str]]
ResourceProbeFn = Callable[[], Any]
ModelSlotWaitingFn = Callable[[float], None]


def _call_ollama_once(
    ollama_call_fn: OllamaCallFn,
    prompt: str,
    *,
    timeout: int | float,
    model: str,
    lane: str | None,
    task_class: str | None,
    attempts: int | None = 1,
    think: bool | None = None,
    num_predict: int | None = None,
    options: Mapping[str, Any] | None = None,
    keep_alive: str | None = None,
    return_metadata: bool = False,
) -> Any:
    kwargs = {
        "timeout": timeout,
        "model": model,
        "task_class": task_class,
        "attempts": attempts,
        "think": think,
        "num_predict": num_predict,
        "options": dict(options) if options else None,
        "keep_alive": keep_alive,
        "return_metadata": return_metadata,
    }
    if ollama_call_fn is chief_llm.ollama_call:
        kwargs["lane"] = lane
        kwargs["_model_slot_held"] = True
    kwargs = {key: value for key, value in kwargs.items() if value is not None}
    if not return_metadata:
        kwargs.pop("return_metadata", None)
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
    result = ollama_call_fn(prompt, **call_kwargs)
    return result if return_metadata else str(result or "")


def _call_ollama_once_with_slot(
    ollama_call_fn: OllamaCallFn,
    prompt: str,
    *,
    timeout: int | float,
    model: str,
    lane: str | None,
    task_class: str | None,
    attempts: int | None,
    think: bool | None,
    num_predict: int | None,
    options: Mapping[str, Any] | None,
    keep_alive: str | None,
    return_metadata: bool,
    model_slot_lock_path: str | Path | None,
    model_slot_max_wait_seconds: float,
    model_slot_ack_threshold_seconds: float,
    on_model_slot_waiting: ModelSlotWaitingFn | None,
) -> Any:
    """Task 131: acquire the box's single model-call slot before calling the model. Waiting
    beats failing for operator-interactive traffic -- a concurrent caller QUEUES instead of
    instant-degrading. A timed-out wait is treated as an honest empty response (same shape as
    a model producing nothing), so callers' existing empty-result handling applies unchanged."""
    try:
        with acquire_model_slot(
            lock_path=model_slot_lock_path,
            max_wait_seconds=model_slot_max_wait_seconds,
            ack_threshold_seconds=model_slot_ack_threshold_seconds,
            on_waiting=on_model_slot_waiting,
        ):
            return _call_ollama_once(
                ollama_call_fn,
                prompt,
                timeout=timeout,
                model=model,
                lane=lane,
                task_class=task_class,
                attempts=attempts,
                think=think,
                num_predict=num_predict,
                options=options,
                keep_alive=keep_alive,
                return_metadata=return_metadata,
            )
    except ModelSlotTimeoutError:
        return {} if return_metadata else ""


def _result_has_text(result: Any) -> bool:
    if isinstance(result, Mapping):
        return bool(str(result.get("text") or result.get("response") or "").strip())
    return bool(str(result or "").strip())


def _snapshot_kwargs(snapshot: Any) -> dict[str, Any]:
    def _mapping_from(method_name: str) -> dict[str, Any]:
        method = getattr(snapshot, method_name, None)
        if not callable(method):
            return {}
        try:
            return dict(method())
        except Exception:
            return {}

    return {
        "available_vram_gb": getattr(snapshot, "available_vram_gb", None),
        "available_ram_gb": getattr(snapshot, "available_ram_gb", None),
        "resident_vram_by_model_gb": _mapping_from("resident_vram_by_model_gb"),
        # Task 146: pass the per-model offload truth (size_vram/size from /api/ps) so the
        # retry selector can refuse residency preference for a mostly-CPU-offloaded model.
        # Snapshots without the method yield {} -> fraction UNKNOWN -> selection unchanged.
        "offload_fraction_by_model": _mapping_from("offload_fraction_by_model"),
        "system_load_1m": getattr(snapshot, "system_load_1m", None),
        "cpu_count": getattr(snapshot, "cpu_count", None),
    }


def _enforce_model_fit(
    primary_model: str,
    *,
    task_class: str | None,
    lane: str | None,
    model_sizes_fn: Callable[[], Mapping[str, float]] | None = None,
) -> tuple[bool, str]:
    """Hardware-fit wall for EXPLICIT caller-passed models (2026-07-09 incident:
    a pre-doctrine chief_router call site hardcoded qwen3.6:latest (27G) on an
    interactive lane and swap-killed the whole box; the resolver's own choices
    already respect the ceilings, but explicit overrides bypassed them).

    Returns (fits, reason). Without a governor lease receipt, unknown size or a
    failed size probe cannot prove box fit and therefore demotes to the safe model.
    """
    try:
        sizes = (model_sizes_fn or chief_llm._ollama_model_sizes)()
        size_gb = sizes.get(primary_model)
        if size_gb is None:
            return False, f"model_fit_unknown_size_demotion:{primary_model}"
        ceiling = (
            chief_llm._ASYNC_MODEL_CEILING_GB
            if chief_llm._is_async_workload(task_class, lane)
            else chief_llm._INTERACTIVE_MODEL_CEILING_GB
        )
        if float(size_gb) > float(ceiling):
            return False, (
                f"model_fit_wall_demotion:{primary_model}:{size_gb:.1f}GB>"
                f"{ceiling:.1f}GB_ceiling"
            )
        return True, f"model_fit_ok:{primary_model}:{size_gb:.1f}GB"
    except Exception as exc:
        return False, f"model_fit_probe_error_demotion:{type(exc).__name__}"


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
    task_class: str | None,
    timeout: int | float,
    primary_model: str | None = None,
    primary_lane: str | None = None,
    lane: str | None = None,
    validation_outcome: str | None = None,
    attempts: int | None = 1,
    think: bool | None = None,
    num_predict: int | None = None,
    options: Mapping[str, Any] | None = None,
    keep_alive: str | None = None,
    return_metadata: bool = False,
    ollama_call_fn: OllamaCallFn | None = None,
    resolve_model_fn: ResolveModelFn | None = None,
    select_model_fn: SelectModelFn | None = None,
    resource_probe_fn: ResourceProbeFn | None = None,
    route_logger: RouteLogger | None = None,
    retry: bool = True,
    model_slot_lock_path: str | Path | None = None,
    model_slot_max_wait_seconds: float = DEFAULT_MODEL_SLOT_MAX_WAIT_SECONDS,
    model_slot_ack_threshold_seconds: float = DEFAULT_MODEL_SLOT_ACK_THRESHOLD_SECONDS,
    on_model_slot_waiting: ModelSlotWaitingFn | None = None,
    model_sizes_fn: Callable[[], Mapping[str, float]] | None = None,
) -> str:
    """Call a local model once, then one adaptive retry on empty output.

    The first attempt preserves the caller's resolved task-class model and
    timeout. The retry reuses the front-door resource-aware allowlist so a cold
    or contended large model can downshift to a small proven local model before
    the caller emits its honest degraded fallback.

    Task 131: both the primary and retry calls acquire the box's single model-call slot
    first (OLLAMA_NUM_PARALLEL=1) -- a concurrent caller queues for its turn instead of
    starving behind another call and honest-failing. ``on_model_slot_waiting`` lets the
    caller send one brief "on it" ack if the wait crosses ``model_slot_ack_threshold_seconds``.
    """

    ollama_call_fn = ollama_call_fn or chief_llm.ollama_call
    resolve_model_fn = resolve_model_fn or resolve_local_model
    select_model_fn = select_model_fn or select_frontdoor_model
    resource_probe_fn = resource_probe_fn or probe_frontdoor_resources

    explicit_model = primary_model is not None
    if primary_model is None or primary_lane is None:
        primary_model, primary_lane = resolve_model_fn(prompt, lane=lane, task_class=task_class)
    if chief_llm._is_governed_interactive_workload(
        task_class=task_class,
        lane=primary_lane,
    ):
        from local_model_governance import (
            INTERACTIVE_KEEP_ALIVE,
            INTERACTIVE_MODEL,
            interactive_runner_options,
        )

        primary_model = INTERACTIVE_MODEL
        options = interactive_runner_options(options)
        keep_alive = INTERACTIVE_KEEP_ALIVE
    if explicit_model:
        fits, fit_reason = _enforce_model_fit(
            primary_model, task_class=task_class, lane=lane, model_sizes_fn=model_sizes_fn
        )
        if not fits:
            demoted_model, demoted_lane = resolve_model_fn(prompt, lane=lane, task_class=task_class)
            print(
                f"[adaptive_model_call] {fit_reason} -> demoted to {demoted_model}",
                flush=True,
            )
            if route_logger is not None:
                route_logger(
                    task_class=task_class,
                    preferred_lane=primary_lane,
                    chosen_lane=demoted_lane,
                    reason=fit_reason,
                    escalation=False,
                    validation_outcome=validation_outcome,
                    model=demoted_model,
                )
            primary_model, primary_lane = demoted_model, demoted_lane
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
    result = _call_ollama_once_with_slot(
        ollama_call_fn,
        prompt,
        timeout=timeout,
        model=primary_model,
        lane=primary_lane,
        task_class=task_class,
        attempts=attempts,
        think=think,
        num_predict=num_predict,
        options=options,
        keep_alive=keep_alive,
        return_metadata=return_metadata,
        model_slot_lock_path=model_slot_lock_path,
        model_slot_max_wait_seconds=model_slot_max_wait_seconds,
        model_slot_ack_threshold_seconds=model_slot_ack_threshold_seconds,
        on_model_slot_waiting=on_model_slot_waiting,
    )
    if _result_has_text(result) or not retry:
        return result

    retry_model, retry_reason = _choose_retry_model(
        primary_model=primary_model,
        select_model_fn=select_model_fn,
        resource_probe_fn=resource_probe_fn,
    )
    if not retry_model:
        return result if return_metadata else ""
    if (
        chief_llm._uses_governed_interactive_runner(
            primary_model,
            task_class=task_class,
            lane=primary_lane,
        )
        and retry_model != primary_model
    ):
        return result if return_metadata else ""
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
    return _call_ollama_once_with_slot(
        ollama_call_fn,
        prompt,
        timeout=timeout,
        model=retry_model,
        lane=primary_lane,
        task_class=task_class,
        attempts=attempts,
        think=think,
        num_predict=num_predict,
        options=options,
        keep_alive=keep_alive,
        return_metadata=return_metadata,
        model_slot_lock_path=model_slot_lock_path,
        model_slot_max_wait_seconds=model_slot_max_wait_seconds,
        model_slot_ack_threshold_seconds=model_slot_ack_threshold_seconds,
        on_model_slot_waiting=on_model_slot_waiting,
    )


def adaptive_ollama_text(
    prompt: str,
    *,
    timeout: int | float = 15,
    task_class: str | None = None,
    lane: str | None = None,
    model: str | None = None,
    attempts: int | None = 1,
    think: bool | None = None,
    num_predict: int | None = None,
    options: Mapping[str, Any] | None = None,
    keep_alive: str | None = None,
    return_metadata: bool = False,
    retry: bool = True,
    **test_overrides: Any,
) -> Any:
    """Compatibility wrapper for old ``ollama_call``-shaped call sites.

    The primary call preserves explicit ``model`` / ``lane`` / ``task_class``
    arguments, while empty responses get the shared adaptive retry.
    """

    primary_lane = lane if model is None else (lane or "explicit_model")
    return adaptive_model_call(
        prompt,
        task_class=task_class,
        timeout=timeout,
        primary_model=model,
        primary_lane=primary_lane,
        lane=lane,
        attempts=attempts,
        think=think,
        num_predict=num_predict,
        options=options,
        keep_alive=keep_alive,
        return_metadata=return_metadata,
        retry=retry,
        **test_overrides,
    )

"""One-model interactive policy and GPU admission for local Ollama work.

The operator-facing path owns one bounded resident model. Background model work
must wait until that interactive residency has expired, and it must unload its
own model after each admitted call.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from model_slot_lease import ModelSlotTimeoutError, acquire_model_slot
from polish_loop.gpu_arbiter import GPUArbiter


INTERACTIVE_MODEL = "qwen3:8b-q4_K_M"
INTERACTIVE_KEEP_ALIVE = "10m"
INTERACTIVE_NUM_CTX = 2048
INTERACTIVE_NUM_GPU = 999
INTERACTIVE_NUM_BATCH = 128
BINDING_SESSION_KEY = "local_model_binding"
DEFAULT_GPU_LEASE_DB = "/home/openclaw/.openclaw/polish_loop/gpu_leases.sqlite"
OLLAMA_PS_URL = "http://127.0.0.1:11434/api/ps"


@dataclass(frozen=True)
class GovernedCallOutcome:
    status: str
    reason: str
    value: Any = None


def _binding_id(request_key: str) -> str:
    material = str(request_key or "interactive-request").encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:20]


def _valid_interactive_binding(binding: Any) -> bool:
    return (
        isinstance(binding, Mapping)
        and str(binding.get("schema_version") or "") == "local_model_binding_v2"
        and str(binding.get("binding_id") or "") != ""
        and str(binding.get("model") or "") == INTERACTIVE_MODEL
        and str(binding.get("keep_alive") or "") == INTERACTIVE_KEEP_ALIVE
        and binding.get("num_ctx") == INTERACTIVE_NUM_CTX
        and binding.get("num_gpu") == INTERACTIVE_NUM_GPU
        and binding.get("num_batch") == INTERACTIVE_NUM_BATCH
    )


def interactive_runner_options(options: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return request options pinned to the one resident interactive runner."""

    governed = dict(options or {})
    governed.update(
        num_ctx=INTERACTIVE_NUM_CTX,
        num_gpu=INTERACTIVE_NUM_GPU,
        num_batch=INTERACTIVE_NUM_BATCH,
    )
    return governed


def bind_interactive_model(
    session: Mapping[str, Any] | None,
    *,
    request_key: str = "",
) -> dict[str, Any]:
    """Attach the operator's fixed local-model decision exactly once."""

    bound = dict(session or {})
    existing = bound.get(BINDING_SESSION_KEY)
    if _valid_interactive_binding(existing):
        bound[BINDING_SESSION_KEY] = dict(existing)
        return bound

    stable_key = (
        request_key
        or str(bound.get("source_message_id") or "")
        or str(bound.get("request_id") or "")
        or "interactive-request"
    )
    bound[BINDING_SESSION_KEY] = {
        "schema_version": "local_model_binding_v2",
        "binding_id": _binding_id(stable_key),
        "model": INTERACTIVE_MODEL,
        "keep_alive": INTERACTIVE_KEEP_ALIVE,
        "num_ctx": INTERACTIVE_NUM_CTX,
        "num_gpu": INTERACTIVE_NUM_GPU,
        "num_batch": INTERACTIVE_NUM_BATCH,
        "decision_source": "operator_directive_telegram_1553",
    }
    return bound


def binding_from_session(session: Mapping[str, Any] | None) -> dict[str, Any]:
    binding = (session or {}).get(BINDING_SESSION_KEY)
    if _valid_interactive_binding(binding):
        return dict(binding)
    return bind_interactive_model(session)[BINDING_SESSION_KEY]


def interactive_model_from_session(session: Mapping[str, Any] | None) -> str:
    return str(binding_from_session(session)["model"])


def _resident_models(*, timeout: float = 0.5) -> set[str]:
    request = urllib.request.Request(OLLAMA_PS_URL, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    names: set[str] = set()
    for entry in payload.get("models") or ():
        if not isinstance(entry, Mapping):
            continue
        name = str(entry.get("name") or entry.get("model") or "").strip()
        if name:
            names.add(name)
    return names


def _governance_disabled_for_test(gpu_lease_db: str | Path | None) -> bool:
    return (
        os.environ.get("OPENCLAW_TEST_MODE", "").strip() == "1"
        and gpu_lease_db is None
        and not os.environ.get("OPENCLAW_GPU_LEASE_DB", "").strip()
    )


def async_model_admission_reason(
    *,
    gpu_lease_db: str | Path | None = None,
    resident_models_fn: Callable[[], set[str]] | None = None,
) -> str | None:
    """Return why background model work should retry later, else ``None``."""

    if _governance_disabled_for_test(gpu_lease_db):
        return None
    residents = resident_models_fn or _resident_models
    try:
        if INTERACTIVE_MODEL in residents():
            return "interactive_model_resident"
    except Exception as exc:
        return f"resident_probe_error:{type(exc).__name__}"

    lease_path = (
        Path(gpu_lease_db)
        if gpu_lease_db is not None
        else Path(os.environ.get("OPENCLAW_GPU_LEASE_DB", "").strip() or DEFAULT_GPU_LEASE_DB)
    )
    try:
        current = GPUArbiter(lease_path).current()
    except Exception as exc:
        return f"gpu_arbiter_error:{type(exc).__name__}"
    if not current or str(current.get("holder_type") or "") != "interactive":
        return None
    try:
        expiry = datetime.fromisoformat(str(current.get("expires_at") or ""))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        if expiry.astimezone(UTC) <= datetime.now(UTC):
            return None
    except ValueError:
        return "interactive_lease_expiry_invalid"
    return "interactive_lease_active"


def run_async_model_call(
    call_model: Callable[[], Any],
    *,
    task_class: str,
    holder_id: str,
    gpu_lease_db: str | Path | None = None,
    model_slot_path: str | Path | None = None,
    resident_models_fn: Callable[[], set[str]] | None = None,
    model_slot_already_held: bool = False,
) -> GovernedCallOutcome:
    """Admit one background call only when the interactive lane is cold."""

    if _governance_disabled_for_test(gpu_lease_db):
        return GovernedCallOutcome(
            status="completed",
            reason="governance_disabled_test_mode",
            value=call_model(),
        )

    residents = resident_models_fn or _resident_models
    try:
        if INTERACTIVE_MODEL in residents():
            return GovernedCallOutcome("deferred", "interactive_model_resident")
    except Exception as exc:
        return GovernedCallOutcome("deferred", f"resident_probe_error:{type(exc).__name__}")

    lease_path = (
        Path(gpu_lease_db)
        if gpu_lease_db is not None
        else Path(os.environ.get("OPENCLAW_GPU_LEASE_DB", "").strip() or DEFAULT_GPU_LEASE_DB)
    )
    try:
        arbiter = GPUArbiter(lease_path)
        lease = arbiter.acquire("build", holder_id, ttl_seconds=3600)
    except Exception as exc:
        return GovernedCallOutcome("deferred", f"gpu_arbiter_error:{type(exc).__name__}")
    if not str(lease.get("status") or "").startswith("acquired"):
        return GovernedCallOutcome("deferred", str(lease.get("reason") or "gpu_busy"))

    nonce = str(lease.get("lease_nonce") or "")

    def admitted_call() -> GovernedCallOutcome:
        current = arbiter.current()
        if not current or str(current.get("lease_nonce") or "") != nonce:
            return GovernedCallOutcome("deferred", "build_lease_preempted")
        try:
            if INTERACTIVE_MODEL in residents():
                return GovernedCallOutcome("deferred", "interactive_model_resident")
        except Exception as exc:
            return GovernedCallOutcome("deferred", f"resident_probe_error:{type(exc).__name__}")
        return GovernedCallOutcome("completed", "build_window_acquired", call_model())

    try:
        if model_slot_already_held:
            return admitted_call()
        try:
            with acquire_model_slot(lock_path=model_slot_path, max_wait_seconds=90):
                return admitted_call()
        except ModelSlotTimeoutError:
            return GovernedCallOutcome("deferred", "model_slot_timeout")
    finally:
        if nonce:
            try:
                arbiter.release(holder_id, nonce)
            except Exception:
                pass


def run_interactive_model_call(
    call_model: Callable[[], Any],
    *,
    holder_id: str,
    gpu_lease_db: str | Path | None = None,
    model_slot_path: str | Path | None = None,
) -> GovernedCallOutcome:
    """Serialize a direct interactive call and advertise its priority to builders."""

    if _governance_disabled_for_test(gpu_lease_db):
        with acquire_model_slot(lock_path=model_slot_path, max_wait_seconds=90):
            return GovernedCallOutcome("completed", "test_model_slot", call_model())

    lease_path = (
        Path(gpu_lease_db)
        if gpu_lease_db is not None
        else Path(os.environ.get("OPENCLAW_GPU_LEASE_DB", "").strip() or DEFAULT_GPU_LEASE_DB)
    )
    arbiter = None
    nonce = ""
    try:
        arbiter = GPUArbiter(lease_path)
        lease = arbiter.acquire("interactive", holder_id, ttl_seconds=180)
        if str(lease.get("status") or "").startswith("acquired"):
            nonce = str(lease.get("lease_nonce") or "")
    except Exception:
        arbiter = None

    try:
        with acquire_model_slot(lock_path=model_slot_path, max_wait_seconds=90):
            return GovernedCallOutcome("completed", "interactive_window", call_model())
    except ModelSlotTimeoutError:
        return GovernedCallOutcome("deferred", "model_slot_timeout")
    finally:
        if arbiter is not None and nonce:
            try:
                arbiter.release(holder_id, nonce)
            except Exception:
                pass


__all__ = [
    "BINDING_SESSION_KEY",
    "GovernedCallOutcome",
    "INTERACTIVE_KEEP_ALIVE",
    "INTERACTIVE_MODEL",
    "INTERACTIVE_NUM_BATCH",
    "INTERACTIVE_NUM_CTX",
    "INTERACTIVE_NUM_GPU",
    "bind_interactive_model",
    "binding_from_session",
    "interactive_runner_options",
    "async_model_admission_reason",
    "interactive_model_from_session",
    "run_async_model_call",
    "run_interactive_model_call",
]

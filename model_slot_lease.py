"""Model-slot lease: a bounded-wait, cross-process lock for the single local-model call the
box can run at once (OLLAMA_NUM_PARALLEL=1).

Task 131 root cause (live evidence 2026-07-07 18:0x): the operator sent 5 texts near-
simultaneously. Two deterministic answers succeeded; both agents needing a live model call
degraded because the second caller starved behind the first, hit its lane timeout, and
honest-failed -- then the adaptive retry re-entered the SAME occupied queue. Waiting beats
failing for operator-interactive traffic: a second concurrent caller should QUEUE for the
slot, not instant-degrade.

This is deliberately a standalone, reusable primitive -- per Fable's directive it is the seed
of 96's box-lease (98's scheduler absorbs it later), not a throwaway bridge.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Iterator

# Literal fallback -- only used when OPENCLAW_MODEL_SLOT_LOCK_PATH is unset. Read via
# default_model_slot_lock_path() at CALL time (never baked into a function signature as a
# bare default), so pytest sandbox isolation (which sets this env var) is honored regardless
# of module import order relative to sandbox installation.
DEFAULT_MODEL_SLOT_LOCK_PATH = "/tmp/openclaw-model-slot.lock"
DEFAULT_MODEL_SLOT_MAX_WAIT_SECONDS = 90.0
DEFAULT_MODEL_SLOT_ACK_THRESHOLD_SECONDS = 8.0
_POLL_INTERVAL_SECONDS = 0.25


def default_model_slot_lock_path() -> str:
    return os.environ.get("OPENCLAW_MODEL_SLOT_LOCK_PATH", "").strip() or DEFAULT_MODEL_SLOT_LOCK_PATH


class ModelSlotTimeoutError(RuntimeError):
    """Raised when the model slot was not freed within the bounded wait."""

    def __init__(self, elapsed_seconds: float, max_wait_seconds: float):
        self.elapsed_seconds = elapsed_seconds
        self.max_wait_seconds = max_wait_seconds
        super().__init__(
            f"model slot not free after {elapsed_seconds:.1f}s (max_wait={max_wait_seconds}s)"
        )


@contextlib.contextmanager
def acquire_model_slot(
    *,
    lock_path: str | Path | None = None,
    max_wait_seconds: float = DEFAULT_MODEL_SLOT_MAX_WAIT_SECONDS,
    on_waiting: Callable[[float], None] | None = None,
    ack_threshold_seconds: float = DEFAULT_MODEL_SLOT_ACK_THRESHOLD_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
    now_fn: Callable[[], float] = time.monotonic,
) -> Iterator[None]:
    """Bounded-wait lease for the box's one model-call slot.

    ``lock_path`` defaults (at CALL time, not import time) to
    ``OPENCLAW_MODEL_SLOT_LOCK_PATH`` if set, else the real box's lock file -- pytest sandbox
    isolation always sets that env var, so a test run never contends with a live process.

    Blocks (polling, never busy-spins past the poll interval) until the slot is free or
    ``max_wait_seconds`` elapses, then raises ``ModelSlotTimeoutError`` -- waiting beats
    failing for operator-interactive traffic, but a caller must still fail eventually rather
    than hang forever.

    ``on_waiting`` fires AT MOST ONCE per acquire, the first time the wait crosses
    ``ack_threshold_seconds`` -- callers use this to send one brief "on it" ack (never spam).
    Exceptions from ``on_waiting`` are swallowed; a broken ack must never block the lease.

    When the slot is immediately free (the common, uncontended case), this costs one
    non-blocking flock syscall -- single-call latency is unchanged.
    """
    path = Path(lock_path) if lock_path is not None else Path(default_model_slot_lock_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    start = now_fn()
    acked = False
    fh = open(path, "a+")
    try:
        while True:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                elapsed = now_fn() - start
                if elapsed >= max_wait_seconds:
                    raise ModelSlotTimeoutError(elapsed, max_wait_seconds)
                if not acked and elapsed >= ack_threshold_seconds and on_waiting is not None:
                    acked = True
                    try:
                        on_waiting(elapsed)
                    except Exception:
                        pass
                sleep_fn(_POLL_INTERVAL_SECONDS)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    finally:
        fh.close()

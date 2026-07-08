from __future__ import annotations

import fcntl
import threading
import time
from pathlib import Path

import pytest

from model_slot_lease import (
    ModelSlotTimeoutError,
    acquire_model_slot,
)


def test_uncontended_acquire_succeeds_immediately_and_releases(tmp_path):
    lock_path = tmp_path / "model.lock"

    with acquire_model_slot(lock_path=lock_path, max_wait_seconds=5.0):
        pass

    # Lease released on exit -- a fresh flock attempt must succeed immediately.
    fh = open(lock_path, "a+")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    finally:
        fh.close()


def test_contended_acquire_waits_then_succeeds_after_release(tmp_path):
    lock_path = tmp_path / "model.lock"
    holder_released = threading.Event()
    waiter_acquired = threading.Event()

    def hold_for_a_moment():
        with acquire_model_slot(lock_path=lock_path, max_wait_seconds=5.0):
            time.sleep(0.3)
        holder_released.set()

    holder = threading.Thread(target=hold_for_a_moment)
    holder.start()
    time.sleep(0.05)  # let the holder acquire first

    start = time.monotonic()
    with acquire_model_slot(lock_path=lock_path, max_wait_seconds=5.0):
        waiter_acquired.set()
    elapsed = time.monotonic() - start

    holder.join(timeout=5)
    assert holder_released.is_set()
    assert waiter_acquired.is_set()
    assert elapsed >= 0.2, "waiter must have actually waited for the holder to release"


def test_timeout_raises_when_wait_exceeds_max(tmp_path):
    lock_path = tmp_path / "model.lock"
    blocker = open(lock_path, "a+")
    fcntl.flock(blocker.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        fake_time = {"now": 0.0}

        def fake_now():
            return fake_time["now"]

        def fake_sleep(seconds):
            fake_time["now"] += 1.0  # advance well past any single poll interval

        with pytest.raises(ModelSlotTimeoutError):
            with acquire_model_slot(
                lock_path=lock_path,
                max_wait_seconds=3.0,
                now_fn=fake_now,
                sleep_fn=fake_sleep,
            ):
                pass
    finally:
        fcntl.flock(blocker.fileno(), fcntl.LOCK_UN)
        blocker.close()


def test_on_waiting_fires_exactly_once_after_threshold(tmp_path):
    lock_path = tmp_path / "model.lock"
    blocker = open(lock_path, "a+")
    fcntl.flock(blocker.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    calls: list[float] = []
    fake_time = {"now": 0.0}

    def fake_now():
        return fake_time["now"]

    def fake_sleep(seconds):
        fake_time["now"] += 1.0

    try:
        with pytest.raises(ModelSlotTimeoutError):
            with acquire_model_slot(
                lock_path=lock_path,
                max_wait_seconds=5.0,
                ack_threshold_seconds=2.0,
                on_waiting=lambda elapsed: calls.append(elapsed),
                now_fn=fake_now,
                sleep_fn=fake_sleep,
            ):
                pass
    finally:
        fcntl.flock(blocker.fileno(), fcntl.LOCK_UN)
        blocker.close()

    assert len(calls) == 1, "on_waiting must fire at most once per acquire, never spam"
    assert calls[0] >= 2.0


def test_on_waiting_exception_does_not_break_acquire(tmp_path):
    lock_path = tmp_path / "model.lock"
    holder_released = threading.Event()

    def hold_for_a_moment():
        with acquire_model_slot(lock_path=lock_path, max_wait_seconds=5.0):
            time.sleep(0.2)
        holder_released.set()

    holder = threading.Thread(target=hold_for_a_moment)
    holder.start()
    time.sleep(0.05)

    def broken_ack(elapsed):
        raise RuntimeError("ack transport down")

    with acquire_model_slot(
        lock_path=lock_path,
        max_wait_seconds=5.0,
        ack_threshold_seconds=0.01,
        on_waiting=broken_ack,
    ):
        pass

    holder.join(timeout=5)
    assert holder_released.is_set()

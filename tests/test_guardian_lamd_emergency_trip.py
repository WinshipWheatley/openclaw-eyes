from __future__ import annotations

import signal

from guardian_lamd_emergency_trip import (
    GUARDIAN_LAMD_EMERGENCY_REASON,
    install_guardian_lamd_emergency_signal,
)


def test_guardian_emergency_signal_trips_lamd_brake_with_fixed_logged_reason(capsys) -> None:
    registered: dict[str, object] = {}
    trip_reasons: list[str] = []

    class _Loop:
        def add_signal_handler(self, signum, callback) -> None:
            registered["signum"] = signum
            registered["callback"] = callback

    def _trip(reason: str):
        trip_reasons.append(reason)
        return {
            "ok": True,
            "state": {
                "state": "FROZEN",
                "set_by": "guardian",
                "generation": 7,
            },
        }

    install_guardian_lamd_emergency_signal(_Loop(), trip=_trip)

    assert registered["signum"] == signal.SIGUSR2
    callback = registered["callback"]
    assert callable(callback)
    callback()

    assert trip_reasons == [GUARDIAN_LAMD_EMERGENCY_REASON]
    output = capsys.readouterr().out
    assert "lamd_emergency_trip=ok" in output
    assert "generation=7" in output


def test_guardian_emergency_signal_logs_failure_without_clearing(capsys) -> None:
    registered: dict[str, object] = {}

    class _Loop:
        def add_signal_handler(self, signum, callback) -> None:
            registered["callback"] = callback

    def _fail(_reason: str):
        raise ConnectionError("broker unavailable")

    install_guardian_lamd_emergency_signal(_Loop(), trip=_fail)
    callback = registered["callback"]
    assert callable(callback)
    callback()

    output = capsys.readouterr().out
    assert "lamd_emergency_trip=failed" in output
    assert "error=ConnectionError" in output

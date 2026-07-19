"""Trip-only LAMD brake hook for the live Guardian service."""

from __future__ import annotations

import signal

from lamd_autosend_brake import guardian_trip


GUARDIAN_LAMD_EMERGENCY_REASON = "guardian operator-class emergency-halt signal"


def install_guardian_lamd_emergency_signal(loop, *, trip=None) -> None:
    """Install the OS signal hook; message content has no route to this module."""

    trip_function = trip or guardian_trip

    def _trip() -> None:
        reason = GUARDIAN_LAMD_EMERGENCY_REASON
        print(
            f"[guardian] lamd_emergency_trip=requested reason={reason}",
            flush=True,
        )
        try:
            result = trip_function(reason)
        except Exception as exc:
            print(
                f"[guardian] lamd_emergency_trip=failed reason={reason} "
                f"error={type(exc).__name__}",
                flush=True,
            )
            return
        state = result.get("state") if isinstance(result, dict) else None
        state = state if isinstance(state, dict) else {}
        status = "ok" if result.get("ok") is True else "refused"
        print(
            f"[guardian] lamd_emergency_trip={status} reason={reason} "
            f"state={state.get('state', '')} set_by={state.get('set_by', '')} "
            f"generation={state.get('generation', '')}",
            flush=True,
        )

    loop.add_signal_handler(signal.SIGUSR2, _trip)

"""No-send guard for safely reloading Cassandra send-capable services."""

from __future__ import annotations

import os


ENV_VAR = "CASSANDRA_NO_SEND_RELOAD_GUARD"
ALT_ENV_VAR = "OPENCLAW_CASSANDRA_NO_SEND_RELOAD_GUARD"
MODE_ENV_VAR = "CASSANDRA_SEND_CAPABLE_MODE"
ALT_MODE_ENV_VAR = "OPENCLAW_CASSANDRA_SEND_CAPABLE_MODE"
STATUS_DRY_RUN_MODE = "status_dry_run"
_TRUTHY = {"1", "true", "yes", "on", "enabled"}


def current_send_capable_mode() -> str:
    """Return the local send-capable service mode without exposing env values."""
    value = os.environ.get(MODE_ENV_VAR) or os.environ.get(ALT_MODE_ENV_VAR) or ""
    return value.strip().lower()


def is_status_dry_run_enabled() -> bool:
    """Return true when services may inspect status but must block sends."""
    return current_send_capable_mode() == STATUS_DRY_RUN_MODE


def is_no_send_reload_guard_enabled() -> bool:
    """Return true when Cassandra send-capable loops must quiesce.

    The guard is intentionally process-local and environment-driven so ignored
    local service env can reload safely without committing secret files.
    """
    return any(
        (os.environ.get(name) or "").strip().lower() in _TRUTHY
        for name in (ENV_VAR, ALT_ENV_VAR)
    )


def should_quiesce_send_capable_service() -> bool:
    """Return true for the emergency startup guard, unless dry-run is explicit."""
    return is_no_send_reload_guard_enabled() and not is_status_dry_run_enabled()


def outbound_delivery_blocked() -> bool:
    """Return true when any local no-send mode blocks outbound delivery."""
    return is_no_send_reload_guard_enabled() or is_status_dry_run_enabled()

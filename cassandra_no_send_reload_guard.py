"""No-send guard for safely reloading Cassandra send-capable services."""

from __future__ import annotations

import os


ENV_VAR = "CASSANDRA_NO_SEND_RELOAD_GUARD"
ALT_ENV_VAR = "OPENCLAW_CASSANDRA_NO_SEND_RELOAD_GUARD"
_TRUTHY = {"1", "true", "yes", "on", "enabled"}


def is_no_send_reload_guard_enabled() -> bool:
    """Return true when Cassandra send-capable loops must quiesce.

    The guard is intentionally process-local and environment-driven so ignored
    local service env can reload safely without committing secret files.
    """
    return any(
        (os.environ.get(name) or "").strip().lower() in _TRUTHY
        for name in (ENV_VAR, ALT_ENV_VAR)
    )

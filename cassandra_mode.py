"""
cassandra_mode.py

Centralized global mode-state checks for Cassandra.
Provides low-level, decision-free file-existence checks for focus and social modes.
"""

from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

FOCUS_LOCK_PATH  = Path("/mnt/c/OpenClaw/logs/cassandra_focus.lock")
SOCIAL_LOCK_PATH = Path("/mnt/c/OpenClaw/logs/cassandra_social.lock")

# ── Mode checks ───────────────────────────────────────────────────────────────

def is_focus_mode() -> bool:
    """Return True if focus mode is active (lock file exists)."""
    return FOCUS_LOCK_PATH.exists()


def is_social_mode() -> bool:
    """Return True if social mode is active (lock file exists)."""
    return SOCIAL_LOCK_PATH.exists()

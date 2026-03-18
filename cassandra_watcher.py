"""
cassandra_watcher.py

Ambient observer daemon for Cassandra.

Polls system state every 30 minutes and sends a tasteful chirp when
a meaningful condition is met.  Respects focus mode and social mode.

Chirp types (v1):
  late_session    — after 11pm, if ops/album activity has been recent
  pending_payment — payment follow-ups with entries > 2 days old
  pending_action  — ops actions with entries > 3 days old

Throttle:
  Max 3 chirps per day, min 4h between chirps.
  Focus mode → silence.  Social mode → silence.
"""

import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

from chief_file_io import load_json
from cassandra_brain import (
    is_focus_mode,
    is_social_mode,
    load_state,
    save_state,
    chirp_allowed,
    log_chirp,
)

_VAULT_SYS   = Path("/mnt/c/OpenClawShared/openclaw-vault/System")
_OPS_PAYMENT = _VAULT_SYS / "Ops Payment Follow-ups.md"
_OPS_ACTIONS = _VAULT_SYS / "Ops Actions.md"
_OPS_LOG     = Path("/mnt/c/OpenClaw/logs/ops_intake_log.md")

POLL_INTERVAL_S = 1800  # 30 minutes


def _send(message: str) -> None:
    try:
        subprocess.run(
            ["python", str(Path.home() / "chief_sender.py"), message],
            check=False,
            timeout=10,
        )
        print(f"[cassandra_watcher] chirped: {message[:80]}", flush=True)
    except Exception as e:
        print(f"[cassandra_watcher] send error: {e}", flush=True)


def _tail_md(path: Path, n: int = 10) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip().startswith("- [")][-n:]


def _entry_age_days(entry: str) -> int | None:
    m = re.search(r"\[(\d{4}-\d{2}-\d{2})", entry)
    if m:
        try:
            d = datetime.strptime(m.group(1), "%Y-%m-%d").date()
            return (datetime.now().date() - d).days
        except Exception:
            pass
    return None


# ── Chirp evaluators ──────────────────────────────────────────────────────────

def _check_late_session() -> tuple[str, str] | None:
    h = datetime.now().hour
    if h >= 23 or h < 5:
        # Only chirp if there's been recent ops/log activity (file modified today)
        today = datetime.now().date().isoformat()
        for path in (_OPS_LOG, _OPS_ACTIONS):
            if path.exists():
                mtime = datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
                if mtime == today:
                    return (
                        "late_session",
                        "It's past midnight and there's been recent activity. "
                        "If you're done — close the loop and rest. Chief holds the fort.",
                    )
    return None


def _check_pending_payments() -> tuple[str, str] | None:
    entries = _tail_md(_OPS_PAYMENT)
    stale = [e for e in entries if (_entry_age_days(e) or 0) > 2]
    if len(stale) >= 2:
        return (
            "pending_payment",
            f"{len(stale)} payment follow-ups have been sitting for 2+ days. "
            "Worth a pass through Ops Payment Follow-ups when you have a moment.",
        )
    if len(stale) == 1:
        return (
            "pending_payment",
            "One payment follow-up has been waiting a few days. Might be worth checking.",
        )
    return None


def _check_pending_actions() -> tuple[str, str] | None:
    entries = _tail_md(_OPS_ACTIONS)
    stale = [e for e in entries if (_entry_age_days(e) or 0) > 3]
    if len(stale) >= 3:
        return (
            "pending_action",
            f"{len(stale)} action items in Ops Actions are 3+ days old. "
            "Consider a quick sweep when you surface.",
        )
    return None


def _evaluate() -> tuple[str, str] | None:
    for fn in (_check_late_session, _check_pending_payments, _check_pending_actions):
        result = fn()
        if result:
            return result
    return None


# ── Main loop ─────────────────────────────────────────────────────────────────

def run_loop() -> None:
    print("[cassandra_watcher] started.", flush=True)
    while True:
        try:
            if not is_focus_mode() and not is_social_mode():
                state = load_state()
                if chirp_allowed("any", state):
                    candidate = _evaluate()
                    if candidate:
                        chirp_type, message = candidate
                        _send(message)
                        log_chirp(chirp_type, state)
                        save_state(state)
        except Exception as e:
            print(f"[cassandra_watcher] error: {e}", flush=True)

        time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":
    run_loop()

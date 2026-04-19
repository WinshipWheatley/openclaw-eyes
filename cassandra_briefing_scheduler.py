"""
cassandra_briefing_scheduler.py

Daemon: polls every 5 minutes.  On each tick:
  1. Check for briefing slots whose generation window is now open.
  2. Generate any due slots that haven't been generated today.
  3. If the window is protected → mark briefing pending, log reason, skip delivery.
  4. If the window is clear → deliver immediately via Telegram + batch voice.
  5. On every tick, also check for stale pending briefings and deliver them
     if the protected window has since cleared.

Protected windows (from cassandra_briefing_brain.protected_reason()):
  focus_mode · social_mode · active_session:<workflow> · scheduler:<task> · approval_pending

Voice on delivery
-----------------
  Uses speak_batch() — Qwen3-TTS if installed (slow but high-quality),
  Kokoro fallback, then Piper, then silent.
  Text is always sent to Telegram first; voice is secondary and non-blocking.
"""

import time
import os
import sys
from pathlib import Path

from cassandra_briefing_brain import (
    due_slots,
    generate_briefing,
    save_briefing,
    mark_delivered,
    refresh_briefing_text,
    pending_briefings,
    is_protected_window,
    protected_reason,
    split_briefing_messages,
    briefing_voice_text,
)
from cassandra_sender import send_message
from cassandra_voice import speak_batch

POLL_INTERVAL = 300  # 5 minutes
_RELOAD_PATHS = (
    Path(__file__),
    Path("/home/openclaw/cassandra_brain.py"),
    Path("/home/openclaw/cassandra_briefing_brain.py"),
    Path("/home/openclaw/cassandra_briefing_morning_context.py"),
    Path("/home/openclaw/finance_state.py"),
    Path("/home/openclaw/finance_state.json"),
    Path("/home/openclaw/cassandra_reality_notes.json"),
)
_SOURCE_MTIMES = {
    str(path): (path.stat().st_mtime if path.exists() else 0.0)
    for path in _RELOAD_PATHS
}


def _restart_if_sources_changed() -> None:
    for raw_path, start_mtime in _SOURCE_MTIMES.items():
        path = Path(raw_path)
        current = path.stat().st_mtime if path.exists() else 0.0
        if current > start_mtime:
            print(
                f"[briefing_scheduler] source change detected ({path.name}) — reloading process",
                flush=True,
            )
            os.execv(sys.executable, [sys.executable, "-u", str(Path(__file__))])


# ── Delivery ──────────────────────────────────────────────────────────────────

def _deliver(entry: dict) -> None:
    """Send a briefing to Telegram then trigger batch voice render."""
    slot  = entry["slot"]
    date  = entry["date"]
    text  = entry["text"]

    try:
        for message in split_briefing_messages(entry):
            send_message(message)
        mark_delivered(date, slot)
        print(
            f"[briefing_scheduler] delivered {date}_{slot} ({len(text)} chars)",
            flush=True,
        )
    except Exception as e:
        print(f"[briefing_scheduler] delivery error ({slot}): {e}", flush=True)
        return

    # Batch voice — non-blocking, optional; failures are swallowed inside speak_batch
    speak_batch(briefing_voice_text(entry))


# ── Main tick ─────────────────────────────────────────────────────────────────

def _tick() -> None:
    _restart_if_sources_changed()
    # 1. Generate any slots that are newly due
    for slot in due_slots():
        print(f"[briefing_scheduler] generating {slot} briefing …", flush=True)
        try:
            text   = generate_briefing(slot)
            reason = protected_reason()
            entry  = save_briefing(slot, text, pending_reason=reason)

            if reason:
                print(
                    f"[briefing_scheduler] {slot} pending — protected window: {reason}",
                    flush=True,
                )
            else:
                _deliver(entry)

        except Exception as e:
            print(f"[briefing_scheduler] error generating {slot}: {e}", flush=True)

    # 2. Deliver any stale pending briefings now that the window may be clear
    if not is_protected_window():
        for entry in pending_briefings():
            # A pending briefing was written under a protected reason.
            # Regenerate now so stale "paused/waiting" language is not delivered late.
            if entry.get("pending_reason"):
                try:
                    refreshed_text = generate_briefing(entry["slot"])
                    refresh_briefing_text(entry["date"], entry["slot"], refreshed_text, pending_reason=None)
                    entry["text"] = refreshed_text
                    entry["pending_reason"] = None
                    print(
                        f"[briefing_scheduler] refreshed pending {entry['date']}_{entry['slot']} before delivery",
                        flush=True,
                    )
                except Exception as e:
                    print(
                        f"[briefing_scheduler] refresh failed for {entry['date']}_{entry['slot']}: {e}",
                        flush=True,
                    )
            print(
                f"[briefing_scheduler] delivering stale pending "
                f"{entry['date']}_{entry['slot']}",
                flush=True,
            )
            _deliver(entry)


# ── Loop ──────────────────────────────────────────────────────────────────────

def run_loop() -> None:
    print("[briefing_scheduler] started.", flush=True)
    while True:
        try:
            _tick()
        except Exception as e:
            print(f"[briefing_scheduler] unhandled error: {e}", flush=True)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run_loop()

"""
cassandra_briefing_scheduler.py

Daemon: polls every 5 minutes.  On each tick:
  1. Check for briefing slots whose generation window is now open.
  2. Generate any due slots that haven't been generated today.
  3. If the window is protected → mark briefing pending, log reason, skip delivery.
  4. If the window is clear → deliver immediately to operator Telegram + batch voice.
  5. On every tick, also check for stale pending briefings and deliver them
     if the protected window has since cleared.

Protected windows (from cassandra_briefing_brain.protected_reason()):
  focus_mode · social_mode · active_session:<workflow> · scheduler:<task> · approval_pending

Voice on delivery
-----------------
  Uses Cassandra's dual voice path so scheduled briefings can produce a
  Telegram voice note as well as local playback when voice is enabled.
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
from cassandra_sender import send_operator_brief
from cassandra_voice import speak_and_send_operator_brief_voice  # Cassandra voices her own brief (af_heart)
from cassandra_no_send_reload_guard import (
    briefing_delivery_blocked,
    is_internal_brief_carveout_enabled,
    is_status_dry_run_enabled,
    should_quiesce_send_capable_service,
)
from cassandra_send_status_dry_run import build_briefing_scheduler_status, format_service_status_marker
from local_model_governance import async_model_admission_reason

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
    if briefing_delivery_blocked():
        print("[briefing_scheduler] briefing delivery blocked by no-send guard", flush=True)
        return

    slot  = entry["slot"]
    date  = entry["date"]
    text  = entry["text"]
    from operator_surface_guard import guard_operator_reply_with_receipt

    def bounded(value: str) -> str:
        return guard_operator_reply_with_receipt(
            value,
            agent_role="CASSANDRA",
            technical_intent=False,
        ).visible_text

    if slot == "morning":
        import json
        try:
            chunks = json.loads(text)
            if isinstance(chunks, list):
                from cassandra_briefing_brain import normalize_speech_text
                for chunk in chunks:
                    header = chunk.get("header", "").strip()
                    body = chunk.get("body", "").strip()
                    if not header or not body:
                        continue
                    message = f"[{header}]\n\n{body}"
                    try:
                        safe_message = bounded(message)
                        send_operator_brief(safe_message)
                        safe_body = bounded(body)
                        voice_text = normalize_speech_text(safe_body)
                        speak_and_send_operator_brief_voice(voice_text)
                    except Exception as e:
                        print(f"[briefing_scheduler] chunk delivery error: {e}", flush=True)
                mark_delivered(date, slot)
                print(f"[briefing_scheduler] delivered {date}_{slot} in {len(chunks)} chunks", flush=True)
                return
        except Exception as e:
            print(f"[briefing_scheduler] JSON parse error for morning chunks: {e}. Falling back to standard.", flush=True)

    try:
        for message in split_briefing_messages(entry):
            safe_message = bounded(message)
            send_operator_brief(safe_message)
        mark_delivered(date, slot)
        print(
            f"[briefing_scheduler] delivered {date}_{slot} ({len(text)} chars)",
            flush=True,
        )
    except Exception as e:
        print(f"[briefing_scheduler] delivery error ({slot}): {e}", flush=True)
        return

    # Voice note/local playback — non-blocking, optional; failures are swallowed inside voice path.
    # Morning slot handled voice note per-chunk above.
    if slot != "morning":
        safe_voice_text = bounded(briefing_voice_text(entry))
        speak_and_send_operator_brief_voice(safe_voice_text)


# ── Main tick ─────────────────────────────────────────────────────────────────

def _refresh_presence_read_model() -> None:
    """Keep agent_presence.json fresh on every tick (no new service; folds into this daemon)."""
    try:
        import subprocess
        subprocess.run([sys.executable, "scripts/export_agent_presence_read_model.py"],
                       cwd="/home/openclaw", capture_output=True, timeout=60)
    except Exception as e:
        print(f"[briefing_scheduler] presence export skipped: {e}", flush=True)


def _tick() -> None:
    _refresh_presence_read_model()
    if is_status_dry_run_enabled():
        status = build_briefing_scheduler_status()
        print(format_service_status_marker("briefing_scheduler", status), flush=True)
        return

    if should_quiesce_send_capable_service() and not is_internal_brief_carveout_enabled():
        print(
            "[briefing_scheduler] no-send reload guard active; skipping scheduler tick",
            flush=True,
        )
        return

    _restart_if_sources_changed()
    # 1. Generate any slots that are newly due
    for slot in due_slots():
        resource_reason = async_model_admission_reason()
        if resource_reason:
            print(
                f"[briefing_scheduler] retrying {slot} later - GPU reserved: {resource_reason}",
                flush=True,
            )
            continue
        print(f"[briefing_scheduler] generating {slot} briefing …", flush=True)
        try:
            text   = generate_briefing(slot)
            reason = protected_reason(slot=slot)
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
    for entry in pending_briefings():
        slot = entry.get("slot")
        if not is_protected_window(slot=slot):
            # A pending briefing was written under a protected reason.
            # Regenerate now so stale "paused/waiting" language is not delivered late.
            if entry.get("pending_reason"):
                resource_reason = async_model_admission_reason()
                if resource_reason:
                    print(
                        f"[briefing_scheduler] refresh of {entry['date']}_{entry['slot']} "
                        f"deferred - GPU reserved: {resource_reason}",
                        flush=True,
                    )
                    continue
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

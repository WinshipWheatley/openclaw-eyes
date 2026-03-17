"""
chief_reporter_brain.py

Third leg of the Workers/Watcher trinity.
Workers queue and process silently. Watcher flags issues silently.
Reporter reads what they did and delivers a readable daily digest via Telegram.

Triggered by:
  - Telegram: "system report", "daily report", "what ran today", etc.
  - Intent: system_report in chief_router.py

Saves report to openclaw-vault/System/Daily Report.md.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from chief_llm import ollama_call

# ── Paths ──────────────────────────────────────────────────────────────────────

LOGS_DIR          = Path("/mnt/c/OpenClaw/logs")
WORKER_OUT        = LOGS_DIR / "worker.out"
MEMORY_OUT        = LOGS_DIR / "memory_worker.out"
STATE_OUT         = LOGS_DIR / "state_worker.out"
LISTENER_OUT      = LOGS_DIR / "listener.out"
BILLING_OUT       = LOGS_DIR / "billing_brain.out"
INPUT_LOG         = LOGS_DIR / "chief_input.log"
WATCHER_STATE     = LOGS_DIR / "chief_watcher_state.json"

VAULT_REPORT      = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Daily Report.md")

# ── Log readers ────────────────────────────────────────────────────────────────

def _tail(path: Path, n: int = 300) -> list[str]:
    """Return last N lines from a file, or [] if missing."""
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-n:]
    except Exception:
        return []


def _today_lines(lines: list[str]) -> list[str]:
    """Filter lines containing today's date string."""
    today = datetime.now().strftime("%Y-%m-%d")
    return [l for l in lines if today in l]


def _count_pattern(lines: list[str], pattern: str) -> int:
    return sum(1 for l in lines if pattern in l)


def _has_errors(lines: list[str]) -> bool:
    error_signals = ["Traceback", "Error:", "Exception:", "CRITICAL", "FATAL"]
    return any(any(s in l for s in error_signals) for l in lines)


# ── Stats collection ───────────────────────────────────────────────────────────

def build_report() -> dict:
    """Collect raw stats from all log sources. Returns a stats dict."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Worker stats
    worker_lines   = _tail(WORKER_OUT)
    queued_today   = _count_pattern(_today_lines(worker_lines), "Queued:")
    queued_total   = _count_pattern(worker_lines, "Queued:")

    # Memory worker
    memory_lines   = _tail(MEMORY_OUT)
    logged_today   = _count_pattern(_today_lines(memory_lines), "Logged to memory:")

    # State worker
    state_lines    = _tail(STATE_OUT)
    state_updates  = _count_pattern(state_lines, "State updated:")

    # Listener errors
    listener_lines = _tail(LISTENER_OUT)
    listener_errors = _has_errors(listener_lines)

    # Billing
    billing_lines  = _tail(BILLING_OUT)
    billing_completions = _count_pattern(billing_lines, "capture complete")

    # Input log (total messages today)
    input_lines    = _tail(INPUT_LOG, 500)
    messages_today = len(_today_lines(input_lines))

    # Watcher state
    watcher_alerts = []
    watcher_alert_count = 0
    try:
        if WATCHER_STATE.exists():
            ws = json.loads(WATCHER_STATE.read_text(encoding="utf-8"))
            keys = ws.get("sent_alert_keys", [])
            watcher_alert_count = len(keys)
            # Extract readable summaries from keys (format: "type|field1|field2...")
            for key in keys[-5:]:  # last 5 keys as samples
                parts = key.split("|")
                if parts:
                    watcher_alerts.append(parts[0].replace("_", " "))
    except Exception:
        pass

    return {
        "date":                 today,
        "generated_at":         datetime.now().strftime("%Y-%m-%d %H:%M"),
        "messages_today":       messages_today,
        "queued_today":         queued_today,
        "queued_total":         queued_total,
        "logged_today":         logged_today,
        "state_updates":        state_updates,
        "listener_errors":      listener_errors,
        "billing_completions":  billing_completions,
        "watcher_alert_count":  watcher_alert_count,
        "watcher_alert_samples": watcher_alerts,
    }


# ── Report formatting ──────────────────────────────────────────────────────────

_FORMAT_PROMPT = """\
You are summarizing system activity for an independent artist's AI assistant called OpenClaw.

Here are the raw stats for {date}:
- Incoming Telegram messages today: {messages_today}
- Messages queued by worker: {queued_today} (today) / {queued_total} total in log
- Items logged to memory: {logged_today}
- State updates written: {state_updates}
- Listener errors detected: {listener_errors}
- Billing sessions completed: {billing_completions}
- Watcher alerts on record: {watcher_alert_count}
- Recent alert types: {watcher_alert_samples}

Write a short, readable daily digest in this format:
📊 OpenClaw — {date}

Workers
  [2-3 bullet points about worker activity]

Watcher
  [1-2 bullet points about alerts]

Sessions
  [billing and general activity]

System health
  [one line: all good, or what needs attention]

Keep it under 400 characters total. Be direct and factual. No filler."""


def format_report(stats: dict) -> str:
    """Use LLM to format stats into a readable digest. Falls back to plain template."""
    prompt = _FORMAT_PROMPT.format(
        date=stats["date"],
        messages_today=stats["messages_today"],
        queued_today=stats["queued_today"],
        queued_total=stats["queued_total"],
        logged_today=stats["logged_today"],
        state_updates=stats["state_updates"],
        listener_errors="Yes — check listener.out" if stats["listener_errors"] else "None",
        billing_completions=stats["billing_completions"],
        watcher_alert_count=stats["watcher_alert_count"],
        watcher_alert_samples=", ".join(stats["watcher_alert_samples"]) or "none",
    )
    result = ollama_call(prompt, timeout=30).strip()
    if result:
        return result

    # Plain-text fallback if LLM unavailable
    alerts = stats["watcher_alert_count"]
    errors = "⚠️ Errors detected — check listener.out" if stats["listener_errors"] else "✓ No errors"
    return (
        f"📊 OpenClaw — {stats['date']}\n\n"
        f"Workers\n"
        f"  • {stats['queued_today']} messages queued today\n"
        f"  • {stats['logged_today']} items logged to memory\n"
        f"  • {stats['state_updates']} state updates written\n\n"
        f"Watcher\n"
        f"  • {alerts} alert(s) on record\n\n"
        f"Sessions\n"
        f"  • {stats['messages_today']} incoming messages today\n"
        f"  • {stats['billing_completions']} billing session(s) completed\n\n"
        f"System health\n"
        f"  • {errors}"
    )


# ── Vault sync ─────────────────────────────────────────────────────────────────

def _write_vault_report(report_text: str, stats: dict) -> None:
    today = stats["date"]
    generated = stats["generated_at"]
    content = (
        "---\n"
        "type: daily-report\n"
        f"date: {today}\n"
        f"generated: {generated}\n"
        "---\n\n"
        f"# Daily Report — {today}\n\n"
        f"_Generated at {generated} by `chief_reporter_brain.py`_\n\n"
        + report_text
    )
    VAULT_REPORT.write_text(content, encoding="utf-8")


# ── Public entry point ─────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    """Generate and return the system report. Saves to vault."""
    stats  = build_report()
    report = format_report(stats)
    _write_vault_report(report, stats)
    return [report]


# ── CLI / smoke test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating report...\n")
    for line in handle():
        print(line)
    print(f"\nVault report written to: {VAULT_REPORT}")

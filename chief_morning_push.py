"""
chief_morning_push.py

Morning briefing push to Winship via Telegram.
Runs daily at 7am via cron. Sends once per day (sentinel guard).

Covers:
  - Sentry countdown
  - Income last 24h
  - Album progress
  - Overdue invoices
"""

import csv
import json
import os
import sys
from datetime import datetime, date
from pathlib import Path

# Load env if not already set (standalone cron execution)
_env_file = Path("/home/openclaw/.chief.env")
if _env_file.exists() and "CHIEF_BOT_TOKEN" not in os.environ:
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line.startswith("export "):
            _line = _line[7:]
        if "=" in _line and not _line.startswith("#"):
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

SENTINEL_DIR  = Path("/mnt/c/OpenClaw/logs")
GATE_FILE     = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Sentry_Gate.json")
ALBUM_CSV     = Path("/mnt/c/OpenClawShared/album/album_work_log.csv")
INVOICE_CSV   = Path("/mnt/c/OpenClaw/billing/tracker/invoice_tracker.csv")


def _sentinel_path() -> Path:
    return SENTINEL_DIR / f"morning_push_sent_{date.today().isoformat()}.txt"


def _sentry_line() -> str:
    try:
        if not GATE_FILE.exists():
            return "Manus trial: status unknown."
        gate = json.loads(GATE_FILE.read_text())
        ts = gate.get("target_timestamp")
        if not ts:
            return "Manus trial: not configured."
        delta = datetime.fromisoformat(ts) - datetime.now()
        total_h = delta.total_seconds() / 3600
        if total_h <= 0:
            return "Manus trial: EXPIRED."
        days = int(total_h // 24)
        hours = int(total_h % 24)
        if gate.get("cancel_required"):
            return f"Manus trial: CANCEL REQUIRED — {days}d {hours}h remaining."
        elif gate.get("authorized_to_pay"):
            return f"Manus trial: {days}d {hours}h remaining (charge authorized)."
        else:
            return f"Manus trial: {days}d {hours}h remaining."
    except Exception:
        return "Manus trial: could not read status."


def _income_line() -> str:
    try:
        sys.path.insert(0, "/home/openclaw")
        from chief_cpa_brain import get_recent_income
        entries = get_recent_income(days=1)
        if not entries:
            return "Income last 24h: none logged."
        total = sum(float(e.get("amount", 0)) for e in entries)
        return f"Income last 24h: ${total:.0f} across {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}."
    except Exception:
        return "Income last 24h: could not read."


def _album_line() -> str:
    try:
        if not ALBUM_CSV.exists():
            return "Album: data unavailable."
        complete = 0
        with open(ALBUM_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    if float(row.get("completion_pct", 0)) >= 80:
                        complete += 1
                except (ValueError, TypeError):
                    pass
        return f"Album: {complete} of 12 songs at 80 percent or more."
    except Exception:
        return "Album: could not read."


def _invoice_line() -> str:
    try:
        if not INVOICE_CSV.exists():
            return "Invoices: data unavailable."
        today = date.today()
        overdue = 0
        with open(INVOICE_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("payment_status", "").lower() in ("paid", ""):
                    continue
                due_str = row.get("due_date", "").strip()
                if not due_str or due_str.lower() in ("due on receipt", "n/a", ""):
                    continue
                try:
                    due = datetime.strptime(due_str, "%Y-%m-%d").date()
                    if due < today:
                        overdue += 1
                except ValueError:
                    pass
        if overdue == 0:
            return "Invoices: none overdue."
        return f"Invoices: {overdue} overdue."
    except Exception:
        return "Invoices: could not read."


def main():
    sentinel = _sentinel_path()
    if sentinel.exists():
        return  # already sent today

    lines = [
        "Morning briefing.",
        _sentry_line(),
        _income_line(),
        _album_line(),
        _invoice_line(),
    ]
    msg = " ".join(lines)

    from chief_sender import send_message
    send_message(msg)

    SENTINEL_DIR.mkdir(parents=True, exist_ok=True)
    sentinel.write_text(f"sent at {datetime.now().isoformat()}\n")


if __name__ == "__main__":
    main()

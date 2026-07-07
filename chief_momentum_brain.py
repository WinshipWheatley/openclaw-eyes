"""
chief_momentum_brain.py

Activity pattern watcher. Reads message logs and billing/album activity to
detect idle periods, measure artist-mode vs admin-mode ratio, and surface
momentum signals.

- Artist mode: album updates, fundo sessions, recording activity
- Admin mode: billing, invoices, email/sms comms, phone logs
- Idle: no activity in >72h

Triggered by:
  - "momentum" / "am i on track" / "activity check" / "how active am i"
  - "artist mode" / "am i in admin mode"
Intent: momentum_check in chief_router.py

Saves to:
  - openclaw-vault/System/Momentum Report.md
"""

import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from adaptive_model_call import adaptive_ollama_text

ollama_call = adaptive_ollama_text

def _local_model_call(*args, **kwargs):
    return globals()["ollama_call"](*args, **kwargs)

# ── Paths ─────────────────────────────────────────────────────────────────────

CHIEF_INPUT_LOG = Path("/mnt/c/OpenClaw/logs/chief_input.log")
ALBUM_SESSION   = Path("/mnt/c/OpenClaw/logs/chief_album_session.json")
BILLING_JSONL   = Path("/home/openclaw/OpenClaw/exports/billing_records.jsonl")
QUEUE_LOG       = Path("/mnt/c/OpenClaw/logs/claude_queue.log")

MOMENTUM_MD = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Momentum Report.md")

# ── Keyword classifiers ───────────────────────────────────────────────────────

ARTIST_KEYWORDS = [
    "song", "album", "mix", "track", "vocal", "fundo", "session",
    "studio", "record", "produce", "beat", "loop", "sample",
    "arc", "album update", "completion",
]

ADMIN_KEYWORDS = [
    "invoice", "billing", "payment", "email", "sms", "phone", "call",
    "log call", "send email", "text", "follow up", "receipt",
    "cpa", "tax", "publishing", "contract",
]

SYSTEM_KEYWORDS = [
    "trinity", "analytics", "goals", "momentum", "queue", "calendar",
    "inspect", "report", "system audit", "brain audit",
]


def _classify_line(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ARTIST_KEYWORDS):
        return "artist"
    if any(k in t for k in ADMIN_KEYWORDS):
        return "admin"
    if any(k in t for k in SYSTEM_KEYWORDS):
        return "system"
    return "other"


# ── Log parser ────────────────────────────────────────────────────────────────

def _parse_input_log(days_back: int = 30) -> list[dict]:
    """Parse chief_input.log → list of {ts, text, mode}."""
    if not CHIEF_INPUT_LOG.exists():
        return []

    cutoff = datetime.now() - timedelta(days=days_back)
    entries = []

    for line in CHIEF_INPUT_LOG.read_text(encoding="utf-8").splitlines():
        m = re.search(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]\s+(.*)", line)
        if not m:
            continue
        try:
            ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        if ts < cutoff:
            continue
        text = m.group(2).strip()
        mode = _classify_line(text)
        entries.append({"ts": ts, "text": text, "mode": mode})

    return entries


# ── Metrics ───────────────────────────────────────────────────────────────────

def _compute_metrics(entries: list[dict]) -> dict:
    now = datetime.now()
    week_ago = now - timedelta(days=7)

    # Last activity timestamp
    if entries:
        last_ts = max(e["ts"] for e in entries)
        idle_hours = (now - last_ts).total_seconds() / 3600
    else:
        last_ts = None
        idle_hours = float("inf")

    # Mode counts — last 7 days
    week_entries = [e for e in entries if e["ts"] >= week_ago]
    mode_counts: dict[str, int] = defaultdict(int)
    for e in week_entries:
        mode_counts[e["mode"]] += 1

    artist_count = mode_counts["artist"]
    admin_count  = mode_counts["admin"]
    system_count = mode_counts["system"]
    other_count  = mode_counts["other"]
    total_week   = len(week_entries)

    if total_week > 0:
        artist_pct = round(artist_count / total_week * 100)
        admin_pct  = round(admin_count / total_week * 100)
    else:
        artist_pct = admin_pct = 0

    # Daily activity pattern — last 7 days
    daily: dict[str, int] = defaultdict(int)
    for e in week_entries:
        day = e["ts"].strftime("%Y-%m-%d")
        daily[day] += 1

    # Streak: consecutive days with activity
    streak = 0
    day = now.date()
    while True:
        if daily.get(day.strftime("%Y-%m-%d"), 0) > 0:
            streak += 1
            day -= timedelta(days=1)
        else:
            break

    # Peak activity hour
    hours: dict[int, int] = defaultdict(int)
    for e in week_entries:
        hours[e["ts"].hour] += 1
    peak_hour = max(hours, key=lambda h: hours[h]) if hours else None

    return {
        "last_activity": last_ts,
        "idle_hours": idle_hours,
        "total_week": total_week,
        "artist_count": artist_count,
        "admin_count": admin_count,
        "system_count": system_count,
        "artist_pct": artist_pct,
        "admin_pct": admin_pct,
        "streak_days": streak,
        "peak_hour": peak_hour,
        "daily": dict(daily),
    }


# ── Report builder ────────────────────────────────────────────────────────────

def _idle_flag(hours: float) -> str:
    if hours < 24:
        return "active"
    if hours < 48:
        return "quiet (>24h)"
    if hours < 72:
        return "slow (>48h)"
    return "⚠ idle (>72h)"


def _build_report(m: dict) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"**Momentum Report — {today}**\n"]

    last = m["last_activity"].strftime("%Y-%m-%d %H:%M") if m["last_activity"] else "no data"
    lines.append(f"Last activity: {last} ({_idle_flag(m['idle_hours'])})")
    lines.append(f"Active streak: {m['streak_days']} day(s)")

    if m["peak_hour"] is not None:
        hour_str = f"{m['peak_hour']:02d}:00"
        lines.append(f"Peak hour: {hour_str}")

    lines.append("")
    lines.append(f"This week: {m['total_week']} messages")
    lines.append(f"  Artist mode: {m['artist_count']} ({m['artist_pct']}%)")
    lines.append(f"  Admin mode:  {m['admin_count']} ({m['admin_pct']}%)")
    lines.append(f"  System:      {m['system_count']}")

    # Artist/admin balance signal
    if m["total_week"] > 0:
        if m["artist_pct"] >= 50:
            lines.append("\n✓ You're in artist mode.")
        elif m["admin_pct"] >= 50:
            lines.append("\n⚠ Heavy admin week. Create something.")
        else:
            lines.append("\nBalanced week.")

    return "\n".join(lines)


# ── LLM narrative ─────────────────────────────────────────────────────────────

_NARRATIVE_PROMPT = """\
You are coaching a music producer/artist on their work patterns.

Here is this week's activity summary:

{report}

Write 2-3 sentences:
- Comment on their momentum honestly
- If they're idle or in heavy admin mode, call it out directly
- Give one specific recommendation for what to do next

Be direct. No bullet points. No headers."""


def _build_narrative(report: str) -> str:
    prompt = _NARRATIVE_PROMPT.format(report=report)
    result = _local_model_call(prompt, timeout=30, lane="strong").strip()
    return result if result else ""


# ── Vault write ───────────────────────────────────────────────────────────────

def _write_momentum_md(report: str, narrative: str) -> None:
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = (
        "---\n"
        "type: momentum-report\n"
        f"last_updated: {today}\n"
        "---\n\n"
        "# Momentum Report\n\n"
        "_Managed by `chief_momentum_brain.py`. Say 'momentum' to refresh._\n\n"
    )
    if narrative:
        content += f"## Summary\n\n{narrative}\n\n"
    content += "## Activity\n\n" + report.replace("**", "").strip() + "\n"
    MOMENTUM_MD.parent.mkdir(parents=True, exist_ok=True)
    MOMENTUM_MD.write_text(content, encoding="utf-8")


# ── Public entry point ────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    entries = _parse_input_log(days_back=30)
    metrics = _compute_metrics(entries)
    report = _build_report(metrics)
    narrative = _build_narrative(report)
    _write_momentum_md(report, narrative)

    parts = []
    if narrative:
        parts.append(narrative + "\n")
    parts.append(report)
    parts.append("\nMomentum report saved to vault/System/Momentum Report.md")

    return ["\n".join(parts)]


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    for line in handle():
        print(line)

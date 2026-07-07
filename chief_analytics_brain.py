"""
chief_analytics_brain.py

Cross-domain metrics dashboard. Covers album progress, content pipeline,
and bot activity. Does NOT handle financial data — that belongs to
chief_financial_brain.py (Finance Operations domain).

Triggered by:
  - "analytics" / "weekly metrics" / "metrics report" / "show analytics"
Intent: analytics_report in chief_router.py

Saves to:
  - openclaw-vault/System/Analytics Report.md
"""

import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from adaptive_model_call import adaptive_ollama_text

ollama_call = adaptive_ollama_text

def _local_model_call(*args, **kwargs):
    return globals()["ollama_call"](*args, **kwargs)

# ── Paths ─────────────────────────────────────────────────────────────────────

BILLING_CSV      = Path("/home/openclaw/OpenClaw/exports/billing_records.csv")
BILLING_JSONL    = Path("/home/openclaw/OpenClaw/exports/billing_records.jsonl")
ALBUM_CSV        = Path("/mnt/c/OpenClawShared/album/album_work_log.csv")
CONTENT_LOG_JSON = Path("/mnt/c/OpenClawShared/album/content_log.json")
QUEUE_LOG        = Path("/mnt/c/OpenClaw/logs/claude_queue.log")
CHIEF_INPUT_LOG  = Path("/mnt/c/OpenClaw/logs/chief_input.log")

VAULT_REPORT = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Analytics Report.md")

# ── Financial metrics ─────────────────────────────────────────────────────────

def _load_billing() -> list[dict]:
    records = []
    if BILLING_JSONL.exists():
        for line in BILLING_JSONL.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
    elif BILLING_CSV.exists():
        with BILLING_CSV.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                records.append(row)
    return records


def _financial_metrics(records: list[dict]) -> dict:
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    ytd_start = datetime(now.year, 1, 1)

    totals = {"week": 0.0, "month": 0.0, "ytd": 0.0, "all_time": 0.0}
    invoice_count = {"week": 0, "month": 0, "ytd": 0}
    types: dict[str, float] = defaultdict(float)

    for r in records:
        # Determine record type and amount
        record_type = r.get("record_type", r.get("type", "")).upper()
        if record_type in ("PAYMENT", "RECEIPT"):
            try:
                amount = float(r.get("payment_amount") or r.get("amount_received") or 0)
            except (ValueError, TypeError):
                amount = 0.0
        elif record_type == "INVOICE":
            try:
                amount = float(r.get("amount_total") or 0)
            except (ValueError, TypeError):
                amount = 0.0
        else:
            amount = 0.0

        # Parse date
        date_str = r.get("service_date") or r.get("payment_date") or r.get("date_created", "")
        try:
            if date_str:
                date = datetime.strptime(date_str[:10], "%Y-%m-%d")
            else:
                continue
        except ValueError:
            continue

        totals["all_time"] += amount
        if date >= ytd_start:
            totals["ytd"] += amount
        if date >= month_ago:
            totals["month"] += amount
        if date >= week_ago:
            totals["week"] += amount

        if record_type == "INVOICE":
            if date >= ytd_start:
                invoice_count["ytd"] += 1
            if date >= month_ago:
                invoice_count["month"] += 1
            if date >= week_ago:
                invoice_count["week"] += 1

        project = r.get("project_or_event", "Other")
        types[project] += amount

    top_projects = sorted(types.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "income_week": totals["week"],
        "income_month": totals["month"],
        "income_ytd": totals["ytd"],
        "income_all_time": totals["all_time"],
        "invoices_week": invoice_count["week"],
        "invoices_month": invoice_count["month"],
        "invoices_ytd": invoice_count["ytd"],
        "top_projects": top_projects,
        "record_count": len(records),
    }


# ── Album metrics ─────────────────────────────────────────────────────────────

def _album_metrics() -> dict:
    if not ALBUM_CSV.exists():
        return {}

    songs = []
    with ALBUM_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            title = row.get("song_title", "").strip()
            if not title:
                continue
            try:
                pct = int(row.get("completion_pct", "0").strip() or "0")
            except ValueError:
                pct = 0
            locked = str(row.get("version_locked", "")).lower() in ("yes", "true", "locked")
            rerecord = str(row.get("needs_rerecord", "")).lower() in ("yes", "true")
            songs.append({"title": title, "pct": pct, "locked": locked, "rerecord": rerecord})

    if not songs:
        return {}

    total_songs = len(songs)
    avg_completion = sum(s["pct"] for s in songs) / total_songs
    locked_count = sum(1 for s in songs if s["locked"])
    rerecord_count = sum(1 for s in songs if s["rerecord"])
    near_ready = sum(1 for s in songs if s["pct"] >= 70)
    complete = sum(1 for s in songs if s["pct"] >= 100)

    return {
        "total_songs": total_songs,
        "avg_completion": round(avg_completion, 1),
        "locked": locked_count,
        "near_ready": near_ready,
        "complete": complete,
        "rerecord_needed": rerecord_count,
    }


# ── Content metrics ───────────────────────────────────────────────────────────

def _content_metrics() -> dict:
    if not CONTENT_LOG_JSON.exists():
        return {}
    try:
        data = json.loads(CONTENT_LOG_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}
    entries = data.get("entries", [])
    return {
        "total": len(entries),
        "in_progress": sum(1 for e in entries if e.get("status") == "in_progress"),
        "suggested": sum(1 for e in entries if e.get("status") == "suggested"),
        "posted": sum(1 for e in entries if e.get("status") == "posted"),
    }


# ── Activity metrics ──────────────────────────────────────────────────────────

def _activity_metrics() -> dict:
    """Count messages from chief_input.log in last 7 and 30 days."""
    if not CHIEF_INPUT_LOG.exists():
        return {}

    now = datetime.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    week_count = 0
    month_count = 0

    for line in CHIEF_INPUT_LOG.read_text(encoding="utf-8").splitlines():
        # Format: [PHONE][2026-03-17 14:23] text
        import re
        m = re.search(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]", line)
        if not m:
            continue
        try:
            ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        if ts >= month_ago:
            month_count += 1
        if ts >= week_ago:
            week_count += 1

    return {"messages_week": week_count, "messages_month": month_count}


# ── Report builder ────────────────────────────────────────────────────────────

def _fmt_money(amount: float) -> str:
    return f"${amount:,.2f}"


def _build_report(fin: dict, album: dict, content: dict, activity: dict) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"**Analytics Report — {today}**\n"]

    # Financial
    if fin.get("record_count", 0) > 0:
        lines.append("**Financial**")
        lines.append(f"  This week:  {_fmt_money(fin['income_week'])} ({fin['invoices_week']} invoices)")
        lines.append(f"  This month: {_fmt_money(fin['income_month'])} ({fin['invoices_month']} invoices)")
        lines.append(f"  YTD:        {_fmt_money(fin['income_ytd'])} ({fin['invoices_ytd']} invoices)")
        if fin["top_projects"]:
            lines.append("  Top projects:")
            for proj, amt in fin["top_projects"]:
                lines.append(f"    {proj}: {_fmt_money(amt)}")
    else:
        lines.append("**Financial** — no billing records yet")

    lines.append("")

    # Album
    if album:
        lines.append("**Album Progress**")
        lines.append(f"  Songs: {album['total_songs']} | Avg completion: {album['avg_completion']}%")
        lines.append(f"  Near ready (≥70%): {album['near_ready']} | Locked: {album['locked']} | Complete: {album['complete']}")
        if album["rerecord_needed"]:
            lines.append(f"  ⚠ Needs re-record: {album['rerecord_needed']}")
    else:
        lines.append("**Album Progress** — no data")

    lines.append("")

    # Content
    if content:
        lines.append("**Content Pipeline**")
        lines.append(f"  Total: {content['total']} | In progress: {content['in_progress']} | Suggested: {content['suggested']} | Posted: {content['posted']}")
    else:
        lines.append("**Content Pipeline** — no data")

    lines.append("")

    # Activity
    if activity:
        lines.append("**Bot Activity**")
        lines.append(f"  Messages — this week: {activity['messages_week']} | this month: {activity['messages_month']}")

    return "\n".join(lines)


# ── LLM narrative ─────────────────────────────────────────────────────────────

_NARRATIVE_PROMPT = """\
You are the analytics voice for OpenClaw, a music production business.

Here is this week's data summary:

{report}

Write a 3-4 sentence business narrative:
- Lead with the most important number or trend
- Note what's moving in the right direction
- Flag anything that needs attention

Be direct. No bullet points. No markdown headers. Sound like a sharp business advisor."""


def _build_narrative(report: str) -> str:
    prompt = _NARRATIVE_PROMPT.format(report=report)
    result = _local_model_call(prompt, timeout=30, lane="strong").strip()
    return result if result else ""


# ── Vault write ───────────────────────────────────────────────────────────────

def _write_report(report: str, narrative: str) -> None:
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = (
        "---\n"
        "type: analytics-report\n"
        f"last_updated: {today}\n"
        "---\n\n"
        "# Analytics Report\n\n"
        "_Managed by `chief_analytics_brain.py`. Run 'weekly metrics' to refresh._\n\n"
    )
    if narrative:
        content += f"## Summary\n\n{narrative}\n\n"
    content += "## Metrics\n\n" + report.replace("**", "").strip() + "\n"
    VAULT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    VAULT_REPORT.write_text(content, encoding="utf-8")


# ── Public entry point ────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    records = _load_billing()
    fin = _financial_metrics(records)
    album = _album_metrics()
    content = _content_metrics()
    activity = _activity_metrics()

    report = _build_report(fin, album, content, activity)
    narrative = _build_narrative(report)
    _write_report(report, narrative)

    reply_parts = [report]
    if narrative:
        reply_parts.insert(0, narrative + "\n")
    reply_parts.append("\nFull report saved to vault/System/Analytics Report.md")

    return ["\n".join(reply_parts)]


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    for line in handle():
        print(line)

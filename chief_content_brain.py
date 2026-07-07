"""
chief_content_brain.py

Content calendar and scheduling brain. Knows what's been posted, what's
queued, what platforms need content, and when things are due. Works
alongside chief_marketing_brain.py — marketing generates ideas and drafts,
content_brain manages the calendar and scheduling logic.

Triggered by:
  - "content calendar" / "content schedule" / "what's due for posting"
  - "content status" / "posting schedule" / "what needs to go up"
  - "schedule post [platform] [date]" / "mark posted [id]"
Intent: content_calendar in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/album/content_log.json  (source of truth — shared)
  - openclaw-vault/Marketing/Content Calendar.md
"""

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from adaptive_model_call import adaptive_ollama_text

ollama_call = adaptive_ollama_text

def _local_model_call(*args, **kwargs):
    return globals()["ollama_call"](*args, **kwargs)

# ── Paths ─────────────────────────────────────────────────────────────────────

CONTENT_LOG_JSON = Path("/mnt/c/OpenClawShared/album/content_log.json")
CONTENT_CAL_MD   = Path("/mnt/c/OpenClawShared/openclaw-vault/Marketing/Content Calendar.md")

# ── Platform posting cadence targets ─────────────────────────────────────────

PLATFORM_TARGETS = {
    "Instagram": 3,   # posts per week
    "TikTok":    3,
    "YouTube":   1,
    "Twitter":   5,
    "Facebook":  2,
}

# ── Storage ───────────────────────────────────────────────────────────────────

def _load() -> dict:
    if CONTENT_LOG_JSON.exists():
        try:
            return json.loads(CONTENT_LOG_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"entries": []}


def _save(data: dict) -> None:
    CONTENT_LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    CONTENT_LOG_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Calendar logic ────────────────────────────────────────────────────────────

def _platform_summary(entries: list[dict]) -> dict:
    """Count posts per platform in the last 7 days."""
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    counts: dict[str, int] = defaultdict(int)
    for e in entries:
        if e.get("status") == "posted":
            date = e.get("date_posted") or ""
            if date >= week_ago:
                platform = e.get("platform", "Unknown")
                counts[platform] += 1
    return dict(counts)


def _overdue_platforms(counts: dict) -> list[str]:
    """Platforms that are below target cadence."""
    overdue = []
    for platform, target in PLATFORM_TARGETS.items():
        current = counts.get(platform, 0)
        if current < target:
            overdue.append(f"{platform} ({current}/{target} this week)")
    return overdue


def _upcoming_suggested(entries: list[dict], days: int = 14) -> list[dict]:
    """Return suggested/in-progress items, sorted by date_suggested."""
    now_str = datetime.now().strftime("%Y-%m-%d")
    cutoff  = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    items = [
        e for e in entries
        if e.get("status") in ("suggested", "in_progress")
    ]
    return sorted(items, key=lambda x: x.get("date_suggested", ""), reverse=True)[:10]


# ── Schedule update ───────────────────────────────────────────────────────────

def _mark_posted(entry_id: str, date: str | None = None) -> tuple[bool, str]:
    data = _load()
    entries = data.get("entries", [])
    for e in entries:
        if e.get("id", "").lower() == entry_id.lower():
            e["status"] = "posted"
            e["date_posted"] = date or datetime.now().strftime("%Y-%m-%d")
            _save(data)
            _write_calendar_md(data)
            return True, e.get("title", entry_id)
    return False, entry_id


def _schedule_post(entry_id: str, platform: str, date: str) -> tuple[bool, str]:
    data = _load()
    for e in data.get("entries", []):
        if e.get("id", "").lower() == entry_id.lower():
            e["platform"] = platform
            e["scheduled_date"] = date
            e["status"] = "in_progress"
            _save(data)
            return True, e.get("title", entry_id)
    return False, entry_id


# ── LLM posting recommendation ────────────────────────────────────────────────

_RECOMMENDATION_PROMPT = """\
You manage the social media content calendar for DPR Music / Fundo, a music production brand.

Content queue (suggested/in-progress):
{queue_items}

Platforms behind target this week:
{overdue}

Write a 2-3 sentence posting recommendation:
- Which item should go up first and on which platform
- Any quick win that would help the most behind platforms
- Keep it practical and specific

Be direct. No bullet points."""


def _get_recommendation(queue: list[dict], overdue: list[str]) -> str:
    if not queue and not overdue:
        return ""
    queue_str = "\n".join(f"- [{e.get('platform','')}] {e.get('title','')} ({e.get('size','')})" for e in queue[:5]) or "none"
    overdue_str = "\n".join(f"- {o}" for o in overdue) or "none"
    prompt = _RECOMMENDATION_PROMPT.format(queue_items=queue_str, overdue=overdue_str)
    try:
        result = _local_model_call(prompt, timeout=20, task_class="chief_structured_plan").strip()
    except Exception:
        result = ""
    return result if _usable_recommendation(result) else _fallback_recommendation(queue, overdue)


def _usable_recommendation(text: str) -> bool:
    stripped = (text or "").strip()
    return len(stripped.split()) >= 2 and stripped.lower() not in {"ok", "n/a", "none", "unknown"}


def _fallback_recommendation(queue: list[dict], overdue: list[str]) -> str:
    first = queue[0] if queue else {}
    if first:
        platform = first.get("platform") or (overdue[0].split(" (", 1)[0] if overdue else "the most behind platform")
        title = first.get("title") or "the first queued item"
        return f"Post or schedule '{title}' next on {platform}. Then cover {overdue[0] if overdue else 'the next behind platform'} with a quick process clip."
    return f"Prioritize the most behind platform first: {overdue[0]}. Make one quick, low-lift post today."


# ── Vault write ───────────────────────────────────────────────────────────────

def _write_calendar_md(data: dict) -> None:
    entries  = data.get("entries", [])
    today    = datetime.now().strftime("%Y-%m-%d %H:%M")

    in_progress = [e for e in entries if e.get("status") == "in_progress"]
    suggested   = [e for e in entries if e.get("status") == "suggested"]
    posted      = sorted(
        [e for e in entries if e.get("status") == "posted"],
        key=lambda x: x.get("date_posted") or "",
        reverse=True,
    )[:10]

    def table_rows(items: list[dict]) -> str:
        if not items:
            return "| — | — | — | — | — |\n"
        rows = []
        for e in items:
            date_col = e.get("date_posted") or e.get("scheduled_date") or e.get("date_suggested", "—")
            rows.append(
                f"| {e.get('id','—')} "
                f"| {e.get('title','—')} "
                f"| {e.get('platform','—')} "
                f"| {e.get('song') or '—'} "
                f"| {date_col} |"
            )
        return "\n".join(rows) + "\n"

    header = "| ID | Title | Platform | Song | Date |\n|---|---|---|---|---|\n"

    counts = _platform_summary(entries)
    overdue = _overdue_platforms(counts)

    platform_rows = "\n".join(
        f"| {p} | {counts.get(p, 0)}/{t} | {'✓' if counts.get(p, 0) >= t else '⚠'} |"
        for p, t in PLATFORM_TARGETS.items()
    )

    content = (
        "---\n"
        "type: content-calendar\n"
        f"last_updated: {today}\n"
        "---\n\n"
        "# Content Calendar\n\n"
        "_Managed by `chief_content_brain.py`._\n\n"
        "## Platform Cadence (this week)\n\n"
        "| Platform | Posted | Target |\n|---|---|---|\n"
        + platform_rows + "\n\n"
        "## In Progress\n\n"
        + header + table_rows(in_progress)
        + "\n## Suggested\n\n"
        + header + table_rows(suggested)
        + "\n## Recently Posted (last 10)\n\n"
        + header + table_rows(posted)
    )
    CONTENT_CAL_MD.parent.mkdir(parents=True, exist_ok=True)
    CONTENT_CAL_MD.write_text(content, encoding="utf-8")


# ── Handlers ──────────────────────────────────────────────────────────────────

def _handle_status() -> list[str]:
    data    = _load()
    entries = data.get("entries", [])
    counts  = _platform_summary(entries)
    overdue = _overdue_platforms(counts)
    queue   = _upcoming_suggested(entries)

    recommendation = _get_recommendation(queue, overdue)
    _write_calendar_md(data)

    in_prog  = sum(1 for e in entries if e.get("status") == "in_progress")
    suggested = sum(1 for e in entries if e.get("status") == "suggested")
    posted   = sum(1 for e in entries if e.get("status") == "posted")

    lines = [
        f"**Content Calendar**\n",
        f"Queue: {in_prog} in-progress | {suggested} suggested | {posted} posted",
    ]

    if overdue:
        lines.append(f"\nPlatforms behind target:")
        for o in overdue:
            lines.append(f"  ⚠ {o}")

    if queue:
        lines.append(f"\nNext up:")
        for e in queue[:5]:
            lines.append(f"  • [{e.get('platform','')}] {e.get('title','')} ({e.get('size','')})")

    if recommendation:
        lines.append(f"\n{recommendation}")

    lines.append("\nCalendar saved to vault/Marketing/Content Calendar.md")
    lines.append("Say 'mark posted [id]' or 'schedule post [id] [platform] [date]' to update.")
    return ["\n".join(lines)]


def _handle_mark_posted(text: str) -> list[str]:
    m = re.search(r"mark\s+posted\s+(\S+)", text, re.IGNORECASE)
    if not m:
        return ["Format: 'mark posted [id]'. Find the ID in the content calendar."]
    entry_id = m.group(1)
    ok, title = _mark_posted(entry_id)
    if ok:
        return [f"Marked as posted: {title} ({entry_id})"]
    return [f"No entry found with ID '{entry_id}'. Check 'content calendar' for IDs."]


def _handle_schedule(text: str) -> list[str]:
    m = re.search(r"schedule\s+(?:post\s+)?(\S+)\s+(\w+)\s+(\S+)", text, re.IGNORECASE)
    if not m:
        return ["Format: 'schedule post [id] [platform] [date]'"]
    entry_id, platform, date = m.group(1), m.group(2), m.group(3)
    ok, title = _schedule_post(entry_id, platform, date)
    if ok:
        return [f"Scheduled: {title} on {platform} for {date}"]
    return [f"No entry found with ID '{entry_id}'."]


# ── Public entry point ────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t = text.lower().strip()

    if "mark posted" in t:
        return _handle_mark_posted(text)

    if "schedule post" in t or re.search(r"schedule\s+\S+\s+\w+\s+\d{4}", t):
        return _handle_schedule(text)

    return _handle_status()


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "content calendar"
    for line in handle(text):
        print(line)

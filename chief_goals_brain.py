"""
chief_goals_brain.py

Tracks 5 stated business/creative goals. Weekly check-in prompts progress
updates. Stores milestones and percent-complete. Shows trajectory toward
each goal over time.

Triggered by:
  - "goals" / "check in" / "goal check" / "how am i doing"
  - "set goal [text]" / "update goal [n]" / "goal progress"
Intent: goals_check in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/album/goals.json  (source of truth)
  - openclaw-vault/System/Goals.md
"""

import json
import re
from datetime import datetime
from pathlib import Path

from chief_llm import claude_call

# ── Paths ─────────────────────────────────────────────────────────────────────

GOALS_JSON = Path("/mnt/c/OpenClawShared/album/goals.json")
GOALS_MD   = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Goals.md")

# ── Default goals (editable via "set goal" command) ───────────────────────────

DEFAULT_GOALS = [
    {
        "id": 1,
        "title": "Release the album",
        "description": "Complete all 12 tracks, mix/master, and release through DistroKid",
        "target_date": "2026-12-31",
        "completion": 0,
        "milestones": [],
        "created": datetime.now().strftime("%Y-%m-%d"),
    },
    {
        "id": 2,
        "title": "Build Fundo brand",
        "description": "Establish Fundo as a recognizable Afrobeats artist — website, social, 3 tracks released",
        "target_date": "2026-12-31",
        "completion": 0,
        "milestones": [],
        "created": datetime.now().strftime("%Y-%m-%d"),
    },
    {
        "id": 3,
        "title": "Grow production income to $5k/month",
        "description": "Consistent monthly production revenue from gigs, sessions, and licensing",
        "target_date": "2026-12-31",
        "completion": 0,
        "milestones": [],
        "created": datetime.now().strftime("%Y-%m-%d"),
    },
    {
        "id": 4,
        "title": "Launch website",
        "description": "DPR Music website live with bio, music player, booking form, and Fundo teaser",
        "target_date": "2026-06-30",
        "completion": 0,
        "milestones": [],
        "created": datetime.now().strftime("%Y-%m-%d"),
    },
    {
        "id": 5,
        "title": "Complete OpenClaw AI system",
        "description": "All brain trilogies built and operational. Full automation of admin, comms, and reporting",
        "target_date": "2026-06-30",
        "completion": 0,
        "milestones": [],
        "created": datetime.now().strftime("%Y-%m-%d"),
    },
]


# ── Storage ───────────────────────────────────────────────────────────────────

def _load_goals() -> list[dict]:
    if GOALS_JSON.exists():
        try:
            return json.loads(GOALS_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Initialize with defaults
    _save_goals(DEFAULT_GOALS)
    return DEFAULT_GOALS


def _save_goals(goals: list[dict]) -> None:
    GOALS_JSON.parent.mkdir(parents=True, exist_ok=True)
    GOALS_JSON.write_text(json.dumps(goals, indent=2), encoding="utf-8")


def _write_goals_md(goals: list[dict]) -> None:
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    def progress_bar(pct: int) -> str:
        filled = pct // 10
        empty = 10 - filled
        return f"[{'█' * filled}{'░' * empty}] {pct}%"

    rows = "\n".join(
        f"| {g['id']} | {g['title']} | {progress_bar(g.get('completion', 0))} | {g.get('target_date', '—')} |"
        for g in goals
    )

    content = (
        "---\n"
        "type: goals\n"
        f"last_updated: {today}\n"
        "---\n\n"
        "# Goals\n\n"
        "_Managed by `chief_goals_brain.py`. Say 'goals' for a check-in._\n\n"
        "| # | Goal | Progress | Target |\n"
        "|---|---|---|---|\n"
        + rows + "\n\n"
    )

    for g in goals:
        content += f"## Goal {g['id']}: {g['title']}\n\n"
        content += f"**Target:** {g.get('target_date', '—')}\n\n"
        content += f"**Description:** {g.get('description', '')}\n\n"
        content += f"**Completion:** {g.get('completion', 0)}%\n\n"
        if g.get("milestones"):
            content += "**Milestones:**\n"
            for m in g["milestones"]:
                content += f"- [{m['date']}] {m['note']}\n"
            content += "\n"

    GOALS_MD.parent.mkdir(parents=True, exist_ok=True)
    GOALS_MD.write_text(content, encoding="utf-8")


# ── LLM check-in ──────────────────────────────────────────────────────────────

_CHECKIN_PROMPT = """\
You are reviewing an artist/producer's stated goals for the year.

Goals:
{goals_text}

Write a 2-3 sentence check-in:
- Acknowledge which goals are moving
- Note which one to focus on most right now based on target dates and completion
- End with one specific actionable suggestion

Be direct and motivating. No bullet points. No markdown headers."""


def _build_goals_text(goals: list[dict]) -> str:
    lines = []
    for g in goals:
        pct = g.get("completion", 0)
        lines.append(f"{g['id']}. {g['title']} — {pct}% complete (target: {g.get('target_date', 'open')})")
    return "\n".join(lines)


def _get_checkin(goals: list[dict]) -> str:
    goals_text = _build_goals_text(goals)
    prompt = _CHECKIN_PROMPT.format(goals_text=goals_text)
    result = claude_call(prompt, timeout=30).strip()
    return result if result else ""


# ── Handlers ──────────────────────────────────────────────────────────────────

def _handle_status(goals: list[dict]) -> list[str]:
    checkin = _get_checkin(goals)
    lines = ["**Goal Tracker**\n"]
    for g in goals:
        pct = g.get("completion", 0)
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        lines.append(f"  {g['id']}. {g['title']}")
        lines.append(f"     [{bar}] {pct}% | Target: {g.get('target_date', '—')}")
    if checkin:
        lines.append(f"\n{checkin}")
    lines.append("\nSay 'update goal [n] [pct]%' or 'milestone goal [n] [note]' to log progress.")
    return ["\n".join(lines)]


def _handle_update(text: str, goals: list[dict]) -> list[str]:
    """Update goal completion. 'update goal 3 60%' or 'goal 3 is at 40%'"""
    m = re.search(r"(?:goal\s+)?(\d)\D+(\d+)\s*%?", text, re.IGNORECASE)
    if not m:
        return ["Couldn't parse goal update. Try: 'update goal 3 60%'"]
    goal_id = int(m.group(1))
    pct = min(100, max(0, int(m.group(2))))
    for g in goals:
        if g["id"] == goal_id:
            old_pct = g.get("completion", 0)
            g["completion"] = pct
            _save_goals(goals)
            _write_goals_md(goals)
            return [f"Goal {goal_id} updated: {old_pct}% → {pct}%\n{g['title']}"]
    return [f"No goal #{goal_id}. Valid goals: 1-{len(goals)}"]


def _handle_milestone(text: str, goals: list[dict]) -> list[str]:
    """Log a milestone note. 'milestone goal 1 finished all vocals'"""
    m = re.search(r"(?:milestone\s+)?(?:goal\s+)?(\d)[^\w]+(.*)", text, re.IGNORECASE)
    if not m:
        return ["Couldn't parse milestone. Try: 'milestone goal 1 finished all vocals'"]
    goal_id = int(m.group(1))
    note = m.group(2).strip()
    if not note:
        return ["Include a note with the milestone."]
    for g in goals:
        if g["id"] == goal_id:
            if "milestones" not in g:
                g["milestones"] = []
            g["milestones"].append({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "note": note,
            })
            _save_goals(goals)
            _write_goals_md(goals)
            return [f"Milestone logged for Goal {goal_id}: {note}"]
    return [f"No goal #{goal_id}."]


def _handle_set(text: str, goals: list[dict]) -> list[str]:
    """Set/replace a goal. 'set goal 5 [new title]'"""
    m = re.search(r"set\s+goal\s+(\d)\s+(.*)", text, re.IGNORECASE)
    if not m:
        return ["Format: 'set goal [n] [new title]'. Goals are numbered 1-5."]
    goal_id = int(m.group(1))
    title = m.group(2).strip()
    for g in goals:
        if g["id"] == goal_id:
            old = g["title"]
            g["title"] = title
            g["description"] = title
            g["completion"] = 0
            g["milestones"] = []
            _save_goals(goals)
            _write_goals_md(goals)
            return [f"Goal {goal_id} replaced:\n  Was: {old}\n  Now: {title}"]
    return [f"No goal #{goal_id}."]


# ── Public entry point ────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    goals = _load_goals()
    t = text.lower().strip()

    if re.search(r"\bupdate\s+goal\b|\bgoal\s+\d\s+is\b|\bset\s+\w+\s+to\b", t):
        return _handle_update(text, goals)

    if "milestone" in t:
        return _handle_milestone(text, goals)

    if t.startswith("set goal"):
        return _handle_set(text, goals)

    # Default: show status with check-in
    _write_goals_md(goals)
    return _handle_status(goals)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "goals"
    for line in handle(text):
        print(line)

"""
cassandra_briefing_morning_context.py

Builds the morning context block for the 08:00 Cassandra briefing.

Four data sections — each has an explicit fallback if the source is unavailable:
  1. task_milestone  — polish loop archive count + queue depth
  2. financial       — recent income + structured finance state + payment follow-ups
  3. music           — album CSV completion summary
  4. surf_cue        — Ocean City, MD weather check → surf/golf/work directive

Public API
----------
  build_morning_briefing_context() -> str
      Assembled multi-section context block, ready to prepend to the morning briefing prompt.

  surf_directive() -> str
      One-word mode string: "surf", "golf", or "work".
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

import harness_context
from finance_state import build_finance_snapshot

# ── Paths ─────────────────────────────────────────────────────────────────────

_ARCHIVE_DIR   = Path("/home/openclaw/polish_loop/archive")
_QUEUE_DIR     = Path("/home/openclaw/polish_loop/tasks")
_ALBUM_CSV     = Path("/mnt/c/OpenClawShared/album/album_work_log.csv")
_OPS_PAYMENT   = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Ops Payment Follow-ups.md")
_LIFE_SYNC     = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Life Sync.md")
_REALITY_NOTES = Path("/home/openclaw/cassandra_reality_notes.json")

# Ocean City, MD — lat/lon for wttr.in surf/weather check
_OCEAN_CITY_QUERY = "38.3365,-75.0849"

# Wind thresholds (mph) for surf/golf/work directive
_SURF_WIND_MAX  = 12   # <= this → surf day possible
_GOLF_WIND_MAX  = 20   # <= this → golf window
# Above _GOLF_WIND_MAX → work mode


# ── Section 1: Task milestone ─────────────────────────────────────────────────

def _task_milestone_snapshot() -> str:
    """Count completed (archive) and queued tasks. Flag 400+ milestone."""
    try:
        completed = len(list(_ARCHIVE_DIR.glob("*.md"))) if _ARCHIVE_DIR.exists() else 0
        queued    = len(list(_QUEUE_DIR.glob("*.md")))   if _QUEUE_DIR.exists() else 0
    except Exception:
        return "Task milestone: data unavailable."

    if completed >= 400:
        milestone_note = f" Milestone: {completed}+ completed."
    elif completed >= 300:
        remaining = 400 - completed
        milestone_note = f" Approaching 400-task milestone ({remaining} to go)."
    else:
        milestone_note = ""

    return (
        f"Task milestone: {completed} tasks completed in archive.{milestone_note} "
        f"{queued} tasks in queue."
    )


# ── Section 2: Financial snapshot ────────────────────────────────────────────

_HISTORICAL_LOG_TS_RE = __import__("re").compile(
    r"^\s*[-*]?\s*\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*(.*)$"
)


def _recent_md_entries(path: Path, *, max_age_days: int, limit: int = 4) -> list[str]:
    if not path.exists():
        return []
    cutoff = harness_context.now() - timedelta(days=max_age_days)
    kept: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("---"):
            continue
        match = _HISTORICAL_LOG_TS_RE.match(line)
        if match:
            try:
                stamp = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
                if stamp < cutoff:
                    continue
                kept.append(f"[{match.group(1)}] {match.group(2).strip()}")
                continue
            except ValueError:
                pass
        kept.append(line)
    return kept[-limit:]


def _load_reality_notes() -> dict:
    try:
        data = json.loads(_REALITY_NOTES.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _financial_reality_lines() -> list[str]:
    lines: list[str] = []
    for key, entry in _load_reality_notes().items():
        if not isinstance(entry, dict):
            continue
        summary = str(entry.get("status_summary") or "").strip()
        if not summary:
            continue
        if not entry.get("payment_answer") and "payment" not in summary.lower() and "invoice" not in summary.lower():
            continue
        label = str(entry.get("label") or key).strip()
        if label:
            lines.append(f"{label}: {summary}")
    return lines

def _financial_snapshot() -> str:
    """Recent income (48h) + open payment follow-ups. Graceful fallback."""
    lines: list[str] = []

    # Income from CPA brain
    try:
        from chief_cpa_brain import get_recent_income
        entries = get_recent_income(days=2)
        if entries:
            items = [
                f"${e['amount']} from {e.get('description') or e.get('category', '?')}"
                for e in entries[:4]
            ]
            lines.append("Recent income (48h): " + ", ".join(items) + ".")
        else:
            lines.append("Recent income: nothing logged in last 48 hours.")
    except Exception:
        lines.append("Recent income: source unavailable.")

    # Payment follow-ups
    try:
        followups = _recent_md_entries(_OPS_PAYMENT, max_age_days=14, limit=4)
        if followups:
            lines.append("Payment follow-ups (recent log): " + "; ".join(followups) + ".")
        else:
            lines.append("Payment follow-ups: none on recent record.")
    except Exception:
        lines.append("Payment follow-ups: read error.")

    finance_snapshot = build_finance_snapshot(limit=3)
    if finance_snapshot:
        finance_lines = [
            line.strip()
            for line in finance_snapshot.splitlines()
            if line.strip() and not line.startswith("[")
        ]
        if finance_lines:
            lines.append("Structured finance state: " + "; ".join(finance_lines) + ".")

    reality_lines = _financial_reality_lines()
    if reality_lines:
        lines.append("Canonical financial reality: " + "; ".join(reality_lines) + ".")

    return "\n".join(lines) if lines else "Financial data: unavailable."


# ── Section 3: Music / album progress ────────────────────────────────────────

def _music_snapshot() -> str:
    """Album CSV completion summary. Fallback if CSV absent or malformed."""
    try:
        if not _ALBUM_CSV.exists():
            return "Album: work log not found. Music status unavailable."

        total = complete = in_progress = 0
        with open(_ALBUM_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                total += 1
                try:
                    pct = float(row.get("completion_pct", 0) or 0)
                except (ValueError, TypeError):
                    pct = 0
                if pct >= 80:
                    complete += 1
                elif pct > 0:
                    in_progress += 1

        if total == 0:
            return "Album: CSV exists but has no song rows. No music progress data."

        unstarted = total - complete - in_progress
        parts = [f"{complete} of {total} songs complete (80%+ done)"]
        if in_progress:
            parts.append(f"{in_progress} in progress")
        if unstarted:
            parts.append(f"{unstarted} not yet started")
        return "Album: " + ", ".join(parts) + "."

    except Exception:
        return "Album: data read error. Music status unavailable."


# ── Section 4: Surf/golf/work cue ────────────────────────────────────────────

def _fetch_weather() -> dict | None:
    """
    Try wttr.in JSON for Ocean City, MD.
    Returns a dict with 'wind_mph' (float) and 'desc' (str), or None on failure.
    Times out in 4 seconds so it never blocks briefing delivery.
    """
    fixture = harness_context.get_fixture("weather")
    if fixture:
        return fixture

    try:
        import requests  # type: ignore[import-not-found]
        url = f"https://wttr.in/{_OCEAN_CITY_QUERY}?format=j1"
        resp = requests.get(url, timeout=4, headers={"User-Agent": "openclaw-briefing/1.0"})
        if resp.status_code != 200:
            return None
        data = resp.json()
        current = data["current_condition"][0]
        wind_mph = float(current.get("windspeedMiles", 0))
        desc     = current.get("weatherDesc", [{}])[0].get("value", "unknown")
        feels    = current.get("FeelsLikeF", "?")
        return {"wind_mph": wind_mph, "desc": desc, "feels_f": feels}
    except Exception:
        return None


def surf_directive(weather: dict | None = None) -> str:
    """
    Return one of: 'surf', 'golf', 'work'.
    Uses fetched weather if provided, else calls _fetch_weather().
    Falls back to 'check conditions' text if weather is unavailable.
    """
    if weather is None:
        weather = _fetch_weather()
    if weather is None:
        return "check"  # fallback sentinel — signals caller to use fallback text

    wind = weather.get("wind_mph", 99)
    desc = str(weather.get("desc", "")).lower()

    # Rain/storm → work mode regardless of wind
    if any(w in desc for w in ("rain", "drizzle", "thunder", "storm", "snow", "sleet")):
        return "work"

    if wind <= _SURF_WIND_MAX:
        return "surf"
    if wind <= _GOLF_WIND_MAX:
        return "golf"
    return "work"


def _surf_cue_text() -> str:
    """
    Build the surf/conditions section with directive.
    Tries live weather, falls back to Life Sync notes, then to static prompt.
    """
    weather = _fetch_weather()

    # Try Life Sync vault note as secondary source
    life_sync_note = ""
    try:
        if _LIFE_SYNC.exists():
            text = _LIFE_SYNC.read_text(encoding="utf-8")
            low = text.lower()
            if "ocean city" in low or "surf" in low:
                # Extract first surf-relevant line
                for line in text.splitlines():
                    if any(k in line.lower() for k in ("surf", "ocean city", "golf", "swell")):
                        life_sync_note = line.strip()
                        break
    except Exception:
        pass

    if weather is not None:
        directive = surf_directive(weather)
        wind  = weather["wind_mph"]
        desc  = weather["desc"]
        feels = weather["feels_f"]
        cue = (
            f"Ocean City conditions: {desc}, wind {wind:.0f} mph, feels {feels}F. "
            f"Directive: {directive.upper()} MODE."
        )
        if life_sync_note:
            cue += f" (Life Sync note: {life_sync_note})"
        return cue

    # Weather fetch failed — use life sync or static fallback
    if life_sync_note:
        return f"Ocean City conditions: weather fetch unavailable. Life Sync note: {life_sync_note}. Check surf app before heading out."

    return "Ocean City conditions: weather data unavailable. Check surf app manually before deciding."


# ── Assembly ──────────────────────────────────────────────────────────────────

def build_morning_briefing_context() -> str:
    """
    Returns a structured multi-section context block for the morning
    briefing prompt.  All sections degrade gracefully; none will raise.
    """
    now = datetime.now().strftime("%H:%M, %A %B %d")
    sections = [
        f"=== MORNING BRIEFING CONTEXT ({now}) ===",
        "",
        "[TASK MILESTONE]",
        _task_milestone_snapshot(),
        "",
        "[FINANCIAL STATUS]",
        _financial_snapshot(),
        "",
        "[MUSIC / ALBUM PROGRESS]",
        _music_snapshot(),
        "",
        "[SURF / WEATHER CUE — OCEAN CITY MD]",
        _surf_cue_text(),
        "",
        "=== END MORNING BRIEFING CONTEXT ===",
    ]
    return "\n".join(sections)


# Compatibility alias while the rest of the system migrates away from the old name.
build_sovereign_context = build_morning_briefing_context

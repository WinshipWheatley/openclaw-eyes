"""
cassandra_briefing_brain.py

Generates, archives, and manages delivery state for Cassandra's scheduled
daily briefings.  Used exclusively by cassandra_briefing_scheduler.py.

Slots
-----
  morning    08:00–09:30
  afternoon  13:00–14:30
  evening    20:00–21:30

Archive
-------
  /mnt/c/OpenClaw/logs/cassandra_briefings/YYYY-MM-DD_{slot}.json
  /mnt/c/OpenClaw/logs/cassandra_briefings/briefing_log.md   (append-only)

Each JSON record:
  {
    "slot":          "morning",
    "date":          "YYYY-MM-DD",
    "text":          "...",
    "generated_at":  "ISO datetime",
    "delivered":     false,
    "delivered_at":  null,
    "pending_reason": null | "focus_mode" | "album_session" | "approval_pending" | ...
  }

Protected-window checks (read-only, no imports from approval/session logic):
  1. Cassandra focus lock file
  2. Cassandra social lock file
  3. Chief session status (reads JSON directly)
  4. Scheduler running_work state (reads JSON directly)
  5. Pending approval (reads JSON directly)
"""

import json
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

from cassandra_brain import build_context_snapshot, build_current_truth_snapshot
from cassandra_mode import is_focus_mode, is_social_mode
from chief_output_utils import tts_clean
from adaptive_model_call import adaptive_ollama_text

ollama_call = adaptive_ollama_text

def _local_model_call(*args, **kwargs):
    return globals()["ollama_call"](*args, **kwargs)

from chief_llm import resolve_local_model, ollama_json
from chief_file_io import save_json, load_json, append_md_tagged

import harness_context
import chief_ops_reporter as ops
from agent_perspective import perspective_prompt


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.environ.get(name, str(default))))
    except ValueError:
        return default


# ── Paths ─────────────────────────────────────────────────────────────────────

BRIEFING_DIR  = Path("/mnt/c/OpenClaw/logs/cassandra_briefings")
BRIEFING_LOG  = BRIEFING_DIR / "briefing_log.md"
_CHIEF_MORNING_SYNTHESIS = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Chief Morning Synthesis.md")
_MORNING_REFERENCE_CACHE = BRIEFING_DIR / "morning_reference_cache.json"
_MORNING_SYNTHESIS_MAX_CHARS = 9000
_MORNING_TEXT_CHUNK_LIMIT = 1200
_MORNING_SPOKEN_SUMMARY_LIMIT = 420
_MORNING_REFERENCE_LINE_LIMIT = 80
_MORNING_TEST_MODE_ENV = "CASSANDRA_MORNING_BRIEF_TEST_MODE"
_NON_MORNING_BRIEF_TOTAL_TIMEOUT_SECONDS = 300
_NON_MORNING_BRIEF_PRIMARY_TIMEOUT_SECONDS = 180
_NON_MORNING_BRIEF_FALLBACK_MODEL = "qwen3:8b-q4_K_M"
_SCHEDULED_BRIEF_TASK_CLASS = "cassandra_scheduled_brief"
_MORNING_DELIVERY_TIMEOUT_SECONDS = _env_int("OPENCLAW_CASSANDRA_MORNING_BRIEF_TIMEOUT_SECONDS", 420, minimum=60)
_MORNING_STACK_GUARDIAN_TIMEOUT_SECONDS = _env_int("OPENCLAW_MORNING_STACK_GUARDIAN_TIMEOUT_SECONDS", 90, minimum=30)
_MORNING_STACK_CHIEF_TIMEOUT_SECONDS = _env_int("OPENCLAW_MORNING_STACK_CHIEF_TIMEOUT_SECONDS", 420, minimum=60)
_MORNING_STACK_CASSANDRA_TIMEOUT_SECONDS = _env_int("OPENCLAW_MORNING_STACK_CASSANDRA_TIMEOUT_SECONDS", 300, minimum=60)
_RECENT_MORNING_SYNTHESIS_REFRESH: dict[str, datetime] = {}

# Read-only peeks at external state (no circular imports)
_SESSION_FILE     = Path("/home/openclaw/OpenClaw/state/chief_session.json")
_SCHEDULER_STATE  = Path("/mnt/c/OpenClawShared/album/scheduler_state.json")
_APPROVAL_PENDING = Path("/mnt/c/OpenClaw/logs/approval_pending.json")

from cassandra_briefing_morning_policy import resolve_morning_model_lane

# Treat very old pending approvals as stale so delayed/abandoned records
# do not keep Cassandra in a permanent protected window.
_APPROVAL_PENDING_MAX_AGE_SECONDS = 900
_APPROVAL_IGNORED_REQUESTERS = {
    "codex-test",
    "claude-test",
}

# ── Slot definitions ──────────────────────────────────────────────────────────

# {slot: (start_hour, end_hour_exclusive, briefing_directive)}
SLOTS = {
    "morning": (
        5, 9,
        "Generate the morning delivery from CHIEF MORNING SYNTHESIS only.\n"
        "Return EXACTLY a JSON array of objects, with NO markdown formatting or fences.\n"
        "Each object must have 'header' (short label) and 'body' (short human-readable text).\n"
        "Required headers: 'Priorities', 'Watchlist', 'Directive'.\n"
        "Optional headers: 'Money / follow-ups', 'Schedule / conditions'.\n"
        "Return the headers in this exact order: Priorities, Watchlist, Money / follow-ups, Schedule / conditions, Directive.\n"
        "Keep each body very concise and conversational."
    ),
    "afternoon": (
        13, 15,
        "Generate a brief afternoon check-in (3–4 sentences).\n"
        "Acknowledge the midday point.\n"
        "Highlight anything still unresolved from the morning if present.\n"
        "Name one priority for the afternoon.\n"
        "Be efficient. No filler.",
    ),
    "evening": (
        20, 22,
        "Generate a brief evening summary (3–4 sentences).\n"
        "Wind down the day — what's still open, what can wait until tomorrow.\n"
        "Keep the tone low-friction and calm.\n"
        "Close the briefing gently. Do not open new threads.",
    ),
}

# ── Protected-window detection ────────────────────────────────────────────────

def _read_json_safe(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _parse_requested_at(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    for parser in (datetime.fromisoformat, lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M:%S")):
        try:
            return parser(value)
        except Exception:
            continue
    return None


def _approval_pending_active() -> bool:
    approval = _read_json_safe(_APPROVAL_PENDING)
    if approval.get("status") != "pending":
        return False

    requester = str(approval.get("requester", "")).strip().lower()
    if requester in _APPROVAL_IGNORED_REQUESTERS:
        return False

    requested_at = _parse_requested_at(str(approval.get("requested_at", "")))
    if requested_at is not None:
        age = (datetime.now() - requested_at).total_seconds()
        if age > _APPROVAL_PENDING_MAX_AGE_SECONDS:
            return False

    return True


def protected_reason(slot: str | None = None) -> str | None:
    """
    Return a short reason string if a protected window is active, else None.
    Reads state files directly — no imports from session/approval/router.
    """
    if is_focus_mode():
        return "focus_mode"
    if is_social_mode():
        return "social_mode"

    session = _read_json_safe(_SESSION_FILE)
    if session.get("status") == "active":
        workflow = session.get("active_workflow") or "workflow"
        return f"active_session:{workflow}"

    sched = _read_json_safe(_SCHEDULER_STATE)
    if sched.get("status") == "running_work":
        ends_at = sched.get("ends_at", "")
        try:
            if not ends_at or datetime.fromisoformat(ends_at) >= datetime.now():
                task = sched.get("task") or "work_block"
                return f"scheduler:{task}"
        except Exception:
            pass  # malformed ends_at — treat as idle

    if _approval_pending_active():
        return "approval_pending"

    if slot == "morning":
        from cassandra_briefing_morning_policy import is_too_early_for_morning_delivery
        if is_too_early_for_morning_delivery():
            return "morning_too_early"

    return None


def is_protected_window(slot: str | None = None) -> bool:
    return protected_reason(slot=slot) is not None


# ── Archive helpers ───────────────────────────────────────────────────────────

def _briefing_path(date: str, slot: str) -> Path:
    return BRIEFING_DIR / f"{date}_{slot}.json"


def load_briefing(date: str, slot: str) -> dict | None:
    p = _briefing_path(date, slot)
    if not p.exists():
        return None
    return load_json(p, None)


def save_briefing(slot: str, text: str, pending_reason: str | None) -> dict:
    """Write the generated briefing to the archive. Returns the entry dict."""
    now   = datetime.now()
    date  = now.date().isoformat()
    path  = _briefing_path(date, slot)
    
    # DEDUPE: If already delivered today, do not overwrite with fresh generation
    # (prevents redundant deliveries if scheduler is reloading or racing)
    if path.exists():
        existing = load_json(path, {})
        if existing.get("delivered"):
            print(f"[briefing_brain] skipping save: {date}_{slot} already delivered", flush=True)
            return existing

    entry = {
        "slot":           slot,
        "date":           date,
        "text":           text,
        "generated_at":   now.isoformat(timespec="seconds"),
        "delivered":      False,
        "delivered_at":   None,
        "pending_reason": pending_reason,
    }
    BRIEFING_DIR.mkdir(parents=True, exist_ok=True)
    save_json(path, entry)

    # Append to markdown log
    tag  = f"{slot}/{'PENDING' if pending_reason else 'queued'}"
    append_md_tagged(BRIEFING_LOG, now.strftime("%Y-%m-%d %H:%M"), tag, text[:120] + "…")

    return entry


def mark_delivered(date: str, slot: str) -> None:
    p = _briefing_path(date, slot)
    entry = load_json(p, {})
    if not entry:
        return
    entry["delivered"]    = True
    entry["delivered_at"] = datetime.now().isoformat(timespec="seconds")
    entry["pending_reason"] = None
    save_json(p, entry)

    ts  = datetime.now().strftime("%Y-%m-%d %H:%M")
    append_md_tagged(BRIEFING_LOG, ts, f"{slot}/delivered", "✓")


def refresh_briefing_text(date: str, slot: str, text: str, pending_reason: str | None = None) -> None:
    """Update archived briefing text before delayed delivery."""
    p = _briefing_path(date, slot)
    entry = load_json(p, {})
    if not entry:
        return
    entry["text"] = text
    entry["generated_at"] = datetime.now().isoformat(timespec="seconds")
    entry["pending_reason"] = pending_reason
    save_json(p, entry)


# ── Scheduling helpers ────────────────────────────────────────────────────────

def due_slots() -> list[str]:
    """
    Return slot names whose generation window is currently open
    and have not yet been generated today.
    """
    now   = datetime.now()
    today = now.date().isoformat()
    due   = []
    for slot, (start_h, end_h, _) in SLOTS.items():
        if start_h <= now.hour < end_h:
            if load_briefing(today, slot) is None:
                due.append(slot)
    return due


def pending_briefings() -> list[dict]:
    """Return today's archived briefings that have been generated but not delivered.
    Prior-day briefings are stale — they remain in the archive as undelivered
    historical records and are not re-delivered when a protected window clears.
    """
    result = []
    if not BRIEFING_DIR.exists():
        return result
    today = datetime.now().date().isoformat()
    for p in sorted(BRIEFING_DIR.glob("????-??-??_*.json")):
        entry = load_json(p, {})
        if entry and not entry.get("delivered") and entry.get("date") == today:
            result.append(entry)
    return result


# ── Morning synthesis artifact helpers ────────────────────────────────────────

def _read_text_safe(path: Path, max_chars: int | None = None) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    if max_chars is not None:
        return text[:max_chars]
    return text


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def morning_brief_test_mode_enabled() -> bool:
    return _env_truthy(_MORNING_TEST_MODE_ENV)


def _morning_task_config() -> tuple[str, str]:
    if morning_brief_test_mode_enabled():
        return "cassandra_morning_brief_test", "llm"
    return resolve_morning_model_lane()


def _file_freshness_note(path: Path, stale_after_seconds: int = 12 * 60 * 60) -> str:
    if not path.exists():
        return "missing: source file not found"
    try:
        changed = datetime.fromtimestamp(path.stat().st_mtime)
        age = (datetime.now() - changed).total_seconds()
        label = "stale" if age > stale_after_seconds else "fresh"
        return f"{label}: source last changed {changed.isoformat(timespec='seconds')}"
    except Exception:
        return "unknown: source timestamp unreadable"


def _extract_markdown_sections(markdown: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = "Overview"
    sections[current] = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line or line == "---":
            continue
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
            continue
        if line.startswith("#") or line.startswith("type:") or line.startswith("generated_at:"):
            continue
        if line.startswith("source_module:") or line.startswith("bounded:"):
            continue
        if len(sections.setdefault(current, [])) >= _MORNING_REFERENCE_LINE_LIMIT:
            continue
        sections[current].append(line)
    return {key: value for key, value in sections.items() if value}


def _section_excerpt(sections: dict[str, list[str]], name: str, limit: int = 5) -> list[str]:
    lines = sections.get(name, [])
    return lines[:limit]


def _clean_artifact_line(line: str) -> str:
    line = re.sub(r"^\s*(?:[-*]|\u2022)\s*", "", str(line or "").strip())
    line = re.sub(r"^[A-Za-z /]+:\s+-\s*", "", line)
    line = re.sub(r"^[A-Za-z /]+:\s+", "", line)
    line = re.sub(r"^\s*(?:[-*]|\u2022)\s*", "", line)
    line = line.replace("`", "")
    line = re.sub(r"\s+", " ", line).strip()
    return line


def _is_metadata_line(line: str) -> bool:
    low = _clean_artifact_line(line).lower()
    return (
        not low
        or low in {"workers", "watcher", "system health"}
        or low.startswith("|")
        or low.startswith("source:")
        or low.startswith("generated:")
        or low.startswith("output artifact:")
        or low.startswith("bound:")
        or low.startswith("pending (")
        or low.startswith("completed (")
        or "openclawshared" in low
        or "source_module" in low
    )


def _clean_section_lines(sections: dict[str, list[str]], name: str, limit: int = 4) -> list[str]:
    cleaned: list[str] = []
    for line in sections.get(name, []):
        if _is_metadata_line(line):
            continue
        item = _clean_artifact_line(line)
        if item and item not in cleaned:
            cleaned.append(item)
        if len(cleaned) >= limit:
            break
    return cleaned


def _sentence(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        return ""
    if text.endswith((".", "!", "?")):
        return text
    return text + "."


def _friendly_gate_line(lines: list[str]) -> str | None:
    combined = " ".join(lines).lower()
    if "no actions currently waiting for approval" in combined:
        if re.search(r"\b1 tasks?\b|\b1 task\b", combined):
            return "The approval gate is clear, and one task is ready in the queue."
        return "The approval gate is clear."
    return None


def _friendly_stale_notes(sections: dict[str, list[str]]) -> list[str]:
    notes: list[str] = []
    for raw in sections.get("Confidence / What May Be Stale", []):
        low = raw.lower()
        if "ops calendar notes" in low:
            notes.append("calendar notes may be stale")
        elif "website qa log" in low:
            notes.append("website QA may be stale")
        elif "stale:" in low:
            notes.append(_clean_artifact_line(raw).rstrip("."))
        if len(notes) >= 2:
            break
    return notes


def _compact_morning_test_context(reference: dict) -> str:
    sections = reference.get("sections") or {}
    priorities = _clean_section_lines(sections, "Top Priorities", 4)
    blockers = _clean_section_lines(sections, "Blockers / Watchlist", 4)
    system_ops = _clean_section_lines(sections, "System / Ops State", 2)
    stale = _friendly_stale_notes(sections)

    priority = _friendly_gate_line(priorities) or (priorities[0] if priorities else "No top priority found.")
    open_items = [
        item for item in priorities
        if "[open]" in item.lower() or "follow up" in item.lower() or "reconcile" in item.lower()
    ]
    if open_items:
        priority = f"{priority} Top open item: {open_items[0]}"

    watch_items: list[str] = []
    for item in blockers:
        low = item.lower()
        if "no actions currently waiting for approval" in low:
            continue
        if "errors detected" in low:
            watch_items.append("listener errors are logged")
        elif "site offline" in low or "status: offline" in low:
            watch_items.append("website QA reports offline")
        elif "freshness: stale" in low or "stale:" in low:
            watch_items.append("one source artifact is stale")
        else:
            watch_items.append(item)
        if len(watch_items) >= 2:
            break

    return "\n".join([
        "CHIEF MORNING SYNTHESIS - COMPACT TEST CONTEXT",
        f"Freshness: {reference.get('freshness', 'freshness unknown')}",
        f"Priority: {priority}",
        f"Watchlist: {', '.join(watch_items) if watch_items else 'No blocker found.'}",
        f"System: {system_ops[0] if system_ops else 'No system state found.'}",
        f"Confidence: {', '.join(stale[:2]) if stale else 'No stale source flagged.'}",
    ])


def _build_morning_context_from_synthesis() -> dict:
    freshness = _file_freshness_note(_CHIEF_MORNING_SYNTHESIS)
    modified_at = None
    if _CHIEF_MORNING_SYNTHESIS.exists():
        try:
            modified_at = datetime.fromtimestamp(_CHIEF_MORNING_SYNTHESIS.stat().st_mtime)
        except Exception:
            pass

    markdown = _read_text_safe(_CHIEF_MORNING_SYNTHESIS, _MORNING_SYNTHESIS_MAX_CHARS)
    if not markdown:
        return {
            "available": False,
            "source_path": str(_CHIEF_MORNING_SYNTHESIS),
            "freshness": freshness,
            "modified_at": modified_at,
            "markdown": "",
            "sections": {},
            "prompt_context": (
                "CHIEF MORNING SYNTHESIS unavailable.\n"
                f"Source: {_CHIEF_MORNING_SYNTHESIS}\n"
                f"Freshness: {freshness}\n"
            ),
        }

    sections = _extract_markdown_sections(markdown)
    current_truth = build_current_truth_snapshot()
    prompt_parts = [
        "CURRENT TRUTH PRECEDENCE",
        current_truth or "No operator-corrected truth overrides are active.",
        "",
        "CHIEF MORNING SYNTHESIS",
        f"Source: {_CHIEF_MORNING_SYNTHESIS}",
        f"Freshness: {freshness}",
        "",
        markdown,
    ]
    return {
        "available": True,
        "source_path": str(_CHIEF_MORNING_SYNTHESIS),
        "freshness": freshness,
        "modified_at": modified_at,
        "markdown": markdown,
        "sections": sections,
        "prompt_context": "\n".join(prompt_parts),
    }


def _recently_refreshed_this_process(path: Path, modified_at: datetime | None) -> bool:
    """Return True for a synthesis file this process just refreshed.

    The morning-window guard compares file mtime against today's 5am start.
    During tests, or any injected policy-window run, a refresh before 5am can
    otherwise be immediately reclassified as "before today's window." Keep the
    exemption narrow: only the same path, only after the recorded refresh start,
    and only if the mtime is not a synthetic future timestamp.
    """
    if modified_at is None:
        return False
    refreshed_at = _RECENT_MORNING_SYNTHESIS_REFRESH.get(str(path))
    if refreshed_at is None:
        return False
    now = datetime.now()
    return refreshed_at <= modified_at <= now + timedelta(seconds=60)


def normalize_speech_text(text: str) -> str:
    """Normalize text for natural TTS output."""
    import re
    from datetime import datetime
    
    # Base TTS cleanup
    text = tts_clean(text)
    
    # Strip paths/urls like `/mnt/c/OpenClaw...` or `https://...`
    text = re.sub(r'(?:/mnt|/home|https?://)[/\w\.-]+', 'the file', text)
    
    # Strip basic markdown artifacts that might remain
    text = re.sub(r'[*`_]', '', text)
    
    # Normalize $500 -> 500 dollars
    text = re.sub(r'\$([\d,]+(?:\.\d{2})?)', r'\1 dollars', text)
    
    # Replace & with 'and'
    text = text.replace('&', 'and')

    # 1. Parenthetical number groups: (300, 450, 750) -> 300, 450, and 750
    def _paren_num_replace(m):
        content = m.group(1).strip()
        if ',' in content:
            nums = [n.strip() for n in content.split(',') if n.strip()]
            if len(nums) > 1:
                return ", ".join(nums[:-1]) + ", and " + nums[-1]
        return content
    text = re.sub(r'\(([\d, ]+)\)', _paren_num_replace, text)

    # 2. Shorthand dates like 3/11 or 5/9/2026
    def _shorthand_date_replace(m):
        try:
            month_idx = int(m.group(1))
            day = int(m.group(2))
            year = m.group(3)
            months = ["", "January", "February", "March", "April", "May", "June", 
                      "July", "August", "September", "October", "November", "December"]
            if 1 <= month_idx <= 12:
                month = months[month_idx]
                suffix = 'th' if 11 <= day <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
                if year:
                    y_val = year if len(year) == 4 else f"20{year}"
                    return f"{month} {day}{suffix}, {y_val}"
                return f"{month} {day}{suffix}"
        except:
            pass
        return m.group(0)
    text = re.sub(r'(?<!\d/)\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b', _shorthand_date_replace, text)

    # 3. Numbered list markers: 1) -> Number 1
    def _list_marker_replace(m):
        prefix = m.group(1) or ""
        num = m.group(2)
        return f"{prefix}Number {num}."
    text = re.sub(r'(^|\s)(\d+)\)', _list_marker_replace, text)
    
    # 4. Date normalizer 2026-04-19 -> April 19th, 2026
    def _date_replace(m):
        try:
            d = datetime.strptime(m.group(0), "%Y-%m-%d")
            suffix = 'th' if 11 <= d.day <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d.day % 10, 'th')
            return d.strftime(f"%B {d.day}{suffix}, %Y")
        except:
            return m.group(0)
    text = re.sub(r'\b20\d{2}-\d{2}-\d{2}\b', _date_replace, text)
    
    return re.sub(r'\s+', ' ', text).strip()

def _compact_spoken_summary(text: str, max_chars: int = _MORNING_SPOKEN_SUMMARY_LIMIT) -> str:
    cleaned = tts_clean(re.sub(r"\s+", " ", text).strip())
    if len(cleaned) <= max_chars:
        return cleaned

    clipped = cleaned[:max_chars].rstrip()
    sentence_end = max(clipped.rfind("."), clipped.rfind("?"), clipped.rfind("!"))
    if sentence_end >= 120:
        return clipped[: sentence_end + 1]
    word_end = clipped.rfind(" ")
    if word_end >= 120:
        return clipped[:word_end].rstrip() + "."
    return clipped.rstrip(".") + "."


def _fallback_morning_delivery(reference: dict) -> str:
    sections = reference.get("sections") or {}
    priorities = _clean_section_lines(sections, "Top Priorities", 4)
    blockers = _clean_section_lines(sections, "Blockers / Watchlist", 4)
    system_ops = _clean_section_lines(sections, "System / Ops State", 3)
    stale = _friendly_stale_notes(sections)

    parts: list[str] = []
    gate_line = _friendly_gate_line(priorities + blockers)
    if gate_line:
        parts.append(gate_line)
    elif priorities:
        parts.append("Top priority: " + _sentence(priorities[0]))

    open_items = [
        item for item in priorities
        if "[open]" in item.lower() or "follow up" in item.lower() or "reconcile" in item.lower()
    ]
    if open_items:
        parts.append("Top open item: " + _sentence(open_items[0]))

    if blockers:
        watch_items: list[str] = []
        for item in blockers:
            low = item.lower()
            if "no actions currently waiting for approval" in low:
                continue
            if "errors detected" in low:
                watch_items.append("listener errors are logged")
            elif "site offline" in low or "status: offline" in low:
                watch_items.append("website QA still reports offline")
            elif "freshness: stale" in low or "stale:" in low:
                watch_items.append("one source artifact is stale")
            else:
                watch_items.append(item.rstrip("."))
            if len(watch_items) >= 3:
                break
        if watch_items:
            parts.append("Watchlist: " + ", ".join(watch_items) + ".")

    if system_ops and not any("worker" in part.lower() for part in parts):
        parts.append("System state: " + _sentence(system_ops[0]))

    if stale:
        parts.append("Confidence: " + ", ".join(stale[:2]) + ".")

    if not parts:
        parts.append(
            "Chief Morning Synthesis is available, but it did not expose enough clean priority lines for a full morning brief."
        )
    return tts_clean(" ".join(parts))


def _write_morning_reference_cache(reference: dict, delivery_text: str) -> None:
    import json
    try:
        chunks = json.loads(delivery_text)
        if isinstance(chunks, list):
            summary_source = " ".join(c.get("body", "") for c in chunks)
        else:
            summary_source = delivery_text
    except Exception:
        summary_source = delivery_text
        
    cache = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_module": "cassandra_briefing_brain.py",
        "source_artifact": reference.get("source_path"),
        "source_freshness": reference.get("freshness"),
        "available": bool(reference.get("available")),
        "sections": reference.get("sections") or {},
        "delivery_text": delivery_text,
        "spoken_summary": _compact_spoken_summary(summary_source),
    }
    BRIEFING_DIR.mkdir(parents=True, exist_ok=True)
    save_json(_MORNING_REFERENCE_CACHE, cache)


def load_morning_reference_cache() -> dict:
    return load_json(_MORNING_REFERENCE_CACHE, {})


def split_briefing_messages(entry: dict, max_chars: int = _MORNING_TEXT_CHUNK_LIMIT) -> list[str]:
    slot = entry.get("slot", "briefing")
    date = entry.get("date", datetime.now().date().isoformat())
    text = str(entry.get("text") or "").strip()
    label = f"[{slot.title()} · {date}]\n\n"
    if len(label + text) <= max_chars:
        return [label + text]

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(paragraph) > max_chars:
            cut = paragraph.rfind(" ", 0, max_chars)
            if cut < 200:
                cut = max_chars
            chunks.append(paragraph[:cut].strip())
            paragraph = paragraph[cut:].strip()
        current = paragraph
    if current:
        chunks.append(current)

    total = len(chunks)
    return [
        f"{label}Part {index}/{total}\n\n{chunk}"
        for index, chunk in enumerate(chunks, start=1)
    ]


def briefing_voice_text(entry: dict) -> str:
    text = str(entry.get("text") or "")
    if entry.get("slot") != "morning":
        return text

    cache = load_morning_reference_cache()
    spoken = str(cache.get("spoken_summary") or "").strip()
    if spoken:
        return spoken
    return _compact_spoken_summary(text)


_PERSONA_BRIEF = f"""\
You are Cassandra, Executive Assistant to the Founder.
{perspective_prompt("cassandra")}
Character: calm, precise, discreet, honest. Hard to rattle.
No filler. No preamble. No motivational language.
Respond directly — your output IS the briefing, ready to send.

Response discipline:
- Lead with the answer. Expand only when it materially improves decision quality.
- Separate confirmed, inferred, and unknown clearly. Never use fake certainty.
- Status order: active lane first, verified live, code/test-only, unresolved, exact next action, backlog.
- Name the exact context when relevant: Mac, PowerShell, WSL, tmux, Telegram, Claude prompt, or vault/repo.
- Treat handoff and Drive docs as reflection layers. Operator-corrected truth is the highest source for client, invoice, and payment workflow; finance state/reality are canonical only when not superseded. Vault and repo are source of truth for the rest.

Capability honesty (always):
- Every claim must be labeled by source: "the log shows", "what's in Ops Actions", "based on the note" — never presented as externally verified fact.
- If the briefing mentions the operator, call him "Winship" or "you"; do not use "I", "me", or "my" for the operator.
- If the briefing uses "I", "me", or "my", that is Cassandra speaking about Cassandra.
- DO NOT SAY "your calendar shows", "the payment hasn't cleared", "the deposit is pending" as real-world fact.
- INSTEAD SAY "what's logged", "I can't confirm externally", "the follow-up is still open in the log".
- Never say a task was completed, sent, or synced unless the log entry explicitly confirms it.\
- When a CURRENT TRUTH PRECEDENCE block appears, treat operator_corrected entries as higher priority than finance state, canonical reality, Chief Morning Synthesis, and historical logs.\
- Do not repeat facts marked stale/superseded as current truth.\
- When a FINANCE STATE block appears, treat it as higher priority than raw historical log lines for client, invoice, and payment facts.\
- When a CANONICAL REALITY block appears, treat it as higher priority than raw historical log lines. If a raw log conflicts with canonical reality, follow canonical reality.\
"""


_MORNING_TEST_PROMPT = f"""\
You are Cassandra. Write a concise morning brief from the compact context only.
{perspective_prompt("cassandra")}
Use 3 short sentences max. Plain language. Mention stale confidence only if it affects the operator's next step.
"""


def _build_briefing_prompt(slot: str, context: str, directive: str, task_class: str) -> str:
    if slot == "morning" and task_class == "cassandra_morning_brief_test":
        return (
            f"{_MORNING_TEST_PROMPT}\n\n"
            f"Compact context:\n{context}\n\n"
            "Cassandra:"
        )

    return (
        f"{_PERSONA_BRIEF}\n\n"
        f"Current context:\n{context}\n\n"
        f"Task — {slot} briefing:\n{directive}\n\n"
        f"Cassandra:"
    )


def _without_pending_actions_section(context: str) -> str:
    """Remove Cassandra's legacy raw Ops Actions block from a snapshot."""
    kept: list[str] = []
    dropping = False
    for raw in str(context or "").splitlines():
        if raw.strip() == "Pending actions:":
            dropping = True
            continue
        if dropping:
            if not raw.strip() or raw.startswith((" ", "\t")):
                continue
            dropping = False
        kept.append(raw)
    return "\n".join(kept).strip()


def _ops_slice_context(action_slice: dict) -> str:
    status = str(action_slice.get("status") or "invalid")
    as_of = action_slice.get("as_of") or "unknown"
    source = action_slice.get("timestamp_source") or "none"
    lines = action_slice.get("lines") or []
    if status == "fresh":
        body = "\n".join(f"  {line}" for line in lines) if lines else "  (none)"
        return (
            f"Ops Actions slice: fresh; source as of {as_of} via {source}.\n"
            f"Current admitted actions:\n{body}"
        )
    return (
        f"Ops Actions slice: {status}; source as of {as_of} via {source}. "
        "No current priority is claimed from this slice."
    )


def _build_scheduled_brief_context() -> str:
    """Build model context with one age-gated Ops Actions representation."""
    canonical = _without_pending_actions_section(build_context_snapshot())
    action_slice = ops.read_ops_actions_slice()
    parts = [part for part in (canonical, _ops_slice_context(action_slice)) if part]
    return "\n\n".join(parts)


# ── Compatibility re-exports ──────────────────────────────────────────────────

def build_action_summary(n_actions: int = 12) -> str:
    return ops.build_action_summary(n_actions)


def classify_ops_actions(lines: list[str]) -> tuple[list[str], list[str]]:
    return ops.classify_ops_actions(lines)


def write_ops_actions_artifact(n_actions: int = 12) -> dict:
    return ops.write_ops_actions_artifact(n_actions)


# ── Harness / Stage Runners ───────────────────────────────────────────────────

def save_briefing_with_generation(
    slot: str,
    text: str,
    pending_reason: str | None,
    generation: dict | None = None,
) -> dict:
    """Write the generated briefing to the archive with optional stage metadata."""
    entry = save_briefing(slot, text, pending_reason)
    if generation:
        entry["generation"] = generation
        save_json(_briefing_path(entry["date"], slot), entry)
    return entry


def _clean_briefing_stage_text(name: str, text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""

    if "</think>" in cleaned:
        cleaned = cleaned.rsplit("</think>", 1)[-1]
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = cleaned.replace("<think>", "").replace("</think>", "")
    cleaned = tts_clean(cleaned).strip()
    if not cleaned:
        return ""

    lines: list[str] = []
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("that's ") and "bullet" in lower:
            continue
        if name == "guardian":
            if lower.startswith("we need a compact morning gate read"):
                continue
            if lower.startswith("identify immediate blockers"):
                continue
            if lower.startswith("approval/safety flags"):
                continue
            if lower.startswith("should not be overstated"):
                continue
            line = re.sub(r"^bullet\s+\d+\s*:\s*", "", line, flags=re.IGNORECASE)
        lines.append(line)

    return "\n".join(lines).strip()


def _truncate_words(text: str, limit: int) -> str:
    words = str(text or "").split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]) + " ..."


def _build_bounded_stage_context(
    inputs: dict[str, str],
    *,
    morning_words: int,
    action_words: int,
    canonical_words: int,
) -> str:
    return (
        f"MORNING BRIEFING CONTEXT\n{_truncate_words(inputs.get('morning_context', ''), morning_words)}\n\n"
        f"ACTION SUMMARY\n{_truncate_words(inputs.get('action_summary', ''), action_words)}\n\n"
        f"CANONICAL CONTEXT\n{_truncate_words(inputs.get('context', ''), canonical_words)}"
    )


def _run_briefing_stage(
    name: str,
    role: str,
    prompt: str,
    lane: str,
    timeout: int,
    fallback_prompt: str | None = None,
) -> dict:
    started = harness_context.now()
    t0 = time.monotonic()
    model, resolved_lane = resolve_local_model(
        prompt,
        lane=lane,
        task_class=_SCHEDULED_BRIEF_TASK_CLASS,
    )
    print(
        f"[cassandra_briefing] stage={name} role={role} lane={resolved_lane} model={model} started",
        flush=True,
    )
    result = _local_model_call(
        prompt,
        timeout=timeout,
        model=model,
        task_class=_SCHEDULED_BRIEF_TASK_CLASS,
        retry=False,
    )
    cleaned = _clean_briefing_stage_text(name, result)
    attempt_count = 1
    retry_used = False
    if not cleaned and fallback_prompt:
        retry_used = True
        attempt_count = 2
        print(
            f"[cassandra_briefing] stage={name} role={role} lane={resolved_lane} model={model} "
            f"retry=compact-fallback",
            flush=True,
        )
        result = _local_model_call(
            fallback_prompt,
            timeout=timeout,
            model=model,
            task_class=_SCHEDULED_BRIEF_TASK_CLASS,
            retry=False,
        )
        cleaned = _clean_briefing_stage_text(name, result)
    finished = harness_context.now()
    duration_ms = int((time.monotonic() - t0) * 1000)
    print(
        f"[cassandra_briefing] stage={name} role={role} lane={resolved_lane} model={model} "
        f"finished duration_ms={duration_ms}",
        flush=True,
    )
    return {
        "name": name,
        "role": role,
        "lane": resolved_lane,
        "model": model,
        "task_class": _SCHEDULED_BRIEF_TASK_CLASS,
        "inference_mode": "live",
        "timing_basis": "per_stage_wall_clock_including_internal_ollama_retries",
        "prompt_words": len(prompt.split()),
        "prompt_preview": prompt[:240],
        "result_raw": result,
        "result_cleaned": cleaned,
        "text": cleaned,  # Compatibility alias for tests
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": finished.isoformat(timespec="seconds"),
        "duration_ms": duration_ms,
        "attempt_count": attempt_count,
        "retry_used": retry_used,
    }


def _build_morning_stack_inputs() -> dict[str, str]:
    fixture_inputs = harness_context.get_fixture("inputs")
    if fixture_inputs:
        return fixture_inputs

    context = _build_scheduled_brief_context()
    try:
        from cassandra_briefing_morning_context import build_morning_briefing_context
        morning_context = build_morning_briefing_context()
    except Exception as e:
        morning_context = f"[morning briefing context unavailable: {e}]"

    return {
        "context": context,
        "morning_context": morning_context,
        "action_summary": build_action_summary(),
    }


def _generate_morning_stack() -> dict:
    from chief_llm import agent_default_lane
    inputs = _build_morning_stack_inputs()
    shared_context = (
        f"MORNING BRIEFING CONTEXT\n{inputs['morning_context']}\n\n"
        f"ACTION SUMMARY\n{inputs['action_summary']}\n\n"
        f"CANONICAL CONTEXT\n{inputs['context']}"
    )
    downstream_context = (
        f"MORNING BRIEFING CONTEXT\n{_truncate_words(inputs['morning_context'], 600)}\n\n"
        f"ACTION SUMMARY\n{_truncate_words(inputs['action_summary'], 250)}\n\n"
        f"CANONICAL CONTEXT\n{_truncate_words(inputs['context'], 350)}"
    )
    compact_context = _build_bounded_stage_context(
        inputs,
        morning_words=260,
        action_words=90,
        canonical_words=140,
    )

    guardian_stage = _run_briefing_stage(
        name="guardian",
        role="guardian",
        lane=agent_default_lane("guardian"),
        timeout=_MORNING_STACK_GUARDIAN_TIMEOUT_SECONDS,
        prompt=(
            "You are Guardian. Produce a compact morning gate read.\n"
            "Return 3-5 short bullets only covering: immediate blockers, approval or safety flags, "
            "and anything that should not be overstated.\n"
            "Output only the final bullets. No reasoning, no self-talk, no tags, no commentary about bullet counts.\n\n"
            f"{shared_context}\n\nGuardian:"
        ),
    )

    chief_stage = _run_briefing_stage(
        name="chief",
        role="chief_morning",
        lane=agent_default_lane("chief_morning"),
        timeout=_MORNING_STACK_CHIEF_TIMEOUT_SECONDS,
        prompt=(
            "You are Chief. Build the morning operating synthesis.\n"
            "Read Guardian first, then combine it with the available subsystem reports.\n"
            "Write 4-6 short lines of operator-facing synthesis only.\n"
            "No hidden reasoning, no XML tags, no preamble, no prompt restatement.\n\n"
            f"GUARDIAN OUTPUT\n{guardian_stage['text'] or '[Guardian output unavailable]'}\n\n"
            f"{downstream_context}\n\nChief:"
        ),
        fallback_prompt=(
            "You are Chief. Produce a compact morning synthesis for the operator.\n"
            "Use the Guardian bullets and the compact context below.\n"
            "Return 4 short lines only. No preamble. No reasoning tags.\n\n"
            f"GUARDIAN OUTPUT\n{guardian_stage['text'] or '[Guardian output unavailable]'}\n\n"
            f"{compact_context}\n\nChief:"
        ),
    )
    if not chief_stage["text"] and guardian_stage["text"]:
        chief_stage["text"] = guardian_stage["text"]
        chief_stage["fallback_source"] = "guardian_stage_passthrough"

    cassandra_stage = _run_briefing_stage(
        name="cassandra",
        role="cassandra_brief",
        lane=agent_default_lane("cassandra_brief", slot="morning"),
        timeout=_MORNING_STACK_CASSANDRA_TIMEOUT_SECONDS,
        prompt=(
            f"{_PERSONA_BRIEF}\n\n"
            "Condense the staged morning stack into the final operator briefing.\n"
            "Use Guardian first for caution framing, Chief second for synthesis, and keep it concise.\n"
            "Return operator-facing text only. No hidden reasoning, no tags, no prompt echo.\n\n"
            f"GUARDIAN OUTPUT\n{guardian_stage['text'] or '[Guardian output unavailable]'}\n\n"
            f"CHIEF OUTPUT\n{chief_stage['text'] or '[Chief output unavailable]'}\n\n"
            f"{downstream_context}\n\nCassandra:"
        ),
        fallback_prompt=(
            f"{_PERSONA_BRIEF}\n\n"
            "Produce the final morning briefing.\n"
            "Use the staged outputs first and the compact context second.\n"
            "3-5 sentences. No markdown. No tags. No prompt echo.\n\n"
            f"GUARDIAN OUTPUT\n{guardian_stage['text'] or '[Guardian output unavailable]'}\n\n"
            f"CHIEF OUTPUT\n{chief_stage['text'] or '[Chief output unavailable]'}\n\n"
            f"{compact_context}\n\nCassandra:"
        ),
    )
    if not cassandra_stage["text"] and chief_stage["text"]:
        cassandra_stage["text"] = chief_stage["text"]
        cassandra_stage["fallback_source"] = "chief_stage_passthrough"
    elif not cassandra_stage["text"] and guardian_stage["text"]:
        cassandra_stage["text"] = guardian_stage["text"]
        cassandra_stage["fallback_source"] = "guardian_stage_passthrough"

    return {
        "text": cassandra_stage["text"] or chief_stage["text"] or guardian_stage["text"],
        "generation": {
            "path": "guardian->chief->cassandra",
            "stages": [guardian_stage, chief_stage, cassandra_stage],
        },
    }


def generate_briefing_bundle(slot: str) -> dict:
    """Return generated text plus generation metadata for archival."""
    if slot == "morning":
        return _generate_morning_stack()

    from chief_llm import agent_default_lane
    _, _, directive = SLOTS[slot]
    context = _build_scheduled_brief_context()
    prompt = (
        f"{_PERSONA_BRIEF}\n\n"
        f"Current context:\n{context}\n\n"
        f"Task — {slot} briefing:\n{directive}\n\n"
        f"Cassandra:"
    )
    lane = agent_default_lane("cassandra_brief", slot=slot)
    stage = _run_briefing_stage(
        name=slot,
        role="cassandra_brief",
        prompt=prompt,
        lane=lane,
        timeout=60 if lane == "deep" else 45,
    )
    return {
        "text": stage["text"],
        "generation": {
            "path": "cassandra",
            "stages": [stage],
        },
    }


def _bounded_ops_slot_fallback(slot: str) -> str:
    ts = datetime.now().strftime("%H:%M")
    action_slice = ops.read_ops_actions_slice()
    if action_slice["status"] != "fresh":
        status = action_slice["status"]
        as_of = action_slice["as_of"]
        if as_of:
            as_of_note = f" as of {as_of[:10]}"
        else:
            as_of_note = " with no usable as-of timestamp"
        return tts_clean(
            f"[{ts} — {slot} fallback] Ops Actions slice is {status}{as_of_note}. "
            "No current priority is claimed from it."
        )

    action_summary = ops.build_action_summary(action_slice=action_slice)
    pending: list[str] = []
    completed: list[str] = []
    section = None
    skip_prefixes = (
        "type:",
        "updated:",
        "generated_at:",
        "owner:",
        "status:",
        "slot:",
    )
    for raw in action_summary.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("Pending ("):
            section = "pending"
            continue
        if line.startswith("Completed ("):
            section = "completed"
            continue
        if line == "(none)":
            continue
        if any(line.lower().startswith(prefix) for prefix in skip_prefixes):
            continue
        if section == "pending":
            pending.append(line.replace("[PRIORITY] ", "").strip())
        elif section == "completed":
            completed.append(line.strip())

    if slot == "evening":
        lead = pending[0] if pending else "No unresolved Ops Actions are on the current board."
        second = pending[1] if len(pending) > 1 else ""
        completed_note = completed[0] if completed else "No completed item is highlighted in the recent Ops Actions slice."
        parts = [
            f"[{ts} — evening fallback] Tonight's top open item: {lead}",
            second if second else "",
            f"Most recent completion note: {completed_note}",
            "Anything beyond those items can wait until tomorrow unless it becomes urgent tonight.",
        ]
        return tts_clean(" ".join(part for part in parts if part))

    if slot == "afternoon":
        lead = pending[0] if pending else "No pending Ops Actions are on the current board."
        completed_note = completed[0] if completed else "No recent completion is highlighted in the current Ops Actions slice."
        parts = [
            f"[{ts} — afternoon fallback] Midday priority: {lead}",
            f"Most recent completion note: {completed_note}",
            "Keep the afternoon bounded to the active open lane only.",
        ]
        return tts_clean(" ".join(parts))

    return ""


def _fallback_briefing_text(slot: str) -> str:
    """Return the existing minimal fallback when the LLM path is empty/unavailable."""

    # Minimal fallback if LLM is unreachable — for morning, include the morning context summary.
    ts = harness_context.now().strftime("%H:%M")
    if slot == "morning":
        try:
            from cassandra_briefing_morning_context import (
                _task_milestone_snapshot,
                _financial_snapshot,
                _music_snapshot,
                _surf_cue_text,
            )
            fallback_body = " ".join([
                _task_milestone_snapshot(),
                _financial_snapshot().replace("\n", " "),
                _music_snapshot(),
                _surf_cue_text(),
            ])
            return tts_clean(f"[{ts} — morning briefing, LLM offline] {fallback_body}")
        except Exception:
            pass

    # For afternoon/evening, use the bounded ops fallback.
    return _bounded_ops_slot_fallback(slot)


def _remaining_non_morning_brief_timeout(started: float) -> int:
    elapsed = time.monotonic() - started
    return max(1, int(_NON_MORNING_BRIEF_TOTAL_TIMEOUT_SECONDS - elapsed))


def generate_briefing(slot: str) -> str:
    """
    Call the fast local LLM to generate a briefing for the given slot.
    Returns the briefing text (may be a fallback if LLM fails).
    Morning slot reads Chief Morning Synthesis as the primary source artifact.
    """
    _, _, directive = SLOTS[slot]
    morning_reference: dict | None = None
    task_class, mode = (
        _morning_task_config()
        if slot == "morning"
        else (_SCHEDULED_BRIEF_TASK_CLASS, "llm")
    )
    
    if slot == "morning":
        morning_reference = _build_morning_context_from_synthesis()
        
        # Check if we need to orchestrate a refresh of Guardian artifacts and Synthesis.
        # We refresh if:
        # 1. Synthesis is missing or stale (> 12h)
        # 2. We are in the morning window (>= 5:00 AM) and synthesis was last generated BEFORE 5:00 AM today
        #    (Ensures we get a truly fresh "today's" synthesis at least once in the morning window).
        should_refresh = not morning_reference.get("available") or "stale" in morning_reference.get("freshness", "").lower()
        
        if not should_refresh:
            mtime = morning_reference.get("modified_at")
            if mtime:
                from cassandra_briefing_morning_policy import is_within_morning_window, ORCHESTRATION_START_TIME
                now = datetime.now()
                if is_within_morning_window():
                    today_start = datetime.combine(now.date(), ORCHESTRATION_START_TIME)
                    # The policy predicate owns the active morning window; tests
                    # may inject it to exercise stale/fresh boundaries.
                    if mtime < today_start and not _recently_refreshed_this_process(
                        _CHIEF_MORNING_SYNTHESIS,
                        mtime,
                    ):
                        should_refresh = True
        
        if should_refresh:
            print(f"[briefing_brain] Triggering morning artifact orchestration (reason: {'stale' if not morning_reference.get('available') or 'stale' in morning_reference.get('freshness', '').lower() else 'first run of window'})", flush=True)
            from chief_morning_orchestrator import refresh_morning_artifacts
            refresh_started = datetime.now()
            if refresh_morning_artifacts():
                _RECENT_MORNING_SYNTHESIS_REFRESH[str(_CHIEF_MORNING_SYNTHESIS)] = refresh_started
                # Re-build context after refresh
                morning_reference = _build_morning_context_from_synthesis()

        # Final staleness/availability check after attempted refresh
        if not morning_reference.get("available") or "stale" in morning_reference.get("freshness", "").lower():
            text = (
                "Chief Morning Synthesis is missing or stale, so I do not have a "
                "safe morning brief to deliver. Run the Chief morning synthesis "
                "artifact first, then retry."
            )
            _write_morning_reference_cache(morning_reference, text)
            return tts_clean(text)

        # Deterministic fallback mode (e.g. after 08:15 deadline)
        if mode == "deterministic":
            text = _fallback_morning_delivery(morning_reference)
            _write_morning_reference_cache(morning_reference, text)
            return text

        if task_class == "cassandra_morning_brief_test":
            context = _compact_morning_test_context(morning_reference)
        else:
            context = morning_reference["prompt_context"]
    else:
        context = _build_scheduled_brief_context()

    prompt = _build_briefing_prompt(slot, context, directive, task_class)

    if slot == "morning":
        import json
        data = ollama_json(prompt, timeout=_MORNING_DELIVERY_TIMEOUT_SECONDS, task_class=task_class)
        if data and isinstance(data, list):
            # Sort the chunks here according to policy order
            from cassandra_briefing_morning_policy import sort_morning_chunks
            data = sort_morning_chunks(data)
            text = json.dumps(data)
            if morning_reference is not None:
                _write_morning_reference_cache(morning_reference, text)
            return text
        result = ""
    else:
        started = time.monotonic()
        model, _lane = resolve_local_model(prompt, task_class=task_class)
        primary_timeout = min(
            _NON_MORNING_BRIEF_PRIMARY_TIMEOUT_SECONDS,
            _remaining_non_morning_brief_timeout(started),
        )
        result = _local_model_call(
            prompt,
            timeout=primary_timeout,
            model=model,
            task_class=task_class,
            retry=False,
        )
        if not result:
            result = _local_model_call(
                prompt,
                timeout=_remaining_non_morning_brief_timeout(started),
                model=_NON_MORNING_BRIEF_FALLBACK_MODEL,
                task_class=task_class,
                retry=False,
            )

    if result:
        text = tts_clean(result.strip())
        if slot == "morning" and morning_reference is not None:
            _write_morning_reference_cache(morning_reference, text)
        return text

    # Minimal fallback if LLM is unreachable.
    ts = datetime.now().strftime("%H:%M")
    if slot == "morning":
        text = f"[{ts} - morning briefing, LLM offline] {_fallback_morning_delivery(morning_reference or {})}"
        if morning_reference is not None:
            _write_morning_reference_cache(morning_reference, text)
        return tts_clean(text)

    return _fallback_briefing_text(slot)


# ── Recall ────────────────────────────────────────────────────────────────────

_RECALL_PATTERNS = (
    "morning log", "afternoon log", "evening log",
    "morning briefing", "afternoon briefing", "evening briefing",
    "last briefing", "today's briefing", "briefing log",
    "recall briefing", "show briefing", "what was the briefing",
    "what was this morning", "what was this afternoon", "what was tonight",
)


def is_recall_request(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in _RECALL_PATTERNS)


def handle_recall(text: str) -> str:
    """Return archived briefing text for a recall request, or a not-found message."""
    t     = today = datetime.now().date().isoformat()
    lower = text.lower()

    # Determine which slot was requested
    if "morning" in lower:
        slots_to_try = ["morning"]
    elif "afternoon" in lower:
        slots_to_try = ["afternoon"]
    elif "evening" in lower or "tonight" in lower or "night" in lower:
        slots_to_try = ["evening"]
    else:
        # "last briefing" — return most recent delivered one across all slots
        slots_to_try = list(SLOTS.keys())

    for slot in slots_to_try:
        entry = load_briefing(today, slot)
        if entry and entry.get("text"):
            delivered = "delivered" if entry.get("delivered") else "pending delivery"
            
            if slot == "morning":
                import json
                try:
                    chunks = json.loads(entry["text"])
                    if isinstance(chunks, list):
                        body = "\n\n".join(f"[{c.get('header', '')}]\n{c.get('body', '')}" for c in chunks)
                        return f"[{slot.title()} · {today} · {delivered}]\n\n{body}"
                except:
                    pass

            return (
                f"[{slot.title()} · {today} · {delivered}]\n\n"
                + entry["text"]
            )

    return f"No briefing archived for today ({today}). Check back after the scheduled window."

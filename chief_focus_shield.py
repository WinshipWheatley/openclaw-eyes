"""
chief_focus_shield.py

Holds non-urgent items during active scheduler work blocks. Surfaces them
at the right moment (break, block end, end of day, or never proactively).

Timing classes:
  interrupt_now       — always surface immediately
  next_break          — surface when scheduler transitions to break
  after_current_block — surface when block stops/completes
  end_of_day          — surface only on explicit end-of-day check
  watch_silently      — never surface proactively; only on explicit check

Brainstorm → shield mapping:
  now     → interrupt_now
  soon    → next_break
  later   → after_current_block
  watch   → watch_silently
  archive → watch_silently

Triggered by:
  - Called by chief_brainstorm_brain after synthesis
  - Called by chief_scheduler_brain on break/stop transitions
  - "focus status" / "held items" / "surface now" commands
Intent: focus_status in chief_router.py

State: /mnt/c/OpenClawShared/album/focus_held.json
"""

import json
from datetime import datetime
from pathlib import Path

STATE_JSON = Path("/mnt/c/OpenClawShared/album/scheduler_state.json")
HELD_JSON  = Path("/mnt/c/OpenClawShared/album/focus_held.json")

_BRAINSTORM_TO_SHIELD = {
    "now":     "interrupt_now",
    "soon":    "next_break",
    "later":   "after_current_block",
    "watch":   "watch_silently",
    "archive": "watch_silently",
}

_TRIGGER_ORDER = [
    "interrupt_now",
    "next_break",
    "after_current_block",
    "end_of_day",
    "watch_silently",
]


# ── State helpers ─────────────────────────────────────────────────────────────

def _load_held() -> list[dict]:
    if HELD_JSON.exists():
        try:
            return json.loads(HELD_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_held(items: list[dict]) -> None:
    HELD_JSON.parent.mkdir(parents=True, exist_ok=True)
    HELD_JSON.write_text(json.dumps(items, indent=2), encoding="utf-8")


def _load_scheduler_state() -> dict:
    if STATE_JSON.exists():
        try:
            return json.loads(STATE_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"status": "idle"}


# ── Public API ────────────────────────────────────────────────────────────────

def is_focus_active() -> bool:
    """True when scheduler has a running work block (not idle, not break, not prompting)."""
    state = _load_scheduler_state()
    return state.get("status") == "running_work"


def classify_timing(brainstorm_timing: str) -> str:
    """Map a brainstorm timing_class to a shield timing class."""
    return _BRAINSTORM_TO_SHIELD.get(brainstorm_timing, "after_current_block")


def should_surface(item: dict) -> bool:
    """
    Return True if the item should be shown to the user now.
    False means hold it — focus is active and it's not interrupt_now.
    """
    timing = item.get("shield_timing") or classify_timing(item.get("timing_class", "later"))
    if timing == "interrupt_now":
        return True
    return not is_focus_active()


def hold_item(item: dict, timing_class: str) -> None:
    """Store an item in the held queue with its shield timing class."""
    held = _load_held()
    entry = {
        "id":            item.get("idea_id") or item.get("id", "unknown"),
        "title":         item.get("title", ""),
        "shield_timing": timing_class,
        "source":        item.get("source", "brainstorm"),
        "held_at":       datetime.now().isoformat(),
        "surfaced":      False,
    }
    # Dedupe by id
    held = [h for h in held if h.get("id") != entry["id"]]
    held.append(entry)
    _save_held(held)


def surface_due(trigger: str) -> list[dict]:
    """
    Pop and return all unsurfaced items whose shield_timing matches trigger.
    Marks them surfaced=True so they won't appear again.
    Also returns any lingering interrupt_now items.
    """
    held = _load_held()
    to_surface = []
    remaining  = []

    for h in held:
        if h.get("surfaced"):
            remaining.append(h)
            continue
        t = h.get("shield_timing", "after_current_block")
        if t == trigger or t == "interrupt_now":
            h["surfaced"] = True
            to_surface.append(h)
        else:
            remaining.append(h)

    _save_held(remaining + to_surface)
    return to_surface


def _held_unsurfaced() -> list[dict]:
    return [h for h in _load_held() if not h.get("surfaced")]


def _held_summary_text() -> str:
    held = _held_unsurfaced()
    if not held:
        return "No items held."
    by_class: dict[str, list] = {}
    for h in held:
        t = h.get("shield_timing", "?")
        by_class.setdefault(t, []).append(h)
    lines = [f"Held items ({len(held)}):"]
    for cls in _TRIGGER_ORDER:
        items = by_class.get(cls, [])
        if items:
            lines.append(f"  {cls} ({len(items)}):")
            for h in items:
                lines.append(f"    • {h['id']}: {h.get('title', '—')}")
    return "\n".join(lines)


# ── Handler ───────────────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t = text.lower().strip()

    if any(k in t for k in ("held items", "focus held", "what's held", "whats held")):
        return [_held_summary_text()]

    if "surface now" in t:
        items = surface_due("interrupt_now")
        if not items:
            return ["No interrupt_now items held."]
        lines = [f"Surfacing {len(items)} item(s):"]
        for h in items:
            lines.append(f"  • {h['id']}: {h.get('title', '—')}")
        return ["\n".join(lines)]

    if "end of day" in t or "eod" in t:
        items = surface_due("end_of_day")
        if not items:
            return ["No end-of-day items held."]
        lines = [f"End-of-day items ({len(items)}):"]
        for h in items:
            lines.append(f"  • {h['id']}: {h.get('title', '—')}")
        return ["\n".join(lines)]

    # Default: focus status
    state  = _load_scheduler_state()
    status = state.get("status", "idle")
    task   = state.get("task", "")
    held   = _held_unsurfaced()
    shield_on = is_focus_active()

    lines = [
        f"Focus Shield: {'ACTIVE' if shield_on else 'off'}",
        f"Scheduler: {status}" + (f" — {task}" if task else ""),
        f"Held items: {len(held)}",
    ]
    if held:
        by_class: dict[str, int] = {}
        for h in held:
            c = h.get("shield_timing", "?")
            by_class[c] = by_class.get(c, 0) + 1
        lines.append("  " + "  ".join(f"{c}: {n}" for c, n in by_class.items()))
    lines.append("\nCommands: 'focus held' · 'surface now' · 'end of day'")
    return ["\n".join(lines)]


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "focus status"
    for line in handle(text):
        print(line)

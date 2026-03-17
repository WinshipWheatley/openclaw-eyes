"""
chief_brainstorm_router.py

Routes synthesized brainstorm items to their correct destination.
Called internally by chief_brainstorm_brain after synthesis, and
directly for backlog management commands.

Route map:
  now     → scheduler (surfaces scheduler command)
  soon    → build_queue (appends to chief_queue_brain)
  later   → backlog
  watch   → watchlist (status=watching)
  archive → archive

Triggered by:
  - Internal call from chief_brainstorm_brain.capture_and_synthesize()
  - "brainstorm queue" / "brainstorm backlog" / "show ideas"
  - "route idea [id] to [target]"
Intent: brainstorm_queue in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/album/brainstorm_log.json
"""

import json
import re
from datetime import datetime
from pathlib import Path

BRAINSTORM_JSON = Path("/mnt/c/OpenClawShared/album/brainstorm_log.json")

_ROUTE_MAP = {
    "now":     "scheduler",
    "soon":    "build_queue",
    "later":   "backlog",
    "watch":   "watchlist",
    "archive": "archive",
}

_STATUS_MAP = {
    "now":     "routed",
    "soon":    "routed",
    "later":   "backlog",
    "watch":   "watching",
    "archive": "archived",
}


# ── Storage ───────────────────────────────────────────────────────────────────

def _load_items() -> list[dict]:
    if BRAINSTORM_JSON.exists():
        try:
            return json.loads(BRAINSTORM_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_items(items: list[dict]) -> None:
    BRAINSTORM_JSON.parent.mkdir(parents=True, exist_ok=True)
    BRAINSTORM_JSON.write_text(json.dumps(items, indent=2), encoding="utf-8")


# ── Route function (called by brainstorm_brain) ───────────────────────────────

def route(item: dict) -> dict:
    """Assign route_target and status based on timing_class. Returns updated item."""
    tc = item.get("timing_class", "later")
    item["route_target"] = _ROUTE_MAP.get(tc, "backlog")
    item["status"]       = _STATUS_MAP.get(tc, "backlog")

    # For "soon" items: push to chief_queue_brain
    if tc == "soon":
        try:
            from chief_queue_brain import handle as queue_handle
            queue_handle(f"queue request: {item['title']} — {item.get('recommended_next_step', '')}")
        except Exception:
            pass

    return item


# ── Handlers ──────────────────────────────────────────────────────────────────

def _handle_reroute(text: str, items: list[dict]) -> list[str]:
    m = re.search(r"route\s+(?:idea\s+)?(bs-\d+)\s+to\s+(\w+)", text, re.IGNORECASE)
    if not m:
        return ["Format: 'route idea BS-0001 to scheduler'"]
    idea_id    = m.group(1).upper()
    new_target = m.group(2).lower()
    for item in items:
        if item.get("idea_id", "").upper() == idea_id:
            item["route_target"] = new_target
            item["status"]       = "re-routed"
            item["notes"].append(
                f"{datetime.now().strftime('%Y-%m-%d')} re-routed to {new_target}"
            )
            _save_items(items)
            return [f"Routed {idea_id} to {new_target}."]
    return [f"Idea {idea_id} not found."]


def _handle_done(text: str, items: list[dict]) -> list[str]:
    m = re.search(r"(bs-\d+)", text, re.IGNORECASE)
    if not m:
        return ["Specify an idea ID. Example: 'brainstorm done BS-0001'"]
    idea_id = m.group(1).upper()
    for item in items:
        if item.get("idea_id", "").upper() == idea_id:
            item["status"] = "done"
            _save_items(items)
            return [f"Marked {idea_id} done."]
    return [f"Idea {idea_id} not found."]


def _handle_list(items: list[dict]) -> list[str]:
    active = [i for i in items if i.get("status") not in ("done", "archived")]
    if not active:
        return ["No active brainstorm items. Say 'brainstorm [idea]' to capture one."]
    lines = [f"Brainstorm backlog ({len(active)} active of {len(items)} total):"]
    for tc in ("now", "soon", "later", "watch"):
        group = [i for i in active if i.get("timing_class") == tc]
        if not group:
            continue
        lines.append(f"\n{tc.capitalize()}:")
        for item in group:
            lines.append(f"  {item['idea_id']}: {item.get('title', '—')}")
            lines.append(f"    {item.get('recommended_next_step', '—')}")
    return ["\n".join(lines)]


# ── Public entry point ────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t     = text.lower().strip()
    items = _load_items()

    if "route idea" in t or re.search(r"route\s+bs-\d+", t):
        return _handle_reroute(text, items)

    if re.search(r"done\s+bs-\d+|bs-\d+\s+done", t):
        return _handle_done(text, items)

    if any(k in t for k in ("brainstorm queue", "brainstorm backlog", "show ideas", "idea list")):
        return _handle_list(items)

    return _handle_list(items)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "brainstorm queue"
    for line in handle(text):
        print(line)

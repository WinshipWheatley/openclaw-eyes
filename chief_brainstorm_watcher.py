"""
chief_brainstorm_watcher.py

Watches brainstorm items that have timing conditions. Surfaces items
when the right implementation moment arrives.

Watches for:
  - Items with status=watching and a trigger_condition
  - Items with timing_class=now that haven't been acted on

Triggered by:
  - "brainstorm status" / "brainstorm watch" / "watching ideas"
  - "brainstorm check [context]" — surfaces items whose condition matches context
  - "brainstorm check" — summary of all active items
Intent: brainstorm_watch in chief_router.py

Saves to: /mnt/c/OpenClawShared/openclaw-vault/System/Brainstorm Log.md (status updates)
"""

import json
import re
from pathlib import Path

BRAINSTORM_JSON = Path("/mnt/c/OpenClawShared/album/brainstorm_log.json")
BRAINSTORM_MD   = Path("/mnt/c/OpenClawShared/openclaw-vault/System/Brainstorm Log.md")


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


# ── Condition check ───────────────────────────────────────────────────────────

def _check_conditions(items: list[dict], context: str) -> list[dict]:
    """Return watching items whose trigger condition has keyword overlap with context."""
    ctx = context.lower()
    surfaced = []
    for item in items:
        if item.get("status") != "watching":
            continue
        cond = item.get("trigger_condition", "").lower()
        if not cond:
            continue
        # Keyword overlap: any meaningful word from cond appears in context
        cond_words = set(re.findall(r"\b\w{4,}\b", cond))  # words 4+ chars
        if any(w in ctx for w in cond_words):
            surfaced.append(item)
    return surfaced


# ── Handlers ──────────────────────────────────────────────────────────────────

def _handle_check(text: str, items: list[dict]) -> list[str]:
    context = re.sub(r"brainstorm\s+(check|watch|status)", "", text, flags=re.IGNORECASE).strip()
    if context:
        surfaced = _check_conditions(items, context)
        if surfaced:
            lines = [f"⚡ {len(surfaced)} idea(s) ready based on: '{context}'\n"]
            for item in surfaced:
                lines.append(f"  {item['idea_id']}: {item.get('title', '—')}")
                lines.append(f"    Trigger was: {item.get('trigger_condition', '—')}")
                lines.append(f"    Next: {item.get('recommended_next_step', '—')}")
            lines.append("\nSay 'brainstorm done BS-XXXX' to mark complete.")
            return ["\n".join(lines)]
        return [f"No watching items match context: '{context}'"]

    # No context — full status summary
    return _handle_status(items)


def _handle_status(items: list[dict]) -> list[str]:
    if not items:
        return ["No brainstorm items yet. Say 'brainstorm [idea]' to capture one."]

    now_items  = [i for i in items if i.get("timing_class") == "now"
                  and i.get("status") not in ("done", "archived")]
    soon_items = [i for i in items if i.get("timing_class") == "soon"
                  and i.get("status") not in ("done", "archived")]
    watching   = [i for i in items if i.get("status") == "watching"]
    done_ct    = sum(1 for i in items if i.get("status") == "done")
    archived_ct = sum(1 for i in items if i.get("status") == "archived")

    lines = [f"**Brainstorm Status** ({len(items)} total)\n"]

    if now_items:
        lines.append(f"Now ({len(now_items)}):")
        for item in now_items:
            lines.append(f"  • {item['idea_id']}: {item.get('title', '—')}")
            lines.append(f"    → {item.get('recommended_next_step', '—')}")

    if soon_items:
        lines.append(f"\nSoon ({len(soon_items)}):")
        for item in soon_items:
            lines.append(f"  • {item['idea_id']}: {item.get('title', '—')}")

    if watching:
        lines.append(f"\nWatching ({len(watching)}):")
        for item in watching:
            lines.append(f"  • {item['idea_id']}: {item.get('title', '—')}")
            lines.append(f"    Waiting for: {item.get('trigger_condition', 'unspecified')}")

    lines.append(f"\nDone: {done_ct} | Archived: {archived_ct}")
    lines.append("Say 'brainstorm check [context]' to surface watching items.")
    return ["\n".join(lines)]


# ── Public entry point ────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    items = _load_items()
    return _handle_check(text, items)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "brainstorm status"
    for line in handle(text):
        print(line)

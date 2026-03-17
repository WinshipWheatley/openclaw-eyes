"""
chief_website_coordinator.py

Site project manager for deeppocketrecords.com. Tracks what's been built,
what still needs building, and prioritizes the next action. Knows brand
rules for both Winship/DPR and Fundo. Can hand specific jobs to
chief_website_creative.py or flag items for human execution.

Triggered by:
  - "site status" / "what does the site need"
  - "website update [what changed]"
  - "site roadmap"
  - "brand rules"
  - "website update [section] done"
Intent: website_coordinator in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/business/website_state.json  (source of truth)
  - /mnt/c/OpenClawShared/openclaw-vault/Website/Coordinator Log.md
"""

import json
import re
from datetime import datetime
from pathlib import Path

from chief_llm import claude_call as ollama_call

# ── Paths ───────────────────────────────────────────────────────────────────────

BUSINESS_DIR     = Path("/mnt/c/OpenClawShared/business")
WEBSITE_JSON     = BUSINESS_DIR / "website_state.json"
VAULT_WEB_DIR    = Path("/mnt/c/OpenClawShared/openclaw-vault/Website")
COORDINATOR_MD   = VAULT_WEB_DIR / "Coordinator Log.md"

# ── Site sections definition ─────────────────────────────────────────────────────

# Each section: id, label, priority (lower = higher priority), human_only flag,
# status: not_started / in_progress / done / blocked
SITE_SECTIONS = [
    {
        "id":         "fundo_teaser",
        "label":      "Fundo Teaser Page",
        "priority":   1,
        "human_only": False,
        "notes":      "Anonymous one-pager. Mystery text + dark visual. No face. First launch test.",
    },
    {
        "id":         "homepage",
        "label":      "Homepage Hero",
        "priority":   2,
        "human_only": False,
        "notes":      "Headline, sub-headline, CTA button, hero image direction.",
    },
    {
        "id":         "about",
        "label":      "About Page",
        "priority":   3,
        "human_only": False,
        "notes":      "Winship bio (long), label story, mission.",
    },
    {
        "id":         "music",
        "label":      "Music / Catalog Page",
        "priority":   4,
        "human_only": False,
        "notes":      "12 songs with descriptions, embeds/players when available.",
    },
    {
        "id":         "booking",
        "label":      "Booking Page",
        "priority":   5,
        "human_only": True,
        "notes":      "Contact form + rates. Requires human to set up form backend.",
    },
    {
        "id":         "contact",
        "label":      "Contact Page",
        "priority":   6,
        "human_only": True,
        "notes":      "Simple email link + social handles. Human sets up mailto or form.",
    },
    {
        "id":         "seo_meta",
        "label":      "SEO Meta Tags",
        "priority":   7,
        "human_only": False,
        "notes":      "Title tags, descriptions, og:image for all pages.",
    },
    {
        "id":         "analytics",
        "label":      "Analytics Setup",
        "priority":   8,
        "human_only": True,
        "notes":      "Google Analytics or Plausible. Requires account setup.",
    },
]

# ── Brand rules (for brand rules command) ────────────────────────────────────────

DPR_BRAND_RULES = {
    "colors":     "Deep navy (#0A1628), warm gold (#C9A84C), white (#FFFFFF), warm grey (#8B8B8B)",
    "typography": "Serif for headlines (Playfair Display or similar). Sans-serif for body (Inter or similar).",
    "tone":       "Sophisticated but not pretentious. Warm, confident, cinematic. No clichés.",
    "imagery":    "Ocean at night, warm interiors, vinyl records, Annapolis architecture.",
    "logo":       "Wordmark-first. Deep Pocket Records in clean serif. Pocket watch motif optional.",
    "avoid":      "Stock photo vibes. Neon. Comic Sans or brush script. Anything that screams 'musician website template'.",
}

FUNDO_BRAND_RULES = {
    "colors":     "Near-black (#0D0D0D), dark teal (#0A2E2E), white text only, no warm tones.",
    "typography": "Monospace or sparse grotesque. Lowercase preferred. No serifs.",
    "tone":       "Opaque. Slightly off. Feels like it's from somewhere you can't name.",
    "imagery":    "No faces. Thrift store finds. Vinyl labels. Texture. Shadow. Found objects.",
    "logo":       "FUNDO in sparse caps. No icon needed. The name IS the logo.",
    "avoid":      "Any photo of a person. Anything that could identify a location. Warmth. Familiarity.",
}

# ── State management ─────────────────────────────────────────────────────────────

def _load_state() -> dict:
    if WEBSITE_JSON.exists():
        try:
            return json.loads(WEBSITE_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Initialize with all sections as not_started
    return {
        "sections": {s["id"]: {"status": "not_started", "updated": "", "notes": s["notes"]} for s in SITE_SECTIONS},
        "updates":  [],
        "created":  datetime.now().strftime("%Y-%m-%d"),
    }


def _save_state(data: dict) -> None:
    BUSINESS_DIR.mkdir(parents=True, exist_ok=True)
    WEBSITE_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _section_status(state: dict, section_id: str) -> str:
    return state["sections"].get(section_id, {}).get("status", "not_started")


# ── Coordinator log writer ────────────────────────────────────────────────────────

def _write_coordinator_md(state: dict) -> None:
    VAULT_WEB_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    status_icon = {"not_started": "⬜", "in_progress": "🔄", "done": "✅", "blocked": "🚫"}

    rows = ""
    for s in SITE_SECTIONS:
        sid    = s["id"]
        status = _section_status(state, sid)
        icon   = status_icon.get(status, "⬜")
        flag   = " _(human)_" if s["human_only"] else ""
        rows  += f"| {s['priority']} | {icon} {s['label']}{flag} | {status} |\n"

    recent = state.get("updates", [])[-10:]
    update_rows = "\n".join(
        f"| {u['timestamp'][:16]} | {u['section']} | {u['note']} |"
        for u in reversed(recent)
    ) or "| — | — | — |"

    content = (
        "---\ntype: website-coordinator-log\n"
        f"last_updated: {today}\n---\n\n"
        "# Website Coordinator Log\n\n"
        "_Managed by `chief_website_coordinator.py` — do not edit manually._\n\n"
        "## Site Sections Status\n\n"
        "| # | Section | Status |\n|---|---|---|\n"
        + rows + "\n"
        "## Recent Updates\n\n"
        "| Time | Section | Note |\n|---|---|---|\n"
        + update_rows + "\n"
    )
    COORDINATOR_MD.write_text(content, encoding="utf-8")


# ── Prompts ──────────────────────────────────────────────────────────────────────

_PRIORITY_PROMPT = """\
You are the website coordinator for Deep Pocket Records (deeppocketrecords.com).

Current site section statuses:
{statuses}

Based on these statuses, write a concise action plan:
1. What is the single most important next action? (be specific)
2. What 2-3 things come after that?
3. Any blockers or dependencies to flag?

Write in plain text, direct and actionable. No markdown formatting. Max 8 sentences."""

_UPDATE_PARSE_PROMPT = """\
A website update message was received. Extract the section being updated and the status.

Known sections: {section_ids}
Valid statuses: not_started, in_progress, done, blocked

Message: {text}

Return JSON: {{"section_id": "...", "status": "...", "note": "..."}}
If you cannot identify a section, use section_id: "general"
Return only valid JSON."""


# ── Handlers ─────────────────────────────────────────────────────────────────────

def _handle_status(state: dict) -> list[str]:
    status_lines = []
    for s in SITE_SECTIONS:
        sid    = s["id"]
        status = _section_status(state, sid)
        flag   = " [HUMAN REQUIRED]" if s["human_only"] else ""
        status_lines.append(f"  P{s['priority']} {s['label']}{flag}: {status}")

    statuses_text = "\n".join(status_lines)
    prompt        = _PRIORITY_PROMPT.format(statuses=statuses_text)
    analysis      = ollama_call(prompt, timeout=30)

    if not analysis:
        # Fallback: find first not_started section
        next_item = next(
            (s for s in SITE_SECTIONS if _section_status(state, s["id"]) == "not_started"),
            None
        )
        analysis = f"Next priority: {next_item['label']}" if next_item else "All sections started."

    _write_coordinator_md(state)
    return [f"Site Status:\n\n{statuses_text}\n\n---\n\n{analysis}"]


def _handle_roadmap(state: dict) -> list[str]:
    lines = ["deeppocketrecords.com — Full Roadmap\n"]
    for s in SITE_SECTIONS:
        sid    = s["id"]
        status = _section_status(state, sid)
        flag   = " [human required]" if s["human_only"] else ""
        lines.append(f"  [{status.upper()}] P{s['priority']} — {s['label']}{flag}")
        if s["notes"]:
            lines.append(f"         {s['notes']}")
    _write_coordinator_md(state)
    return ["\n".join(lines)]


def _handle_update(text: str, state: dict) -> list[str]:
    section_ids = ", ".join(s["id"] for s in SITE_SECTIONS)
    prompt      = _UPDATE_PARSE_PROMPT.format(section_ids=section_ids, text=text)

    from chief_llm import claude_json
    parsed = claude_json(prompt, timeout=20)
    if not isinstance(parsed, dict):
        parsed = {"section_id": "general", "status": "in_progress", "note": text[:80]}

    sid    = parsed.get("section_id", "general")
    status = parsed.get("status", "in_progress")
    note   = parsed.get("note", text[:80])

    if sid in state["sections"]:
        state["sections"][sid]["status"]  = status
        state["sections"][sid]["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    state.setdefault("updates", []).append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "section":   sid,
        "status":    status,
        "note":      note,
    })
    _save_state(state)
    _write_coordinator_md(state)

    section_label = next((s["label"] for s in SITE_SECTIONS if s["id"] == sid), sid)
    return [f"Updated: {section_label} → {status.upper()}\nNote: {note}"]


def _handle_brand_rules() -> list[str]:
    lines = ["Brand Rules — Deep Pocket Records (DPR)\n"]
    for k, v in DPR_BRAND_RULES.items():
        lines.append(f"  {k.upper()}: {v}")
    lines.append("\n---\nBrand Rules — FUNDO\n")
    for k, v in FUNDO_BRAND_RULES.items():
        lines.append(f"  {k.upper()}: {v}")
    return ["\n".join(lines)]


# ── Public entry point ───────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t     = text.lower().strip()
    state = _load_state()

    if any(k in t for k in ("brand rules", "brand guide", "brand standards")):
        return _handle_brand_rules()

    if any(k in t for k in ("roadmap", "full list", "everything we need")):
        return _handle_roadmap(state)

    if any(k in t for k in ("website update", "mark", "section done", "section complete", "set status")):
        return _handle_update(text, state)

    # default: status + next action
    return _handle_status(state)


# ── CLI ──────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "site status"
    print(f"Running website coordinator brain: '{text}'\n")
    for line in handle(text):
        print(line)
    print(f"\nState JSON: {WEBSITE_JSON}")
    print(f"Coordinator Log: {COORDINATOR_MD}")

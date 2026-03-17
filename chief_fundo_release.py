"""
chief_fundo_release.py

Manages the release pipeline for Fundo tracks. When a track is ready,
generates a release checklist and coordinates handoff to marketing and
DistroKid submission.

Flow:
  1. Load session data for the named track from fundo_sessions.json
  2. Run release readiness check (Suno approved, elements complete)
  3. Generate release checklist: mix check, archive Suno ref, DistroKid
     submission fields, social content queue
  4. Save release record to vault/Fundo/Releases/

Triggered by:
  - "fundo release [song]" / "release fundo [song]"
  - "release checklist [song]" / "fundo ready [song]"
Intent: fundo_release in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/business/fundo_releases.json
  - openclaw-vault/Fundo/Releases/[slug].md
"""

import json
import re
from datetime import datetime
from pathlib import Path

from chief_llm import ollama_call

# ── Paths ─────────────────────────────────────────────────────────────────────

BUSINESS_DIR   = Path("/mnt/c/OpenClawShared/business")
SESSIONS_JSON  = BUSINESS_DIR / "fundo_sessions.json"
RELEASES_JSON  = BUSINESS_DIR / "fundo_releases.json"
RELEASES_DIR   = Path("/mnt/c/OpenClawShared/openclaw-vault/Fundo/Releases")

# ── DistroKid submission fields ───────────────────────────────────────────────

DISTROKID_FIELDS = [
    "Track title",
    "Primary artist: FUNDO",
    "Genre (primary): Electronic / World",
    "Genre (secondary): Afrobeats",
    "Release date (choose Tuesday for algorithmic benefit)",
    "Cover art: 3000×3000px JPG, no explicit text, no logos",
    "ISRC: auto-assign or enter existing",
    "Lyrics (optional — upload .txt)",
    "Content advisory: clean / explicit",
    "Stores: All (ensure TikTok/Instagram enabled)",
    "Songwriter/composer credits",
    "Publisher: Deep Pocket Records",
]

# ── Social content queue items ────────────────────────────────────────────────

SOCIAL_QUEUE_ITEMS = [
    "Teaser clip (15s) — Instagram Reel + TikTok",
    "Cover art reveal — Instagram post",
    "Release day post — all platforms",
    "Behind-the-scenes production clip — Instagram Story",
    "DistroKid link-in-bio update",
    "Spotify pre-save link (if applicable)",
]

# ── Storage ───────────────────────────────────────────────────────────────────

def _load_sessions() -> list[dict]:
    if SESSIONS_JSON.exists():
        try:
            data = json.loads(SESSIONS_JSON.read_text(encoding="utf-8"))
            # Handle both list and {"sessions": [...]} formats
            if isinstance(data, list):
                return data
            return data.get("sessions", [])
        except Exception:
            pass
    return []


def _load_releases() -> list[dict]:
    if RELEASES_JSON.exists():
        try:
            return json.loads(RELEASES_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_releases(releases: list[dict]) -> None:
    RELEASES_JSON.parent.mkdir(parents=True, exist_ok=True)
    RELEASES_JSON.write_text(json.dumps(releases, indent=2), encoding="utf-8")


def _find_session(sessions: list[dict], name: str) -> dict | None:
    name_lower = name.lower().strip()
    for s in sessions:
        if name_lower in s.get("name", "").lower():
            return s
    return None


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower().strip()).strip("-")


# ── Readiness check ───────────────────────────────────────────────────────────

def _check_readiness(session: dict) -> dict:
    """Return a dict of checks and whether they pass."""
    elements_done = session.get("elements_done", [])
    all_elements = [
        "kick", "bass", "hi_hat_percussion", "world_percussion",
        "pads_chords", "melody_lead", "texture_atmosphere",
        "arrangement", "mix_balance", "final_export",
    ]
    missing_elements = [e for e in all_elements if e not in elements_done]

    return {
        "suno_approved": session.get("suno_approved", False),
        "elements_complete": len(missing_elements) == 0,
        "missing_elements": missing_elements,
        "has_suno_prompt": bool(session.get("suno_prompt")),
        "session_notes": session.get("notes", []),
        "phase": session.get("phase", "unknown"),
    }


# ── LLM checklist builder ─────────────────────────────────────────────────────

_CHECKLIST_PROMPT = """\
You are the release coordinator for FUNDO, an anonymous Afrobeats/World electronic producer.

Track: {name}
Suno prompt (north star reference): {suno_prompt}
Session notes: {notes}
Elements completed: {elements_done}
Readiness: Suno approved={suno_approved}, all elements done={elements_complete}

Write a concise release brief (3-4 sentences):
- State whether the track is ready to release or what's blocking it
- Note the sonic character based on the Suno prompt
- Suggest the best timing/context for this release in the Fundo arc

Be direct. No bullet points in the narrative. Sound like a sharp A&R."""


def _build_narrative(session: dict, readiness: dict) -> str:
    notes_str = "; ".join(session.get("notes", [])[-3:]) or "none"
    prompt = _CHECKLIST_PROMPT.format(
        name=session.get("name", "unknown"),
        suno_prompt=(session.get("suno_prompt") or "not yet generated")[:300],
        notes=notes_str,
        elements_done=", ".join(session.get("elements_done", [])) or "none",
        suno_approved=readiness["suno_approved"],
        elements_complete=readiness["elements_complete"],
    )
    result = ollama_call(prompt, timeout=30).strip()
    return result if result else ""


# ── Vault write ───────────────────────────────────────────────────────────────

def _write_release_md(session: dict, readiness: dict, narrative: str) -> Path:
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    name = session.get("name", "unknown")
    slug = _slug(name)
    today = datetime.now().strftime("%Y-%m-%d")

    status = "ready" if (readiness["suno_approved"] and readiness["elements_complete"]) else "in-progress"

    lines = [
        "---",
        f"title: \"{name}\"",
        "type: fundo-release",
        f"status: {status}",
        f"created: {today}",
        "---",
        "",
        f"# Fundo Release: {name}",
        "",
    ]

    if narrative:
        lines += [narrative, ""]

    lines += [
        "## Readiness",
        "",
        f"- Suno prompt approved: {'✓' if readiness['suno_approved'] else '✗'}",
        f"- All elements complete: {'✓' if readiness['elements_complete'] else '✗'}",
    ]
    if readiness["missing_elements"]:
        lines.append(f"- Missing: {', '.join(readiness['missing_elements'])}")

    if session.get("suno_prompt"):
        lines += ["", "## Suno Reference Prompt", "", f"```", session["suno_prompt"][:500], "```"]

    lines += [
        "",
        "## DistroKid Submission Checklist",
        "",
    ]
    for field in DISTROKID_FIELDS:
        lines.append(f"- [ ] {field}")

    lines += [
        "",
        "## Social Content Queue",
        "",
    ]
    for item in SOCIAL_QUEUE_ITEMS:
        lines.append(f"- [ ] {item}")

    if session.get("notes"):
        lines += ["", "## Session Notes", ""]
        for note in session["notes"][-10:]:
            lines.append(f"- {note}")

    path = RELEASES_DIR / f"{slug}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ── Handlers ──────────────────────────────────────────────────────────────────

def _handle_release(song_name: str) -> list[str]:
    sessions = _load_sessions()
    session = _find_session(sessions, song_name)

    if not session:
        # No session found — generate a blank checklist
        blank = {
            "name": song_name.title(),
            "suno_approved": False,
            "elements_done": [],
            "suno_prompt": "",
            "notes": [],
            "phase": "not_started",
        }
        readiness = _check_readiness(blank)
        narrative = f"No active Fundo session found for '{song_name}'. Release checklist generated as a template — run 'fundo session {song_name}' to start production."
        md_path = _write_release_md(blank, readiness, narrative)

        # Save release record
        releases = _load_releases()
        releases.append({
            "name": blank["name"],
            "created": datetime.now().isoformat(),
            "status": "template",
        })
        _save_releases(releases)

        return [
            f"No active session for '{song_name}'. Release template created.\n\n"
            f"DistroKid checklist and social queue saved to:\n"
            f"vault/Fundo/Releases/{_slug(song_name)}.md\n\n"
            f"Run 'fundo session {song_name}' to start production."
        ]

    readiness = _check_readiness(session)
    narrative = _build_narrative(session, readiness)
    md_path = _write_release_md(session, readiness, narrative)

    # Save release record
    releases = _load_releases()
    releases = [r for r in releases if r.get("name", "").lower() != session["name"].lower()]
    releases.append({
        "name": session["name"],
        "created": datetime.now().isoformat(),
        "status": "ready" if (readiness["suno_approved"] and readiness["elements_complete"]) else "in-progress",
    })
    _save_releases(releases)

    # Queue social content to marketing brain
    _queue_social_content(session["name"])

    lines = []
    if narrative:
        lines.append(narrative)
        lines.append("")

    if readiness["suno_approved"] and readiness["elements_complete"]:
        lines.append(f"✓ {session['name']} is release-ready.")
    else:
        blockers = []
        if not readiness["suno_approved"]:
            blockers.append("Suno prompt not yet approved")
        if not readiness["elements_complete"]:
            blockers.append(f"Incomplete elements: {', '.join(readiness['missing_elements'])}")
        lines.append(f"⚠ Not yet ready. Blockers: {'; '.join(blockers)}")

    lines += [
        "",
        "Release checklist saved to vault/Fundo/Releases/",
        "DistroKid fields and social queue included.",
        "Say 'marketing ideas fundo' to draft social posts.",
    ]
    return ["\n".join(lines)]


def _queue_social_content(name: str) -> None:
    """Notify content log that social content is needed for this release."""
    try:
        content_log = Path("/mnt/c/OpenClawShared/album/content_log.json")
        if content_log.exists():
            data = json.loads(content_log.read_text(encoding="utf-8"))
        else:
            data = {"entries": []}
        entries = data.get("entries", [])
        # Check if already queued
        if not any(e.get("song") == name and e.get("status") in ("suggested", "in_progress") for e in entries):
            entries.append({
                "id": f"FUNDO-REL-{_slug(name).upper()[:8]}",
                "title": f"Release campaign: {name}",
                "platform": "Instagram, TikTok",
                "size": "short_form",
                "song": name,
                "status": "suggested",
                "date_suggested": datetime.now().strftime("%Y-%m-%d"),
            })
            data["entries"] = entries
            content_log.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def _handle_list() -> list[str]:
    """Show all release records."""
    releases = _load_releases()
    if not releases:
        return ["No Fundo releases tracked yet. Say 'fundo release [song]' to start."]
    lines = [f"Fundo release pipeline ({len(releases)} tracks):"]
    for r in releases:
        status_icon = "✓" if r.get("status") == "ready" else "⚠" if r.get("status") == "in-progress" else "○"
        lines.append(f"  {status_icon} {r['name']} — {r.get('status', 'template')}")
    return ["\n".join(lines)]


# ── Public entry point ────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t = text.lower().strip()

    # "fundo releases" / "release status" → list all
    if t in ("fundo releases", "release status", "fundo release status"):
        return _handle_list()

    # Extract song name from "fundo release [song]" / "release fundo [song]" etc.
    patterns = [
        r"fundo\s+release\s+(.+)",
        r"release\s+fundo\s+(.+)",
        r"release\s+checklist\s+(.+)",
        r"fundo\s+ready\s+(.+)",
    ]
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            song = m.group(1).strip()
            return _handle_release(song)

    return ["Specify a track. Example: 'fundo release track 1' or 'fundo release [song name]'"]


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "fundo release track 1"
    for line in handle(text):
        print(line)

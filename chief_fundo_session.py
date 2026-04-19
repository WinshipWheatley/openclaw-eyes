"""
chief_fundo_session.py

Production coaching brain for building Fundo tracks. Two-phase flow:

  Phase 1: Generates a detailed Suno prompt (north star vision). User
           pastes into Suno, listens, and approves or revises.
  Phase 2: After approval, coaches element by element with specific,
           tool-aware instructions. Paint by number — brain picks the
           colors, Winship decides how to paint.

Tool awareness:
  - MPC: beat programming, sample layout, pad assignments
  - Ableton 11 (PC): arrangement, FX chains, mixing, export
  - Logic (Mac): final mixing, mastering, plugin suggestions

Instruction style — specific, not vague:
  "On Ableton track 1 (KICK), place a 909 kick on every beat at 126bpm.
   Layer an 808 sub at -12dB on beats 1 and 3. Sidechain 808 to hi-hat
   bus: 30ms attack, 80ms release..."

Triggered by:
  - "fundo session" / "work on fundo" / "new fundo track"
  - "fundo [song name]" — loads or creates a session for that track
  - "approve" — approves the Suno prompt, triggers Phase 2
  - "revise [notes]" — revises the prompt with feedback
Intent: fundo_session in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/business/fundo_sessions.json  (source of truth)
  - /mnt/c/OpenClawShared/openclaw-vault/Fundo/Sessions/[SLUG].md
"""

import json
import re
from datetime import datetime
from pathlib import Path

from chief_llm import claude_call as deferred_fundo_session_call
from chief_llm import ollama_call

# ── Paths ────────────────────────────────────────────────────────────────────────

BUSINESS_DIR      = Path("/mnt/c/OpenClawShared/business")
SESSIONS_JSON     = BUSINESS_DIR / "fundo_sessions.json"
FUNDO_SESSIONS_MD = Path("/mnt/c/OpenClawShared/openclaw-vault/Fundo/Sessions")

TARGET_SONGS = 15

# ── Fundo sonic DNA (embedded — this is the brief) ───────────────────────────────

FUNDO_DNA = """\
FUNDO — Production Brief

NAME: FUNDO (means "deep" in Portuguese)
PERSONA: Anonymous electronic producer. No face, no real name, no location revealed.
TARGET: 15 tracks

SONIC DNA:
  ROOT: World rhythm — bossa nova syncopation, Cuban percussion (conga, quinto, bongos),
        Fela Kuti Afrobeat (interlocking horn lines, polyrhythmic drums, extended grooves)
  FILTER: Baltimore club (fast 130bpm+ hi-hat patterns, vocal chops), Miami house
          (lush pads, deep bass, soulful), UK drum and bass / jungle (170bpm+ breaks,
          sub-bass weight, amen chops), German techno (minimal, hypnotic, industrial edge),
          Empire of the Sun (cosmic synths, euphoric energy, cinematic scale)

MOOD ARC (15 songs):
  1-3:   Arrival — deep, hypnotic, slow-building. World roots upfront.
  4-6:   Rising — tempo climbs, bass gets heavier, polyrhythm intensifies.
  7-9:   Peak — full fusion. All DNA present. Dancefloor energy.
  10-11: Descent — stripped back, emotional, world instruments come forward.
  12-13: Reflection — slow, textural, almost ambient but rhythmic.
  14-15: Exit — cosmic, open-ended. Listener doesn't know if it ended or continued without them.

TOOLS:
  MPC: Beat programming, sample chopping, pad assignments, swing percentage
  Ableton 11 (PC): Arrangement, FX chains, automation, clip launching, final mix prep
  Logic (Mac): Final mixing, mastering, plugin access (Logic Pro instruments), bounce

TEMPO RANGES:
  Afrobeat / Bossa: 96-112 bpm
  Baltimore club: 130-136 bpm
  House: 120-128 bpm
  DnB / Jungle: 160-174 bpm
  Techno: 130-145 bpm
  Hybrid tracks: pick one grid, layer polyrhythm on top"""

# ── Session state ─────────────────────────────────────────────────────────────────

def _load_sessions() -> dict:
    if SESSIONS_JSON.exists():
        try:
            return json.loads(SESSIONS_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"sessions": [], "active_slug": None}


def _save_sessions(data: dict) -> None:
    BUSINESS_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _get_session(data: dict, slug: str) -> dict | None:
    return next((s for s in data["sessions"] if s["slug"] == slug), None)


def _create_session(data: dict, name: str) -> dict:
    slug = _slug(name)
    session = {
        "slug":           slug,
        "name":           name,
        "created":        datetime.now().strftime("%Y-%m-%d %H:%M"),
        "phase":          "suno",        # suno | coaching
        "suno_prompt":    "",
        "approved":       False,
        "revision_notes": [],
        "position":       len(data["sessions"]) + 1,
        "elements":       [],            # coached elements so far
        "notes":          [],
    }
    data["sessions"].append(session)
    data["active_slug"] = slug
    return session


# ── Phase 1: Suno prompt generation ──────────────────────────────────────────────

_SUNO_PROMPT_TEMPLATE = """\
{dna}

Generate a detailed Suno prompt for Fundo track #{position}: "{name}".

The Suno prompt is the north star vision — it will never be released, it is only
used to hear the musical idea quickly so we can decide if the direction is right.

The prompt should include:
1. GENRE / STYLE: specific genre blend from the DNA above (pick the right position in the arc)
2. TEMPO: exact BPM
3. KEY / SCALE: key and scale/mode
4. MOOD: 3-5 adjectives
5. INSTRUMENTS: specific instruments and their role
6. STRUCTURE: verse/chorus/breakdown layout (e.g. intro 8 bars, verse 16...)
7. REFERENCE ARTISTS: 2-3 specific artists this should sound like
8. SUNO STYLE TAGS: 8-12 comma-separated tags for Suno's style field
9. TITLE SUGGESTION: a cryptic single-word or two-word title appropriate for Fundo

Format it as a clean brief that can be pasted directly into Suno's prompt field.
Return the brief only — no explanations, no markdown headers."""


def _generate_suno_prompt(session: dict) -> str:
    prompt = _SUNO_PROMPT_TEMPLATE.format(
        dna=FUNDO_DNA,
        position=session["position"],
        name=session["name"],
    )
    result = ollama_call(prompt, timeout=40, task_class="chief_structured_plan")
    return result or f"Suno prompt generation failed for '{session['name']}'. Check local model routing."


# ── Phase 2: Element coaching ─────────────────────────────────────────────────────

_ELEMENT_ORDER = [
    "kick",
    "bass",
    "hi_hat_percussion",
    "world_percussion",
    "pads_chords",
    "melody_lead",
    "texture_atmosphere",
    "arrangement",
    "mix_balance",
    "final_export",
]

_ELEMENT_LABELS = {
    "kick":              "Kick Drum Foundation",
    "bass":              "Bass Line",
    "hi_hat_percussion": "Hi-Hat & Percussive Grid",
    "world_percussion":  "World Percussion Layer",
    "pads_chords":       "Pads & Chord Stabs",
    "melody_lead":       "Melody / Lead Line",
    "texture_atmosphere":"Texture & Atmosphere",
    "arrangement":       "Full Arrangement",
    "mix_balance":       "Mix Balance",
    "final_export":      "Final Export",
}

_COACHING_PROMPT = """\
{dna}

TRACK: "{name}" (Track #{position})
APPROVED SUNO VISION:
{suno_prompt}

ELEMENTS ALREADY COACHED: {coached_list}

Now coach the element: {element_label}

Rules for your coaching instructions:
- Be SPECIFIC. Not "make it funky." Say: "Place a 909 kick on beats 1, 2, 3, 4 at 128bpm."
- Name the TOOL explicitly: "In Ableton, on Track 1 (KICK)..." or "On your MPC, pad A1..."
- Give EXACT values: BPM, dB levels, ms for attack/release, note names, bar counts
- If there are multiple options, give the BEST one first with one alternative
- Explain WHY this choice serves the track's DNA
- End with: "Tell me when this element is set. Next: [next element]."

Return plain text coaching instructions only."""


def _coach_next_element(session: dict) -> str:
    coached = session.get("elements", [])
    remaining = [e for e in _ELEMENT_ORDER if e not in coached]
    if not remaining:
        return (
            f"All elements coached for '{session['name']}'. "
            "The track is built! Do a final listen and use 'fundo session notes [anything]' "
            "to log observations before moving to the next track."
        )
    next_element = remaining[0]
    label        = _ELEMENT_LABELS[next_element]
    coached_list = ", ".join(_ELEMENT_LABELS[e] for e in coached) or "none yet"

    prompt = _COACHING_PROMPT.format(
        dna=FUNDO_DNA,
        name=session["name"],
        position=session["position"],
        suno_prompt=session.get("suno_prompt", ""),
        coached_list=coached_list,
        element_label=label,
    )
    result = deferred_fundo_session_call(prompt, timeout=45)
    return result or f"Coaching unavailable for {label} — check Claude API."


# ── Release handoff ──────────────────────────────────────────────────────────────

def _queue_release_handoff(session: dict) -> bool:
    """If all 10 elements are done, trigger fundo_release and return True. Idempotent."""
    if set(session.get("elements", [])) < set(_ELEMENT_ORDER):
        return False  # not all done yet

    # Idempotency check — skip if a release entry already exists
    releases_json = Path("/mnt/c/OpenClawShared/business/fundo_releases.json")
    try:
        if releases_json.exists():
            data = json.loads(releases_json.read_text(encoding="utf-8"))
            releases = data if isinstance(data, list) else data.get("releases", [])
            slug = session["slug"]
            if any(r.get("slug") == slug for r in releases):
                return False
    except Exception:
        pass

    try:
        from chief_fundo_release import handle as release_handle
        release_handle(f"fundo release {session['name']}")
        return True
    except Exception:
        return False


# ── Vault note writer ─────────────────────────────────────────────────────────────

def _write_session_md(session: dict) -> None:
    FUNDO_SESSIONS_MD.mkdir(parents=True, exist_ok=True)
    slug   = session["slug"]
    path   = FUNDO_SESSIONS_MD / f"{slug}.md"
    today  = datetime.now().strftime("%Y-%m-%d %H:%M")
    phase  = "✅ Coaching" if session["approved"] else "🎵 Suno Vision"
    coached = ", ".join(_ELEMENT_LABELS.get(e, e) for e in session.get("elements", [])) or "_none yet_"
    notes  = "\n".join(f"- {n}" for n in session.get("notes", [])) or "_no notes_"
    revs   = "\n".join(f"- {r}" for r in session.get("revision_notes", [])) or "_none_"

    content = (
        f"---\ntype: fundo-session\nslug: {slug}\nphase: {phase}\n"
        f"last_updated: {today}\n---\n\n"
        f"# Fundo Session — {session['name']}\n\n"
        f"**Position:** Track #{session['position']} of {TARGET_SONGS}  \n"
        f"**Phase:** {phase}  \n"
        f"**Created:** {session['created']}\n\n"
        "## Suno Prompt\n\n"
        f"```\n{session.get('suno_prompt', '_(not generated yet)_')}\n```\n\n"
        "## Revision Notes\n\n" + revs + "\n\n"
        "## Elements Coached\n\n" + coached + "\n\n"
        "## Session Notes\n\n" + notes + "\n"
    )
    path.write_text(content, encoding="utf-8")


# ── Public entry point ────────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t    = text.lower().strip()
    data = _load_sessions()

    # ── Approve current Suno prompt ──────────────────────────────────────────────
    if t == "approve" or t.startswith("approve "):
        slug = data.get("active_slug")
        if not slug:
            return ["No active Fundo session. Start one with 'new fundo track [name]'."]
        session = _get_session(data, slug)
        if not session:
            return ["No active Fundo session found."]
        session["approved"] = True
        session["phase"]    = "coaching"
        _save_sessions(data)
        _write_session_md(session)
        coaching = _coach_next_element(session)
        return [
            f"✅ Suno vision approved for '{session['name']}'.\n\n"
            f"Starting build coaching — Track #{session['position']}\n\n"
            + coaching
        ]

    # ── Revise Suno prompt ───────────────────────────────────────────────────────
    if t.startswith("revise"):
        slug = data.get("active_slug")
        if not slug:
            return ["No active Fundo session to revise."]
        session = _get_session(data, slug)
        if not session:
            return ["No active session found."]
        notes = text[6:].strip() or "no specific notes"
        session["revision_notes"].append(notes)

        # Regenerate with revision context
        revise_context = (
            f"Previous prompt:\n{session['suno_prompt']}\n\n"
            f"Revision feedback: {notes}\n\n"
            "Regenerate the Suno prompt incorporating this feedback."
        )
        prompt = _SUNO_PROMPT_TEMPLATE.format(
            dna=FUNDO_DNA + "\n\n" + revise_context,
            position=session["position"],
            name=session["name"],
        )
        new_prompt = ollama_call(prompt, timeout=40, task_class="chief_structured_plan")
        if new_prompt:
            session["suno_prompt"] = new_prompt
            _save_sessions(data)
            _write_session_md(session)
            return [
                f"Revised Suno prompt for '{session['name']}':\n\n{new_prompt}\n\n"
                "Paste this into Suno and listen. Reply 'approve' or 'revise [notes]'."
            ]
        return ["Revision failed — check Claude API."]

    # ── Element coached — mark done ──────────────────────────────────────────────
    if "element done" in t or "next element" in t or "move on" in t:
        slug = data.get("active_slug")
        if not slug:
            return ["No active Fundo session."]
        session = _get_session(data, slug)
        if not session or not session["approved"]:
            return ["Approve the Suno prompt first."]
        coached = session.get("elements", [])
        remaining = [e for e in _ELEMENT_ORDER if e not in coached]
        if remaining:
            session.setdefault("elements", []).append(remaining[0])
            _save_sessions(data)
            _write_session_md(session)
            coaching = _coach_next_element(session)
            reply = [coaching]
            if _queue_release_handoff(session):
                reply.append(f"\n→ Release checklist generated in vault/Fundo/Releases/{session['slug']}.md")
            return reply
        return [f"All elements complete for '{session['name']}'! Great session."]

    # ── Log a session note ────────────────────────────────────────────────────────
    if "session note" in t or "fundo note" in t:
        slug = data.get("active_slug")
        if not slug:
            return ["No active Fundo session."]
        session = _get_session(data, slug)
        if not session:
            return ["No active session found."]
        note = re.sub(r"(session note|fundo note)\s*:?\s*", "", text, flags=re.IGNORECASE).strip()
        session.setdefault("notes", []).append(f"{datetime.now().strftime('%H:%M')} — {note}")
        _save_sessions(data)
        _write_session_md(session)
        return [f"Note logged for '{session['name']}'."]

    # ── Session status ────────────────────────────────────────────────────────────
    if any(k in t for k in ("fundo status", "fundo progress", "how many fundo")):
        sessions = data.get("sessions", [])
        done     = sum(1 for s in sessions if s.get("approved"))
        lines    = [f"Fundo Progress: {len(sessions)}/{TARGET_SONGS} tracks started, {done} approved\n"]
        for s in sessions:
            phase = "✅ approved" if s["approved"] else "🎵 suno vision"
            elems = len(s.get("elements", []))
            lines.append(f"  Track #{s['position']}: {s['name']} [{phase}] {elems}/{len(_ELEMENT_ORDER)} elements")
        return ["\n".join(lines)]

    # ── Start or resume a named session ──────────────────────────────────────────
    # Extract song name from message
    name_match = re.sub(
        r"(new fundo track|fundo session|work on fundo|fundo)\s*",
        "", text, flags=re.IGNORECASE
    ).strip()
    song_name = name_match if name_match else f"Track {len(data['sessions']) + 1}"

    # Check if session exists
    slug    = _slug(song_name)
    session = _get_session(data, slug)

    if session:
        # Resume existing session
        data["active_slug"] = slug
        _save_sessions(data)
        if session["approved"]:
            coaching = _coach_next_element(session)
            return [
                f"Resuming '{session['name']}' (Track #{session['position']}) — coaching phase.\n\n"
                + coaching
            ]
        else:
            return [
                f"Resuming '{session['name']}' — Suno vision phase.\n\n"
                f"Current prompt:\n{session['suno_prompt']}\n\n"
                "Reply 'approve' or 'revise [notes]'."
            ]
    else:
        # Create new session
        session = _create_session(data, song_name)
        suno    = _generate_suno_prompt(session)
        session["suno_prompt"] = suno
        _save_sessions(data)
        _write_session_md(session)
        return [
            f"🎵 Fundo Track #{session['position']}: '{song_name}'\n\n"
            f"Suno Prompt:\n\n{suno}\n\n"
            "─────────────────────────────\n"
            "Paste this into Suno. Listen. Reply:\n"
            "  'approve' → start element-by-element build coaching\n"
            "  'revise [notes]' → regenerate with adjustments"
        ]


# ── CLI ───────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "new fundo track Arrival"
    print(f"Running Fundo session brain: '{text}'\n")
    for line in handle(text):
        print(line)
    print(f"\nSessions JSON: {SESSIONS_JSON}")

import json
import re
import time
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path

OLLAMA_MODEL = "qwen2.5-coder:7b"
OLLAMA_URL = "http://localhost:11434/api/generate"

_LLM_EXTRACT_PROMPT = """\
You are extracting music production facts from a producer's session notes.
Return ONLY a valid JSON object. Only include a field when the note EXPLICITLY
and CLEARLY states that fact. If you are not certain, leave the field out.
Never guess. Never infer from vague praise like "sounds great" or "vibing".

Field definitions (all optional):
  version_locked        "yes"|"no"  — the final version of the SONG is chosen/locked
  needs_rerecord        "yes"       — something needs to be re-recorded
  rerecord_reason       string      — what specifically needs re-recording
  drums_pass            "done"      — drum tracking/editing is complete
  bass_pass             "done"      — bass tracking/editing is complete
  guitars_pass          "done"      — guitar tracking/editing is complete
  keys_pass             "done"      — keys/synths tracking is complete
  structure_pass        "done"      — song structure/arrangement is finalized
  vocals_pass           "done"      — lead vocals are final (not just "sounding good")
  mix_readiness         "not_ready"|"close"|"ready"|"mixed"
  mix_prep_done         "yes"|"no"  — session prep (labeling, gain staging) done
  status                "mastered"  — the song has been mastered (not just mixed)
  vocal_archetype_primary    string — explicit archetype label for the vocal character
  vocal_archetype_influences string — slash-separated genre influences on the vocal

Rules:
- "drums locked" or "drums are done" -> drums_pass: "done"
- "version locked" or "settled on this version" -> version_locked: "yes"
- "needs a re-record" / "redo the vocals" -> needs_rerecord: "yes"
- "sounds great" / "vibing" / "happy with it" -> extract NOTHING
- "drums sound great" -> extract NOTHING (not the same as done/locked)
- Only set status:"mastered" if the word "mastered" is explicitly used

Examples:
Notes: "Drums locked, bass is done, guitars still need a re-record on the outro."
JSON: {{"drums_pass":"done","bass_pass":"done","needs_rerecord":"yes","rerecord_reason":"outro guitars"}}

Notes: "The version is locked. Mix prep is done."
JSON: {{"version_locked":"yes","mix_prep_done":"yes"}}

Notes: "Sounds great, really feeling this one."
JSON: {{}}

Notes:
{text}

JSON:"""

from chief_session_manager import (
    get_workflow_state,
    set_workflow_state,
    mark_complete,
    reset_session as sm_reset_session,
)
from chief_album_io import (
    ensure_csv,
    load_song_md,
    save_song_md,
    upsert_csv_row,
    add_dynamic_column,
    append_session_history,
    list_all_songs,
    load_arc_md,
    save_arc_md,
    score_completion,
    derive_batch_days,
    CSV_PATH,
)

# ── Session default ────────────────────────────────────────────────────────────

_ALBUM_DEFAULT = {
    "active": False,
    "phase": "idle",
    "song_title": "",
    "topics_covered": [],
    "notes": {},
    "structured": {},
    "dynamic_columns": [],
    "history": [],
    "turn": 0,
    "arc_active": False,
    "last_topic_asked": None,
    "last_topic_stack": [],
    "return_mode": None,       # "full" | "targeted" | None (new song)
    "targeted_sections": [],   # only used when return_mode == "targeted"
}


def load_session() -> dict:
    state = get_workflow_state()
    if not state:
        return json.loads(json.dumps(_ALBUM_DEFAULT))
    return state


def save_session(session: dict) -> None:
    set_workflow_state(session)


def reset_session() -> None:
    """Fully clear all album session state back to system default."""
    sm_reset_session()


# ── Topic system ───────────────────────────────────────────────────────────────

TOPIC_KEYWORDS = {
    "structure": [
        "intro", "bridge", "chorus", "verse", "structure", "arrangement",
        "length", "section", "hook", "outro", "pre-chorus", "clutter",
        "too long", "cut it", "tighten", "bars", "feels long", "transition",
    ],
    "vocals": [
        "vocal", "lead", "voice", "re-record", "rerecord", "bgv",
        "backing vocal", "harmony", "double", "redo the vocal",
        "scratch vocal", "lead is", "leads are", "vocals are",
    ],
    "drums": [
        "drum", "kick", "snare", "groove", "percussion", "beat", "hi-hat",
        "overhead", "room", "fill", "pocket",
    ],
    "bass": ["bass", "low end", "bottom end", "sub"],
    "guitars": [
        "guitar", "dl16", "acoustic", "electric", "strum", "nylon",
        "classical guitar", "distorted", "riff", "chord",
    ],
    "keys": [
        "keys", "piano", "synth", "pad", "organ", "electronica",
        "world rhythm", "rhodes", "wurlitzer", "strings", "brass",
        "melodica", "mbira", "kalimba",
    ],
    "mix_readiness": [
        "mix", "mixing", "ready to mix", "not ready to mix",
        "close to mix", "mix-ready", "ready for mix",
    ],
    "mix_prep": [
        "mix prep", "gain stage", "tracks labeled", "snapshot",
        "session prep", "label the tracks", "prepped", "prep the session",
    ],
    "suno_reference": [
        "suno", "genre", "reference", "yacht rock", "soul", "pop rock",
        "afrobeat", "world", "stylistic", "sounds like", "leans like",
    ],
    "lyrics": [
        "lyrics", "words", "the verse goes", "chorus goes",
        "line about", "lyric", "written", "song says",
    ],
    "vocal_archetype": [
        "archetype", "character", "persona", "confessional",
        "soul man", "storyteller", "preacher", "crooner", "griot",
        "who is the singer", "voice of the song", "narrator",
        "vibe of the singer",
    ],
    "feels_magical": [
        "magical", "feels magical", "special", "love the", "best part",
        "nailed it", "preserve", "protect", "keep this", "strongest",
        "don't touch", "dont touch", "working really well", "perfect as is",
        "stands out", "most alive", "hits different",
    ],
    "needs_refinement": [
        "needs work", "not quite", "not quite right", "refine", "not there yet",
        "could be better", "feels weak", "not right", "missing something",
        "not sure about", "not happy with", "needs attention", "tweak", "improve",
        "off somehow", "still off", "doesn't land",
    ],
}

TOPIC_ORDER = [
    "structure", "vocals", "drums", "bass", "guitars", "keys",
    "mix_readiness", "mix_prep", "suno_reference", "lyrics", "vocal_archetype",
    "feels_magical", "needs_refinement",
]

TOPIC_TO_SECTION = {
    "structure":        "Structure Notes",
    "vocals":           "Vocals / Lyrics",
    "vocal_archetype":  "Vocal Archetype",
    "drums":            "Drums",
    "bass":             "Bass",
    "guitars":          "Guitars",
    "keys":             "Keys / Synths / Electronica / World Rhythm",
    "mix_readiness":    "Mix Notes",
    "mix_prep":         "Mix Notes",
    "suno_reference":   "Suno Reference",
    "lyrics":           "Lyrics",
    "feels_magical":    "Feels Magical",
    "needs_refinement": "Needs Refinement",
}

TOPIC_PROMPTS = {
    "structure": (
        "How's the structure feeling — is the arrangement sitting right, "
        "or are there sections that still feel off or cluttered?"
    ),
    "vocals": (
        "Talk to me about the vocals — are the leads in a good place, "
        "any re-records needed, and what's the BGV plan?"
    ),
    "drums": "What's the drum situation — groove locked, editing done?",
    "bass": "How's the bass — tone right, parts locked, anything needing attention?",
    "guitars": "Guitars — are all parts done, or is anything still needing a re-record?",
    "keys": "Keys, synths, electronica, world rhythm elements — where do those sit?",
    "mix_readiness": "Mix readiness — would you call it not ready, close, or ready to mix?",
    "mix_prep": "Mix prep status — tracks labeled, gain staged, snapshot done?",
    "suno_reference": (
        "I want to capture the Suno reference — what's the genre and stylistic "
        "breakdown per instrument or element for this song?"
    ),
    "lyrics": "Want to drop the full lyrics in here while we're on it?",
    "vocal_archetype": (
        "One thing I want to lock in — who is the singer on this song? "
        "What's the vocal character? Like late-night confessional, strutting soul man, "
        "world-weary storyteller — give me the archetype and what it leans toward."
    ),
    "feels_magical": (
        "What about this song feels genuinely special — what's working that we should protect and not mess with?"
    ),
    "needs_refinement": (
        "What's not quite right yet, but isn't a hard blocker? "
        "What would you tweak or improve if you had one more pass?"
    ),
}


def _detect_topics(text: str) -> list:
    t = text.lower()
    return [topic for topic, kws in TOPIC_KEYWORDS.items() if any(kw in t for kw in kws)]


def _next_topic_and_prompt(session: dict) -> tuple:
    covered = set(session.get("topics_covered", []))
    for topic in TOPIC_ORDER:
        if topic not in covered:
            return topic, TOPIC_PROMPTS[topic]
    return None, None


# ── LLM extraction ─────────────────────────────────────────────────────────────

_VALID_EXTRACT_FIELDS = {
    "version_locked", "needs_rerecord", "rerecord_reason",
    "drums_pass", "bass_pass", "guitars_pass", "keys_pass",
    "structure_pass", "vocals_pass",
    "mix_readiness", "mix_prep_done", "status",
    "vocal_archetype_primary", "vocal_archetype_influences",
}


def _llm_extract_structured(text: str) -> dict:
    """Call the local LLM to extract structured fields from free-form notes.
    Returns {} on any failure so callers can fall back to regex."""
    prompt = _LLM_EXTRACT_PROMPT.format(text=text)
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }).encode()
    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())
        raw = result.get("response", "").strip()
        # Strip markdown fences if the model wrapped the JSON
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw.strip())
        data = json.loads(raw)
        # Only keep known fields with non-empty string values
        return {k: v for k, v in data.items()
                if k in _VALID_EXTRACT_FIELDS and isinstance(v, str) and v.strip()}
    except Exception:
        return {}


# ── Structured field extraction (regex fallback) ───────────────────────────────

def _extract_structured(text: str) -> dict:
    t = text.lower()
    data = {}

    if any(p in t for p in [
        "version locked", "locked in", "settled on this version",
        "that's the one", "version is locked", "going with this version",
    ]):
        data["version_locked"] = "yes"
    if any(p in t for p in ["not locked", "still deciding", "haven't picked", "not settled"]):
        data["version_locked"] = "no"

    if any(p in t for p in [
        "re-record", "rerecord", "need to redo", "full redo",
        "redo the", "full re-record", "needs a re-record",
    ]):
        data["needs_rerecord"] = "yes"

    for field, keywords in [
        ("drums_pass",    ["drums done", "drums are done", "drums locked", "drums are locked", "drum tracking done"]),
        ("bass_pass",     ["bass done", "bass is done", "bass locked", "bass is locked"]),
        ("guitars_pass",  ["guitars done", "guitars are done", "guitar done", "guitars locked", "guitar tracking done"]),
        ("keys_pass",     ["keys done", "keys are done", "synths done", "keys locked"]),
        ("structure_pass",["structure locked", "structure done", "arrangement done", "arrangement locked", "structure is locked"]),
        ("vocals_pass",   ["vocals done", "vocals are done", "leads done", "leads are done", "vocals locked", "lead vocal done"]),
    ]:
        if any(p in t for p in keywords):
            data[field] = "done"

    if any(p in t for p in ["not ready to mix", "not ready for mix", "not there yet for mix"]):
        data["mix_readiness"] = "not_ready"
    elif any(p in t for p in ["close to mix", "almost ready to mix", "nearly mix-ready"]):
        data["mix_readiness"] = "close"
    elif any(p in t for p in ["ready to mix", "ready for mix", "mix ready", "mix-ready"]):
        data["mix_readiness"] = "ready"
    elif any(p in t for p in ["been mixed", "mixing is done", "mix is done"]):
        data["mix_readiness"] = "mixed"

    if any(p in t for p in ["mix prep done", "prep is done", "tracks are labeled", "gain staged", "session is prepped"]):
        data["mix_prep_done"] = "yes"
    if any(p in t for p in ["mix prep not done", "not prepped yet", "prep not done"]):
        data["mix_prep_done"] = "no"

    if "mastered" in t and "not mastered" not in t:
        data["status"] = "mastered"

    return data


def _extract_vocal_archetype(text: str) -> dict:
    data = {}
    t = text.lower()
    archetype_signals = [
        "confessional", "soul man", "storyteller", "preacher", "crooner",
        "griot", "narrator", "troubadour", "balladeer", "poet", "prophet",
        "survivor", "lover", "wanderer", "teacher", "witness",
    ]
    influence_signals = [
        "gospel", "yacht rock", "afrobeat", "r&b", "soul", "folk",
        "blues", "jazz", "pop", "rock", "world", "reggae", "funk",
        "country", "electronic", "classical",
    ]
    found_archetypes = [a for a in archetype_signals if a in t]
    found_influences = [i for i in influence_signals if i in t]
    if found_archetypes:
        data["vocal_archetype_primary"] = found_archetypes[0]
    if found_influences:
        data["vocal_archetype_influences"] = " / ".join(found_influences[:3])
    return data


# ── Notes accumulation ─────────────────────────────────────────────────────────

def _best_section(text: str, topics: list) -> str:
    """Return the single most relevant markdown section for this text.
    Score each detected topic by keyword hit count; break ties by TOPIC_ORDER."""
    if not topics:
        return "Vibe / Feel"
    t = text.lower()
    best_topic, best_score = None, -1
    for i, topic in enumerate(TOPIC_ORDER):
        if topic not in topics:
            continue
        score = sum(1 for kw in TOPIC_KEYWORDS[topic] if kw in t)
        # weight by inverse position so earlier topics win ties
        weighted = score * 1000 - i
        if weighted > best_score:
            best_score, best_topic = weighted, topic
    return TOPIC_TO_SECTION.get(best_topic, "Vibe / Feel")


def _accumulate_notes(session: dict, text: str, topics: list) -> dict:
    notes = dict(session.get("notes", {}))
    section = _best_section(text, topics)
    # In targeted mode, only write to sections the user explicitly asked to update
    targeted = session.get("targeted_sections", [])
    if targeted and section not in targeted:
        return notes  # discard — not a section they want to touch
    existing = notes.get(section, "").strip()
    notes[section] = (existing + "\n\n" + text).strip() if existing else text
    return notes


def _process_message(session: dict, text: str) -> dict:
    topics = _detect_topics(text)
    covered = set(session.get("topics_covered", []))
    covered.update(topics)
    session["topics_covered"] = list(covered)
    session["notes"] = _accumulate_notes(session, text, topics)

    # Try LLM extraction first; fall back to regex if it fails or returns nothing
    new_structured = _llm_extract_structured(text)
    if not new_structured:
        new_structured = _extract_structured(text)
        new_structured.update(_extract_vocal_archetype(text))

    session["structured"] = {**session.get("structured", {}), **new_structured}
    session.setdefault("history", []).append({"role": "user", "text": text})
    session["turn"] = session.get("turn", 0) + 1
    return session


# ── Done / skip / go-back signals ─────────────────────────────────────────────

def _is_done_signal(text: str) -> bool:
    t = text.lower().strip()
    return any(p in t for p in [
        "done", "that's it", "thats it", "that's all", "thats all",
        "all good", "we're good", "wrap it up", "save it",
        "that's everything", "thats everything", "nothing else",
        "finish it", "lock it in", "close it out",
    ])


def _is_skip_signal(text: str) -> bool:
    t = text.lower().strip()
    # Explicit skip phrases
    if any(p in t for p in [
        "skip", "not sure", "idk", "move on", "pass", "next",
        "no idea", "n/a", "dont know", "don't know", "unsure",
        "nothing on that", "no notes on that", "not right now",
        "nothing yet", "none yet", "no notes", "nothing to add",
        "nah", "nope",
    ]):
        return True
    # Vague short responses with no topic content — treat as skip rather
    # than polluting a section with meaningless filler
    words = t.split()
    if len(words) <= 4 and not _detect_topics(text):
        return True
    return False


def _is_full_review_signal(text: str) -> bool:
    t = text.lower().strip()
    return any(p in t for p in [
        "full", "re-review", "review", "everything", "all of it",
        "go through it", "full review", "start over", "from the top",
    ])


def _is_targeted_signal(text: str) -> bool:
    t = text.lower().strip()
    return any(p in t for p in [
        "specific", "just update", "update specific", "targeted",
        "only", "just", "certain",
    ]) or bool(_detect_targeted_sections(text))


def _detect_targeted_sections(text: str) -> list:
    """Return list of section names explicitly mentioned in text."""
    t = text.lower()
    mapping = [
        (["structure", "arrangement", "intro", "bridge", "chorus", "verse"], "Structure Notes"),
        (["vocal", "lead", "bgv", "backing", "voice", "re-record", "rerecord"], "Vocals / Lyrics"),
        (["drum", "kick", "snare", "groove", "beat"], "Drums"),
        (["bass", "low end"], "Bass"),
        (["guitar", "riff", "chord", "acoustic", "electric"], "Guitars"),
        (["keys", "synth", "piano", "organ", "pad", "world rhythm", "electronica"], "Keys / Synths / Electronica / World Rhythm"),
        (["mix", "mixing", "mix prep", "ready to mix"], "Mix Notes"),
        (["lyric", "words", "verse goes", "chorus goes"], "Lyrics"),
        (["archetype", "character", "persona", "who is the singer"], "Vocal Archetype"),
        (["suno", "genre", "reference", "style"], "Suno Reference"),
    ]
    found = []
    for keywords, section in mapping:
        if any(kw in t for kw in keywords) and section not in found:
            found.append(section)
    return found


def _is_go_back_signal(text: str) -> bool:
    t = text.lower().strip()
    return any(p in t for p in [
        "go back", "wait", "actually", "let me fix that",
        "hold on", "scratch that", "change that last one",
        "that was wrong", "undo that",
    ])


# ── Song title matching ────────────────────────────────────────────────────────

_SONG_NAME_PREAMBLES = [
    "i need to work on ", "i want to work on ", "let's work on ",
    "let's do ", "let's start with ", "can we work on ", "can we do ",
    "work on ", "working on ", "start with ", "do ",
    "it's ", "it is ", "the song is ", "the song's called ", "song is ",
    "it's called ", "its called ", "called ",
]


def _match_song_title(text: str) -> str | None:
    """Match text to a known song title. Returns None if no confident match."""
    # Only match against the canonical album songs to prevent stray files from
    # polluting the match pool.
    known = [s for s in list_all_songs() if s in _ALBUM_SONGS]
    if not known:
        known = list(_ALBUM_SONGS)
    t = text.lower().strip()

    # Strip common preamble phrases to isolate the song name
    cleaned = t
    for preamble in _SONG_NAME_PREAMBLES:
        if cleaned.startswith(preamble):
            cleaned = cleaned[len(preamble):].strip()
            break

    # Try exact match on cleaned first, then original
    for candidate in ([cleaned, t] if cleaned != t else [t]):
        for song in known:
            if song.lower() == candidate:
                return song

    # Substring: song title appears inside cleaned text
    for candidate in ([cleaned, t] if cleaned != t else [t]):
        for song in known:
            if song.lower() in candidate:
                return song

    # Word overlap score (require at least 1 meaningful word match)
    candidate_words = set(re.sub(r"[^\w\s]", "", cleaned).split())
    stop_words = {"i", "a", "an", "the", "to", "on", "in", "of", "it", "is",
                  "we", "do", "let", "can", "with", "for", "and", "work"}
    candidate_words -= stop_words
    best, best_score = None, 0
    for song in known:
        song_words = set(song.lower().split()) - stop_words
        score = len(candidate_words & song_words)
        if score > best_score:
            best_score, best = score, song
    if best_score > 0:
        return best

    # No confident match — return None so the caller can re-ask
    return None


def _summarize_existing(sections: dict) -> str:
    """Full section dump — used internally."""
    lines = []
    for section, content in sections.items():
        if content.strip() and section not in ("Session History",):
            snippet = content.strip()[:120]
            ellipsis = "..." if len(content.strip()) > 120 else ""
            lines.append(f"**{section}:** {snippet}{ellipsis}")
    return "\n".join(lines) if lines else ""


def _brief_summary(sections: dict) -> str:
    """2-3 line returning-user summary: only the most populated sections."""
    priority = [
        "Structure Notes", "Vocals / Lyrics", "Drums", "Bass",
        "Guitars", "Keys / Synths / Electronica / World Rhythm",
        "Mix Notes", "Vibe / Feel",
    ]
    lines = []
    for section in priority:
        content = sections.get(section, "").strip()
        if content:
            snippet = content.replace("\n", " ")[:80]
            ellipsis = "..." if len(content) > 80 else ""
            lines.append(f"{section}: {snippet}{ellipsis}")
        if len(lines) == 3:
            break
    return "\n".join(lines) if lines else ""


# ── Finalization ───────────────────────────────────────────────────────────────

def _finalize(session: dict) -> list:
    song_title = session["song_title"]
    structured = dict(session.get("structured", {}))
    structured["song_title"] = song_title

    batch_days = derive_batch_days(structured)
    structured["batch_days"] = ", ".join(batch_days)

    pct, blocker = score_completion(structured)
    structured["completion_pct"] = str(pct)
    structured["completion_blocker"] = blocker

    # Pull feels_magical / needs_refinement from notes into CSV fields
    for csv_field, section_name in [
        ("feels_magical",    "Feels Magical"),
        ("needs_refinement", "Needs Refinement"),
    ]:
        note_text = session.get("notes", {}).get(section_name, "").strip()
        if note_text and not structured.get(csv_field):
            structured[csv_field] = note_text[:150].replace("\n", " ")

    ensure_csv()
    upsert_csv_row(structured)

    for col in session.get("dynamic_columns", []):
        add_dynamic_column(col)

    existing_sections = load_song_md(song_title)
    for section, content in session.get("notes", {}).items():
        if content.strip():
            old = existing_sections.get(section, "").strip()
            existing_sections[section] = (old + "\n\n" + content).strip() if old else content
    save_song_md(song_title, existing_sections)

    history_entry = (
        f"Session complete. Completion: {pct}%. "
        f"Blocker: {blocker}. "
        f"Batch days: {', '.join(batch_days) if batch_days else 'none'}."
    )
    append_session_history(song_title, history_entry)
    reset_session()

    try:
        from chief_obsidian_sync import run_sync
        run_sync()
    except Exception:
        pass  # sync failure never blocks the brain

    # Auto-queue to release/content pipeline if song is release-eligible
    try:
        from chief_album_mixer import _queue_marketing_handoff
        _queue_marketing_handoff(song_title, structured)
    except Exception:
        pass

    batch_line = ", ".join(batch_days) if batch_days else "none — you might be done!"
    return [
        f"Locked in {song_title}.\n"
        f"Completion: {pct}%\n"
        f"Blocker: {blocker}\n"
        f"Batch days needed: {batch_line}\n"
        f"Notes saved to {song_title}.md"
    ]


# ── Status ─────────────────────────────────────────────────────────────────────

_PHASE_LABELS = {
    "song_name":          "waiting for song name",
    "return_mode_choice": "waiting for review mode (full / targeted)",
    "open":               "in conversation",
    "follow_up":          "answering questions",
    "finalizing":         "finalizing",
    "restart_prompt":     "paused — waiting for continue / status / restart choice",
}


def handle_status() -> list:
    """Return plain-language album session status."""
    session = load_session()

    if not session.get("active"):
        return [
            "No album session active.\n"
            "Send 'album' to start one."
        ]

    song       = session.get("song_title") or "(song not named yet)"
    phase      = session.get("phase", "idle")
    covered    = session.get("topics_covered", [])
    remaining  = [t for t in TOPIC_ORDER if t not in covered]
    structured = {k: v for k, v in session.get("structured", {}).items() if v}
    turn       = session.get("turn", 0)
    last_q     = session.get("last_topic_asked")
    notes      = {s: c for s, c in session.get("notes", {}).items()
                  if c.strip() and s != "Session History"}

    lines = [
        f"Album session: ACTIVE",
        f"Song: {song}",
        f"Phase: {_PHASE_LABELS.get(phase, phase)}",
    ]

    if last_q:
        lines.append(f"Last question asked: {last_q}")

    if covered:
        lines.append(f"Topics covered ({len(covered)}/{len(TOPIC_ORDER)}): {', '.join(covered)}")
    if remaining:
        shown = remaining[:5]
        tail  = f" +{len(remaining)-5} more" if len(remaining) > 5 else ""
        lines.append(f"Remaining: {', '.join(shown)}{tail}")

    if structured:
        field_str = ", ".join(f"{k}={v}" for k, v in list(structured.items())[:8])
        lines.append(f"Recorded fields: {field_str}")

    if notes:
        lines.append(f"Notes sections: {', '.join(notes.keys())}")

    if turn > 0:
        lines.append(f"Turns: {turn}")

    lines += [
        "",
        "Session is disk-persisted — survives stack restarts.",
        "Writes to .md + CSV on 'done'. Say 'done' to finalize.",
    ]
    return ["\n".join(lines)]


# ── handle() ──────────────────────────────────────────────────────────────────

def handle(text: str) -> list:
    """Process one album brain message. Returns reply strings.
    Returns [] if no active session. Does not call send_reply()."""
    session = load_session()
    if not session.get("active") or session.get("arc_active"):
        return []

    replies = []
    msg = text.strip()
    phase = session.get("phase", "idle")

    # ── Detect "album" alone as a restart-intent signal ───────────────────────
    # If the user sends "album" while a session is already running, don't treat
    # it as an answer — offer explicit choices instead.
    if msg.lower().strip() in ("album", "album session") and phase not in ("song_name", "restart_prompt"):
        song = session.get("song_title") or "this song"
        session["_prev_phase"] = phase
        session["phase"] = "restart_prompt"
        save_session(session)
        return [
            f"Album session already active for *{song}*.\n\n"
            "Options:\n"
            "  `continue` — pick up where we left off\n"
            "  `album status` — see what's been recorded\n"
            "  `restart song` — start a new pass (vault notes kept)"
        ]

    if phase == "restart_prompt":
        t = msg.lower().strip()
        if any(k in t for k in ("continue", "pick up", "resume", "keep going")):
            prev = session.get("_prev_phase", "open")
            session["phase"] = prev
            save_session(session)
            song = session.get("song_title", "session")
            last_q = session.get("last_topic_asked")
            if last_q:
                prompt = TOPIC_PROMPTS.get(last_q, "What's next?")
                replies.append(f"Continuing *{song}*.\n\nBack to: {prompt}")
            else:
                replies.append(f"Continuing *{song}*. What's on your mind?")
        elif "status" in t:
            replies.extend(handle_status())
        elif any(k in t for k in ("restart", "start over", "fresh", "new pass")):
            song_title = session.get("song_title", "")
            # Explicit: vault notes from prior sessions are kept — only session memory resets
            reset_session()
            set_workflow_state({
                **_ALBUM_DEFAULT,
                "active": True,
                "phase": "open",
                "song_title": song_title,
                "return_mode": "full",
                "notes": load_song_md(song_title) if song_title else {},
            })
            replies.append(
                f"Starting a new pass for *{song_title}*.\n"
                "Previous vault notes are kept — this session adds to them.\n\n"
                "Talk to me — where does this song stand right now?"
            )
        else:
            song = session.get("song_title", "this song")
            replies.append(
                f"Album session active for *{song}*. Reply:\n"
                "  `continue` · `album status` · `restart song`"
            )
        return replies

    if phase == "song_name":
        song_title = _match_song_title(msg)
        if song_title is None:
            save_session(session)
            known = list(_ALBUM_SONGS)
            replies.append(
                f"I didn't catch which song. Which one are we working on?\n"
                f"({', '.join(known)})"
            )
        else:
            session["song_title"] = song_title
            existing_sections = load_song_md(song_title)
            session["notes"] = existing_sections
            try:
                import csv as _csv
                if CSV_PATH.exists():
                    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
                        for row in _csv.DictReader(f):
                            if row.get("song_title", "").lower() == song_title.lower():
                                session["structured"] = {k: v for k, v in row.items() if v}
            except Exception:
                pass

            brief = _brief_summary(existing_sections)
            if brief:
                # Returning user — show summary, ask review mode
                session["phase"] = "return_mode_choice"
                save_session(session)
                replies.append(
                    f"Got it — {song_title}. Here's what I already have:\n\n{brief}\n\n"
                    "Want to do a full re-review, or just update specific things?"
                )
            else:
                # Fresh song — go straight to open conversation
                session["phase"] = "open"
                session["return_mode"] = "full"
                save_session(session)
                replies.append(
                    f"Got it — {song_title}. "
                    "Talk to me about it — where is it at, what does it need, "
                    "what are you feeling about it?"
                )

    elif phase == "return_mode_choice":
        if _is_full_review_signal(msg):
            session["return_mode"] = "full"
            session["targeted_sections"] = []
            session["phase"] = "open"
            save_session(session)
            replies.append(
                "Got it — full re-review. Talk to me, what's changed or what's on your mind?"
            )
        else:
            # Try to detect which sections they named
            sections = _detect_targeted_sections(msg)
            if sections:
                session["return_mode"] = "targeted"
                session["targeted_sections"] = sections
                section_names = ", ".join(sections)
                session["phase"] = "open"
                save_session(session)
                replies.append(
                    f"Got it — just updating {section_names}. What's the latest on those?"
                )
            else:
                # They said something like "just update specific things" without naming sections
                save_session(session)
                replies.append(
                    "Which sections do you want to update? "
                    "(e.g. vocals, drums, guitars, structure, mix notes)"
                )

    elif phase in ("open", "follow_up"):
        if _is_done_signal(msg) and phase == "follow_up":
            session["phase"] = "finalizing"
            save_session(session)
            replies.extend(_finalize(session))

        elif _is_go_back_signal(msg):
            stack = session.get("last_topic_stack", [])
            covered = list(session.get("topics_covered", []))
            if stack:
                prev_topic = stack.pop()
                session["last_topic_stack"] = stack
                if prev_topic in covered:
                    covered.remove(prev_topic)
                session["topics_covered"] = covered
                session["last_topic_asked"] = prev_topic
                save_session(session)
                replies.append(TOPIC_PROMPTS[prev_topic])
            else:
                replies.append("Nothing to go back to — we're at the start.")

        elif _is_skip_signal(msg):
            # Mark the last question as covered without extracting anything
            last = session.get("last_topic_asked")
            if last:
                covered = list(session.get("topics_covered", []))
                if last not in covered:
                    covered.append(last)
                session["topics_covered"] = covered
            session["phase"] = "follow_up"
            next_topic, next_prompt = _next_topic_and_prompt(session)
            if next_topic:
                stack = list(session.get("last_topic_stack", []))
                if last:
                    stack.append(last)
                session["last_topic_stack"] = stack
                session["last_topic_asked"] = next_topic
                save_session(session)
                replies.append(f"OK, skipped. Next: {next_prompt}")
            else:
                replies.extend(_finalize(session))

        else:
            # Mark the topic we asked about as covered regardless of content (fix loop bug)
            last = session.get("last_topic_asked")
            if last:
                covered = list(session.get("topics_covered", []))
                if last not in covered:
                    covered.append(last)
                session["topics_covered"] = covered
                stack = list(session.get("last_topic_stack", []))
                stack.append(last)
                session["last_topic_stack"] = stack

            session = _process_message(session, msg)
            session["phase"] = "follow_up"

            next_topic, next_prompt = _next_topic_and_prompt(session)
            if next_topic:
                session["last_topic_asked"] = next_topic
                save_session(session)
                song = session.get("song_title", "session")
                # Brief acknowledgment so the user knows their answer was saved
                replies.append(f"✓ Recorded for *{song}*.\n\nNext: {next_prompt}")
            else:
                replies.extend(_finalize(session))

    elif phase == "finalizing":
        replies.extend(_finalize(session))

    return replies


# ── handle_arc() ──────────────────────────────────────────────────────────────

_ARC_NORTH_STAR = (
    "North star: these should not just be love songs. "
    "When listened to in order, they should feel like a story about "
    "growth, warnings, and self-awareness."
)

_STORY_KEYWORDS = [
    "growth", "warning", "self-aware", "lesson", "change", "journey",
    "regret", "hope", "loss", "survival", "transformation", "reckoning",
]

_ALBUM_SONGS = [
    "1 In A Million", "A Night To Remember", "Blue Weather", "Built By Stars",
    "Can You Feel It", "Count On Your Faith", "I Cry Over Love", "Im Somebody",
    "Kamakazi Of Life", "Slow Me Down", "Ten Fingers", "The Future",
]


def handle_arc(text: str) -> list:
    """Generate arc analysis across all songs. Returns reply strings."""
    songs = list_all_songs()
    if not songs:
        return ["No song notes found. Run album sessions first."]

    all_sections = {song: load_song_md(song) for song in songs}

    song_summaries = []
    themes_found = []
    songs_with_lyrics = []
    songs_needing_work = []

    for song in _ALBUM_SONGS:
        secs = all_sections.get(song, {})
        lyrics = secs.get("Lyrics", "").strip()
        vocals = secs.get("Vocals / Lyrics", "").strip()
        structure = secs.get("Structure Notes", "").strip()
        archetype = secs.get("Vocal Archetype", "").strip()
        vibe = secs.get("Vibe / Feel", "").strip()

        if lyrics:
            songs_with_lyrics.append(song)

        combined = " ".join([lyrics, vocals, vibe]).lower()
        themes_found.extend(kw for kw in _STORY_KEYWORDS if kw in combined)

        has_notes = any([lyrics, vocals, structure, vibe])
        if not has_notes:
            songs_needing_work.append(song)

        snippet = (archetype or vibe or structure or vocals or "no notes yet")[:100]
        song_summaries.append(f"- **{song}**: {snippet}")

    theme_tally = {}
    for t in themes_found:
        theme_tally[t] = theme_tally.get(t, 0) + 1
    top_themes = sorted(theme_tally, key=lambda x: -theme_tally[x])[:5]

    songs_filled = len(_ALBUM_SONGS) - len(songs_needing_work)
    story_verdict = (
        "Leaning toward a story"
        if len(top_themes) >= 3
        else "Still reading as a collection — needs more thematic connective tissue"
    )

    song_list = "\n".join(f"{i+1}. {s}" for i, s in enumerate(_ALBUM_SONGS))
    summary_list = "\n".join(song_summaries)
    arc_text = (
        f"# Album Arc\n"
        f"_Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n"
        f"## Overarching Theme\n\n{_ARC_NORTH_STAR}\n\n"
        f"Top themes detected: {', '.join(top_themes) if top_themes else 'not enough notes yet'}\n\n"
        f"## Song Snapshots\n\n{summary_list}\n\n"
        f"## Lyrical Cohesion\n\n"
        f"Songs with lyrics captured: {len(songs_with_lyrics)} of {len(_ALBUM_SONGS)}\n"
        f"Songs still needing notes: {', '.join(songs_needing_work) if songs_needing_work else 'none'}\n\n"
        f"## Story Assessment\n\n{story_verdict}\n\n"
        f"## Suggested Track Order\n\n"
        f"Current canonical order (revise after all lyrics are in):\n{song_list}\n\n"
        f"## Lyric Tweak Notes\n\n_(Fill in after all lyrics are captured)_\n\n"
        f"## Session History\n\n"
        f"{datetime.now().strftime('%Y-%m-%d')}: Arc analysis run. "
        f"{songs_filled}/{len(_ALBUM_SONGS)} songs have notes.\n"
    )

    save_arc_md(arc_text)
    reset_session()

    return [
        f"Album arc analysis complete. {songs_filled}/{len(_ALBUM_SONGS)} songs have notes.\n"
        f"Top themes: {', '.join(top_themes) if top_themes else 'not enough notes yet'}\n"
        f"Story verdict: {story_verdict}\n"
        f"Songs still needing notes: {', '.join(songs_needing_work) if songs_needing_work else 'all covered'}\n"
        f"Saved to album_arc.md."
    ]


# ── Quick inline update (no full session) ─────────────────────────────────────

_QUICK_UPDATE_PROMPT = """\
A music producer said something that mentions updating a specific song's status.
Extract ONLY the fields you are certain about. Return valid JSON only — no explanation.

Fields (all optional):
  song_title  : exact song name from this list: {song_list}
  field       : one of: drums_pass, bass_pass, guitars_pass, keys_pass,
                structure_pass, vocals_pass, version_locked, needs_rerecord,
                rerecord_reason, mix_readiness, mix_prep_done, status
  value       : the value for that field (e.g. "done", "yes", "ready", "mastered")
  note        : a short one-line note to append to the song's markdown (optional)
  section     : which markdown section the note belongs to (optional)

If you cannot confidently identify both song_title and field, return {{}}.

Message: {text}

JSON:"""


def handle_quick_update(text: str) -> list:
    """Handle a quick out-of-session field update. Returns reply strings."""
    song_list = ", ".join(_ALBUM_SONGS)
    prompt = _QUICK_UPDATE_PROMPT.format(text=text, song_list=song_list)
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }).encode()
    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())
        raw = result.get("response", "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw.strip())
        data = json.loads(raw)
    except Exception:
        return ["Couldn't parse that update — try starting a full album session."]

    song_title = data.get("song_title", "").strip()
    field = data.get("field", "").strip()
    value = data.get("value", "").strip()

    if not song_title or not field or not value:
        return ["I caught something about the album but couldn't pin down the song and field. Try being more specific, e.g. 'guitars are done for Blue Weather'."]

    # Validate song title against canonical list
    matched = _match_song_title(song_title)
    if not matched:
        return [f"I couldn't match '{song_title}' to a known song."]

    # Update CSV
    upsert_csv_row({"song_title": matched, field: value})

    # Append note to markdown if provided
    note = data.get("note", "").strip()
    section = data.get("section", "").strip()
    if note:
        if not section:
            # Fall back to detecting section from field name
            field_to_section = {
                "drums_pass": "Drums", "bass_pass": "Bass",
                "guitars_pass": "Guitars", "keys_pass": "Keys / Synths / Electronica / World Rhythm",
                "structure_pass": "Structure Notes", "vocals_pass": "Vocals / Lyrics",
                "version_locked": "Structure Notes", "needs_rerecord": "Vocals / Lyrics",
                "mix_readiness": "Mix Notes", "mix_prep_done": "Mix Notes",
                "status": "Mix Notes",
            }
            section = field_to_section.get(field, "Vibe / Feel")
        sections = load_song_md(matched)
        existing = sections.get(section, "").strip()
        sections[section] = (existing + "\n\n" + note).strip() if existing else note
        save_song_md(matched, sections)

    append_session_history(matched, f"Quick update: {field} = {value}.")

    try:
        from chief_obsidian_sync import run_sync
        run_sync()
    except Exception:
        pass

    return [f"Got it — updated {field} for {matched}. Saved to CSV and notes."]


# ── Legacy polling shim ────────────────────────────────────────────────────────

if __name__ == "__main__":
    QUEUE_LOG = Path("/mnt/c/OpenClaw/logs/chief_queue.log")
    REPLIED_LOG = Path("/mnt/c/OpenClaw/logs/chief_album_replied.log")

    seen = set()
    if REPLIED_LOG.exists():
        with REPLIED_LOG.open("r", encoding="utf-8") as f:
            for line in f:
                seen.add(line.rstrip("\n"))

    print("Chief album brain online (legacy polling mode).")

    while True:
        if QUEUE_LOG.exists():
            with QUEUE_LOG.open("r", encoding="utf-8") as f:
                for line in f:
                    clean = line.rstrip("\n")
                    if not clean or clean in seen:
                        continue
                    msg = clean.split("] ", 1)[1].strip() if "] " in clean else clean.strip()
                    replies = handle(msg)
                    for r in replies:
                        subprocess.run(
                            ["python3", str(Path.home() / "chief_sender.py"), r],
                            check=False,
                        )
                    seen.add(clean)
                    with REPLIED_LOG.open("a", encoding="utf-8") as rf:
                        rf.write(clean + "\n")
        time.sleep(2)

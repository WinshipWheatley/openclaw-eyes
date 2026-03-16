import json
import re
import time
import subprocess
from datetime import datetime
from pathlib import Path

from chief_session_manager import (
    get_workflow_state,
    set_workflow_state,
    mark_complete,
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
}


def load_session() -> dict:
    state = get_workflow_state()
    if not state:
        return json.loads(json.dumps(_ALBUM_DEFAULT))
    return state


def save_session(session: dict) -> None:
    set_workflow_state(session)


def reset_session() -> None:
    set_workflow_state(json.loads(json.dumps(_ALBUM_DEFAULT)))
    mark_complete()


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
}

TOPIC_ORDER = [
    "structure", "vocals", "drums", "bass", "guitars", "keys",
    "mix_readiness", "mix_prep", "suno_reference", "lyrics", "vocal_archetype",
]

TOPIC_TO_SECTION = {
    "structure":       "Structure Notes",
    "vocals":          "Vocals / Lyrics",
    "vocal_archetype": "Vocal Archetype",
    "drums":           "Drums",
    "bass":            "Bass",
    "guitars":         "Guitars",
    "keys":            "Keys / Synths / Electronica / World Rhythm",
    "mix_readiness":   "Mix Notes",
    "mix_prep":        "Mix Notes",
    "suno_reference":  "Suno Reference",
    "lyrics":          "Lyrics",
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
    "guitars": (
        "Guitars — all parts done, or is anything going through DL16 "
        "or needing a re-record?"
    ),
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
}


def _detect_topics(text: str) -> list:
    t = text.lower()
    return [topic for topic, kws in TOPIC_KEYWORDS.items() if any(kw in t for kw in kws)]


def _next_topic_prompt(session: dict):
    covered = set(session.get("topics_covered", []))
    for topic in TOPIC_ORDER:
        if topic not in covered:
            return TOPIC_PROMPTS[topic]
    return None


# ── Structured field extraction ────────────────────────────────────────────────

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
        ("drums_pass",    ["drums done", "drums are done", "drums locked", "drums are locked", "drums are good", "drum tracking done"]),
        ("bass_pass",     ["bass done", "bass is done", "bass locked", "bass is locked", "bass is good"]),
        ("guitars_pass",  ["guitars done", "guitars are done", "guitar done", "guitars locked", "guitar tracking done"]),
        ("keys_pass",     ["keys done", "keys are done", "synths done", "keys locked", "keys are good"]),
        ("structure_pass",["structure locked", "structure done", "arrangement done", "arrangement locked", "structure is good", "structure is locked"]),
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

def _accumulate_notes(session: dict, text: str, topics: list) -> dict:
    notes = dict(session.get("notes", {}))
    sections_hit = set()
    for topic in topics:
        section = TOPIC_TO_SECTION.get(topic)
        if section:
            sections_hit.add(section)
    if not sections_hit:
        sections_hit.add("Vibe / Feel")
    for section in sections_hit:
        existing = notes.get(section, "").strip()
        notes[section] = (existing + "\n\n" + text).strip() if existing else text
    return notes


def _process_message(session: dict, text: str) -> dict:
    topics = _detect_topics(text)
    covered = set(session.get("topics_covered", []))
    covered.update(topics)
    session["topics_covered"] = list(covered)
    session["notes"] = _accumulate_notes(session, text, topics)
    new_structured = _extract_structured(text)
    new_structured.update(_extract_vocal_archetype(text))
    session["structured"] = {**session.get("structured", {}), **new_structured}
    session.setdefault("history", []).append({"role": "user", "text": text})
    session["turn"] = session.get("turn", 0) + 1
    return session


# ── Done signal ────────────────────────────────────────────────────────────────

def _is_done_signal(text: str) -> bool:
    t = text.lower().strip()
    return any(p in t for p in [
        "done", "that's it", "thats it", "that's all", "thats all",
        "all good", "we're good", "wrap it up", "save it",
        "that's everything", "thats everything", "nothing else",
        "finish it", "lock it in", "close it out",
    ])


# ── Song title matching ────────────────────────────────────────────────────────

def _match_song_title(text: str) -> str:
    known = list_all_songs()
    t = text.lower().strip()
    for song in known:
        if song.lower() == t:
            return song
    for song in known:
        if t in song.lower() or song.lower() in t:
            return song
    text_words = set(re.sub(r"[^\w\s]", "", t).split())
    best, best_score = None, 0
    for song in known:
        song_words = set(song.lower().split())
        score = len(text_words & song_words)
        if score > best_score:
            best_score, best = score, song
    return best if best else text.strip().title()


def _summarize_existing(sections: dict) -> str:
    lines = []
    for section, content in sections.items():
        if content.strip() and section not in ("Session History",):
            snippet = content.strip()[:120]
            ellipsis = "..." if len(content.strip()) > 120 else ""
            lines.append(f"**{section}:** {snippet}{ellipsis}")
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

    batch_line = ", ".join(batch_days) if batch_days else "none — you might be done!"
    return [
        f"Locked in {song_title}.\n"
        f"Completion: {pct}%\n"
        f"Blocker: {blocker}\n"
        f"Batch days needed: {batch_line}\n"
        f"Notes saved to {song_title}.md"
    ]


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

    if phase == "song_name":
        song_title = _match_song_title(msg)
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
        session["phase"] = "open"
        save_session(session)
        summary = _summarize_existing(existing_sections)
        if summary:
            replies.append(
                f"Got it — {song_title}. Here's what I have so far:\n\n{summary}\n\n"
                "Tell me what's changed or what's on your mind about it."
            )
        else:
            replies.append(
                f"Got it — {song_title}. "
                "Talk to me about it — where is it at, what does it need, "
                "what are you feeling about it?"
            )

    elif phase in ("open", "follow_up"):
        if _is_done_signal(msg) and phase == "follow_up":
            session["phase"] = "finalizing"
            save_session(session)
            replies.extend(_finalize(session))
        else:
            session = _process_message(session, msg)
            session["phase"] = "follow_up"
            save_session(session)
            next_prompt = _next_topic_prompt(session)
            if next_prompt:
                replies.append(next_prompt)
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

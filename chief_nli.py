"""
chief_nli.py

Chief-level Natural Language Interface — Intent Transduction layer.
Pass 1: natural status/trust language around active workflows.

Detects conversational status/trust queries and responds naturally
using existing session state and brain status functions.

Handles:
  - Album session status ("where are we at with the album")
  - Active workflow status ("what are we doing", "what's active")
  - Save/record confirmation ("did you save that", "was that recorded")
  - Pending question recap ("what question are we on", "where were we")

Does NOT replace existing intents or change routing for anything else.
Exact commands continue to work as before — this is additive only.

Wired into chief_router.py after approval gate, before session checks.
Intent: nli_status in chief_router.py
"""

import re
from chief_session_manager import load_session


# ── Intent patterns ───────────────────────────────────────────────────────────

# Save/record confirmation — specific enough to always match, even mid-session
_SAVE_PATTERNS = [
    r"did (you |that )?save",
    r"was that (recorded|saved|captured|stored|logged)",
    r"did that (go through|save|record|work)",
    r"is that (saved|recorded|in the notes|in the log)",
    r"did it save",
    r"did you get that",
    r"was that logged",
    r"(is|was) that (in )?the (notes|record|csv|log)",
    r"did you record that",
]

# Status/context queries — match when text is short and conversational
_STATUS_PATTERNS = [
    r"where are we at",
    r"where were we",
    r"what are we (doing|working on)",
    r"what am i (doing|working on|answering)",
    r"are we (still )?on (this )?song",
    r"what('?s| is) (the )?current (question|stage|step|phase)",
    r"what (question|topic) are we on",
    r"what am i answering",
    r"what('?s| is) (happening|going on|active|running|next)",
    r"what('?s| is) waiting (on me|for me|to happen)",
    r"what('?s| is) pending",
    r"where (did we|are we) leave? off",
    r"what (was|is) the (last|current) question",
    r"what do (you|we) (need|want) from me",
    r"remind me",
    r"(with|on) the album",
]

# Topic content words that suggest a message is an actual album answer
# rather than a status query. If present + text is long, fall through.
_TOPIC_SIGNALS = [
    "drums", "bass", "guitar", "vocals", "keys", "synth", "structure",
    "mix", "bridge", "chorus", "verse", "intro", "outro", "lyric",
    "rerecord", "re-record", "arrangement", "suno", "archetype",
]


def detect_nli_query(text: str) -> str | None:
    """
    Returns "save_confirm", "status", or None.

    Conservative detection: never fires on long substantive messages
    that look like actual answers.
    """
    t = text.lower().strip()
    words = t.split()

    # Save confirm: match specifically regardless of length
    for pat in _SAVE_PATTERNS:
        if re.search(pat, t):
            return "save_confirm"

    # Status: only match short messages (≤10 words) to avoid
    # treating real answers as status queries
    if len(words) > 10:
        return None

    # If text contains substantive topic content, let album brain handle it
    topic_hits = sum(1 for sig in _TOPIC_SIGNALS if sig in t)
    if topic_hits >= 2:
        return None

    for pat in _STATUS_PATTERNS:
        if re.search(pat, t):
            return "status"

    return None


# ── Workflow labels ────────────────────────────────────────────────────────────

_WORKFLOW_LABELS = {
    "album":     "album session",
    "billing":   "billing workflow",
    "brainstorm": "brainstorm capture",
    "album_arc": "album arc review",
    "fundo":     "Fundo session",
}


def _label(workflow: str | None) -> str:
    return _WORKFLOW_LABELS.get(workflow or "", workflow or "unknown workflow")


# ── Response builders ─────────────────────────────────────────────────────────

def _respond_save_confirm(session: dict) -> list[str]:
    workflow = session.get("active_workflow")
    status   = session.get("status", "idle")
    wf       = session.get("workflow_state", {})

    if status != "active" or not workflow:
        return ["Nothing is currently active — nothing to save."]

    if workflow == "album":
        turn = wf.get("turn", 0)
        song = wf.get("song_title", "")
        phase = wf.get("phase", "")
        if turn == 0:
            return [
                f"Session is open for *{song}*, but no answers have been recorded yet."
            ]
        last_topic = wf.get("last_topic_asked", "")
        last_covered = (wf.get("topics_covered") or [])[-1:][0] if wf.get("topics_covered") else ""
        saved_section = last_covered or last_topic or "the last topic"
        return [
            f"Yes — recorded. Turn {turn} for *{song}*.\n"
            f"Last topic saved: {saved_section}.\n"
            "Session state is disk-persisted — survives restarts."
        ]

    # Other workflows: confirm active
    return [
        f"Yes — {_label(workflow)} is active and tracking state to disk.\n"
        "Say 'done' or 'cancel' to end it."
    ]


def _respond_status(session: dict, original_text: str) -> list[str]:
    workflow = session.get("active_workflow")
    status   = session.get("status", "idle")
    wf       = session.get("workflow_state", {})

    if status != "active" or not workflow:
        # Check if user specifically asked about album
        t = original_text.lower()
        if "album" in t:
            return [
                "No album session is currently active.\n"
                "Send 'album' to start one."
            ]
        return [
            "Nothing is currently active.\n"
            "Send 'album' to start an album session, or 'schedule [task] [X]min' to start a work block."
        ]

    if workflow == "album":
        return _respond_album_status(wf)

    if workflow == "album_arc":
        return ["Running album arc review — no further input needed, it's processing."]

    if workflow == "billing":
        mode = session.get("active_mode") or wf.get("mode") or "billing"
        step = session.get("step", 0)
        return [
            f"Active: billing ({mode}), step {step + 1}.\n"
            "Say 'cancel' to exit or keep answering billing questions."
        ]

    if workflow == "brainstorm":
        phase = wf.get("phase", "")
        if phase == "brainstorm_capture":
            return ["Waiting for your brainstorm idea. What's the thought?"]
        return [f"Active: {_label(workflow)}. Say 'cancel' to exit."]

    return [
        f"Active: {_label(workflow)}.\n"
        "Say 'cancel' to exit, or keep going."
    ]


def _respond_album_status(wf: dict) -> list[str]:
    song       = wf.get("song_title") or "(song not named yet)"
    phase      = wf.get("phase", "idle")
    turn       = wf.get("turn", 0)
    covered    = wf.get("topics_covered") or []
    remaining  = [t for t in _TOPIC_ORDER if t not in covered]
    last_topic = wf.get("last_topic_asked")

    _PHASE_NATURAL = {
        "song_name":          "waiting for you to name the song",
        "return_mode_choice": "waiting — full re-review or just specific topics?",
        "open":               "open conversation mode",
        "follow_up":          "working through topic questions",
        "restart_prompt":     "paused — say 'continue', 'album status', or 'restart song'",
        "finalizing":         "finalizing and saving",
    }
    phase_desc = _PHASE_NATURAL.get(phase, phase)

    lines = [f"We're in an album session for *{song}*."]

    if phase in ("follow_up", "open") and last_topic:
        from chief_album_brain import TOPIC_PROMPTS
        prompt = TOPIC_PROMPTS.get(last_topic, "")
        if prompt:
            lines.append(f"Current question ({last_topic}): {prompt[:100]}")
        else:
            lines.append(f"Current topic: {last_topic}")
    else:
        lines.append(f"Phase: {phase_desc}")

    if covered:
        lines.append(f"Covered {len(covered)}/{len(_TOPIC_ORDER)}: {', '.join(covered)}")
    if remaining:
        shown = remaining[:4]
        tail  = f" +{len(remaining)-4} more" if len(remaining) > 4 else ""
        lines.append(f"Still to go: {', '.join(shown)}{tail}")

    if turn > 0:
        lines.append(f"Answers recorded: {turn}")

    lines.append("Say 'done' to finalize, 'skip' to move on, or keep answering.")
    return ["\n".join(lines)]


# Topic order reference (mirrors chief_album_brain without importing it for this)
_TOPIC_ORDER = [
    "structure", "vocals", "drums", "bass", "guitars", "keys",
    "mix_readiness", "mix_prep", "suno_reference", "lyrics", "vocal_archetype",
]


# ── Public entry point ────────────────────────────────────────────────────────

def handle(text: str) -> list[str]:
    """
    Called by router when detect_nli_query returns non-None.
    Returns natural-language response list.
    """
    query_type = detect_nli_query(text)
    if not query_type:
        return []

    session = load_session()

    if query_type == "save_confirm":
        return _respond_save_confirm(session)

    if query_type == "status":
        return _respond_status(session, text)

    return []


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "where are we at"
    result = handle(text)
    for line in result:
        print(line)
    if not result:
        print(f"No NLI match for: '{text}' (would fall through to normal routing)")

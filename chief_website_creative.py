"""
chief_website_creative.py

Generates all creative assets for deeppocketrecords.com — copy, bios, song
descriptions, SVG logo variations, Canva briefs, and Fundo mystery text.

Two brand modes kept strictly separate:
  DPR mode  — Deep Pocket Records / Winship Wheatley IV identity
  FUNDO mode — anonymous alter-ego identity (no face, no real name)

North star: visitor lands and says "I have never seen this before."

Triggered by:
  - "headline [context]"           → 5 headline options
  - "bio [short|long] [winship|fundo]" → artist bio copy
  - "song description [name]"      → album track blurb
  - "fundo mystery text"           → opaque teaser copy, in character
  - "logo [style]"                 → SVG logo variation as inline text
  - "canva brief [element]"        → formatted Canva direction card
  - "website copy [topic]"         → general creative brief
Intent: website_creative in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/openclaw-vault/Website/Creative Log.md
"""

import re
from datetime import datetime
from pathlib import Path

from chief_llm import ollama_call

# ── Paths ───────────────────────────────────────────────────────────────────────

VAULT_WEB_DIR   = Path("/mnt/c/OpenClawShared/openclaw-vault/Website")
CREATIVE_LOG_MD = VAULT_WEB_DIR / "Creative Log.md"

# ── Brand contexts ──────────────────────────────────────────────────────────────

DPR_IDENTITY = """\
BRAND: Deep Pocket Records
ARTIST: Winship Wheatley IV — solo artist, composer, multi-instrumentalist
LOCATION: Annapolis, Maryland
GENRES: Yacht Rock · Pop Rock · Soul · Electronica · World Rhythm
LABEL: Deep Pocket Records (self-owned, sole proprietorship under Winship Live)
DOMAIN: deeppocketrecords.com (registered March 15, 2026)
VIBE: Sophisticated but not pretentious. Soulful but not retro. The ocean at night.
      A vinyl record playing in a well-lit room. Quality over quantity.
CATALOG: 12 songs — 1 In A Million, A Night To Remember, Blue Weather, Built By Stars,
         Can You Feel It, Count On Your Faith, I Cry Over Love, Im Somebody,
         Kamakazi Of Life, Slow Me Down, Ten Fingers, The Future
TONE: Warm, confident, cinematic. No clichés. No "journey." No "passion for music."
VISUAL DIRECTION: Deep navy, warm gold, clean serif typography. Ocean + pocket watch motif.
GOAL: Visitor lands and says "I have never seen this before."
"""

FUNDO_IDENTITY = """\
BRAND: FUNDO
MEANING: "Deep" in Portuguese
PERSONA: Anonymous electronic producer. No face visible. No real name. No location.
PROJECT: Electronic alter-ego on Deep Pocket Records. 15-song target.
SOUND DNA: World rhythm at the root (bossa nova, Cuban percussion / conch quinto,
           Fela Kuti Afrobeat) filtered through Baltimore club, Miami house,
           UK drum and bass / jungle, German techno, Empire of the Sun cosmic energy.
MYSTERY: Nobody knows if it's human or AI. That ambiguity is intentional.
VISUAL: Thrift store anonymous aesthetic. Found objects. Texture. Dark. No face.
        Think: a mask made of old vinyl labels. A figure in shadow. Never direct eye contact.
TONE: Opaque. Slightly off. Feels like it's from somewhere you can't name.
      Speaks in fragments. Hints, never explains.
PLATFORMS: TikTok (fast visual hook, no personal info), Instagram (dark aesthetic, minimal text)
GOAL: People share it because they can't explain it.
"""

# ── DPR song blurbs seed (expanded by LLM per request) ─────────────────────────

SONG_MOODS = {
    "1 In A Million":      "euphoric, once-in-a-lifetime love anthem",
    "A Night To Remember": "cinematic, late-night energy, unforgettable moment",
    "Blue Weather":        "melancholic but hopeful, emotional weather system",
    "Built By Stars":      "cosmic, aspirational, built from something bigger",
    "Can You Feel It":     "groove-driven, communal, kinetic dance floor energy",
    "Count On Your Faith": "soulful reassurance, spiritual without being preachy",
    "I Cry Over Love":     "vulnerable, honest, no armor",
    "Im Somebody":         "declarative, empowerment, earned confidence",
    "Kamakazi Of Life":    "reckless momentum, living without brakes",
    "Slow Me Down":        "longing, the request to pause time",
    "Ten Fingers":         "complex, layered, the weight of a disputed legacy",
    "The Future":          "forward-looking, visionary, the open road",
}

# ── Prompt templates ─────────────────────────────────────────────────────────────

_HEADLINE_PROMPT = """\
{identity}

Write 5 distinct homepage headline options for the context below.
Each headline should be 3-10 words. No clichés. No "welcome to." No "journey."
Make each one feel different — try: declarative, interrogative, abstract, cinematic, minimal.
The goal: visitor lands and says "I have never seen this before."

Context: {context}

Return a numbered list, one headline per line. No explanations."""

_BIO_PROMPT = """\
{identity}

Write a {length} artist bio. Rules:
- No clichés ("journey," "passion," "unique sound," "burst onto the scene")
- No third-person opener with the full name — start with a strong declarative or image
- {length_note}
- Tone matches the brand identity above exactly
- The reader should feel something, not just learn facts

Return plain text only. No markdown. No headers."""

_SONG_DESC_PROMPT = """\
{identity}

Write a 2-3 sentence description of the song "{song}" for the website music page.
The song's emotional core: {mood}
Rules:
- No clichés about "feeling" or "taking the listener on a journey"
- Write like a great music journalist, not a press release
- Make someone want to press play immediately
- Match the brand tone above

Return plain text only."""

_FUNDO_MYSTERY_PROMPT = """\
{identity}

Generate mysterious teaser copy for the Fundo teaser page on deeppocketrecords.com.
This is the FIRST thing people see about Fundo — before any music is released.
Rules:
- Maximum 4 lines total
- Each line stands alone — cryptic, not explained
- Could be interpreted multiple ways
- No name. No face. No biography.
- Feels like it came from somewhere you can't locate on a map
- The reader should feel slightly unsettled in a good way

Return only the 4 lines, no other text."""

_CANVA_BRIEF_PROMPT = """\
{identity}

Write a Canva design direction card for: {element}
Format it exactly like this:

ELEMENT: {element}
SIZE: [recommended dimensions]
BACKGROUND: [color/texture/image direction]
TYPOGRAPHY: [font style, size, color, placement]
IMAGERY: [what images or graphics to use — specific, not vague]
MOOD: [3 adjectives]
AVOID: [what not to do]
CANVA TEMPLATE TIP: [one specific tip for finding the right template]

Keep each line brief and actionable. A designer reading this should know exactly what to build."""

_GENERAL_COPY_PROMPT = """\
{identity}

Write website copy for: {topic}
Rules:
- Match the brand voice exactly
- No filler words, no clichés
- Every sentence earns its place
- Visitor should feel something before they scroll

Return clean copy, ready to paste into a CMS. No markdown headers unless they're actual section headers."""

_SVG_LOGO_PROMPT = """\
{identity}

Describe and generate a simple SVG logo concept for the "{style}" style variation.
First, describe the concept in 2 sentences.
Then output a minimal SVG (viewBox="0 0 200 60") that could represent the brand wordmark.
Use only basic SVG shapes (rect, circle, text, path, line, polyline).
The SVG should be clean enough to read at small sizes.

Return:
CONCEPT: [2-sentence description]
SVG:
[the svg code starting with <svg]"""


# ── Core handlers ────────────────────────────────────────────────────────────────

def _detect_mode(text: str) -> str:
    """Return 'fundo' if this request is fundo-oriented, else 'dpr'."""
    if "fundo" in text.lower():
        return "fundo"
    return "dpr"


def _identity(mode: str) -> str:
    return FUNDO_IDENTITY if mode == "fundo" else DPR_IDENTITY


def _generate_headlines(text: str) -> list[str]:
    mode    = _detect_mode(text)
    context = re.sub(r"headline\s*", "", text, flags=re.IGNORECASE).strip() or "homepage hero section"
    prompt  = _HEADLINE_PROMPT.format(identity=_identity(mode), context=context)
    result  = ollama_call(prompt, timeout=30, task_class="chief_structured_plan")
    if not result:
        return ["Couldn't generate headlines — try again or check Claude API connection."]
    _log_entry("headline", context, result, mode)
    return [f"Headlines ({mode.upper()} mode) for: {context}\n\n{result}"]


def _generate_bio(text: str) -> list[str]:
    t    = text.lower()
    mode = "fundo" if "fundo" in t else "dpr"

    if "short" in t:
        length      = "SHORT (50-80 words)"
        length_note = "50-80 words max"
    else:
        length      = "LONG (150-200 words)"
        length_note = "150-200 words, build a full picture"

    prompt = _BIO_PROMPT.format(
        identity=_identity(mode),
        length=length,
        length_note=length_note,
    )
    result = ollama_call(prompt, timeout=40, task_class="chief_structured_plan")
    if not result:
        return ["Bio generation failed — check Claude API."]
    _log_entry("bio", f"{length} {mode}", result, mode)
    return [f"Bio ({length} · {mode.upper()} mode):\n\n{result}"]


def _generate_song_description(text: str) -> list[str]:
    # Try to match a known song title from the text
    t        = text.lower()
    matched  = None
    for song in SONG_MOODS:
        if song.lower() in t:
            matched = song
            break

    # Fallback: strip "song description" prefix
    if not matched:
        song_name = re.sub(r"song\s*description\s*", "", text, flags=re.IGNORECASE).strip()
        song_name = song_name or "Unknown Song"
        mood      = "introspective, layered"
        matched   = song_name
    else:
        mood = SONG_MOODS[matched]

    prompt = _SONG_DESC_PROMPT.format(
        identity=_identity("dpr"),
        song=matched,
        mood=mood,
    )
    result = ollama_call(prompt, timeout=30, task_class="chief_structured_plan")
    if not result:
        return [f"Song description for '{matched}' failed — check Claude API."]
    _log_entry("song_description", matched, result, "dpr")
    return [f"Song description — {matched}:\n\n{result}"]


def _generate_fundo_mystery(text: str) -> list[str]:
    prompt = _FUNDO_MYSTERY_PROMPT.format(identity=_identity("fundo"))
    result = ollama_call(prompt, timeout=30, task_class="chief_structured_plan")
    if not result:
        return ["Mystery text generation failed — check Claude API."]
    _log_entry("fundo_mystery", "teaser page", result, "fundo")
    return [f"Fundo mystery text:\n\n{result}"]


def _generate_svg_logo(text: str) -> list[str]:
    style  = re.sub(r"logo\s*", "", text, flags=re.IGNORECASE).strip() or "minimal wordmark"
    mode   = _detect_mode(text)
    prompt = _SVG_LOGO_PROMPT.format(identity=_identity(mode), style=style)
    result = ollama_call(prompt, timeout=40, task_class="chief_structured_plan")
    if not result:
        return ["SVG logo generation failed — check Claude API."]
    _log_entry("logo_svg", style, result, mode)
    # Note Canva availability
    note = "\n\n📌 Note: Once you approve this concept, recreate it in Canva using Brand Kit > Logo. Canva Pro allows SVG export."
    return [f"Logo concept — {style} ({mode.upper()} mode):\n\n{result}{note}"]


def _generate_canva_brief(text: str) -> list[str]:
    element = re.sub(r"canva\s*brief\s*", "", text, flags=re.IGNORECASE).strip() or "homepage hero image"
    mode    = _detect_mode(text)
    prompt  = _CANVA_BRIEF_PROMPT.format(identity=_identity(mode), element=element)
    result  = ollama_call(prompt, timeout=30, task_class="chief_structured_plan")
    if not result:
        return ["Canva brief generation failed — check Claude API."]
    _log_entry("canva_brief", element, result, mode)
    return [f"Canva design brief — {element} ({mode.upper()} mode):\n\n{result}"]


def _generate_general_copy(text: str) -> list[str]:
    topic  = re.sub(r"website\s*copy\s*", "", text, flags=re.IGNORECASE).strip() or text[:80]
    mode   = _detect_mode(text)
    prompt = _GENERAL_COPY_PROMPT.format(identity=_identity(mode), topic=topic)
    result = ollama_call(prompt, timeout=40, task_class="chief_structured_plan")
    if not result:
        return ["Copy generation failed — check Claude API."]
    _log_entry("general_copy", topic, result, mode)
    return [f"Website copy — {topic} ({mode.upper()} mode):\n\n{result}"]


# ── Logging ──────────────────────────────────────────────────────────────────────

def _log_entry(asset_type: str, context: str, content: str, mode: str) -> None:
    VAULT_WEB_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = (
        f"\n## {timestamp} · {asset_type.replace('_', ' ').title()} · {mode.upper()}\n\n"
        f"**Context:** {context}\n\n"
        f"{content}\n\n---"
    )
    existing = CREATIVE_LOG_MD.read_text(encoding="utf-8") if CREATIVE_LOG_MD.exists() else (
        "---\ntype: creative-log\n---\n\n# Website Creative Log\n\n"
        "_Generated by `chief_website_creative.py`_\n"
    )
    CREATIVE_LOG_MD.write_text(existing + entry, encoding="utf-8")


# ── Public entry point ───────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t = text.lower().strip()

    if re.search(r"\bheadline", t):
        return _generate_headlines(text)

    if re.search(r"\bbio\b", t):
        return _generate_bio(text)

    if re.search(r"\bsong description\b", t) or re.search(r"\btrack description\b", t):
        return _generate_song_description(text)

    if "mystery text" in t or ("fundo" in t and "teas" in t):
        return _generate_fundo_mystery(text)

    if re.search(r"\blogo\b", t):
        return _generate_svg_logo(text)

    if "canva brief" in t or "canva direction" in t:
        return _generate_canva_brief(text)

    # default: general copy
    return _generate_general_copy(text)


# ── CLI ──────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "website copy about page"
    print(f"Running website creative brain: '{text}'\n")
    for line in handle(text):
        print(line)
    print(f"\nCreative Log: {CREATIVE_LOG_MD}")

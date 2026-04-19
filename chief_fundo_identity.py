"""
chief_fundo_identity.py

Manages the Fundo brand and identity. The full sonic brief is embedded
directly — this file IS the source of truth, not a loader.

Generates: visual direction notes, artist statement (vague/anonymous),
press bio (no personal details), mood board descriptions, 15-song arc briefs.

Exports get_fundo_context() for use by marketing brain and website creative brain.

Triggered by:
  - "fundo brief" / "fundo identity" / "fundo brand"
  - "fundo visual"
  - "fundo song [number]"
  - "who is fundo"
Intent: fundo_identity in chief_router.py

Saves to:
  - /mnt/c/OpenClawShared/openclaw-vault/Fundo/Fundo Identity.md
"""

from datetime import datetime
from pathlib import Path

from chief_llm import ollama_call

# ── Paths ────────────────────────────────────────────────────────────────────────

FUNDO_VAULT_DIR = Path("/mnt/c/OpenClawShared/openclaw-vault/Fundo")
IDENTITY_MD     = FUNDO_VAULT_DIR / "Fundo Identity.md"

# ── The brief — embedded, authoritative ──────────────────────────────────────────

FUNDO_FULL_BRIEF = """\
FUNDO — Complete Identity Brief

NAME: FUNDO
MEANING: "Deep" in Portuguese
TYPE: Anonymous electronic alter-ego project on Deep Pocket Records
TARGET: 15 songs

━━━ SONIC DNA ━━━

ROOT INFLUENCES (world rhythm foundation):
  · Bossa nova — syncopation, nylon string ghost comping, intimate swing
  · Cuban percussion — conga, quinto, bongo interlocking patterns, warm and dry
  · Fela Kuti Afrobeat — extended polyrhythmic grooves, horn stabs, bass as anchor

FILTER LAYER (modern electronic):
  · Baltimore club — 130bpm+ hi-hat patterns, vocal fragment chops, aggressive energy
  · Miami house — lush pads, deep sub bass, soulful chord progressions
  · UK drum and bass / jungle — 170bpm amen breaks, sub-bass weight, chaotic-but-locked
  · German techno — minimal, hypnotic, industrial edge, long builds
  · Empire of the Sun — cosmic synth washes, euphoric energy, cinematic scale

THE QUESTION FUNDO ASKS: What happens when a Yoruba rhythm dreams of Berlin?

━━━ 15-SONG ARC ━━━

ARRIVAL (1-3): Deep, hypnotic, slow-building. World roots upfront. No drops.
  · Track 1: Arrival ritual — roots dominant, sub-bass drone, sparse
  · Track 2: First fusion — one electronic layer joins the world rhythm
  · Track 3: The groove solidifies — tempo locks, depth increases

RISING (4-6): Tempo climbs, bass heavier, polyrhythm intensifies.
  · Track 4: Baltimore energy enters — hi-hats accelerate, still rooted
  · Track 5: House warmth — pads swell, emotional mid-section
  · Track 6: DnB break moment — jungle chaos reigned in by Afrobeat structure

PEAK (7-9): Full fusion. All DNA present. Maximum dancefloor energy.
  · Track 7: Peak track — everything at once, the center of the project
  · Track 8: Techno discipline — stripped of melody, pure rhythmic intensity
  · Track 9: Cosmic — Empire of the Sun euphoria filtered through Cuban percussion

DESCENT (10-11): Stripped back. World instruments come forward. Emotional.
  · Track 10: The conversation — two world instruments, minimal electronics
  · Track 11: Memory — familiar elements from Track 1 return, transformed

REFLECTION (12-13): Slow, textural, rhythmic-ambient.
  · Track 12: Drone study — almost static, micro-movements only
  · Track 13: The space between beats — rhythm implied, rarely stated

EXIT (14-15): Cosmic, open-ended. The listener doesn't know if it ended.
  · Track 14: Dissolution — sounds lose their grid, float
  · Track 15: Departure — the last sound is the first sound, played differently

━━━ VISUAL IDENTITY ━━━

AESTHETIC: Thrift store anonymous. No face visible. No location revealed.
PALETTE: Near-black (#0D0D0D), dark teal (#0A2E2E), white text only
TYPOGRAPHY: Monospace or sparse grotesque. Lowercase preferred. No serifs.

IMAGERY DIRECTIONS:
  · Found objects on dark surfaces — vinyl record labels, old passports, worn fabric
  · Extreme close-ups of instruments, never the player's face
  · Shadows and silhouettes. The shape of a figure but never their features.
  · Textures: concrete, water, circuit board, woven cane
  · A mask made of old vinyl record labels
  · A figure in shadow in a lit doorway — never direct eye contact

WHAT TO AVOID: Any photo of a person's face. Any identifiable location marker.
               Warm colors. Anything friendly or approachable. Typography that smiles.

━━━ PERSONA RULES ━━━

Nobody knows if FUNDO is human or AI. That ambiguity is intentional and protected.
Never confirm or deny. Never state a location. Never use a real name.
Speaks in fragments. Hints, never explains.
The mystery IS the brand.

IN CHARACTER EXAMPLES:
  · "something was recorded. whether it was by a person is not the question."
  · "fundo does not perform. fundo transmits."
  · "the name means deep. everything else is interpretation."

PLATFORMS:
  · TikTok: fast visual hook, no personal info, texture and rhythm-focused clips
  · Instagram: dark aesthetic, minimal text, image-first, long captions that say nothing clearly
"""


# ── Context export (for other brains) ────────────────────────────────────────────

def get_fundo_context() -> str:
    """Return the Fundo identity brief for injection into other brains' prompts."""
    return FUNDO_FULL_BRIEF


# ── Prompt templates ─────────────────────────────────────────────────────────────

_BRIEF_PROMPT = """\
{brief}

Summarize the Fundo identity in 5-7 sentences for someone who has never heard of Fundo.
Rules:
- Sound like someone describing something they can't quite explain
- No clichés about "genre-blending" or "pushing boundaries"
- Don't reveal the real artist behind Fundo
- The tone should feel slightly off — familiar but from somewhere unidentifiable
Return plain text only."""

_VISUAL_PROMPT = """\
{brief}

Generate a visual direction document for one specific Fundo content piece.
The piece: {context}

Format it as an art director's brief:
CONCEPT: [1 sentence — the single image idea]
SHOT/ELEMENT: [what is literally in frame or in the graphic]
MOOD: [3 adjectives]
PALETTE: [specific colors]
TEXTURE: [physical or digital texture to apply]
WHAT IS NOT SHOWN: [what is deliberately absent]
CAPTION DIRECTION: [how the caption should read — fragments, lowercase, cryptic]

Return only the brief, no other text."""

_ARC_PROMPT = """\
{brief}

Give a production brief for Track #{number} in the Fundo arc.

Include:
- Where this track falls in the arc (arrival/rising/peak/descent/reflection/exit)
- The emotional function of this track in the full 15-song journey
- 3 specific sonic references (artists + specific song or album if possible)
- Tempo range
- Key instruments or sounds that must be present
- One thing that should NOT be in this track

Keep it to 8-10 sentences. Plain text, no markdown."""

_WHO_PROMPT = """\
{brief}

Someone just asked: "Who is Fundo?"
Answer in character — as if Fundo itself is responding, or as if someone close to the project
is describing it. Rules:
- 3-5 sentences maximum
- Cryptic but not annoying — leaves the listener wanting more
- Never confirm human or AI
- Never state a location or real name
Return the response only."""


# ── Handlers ─────────────────────────────────────────────────────────────────────

def _write_identity_md() -> None:
    FUNDO_VAULT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    content = (
        "---\ntype: fundo-identity\n"
        f"last_updated: {today}\n---\n\n"
        "# Fundo Identity\n\n"
        "_Source of truth for the Fundo alter-ego project. Do not edit manually._\n\n"
        "```\n" + FUNDO_FULL_BRIEF + "\n```\n"
    )
    if not IDENTITY_MD.exists():
        IDENTITY_MD.write_text(content, encoding="utf-8")


def handle(text: str = "") -> list[str]:
    t = text.lower().strip()
    _write_identity_md()

    # ── Who is Fundo ─────────────────────────────────────────────────────────────
    if "who is fundo" in t or "what is fundo" in t:
        prompt = _WHO_PROMPT.format(brief=FUNDO_FULL_BRIEF)
        result = ollama_call(prompt, timeout=25, task_class="chief_structured_plan")
        return [result or "fundo does not answer directly."]

    # ── Visual direction ─────────────────────────────────────────────────────────
    if "fundo visual" in t or "visual direction" in t:
        import re
        context = re.sub(r"fundo visual|visual direction", "", text, flags=re.IGNORECASE).strip()
        context = context or "an Instagram post announcing the first release"
        prompt  = _VISUAL_PROMPT.format(brief=FUNDO_FULL_BRIEF, context=context)
        result  = ollama_call(prompt, timeout=30, task_class="chief_structured_plan")
        fallback = "VISUAL CONCEPT (Fallback): Thrift store anonymous. Near-black palette. Found objects and textures. No face visible."
        return [result or fallback]

    # ── Arc brief for specific track number ──────────────────────────────────────
    if "fundo song" in t or "track brief" in t or "arc brief" in t:
        import re
        m = re.search(r"\d+", text)
        num = int(m.group()) if m else 1
        num = max(1, min(num, 15))
        prompt = _ARC_PROMPT.format(brief=FUNDO_FULL_BRIEF, number=num)
        result = ollama_call(prompt, timeout=30, task_class="chief_structured_plan")
        fallback = f"Track #{num} (Fallback): Refer to the 15-song arc in Fundo Identity.md for position details."
        return [f"Track #{num} Arc Brief:\n\n{result}" if result else fallback]

    # ── Full brief (default) ─────────────────────────────────────────────────────
    prompt = _BRIEF_PROMPT.format(brief=FUNDO_FULL_BRIEF)
    result = ollama_call(prompt, timeout=30, task_class="chief_structured_plan")
    full   = result or "Fundo: an anonymous electronic project. Roots in world rhythm. Filtered through club, house, DnB, techno, and cosmic energy. Nobody knows if it's human or AI."
    return [f"Fundo Identity:\n\n{full}\n\n---\nFull brief saved to: openclaw-vault/Fundo/Fundo Identity.md"]


# ── CLI ───────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "fundo brief"
    print(f"Running Fundo identity brain: '{text}'\n")
    for line in handle(text):
        print(line)
    print(f"\nIdentity MD: {IDENTITY_MD}")

"""
chief_brand_brain.py

Brand voice and style guide for both DPR Music (Winship) and Fundo.
Knows visual identity, tone of voice, what's on-brand vs off-brand.
Referenced by chief_website_creative.py and chief_marketing_brain.py.

Triggered by:
  - "brand guide" / "brand rules" / "style guide"
  - "is this on brand [text]" / "on brand check"
  - "brand guide for dpr" / "brand guide for fundo"
  - "dpr brand" / "fundo brand guide"
Intent: brand_guide in chief_router.py

Saves to:
  - openclaw-vault/Marketing/Brand Guide.md
"""

import re
from datetime import datetime
from pathlib import Path

from chief_llm import ollama_call

# ── Paths ─────────────────────────────────────────────────────────────────────

BRAND_GUIDE_MD = Path("/mnt/c/OpenClawShared/openclaw-vault/Marketing/Brand Guide.md")

# ── Brand identities ──────────────────────────────────────────────────────────

DPR_BRAND = {
    "name": "DPR Music / Winship",
    "label": "Deep Pocket Records",
    "domain": "deeppocketrecords.com",
    "genres": ["Yacht Rock", "Pop Rock", "Soul", "Electronica", "World Rhythm"],
    "tone": [
        "Warm but confident",
        "Storytelling-forward — every song has a narrative",
        "Crafted, not viral — quality over algorithm",
        "Southern warmth with global reach",
        "Honest about the process",
    ],
    "visual": [
        "Rich, warm color palette — golds, deep navies, warm neutrals",
        "Photography style: candid studio shots, natural light, analog warmth",
        "Typography: classic serif for headlines, clean sans for body",
        "No heavy filters — honest, warm photography",
        "Album art: evocative, painterly, cinematic",
    ],
    "on_brand": [
        "Personal stories behind the songs",
        "Craft and process (studio, instruments, production)",
        "Collaborations with other artists in the genre",
        "Live performance clips and behind-the-scenes",
        "Milestone announcements (release dates, album progress)",
        "Fan interaction that's genuine, not performative",
    ],
    "off_brand": [
        "Trend-chasing content (viral dances, memes)",
        "Aggressive promotion ('BUY NOW', countdown spam)",
        "Corporate/cold tone",
        "Over-edited, filtered, or artificial visuals",
        "Anything that feels fake or manufactured",
        "Negativity about other artists",
    ],
    "platforms": {
        "Instagram": "Visual storytelling — album art, studio sessions, personal moments",
        "TikTok": "Short process clips, behind-the-scenes, song previews (keep authentic)",
        "YouTube": "Full performance, full song reveals, production breakdowns",
        "Twitter": "Quick thoughts, song lyrics, fan conversation",
        "Facebook": "Longer updates, event announcements, older demographic engagement",
    },
    "hashtag_strategy": "#DPRMusic #DeepPocketRecords #YachtRock #NewMusic #IndieArtist",
}

FUNDO_BRAND = {
    "name": "FUNDO",
    "origin": "Anonymous. No face, no real name, no location.",
    "meaning": "Portuguese for 'deep'",
    "genres": ["Afrobeats", "World Electronic", "Baltimore Club", "UK Drum & Bass", "Global Fusion"],
    "tone": [
        "Mysterious and anonymous — let the music speak",
        "Cryptic but not pretentious",
        "Global and rootless — belongs to no single place",
        "Hypnotic, deep, purposeful",
        "Sparse communication — quality over quantity of posts",
    ],
    "visual": [
        "Dark, textural backgrounds — deep blues, blacks, earth tones",
        "Abstract or obscured imagery — no faces",
        "World instrument photography (kora, congas, djembe) shot dramatically",
        "Generative or geometric art for singles",
        "Video: always partially obscured, shadows, silhouettes",
    ],
    "on_brand": [
        "Track teasers with no context (let people wonder)",
        "Single cover reveals",
        "Short production clips — hands on instruments, never a face",
        "Cryptic one-line captions",
        "Cross-cultural music references and influences",
        "DistroKid / streaming links",
    ],
    "off_brand": [
        "Revealing identity or location",
        "Casual, everyday content (food, travel, personal)",
        "Overexplaining the music",
        "Talking about DPR / Winship in the same breath",
        "Upbeat, friendly marketing tone",
        "Bright, colorful, cheerful visuals",
    ],
    "platforms": {
        "Instagram": "Visual mystery — dark, textural posts, short cryptic captions",
        "TikTok": "15-30s production clips, obscured identity, strong hook",
        "YouTube": "Full track with visualizer, no face cam",
        "SoundCloud": "Early releases, exclusive previews",
        "Spotify": "Primary distribution, playlist pitching target",
    },
    "hashtag_strategy": "#FUNDO #Afrobeats #WorldElectronic #GlobalGroove #AfrobeatProducer",
}


# ── On-brand checker ──────────────────────────────────────────────────────────

_BRAND_CHECK_PROMPT = """\
You are the brand manager for {brand_name}.

Brand rules:
Tone: {tone}
On-brand: {on_brand}
Off-brand: {off_brand}

Evaluate this content:
"{content}"

Give a 2-sentence verdict:
- Is it on-brand or off-brand, and why
- If off-brand, suggest one specific fix

Be direct."""


def _check_on_brand(content: str, brand: dict) -> str:
    prompt = _BRAND_CHECK_PROMPT.format(
        brand_name=brand["name"],
        tone="; ".join(brand["tone"][:3]),
        on_brand="; ".join(brand["on_brand"][:4]),
        off_brand="; ".join(brand["off_brand"][:4]),
        content=content[:500],
    )
    try:
        result = ollama_call(prompt, timeout=20, task_class="chief_structured_plan").strip()
    except Exception:
        result = ""
    return result if _usable_brand_check(result) else _fallback_brand_check(content, brand)


def _usable_brand_check(text: str) -> bool:
    stripped = (text or "").strip()
    return len(stripped.split()) >= 2 and stripped.lower() not in {"ok", "n/a", "none", "unknown"}


def _fallback_brand_check(content: str, brand: dict) -> str:
    return f"Manual brand check needed for {brand['name']}. Compare it against the guide; strongest on-brand anchor: {brand['on_brand'][0]}."


# ── Report builder ────────────────────────────────────────────────────────────

def _format_brand_guide(brand: dict) -> list[str]:
    lines = [
        f"## {brand['name']}",
        "",
    ]
    if brand.get("label"):
        lines.append(f"**Label:** {brand['label']}")
    if brand.get("origin"):
        lines.append(f"**Identity:** {brand['origin']}")
    if brand.get("meaning"):
        lines.append(f"**Name meaning:** {brand['meaning']}")
    lines.append(f"**Genres:** {', '.join(brand['genres'])}")
    lines += [
        "",
        "**Tone of voice:**",
    ]
    lines += [f"- {t}" for t in brand["tone"]]
    lines += [
        "",
        "**Visual identity:**",
    ]
    lines += [f"- {v}" for v in brand["visual"]]
    lines += [
        "",
        "**On-brand ✓**",
    ]
    lines += [f"- {o}" for o in brand["on_brand"]]
    lines += [
        "",
        "**Off-brand ✗**",
    ]
    lines += [f"- {o}" for o in brand["off_brand"]]
    lines += [
        "",
        "**Platform strategy:**",
    ]
    for platform, strategy in brand["platforms"].items():
        lines.append(f"- **{platform}:** {strategy}")
    lines.append(f"\n**Hashtags:** {brand.get('hashtag_strategy', '')}")
    return lines


# ── Vault write ───────────────────────────────────────────────────────────────

def _write_brand_guide_md() -> None:
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    dpr_lines = _format_brand_guide(DPR_BRAND)
    fundo_lines = _format_brand_guide(FUNDO_BRAND)
    content = (
        "---\n"
        "type: brand-guide\n"
        f"last_updated: {today}\n"
        "---\n\n"
        "# Brand Guide\n\n"
        "_Managed by `chief_brand_brain.py`. Both brands are kept strictly separate._\n\n"
        + "\n".join(dpr_lines)
        + "\n\n---\n\n"
        + "\n".join(fundo_lines)
        + "\n"
    )
    BRAND_GUIDE_MD.parent.mkdir(parents=True, exist_ok=True)
    BRAND_GUIDE_MD.write_text(content, encoding="utf-8")


# ── Handlers ──────────────────────────────────────────────────────────────────

def _detect_brand(text: str) -> str:
    t = text.lower()
    if "fundo" in t:
        return "fundo"
    if any(k in t for k in ("dpr", "winship", "deep pocket", "deeppocket")):
        return "dpr"
    return "both"


def _handle_guide(brand_key: str) -> list[str]:
    _write_brand_guide_md()
    if brand_key == "fundo":
        lines = [f"**Fundo Brand Guide**\n"] + _format_brand_guide(FUNDO_BRAND)
    elif brand_key == "dpr":
        lines = [f"**DPR Music Brand Guide**\n"] + _format_brand_guide(DPR_BRAND)
    else:
        lines = (
            ["**Brand Guide — DPR Music & Fundo**\n",
             "_Two separate brands. Never mix them._\n"]
            + _format_brand_guide(DPR_BRAND)
            + ["\n---\n"]
            + _format_brand_guide(FUNDO_BRAND)
        )
    lines.append("\nFull guide saved to vault/Marketing/Brand Guide.md")
    return ["\n".join(lines)]


def _handle_check(text: str) -> list[str]:
    # Extract the content to check: "is this on brand [content]" or "on brand check [content]"
    m = re.search(r"(?:is\s+this\s+on\s+brand|on\s+brand\s+check|brand\s+check)\s+(?:for\s+\w+\s+)?(.+)", text, re.IGNORECASE)
    if not m:
        return ["Format: 'is this on brand [content to check]' or 'is this on brand for fundo [content]'"]
    content = m.group(1).strip()
    brand_key = _detect_brand(text)

    if brand_key == "fundo":
        verdict = _check_on_brand(content, FUNDO_BRAND)
        return [f"**Fundo brand check:**\n{verdict}"]
    else:
        verdict = _check_on_brand(content, DPR_BRAND)
        return [f"**DPR brand check:**\n{verdict}"]


# ── Public entry point ────────────────────────────────────────────────────────

def handle(text: str = "") -> list[str]:
    t = text.lower().strip()

    if any(k in t for k in ("is this on brand", "on brand check", "brand check")):
        return _handle_check(text)

    brand_key = _detect_brand(text)
    return _handle_guide(brand_key)


# ── Exported context for other brains ─────────────────────────────────────────

def get_dpr_brand_rules() -> dict:
    """Called by chief_website_creative.py and chief_marketing_brain.py."""
    return DPR_BRAND


def get_fundo_brand_rules() -> dict:
    """Called by chief_website_creative.py and chief_marketing_brain.py."""
    return FUNDO_BRAND


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "brand guide"
    for line in handle(text):
        print(line)

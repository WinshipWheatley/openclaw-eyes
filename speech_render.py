"""Render a message for the EAR, not the eye.

The text path (what the operator reads) and the voice path (what he hears) carry the
SAME information, but a screen and a speaker want different shapes. The text keeps its
emojis and formatting; the voice should sound natural — no "smiling face" read aloud,
no "$" or "→" spoken as symbols.

`to_speech_text` is the speech-tailoring pass, applied ONLY on the voice path (inside
agent_voice_sender._prepare_text), so the text reply is never altered. It builds on
chief_output_utils.tts_clean (markdown) and adds the spoken layer: emoji removal,
symbol-to-word, currency, and URL collapsing. Deterministic — no model, no GPU, instant,
and the two renders can never drift in content because the facts are identical.
"""
from __future__ import annotations

import re

from chief_output_utils import tts_clean

# Emoji + pictographic ranges, variation selectors, ZWJ, skin-tone modifiers,
# regional indicators, dingbats, arrows-as-symbols. Stripped (not spoken).
_EMOJI = re.compile(
    "["
    "\U0001F300-\U0001FAFF"   # symbols, pictographs, emoticons, supplemental, extended-A
    "\U0001F000-\U0001F0FF"   # mahjong/dominoes/cards
    "\U00002600-\U000027BF"   # misc symbols + dingbats
    "\U00002B00-\U00002BFF"   # misc symbols & arrows
    "\U00002190-\U000021FF"   # arrows block
    "\U0001F1E6-\U0001F1FF"   # regional indicators (flags)
    "\U0000FE00-\U0000FE0F"   # variation selectors
    "\U0001F3FB-\U0001F3FF"   # skin-tone modifiers
    "\U00002300-\U000023FF"   # misc technical (⌚⏰ etc.)
    "]+",
    flags=re.UNICODE,
)
_ZWJ = re.compile("‍")
_URL = re.compile(r"https?://\S+", flags=re.IGNORECASE)
# $1,234 or $1,234.56  -> spoken dollars (and cents only when non-zero)
_CURRENCY = re.compile(r"\$\s?([0-9][0-9,]*)(?:\.([0-9]{2}))?")
_ARROW = re.compile(r"\s*(?:->|→|⟶)\s*")


def _currency_repl(m: re.Match) -> str:
    whole = m.group(1).replace(",", "")
    cents = m.group(2)
    out = f"{int(whole)} dollars"
    if cents and cents != "00":
        out += f" and {int(cents)} cents"
    return out


def to_speech_text(text: str | None, *, agent: str | None = None) -> str:
    """Transform a reply into speech-friendly text. ``agent`` is accepted for future
    per-agent spoken styling but does not change v1 (universal) behavior."""
    if not text:
        return ""
    s = tts_clean(str(text))            # markdown layer (reused)
    s = _URL.sub("link", s)             # bare URLs -> "link"
    s = _ARROW.sub(" to ", s)           # PROPOSED → READY -> "PROPOSED to READY"
    s = _CURRENCY.sub(_currency_repl, s)
    s = _ZWJ.sub("", s)
    s = _EMOJI.sub(" ", s)              # strip emoji/pictographs/symbol-arrows
    s = re.sub(r"\s*[—–]\s*", ", ", s)  # em/en dash -> a spoken pause, not silence
    s = re.sub(r"[•·▪◦‣⁃]\s*", "", s)    # leftover bullets/dots tts_clean didn't catch
    # spoken symbol words (only where a screen-symbol reads wrong aloud)
    s = re.sub(r"\s*&\s*", " and ", s)
    s = re.sub(r"(\d)\s*%", r"\1 percent", s)
    s = re.sub(r"\s*%\s*", " percent ", s)
    # a stray emoji-strip can leave " , " or " !" — tidy punctuation spacing
    s = re.sub(r"\s+([,.!?;:])", r"\1", s)
    s = re.sub(r"([,])\s*([,.!?;:])", r"\2", s)   # collapse doubled separators (", ," -> ",")
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip(" ,;:-")

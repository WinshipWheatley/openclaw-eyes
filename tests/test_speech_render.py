from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from speech_render import to_speech_text  # noqa: E402


def test_emojis_are_removed_not_spoken():
    # The actual pain: Cassandra's emojis were read aloud unnaturally.
    assert to_speech_text("Great news, the gig is booked! 😊🎉") == "Great news, the gig is booked!"
    assert to_speech_text("All set ✅ — invoice sent 💸") == "All set, invoice sent"


def test_emoji_with_variation_selector_and_zwj():
    assert to_speech_text("Heads up ⚠️ and family 👨‍👩‍👧 done") == "Heads up and family done"


def test_markdown_is_flattened_via_tts_clean():
    assert to_speech_text("**Bold** and `code` and _italics_") == "Bold and code and italics"
    assert to_speech_text("[click here](https://example.com)") == "click here"


def test_currency_is_spoken():
    assert to_speech_text("The invoice is $2,000 total") == "The invoice is 2000 dollars total"
    assert to_speech_text("paid $250") == "paid 250 dollars"
    assert to_speech_text("$1,500.50 due") == "1500 dollars and 50 cents due"


def test_common_symbols_become_words():
    assert to_speech_text("R&B set at 50% done") == "R and B set at 50 percent done"
    assert to_speech_text("PROPOSED → READY") == "PROPOSED to READY"


def test_bare_urls_collapse_to_link():
    assert to_speech_text("see https://example.com/path?x=1 now") == "see link now"


def test_plain_text_is_untouched():
    assert to_speech_text("You have two gigs this week.") == "You have two gigs this week."


def test_empty_and_none_are_safe():
    assert to_speech_text("") == ""
    assert to_speech_text(None) == ""


def test_whitespace_is_collapsed():
    assert to_speech_text("too    many     spaces") == "too many spaces"


def test_agent_param_is_accepted_for_future_tailoring():
    # signature must accept agent= without changing v1 behavior
    assert to_speech_text("hello 🎵", agent="niles") == "hello"


def test_synth_kokoro_wav_speech_renders_for_every_agent(monkeypatch, tmp_path):
    # The universal chokepoint: ALL Kokoro agents funnel through synth_kokoro_wav, so
    # proving the render here proves it for maestro/cassandra/chief/guardian/niles/hermes
    # at once — no model load, no snowglobe.
    import agent_kokoro_voice as akv

    captured = {}

    def fake_loader(lang):
        def pipe(text, voice=None, speed=None):
            captured["text"] = text
            return []  # no chunks -> returns False, but we captured the speech-rendered text

        return pipe

    monkeypatch.setattr(akv, "_load_pipeline", fake_loader)
    akv.synth_kokoro_wav("Booked! 🎉 $250 at R&B night 😊", "af_heart", tmp_path / "x.wav")

    assert "🎉" not in captured["text"] and "😊" not in captured["text"]
    assert "250 dollars" in captured["text"]
    assert "R and B" in captured["text"]

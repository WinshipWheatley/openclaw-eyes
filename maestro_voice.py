"""
maestro_voice.py - Maestro's voice (Kokoro am_michael).

Standalone on purpose: Cassandra's voice path is load-bearing for her Telegram
replies. Maestro - the front-door conductor - gets his own distinct voice.
First surface: the operator morning brief. Synthesis only; the SEND is
delegated to cassandra_sender.send_operator_brief_voice(), which keeps the exact
operator-resolved / SEND_HOLD / carve-out posture as before.
"""
import io
import os
import threading
import wave
from pathlib import Path

from cassandra_mode import is_focus_mode, is_social_mode
from chief_output_utils import tts_clean
import chief_env  # noqa: F401  — loads .chief.env into os.environ
from agent_kokoro_voice import synth_kokoro_wav, voice_for_agent

VOICE_ENABLED = os.environ.get("CASSANDRA_VOICE", "0") == "1"
MAESTRO_VOICE_BACKEND = os.environ.get("MAESTRO_VOICE_BACKEND", "kokoro").lower()
MAESTRO_KOKORO_VOICE = voice_for_agent("maestro")
MAESTRO_KOKORO_SPEED = float(os.environ.get("MAESTRO_KOKORO_SPEED", "1.0"))
MAESTRO_VOICE_MODEL = os.environ.get(
    "MAESTRO_VOICE_MODEL",
    "/home/openclaw/piper_voices/en_GB-alan-medium.onnx",
)
# Piper fallback tuning only. No reverb, no pitch effects.
LENGTH_SCALE = float(os.environ.get("MAESTRO_VOICE_LENGTH_SCALE", "1.06"))
NOISE_SCALE = float(os.environ.get("MAESTRO_VOICE_NOISE_SCALE", "0.55"))
NOISE_W = float(os.environ.get("MAESTRO_VOICE_NOISE_W", "0.75"))
MAX_CHARS_BATCH = 800

_WAV_BRIEF = Path("/mnt/c/OpenClaw/logs/maestro_brief.wav")

_voice = None
_voice_lock = threading.Lock()


def _load_maestro_voice():
    global _voice
    if _voice is not None:
        return _voice
    with _voice_lock:
        if _voice is None:
            if not Path(MAESTRO_VOICE_MODEL).is_file():
                raise FileNotFoundError(f"Maestro Piper model not found: {MAESTRO_VOICE_MODEL}")
            from piper.voice import PiperVoice
            print(f"[maestro_voice] loading Piper: {MAESTRO_VOICE_MODEL}", flush=True)
            _voice = PiperVoice.load(MAESTRO_VOICE_MODEL)
            print("[maestro_voice] Piper ready.", flush=True)
    return _voice


def _synth_maestro_piper_wav(text: str, wav_path: Path) -> bool:
    """Render text to a WAV through Maestro's Piper fallback."""
    from piper.config import SynthesisConfig
    voice = _load_maestro_voice()
    cfg = SynthesisConfig(
        length_scale=LENGTH_SCALE,
        noise_scale=NOISE_SCALE,
        noise_w_scale=NOISE_W,
    )
    chunks = list(voice.synthesize(text, cfg))
    if not chunks:
        return False
    buf = io.BytesIO()
    wf = wave.open(buf, "wb")
    wf.setnchannels(chunks[0].sample_channels)
    wf.setsampwidth(chunks[0].sample_width)
    wf.setframerate(chunks[0].sample_rate)
    for c in chunks:
        wf.writeframes(c.audio_int16_bytes)
    wf.close()
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    wav_path.write_bytes(buf.getvalue())
    return True


def synth_maestro_wav(text: str, wav_path: Path) -> bool:
    """Render text to a WAV in Maestro's voice. No playback, no send."""
    if MAESTRO_VOICE_BACKEND == "kokoro":
        try:
            if synth_kokoro_wav(text, MAESTRO_KOKORO_VOICE, wav_path, speed=MAESTRO_KOKORO_SPEED):
                return True
            print("[maestro_voice] Kokoro returned no audio; fallback -> Piper", flush=True)
        except Exception as e:
            print(f"[maestro_voice] Kokoro failed; fallback -> Piper: {e}", flush=True)
    return _synth_maestro_piper_wav(text, wav_path)


def _clean(text: str) -> str:
    try:
        cleaned = tts_clean(text)
    except Exception:
        cleaned = text
    return (cleaned or "").strip()[:MAX_CHARS_BATCH]


def synthesize_brief(text: str) -> "Path | None":
    """Gated synth of the operator brief in Maestro's voice. Returns WAV path or None."""
    try:
        import harness_context
        if harness_context.is_harness_mode():
            print(f"[harness] no-voice Maestro brief: {text[:50]}...", flush=True)
            return None
    except Exception:
        pass
    if not VOICE_ENABLED:
        return None
    if is_focus_mode() or is_social_mode():
        print("[maestro_voice] silenced by gate", flush=True)
        return None
    clean = _clean(text)
    if not clean:
        return None
    try:
        if synth_maestro_wav(clean, _WAV_BRIEF):
            return _WAV_BRIEF
    except Exception as e:
        print(f"[maestro_voice] synth error: {e}", flush=True)
    return None


def speak_and_send_operator_brief_voice(text: str) -> None:
    """
    Drop-in replacement for cassandra_voice.speak_and_send_operator_brief_voice.
    Renders the operator brief in Maestro's voice and sends it through the same
    operator-resolved voice-note path (unchanged SEND_HOLD / carve-out posture).
    Text is always delivered first by the caller; voice is secondary, best-effort.
    """
    wav = synthesize_brief(text)
    if wav is None:
        return
    try:
        from cassandra_sender import send_operator_brief_voice
        send_operator_brief_voice(str(wav))
    except Exception as e:
        print(f"[maestro_voice] send error: {e}", flush=True)


if __name__ == "__main__":
    import sys
    txt = " ".join(sys.argv[1:]) or (
        "Maestro here. Systems are green and the line is holding. "
        "Your masters, your data, your call."
    )
    if synth_maestro_wav(_clean(txt) or txt, _WAV_BRIEF):
        print(f"[maestro_voice] wrote {_WAV_BRIEF}")
    else:
        print("[maestro_voice] no audio produced")

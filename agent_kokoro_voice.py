"""Shared Kokoro-82M synthesis helpers for OpenClaw agent voices.

This module only synthesizes local WAV files. It does not play audio, send
messages, start listeners, call external APIs, or mutate runtime state.
"""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Any, Iterable


KOKORO_SAMPLE_RATE = 24000
DEFAULT_KOKORO_LANG = "a"
DEFAULT_TARGET_RMS = 0.12
DEFAULT_PEAK_CEILING = 0.98
DEFAULT_MAX_LOUDNESS_GAIN = 3.0

AGENT_KOKORO_VOICES = {
    "maestro": "am_michael",
    "cassandra": "af_heart",
    "chief": "bm_george",
    "guardian": "am_onyx",
    "niles": "am_puck",
    "hermes": "am_echo",
}

KOKORO_PRONUNCIATION_LEXICON = {
    "Live": "lyve",
}

_PIPELINES: dict[str, Any] = {}
_PIPELINE_LOCK = threading.Lock()
_SYNTH_LOCK = threading.Lock()


def voice_for_agent(agent_ref: str) -> str:
    """Return the approved Kokoro voice id for a known OpenClaw agent."""

    key = str(agent_ref or "").strip().lower()
    return AGENT_KOKORO_VOICES[key]


def apply_pronunciation_lexicon(
    text: str | None,
    lexicon: dict[str, str] | None = None,
) -> str:
    """Apply durable Kokoro pronunciation respellings before synthesis."""

    rendered = str(text or "")
    for source, replacement in (lexicon or KOKORO_PRONUNCIATION_LEXICON).items():
        source_text = str(source or "").strip()
        replacement_text = str(replacement or "").strip()
        if not source_text or not replacement_text:
            continue
        rendered = re.sub(
            rf"(?<!\w){re.escape(source_text)}(?!\w)",
            replacement_text,
            rendered,
        )
    return rendered


def _load_pipeline(lang_code: str) -> Any:
    lang = str(lang_code or DEFAULT_KOKORO_LANG).strip() or DEFAULT_KOKORO_LANG
    with _PIPELINE_LOCK:
        pipeline = _PIPELINES.get(lang)
        if pipeline is None:
            from kokoro import KPipeline

            pipeline = KPipeline(lang_code=lang)
            _PIPELINES[lang] = pipeline
        return pipeline


def _combine_audio_chunks(chunks: Iterable[Any]) -> Any:
    import numpy as np

    arrays = [np.asarray(chunk, dtype=np.float32) for chunk in chunks]
    if not arrays:
        return None
    return np.concatenate(arrays).astype(np.float32)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def normalize_loudness(
    audio: Any,
    *,
    target_rms: float | None = None,
    peak_ceiling: float | None = None,
    max_gain: float | None = None,
) -> Any:
    """Raise quiet output RMS with one clean gain stage, never clipping."""

    import numpy as np

    arr = np.asarray(audio, dtype=np.float32)
    if arr.size == 0:
        return arr
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32, copy=False)
    rms = float(np.sqrt(np.mean(np.square(arr, dtype=np.float32), dtype=np.float64)))
    peak = float(np.max(np.abs(arr)))
    if rms <= 0.0 or peak <= 0.0:
        return arr

    resolved_target = float(target_rms if target_rms is not None else _env_float("OPENCLAW_KOKORO_TARGET_RMS", DEFAULT_TARGET_RMS))
    resolved_ceiling = float(peak_ceiling if peak_ceiling is not None else _env_float("OPENCLAW_KOKORO_PEAK_CEILING", DEFAULT_PEAK_CEILING))
    resolved_max_gain = float(max_gain if max_gain is not None else _env_float("OPENCLAW_KOKORO_MAX_GAIN", DEFAULT_MAX_LOUDNESS_GAIN))
    if resolved_target <= 0.0 or resolved_ceiling <= 0.0 or resolved_max_gain <= 1.0:
        return arr

    desired_gain = resolved_target / rms
    peak_limited_gain = resolved_ceiling / peak
    gain = min(desired_gain, peak_limited_gain, resolved_max_gain)
    if gain <= 1.0:
        return arr
    return (arr * gain).astype(np.float32)


def _write_wav(path: Path, audio: Any, sample_rate: int) -> None:
    import soundfile as sf

    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), normalize_loudness(audio), sample_rate, subtype="PCM_16")


def synth_kokoro_wav(
    text: str,
    voice: str,
    wav_path: str | Path,
    *,
    speed: float | None = None,
    lang_code: str | None = None,
) -> bool:
    """Synthesize text to a 24 kHz WAV using Kokoro-82M."""

    # Speech-tailor the text for the EAR at the universal Kokoro chokepoint, so EVERY
    # agent (agent_voice_sender, cassandra_voice, maestro_voice, the Hermes service) gets
    # emoji-free, symbol-spoken audio. The text path the operator reads is never touched.
    try:
        from speech_render import to_speech_text
        text = to_speech_text(text)
    except Exception:
        pass
    text = apply_pronunciation_lexicon(text)
    clean = " ".join(str(text or "").split())
    if not clean:
        return False
    selected_voice = str(voice or "").strip()
    if not selected_voice:
        return False
    lang = str(lang_code or os.environ.get("OPENCLAW_KOKORO_LANG") or DEFAULT_KOKORO_LANG)
    selected_speed = float(speed if speed is not None else os.environ.get("OPENCLAW_KOKORO_SPEED", "1.0"))
    pipeline = _load_pipeline(lang)
    audio_chunks: list[Any] = []
    with _SYNTH_LOCK:
        for _graphemes, _phonemes, audio in pipeline(clean, voice=selected_voice, speed=selected_speed):
            audio_chunks.append(audio)
    combined = _combine_audio_chunks(audio_chunks)
    if combined is None:
        return False
    _write_wav(Path(wav_path), combined, KOKORO_SAMPLE_RATE)
    return True


def reset_kokoro_voice_cache_for_tests() -> None:
    with _PIPELINE_LOCK:
        _PIPELINES.clear()

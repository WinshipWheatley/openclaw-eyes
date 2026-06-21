"""Shared Kokoro-82M synthesis helpers for OpenClaw agent voices.

This module only synthesizes local WAV files. It does not play audio, send
messages, start listeners, call external APIs, or mutate runtime state.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Iterable


KOKORO_SAMPLE_RATE = 24000
DEFAULT_KOKORO_LANG = "a"

AGENT_KOKORO_VOICES = {
    "maestro": "am_michael",   # keep — conductor / front-door orchestrator
    "cassandra": "af_heart",   # keep — female executive assistant (operator-confirmed)
    "chief": "am_onyx",        # operational foreman
    "guardian": "am_echo",     # quiet authoritative gatekeeper
    "hermes": "am_eric",       # systems architect / advisor
    "niles": "am_fenrir",      # creative studio operator
    "fin": "af_aoife",         # Fin — distinct female voice
}

_PIPELINES: dict[str, Any] = {}
_PIPELINE_LOCK = threading.Lock()
_SYNTH_LOCK = threading.Lock()


def voice_for_agent(agent_ref: str) -> str:
    """Return the approved Kokoro voice id for a known OpenClaw agent."""

    key = str(agent_ref or "").strip().lower()
    return AGENT_KOKORO_VOICES[key]


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


def _write_wav(path: Path, audio: Any, sample_rate: int) -> None:
    import soundfile as sf

    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, sample_rate, subtype="PCM_16")


def synth_kokoro_wav(
    text: str,
    voice: str,
    wav_path: str | Path,
    *,
    speed: float | None = None,
    lang_code: str | None = None,
) -> bool:
    """Synthesize text to a 24 kHz WAV using Kokoro-82M."""

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

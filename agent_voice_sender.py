"""Shared Kokoro voice-note sender for first-class OpenClaw agents."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Callable

import requests

import chief_env  # noqa: F401 - loads .chief.env into os.environ when available
from agent_kokoro_voice import synth_kokoro_wav, voice_for_agent
from chief_output_utils import tts_clean  # noqa: F401 - kept for back-compat
from speech_render import to_speech_text


FIRST_CLASS_AGENTS = ("maestro", "cassandra", "chief", "guardian", "niles", "hermes")
DEFAULT_WAV_DIR = Path("/mnt/c/OpenClaw/logs")
MAX_AGENT_VOICE_CHARS = 800


@dataclass(frozen=True)
class AgentVoiceReceipt:
    agent: str
    voice: str
    wav_path: str
    synthesized: bool
    sent: bool = False
    chat_id: str | None = None
    token_env: str | None = None
    error: str = ""


SendVoiceNoteFn = Callable[..., None]


def _normalize_agent(agent: str) -> str:
    key = str(agent or "").strip().lower().replace("clara reid", "cassandra")
    if key == "clara":
        key = "cassandra"
    if key not in FIRST_CLASS_AGENTS:
        raise KeyError(f"unknown OpenClaw voice agent: {agent!r}")
    return key


def _agent_wav_path(agent: str) -> Path:
    return DEFAULT_WAV_DIR / f"{agent}_voice_note.wav"


def _speed_for_agent(agent: str) -> float:
    env_name = f"{agent.upper()}_KOKORO_SPEED"
    raw = os.environ.get(env_name) or os.environ.get("OPENCLAW_AGENT_KOKORO_SPEED")
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    if agent == "cassandra":
        return 0.9
    return 1.0


def _prepare_text(text: str) -> str:
    try:
        # Speech-tailored render (emoji-free, symbols spoken) — voice path only.
        # The text path the operator reads is never touched by this.
        clean = to_speech_text(str(text or ""))
    except Exception:
        clean = str(text or "")
    clean = " ".join(clean.split()).strip()
    return clean[:MAX_AGENT_VOICE_CHARS]


def synthesize_agent_wav(
    agent: str,
    text: str,
    *,
    wav_path: str | Path | None = None,
    speed: float | None = None,
) -> AgentVoiceReceipt:
    """Synthesize ``text`` in the agent's mapped Kokoro voice. No send."""
    normalized = _normalize_agent(agent)
    voice = voice_for_agent(normalized)
    out = Path(wav_path) if wav_path is not None else _agent_wav_path(normalized)
    clean = _prepare_text(text)
    if not clean:
        return AgentVoiceReceipt(normalized, voice, str(out), False, error="empty_text")
    try:
        ok = synth_kokoro_wav(clean, voice, out, speed=_speed_for_agent(normalized) if speed is None else speed)
    except Exception as exc:
        return AgentVoiceReceipt(normalized, voice, str(out), False, error=str(exc))
    return AgentVoiceReceipt(normalized, voice, str(out), bool(ok), error="" if ok else "synth_failed")


def _token_env_for_agent(agent: str) -> str:
    mapping = {
        "maestro": ("MAESTRO_BOT_TOKEN", "TELEGRAM_BOT_TOKEN"),
        "cassandra": ("CASSANDRA_BOT_TOKEN",),
        "chief": ("TELEGRAM_BOT_TOKEN", "CHIEF_BOT_TOKEN"),
        "guardian": ("GUARDIAN_BOT_TOKEN",),
        "niles": ("NILES_BOT_TOKEN", "PRODUCER_BOT_TOKEN"),
        "hermes": ("HERMES_BOT_TOKEN",),
    }
    for env_name in mapping[agent]:
        if os.environ.get(env_name):
            return env_name
    raise RuntimeError(f"No Telegram bot token configured for agent voice lane {agent!r}.")


def _chat_id_for_agent(agent: str, chat_id: str | int | None) -> str:
    if chat_id is not None:
        return str(chat_id)
    for env_name in (f"{agent.upper()}_CHAT_ID", "TELEGRAM_AUTHORIZED_USER_ID", "TELEGRAM_CHAT_ID"):
        value = os.environ.get(env_name)
        if value:
            return str(value)
    raise RuntimeError(f"No Telegram chat id configured for agent voice lane {agent!r}.")


def _send_telegram_voice_note(agent: str, audio_path: str, *, chat_id: str | int | None = None) -> str:
    token_env = _token_env_for_agent(agent)
    token = os.environ[token_env]
    target_chat = _chat_id_for_agent(agent, chat_id)
    send_path = audio_path
    ogg_path: str | None = None
    try:
        if audio_path.lower().endswith(".wav"):
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise RuntimeError("ffmpeg not found for Telegram voice-note conversion")
            fd, ogg_path = tempfile.mkstemp(suffix=".ogg")
            os.close(fd)
            subprocess.run(
                [ffmpeg, "-y", "-loglevel", "error", "-i", audio_path, "-c:a", "libopus", "-b:a", "32k", ogg_path],
                check=True,
                timeout=30,
            )
            send_path = ogg_path
        with open(send_path, "rb") as handle:
            response = requests.post(
                f"https://api.telegram.org/bot{token}/sendVoice",
                data={"chat_id": target_chat},
                files={"voice": ("voice.ogg", handle, "audio/ogg")},
                timeout=30,
            )
        response.raise_for_status()
        return target_chat
    finally:
        if ogg_path and os.path.exists(ogg_path):
            try:
                os.unlink(ogg_path)
            except OSError:
                pass


def send_agent_voice_note(
    agent: str,
    text: str,
    *,
    wav_path: str | Path | None = None,
    chat_id: str | int | None = None,
    speed: float | None = None,
    send_voice_note_fn: SendVoiceNoteFn | None = None,
) -> AgentVoiceReceipt:
    """Synthesize and send an agent voice note through that agent's Telegram lane."""
    receipt = synthesize_agent_wav(agent, text, wav_path=wav_path, speed=speed)
    if not receipt.synthesized:
        return receipt
    try:
        if send_voice_note_fn is None:
            resolved_chat = _send_telegram_voice_note(receipt.agent, receipt.wav_path, chat_id=chat_id)
            token_env = _token_env_for_agent(receipt.agent)
        else:
            resolved_chat = str(chat_id) if chat_id is not None else None
            token_env = None
            send_voice_note_fn(receipt.wav_path, chat_id=resolved_chat)
        return AgentVoiceReceipt(
            receipt.agent,
            receipt.voice,
            receipt.wav_path,
            True,
            sent=True,
            chat_id=resolved_chat,
            token_env=token_env,
        )
    except Exception as exc:
        return AgentVoiceReceipt(
            receipt.agent,
            receipt.voice,
            receipt.wav_path,
            True,
            sent=False,
            chat_id=str(chat_id) if chat_id is not None else None,
            error=str(exc),
        )


__all__ = [
    "AgentVoiceReceipt",
    "FIRST_CLASS_AGENTS",
    "send_agent_voice_note",
    "synthesize_agent_wav",
]

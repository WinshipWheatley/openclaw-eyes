"""
cassandra_voice.py

Cassandra local TTS with two voice lanes.

Voice lanes
-----------
  live   — Kokoro-82M primary → Piper fallback
           Used by: all live Telegram replies, watcher chirps
  batch  — Qwen3-TTS-0.6B primary → Kokoro fallback → Piper fallback
           Used by: scheduled briefings and long recap summaries only

Content/social replies
----------------------
  speak() and speak_batch() both accept a suppress=True flag.
  The Cassandra listener sets suppress=True for content/social-style replies
  so those stay text-only unless explicitly requested.

Environment variables
---------------------
  CASSANDRA_VOICE=1               enable speech (default: 0 = off)
  CASSANDRA_LIVE_BACKEND          live lane backend: kokoro (default) or piper
  CASSANDRA_BATCH_BACKEND         batch lane backend: qwen3 (default), kokoro, or piper
  CASSANDRA_VOICE_MODEL           Piper .onnx path
                                  default: /home/openclaw/piper_voices/en_GB-jenny_dioco-medium.onnx
  CASSANDRA_VOICE_LENGTH_SCALE    Piper: default 1.15
  CASSANDRA_VOICE_NOISE_SCALE     Piper: default 0.6
  CASSANDRA_VOICE_NOISE_W         Piper: default 0.8
  CASSANDRA_KOKORO_VOICE          default: af_heart
  CASSANDRA_KOKORO_SPEED          default: 0.9
  CASSANDRA_QWEN3_MODEL           default: Qwen/Qwen3-TTS-0.6B

Silence gates
-------------
  - Focus mode active  → no speech; text reply still sends
  - Social mode active → no speech; text reply still sends

Max chars spoken: 400 for live, 800 for batch.

If synthesis or playback fails, the exception is logged and swallowed —
Cassandra's text reply is unaffected.
"""

import io
import os
import re
import shutil
import subprocess
import threading
import time
import wave
from pathlib import Path

from cassandra_brain import is_focus_mode, is_social_mode
from chief_output_utils import tts_clean

# ── Env ───────────────────────────────────────────────────────────────────────

def _load_env_file() -> None:
    env_path = "/home/openclaw/.chief.env"
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.startswith("export "):
                    line = line[len("export "):].strip()
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass

_load_env_file()

# ── Config ────────────────────────────────────────────────────────────────────

VOICE_ENABLED  = os.environ.get("CASSANDRA_VOICE", "0") == "1"
LIVE_BACKEND   = os.environ.get("CASSANDRA_LIVE_BACKEND",  "kokoro").lower()
BATCH_BACKEND  = os.environ.get("CASSANDRA_BATCH_BACKEND", "qwen3").lower()
PREMIUM_BACKEND = "kokoro"

_KOKORO_VOICE = os.environ.get("CASSANDRA_KOKORO_VOICE", "af_heart")
_KOKORO_SPEED = os.environ.get("CASSANDRA_KOKORO_SPEED", "0.9")

# Piper-specific (used as fallback in both lanes)
VOICE_MODEL    = os.environ.get(
    "CASSANDRA_VOICE_MODEL",
    "/home/openclaw/piper_voices/en_GB-jenny_dioco-medium.onnx",
)
LENGTH_SCALE   = float(os.environ.get("CASSANDRA_VOICE_LENGTH_SCALE", "1.15"))
NOISE_SCALE    = float(os.environ.get("CASSANDRA_VOICE_NOISE_SCALE",  "0.6"))
NOISE_W        = float(os.environ.get("CASSANDRA_VOICE_NOISE_W",      "0.8"))

MAX_CHARS_LIVE  = 400
MAX_CHARS_BATCH = 800

# WAV temp files — on the C: drive so PowerShell SoundPlayer can reach them
_WAV_LIVE       = Path("/mnt/c/OpenClaw/logs/cassandra_speech.wav")
_WAV_BATCH      = Path("/mnt/c/OpenClaw/logs/cassandra_speech_batch.wav")
_WAV_REPLY      = Path("/mnt/c/OpenClaw/logs/cassandra_reply.wav")
_WAV_REPLY_LEGACY = Path("/mnt/c/OpenClaw/logs/cassandra_voice_note.wav")
_WIN_WAV_LIVE  = r"C:\OpenClaw\logs\cassandra_speech.wav"
_WIN_WAV_BATCH = r"C:\OpenClaw\logs\cassandra_speech_batch.wav"
_WIN_WAV_REPLY = r"C:\OpenClaw\logs\cassandra_reply.wav"

# ── Lazy Piper loader ─────────────────────────────────────────────────────────

_voice = None
_voice_lock = threading.Lock()
_reply_delivery_lock = threading.Lock()
_local_playback_lock = threading.Lock()
_local_playback_failed_at = 0.0
_LOCAL_PLAYBACK_TIMEOUT_SECONDS = 3
_LOCAL_PLAYBACK_COOLDOWN_SECONDS = 120


def _load_piper_voice():
    global _voice
    if _voice is not None:
        return _voice
    with _voice_lock:
        if _voice is None:
            from piper.voice import PiperVoice
            print(f"[cassandra_voice] loading Piper: {VOICE_MODEL}", flush=True)
            _voice = PiperVoice.load(VOICE_MODEL)
            print("[cassandra_voice] Piper ready.", flush=True)
    return _voice


# ── Low-level synth helpers ───────────────────────────────────────────────────

def _mark_local_playback_failure() -> None:
    global _local_playback_failed_at
    with _local_playback_lock:
        _local_playback_failed_at = time.monotonic()


def _clear_local_playback_failure() -> None:
    global _local_playback_failed_at
    with _local_playback_lock:
        _local_playback_failed_at = 0.0


def _local_playback_cooldown_remaining() -> float:
    with _local_playback_lock:
        failed_at = _local_playback_failed_at
    if failed_at <= 0:
        return 0.0
    remaining = _LOCAL_PLAYBACK_COOLDOWN_SECONDS - (time.monotonic() - failed_at)
    return max(0.0, remaining)


def _play_wav(win_path: str, wav_path: Path | None = None) -> tuple[bool, str | None]:
    cooldown_remaining = _local_playback_cooldown_remaining()
    if cooldown_remaining > 0:
        return False, f"cooldown active for {int(cooldown_remaining)}s after prior playback failure"
    if wav_path is not None and not wav_path.exists():
        _mark_local_playback_failure()
        return False, f"wav not found: {wav_path}"
    ps_exe = shutil.which("powershell.exe") or \
             "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    if not ps_exe or not Path(ps_exe).exists():
        _mark_local_playback_failure()
        return False, "powershell.exe not available for host playback"
    child_cmd = (
        f"$p = New-Object System.Media.SoundPlayer '{win_path}'; "
        "$p.PlaySync()"
    )
    ps_cmd = (
        "$ErrorActionPreference = 'Stop'; "
        f"$child = \"{ps_exe}\"; "
        f"$inner = \"{child_cmd.replace('\"', '`\"')}\"; "
        "Start-Process -WindowStyle Hidden "
        "-FilePath $child "
        "-ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-Command',$inner) "
        "| Out-Null"
    )
    try:
        result = subprocess.run(
            [ps_exe, "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=_LOCAL_PLAYBACK_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        _mark_local_playback_failure()
        return False, f"timed out after {_LOCAL_PLAYBACK_TIMEOUT_SECONDS}s"
    except Exception as e:
        _mark_local_playback_failure()
        return False, str(e)

    if result.returncode != 0:
        _mark_local_playback_failure()
        detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
        return False, detail

    _clear_local_playback_failure()
    return True, None


def _synth_piper(text: str, wav_path: Path) -> None:
    """Write Piper synthesis to wav_path without playing."""
    from piper.config import SynthesisConfig

    voice = _load_piper_voice()
    cfg   = SynthesisConfig(
        length_scale=LENGTH_SCALE,
        noise_scale=NOISE_SCALE,
        noise_w_scale=NOISE_W,
    )
    chunks = list(voice.synthesize(text, cfg))
    if not chunks:
        return

    buf = io.BytesIO()
    wf  = wave.open(buf, "wb")
    wf.setnchannels(chunks[0].sample_channels)
    wf.setsampwidth(chunks[0].sample_width)
    wf.setframerate(chunks[0].sample_rate)
    for c in chunks:
        wf.writeframes(c.audio_int16_bytes)
    wf.close()

    wav_path.parent.mkdir(parents=True, exist_ok=True)
    wav_path.write_bytes(buf.getvalue())


def _speak_piper(text: str, wav_path: Path, win_path: str) -> None:
    _synth_piper(text, wav_path)
    ok, reason = _play_wav(win_path, wav_path)
    if not ok:
        raise RuntimeError(reason or "local playback failed")


def _synth_plugin(text: str, backend_name: str, wav_path: Path) -> bool:
    """Attempt synthesis via a cassandra_tts_backends backend. Returns True on success."""
    try:
        from cassandra_tts_backends import get_backend
        backend = get_backend(backend_name)
        return backend.synthesize(text, wav_path)
    except Exception as e:
        print(f"[cassandra_voice] {backend_name} failed: {e}", flush=True)
        return False


def _speak_plugin(text: str, backend_name: str, wav_path: Path, win_path: str) -> bool:
    """Attempt synthesis via a cassandra_tts_backends backend. Returns True on success."""
    ok = _synth_plugin(text, backend_name, wav_path)
    if ok:
        played, reason = _play_wav(win_path, wav_path)
        if not played:
            raise RuntimeError(reason or "local playback failed")
    return ok


def _normalize_tts_subject_markers(text: str) -> str:
    replacements = {
        "re": "Reply",
        "fw": "Forwarded",
        "fwd": "Forwarded",
    }

    def _repl(match: re.Match[str]) -> str:
        return f"{replacements[match.group(1).lower()]}: "

    return re.sub(r"(?i)\b(re|fw|fwd)\s*:\s*", _repl, str(text or ""))


def _normalize_tts_line_pauses(text: str) -> str:
    labels = (
        "from clara",
        "ball state",
        "status",
        "current live email thread subject",
        "conversation",
        "waiting on winship",
        "cassandra is trying to",
        "from",
        "subject",
    )
    out: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if line.endswith(":") and any(lower[:-1].strip() == label for label in labels):
            out.append(f"{line[:-1].strip()}.")
            continue
        if line[-1] not in ".!?;:":
            word_count = len(line.split())
            if word_count <= 4 or any(lower == label for label in labels):
                line = f"{line}."
        out.append(line)
    return "\n".join(out)


def _trim_tts_text(text: str, limit: int = MAX_CHARS_BATCH) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(clean) <= limit:
        return clean

    for marker in (". ", "! ", "? "):
        cut = clean.rfind(marker, 0, limit)
        if cut >= max(limit // 2, 1):
            return clean[: cut + 1].strip()

    cut = clean.rfind(" ", 0, limit)
    if cut > 0:
        return clean[:cut].strip()
    return clean[:limit].strip()


def _prepare_tts_text(text: str, limit: int) -> str:
    clean = tts_clean(str(text or ""))
    clean = _normalize_tts_subject_markers(clean)
    clean = _normalize_tts_line_pauses(clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return _trim_tts_text(clean, limit)


def _cleanup_unused_reply_wavs() -> None:
    if _WAV_REPLY_LEGACY.exists():
        try:
            _WAV_REPLY_LEGACY.unlink()
        except Exception:
            pass


def _mirror_reply_wav_to_live_path() -> None:
    try:
        if _WAV_REPLY.exists():
            _WAV_LIVE.write_bytes(_WAV_REPLY.read_bytes())
    except Exception as e:
        print(f"[cassandra_voice] live mirror failed: {e}", flush=True)


def _synthesize_live_lane(text: str, wav_path: Path) -> bool:
    print(
        f"[cassandra_voice] live premium lane={PREMIUM_BACKEND} voice={_KOKORO_VOICE} speed={_KOKORO_SPEED}",
        flush=True,
    )
    ok = _synth_plugin(text, PREMIUM_BACKEND, wav_path)
    if ok:
        return True

    backend = LIVE_BACKEND if LIVE_BACKEND != "qwen3" else "kokoro"
    if backend == "piper":
        _synth_piper(text, wav_path)
        return True

    ok = _synth_plugin(text, backend, wav_path)
    if ok:
        return True

    print("[cassandra_voice] live fallback → Piper", flush=True)
    _synth_piper(text, wav_path)
    return True


# ── Lane runners (called inside daemon threads) ───────────────────────────────

def _live_sync(text: str) -> None:
    """
    Live lane: Kokoro → Piper.
    Qwen3 is never used here regardless of LIVE_BACKEND value.
    """
    try:
        _synthesize_live_lane(text, _WAV_LIVE)
        played, reason = _play_wav(_WIN_WAV_LIVE, _WAV_LIVE)
        if played:
            print(f"[cassandra_voice] live spoke ({len(text)} chars)", flush=True)
        else:
            print(f"[cassandra_voice] live playback degraded: {reason}", flush=True)
    except Exception as e:
        print(f"[cassandra_voice] live error: {e}", flush=True)


def _batch_sync(text: str) -> None:
    """
    Batch lane: Qwen3 → Kokoro → Piper.
    Intended for scheduled briefings and long summaries.
    High latency is acceptable.
    """
    try:
        primary = BATCH_BACKEND  # default qwen3

        if primary == "piper":
            _speak_piper(text, _WAV_BATCH, _WIN_WAV_BATCH)
            print(f"[cassandra_voice] batch spoke via Piper ({len(text)} chars)", flush=True)
            return

        ok = _speak_plugin(text, primary, _WAV_BATCH, _WIN_WAV_BATCH)
        if ok:
            print(f"[cassandra_voice] batch spoke via {primary} ({len(text)} chars)", flush=True)
            return

        # Fallback chain: if qwen3 failed, try kokoro before piper
        if primary == "qwen3":
            print("[cassandra_voice] batch fallback → Kokoro", flush=True)
            ok = _speak_plugin(text, "kokoro", _WAV_BATCH, _WIN_WAV_BATCH)
            if ok:
                print(f"[cassandra_voice] batch spoke via kokoro ({len(text)} chars)", flush=True)
                return

        print("[cassandra_voice] batch fallback → Piper", flush=True)
        _speak_piper(text, _WAV_BATCH, _WIN_WAV_BATCH)
        print(f"[cassandra_voice] batch spoke via Piper ({len(text)} chars)", flush=True)

    except Exception as e:
        print(f"[cassandra_voice] batch error: {e}", flush=True)


# ── Public API ────────────────────────────────────────────────────────────────

def speak(text: str, suppress: bool = False) -> None:
    import harness_context
    if harness_context.is_harness_mode():
        print(f"[harness] no-voice Speak: {text[:50]}...", flush=True)
        return
    """
    Live-lane TTS: Kokoro → Piper fallback. Non-blocking.
    suppress=True skips voice (used for content/social replies).
    Text reply to Telegram is always sent first; this is secondary.
    """
    if not VOICE_ENABLED or suppress:
        return
    if is_focus_mode() or is_social_mode():
        print("[cassandra_voice] silenced by gate", flush=True)
        return

    clean = _prepare_tts_text(text, MAX_CHARS_LIVE)
    if not clean:
        return

    threading.Thread(target=_live_sync, args=(clean,), daemon=True).start()


def speak_batch(text: str) -> None:
    import harness_context
    if harness_context.is_harness_mode():
        print(f"[harness] no-voice Speak-Batch: {text[:50]}...", flush=True)
        return
    """
    Batch-lane TTS: Qwen3 → Kokoro → Piper fallback. Non-blocking.
    For scheduled briefings and long summaries only.
    Respects focus/social gates. Does NOT truncate at MAX_CHARS_LIVE.
    """
    if not VOICE_ENABLED:
        return
    if is_focus_mode() or is_social_mode():
        print("[cassandra_voice] batch silenced by gate", flush=True)
        return

    clean = _prepare_tts_text(text, MAX_CHARS_BATCH)
    if not clean:
        return

    threading.Thread(target=_batch_sync, args=(clean,), daemon=True).start()


def synthesize_for_voice_note(text: str) -> "Path | None":
    """
    Synthesize text to a WAV file for Telegram voice note upload.
    Synchronous — no playback. Returns the WAV path on success, None on failure.
    Respects VOICE_ENABLED and focus/social gates (no audio generated when silenced).
    """
    if not VOICE_ENABLED:
        return None
    if is_focus_mode() or is_social_mode():
        return None

    clean = _prepare_tts_text(text, MAX_CHARS_BATCH)
    if not clean:
        return None

    try:
        with _reply_delivery_lock:
            _cleanup_unused_reply_wavs()
            _synthesize_live_lane(clean, _WAV_REPLY)
            return _WAV_REPLY
    except Exception as e:
        print(f"[cassandra_voice] voice_note synth error: {e}", flush=True)
        return None


def _deliver_dual_voice_reply_sync(text: str, chat_id: str | int | None = None) -> None:
    if not VOICE_ENABLED:
        return
    if is_focus_mode() or is_social_mode():
        print("[cassandra_voice] dual voice silenced by gate", flush=True)
        return

    clean = _prepare_tts_text(text, MAX_CHARS_BATCH)
    if not clean:
        return

    try:
        from cassandra_sender import send_voice_note

        with _reply_delivery_lock:
            _cleanup_unused_reply_wavs()
            _synthesize_live_lane(clean, _WAV_REPLY)
            _mirror_reply_wav_to_live_path()
            played, reason = _play_wav(_WIN_WAV_LIVE, _WAV_LIVE)
            if played:
                print(f"[cassandra_voice] local playback ok ({len(clean)} chars)", flush=True)
            else:
                print(
                    f"[cassandra_voice] local playback degraded; Telegram voice continues: {reason}",
                    flush=True,
                )
            send_voice_note(str(_WAV_REPLY), chat_id=str(chat_id) if chat_id is not None else None)
        print(f"[cassandra_voice] dual voice delivered ({len(clean)} chars)", flush=True)
    except Exception as e:
        print(f"[cassandra_voice] dual voice error: {e}", flush=True)


def speak_and_send_voice_note(text: str, chat_id: str | int | None = None, suppress: bool = False) -> None:
    """
    Render one reply WAV and fan it out to both local playback and Telegram voice note.
    Non-blocking. Used for operator-facing reply delivery so the two outputs stay in sync.
    """
    import harness_context
    if harness_context.is_harness_mode():
        print(f"[harness] no-voice Dual: {str(text)[:50]}...", flush=True)
        return
    if not VOICE_ENABLED or suppress:
        return
    if is_focus_mode() or is_social_mode():
        print("[cassandra_voice] dual voice silenced by gate", flush=True)
        return

    threading.Thread(
        target=_deliver_dual_voice_reply_sync,
        args=(text, chat_id),
        daemon=True,
    ).start()

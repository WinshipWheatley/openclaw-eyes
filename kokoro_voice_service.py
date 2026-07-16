#!/usr/bin/env python3
"""Warm localhost Kokoro voice-synth service.

The conversational Hermes runs through the vendored gateway in its OWN venv
(py3.11, no Kokoro/torch). To give him the SAME local Kokoro voice the other
five agents use (am_echo) WITHOUT loading a torch model per message (GPU
contention on the ~6GB box) or installing Kokoro a second time, this service
holds ONE warm KPipeline (in chief_env) and synthesizes on request over
127.0.0.1. Local-only, $0, no external network calls.

  POST /synth   {"agent": "hermes", "text": "..."}  -> {"ok": true, "ogg": "/path.ogg", "format": "ogg"}
  GET  /health                                       -> {"ok": true, "warm": <bool>}

The gateway client (kokoro_voice_client.py, stdlib-only) calls this and hands the
returned file to the gateway's own Telegram adapter, so there is exactly one
voice note per reply (it reuses the gateway's send pipeline + dedup).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = int(os.environ.get("OPENCLAW_KOKORO_VOICE_PORT", "8771"))
DEFAULT_OUT_DIR = Path(os.environ.get("OPENCLAW_KOKORO_VOICE_DIR", "/tmp/openclaw_kokoro_voice"))

_WARM = False
_REQUEST_LOCK = threading.Lock()


def wav_to_ogg(wav_path: str) -> str | None:
    """Convert a wav to OGG/Opus (Telegram voice-bubble format). None if ffmpeg is absent/fails."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    ogg = wav_path.rsplit(".", 1)[0] + ".ogg"
    try:
        proc = subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-i", wav_path, "-c:a", "libopus", "-b:a", "32k", ogg],
            capture_output=True, timeout=30,
        )
    except Exception:
        return None
    return ogg if proc.returncode == 0 and os.path.isfile(ogg) else None


def _default_synth(agent: str, text: str, wav_path: str) -> tuple[bool, str]:
    import agent_voice_sender  # heavy (Kokoro) — only imported in the service process
    receipt = agent_voice_sender.synthesize_agent_wav(agent, text, wav_path=wav_path)
    return bool(receipt.synthesized), receipt.wav_path


def build_voice_audio(
    agent: str,
    text: str,
    *,
    synth_fn: Callable[[str, str, str], tuple[bool, str]] = _default_synth,
    convert_fn: Callable[[str], str | None] = wav_to_ogg,
    out_dir: str | Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    """Synthesize ``agent``'s Kokoro voice for ``text`` and convert to OGG. Pure + injectable."""
    if not text or not text.strip():
        return {"ok": False, "error": "empty_text"}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    wav_path = str(out / f"{agent}_{uuid4().hex[:12]}.wav")
    try:
        ok, wav = synth_fn(agent, text, wav_path)
    except Exception as exc:  # never let a synth crash take down the service
        return {"ok": False, "error": f"synth_error:{exc}"}
    if not ok or not wav or not os.path.isfile(wav):
        return {"ok": False, "error": "synth_failed"}
    ogg = convert_fn(wav)
    if ogg:
        return {"ok": True, "ogg": ogg, "wav": wav, "format": "ogg"}
    # ffmpeg missing — deliver the wav rather than nothing (Telegram still accepts it as voice)
    return {"ok": True, "ogg": None, "wav": wav, "format": "wav"}


def build_voice_audio_guarded(
    agent: str,
    text: str,
    *,
    synth_fn: Callable[[str, str, str], tuple[bool, str]] = _default_synth,
    convert_fn: Callable[[str], str | None] = wav_to_ogg,
    out_dir: str | Path = DEFAULT_OUT_DIR,
    request_lock: threading.Lock = _REQUEST_LOCK,
) -> dict[str, Any]:
    """Run at most one synthesis; reject contention instead of queueing it."""

    if not request_lock.acquire(blocking=False):
        return {"ok": False, "error": "busy"}
    try:
        return build_voice_audio(
            agent,
            text,
            synth_fn=synth_fn,
            convert_fn=convert_fn,
            out_dir=out_dir,
        )
    finally:
        request_lock.release()


def cleanup_result_audio(result: dict[str, Any]) -> None:
    """Remove only audio artifacts named by a completed synthesis result."""

    seen: set[Path] = set()
    for key in ("wav", "ogg"):
        value = result.get(key)
        if not isinstance(value, str) or not value:
            continue
        path = Path(value)
        if path in seen or path.suffix.lower() not in {".wav", ".ogg"}:
            continue
        seen.add(path)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


class _Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict[str, Any]) -> bool:
        body = json.dumps(payload).encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return True
        except (BrokenPipeError, ConnectionResetError):
            return False

    def log_message(self, *args: Any) -> None:  # quiet
        pass

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self._json(200, {"ok": True, "warm": _WARM})
        else:
            self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/synth":
            self._json(404, {"ok": False, "error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
            agent = str(data.get("agent") or "hermes")
            text = str(data.get("text") or "")
        except Exception:
            self._json(400, {"ok": False, "error": "bad_request"})
            return
        result = build_voice_audio_guarded(agent, text)
        delivered = self._json(200 if result.get("ok") else 422, result)
        if not delivered:
            cleanup_result_audio(result)


def main() -> int:
    global _WARM
    DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Warm the model so the first real request is fast (load KPipeline once, here).
    try:
        warm = build_voice_audio_guarded("hermes", "Voice service online.")
        _WARM = bool(warm.get("ok"))
    except Exception:
        _WARM = False
    server = ThreadingHTTPServer((DEFAULT_HOST, DEFAULT_PORT), _Handler)
    print(f"kokoro_voice_service on http://{DEFAULT_HOST}:{DEFAULT_PORT} (warm={_WARM})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Stdlib-only client for the warm Kokoro voice service (kokoro_voice_service.py).

Lives on the gateway side, where the venv is py3.11 with NO Kokoro/torch — so this
module imports nothing heavy. It POSTs reply text to the warm synth service and
returns a local audio-file PATH for the gateway's Telegram adapter to send. Every
failure (service down, synth failure, bad response) returns None so the gateway
keeps replying with text even when voice is unavailable.
"""
from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

DEFAULT_URL = os.environ.get("OPENCLAW_KOKORO_VOICE_URL", "http://127.0.0.1:8771")


@dataclass(frozen=True)
class SynthesisResult:
    path: str | None
    error: str
    timeout_seconds: float


def synthesis_timeout_seconds(text: str) -> float:
    """Scale the client budget for speech length, bounded to two minutes."""

    length = len(str(text or ""))
    if length <= 160:
        return 15.0
    return min(120.0, 15.0 + ((length - 160) / 8.0))


def request_synthesis(
    text: str,
    *,
    agent: str = "hermes",
    base_url: str | None = None,
    timeout: float | None = None,
    opener: Callable | None = None,
) -> SynthesisResult:
    """Request one warm synthesis and preserve the failure class for callers."""

    budget = float(timeout) if timeout is not None else synthesis_timeout_seconds(text)
    if not text or not text.strip():
        return SynthesisResult(path=None, error="empty_text", timeout_seconds=budget)
    url = (base_url or DEFAULT_URL).rstrip("/") + "/synth"
    body = json.dumps({"agent": agent, "text": text}).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        raw = (opener or urlopen)(req, timeout=budget).read()
        data = json.loads(raw)
    except HTTPError as exc:
        try:
            data = json.loads(exc.read())
        except Exception:
            return SynthesisResult(path=None, error="unavailable", timeout_seconds=budget)
    except (TimeoutError, socket.timeout):
        return SynthesisResult(path=None, error="timeout", timeout_seconds=budget)
    except Exception:
        return SynthesisResult(path=None, error="unavailable", timeout_seconds=budget)
    if not isinstance(data, dict):
        return SynthesisResult(path=None, error="invalid_response", timeout_seconds=budget)
    if not data.get("ok"):
        error = str(data.get("error") or "synth_failed")
        return SynthesisResult(path=None, error=error, timeout_seconds=budget)
    path = data.get("ogg") or data.get("wav")
    return SynthesisResult(
        path=str(path) if path else None,
        error="" if path else "missing_audio_path",
        timeout_seconds=budget,
    )


def synthesize_remote(
    text: str,
    *,
    agent: str = "hermes",
    base_url: str | None = None,
    timeout: float = 15.0,
    opener: Callable | None = None,
) -> str | None:
    """POST ``text`` to the warm Kokoro service; return an audio file path, or None (fail-soft)."""
    return request_synthesis(
        text,
        agent=agent,
        base_url=base_url,
        timeout=timeout,
        opener=opener,
    ).path

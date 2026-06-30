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
from typing import Callable
from urllib.request import Request, urlopen

DEFAULT_URL = os.environ.get("OPENCLAW_KOKORO_VOICE_URL", "http://127.0.0.1:8771")


def synthesize_remote(
    text: str,
    *,
    agent: str = "hermes",
    base_url: str | None = None,
    timeout: float = 15.0,
    opener: Callable | None = None,
) -> str | None:
    """POST ``text`` to the warm Kokoro service; return an audio file path, or None (fail-soft)."""
    if not text or not text.strip():
        return None
    url = (base_url or DEFAULT_URL).rstrip("/") + "/synth"
    body = json.dumps({"agent": agent, "text": text}).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        raw = (opener or urlopen)(req, timeout=timeout).read()
        data = json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, dict) or not data.get("ok"):
        return None
    return data.get("ogg") or data.get("wav")

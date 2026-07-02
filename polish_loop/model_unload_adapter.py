"""Live model-unload adapter for the polish-loop builder.

A small, side-effect-bounded helper that asks a locally running ollama daemon to
unload a model immediately (``keep_alive=0``) so a preempting interactive session can
have the GPU back promptly. This module never starts, stops, or supervises ollama --
it only makes one best-effort POST and always returns an honest status dict; it never
raises, so a builder can call it opportunistically between build units without needing
its own try/except scaffolding.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable


DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_TIMEOUT_SECONDS = 5.0

UrlOpen = Callable[..., Any]


def unload_model(
    model: str,
    *,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    urlopen: UrlOpen = urllib.request.urlopen,
) -> dict[str, Any]:
    """Ask ollama to unload ``model`` immediately.

    Returns a dict with at least ``status`` and ``model`` keys. ``status`` is one of:
      - "unloaded": the request was sent and ollama returned a response.
      - "skipped": ``model`` was empty; no network call was made.
      - "error": the request could not be completed (network error, timeout, or any
        other unexpected exception). ``reason`` carries a short diagnostic string.

    This function never raises -- callers can invoke it opportunistically (e.g. right
    before yielding the GPU back to a preempting interactive session) without wrapping
    it in their own error handling.
    """
    model = str(model or "").strip()
    if not model:
        return {"status": "skipped", "reason": "empty_model_name", "model": model}

    payload = json.dumps({"model": model, "prompt": "", "keep_alive": 0}).encode("utf-8")
    request = urllib.request.Request(
        f"{str(base_url).rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            status_code = getattr(response, "status", 200)
            response.read()
        return {"status": "unloaded", "model": model, "http_status": status_code}
    except Exception as exc:  # noqa: BLE001 - this adapter must never raise
        return {
            "status": "error",
            "reason": f"{exc.__class__.__name__}: {exc}",
            "model": model,
        }


__all__ = ["unload_model", "DEFAULT_OLLAMA_BASE_URL", "DEFAULT_TIMEOUT_SECONDS"]

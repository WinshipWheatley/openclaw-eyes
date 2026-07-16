from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kokoro_voice_client as client  # noqa: E402


def _opener_returning(payload):
    def _open(req, timeout=None):
        return io.BytesIO(json.dumps(payload).encode("utf-8"))
    return _open


def _opener_boom(req, timeout=None):
    raise ConnectionRefusedError("service down")


def _opener_timeout(req, timeout=None):
    raise TimeoutError("synthesis exceeded client budget")


def test_returns_ogg_path_on_success():
    path = client.synthesize_remote("hi", agent="hermes",
                                    opener=_opener_returning({"ok": True, "ogg": "/x.ogg", "format": "ogg"}))
    assert path == "/x.ogg"


def test_prefers_ogg_but_falls_back_to_wav():
    path = client.synthesize_remote("hi", opener=_opener_returning({"ok": True, "ogg": None, "wav": "/x.wav"}))
    assert path == "/x.wav"


def test_service_down_returns_none_not_raises():
    # Fail-soft: the gateway must keep replying even if the voice service is offline.
    assert client.synthesize_remote("hi", opener=_opener_boom) is None


def test_request_result_distinguishes_timeout_from_unavailable_service():
    timed_out = client.request_synthesis("hi", opener=_opener_timeout)
    unavailable = client.request_synthesis("hi", opener=_opener_boom)

    assert timed_out.path is None and timed_out.error == "timeout"
    assert unavailable.path is None and unavailable.error == "unavailable"


def test_timeout_budget_scales_with_text_and_is_bounded():
    assert client.synthesis_timeout_seconds("short") == 15.0
    assert 15.0 < client.synthesis_timeout_seconds("x" * 400) < 120.0
    assert client.synthesis_timeout_seconds("x" * 10_000) == 120.0


def test_not_ok_returns_none():
    assert client.synthesize_remote("hi", opener=_opener_returning({"ok": False, "error": "synth_failed"})) is None


def test_busy_response_is_preserved_for_backpressure():
    result = client.request_synthesis("hi", opener=_opener_returning({"ok": False, "error": "busy"}))

    assert result.path is None and result.error == "busy"


def test_http_error_body_preserves_busy_backpressure() -> None:
    def opener(req, timeout=None):
        raise HTTPError(
            req.full_url,
            422,
            "Unprocessable Entity",
            {},
            io.BytesIO(json.dumps({"ok": False, "error": "busy"}).encode("utf-8")),
        )

    result = client.request_synthesis("hi", opener=opener)

    assert result.path is None and result.error == "busy"


def test_posts_agent_and_text_to_synth_endpoint():
    seen = {}

    def _open(req, timeout=None):
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data)
        return io.BytesIO(json.dumps({"ok": True, "ogg": "/o.ogg"}).encode("utf-8"))

    client.synthesize_remote("hello world", agent="hermes", base_url="http://127.0.0.1:8771", opener=_open)
    assert seen["url"].endswith("/synth")
    assert seen["body"] == {"agent": "hermes", "text": "hello world"}

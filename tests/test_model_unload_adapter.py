from __future__ import annotations

import json
import socket
import urllib.error

from polish_loop.model_unload_adapter import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    unload_model,
)


class _FakeResponse:
    def __init__(self, *, status: int = 200, body: bytes = b"{}"):
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc_info) -> bool:
        return False


def test_unload_model_posts_keep_alive_zero_to_ollama_generate():
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeResponse(status=200)

    result = unload_model("ornith:9b", urlopen=fake_urlopen)

    assert captured["url"] == f"{DEFAULT_OLLAMA_BASE_URL}/api/generate"
    assert captured["method"] == "POST"
    assert captured["body"] == {"model": "ornith:9b", "prompt": "", "keep_alive": 0}
    assert captured["timeout"] == DEFAULT_TIMEOUT_SECONDS
    assert result["status"] == "unloaded"
    assert result["model"] == "ornith:9b"
    assert result["http_status"] == 200


def test_unload_model_uses_custom_base_url_and_timeout():
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return _FakeResponse(status=200)

    unload_model(
        "chief-fast:latest",
        base_url="http://127.0.0.1:9999/",
        timeout=1.5,
        urlopen=fake_urlopen,
    )

    assert captured["url"] == "http://127.0.0.1:9999/api/generate"
    assert captured["timeout"] == 1.5


def test_unload_model_never_raises_on_connection_refused():
    def fake_urlopen(request, timeout=None):
        raise urllib.error.URLError(ConnectionRefusedError("connection refused"))

    result = unload_model("ornith:9b", urlopen=fake_urlopen)

    assert result["status"] == "error"
    assert "connection" in result["reason"].lower() or "refused" in result["reason"].lower()
    assert result["model"] == "ornith:9b"


def test_unload_model_never_raises_on_timeout():
    def fake_urlopen(request, timeout=None):
        raise socket.timeout("timed out")

    result = unload_model("ornith:9b", urlopen=fake_urlopen)

    assert result["status"] == "error"
    assert result["model"] == "ornith:9b"


def test_unload_model_never_raises_on_unexpected_exception():
    def fake_urlopen(request, timeout=None):
        raise ValueError("boom")

    result = unload_model("ornith:9b", urlopen=fake_urlopen)

    assert result["status"] == "error"
    assert "boom" in result["reason"]


def test_unload_model_skips_empty_model_name_without_network_call():
    calls: list[object] = []

    def fake_urlopen(request, timeout=None):
        calls.append(request)
        return _FakeResponse(status=200)

    result = unload_model("", urlopen=fake_urlopen)

    assert result["status"] == "skipped"
    assert result["reason"] == "empty_model_name"
    assert calls == []

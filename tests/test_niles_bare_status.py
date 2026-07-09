"""Tests for the Niles bare-status doctrine (task 143, CLASS #4).

Live evidence (pass-1): Niles has zero status awareness -- a bare "status?" would be
parsed by the production-intent parser as an unrecognized production question with no
action verb. These tests pin the fix: a bare status ask is answered deterministically
(no model call, no live X32 network ping) with rig state + tracks in flight.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _GuardMustNotPass(Exception):
    pass


class _FakeUser:
    def __init__(self, user_id):
        self.id = user_id


class _FakeMessage:
    def __init__(self, text):
        self.text = text
        self.replies = []

    async def reply_text(self, text, **kwargs):
        self.replies.append(text)


class _FakeUpdate:
    def __init__(self, text, user_id):
        self.message = _FakeMessage(text)
        self.effective_user = _FakeUser(user_id)
        self.effective_chat = types.SimpleNamespace(id=42)
        self.update_id = 7


class _FakeFilter:
    def __and__(self, other):
        return self

    def __invert__(self):
        return self


class _FakeBot:
    async def send_chat_action(self, chat_id, action):
        return None


def _load_producer_listener(monkeypatch):
    monkeypatch.setenv("PRODUCER_BOT_TOKEN", "test-token")
    monkeypatch.setenv("PRODUCER_AUTHORIZED_USER_ID", "123")
    fake_filters = types.SimpleNamespace(
        TEXT=_FakeFilter(), COMMAND=_FakeFilter(), VOICE=_FakeFilter()
    )

    class _FakeApplicationBuilder:
        def token(self, _token):
            return self

        def build(self):
            return types.SimpleNamespace(add_handler=lambda *a, **k: None, run_polling=lambda: None)

    monkeypatch.setitem(sys.modules, "telegram", types.SimpleNamespace(Update=object))
    monkeypatch.setitem(
        sys.modules,
        "telegram.ext",
        types.SimpleNamespace(
            ApplicationBuilder=_FakeApplicationBuilder,
            MessageHandler=lambda *a, **k: None,
            filters=fake_filters,
            ContextTypes=types.SimpleNamespace(DEFAULT_TYPE=object()),
        ),
    )
    sys.modules.pop("producer_listener", None)
    import producer_listener

    module = importlib.reload(producer_listener)
    monkeypatch.setattr(module, "record_telegram_listener_update_safe", lambda **kwargs: None)
    monkeypatch.setattr(module, "_queue_for_memory", lambda text: None)
    monkeypatch.setattr(module, "_fire_agent_voice", lambda *a, **k: None)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class TestIsBareStatusQuery:
    def test_bare_word_matches(self, monkeypatch):
        module = _load_producer_listener(monkeypatch)
        assert module._is_bare_status_query("status") is True
        assert module._is_bare_status_query("status?") is True

    def test_production_question_does_not_match(self, monkeypatch):
        module = _load_producer_listener(monkeypatch)
        assert module._is_bare_status_query("make it feel like a summer night") is False


class TestBuildNilesBareStatusAnswer:
    def test_fresh_registry_reports_tracks_and_rig(self, tmp_path, monkeypatch):
        module = _load_producer_listener(monkeypatch)
        _write_json(
            tmp_path / "generated" / "read_models" / "niles_track_registry.json",
            {"generated_at": "2026-07-01T00:00:00+00:00", "track_count": 12, "status_summary": {"idea": 12}},
        )
        monkeypatch.chdir(tmp_path)

        answer = module.build_niles_bare_status_answer()

        assert "Rig:" in answer
        assert "gated at my trust tier" in answer
        assert "Tracks: 12 in flight (12 idea)." in answer

    def test_never_pings_the_live_desk(self, tmp_path, monkeypatch):
        """The rig line must use the deterministic gated path, never a live network ping,
        so a hung/slow desk can never blow the shared status-answer speed budget."""
        module = _load_producer_listener(monkeypatch)
        _write_json(tmp_path / "generated" / "read_models" / "niles_track_registry.json", {"track_count": 0, "status_summary": {}})
        monkeypatch.chdir(tmp_path)

        def _forbidden_factory():
            raise _GuardMustNotPass("must not construct a live X32 controller")

        import niles_x32_capability

        monkeypatch.setattr(niles_x32_capability, "_handle_status", lambda allow_network, controller_factory: (_ for _ in ()).throw(_GuardMustNotPass("must not be called with network allowed")) if allow_network else {"reply": "gated"})

        answer = module.build_niles_bare_status_answer()
        assert "Rig: gated" in answer

    def test_stale_registry_excluded(self, tmp_path, monkeypatch):
        module = _load_producer_listener(monkeypatch)
        _write_json(
            tmp_path / "generated" / "read_models" / "niles_track_registry.json",
            {"generated_at": "2026-01-01T00:00:00+00:00", "track_count": 12, "status_summary": {"idea": 12}},
        )
        monkeypatch.chdir(tmp_path)

        answer = module.build_niles_bare_status_answer()

        assert "Tracks: registry data is stale, excluded." in answer
        assert "12 in flight" not in answer


class TestHandleMessageBareStatus:
    def test_bare_status_answered_before_producer_intake(self, monkeypatch, tmp_path):
        module = _load_producer_listener(monkeypatch)
        _write_json(
            tmp_path / "generated" / "read_models" / "niles_track_registry.json",
            {"generated_at": "2026-07-01T00:00:00+00:00", "track_count": 3, "status_summary": {"idea": 3}},
        )
        monkeypatch.chdir(tmp_path)

        async def _boom(payload):
            raise _GuardMustNotPass("producer intake ran for a bare status ask")

        monkeypatch.setattr(module, "_run_producer_intake", _boom)
        update = _FakeUpdate("status?", user_id=123)
        context = types.SimpleNamespace(bot=_FakeBot())
        asyncio.run(module.handle_message(update, context))

        assert len(update.message.replies) == 1
        assert "Tracks: 3 in flight" in update.message.replies[0]

    def test_production_question_still_reaches_intake(self, monkeypatch):
        module = _load_producer_listener(monkeypatch)

        async def _ok(payload):
            return "PRODUCTION-OK"

        monkeypatch.setattr(module, "_run_producer_intake", _ok)
        update = _FakeUpdate("make it feel like a summer night", user_id=123)
        context = types.SimpleNamespace(bot=_FakeBot())
        asyncio.run(module.handle_message(update, context))

        assert update.message.replies == ["PRODUCTION-OK"]

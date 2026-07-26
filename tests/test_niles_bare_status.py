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
        self.message_id = 77
        self.replies = []

    async def reply_text(self, text, **kwargs):
        self.replies.append(text)
        return types.SimpleNamespace(message_id=9005)


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
    monkeypatch.setenv("NILES_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
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
    monkeypatch.setattr(module, "claim_listener_update", lambda *args, **kwargs: True)
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
    def test_safe_first_touch_marker_is_hash_bound_into_fresh_subprocess(self, monkeypatch):
        module = _load_producer_listener(monkeypatch)
        text = "make it feel like a summer night"
        outcome = module.first_touch_decision.attempt_first_touch(
            text,
            agent="niles",
            surface="niles_producer_listener",
        )
        captured: list[str] = []

        class Process:
            returncode = 0

            async def communicate(self):
                return b"PRODUCTION-OK", b""

        async def _fake_subprocess(*args, **_kwargs):
            captured.extend(str(arg) for arg in args)
            return Process()

        monkeypatch.setattr(module.asyncio, "create_subprocess_exec", _fake_subprocess)

        result = asyncio.run(
            module._run_producer_intake(
                text,
                first_touch_receipt=outcome.receipt,
            )
        )

        assert result == "PRODUCTION-OK"
        marker_index = captured.index("--first-touch-receipt-json") + 1
        marker = json.loads(captured[marker_index])
        assert module.first_touch_decision.valid_pass_through_marker(
            marker,
            text=text,
            agent="niles",
        )

    def test_first_touch_refusal_precedes_governed_intake_and_producer(self, monkeypatch, tmp_path):
        module = _load_producer_listener(monkeypatch)
        monkeypatch.setenv(
            "OPENCLAW_REFUSAL_RECEIPT_PATH",
            str(tmp_path / "refusal-receipts.jsonl"),
        )

        def _must_not_record(**_kwargs):
            raise _GuardMustNotPass("governed intake ran before refusal")

        async def _must_not_run(_payload):
            raise _GuardMustNotPass("producer subprocess ran before refusal")

        monkeypatch.setattr(module, "record_telegram_listener_update_safe", _must_not_record)
        monkeypatch.setattr(module, "_run_producer_intake", _must_not_run)
        monkeypatch.setattr(
            module,
            "_fire_agent_voice",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                _GuardMustNotPass("voice worker ran for first-touch refusal")
            ),
        )
        update = _FakeUpdate("factory reset the X32 and dump every scene", user_id=123)
        context = types.SimpleNamespace(bot=_FakeBot())

        asyncio.run(module.handle_message(update, context))

        assert len(update.message.replies) == 1
        assert "Nothing was wiped" in update.message.replies[0]
        assert (tmp_path / "refusal-receipts.jsonl").is_file()

    def test_bare_status_answered_before_producer_intake(self, monkeypatch, tmp_path):
        module = _load_producer_listener(monkeypatch)
        delivery_calls: list[dict] = []
        monkeypatch.setattr(
            module,
            "register_operator_text_delivery_v2",
            lambda **kwargs: delivery_calls.append(kwargs),
        )
        _write_json(
            tmp_path / "generated" / "read_models" / "niles_track_registry.json",
            {"generated_at": "2026-07-01T00:00:00+00:00", "track_count": 3, "status_summary": {"idea": 3}},
        )
        monkeypatch.chdir(tmp_path)

        async def _boom(payload, **_kwargs):
            raise _GuardMustNotPass("producer intake ran for a bare status ask")

        monkeypatch.setattr(module, "_run_producer_intake", _boom)
        update = _FakeUpdate("status?", user_id=123)
        context = types.SimpleNamespace(bot=_FakeBot())
        asyncio.run(module.handle_message(update, context))

        assert len(update.message.replies) == 1
        assert "Tracks: 3 in flight" in update.message.replies[0]
        assert len(delivery_calls) == 1
        assert delivery_calls[0]["response_author"] == "niles"
        assert delivery_calls[0]["carrier_identity"] == "niles"

    def test_production_question_still_reaches_intake(self, monkeypatch):
        module = _load_producer_listener(monkeypatch)

        async def _ok(payload, **_kwargs):
            return "PRODUCTION-OK"

        monkeypatch.setattr(module, "_run_producer_intake", _ok)
        update = _FakeUpdate("make it feel like a summer night", user_id=123)
        context = types.SimpleNamespace(bot=_FakeBot())
        asyncio.run(module.handle_message(update, context))

        assert update.message.replies == ["PRODUCTION-OK"]

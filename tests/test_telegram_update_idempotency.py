from __future__ import annotations

import asyncio
import importlib
import sqlite3
import sys
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from telegram_agent_intake import (
    TelegramUpdateClaimDisposition,
    VerifiedTelegramBotIdentity,
    claim_telegram_update,
)


def _identity(*, role: str = "chief", username: str = "chief_status_bot", bot_id: int = 4101):
    return VerifiedTelegramBotIdentity(
        role=role,
        expected_username=username,
        actual_username=username,
        actual_bot_id=bot_id,
        expected_bot_id=bot_id,
    )


def test_2112_pending_update_replay_is_claimed_once_independent_of_text_and_time(tmp_path: Path) -> None:
    db = tmp_path / "business.sqlite"
    first = claim_telegram_update(
        source_channel="chief_listener",
        telegram_update_id=2112,
        verified_identity=_identity(),
        db_path=db,
    )
    replay = claim_telegram_update(
        source_channel="chief_listener",
        telegram_update_id="2112",
        verified_identity=_identity(),
        db_path=db,
    )

    assert first.disposition is TelegramUpdateClaimDisposition.CLAIMED
    assert replay.disposition is TelegramUpdateClaimDisposition.DUPLICATE
    assert first.claim_key == replay.claim_key

    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT bot_role, expected_bot_username, actual_bot_username, actual_bot_id, telegram_update_id, source_channel "
            "FROM telegram_update_id_claims"
        ).fetchone()
    assert row == ("chief", "chief_status_bot", "chief_status_bot", 4101, "2112", "chief_listener")


def test_claim_survives_database_reopen_and_new_process_shape(tmp_path: Path) -> None:
    db = tmp_path / "business.sqlite"
    assert claim_telegram_update(
        source_channel="cassandra_listener",
        telegram_update_id=700,
        verified_identity=_identity(role="cassandra", username="cassandra_bot", bot_id=5002),
        db_path=db,
    ).disposition is TelegramUpdateClaimDisposition.CLAIMED

    # A fresh identity value object models a new process after restart.
    assert claim_telegram_update(
        source_channel="cassandra_listener",
        telegram_update_id=700,
        verified_identity=_identity(role="cassandra", username="cassandra_bot", bot_id=5002),
        db_path=str(db),
    ).disposition is TelegramUpdateClaimDisposition.DUPLICATE


def test_simultaneous_claims_have_exactly_one_winner(tmp_path: Path) -> None:
    db = tmp_path / "business.sqlite"

    def attempt(_index: int):
        return claim_telegram_update(
            source_channel="maestro_listener",
            telegram_update_id=9001,
            verified_identity=_identity(role="maestro", username="maestro_bot", bot_id=6003),
            db_path=db,
        ).disposition

    with ThreadPoolExecutor(max_workers=12) as pool:
        dispositions = list(pool.map(attempt, range(24)))

    assert dispositions.count(TelegramUpdateClaimDisposition.CLAIMED) == 1
    assert dispositions.count(TelegramUpdateClaimDisposition.DUPLICATE) == 23


def test_same_update_id_on_distinct_verified_bot_identity_is_not_a_collision(tmp_path: Path) -> None:
    db = tmp_path / "business.sqlite"
    chief = claim_telegram_update(
        source_channel="chief_listener",
        telegram_update_id=44,
        verified_identity=_identity(role="chief", username="chief_bot", bot_id=101),
        db_path=db,
    )
    maestro = claim_telegram_update(
        source_channel="maestro_listener",
        telegram_update_id=44,
        verified_identity=_identity(role="maestro", username="maestro_bot", bot_id=102),
        db_path=db,
    )

    assert chief.disposition is TelegramUpdateClaimDisposition.CLAIMED
    assert maestro.disposition is TelegramUpdateClaimDisposition.CLAIMED
    assert chief.claim_key != maestro.claim_key


def test_same_numeric_bot_and_update_collide_across_channel_role_and_username(tmp_path: Path) -> None:
    db = tmp_path / "business.sqlite"
    first = claim_telegram_update(
        source_channel="chief_listener",
        telegram_update_id=696,
        verified_identity=_identity(role="chief", username="chief_old_name", bot_id=4101),
        db_path=db,
    )
    replay_after_rename_or_crosswire = claim_telegram_update(
        source_channel="maestro_listener",
        telegram_update_id=696,
        verified_identity=_identity(role="maestro", username="maestro_or_renamed", bot_id=4101),
        db_path=db,
    )

    assert first.disposition is TelegramUpdateClaimDisposition.CLAIMED
    assert replay_after_rename_or_crosswire.disposition is TelegramUpdateClaimDisposition.DUPLICATE
    assert first.claim_key == replay_after_rename_or_crosswire.claim_key


def test_missing_update_id_and_store_failure_return_error_fail_closed(tmp_path: Path, monkeypatch) -> None:
    missing = claim_telegram_update(
        source_channel="guardian_listener",
        telegram_update_id=None,
        verified_identity=_identity(role="guardian", username="guardian_bot", bot_id=8004),
        db_path=tmp_path / "business.sqlite",
    )
    assert missing.disposition is TelegramUpdateClaimDisposition.ERROR
    assert missing.reason == "missing_update_id"

    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("secret path")))
    failed = claim_telegram_update(
        source_channel="guardian_listener",
        telegram_update_id=1,
        verified_identity=_identity(role="guardian", username="guardian_bot", bot_id=8004),
        db_path=tmp_path / "business.sqlite",
    )
    assert failed.disposition is TelegramUpdateClaimDisposition.ERROR
    assert failed.reason == "claim_store_unavailable:OSError"
    assert "secret path" not in repr(failed)


def _import_listener(module_name: str, monkeypatch):
    monkeypatch.setenv("MAESTRO_BOT_TOKEN", "maestro-token")
    monkeypatch.setenv("CHIEF_BOT_TOKEN", "chief-token")
    monkeypatch.setenv("CASSANDRA_BOT_TOKEN", "cassandra-token")
    monkeypatch.setenv("GUARDIAN_BOT_TOKEN", "guardian-token")
    monkeypatch.setenv("NILES_BOT_TOKEN", "niles-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "123")
    monkeypatch.setenv("PRODUCER_AUTHORIZED_USER_ID", "123")
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


class _AuthorizedDuplicateUpdate:
    update_id = 2112
    effective_user = SimpleNamespace(id=123, full_name="Operator")
    effective_chat = SimpleNamespace(id=123)
    message = SimpleNamespace(text="status?", voice=object())
    callback_query = SimpleNamespace(from_user=SimpleNamespace(id=123))


@pytest.mark.parametrize(
    ("module_name", "handler_name"),
    (
        ("maestro_listener", "handle_message"),
        ("maestro_listener", "handle_photo"),
        ("chief_listener", "handle_message"),
        ("chief_listener", "handle_callback"),
        ("cassandra_listener", "handle_message"),
        ("cassandra_listener", "handle_voice"),
        ("chief_guardian_listener", "handle_message"),
        ("chief_guardian_listener", "handle_callback_query"),
        ("producer_listener", "handle_message"),
    ),
)
def test_every_listener_adapter_duplicate_returns_before_reply_or_side_effect(
    module_name: str,
    handler_name: str,
    monkeypatch,
) -> None:
    module = _import_listener(module_name, monkeypatch)
    calls: list[str] = []

    def duplicate_guard(*args, **kwargs) -> bool:
        calls.append("claim")
        return False

    monkeypatch.setattr(module, "claim_listener_update", duplicate_guard)
    if module_name == "cassandra_listener":
        monkeypatch.setattr(module, "is_designated_contact_sender", lambda **kwargs: False)
    asyncio.run(getattr(module, handler_name)(_AuthorizedDuplicateUpdate(), SimpleNamespace()))

    assert calls == ["claim"]


def test_adapter_claim_guards_precede_business_side_effects() -> None:
    expected = {
        ("maestro_listener.py", "handle_message"): "record_maestro_intake_metadata",
        ("maestro_listener.py", "handle_photo"): "asyncio.create_task",
        ("chief_listener.py", "handle_message"): "record_telegram_listener_update_safe",
        ("chief_listener.py", "handle_callback"): "await query.answer",
        ("cassandra_listener.py", "handle_message"): 'print(',
        ("cassandra_listener.py", "handle_voice"): "await update.message.reply_text",
        ("chief_guardian_listener.py", "handle_message"): "record_telegram_listener_update_safe",
        ("chief_guardian_listener.py", "handle_callback_query"): "await query.answer",
        ("producer_listener.py", "handle_message"): "_queue_for_memory",
    }
    for (path, handler), side_effect in expected.items():
        source = open(path, encoding="utf-8").read()
        start = source.index(f"async def {handler}(")
        next_def = source.find("\nasync def ", start + 1)
        next_sync_def = source.find("\ndef ", start + 1)
        ends = [index for index in (next_def, next_sync_def) if index != -1]
        body = source[start : min(ends) if ends else len(source)]
        assert body.index("claim_listener_update") < body.index(side_effect)


@pytest.mark.parametrize(
    ("module_name", "handler_name"),
    (
        ("maestro_listener", "handle_message"),
        ("maestro_listener", "handle_photo"),
        ("chief_listener", "handle_message"),
        ("chief_listener", "handle_callback"),
        ("cassandra_listener", "handle_message"),
        ("cassandra_listener", "handle_voice"),
        ("chief_guardian_listener", "handle_message"),
        ("chief_guardian_listener", "handle_callback_query"),
        ("producer_listener", "handle_message"),
    ),
)
def test_unauthorized_updates_do_not_claim_or_reach_business_work(
    module_name: str,
    handler_name: str,
    monkeypatch,
) -> None:
    module = _import_listener(module_name, monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(module, "claim_listener_update", lambda *args, **kwargs: calls.append("claim") or True)
    if module_name == "cassandra_listener":
        monkeypatch.setattr(module, "is_designated_contact_sender", lambda **kwargs: False)

    unauthorized = SimpleNamespace(
        update_id=77,
        effective_user=SimpleNamespace(id=999, full_name="Untrusted"),
        effective_chat=SimpleNamespace(id=999),
        message=SimpleNamespace(text="run business work", voice=object()),
        callback_query=SimpleNamespace(from_user=SimpleNamespace(id=999)),
    )
    asyncio.run(getattr(module, handler_name)(unauthorized, SimpleNamespace()))

    assert calls == []


def test_hermes_post_batch_defense_uses_vendor_platform_update_id_before_reasoning(monkeypatch) -> None:
    import openclaw_hermes_gateway_policy as policy

    calls: list[tuple[str, int]] = []

    class Platform:
        value = "telegram"

    class GatewayRunner:
        def _is_user_authorized(self, _source):
            return True

        async def _handle_message(self, _event):
            raise AssertionError("duplicate Hermes event reached original handler")

    event = SimpleNamespace(
        text="status?",
        internal=False,
        platform_update_id=2112,
        source=SimpleNamespace(user_id="operator", platform=Platform()),
        get_command=lambda: None,
    )

    def duplicate_claim(received_event) -> bool:
        calls.append(("claim", received_event.platform_update_id))
        return False

    monkeypatch.setattr(policy, "_claim_hermes_telegram_event", duplicate_claim)
    module = SimpleNamespace(GatewayRunner=GatewayRunner)
    policy.install_gateway_policy_patch(gateway_run_module=module, base_adapter_cls=None)

    assert asyncio.run(GatewayRunner()._handle_message(event)) is None
    assert calls == [("claim", 2112)]


class _HermesMessageTypes:
    TEXT = "text"
    COMMAND = "command"
    LOCATION = "location"
    STICKER = "sticker"
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    VOICE = "voice"
    DOCUMENT = "document"


class _HermesPlatform:
    value = "telegram"


class _RawHermesMessage:
    def __init__(self, *, text: str = "", user_id: str = "operator", photo: bool = False, album: str | None = None):
        self.text = text
        self.caption = "album caption" if photo else None
        self.user_id = user_id
        self.photo = [object()] if photo else []
        self.media_group_id = album
        self.sticker = None
        self.video = None
        self.audio = None
        self.voice = None
        self.document = None
        self.location = None
        self.venue = None


class _RawHermesAdapter:
    def __init__(self, runner, timeline: list[str]):
        self._message_handler = runner._handle_message
        self.timeline = timeline
        self.pending_text = None
        self.pending_album = None
        self.original_text_calls = 0
        self.original_media_calls = 0
        self.original_callback_calls = 0

    def _should_process_message(self, _message, *, is_command=False):
        return True

    def _is_callback_user_authorized(self, user_id):
        self.timeline.append(f"callback-auth:{user_id}")
        return str(user_id) == "operator"

    def _build_message_event(self, message, message_type, update_id=None):
        self.timeline.append(f"build:{update_id}:{message_type}")
        return SimpleNamespace(
            text=message.text,
            source=SimpleNamespace(user_id=message.user_id, platform=_HermesPlatform()),
            platform_update_id=update_id,
            media_urls=[],
            media_types=[],
        )

    async def _handle_text_message(self, update, _context):
        self.original_text_calls += 1
        event = self._build_message_event(update.message, _HermesMessageTypes.TEXT, update_id=update.update_id)
        if self.pending_text is None:
            self.pending_text = event
        else:
            self.pending_text.text += "\n" + event.text

    async def _handle_command(self, update, _context):
        event = self._build_message_event(update.message, _HermesMessageTypes.COMMAND, update_id=update.update_id)
        await self._message_handler(event)

    async def _handle_location_message(self, update, _context):
        event = self._build_message_event(update.message, _HermesMessageTypes.LOCATION, update_id=update.update_id)
        await self._message_handler(event)

    async def _handle_media_message(self, update, _context):
        self.original_media_calls += 1
        event = self._build_message_event(update.message, _HermesMessageTypes.PHOTO, update_id=update.update_id)
        self.timeline.append(f"cache:{update.update_id}")
        event.media_urls.append(f"cache/{update.update_id}.jpg")
        if self.pending_album is None:
            self.pending_album = event
        else:
            self.pending_album.media_urls.extend(event.media_urls)

    async def _handle_callback_query(self, update, _context):
        self.original_callback_calls += 1
        self.timeline.append(f"callback-work:{update.update_id}:{update.callback_query.data}")


def _install_raw_hermes_fixture(monkeypatch, timeline: list[str]):
    import openclaw_hermes_gateway_policy as policy

    dispatched: list[object] = []

    class GatewayRunner:
        def _is_user_authorized(self, source):
            return source.user_id == "operator"

        async def _handle_message(self, event):
            dispatched.append(event)
            return "handled"

    claimed: set[int] = set()

    def claim(_event, update_id):
        numeric = int(update_id)
        timeline.append(f"claim:{numeric}")
        if numeric in claimed:
            return False
        claimed.add(numeric)
        return True

    monkeypatch.setattr(policy, "_claim_hermes_raw_update", claim)
    monkeypatch.setattr(
        policy,
        "_claim_hermes_telegram_event",
        lambda _event: (_ for _ in ()).throw(AssertionError("raw-preclaimed event was claimed twice")),
    )
    policy.install_gateway_policy_patch(
        gateway_run_module=SimpleNamespace(GatewayRunner=GatewayRunner),
        base_adapter_cls=None,
        telegram_adapter_cls=_RawHermesAdapter,
        message_type_cls=_HermesMessageTypes,
    )
    runner = GatewayRunner()
    return policy, runner, _RawHermesAdapter(runner, timeline), dispatched


def test_hermes_two_rapid_text_ids_are_each_claimed_before_batch_and_replay_is_suppressed(monkeypatch) -> None:
    timeline: list[str] = []
    _policy, runner, adapter, dispatched = _install_raw_hermes_fixture(monkeypatch, timeline)
    first = SimpleNamespace(update_id=3101, message=_RawHermesMessage(text="Please summarize the"))
    second = SimpleNamespace(update_id=3102, message=_RawHermesMessage(text="project notes from today."))

    asyncio.run(adapter._handle_text_message(first, SimpleNamespace()))
    asyncio.run(adapter._handle_text_message(second, SimpleNamespace()))
    asyncio.run(adapter._handle_text_message(first, SimpleNamespace()))
    asyncio.run(adapter._handle_text_message(second, SimpleNamespace()))

    assert timeline.count("claim:3101") == 2
    assert timeline.count("claim:3102") == 2
    assert adapter.original_text_calls == 2
    assert adapter.pending_text.text == "Please summarize the\nproject notes from today."
    assert adapter.pending_text._openclaw_raw_update_preclaimed is True
    asyncio.run(runner._handle_message(adapter.pending_text))
    assert dispatched == [adapter.pending_text]


def test_hermes_callback_authorizes_then_claims_before_vendor_work_and_suppresses_replay(monkeypatch) -> None:
    timeline: list[str] = []
    _policy, _runner, adapter, _dispatched = _install_raw_hermes_fixture(monkeypatch, timeline)
    query = SimpleNamespace(data="ea:once:17", from_user=SimpleNamespace(id="operator"))
    update = SimpleNamespace(update_id=5101, callback_query=query)

    asyncio.run(adapter._handle_callback_query(update, SimpleNamespace()))
    asyncio.run(adapter._handle_callback_query(update, SimpleNamespace()))

    assert timeline.count("callback-auth:operator") == 2
    assert timeline.count("claim:5101") == 2
    assert timeline.count("callback-work:5101:ea:once:17") == 1
    assert timeline.index("callback-auth:operator") < timeline.index("claim:5101")
    assert timeline.index("claim:5101") < timeline.index("callback-work:5101:ea:once:17")
    assert adapter.original_callback_calls == 1


def test_hermes_unauthorized_or_empty_callback_never_claims_or_reaches_vendor_work(monkeypatch) -> None:
    timeline: list[str] = []
    _policy, _runner, adapter, _dispatched = _install_raw_hermes_fixture(monkeypatch, timeline)
    unauthorized = SimpleNamespace(
        update_id=5201,
        callback_query=SimpleNamespace(data="mm:0", from_user=SimpleNamespace(id="stranger")),
    )
    empty = SimpleNamespace(
        update_id=5202,
        callback_query=SimpleNamespace(data="", from_user=SimpleNamespace(id="operator")),
    )

    asyncio.run(adapter._handle_callback_query(unauthorized, SimpleNamespace()))
    asyncio.run(adapter._handle_callback_query(empty, SimpleNamespace()))

    assert "callback-auth:stranger" in timeline
    assert "callback-auth:operator" not in timeline
    assert "claim:5201" not in timeline
    assert "claim:5202" not in timeline
    assert not any(item.startswith("callback-work:") for item in timeline)
    assert adapter.original_callback_calls == 0


def test_hermes_two_photo_album_ids_claim_before_cache_and_replays_do_no_work(monkeypatch) -> None:
    timeline: list[str] = []
    _policy, runner, adapter, dispatched = _install_raw_hermes_fixture(monkeypatch, timeline)
    first = SimpleNamespace(update_id=4101, message=_RawHermesMessage(photo=True, album="album-1"))
    second = SimpleNamespace(update_id=4102, message=_RawHermesMessage(photo=True, album="album-1"))

    asyncio.run(adapter._handle_media_message(first, SimpleNamespace()))
    asyncio.run(adapter._handle_media_message(second, SimpleNamespace()))
    asyncio.run(adapter._handle_media_message(first, SimpleNamespace()))
    asyncio.run(adapter._handle_media_message(second, SimpleNamespace()))
    untrusted = SimpleNamespace(
        update_id=4199,
        message=_RawHermesMessage(photo=True, album="album-1", user_id="stranger"),
    )
    asyncio.run(adapter._handle_media_message(untrusted, SimpleNamespace()))

    assert timeline.index("claim:4101") < timeline.index("cache:4101")
    assert timeline.index("claim:4102") < timeline.index("cache:4102")
    assert timeline.count("cache:4101") == 1
    assert timeline.count("cache:4102") == 1
    assert "claim:4199" not in timeline
    assert "cache:4199" not in timeline
    assert adapter.original_media_calls == 2
    assert adapter.pending_album.media_urls == ["cache/4101.jpg", "cache/4102.jpg"]
    assert adapter.pending_album._openclaw_raw_update_preclaimed is True
    asyncio.run(runner._handle_message(adapter.pending_album))
    assert dispatched == [adapter.pending_album]


def test_hermes_runtime_discovery_installs_raw_telegram_adapter_patch(monkeypatch) -> None:
    import openclaw_hermes_gateway_policy as policy

    class GatewayRunner:
        async def _handle_message(self, _event):
            return "ok"

    class DiscoveredTelegramAdapter:
        pass

    class BaseAdapter:
        async def _send_with_retry(self, *args, **kwargs):
            return None

    gateway_package = types.ModuleType("gateway")
    platforms_package = types.ModuleType("gateway.platforms")
    telegram_module = types.ModuleType("gateway.platforms.telegram")
    telegram_module.TelegramAdapter = DiscoveredTelegramAdapter
    base_module = types.ModuleType("gateway.platforms.base")
    base_module.MessageType = _HermesMessageTypes
    monkeypatch.setitem(sys.modules, "gateway", gateway_package)
    monkeypatch.setitem(sys.modules, "gateway.platforms", platforms_package)
    monkeypatch.setitem(sys.modules, "gateway.platforms.telegram", telegram_module)
    monkeypatch.setitem(sys.modules, "gateway.platforms.base", base_module)

    installed: list[tuple[object, object]] = []
    monkeypatch.setattr(
        policy,
        "_install_hermes_raw_update_claim_patch",
        lambda adapter, message_types: installed.append((adapter, message_types)),
    )

    policy.install_gateway_policy_patch(
        gateway_run_module=SimpleNamespace(GatewayRunner=GatewayRunner),
        base_adapter_cls=BaseAdapter,
    )

    assert installed == [(DiscoveredTelegramAdapter, _HermesMessageTypes)]

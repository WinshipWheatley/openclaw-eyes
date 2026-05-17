import importlib


def _fail(name):
    def _inner(*args, **kwargs):
        raise AssertionError(f"{name} should not be called while no-send reload guard is active")

    return _inner


def test_no_send_reload_guard_env_truthy(monkeypatch):
    import cassandra_no_send_reload_guard as guard

    monkeypatch.delenv(guard.ENV_VAR, raising=False)
    monkeypatch.delenv(guard.ALT_ENV_VAR, raising=False)
    assert guard.is_no_send_reload_guard_enabled() is False

    monkeypatch.setenv(guard.ENV_VAR, "1")
    assert guard.is_no_send_reload_guard_enabled() is True

    monkeypatch.setenv(guard.ENV_VAR, "false")
    monkeypatch.setenv(guard.ALT_ENV_VAR, "yes")
    assert guard.is_no_send_reload_guard_enabled() is True


def test_watcher_first_tick_quiesces_all_send_capable_paths(monkeypatch):
    monkeypatch.setenv("CASSANDRA_NO_SEND_RELOAD_GUARD", "1")
    import cassandra_watcher as watcher

    importlib.reload(watcher)
    monkeypatch.setattr(watcher, "_restart_if_sources_changed", _fail("source reload"), raising=False)
    monkeypatch.setattr(watcher, "process_pending_followups", _fail("pending followups"), raising=False)
    monkeypatch.setattr(watcher, "process_inbound_email_replies", _fail("inbound email polling"), raising=False)
    monkeypatch.setattr(watcher, "_dispatch_future_actions", _fail("future action dispatch"), raising=False)
    monkeypatch.setattr(watcher, "_evaluate", _fail("ambient evaluator"), raising=False)
    monkeypatch.setattr(watcher, "_send", _fail("telegram send"), raising=False)
    monkeypatch.setattr(watcher, "_telegram_send", _fail("future telegram send"), raising=False)

    assert watcher._tick_once(123.0) == 123.0


def test_briefing_scheduler_first_tick_quiesces_all_delivery_paths(monkeypatch):
    monkeypatch.setenv("CASSANDRA_NO_SEND_RELOAD_GUARD", "1")
    import cassandra_briefing_scheduler as scheduler

    importlib.reload(scheduler)
    monkeypatch.setattr(scheduler, "_restart_if_sources_changed", _fail("source reload"), raising=False)
    monkeypatch.setattr(scheduler, "due_slots", _fail("due slot lookup"), raising=False)
    monkeypatch.setattr(scheduler, "generate_briefing", _fail("briefing generation"), raising=False)
    monkeypatch.setattr(scheduler, "save_briefing", _fail("briefing save"), raising=False)
    monkeypatch.setattr(scheduler, "pending_briefings", _fail("pending briefing lookup"), raising=False)
    monkeypatch.setattr(scheduler, "_deliver", _fail("briefing delivery"), raising=False)
    monkeypatch.setattr(scheduler, "send_message", _fail("telegram send"), raising=False)
    monkeypatch.setattr(scheduler, "speak_and_send_voice_note", _fail("voice send"), raising=False)

    scheduler._tick()


def test_guard_does_not_grant_send_authority():
    import cassandra_no_send_reload_guard as guard

    assert guard.ENV_VAR == "CASSANDRA_NO_SEND_RELOAD_GUARD"
    assert "SEND" in guard.ENV_VAR
    assert not hasattr(guard, "send_message")

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import asyncio
import importlib
import sys


def import_chief_listener(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_USER_ID", "12345")
    sys.modules.pop("chief_listener", None)
    return importlib.import_module("chief_listener")


def test_import_does_not_start_polling(monkeypatch):
    chief_listener = import_chief_listener(monkeypatch)

    assert hasattr(chief_listener, "build_application")
    assert hasattr(chief_listener, "run_listener")
    assert "app" not in vars(chief_listener)


def test_run_listener_awaits_lifecycle_once_in_order(monkeypatch):
    chief_listener = import_chief_listener(monkeypatch)
    calls = []

    class FakeUpdater:
        def __init__(self):
            self.running = False

        async def start_polling(self):
            calls.append("start_polling")
            self.running = True

        async def stop(self):
            calls.append("updater.stop")
            self.running = False

    class FakeApplication:
        def __init__(self, stop_event):
            self.updater = FakeUpdater()
            self.post_init = self._post_init
            self.running = False
            self._stop_event = stop_event

        async def initialize(self):
            calls.append("initialize")

        async def _post_init(self, application):
            assert application is self
            calls.append("post_init")

        async def start(self):
            calls.append("start")
            self.running = True
            self._stop_event.set()

        async def stop(self):
            calls.append("stop")
            self.running = False

        async def shutdown(self):
            calls.append("shutdown")

    async def scenario():
        stop_event = asyncio.Event()
        await chief_listener.run_listener(FakeApplication(stop_event), stop_event)

    asyncio.run(scenario())

    assert calls == [
        "initialize",
        "post_init",
        "start_polling",
        "start",
        "updater.stop",
        "stop",
        "shutdown",
    ]
    assert calls.count("updater.stop") == 1

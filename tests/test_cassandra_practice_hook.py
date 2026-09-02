"""Practice messages are answered by the practice store before any model runs.

The hook sits in Cassandra's deterministic cascade next to the other no-model
answers. It fails open: when the message is not about practice, or the practice
store is unavailable, the rest of the brain proceeds exactly as before.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _isolate_handle(monkeypatch, tmp_path: Path):
    import cassandra_brain

    logged: list[dict] = []
    monkeypatch.setattr(cassandra_brain, "process_pending_followups", lambda: [])
    monkeypatch.setattr(cassandra_brain, "load_state", lambda: dict(cassandra_brain._DEFAULT_STATE))
    monkeypatch.setattr(cassandra_brain, "save_state", lambda _state: None)
    monkeypatch.setattr(
        cassandra_brain,
        "_log_conversation",
        lambda text, replies, route="llm", metadata=None, **kwargs: logged.append(
            {"text": text, "replies": replies, "route": route, "metadata": metadata or {}}
        ),
    )
    monkeypatch.setenv("OPENCLAW_CONTRACT_RECEIPT_DB", str(tmp_path / "receipts.sqlite3"))
    monkeypatch.setenv(cassandra_brain.PRACTICE_DB_ENV_VAR, str(tmp_path / "practice.sqlite3"))
    return cassandra_brain, logged


def test_helper_returns_none_for_non_practice_text(monkeypatch, tmp_path: Path) -> None:
    cassandra_brain, _logged = _isolate_handle(monkeypatch, tmp_path)
    assert cassandra_brain._handle_practice_text_safely("did the Capital Hilton check arrive?") is None
    assert cassandra_brain._handle_practice_text_safely("the practice of invoicing is tedious") is None


def test_helper_fails_open_when_store_is_unavailable(monkeypatch, tmp_path: Path) -> None:
    import sys
    import types

    cassandra_brain, _logged = _isolate_handle(monkeypatch, tmp_path)
    broken = types.ModuleType("practice_loop")
    broken.DEFAULT_DB_PATH = tmp_path / "practice.sqlite3"

    class _BrokenStore:
        def __init__(self, _path: str) -> None:
            raise RuntimeError("store down")

    broken.PracticeStore = _BrokenStore
    broken.handle_practice_text = lambda *_a, **_k: "never reached"
    monkeypatch.setitem(sys.modules, "practice_loop", broken)
    assert cassandra_brain._handle_practice_text_safely("what should I practice") is None


def test_helper_answers_practice_messages_from_the_store(monkeypatch, tmp_path: Path) -> None:
    pytest.importorskip("practice_loop")
    cassandra_brain, _logged = _isolate_handle(monkeypatch, tmp_path)
    added = cassandra_brain._handle_practice_text_safely("add song Blue Weather to album")
    assert added is not None and "Blue Weather" in added
    plan = cassandra_brain._handle_practice_text_safely("what should I practice")
    assert plan is not None and "Blue Weather" in plan


def test_handle_routes_practice_text_without_a_model(monkeypatch, tmp_path: Path) -> None:
    cassandra_brain, logged = _isolate_handle(monkeypatch, tmp_path)
    monkeypatch.setattr(cassandra_brain, "_handle_practice_text_safely", lambda query: "Practice canary: " + query)
    monkeypatch.setattr(
        cassandra_brain,
        "_call",
        lambda *_args, **_kwargs: pytest.fail("model ran for a practice message"),
    )

    replies = cassandra_brain.handle("practiced Blue Weather 30 min")

    assert replies == ["Practice canary: practiced Blue Weather 30 min"]
    assert logged and logged[-1]["route"] == "practice_loop"
    assert logged[-1]["metadata"]["model_called"] is False
    assert logged[-1]["metadata"]["email_send_performed"] is False

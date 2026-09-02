from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import practice_loop as pl

NOW = datetime(2026, 9, 2, 13, 0, tzinfo=timezone.utc)


def _store(tmp_path: Path) -> pl.PracticeStore:
    return pl.PracticeStore(tmp_path / "practice.sqlite3")


def test_add_song_is_idempotent_and_merges_tags(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.add_song("Blue Weather", tags=("album",), now=NOW)
    store.add_song("blue weather!", tags=("hilton_set",), configurations=("acoustic",), now=NOW)
    songs = store.list_songs()
    assert [s.title for s in songs] == ["Blue Weather"]
    assert songs[0].tags == ("album", "hilton_set")
    assert songs[0].configurations == ("acoustic",)


def test_plan_orders_never_practiced_then_low_confidence_then_stale(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.add_song("Fresh", now=NOW)
    store.add_song("Shaky", now=NOW)
    store.add_song("Solid Old", now=NOW)
    store.add_song("Solid New", now=NOW)
    store.log_session("Shaky", 25, practiced_at=NOW - timedelta(days=1))  # confidence 1
    for day in range(5):
        store.log_session("Solid Old", 25, practiced_at=NOW - timedelta(days=40 - day))  # confidence 5
    for day in range(5):
        store.log_session("Solid New", 25, practiced_at=NOW - timedelta(days=5 - day))  # confidence 5

    plan = store.plan(minutes_budget=45, now=NOW)

    assert [slot["title"] for slot in plan] == ["Fresh", "Shaky", "Solid Old"]
    assert plan[0]["reason"] == "never practiced"
    assert plan[1]["reason"] == "confidence 1 of 5"
    assert plan[2]["reason"] == "36 days since last time"
    assert sum(slot["minutes"] for slot in plan) <= 45
    assert all(pl.MIN_SLOT_MINUTES <= slot["minutes"] <= pl.MAX_SLOT_MINUTES for slot in plan)


def test_confidence_bumps_once_per_real_session_and_caps(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.add_song("Ten Fingers", now=NOW)
    store.log_session("Ten Fingers", 10, practiced_at=NOW)  # too short to bump
    assert store.song_status("Ten Fingers").confidence == 0
    for i in range(7):
        store.log_session("Ten Fingers", 30, practiced_at=NOW + timedelta(hours=i))
    status = store.song_status("Ten Fingers")
    assert status.confidence == pl.CONFIDENCE_MAX
    assert status.sessions_count == 8
    assert status.total_minutes == 220


def test_streak_and_weekly_minutes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.add_song("The Future", now=NOW)
    for days_ago in (0, 1, 2, 4):
        store.log_session("The Future", 20, practiced_at=NOW - timedelta(days=days_ago))
    summary = store.status_summary(now=NOW)
    assert summary["streak_days"] == 3
    assert summary["minutes_this_week"] == 80
    assert summary["song_count"] == 1


@pytest.mark.parametrize(
    "text",
    [
        "did the Capital Hilton check arrive?",
        "the practice of invoicing is tedious",
        "St. Anne's practice was cancelled",
        "practice makes perfect, right?",
        "add a calendar entry for practice tomorrow",
        "",
    ],
)
def test_handler_ignores_non_practice_messages(tmp_path: Path, text: str) -> None:
    store = _store(tmp_path)
    assert pl.handle_practice_text(text, store=store, now=NOW) is None


def test_handler_add_log_plan_status_round_trip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert pl.handle_practice_text("What should I practice?", store=store, now=NOW).startswith("No repertoire yet")

    added = pl.handle_practice_text("add song Blue Weather to album", store=store, now=NOW)
    assert added == "Added Blue Weather to album. 1 songs in the repertoire."

    logged = pl.handle_practice_text("practiced blue weather for 30 min in acoustic: chorus still shaky", store=store, now=NOW)
    assert logged == "Logged 30 minutes on Blue Weather. Confidence 1 of 5."
    session = store.sessions_since(NOW - timedelta(hours=1))[0]
    assert session["configuration"] == "acoustic"
    assert session["notes"] == "chorus still shaky"

    pl.handle_practice_text("add song The Future", store=store, now=NOW)
    plan = pl.handle_practice_text("practice plan 30 min", store=store, now=NOW)
    assert plan.splitlines()[0] == "Practice today, 30 minutes:"
    assert "The Future, 15 min (never practiced)" in plan
    assert "Blue Weather, 15 min (confidence 1 of 5)" in plan

    status = pl.handle_practice_text("practice status", store=store, now=NOW)
    assert status.startswith("2 songs, average confidence 0.5 of 5. 30 minutes this week, streak 1 days.")
    assert "Not touched in 14 days: The Future." in status

    assert pl.handle_practice_text("songs for album", store=store, now=NOW) == "album: Blue Weather."


def test_handler_asks_instead_of_guessing_between_songs(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.add_song("Can You Feel It", now=NOW)
    store.add_song("Count On Your Faith", now=NOW)
    reply = pl.handle_practice_text("practiced c 20 min", store=store, now=NOW)
    assert reply == "Which one: Can You Feel It, Count On Your Faith?"
    missing = pl.handle_practice_text("practiced Kamakazi 20 min", store=store, now=NOW)
    assert missing.startswith("I do not have \"Kamakazi\" yet.")


def test_seed_album_and_targets(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert pl.seed_album_repertoire(store, now=NOW) == 12
    assert pl.seed_album_repertoire(store, now=NOW) == 0
    assert pl.seed_targets(store, pl.DEFAULT_TARGETS_PATH) == 2
    names = [t["name"] for t in store.list_targets()]
    assert names == ["album", "hilton_build"]


def test_read_model_exports_and_is_deterministic(tmp_path: Path) -> None:
    db = tmp_path / "practice.sqlite3"
    store = pl.PracticeStore(db)
    pl.seed_album_repertoire(store, now=NOW)
    store.log_session("Blue Weather", 30, practiced_at=NOW - timedelta(days=1))
    store.close()

    first = pl.export_practice_plan(db_path=db, export_root=tmp_path / "rm", now=NOW)
    a = (tmp_path / "rm" / "practice_plan.json").read_bytes()
    pl.export_practice_plan(db_path=db, export_root=tmp_path / "rm", now=NOW)
    assert (tmp_path / "rm" / "practice_plan.json").read_bytes() == a
    payload = json.loads(a)
    assert payload["read_model_id"] == "practice_plan"
    assert payload["plan"][0]["reason"] == "never practiced"
    assert payload["authority_boundary"]["external_model_called"] is False
    assert first["song_count"] == 12
    operator = (tmp_path / "rm" / "practice_plan_OPERATOR.md").read_text(encoding="utf-8")
    assert operator.startswith("# Practice Plan")
    assert "Boundary:" in operator

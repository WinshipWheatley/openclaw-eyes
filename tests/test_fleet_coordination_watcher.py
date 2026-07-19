from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from codex_app_server_control import MidturnDeliveryOutcome
from fleet_coordination_contracts import write_wake_ping


def _note(path: Path, text: str, *, mtime_ns: int) -> Path:
    path.write_text(text, encoding="utf-8")
    os.utime(path, ns=(mtime_ns, mtime_ns))
    return path


def _paths(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    inbound = tmp_path / "inbound"
    wake_dir = tmp_path / "WAKE"
    inbound.mkdir()
    wake_dir.mkdir()
    return inbound, wake_dir, tmp_path / "cursor.json", tmp_path / "watcher.json"


def test_ten_new_files_coalesce_into_one_normal_doorbell(tmp_path: Path) -> None:
    from fleet_coordination_watcher import dispatch_once, prime_dispatcher

    inbound, wake_dir, cursor, watcher = _paths(tmp_path)
    prime_dispatcher(
        seat="PC-Sol",
        inbound_dirs=(inbound,),
        wake_dir=wake_dir,
        state_path=cursor,
        watcher_state_path=watcher,
    )
    notes = tuple(
        _note(inbound / f"FABLE-BURST-{index}.md", str(index), mtime_ns=1_000_000 + index)
        for index in range(10)
    )
    doorbells: list[tuple[Path, ...]] = []

    result = dispatch_once(
        seat="PC-Sol",
        inbound_dirs=(inbound,),
        wake_dir=wake_dir,
        state_path=cursor,
        watcher_state_path=watcher,
        doorbell=lambda paths: doorbells.append(paths) or "woke",
        midturn=lambda message, event_id: (_ for _ in ()).throw(AssertionError("not urgent")),
        now_epoch=1_000.0,
    )

    assert result.status == "delivered"
    assert result.priority == "normal"
    assert result.coalesced_count == 9
    assert len(doorbells) == 1
    assert set(doorbells[0]) == set(notes)
    second = dispatch_once(
        seat="PC-Sol",
        inbound_dirs=(inbound,),
        wake_dir=wake_dir,
        state_path=cursor,
        watcher_state_path=watcher,
        doorbell=lambda paths: (_ for _ in ()).throw(AssertionError("replayed")),
        midturn=lambda message, event_id: (_ for _ in ()).throw(AssertionError("replayed")),
        now_epoch=1_001.0,
    )
    assert second.status == "no_change"
    state = json.loads(watcher.read_text(encoding="utf-8"))
    assert state["delivery_counts"]["doorbell"] == 1
    assert state["delivery_counts"]["coalesced"] == 9


def test_verified_urgent_ping_is_injected_with_reason_and_sha(tmp_path: Path) -> None:
    from fleet_coordination_watcher import dispatch_once, prime_dispatcher

    inbound, wake_dir, cursor, watcher = _paths(tmp_path)
    prime_dispatcher(
        seat="PC-Sol",
        inbound_dirs=(inbound,),
        wake_dir=wake_dir,
        state_path=cursor,
        watcher_state_path=watcher,
    )
    reference = _note(tmp_path / "operator-directive.md", "STOP MARKER", mtime_ns=2_000_000)
    wake = write_wake_ping(
        wake_dir=wake_dir,
        from_seat="Opus",
        to_seat="PC-Sol",
        mission_id="SAFETY-STOP-1",
        reference_path=reference,
        priority="urgent",
        urgent_reason="safety_stop",
        now=datetime(2026, 7, 19, 2, 45, tzinfo=timezone.utc),
    )
    injected: list[tuple[str, str]] = []

    result = dispatch_once(
        seat="PC-Sol",
        inbound_dirs=(inbound,),
        wake_dir=wake_dir,
        state_path=cursor,
        watcher_state_path=watcher,
        doorbell=lambda paths: (_ for _ in ()).throw(AssertionError("active urgent must not resume")),
        midturn=lambda message, event_id: injected.append((message, event_id))
        or MidturnDeliveryOutcome("delivered", "thread", "turn"),
        now_epoch=2_000.0,
    )

    assert result.status == "delivered"
    assert result.priority == "urgent"
    assert len(injected) == 1
    assert str(wake) in injected[0][0]
    assert str(reference) in injected[0][0]
    assert "SAFETY-STOP-1" in injected[0][0]
    assert "safety_stop" in injected[0][0]
    assert json.loads(wake.read_text(encoding="utf-8"))["sha"] in injected[0][0]
    state = json.loads(watcher.read_text(encoding="utf-8"))
    assert state["delivery_counts"]["midturn"] == 1
    assert state["delivery_counts"]["urgent"] == 1


def test_urgent_idle_uses_doorbell_but_failed_steer_does_not(tmp_path: Path) -> None:
    from fleet_coordination_watcher import dispatch_once, prime_dispatcher

    inbound, wake_dir, cursor, watcher = _paths(tmp_path)
    prime_dispatcher(
        seat="PC-Sol",
        inbound_dirs=(inbound,),
        wake_dir=wake_dir,
        state_path=cursor,
        watcher_state_path=watcher,
    )
    first_ref = _note(tmp_path / "first.md", "first", mtime_ns=3_000_000)
    write_wake_ping(
        wake_dir=wake_dir,
        from_seat="Opus",
        to_seat="PC-Sol",
        mission_id="CONFER-1",
        reference_path=first_ref,
        priority="urgent",
        urgent_reason="blocking_confer",
        now=datetime(2026, 7, 19, 2, 46, tzinfo=timezone.utc),
    )
    doorbells: list[tuple[Path, ...]] = []
    idle = dispatch_once(
        seat="PC-Sol",
        inbound_dirs=(inbound,),
        wake_dir=wake_dir,
        state_path=cursor,
        watcher_state_path=watcher,
        doorbell=lambda paths: doorbells.append(paths) or "woke",
        midturn=lambda message, event_id: MidturnDeliveryOutcome("idle", "thread"),
        now_epoch=3_000.0,
    )
    assert idle.status == "delivered"
    assert doorbells == [(first_ref,)]

    second_ref = _note(tmp_path / "second.md", "second", mtime_ns=3_100_000)
    write_wake_ping(
        wake_dir=wake_dir,
        from_seat="Opus",
        to_seat="PC-Sol",
        mission_id="CONFER-2",
        reference_path=second_ref,
        priority="urgent",
        urgent_reason="blocking_confer",
        now=datetime(2026, 7, 19, 2, 47, tzinfo=timezone.utc),
    )
    failed = dispatch_once(
        seat="PC-Sol",
        inbound_dirs=(inbound,),
        wake_dir=wake_dir,
        state_path=cursor,
        watcher_state_path=watcher,
        doorbell=lambda paths: (_ for _ in ()).throw(AssertionError("failed steer must not resume")),
        midturn=lambda message, event_id: MidturnDeliveryOutcome(
            "steer_failed", "thread", "turn", "not steerable"
        ),
        now_epoch=3_100.0,
    )
    assert failed.status == "midturn_undelivered"
    repeat = dispatch_once(
        seat="PC-Sol",
        inbound_dirs=(inbound,),
        wake_dir=wake_dir,
        state_path=cursor,
        watcher_state_path=watcher,
        doorbell=lambda paths: (_ for _ in ()).throw(AssertionError("failed event replayed")),
        midturn=lambda message, event_id: (_ for _ in ()).throw(AssertionError("failed event replayed")),
        now_epoch=3_101.0,
    )
    assert repeat.status == "no_change"
    assert json.loads(watcher.read_text(encoding="utf-8"))["delivery_counts"]["failures"] == 1


def test_doorbell_rate_cap_waits_in_plumbing_not_in_model(tmp_path: Path) -> None:
    from fleet_coordination_watcher import dispatch_once, prime_dispatcher

    inbound, wake_dir, cursor, watcher = _paths(tmp_path)
    prime_dispatcher(
        seat="PC-Sol",
        inbound_dirs=(inbound,),
        wake_dir=wake_dir,
        state_path=cursor,
        watcher_state_path=watcher,
    )
    waits: list[float] = []
    for index, now in enumerate((4_000.0, 4_001.0, 4_002.0)):
        _note(inbound / f"FABLE-{index}.md", str(index), mtime_ns=4_000_000 + index)
        result = dispatch_once(
            seat="PC-Sol",
            inbound_dirs=(inbound,),
            wake_dir=wake_dir,
            state_path=cursor,
            watcher_state_path=watcher,
            doorbell=lambda paths: "woke",
            midturn=lambda message, event_id: MidturnDeliveryOutcome("idle", "thread"),
            now_epoch=now,
            max_doorbells_per_minute=2,
            rate_limit_waiter=waits.append,
        )
        assert result.status == "delivered"

    assert waits == [58.0]


def test_noise_symlinks_and_wakes_for_other_seats_are_ignored(tmp_path: Path) -> None:
    from fleet_coordination_watcher import dispatch_once, prime_dispatcher

    inbound, wake_dir, cursor, watcher = _paths(tmp_path)
    prime_dispatcher(
        seat="PC-Sol",
        inbound_dirs=(inbound,),
        wake_dir=wake_dir,
        state_path=cursor,
        watcher_state_path=watcher,
    )
    outside = _note(tmp_path / "outside.md", "outside", mtime_ns=5_000_000)
    (inbound / "linked.md").symlink_to(outside)
    for name in (".hidden.md", "CHECKIN-seat.md", "RECEIPT-old.md", "ACK-old.md", "note.tmp"):
        _note(inbound / name, "noise", mtime_ns=5_000_001)
    other = {
        "from": "Opus",
        "to": "Gemini",
        "file": str(outside),
        "sha": "0" * 64,
        "needs_human_kick": False,
        "priority": "normal",
    }
    (wake_dir / "WAKE-Gemini-20260719T025000Z.json").write_text(json.dumps(other), encoding="utf-8")

    result = dispatch_once(
        seat="PC-Sol",
        inbound_dirs=(inbound,),
        wake_dir=wake_dir,
        state_path=cursor,
        watcher_state_path=watcher,
        doorbell=lambda paths: (_ for _ in ()).throw(AssertionError("noise woke")),
        midturn=lambda message, event_id: (_ for _ in ()).throw(AssertionError("noise steered")),
        now_epoch=5_000.0,
    )

    assert result.status == "no_change"

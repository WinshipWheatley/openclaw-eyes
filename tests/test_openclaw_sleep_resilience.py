import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_sleep_resilience as sleep_resilience


FIXED_NOW = datetime(2026, 6, 18, 16, 0, 0, tzinfo=timezone.utc)


def test_detect_resume_gap_uses_wall_clock_delta():
    previous = FIXED_NOW - timedelta(minutes=45)

    detected, delta = sleep_resilience.detect_resume_gap(
        previous_wall_utc=previous,
        now_utc=FIXED_NOW,
        interval_seconds=60,
        resume_gap_seconds=600,
    )

    assert detected is True
    assert delta == 2700


def test_recent_fleet_activity_ignores_old_and_self_files(tmp_path):
    to_claude = tmp_path / "inbox/to-claude"
    to_claude.mkdir(parents=True)
    recent = to_claude / "LANE-E-POLL-20260618T120000-0400.md"
    old = to_claude / "LANE-C-POLL-old.md"
    self_note = to_claude / "OPENCLAW-SLEEP-RESILIENCE-20260618T120000-0400.md"
    recent.write_text("recent", encoding="utf-8")
    old.write_text("old", encoding="utf-8")
    self_note.write_text("self", encoding="utf-8")
    recent_time = FIXED_NOW.timestamp() - 30
    old_time = FIXED_NOW.timestamp() - 5000
    os.utime(recent, (recent_time, recent_time))
    os.utime(old, (old_time, old_time))
    os.utime(self_note, (recent_time, recent_time))

    activity = sleep_resilience.recent_fleet_activity(
        tmp_path,
        now_utc=FIXED_NOW,
        active_window_seconds=900,
    )

    assert [row["name"] for row in activity] == [recent.name]


def test_run_once_writes_resume_receipt_and_invokes_bounded_keeper(tmp_path):
    orch = tmp_path / "orch"
    to_claude = orch / "inbox/to-claude"
    to_claude.mkdir(parents=True)
    note = to_claude / "LANE-E-AUTO-POLL-20260618T155900-0400.md"
    note.write_text("alive", encoding="utf-8")
    mtime = FIXED_NOW.timestamp() - 60
    os.utime(note, (mtime, mtime))

    read_root = tmp_path / "read_models"
    read_root.mkdir()
    (read_root / sleep_resilience.STATE_EXPORT_NAME).write_text(
        json.dumps({"last_wall_utc": (FIXED_NOW - timedelta(hours=1)).isoformat()}),
        encoding="utf-8",
    )
    calls = []

    def fake_runner(args):
        calls.append(args)
        if args and args[0] == "powershell.exe":
            return sleep_resilience.CommandResult(0, "", "")
        return sleep_resilience.CommandResult(
            0,
            json.dumps({"run_status": "NO_ACTION_REQUIRED", "action_count": 0}),
            "",
        )

    payload = sleep_resilience.run_once(
        orch_root=orch,
        read_model_root=read_root,
        interval_seconds=60,
        active_window_seconds=900,
        resume_gap_seconds=600,
        apply_host_awake=True,
        run_service_keeper_on_resume=True,
        now_utc=FIXED_NOW,
        runner=fake_runner,
    )

    assert payload["active_work_visible"] is True
    assert payload["resume_gap_detected"] is True
    assert payload["host_awake"]["status"] == "APPLIED"
    assert payload["resume_recovery"]["status"] == "RAN"
    assert any(call and call[0] == "powershell.exe" for call in calls)
    assert any("openclaw_service_keeper.py" in " ".join(call) for call in calls)
    assert (read_root / sleep_resilience.JSON_EXPORT_NAME).exists()
    assert (read_root / sleep_resilience.OPERATOR_EXPORT_NAME).exists()


def test_windows_awake_command_clears_or_sets_system_required():
    set_cmd = " ".join(sleep_resilience.windows_awake_command(active=True))
    clear_cmd = " ".join(sleep_resilience.windows_awake_command(active=False))

    assert "SetThreadExecutionState(0x80000001)" in set_cmd
    assert "SetThreadExecutionState(0x80000000)" in clear_cmd

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
POLISH_LOOP_DIR = ROOT / "polish_loop"

if str(POLISH_LOOP_DIR) not in sys.path:
    sys.path.insert(0, str(POLISH_LOOP_DIR))

import orchestrator  # noqa: E402


@pytest.fixture
def isolated_orchestrator(tmp_path, monkeypatch):
    loop_dir = tmp_path / "polish_loop"
    current_dir = loop_dir / "current"
    tasks_dir = loop_dir / "tasks"
    archive_dir = loop_dir / "archive"
    current_dir.mkdir(parents=True)
    tasks_dir.mkdir()
    archive_dir.mkdir()

    status_file = loop_dir / "status.json"
    task_file = loop_dir / "task.md"
    pc_output = current_dir / "pc_output.md"
    mac_review = current_dir / "mac_review.md"
    closeout = current_dir / "closeout.ok"
    log_file = tmp_path / "orchestrator.log"

    monkeypatch.setattr(orchestrator, "LOOP_DIR", loop_dir, raising=False)
    monkeypatch.setattr(orchestrator, "CURRENT_DIR", current_dir, raising=False)
    monkeypatch.setattr(orchestrator, "STATUS_FILE", status_file, raising=False)
    monkeypatch.setattr(orchestrator, "TASK_MD", task_file, raising=False)
    monkeypatch.setattr(orchestrator, "PC_OUTPUT", pc_output, raising=False)
    monkeypatch.setattr(orchestrator, "MAC_REVIEW", mac_review, raising=False)
    monkeypatch.setattr(orchestrator, "CLOSEOUT", closeout, raising=False)
    monkeypatch.setattr(orchestrator, "LOG_FILE", log_file, raising=False)
    monkeypatch.setattr(orchestrator, "_TEST_SUPPRESS_FILE_LOGS", False, raising=False)

    launches: list[list[str]] = []

    class _FakePopen:
        def __init__(self, args):
            launches.append(args)

    monkeypatch.setattr(orchestrator.subprocess, "Popen", _FakePopen)

    status_file.write_text(
        json.dumps(
            {
                "status": "idle",
                "task_name": "previous-task",
                "pass": 1,
                "approved": False,
                "block_reason": None,
                "parked_from": None,
                "parked_reason": None,
                "relaunch_attempted": False,
                "blocked_notified": False,
            }
        )
    )

    return {
        "loop_dir": loop_dir,
        "tasks_dir": tasks_dir,
        "task_file": task_file,
        "status_file": status_file,
        "log_file": log_file,
        "launches": launches,
    }


def test_queued_task_frontmatter_error_requires_title_and_goal(tmp_path):
    task_file = tmp_path / "bad-task.md"
    task_file.write_text("title: only title\nscope:\n- missing goal\n")

    assert (
        orchestrator.queued_task_frontmatter_error(task_file)
        == "missing required frontmatter field(s): goal"
    )


def test_handle_idle_skips_invalid_queued_task_and_promotes_next_valid_one(isolated_orchestrator):
    invalid_task = isolated_orchestrator["tasks_dir"] / "a-invalid.md"
    valid_task = isolated_orchestrator["tasks_dir"] / "b-valid.md"
    invalid_task.write_text("title: Missing goal\nscope:\n- nope\n")
    valid_content = "title: Valid task\ngoal: Ship it\nscope:\n- yep\n"
    valid_task.write_text(valid_content)

    orchestrator.handle_idle({"status": "idle", "task_name": "previous-task"})

    assert "b-valid" == json.loads(isolated_orchestrator["status_file"].read_text())["task_name"]
    assert isolated_orchestrator["task_file"].read_text() == valid_content
    assert invalid_task.exists()
    assert not valid_task.exists()
    # Orchestrator delegates launch to builder_watcher — no direct subprocess.Popen
    assert isolated_orchestrator["launches"] == []
    log_text = isolated_orchestrator["log_file"].read_text()
    assert "skipping queued task a-invalid.md: missing required frontmatter field(s): goal" in log_text
    assert "promoting queued task b-valid.md → task.md" in log_text


def test_handle_idle_skips_all_invalid_queued_tasks_without_promoting(isolated_orchestrator):
    invalid_task = isolated_orchestrator["tasks_dir"] / "a-invalid.md"
    invalid_task.write_text("goal: Missing title\nscope:\n- nope\n")

    orchestrator.handle_idle({"status": "idle", "task_name": "previous-task"})

    status = json.loads(isolated_orchestrator["status_file"].read_text())
    assert status["status"] == "idle"
    assert status["task_name"] == "previous-task"
    assert invalid_task.exists()
    assert not isolated_orchestrator["task_file"].exists()
    assert isolated_orchestrator["launches"] == []
    log_text = isolated_orchestrator["log_file"].read_text()
    assert "skipping queued task a-invalid.md: missing required frontmatter field(s): title" in log_text
    assert "queued tasks invalid or skipped — waiting" in log_text


def test_handle_idle_skips_human_supervised_queued_task_and_promotes_next_valid_one(isolated_orchestrator):
    human_task = isolated_orchestrator["tasks_dir"] / "a-human.md"
    valid_task = isolated_orchestrator["tasks_dir"] / "b-valid.md"
    human_task.write_text(
        "title: Human Task\n"
        "goal: Needs real-world verification\n"
        "**Assigned to:** Human-supervised\n"
        "**Execution mode:** Human-supervised capture and record\n"
    )
    valid_content = "title: Valid task\ngoal: Ship it\nscope:\n- yep\n"
    valid_task.write_text(valid_content)

    orchestrator.handle_idle({"status": "idle", "task_name": "previous-task"})

    assert "b-valid" == json.loads(isolated_orchestrator["status_file"].read_text())["task_name"]
    assert isolated_orchestrator["task_file"].read_text() == valid_content
    assert human_task.exists()
    assert not valid_task.exists()
    # Orchestrator delegates launch to builder_watcher — no direct subprocess.Popen
    assert isolated_orchestrator["launches"] == []
    log_text = isolated_orchestrator["log_file"].read_text()
    assert "skipping queued task a-human.md: human-supervised execution mode" in log_text
    assert "promoting queued task b-valid.md → task.md" in log_text


def test_pc_output_valid_requires_cost_truth_and_headroom_sections(isolated_orchestrator):
    isolated_orchestrator["task_file"].write_text("title: Valid\ngoal: Ship it\n")
    isolated_orchestrator["status_file"].write_text(
        json.dumps({"status": "pc_turn", "task_name": "x", "pass": 16, "approved": False})
    )
    isolated_orchestrator["loop_dir"].joinpath("current", "pc_output.md").write_text(
        "\n".join(
            [
                "PASS: 16",
                "STATUS: DONE",
                "",
                "CHANGES:",
                "- file",
                "",
                "REASONING:",
                "- why",
                "",
                "ROLLBACK PLAN:",
                "- revert",
            ]
        )
    )

    valid, reason = orchestrator.pc_output_valid(16)
    assert valid is False
    assert reason == "quality_gate"


def test_handle_pc_turn_builder_timeout_archives_using_task_md_title(
    isolated_orchestrator, monkeypatch
):
    isolated_orchestrator["task_file"].write_text(
        "---\n"
        "title: Real Active Task\n"
        "goal: Ship it\n"
        "---\n"
    )
    isolated_orchestrator["status_file"].write_text(
        json.dumps(
            {
                "status": "pc_turn",
                "task_name": "stale-status-task",
                "pass": 2,
                "approved": False,
                "relaunch_attempted": True,
            }
        )
    )
    isolated_orchestrator["loop_dir"].joinpath("current", "pc_output.md").write_text(
        "PASS: 2\nSTATUS: BLOCKED\n"
    )

    recovery_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(orchestrator, "builder_running", lambda: False)
    monkeypatch.setattr(
        orchestrator,
        "_queue_manus_recovery_task",
        lambda failed_task, reason: recovery_calls.append((failed_task, reason)) or None,
    )

    orchestrator.handle_pc_turn(
        {
            "status": "pc_turn",
            "task_name": "stale-status-task",
            "pass": 2,
            "approved": False,
            "relaunch_attempted": True,
        },
        elapsed=orchestrator.BUILDER_TIMEOUT,
    )

    archive_names = sorted(p.name for p in isolated_orchestrator["loop_dir"].joinpath("archive").iterdir())
    assert any(name.startswith("task_Real Active Task_p2_builder_timeout_") for name in archive_names)
    assert any(name.startswith("pc_output_Real Active Task_p2_builder_timeout_") for name in archive_names)
    assert not any("stale-status-task" in name for name in archive_names)
    assert recovery_calls == [("Real Active Task", "builder_timeout_after_retry")]


def test_handle_pc_turn_builder_timeout_falls_back_to_status_task_name_when_task_md_missing(
    isolated_orchestrator, monkeypatch
):
    isolated_orchestrator["status_file"].write_text(
        json.dumps(
            {
                "status": "pc_turn",
                "task_name": "status-task-name",
                "pass": 1,
                "approved": False,
                "relaunch_attempted": True,
            }
        )
    )
    isolated_orchestrator["loop_dir"].joinpath("current", "pc_output.md").write_text(
        "PASS: 1\nSTATUS: BLOCKED\n"
    )

    monkeypatch.setattr(orchestrator, "builder_running", lambda: False)
    monkeypatch.setattr(orchestrator, "_queue_manus_recovery_task", lambda failed_task, reason: None)

    orchestrator.handle_pc_turn(
        {
            "status": "pc_turn",
            "task_name": "status-task-name",
            "pass": 1,
            "approved": False,
            "relaunch_attempted": True,
        },
        elapsed=orchestrator.BUILDER_TIMEOUT,
    )

    archive_names = sorted(p.name for p in isolated_orchestrator["loop_dir"].joinpath("archive").iterdir())
    assert any(name.startswith("pc_output_status-task-name_p1_builder_timeout_") for name in archive_names)


def test_handle_approved_waits_when_closeout_ok_missing(isolated_orchestrator):
    isolated_orchestrator["task_file"].write_text("title: Real Task\ngoal: Ship it\n")
    isolated_orchestrator["status_file"].write_text(
        json.dumps(
            {
                "status": "approved",
                "task_name": "real-task",
                "pass": 1,
                "approved": True,
            }
        )
    )
    isolated_orchestrator["loop_dir"].joinpath("current", "pc_output.md").write_text("PASS: 1\nSTATUS: DONE\n")
    isolated_orchestrator["loop_dir"].joinpath("current", "mac_review.md").write_text("APPROVED\n")

    orchestrator.handle_approved(
        {
            "status": "approved",
            "task_name": "real-task",
            "pass": 1,
            "approved": True,
        }
    )

    status = json.loads(isolated_orchestrator["status_file"].read_text())
    archive_names = sorted(p.name for p in isolated_orchestrator["loop_dir"].joinpath("archive").iterdir())
    assert status["status"] == "approved"
    assert isolated_orchestrator["task_file"].exists()
    assert isolated_orchestrator["loop_dir"].joinpath("current", "pc_output.md").exists()
    assert isolated_orchestrator["loop_dir"].joinpath("current", "mac_review.md").exists()
    assert archive_names == []


def test_handle_approved_waits_when_closeout_ok_is_invalid(isolated_orchestrator):
    isolated_orchestrator["task_file"].write_text("title: Real Task\ngoal: Ship it\n")
    isolated_orchestrator["status_file"].write_text(
        json.dumps(
            {
                "status": "approved",
                "task_name": "real-task",
                "pass": 1,
                "approved": True,
            }
        )
    )
    isolated_orchestrator["loop_dir"].joinpath("current", "pc_output.md").write_text("PASS: 1\nSTATUS: DONE\n")
    isolated_orchestrator["loop_dir"].joinpath("current", "mac_review.md").write_text("APPROVED\n")
    isolated_orchestrator["loop_dir"].joinpath("current", "closeout.ok").write_text("not json")

    orchestrator.handle_approved(
        {
            "status": "approved",
            "task_name": "real-task",
            "pass": 1,
            "approved": True,
        }
    )

    status = json.loads(isolated_orchestrator["status_file"].read_text())
    archive_names = sorted(p.name for p in isolated_orchestrator["loop_dir"].joinpath("archive").iterdir())
    assert status["status"] == "approved"
    assert isolated_orchestrator["task_file"].exists()
    assert isolated_orchestrator["loop_dir"].joinpath("current", "closeout.ok").exists()
    assert archive_names == []


def test_handle_approved_idles_when_closeout_ok_matches(isolated_orchestrator):
    isolated_orchestrator["task_file"].write_text("title: real-task\ngoal: Ship it\n")
    isolated_orchestrator["status_file"].write_text(
        json.dumps(
            {
                "status": "approved",
                "task_name": "real-task",
                "pass": 1,
                "approved": True,
            }
        )
    )
    isolated_orchestrator["loop_dir"].joinpath("current", "pc_output.md").write_text("PASS: 1\nSTATUS: DONE\n")
    isolated_orchestrator["loop_dir"].joinpath("current", "mac_review.md").write_text("APPROVED\n")
    isolated_orchestrator["loop_dir"].joinpath("current", "closeout.ok").write_text(
        json.dumps({"task_name": "real-task", "pass": 1, "confirmed_at": "2026-04-04T12:00:00"})
    )

    orchestrator.handle_approved(
        {
            "status": "approved",
            "task_name": "real-task",
            "pass": 1,
            "approved": True,
        }
    )

    status = json.loads(isolated_orchestrator["status_file"].read_text())
    archive_names = sorted(p.name for p in isolated_orchestrator["loop_dir"].joinpath("archive").iterdir())
    assert status["status"] == "idle"
    assert not isolated_orchestrator["task_file"].exists()
    assert any(name.startswith("task_real-task_") for name in archive_names)
    assert any(name.startswith("pc_output_real-task_") for name in archive_names)
    assert any(name.startswith("mac_review_real-task_") for name in archive_names)
    assert any(name.startswith("closeout_real-task_") for name in archive_names)


def test_handle_approved_archives_using_task_md_title_when_status_task_is_stale(isolated_orchestrator):
    isolated_orchestrator["task_file"].write_text(
        "---\n"
        "title: Real Approved Task\n"
        "goal: Ship it\n"
        "---\n"
    )
    isolated_orchestrator["status_file"].write_text(
        json.dumps(
            {
                "status": "approved",
                "task_name": "stale-status-task",
                "pass": 1,
                "approved": True,
            }
        )
    )
    isolated_orchestrator["loop_dir"].joinpath("current", "pc_output.md").write_text("PASS: 1\nSTATUS: DONE\n")
    isolated_orchestrator["loop_dir"].joinpath("current", "mac_review.md").write_text("APPROVED\n")
    isolated_orchestrator["loop_dir"].joinpath("current", "closeout.ok").write_text(
        json.dumps({"task_name": "stale-status-task", "pass": 1, "confirmed_at": "2026-04-04T12:00:00"})
    )

    orchestrator.handle_approved(
        {
            "status": "approved",
            "task_name": "stale-status-task",
            "pass": 1,
            "approved": True,
        }
    )

    status = json.loads(isolated_orchestrator["status_file"].read_text())
    archive_names = sorted(p.name for p in isolated_orchestrator["loop_dir"].joinpath("archive").iterdir())
    assert status["status"] == "idle"
    assert any(name.startswith("task_Real Approved Task_") for name in archive_names)
    assert any(name.startswith("pc_output_Real Approved Task_") for name in archive_names)
    assert any(name.startswith("mac_review_Real Approved Task_") for name in archive_names)
    assert any(name.startswith("closeout_Real Approved Task_") for name in archive_names)
    assert not any("stale-status-task" in name for name in archive_names)


def test_handle_approved_archives_using_status_task_name_when_task_md_missing(isolated_orchestrator):
    isolated_orchestrator["status_file"].write_text(
        json.dumps(
            {
                "status": "approved",
                "task_name": "status-approved-task",
                "pass": 1,
                "approved": True,
            }
        )
    )
    isolated_orchestrator["loop_dir"].joinpath("current", "pc_output.md").write_text("PASS: 1\nSTATUS: DONE\n")
    isolated_orchestrator["loop_dir"].joinpath("current", "mac_review.md").write_text("APPROVED\n")
    isolated_orchestrator["loop_dir"].joinpath("current", "closeout.ok").write_text(
        json.dumps({"task_name": "status-approved-task", "pass": 1, "confirmed_at": "2026-04-04T12:00:00"})
    )

    orchestrator.handle_approved(
        {
            "status": "approved",
            "task_name": "status-approved-task",
            "pass": 1,
            "approved": True,
        }
    )

    status = json.loads(isolated_orchestrator["status_file"].read_text())
    archive_names = sorted(p.name for p in isolated_orchestrator["loop_dir"].joinpath("archive").iterdir())
    assert status["status"] == "idle"
    assert not any(name.startswith("task_status-approved-task_") for name in archive_names)
    assert any(name.startswith("pc_output_status-approved-task_") for name in archive_names)
    assert any(name.startswith("mac_review_status-approved-task_") for name in archive_names)
    assert any(name.startswith("closeout_status-approved-task_") for name in archive_names)


def test_handle_mac_turn_blocks_when_review_header_mismatches_task_and_pass(isolated_orchestrator):
    isolated_orchestrator["task_file"].write_text("title: Current Active Task\ngoal: Ship it\n")
    isolated_orchestrator["status_file"].write_text(
        json.dumps(
            {
                "status": "mac_turn",
                "task_name": "current-task",
                "pass": 2,
                "approved": False,
            }
        )
    )
    isolated_orchestrator["loop_dir"].joinpath("current", "mac_review.md").write_text(
        "# Mac Review — old-task Pass 1\n\nNEEDS_REWORK\n"
    )

    orchestrator.handle_mac_turn(
        {
            "status": "mac_turn",
            "task_name": "current-task",
            "pass": 2,
            "approved": False,
        },
        elapsed=0,
    )

    status = json.loads(isolated_orchestrator["status_file"].read_text())
    assert status["status"] == "blocked"
    assert status["block_reason"] == "stale_mac_review"


def test_handle_mac_turn_accepts_review_header_matching_active_task_title(isolated_orchestrator):
    isolated_orchestrator["task_file"].write_text("title: Current Active Task\ngoal: Ship it\n")
    isolated_orchestrator["status_file"].write_text(
        json.dumps(
            {
                "status": "mac_turn",
                "task_name": "current-task",
                "pass": 2,
                "approved": False,
            }
        )
    )
    isolated_orchestrator["loop_dir"].joinpath("current", "mac_review.md").write_text(
        "# Mac Review — Current Active Task Pass 2\n\nNEEDS_REWORK\n"
    )

    orchestrator.handle_mac_turn(
        {
            "status": "mac_turn",
            "task_name": "current-task",
            "pass": 2,
            "approved": False,
        },
        elapsed=0,
    )

    status = json.loads(isolated_orchestrator["status_file"].read_text())
    assert status["status"] == "pc_turn"
    assert status["pass"] == 3


# ---------------------------------------------------------------------------
# Chief acceptance gate integration (harness-backed retest tasks only)
# ---------------------------------------------------------------------------

def _setup_harness_mac_turn(isolated_orchestrator, monkeypatch, verdict_fn):
    """Helper: set up a harness-backed retest in mac_turn with APPROVED review and a mocked gate."""
    isolated_orchestrator["task_file"].write_text(
        "title: Harness Task\n"
        "execution_mode: harness-backed-retest\n"
        "harness_mode: dry-run\n"
        "harness_flow: morning_brief\n"
    )
    isolated_orchestrator["loop_dir"].joinpath("current", "pc_output.md").write_text(
        "PASS: 1\nCHANGES: edited foo.py\nREASONING: fix\n"
        "ROLLBACK PLAN: revert\nCOST: $0\nTRUTH: ok\nHEADROOM: fine\n"
    )
    isolated_orchestrator["loop_dir"].joinpath("current", "mac_review.md").write_text("APPROVED\n")
    monkeypatch.setattr(
        orchestrator, "_chief_acceptance_verdict", verdict_fn,
    )


def test_chief_gate_approve_reaches_approved(isolated_orchestrator, monkeypatch):
    _setup_harness_mac_turn(isolated_orchestrator, monkeypatch, lambda status: "APPROVE")
    orchestrator.handle_mac_turn(
        {"status": "mac_turn", "task_name": "harness-task", "pass": 1, "approved": False},
        elapsed=0,
    )
    status = json.loads(isolated_orchestrator["status_file"].read_text())
    assert status["status"] == "approved"
    assert status["approved"] is True


def test_chief_gate_rework_loops_back(isolated_orchestrator, monkeypatch):
    _setup_harness_mac_turn(isolated_orchestrator, monkeypatch, lambda status: "REWORK")
    orchestrator.handle_mac_turn(
        {"status": "mac_turn", "task_name": "harness-task", "pass": 1, "approved": False},
        elapsed=0,
    )
    status = json.loads(isolated_orchestrator["status_file"].read_text())
    assert status["status"] == "pc_turn"
    assert status["pass"] == 2


def test_chief_gate_insufficient_blocks(isolated_orchestrator, monkeypatch):
    _setup_harness_mac_turn(isolated_orchestrator, monkeypatch, lambda status: "INSUFFICIENT_EVIDENCE")
    orchestrator.handle_mac_turn(
        {"status": "mac_turn", "task_name": "harness-task", "pass": 1, "approved": False},
        elapsed=0,
    )
    status = json.loads(isolated_orchestrator["status_file"].read_text())
    assert status["status"] == "blocked"
    assert status["block_reason"] == "chief_insufficient_evidence"


def test_non_harness_task_skips_chief_gate(isolated_orchestrator, monkeypatch):
    """Non-harness-backed tasks should go straight to approved without calling the gate."""
    isolated_orchestrator["task_file"].write_text(
        "title: Normal Task\ngoal: Ship it\n"
    )
    isolated_orchestrator["loop_dir"].joinpath("current", "pc_output.md").write_text(
        "PASS: 1\nCHANGES: x\nREASONING: y\nROLLBACK PLAN: z\nCOST: $0\nTRUTH: ok\nHEADROOM: ok\n"
    )
    isolated_orchestrator["loop_dir"].joinpath("current", "mac_review.md").write_text("APPROVED\n")
    gate_calls = []
    monkeypatch.setattr(
        orchestrator, "_chief_acceptance_verdict",
        lambda status: gate_calls.append(1) or "REWORK",
    )
    orchestrator.handle_mac_turn(
        {"status": "mac_turn", "task_name": "normal-task", "pass": 1, "approved": False},
        elapsed=0,
    )
    status = json.loads(isolated_orchestrator["status_file"].read_text())
    assert status["status"] == "approved"
    assert gate_calls == [], "gate should not be called for non-harness tasks"

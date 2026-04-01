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
    assert isolated_orchestrator["launches"] == [["bash", "/home/openclaw/polish_loop/run_polish_pass.sh"]]
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

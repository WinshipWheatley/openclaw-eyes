from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polish_loop_backlog_ingest import ingest
from polish_loop.control_plane import ControlPlaneLedger, TaskRejected


POLICY_PATH = ROOT / "polish_loop" / "ingest_policy.json"


def _assert_git_tracked(relative_path: str) -> None:
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative_path],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _write_queue(path: Path) -> None:
    path.write_text(
        """# Some Header
NEW BATCH 044-093
- **083** [P2/brain-quality] test-task-083
- **084** [P1/finance] ar-receivables-packet-084
- **085** [P1/finance] ar-receivables-packet-085
- **089** [P1/other] test-task-089
""",
        encoding="utf-8",
    )


def _seed_minimal_tasks_table(path: Path) -> None:
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, status TEXT, payload TEXT)")
        con.commit()
    finally:
        con.close()


def test_ingest_policy_file_is_committed_and_blocks_known_ar_collision_tasks():
    _assert_git_tracked("polish_loop/ingest_policy.json")

    data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    blocked = {
        task_id
        for policy in data["policies"]
        if policy.get("match", {}).get("queue") == "MASTER-WORK-QUEUE.md"
        for task_id in policy.get("match", {}).get("task_ids", [])
    }

    assert {"backlog-084", "backlog-085", "backlog-086", "backlog-087", "backlog-088"} <= blocked


def test_backlog_ingest_dry_run_filters_policy_blocked_tasks(tmp_path):
    queue_path = tmp_path / "MASTER-WORK-QUEUE.md"
    ledger_path = tmp_path / "control_plane.sqlite3"
    _write_queue(queue_path)
    _seed_minimal_tasks_table(ledger_path)

    res = ingest(queue_path, ledger_path, dry_run=True)
    parsed_task_ids = {it["task_id"] for it in res["items"]}

    assert {"backlog-083", "backlog-089"} <= parsed_task_ids
    assert "backlog-084" not in parsed_task_ids
    assert "backlog-085" not in parsed_task_ids


def test_control_plane_admission_rejects_policy_blocked_queue_task(tmp_path):
    ledger = ControlPlaneLedger(tmp_path / "control.sqlite3", status_view_path=tmp_path / "status.json")

    with pytest.raises(TaskRejected, match="Gig-to-Cash Roadmap Collision"):
        ledger.admit_task(
            task_id="backlog-084",
            source="human_intent",
            task_type="codex_backlog",
            requested_status="READY",
            payload={"queue_ref": "/mnt/e/openclaw/orchestration/MASTER-WORK-QUEUE.md"},
            acceptance_ref={"queue": "MASTER-WORK-QUEUE.md", "batch": "044-093"},
        )

    with ledger.connect() as conn:
        row = conn.execute("SELECT id FROM tasks WHERE id = ?", ("backlog-084",)).fetchone()
    assert row is None

from __future__ import annotations

import dataclasses
import json
import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polish_loop import orchestrator
from polish_loop.control_plane import ControlPlaneLedger, TaskLease
from polish_loop.worker_runtime import WorkerRuntimeConfig, WorkerRuntimeResult


def _ledger(tmp_path: Path) -> ControlPlaneLedger:
    return ControlPlaneLedger(tmp_path / "control.sqlite3")


def _config(tmp_path: Path) -> WorkerRuntimeConfig:
    loop_dir = tmp_path / "loop"
    return WorkerRuntimeConfig(
        local_builder_path=tmp_path / "never-run-local-builder.py",
        loop_dir=loop_dir,
        task_path=loop_dir / "task.md",
        pc_output_path=loop_dir / "current" / "pc_output.md",
        artifact_dir=loop_dir / "current",
        subprocess_timeout_seconds=1,
    )


def _admit_ready(
    ledger: ControlPlaneLedger,
    *,
    task_id: str = "synthetic-loop-closure",
    max_attempts: int = 3,
) -> str:
    return ledger.admit_task(
        task_id=task_id,
        source="human_intent",
        task_type="synthetic_polish_loop",
        requested_status="READY",
        payload={"goal": "prove local builder bridge closure", "synthetic": True},
        acceptance_ref={"synthetic": True},
        max_attempts=max_attempts,
    )


def _rows(ledger: ControlPlaneLedger, sql: str) -> list[dict]:
    with sqlite3.connect(ledger.path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql).fetchall()]


def _success_result(config: WorkerRuntimeConfig, lease: TaskLease) -> WorkerRuntimeResult:
    config.pc_output_path.parent.mkdir(parents=True, exist_ok=True)
    config.pc_output_path.write_text(
        "\n".join(
            [
                "PASS: 1",
                "STATUS: DONE",
                "",
                "CHANGES:",
                "- synthetic bridge test wrote candidate evidence",
                "",
                "REASONING:",
                "- Fake builder proves dispatch-to-ledger closure.",
                "",
                "ROLLBACK PLAN:",
                "- Revert synthetic test fixture.",
                "",
                "COST:",
                "- 0 external calls.",
                "",
                "TRUTH:",
                "- Verified: fake builder was invoked exactly once.",
                "",
                "HEADROOM:",
                "- Not applicable.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    artifact_path = config.artifact_dir / f"{lease.task_id}.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text('{"synthetic": true}\n', encoding="utf-8")
    return WorkerRuntimeResult(
        task_id=lease.task_id,
        exit_code=0,
        submitted_candidate=True,
        failure_recorded=False,
        artifact_path=artifact_path,
        pc_output_path=config.pc_output_path,
    )


def _failure_result(config: WorkerRuntimeConfig, lease: TaskLease) -> WorkerRuntimeResult:
    artifact_path = config.artifact_dir / f"{lease.task_id}-failed.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text('{"synthetic": "failed"}\n', encoding="utf-8")
    return WorkerRuntimeResult(
        task_id=lease.task_id,
        exit_code=7,
        submitted_candidate=False,
        failure_recorded=False,
        artifact_path=artifact_path,
        pc_output_path=config.pc_output_path,
        fingerprint="synthetic_builder_failure",
    )


def test_synthetic_success_closes_dispatch_to_ledger_with_fake_builder(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    task_id = _admit_ready(ledger)
    config = _config(tmp_path)
    calls: list[str] = []

    def fake_builder(ledger_arg, lease, *, config):
        calls.append(lease.task_id)
        assert ledger_arg.path == ledger.path
        return _success_result(config, lease)

    def forbidden_default_builder(*_args, **_kwargs):
        raise AssertionError("default local builder must not run in this test")

    monkeypatch.setattr(orchestrator, "run_local_builder_worker", forbidden_default_builder)

    result = orchestrator.run_phase_c_once(
        ledger_path=ledger.path,
        owner="orchestrator-test",
        worker_config=config,
        builder_runner=fake_builder,
        enable_local_builder=True,
    )

    assert result.dispatched is True
    assert result.task_id == task_id
    assert calls == [task_id]
    task = ledger.get_task(task_id)
    assert task["status"] == "VERIFYING"
    assert task["candidate_evidence"]["schema_version"] == "polish_loop_local_builder_receipt_v0"
    assert task["candidate_evidence"]["worker_runtime"] == "phase_c_closure_bridge"
    assert task["candidate_evidence"]["pc_output_path"] == str(config.pc_output_path)
    assert _rows(ledger, "SELECT event_type FROM events ORDER BY id")[-1]["event_type"] == "CANDIDATE_SUBMITTED"


def test_synthetic_failure_records_retry_receipt_without_infinite_loop(tmp_path):
    ledger = _ledger(tmp_path)
    task_id = _admit_ready(ledger, max_attempts=3)
    config = _config(tmp_path)
    calls: list[str] = []

    def fake_builder(_ledger, lease, *, config):
        calls.append(lease.task_id)
        return _failure_result(config, lease)

    orchestrator.run_phase_c_once(
        ledger_path=ledger.path,
        owner="orchestrator-test",
        worker_config=config,
        builder_runner=fake_builder,
        enable_local_builder=True,
    )

    task = ledger.get_task(task_id)
    assert calls == [task_id]
    assert task["status"] == "READY"
    assert task["attempts"] == 1
    assert task["failure_fingerprint"] == "synthetic_builder_failure"
    attempts = _rows(ledger, "SELECT status, failure_fingerprint, evidence FROM attempts")
    assert len(attempts) == 1
    assert attempts[0]["status"] == "READY"
    assert attempts[0]["failure_fingerprint"] == "synthetic_builder_failure"
    receipt = json.loads(attempts[0]["evidence"])
    assert receipt["schema_version"] == "polish_loop_failure_receipt_v0"
    assert receipt["detail"]["status"] == "builder_failed"
    assert _rows(ledger, "SELECT event_type FROM events ORDER BY id")[-1]["event_type"] == "TASK_REQUEUED"


def test_builder_exception_is_caught_and_recorded_as_failure(tmp_path):
    ledger = _ledger(tmp_path)
    task_id = _admit_ready(ledger, max_attempts=3)
    config = _config(tmp_path)

    def exploding_builder(_ledger, _lease, *, config):
        raise RuntimeError("synthetic builder boom")

    result = orchestrator.run_phase_c_once(
        ledger_path=ledger.path,
        owner="orchestrator-test",
        worker_config=config,
        builder_runner=exploding_builder,
        enable_local_builder=True,
    )

    assert result.dispatched is True
    task = ledger.get_task(task_id)
    assert task["status"] == "READY"
    assert task["failure_fingerprint"].startswith("local_builder_exception_runtimeerror_")
    attempts = _rows(ledger, "SELECT evidence FROM attempts")
    receipt = json.loads(attempts[0]["evidence"])
    assert receipt["detail"]["status"] == "builder_exception"
    assert receipt["detail"]["exception_type"] == "RuntimeError"


def test_local_builder_flag_off_writes_directive_but_does_not_call_builder(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    task_id = _admit_ready(ledger)
    config = _config(tmp_path)
    calls: list[str] = []
    monkeypatch.delenv(orchestrator.LOCAL_BUILDER_FLAG, raising=False)

    def fake_builder(_ledger, lease, *, config):
        calls.append(lease.task_id)
        return _success_result(config, lease)

    orchestrator.run_phase_c_once(
        ledger_path=ledger.path,
        owner="orchestrator-test",
        worker_config=config,
        builder_runner=fake_builder,
    )

    task = ledger.get_task(task_id)
    assert calls == []
    assert task["status"] == "LEASED"
    assert task["candidate_evidence"] is None
    assert len(sorted((config.loop_dir / "to-pc").glob("FIX-*.md"))) == 1


def test_non_dispatchable_task_does_not_call_builder(tmp_path):
    ledger = _ledger(tmp_path)
    task_id = ledger.admit_task(
        task_id="held-synthetic-task",
        source="human_intent",
        task_type="synthetic_polish_loop",
        requested_status="PROPOSED",
        payload={"goal": "held task should not dispatch"},
        acceptance_ref={"synthetic": True},
    )
    config = _config(tmp_path)
    calls: list[str] = []

    def fake_builder(_ledger, lease, *, config):
        calls.append(lease.task_id)
        return _success_result(config, lease)

    result = orchestrator.run_phase_c_once(
        ledger_path=ledger.path,
        owner="orchestrator-test",
        worker_config=config,
        builder_runner=fake_builder,
        enable_local_builder=True,
    )

    assert result.dispatched is False
    assert calls == []
    assert ledger.get_task(task_id)["status"] == "PROPOSED"


def test_wrong_lease_is_rejected_before_success_or_builder_call(tmp_path):
    ledger = _ledger(tmp_path)
    task_id = _admit_ready(ledger)
    lease = ledger.claim_next_ready(owner="orchestrator-test")
    assert lease is not None
    wrong_lease = dataclasses.replace(lease, lease_nonce="stale-or-wrong-nonce")
    config = _config(tmp_path)
    calls: list[str] = []

    def fake_builder(_ledger, lease, *, config):
        calls.append(lease.task_id)
        return _success_result(config, lease)

    receipt = orchestrator.phase_c_dispatch_local_builder(
        wrong_lease,
        ledger=ledger,
        config=config,
        builder_runner=fake_builder,
        enable_local_builder=True,
    )

    task = ledger.get_task(task_id)
    assert receipt.status == "stale_lease_not_dispatched"
    assert receipt.builder_invoked is False
    assert calls == []
    assert task["status"] == "LEASED"
    assert task["candidate_evidence"] is None


def test_missing_lease_is_rejected_without_success_or_builder_call(tmp_path):
    ledger = _ledger(tmp_path)
    config = _config(tmp_path)
    missing_lease = TaskLease(
        task_id="missing-task",
        owner="orchestrator-test",
        lease_nonce="missing",
        lease_expiry="2099-01-01T00:00:00+00:00",
        attempt_no=1,
        version=1,
    )
    calls: list[str] = []

    def fake_builder(_ledger, lease, *, config):
        calls.append(lease.task_id)
        return _success_result(config, lease)

    receipt = orchestrator.phase_c_dispatch_local_builder(
        missing_lease,
        ledger=ledger,
        config=config,
        builder_runner=fake_builder,
        enable_local_builder=True,
    )

    assert receipt.status == "missing_task"
    assert calls == []
    assert ledger.counts()["tasks"] == 0


def test_injected_fake_builder_path_does_not_launch_subprocess(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    _admit_ready(ledger)
    config = _config(tmp_path)

    def forbidden_subprocess_run(*_args, **_kwargs):
        raise AssertionError("no subprocess or model process may launch in bridge tests")

    def fake_builder(_ledger, lease, *, config):
        return _success_result(config, lease)

    monkeypatch.setattr(subprocess, "run", forbidden_subprocess_run)

    orchestrator.run_phase_c_once(
        ledger_path=ledger.path,
        owner="orchestrator-test",
        worker_config=config,
        builder_runner=fake_builder,
        enable_local_builder=True,
    )

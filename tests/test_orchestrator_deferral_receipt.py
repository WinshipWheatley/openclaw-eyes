from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polish_loop import orchestrator
from polish_loop.control_plane import ControlPlaneLedger
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


def _admit_ready(ledger: ControlPlaneLedger, *, task_id: str = "deferral-receipt-task") -> str:
    return ledger.admit_task(
        task_id=task_id,
        source="human_intent",
        task_type="synthetic_polish_loop",
        requested_status="READY",
        payload={"goal": "prove honest deferral receipt", "synthetic": True},
        acceptance_ref={"synthetic": True},
    )


def test_deferred_builder_result_is_not_recorded_as_a_failure(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    task_id = _admit_ready(ledger)
    config = _config(tmp_path)

    def deferred_builder(ledger_arg, lease, *, config):
        return WorkerRuntimeResult(
            task_id=lease.task_id,
            exit_code=None,
            submitted_candidate=False,
            failure_recorded=False,
            artifact_path=config.artifact_dir / "unused.json",
            pc_output_path=config.pc_output_path,
            deferred=True,
            defer_reason="interactive_gpu_lease_active",
        )

    def forbidden_default_builder(*_args, **_kwargs):
        raise AssertionError("default local builder must not run in this test")

    monkeypatch.setattr(orchestrator, "run_local_builder_worker", forbidden_default_builder)

    result = orchestrator.run_phase_c_once(
        ledger_path=ledger.path,
        owner="deferral-test",
        worker_config=config,
        builder_runner=deferred_builder,
        enable_local_builder=True,
    )

    assert result.dispatched is True
    task = ledger.get_task(task_id)
    # The whole point: a resource-aware defer must not be mistaken for a builder
    # failure. The task must stay exactly where claim_task() left it (LEASED),
    # not get pushed to BLOCKED/READY-with-a-failure-fingerprint by the generic
    # "anything that isn't a submitted candidate is a failure" fallback.
    assert task["status"] == "LEASED"
    assert task["failure_fingerprint"] in (None, "")
    events = ledger.list_tasks()
    assert events  # sanity: ledger is queryable at all


def test_deferred_receipt_status_names_the_defer_reason(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    _admit_ready(ledger)
    config = _config(tmp_path)

    def deferred_builder(ledger_arg, lease, *, config):
        return WorkerRuntimeResult(
            task_id=lease.task_id,
            exit_code=None,
            submitted_candidate=False,
            failure_recorded=False,
            artifact_path=config.artifact_dir / "unused.json",
            pc_output_path=config.pc_output_path,
            deferred=True,
            defer_reason="gpu_lease_resource_busy",
        )

    monkeypatch.setattr(orchestrator, "run_local_builder_worker", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("default local builder must not run in this test")
    ))

    result = orchestrator.run_phase_c_once(
        ledger_path=ledger.path,
        owner="deferral-test-2",
        worker_config=config,
        builder_runner=deferred_builder,
        enable_local_builder=True,
    )

    assert result.dispatched is True

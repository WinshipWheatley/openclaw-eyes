from __future__ import annotations

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


def _ledger(tmp_path: Path) -> ControlPlaneLedger:
    return ControlPlaneLedger(tmp_path / "control.sqlite3")


def _admit_and_claim(
    ledger: ControlPlaneLedger,
    *,
    task_id: str = "file-ledger-synthetic",
    max_attempts: int = 3,
) -> TaskLease:
    ledger.admit_task(
        task_id=task_id,
        source="human_intent",
        task_type="synthetic_polish_loop",
        requested_status="READY",
        payload={"goal": "reconcile file loop with ledger", "synthetic": True},
        acceptance_ref={"synthetic": True},
        max_attempts=max_attempts,
    )
    lease = ledger.claim_task(task_id, owner="orchestrator-test", lease_seconds=600)
    assert lease is not None
    return lease


def _status_for(ledger: ControlPlaneLedger, lease: TaskLease, **overrides) -> dict:
    status = {
        "status": "pc_turn",
        "task_name": lease.task_id,
        "pass": lease.attempt_no,
        "phase_c_status": "LEASED",
        "phase_c_task_id": lease.task_id,
        "phase_c_owner": lease.owner,
        "phase_c_ledger": str(ledger.path),
    }
    status.update(overrides)
    return status


def _write_valid_pc_output(path: Path, *, pass_num: int = 1) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"PASS: {pass_num}",
                "STATUS: DONE",
                "",
                "CHANGES:",
                "- synthetic file-loop output",
                "",
                "REASONING:",
                "- Proves the file-loop result bridge records ledger evidence.",
                "",
                "ROLLBACK PLAN:",
                "- Unset the bridge flag.",
                "",
                "COST:",
                "- 0 external calls.",
                "",
                "TRUTH:",
                "- Verified: synthetic temp SQLite only.",
                "",
                "HEADROOM:",
                "- Not applicable.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _rows(ledger: ControlPlaneLedger, sql: str) -> list[dict]:
    with sqlite3.connect(ledger.path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql).fetchall()]


def test_flag_off_bridge_is_inert_and_does_not_mutate_ledger(tmp_path):
    ledger = _ledger(tmp_path)
    lease = _admit_and_claim(ledger)
    pc_output = _write_valid_pc_output(tmp_path / "loop" / "current" / "pc_output.md")

    receipt = orchestrator.reconcile_file_loop_result_with_ledger(
        _status_for(ledger, lease),
        result_kind="success",
        pc_output_path=pc_output,
        status_json_path=tmp_path / "status.json",
        task_md_path=tmp_path / "task.md",
        bridge_enabled=False,
    )

    task = ledger.get_task(lease.task_id)
    assert receipt.status == "bridge_disabled"
    assert receipt.ledger_recorded is False
    assert task["status"] == "LEASED"
    assert task["candidate_evidence"] is None


def test_valid_file_loop_output_records_candidate_evidence(tmp_path):
    ledger = _ledger(tmp_path)
    lease = _admit_and_claim(ledger)
    pc_output = _write_valid_pc_output(tmp_path / "loop" / "current" / "pc_output.md")

    receipt = orchestrator.reconcile_file_loop_result_with_ledger(
        _status_for(ledger, lease),
        result_kind="success",
        pc_output_path=pc_output,
        status_json_path=tmp_path / "status.json",
        task_md_path=tmp_path / "task.md",
        bridge_enabled=True,
    )

    task = ledger.get_task(lease.task_id)
    assert receipt.status == "candidate_submitted"
    assert receipt.evidence_recorded is True
    assert task["status"] == "VERIFYING"
    assert task["candidate_evidence"]["schema_version"] == "polish_loop_file_ledger_reconciliation_receipt_v0"
    assert task["candidate_evidence"]["bridge"] == "orchestrator_file_loop_reconciliation"
    assert task["candidate_evidence"]["pc_output_path"] == str(pc_output)
    assert _rows(ledger, "SELECT event_type FROM events ORDER BY id")[-1]["event_type"] == "CANDIDATE_SUBMITTED"


def test_file_loop_failure_records_retry_receipt(tmp_path):
    ledger = _ledger(tmp_path)
    lease = _admit_and_claim(ledger, max_attempts=3)
    pc_output = tmp_path / "loop" / "current" / "pc_output.md"

    receipt = orchestrator.reconcile_file_loop_result_with_ledger(
        _status_for(ledger, lease),
        result_kind="failure",
        failure_reason="weak_pc_output_quality",
        pc_output_path=pc_output,
        status_json_path=tmp_path / "status.json",
        task_md_path=tmp_path / "task.md",
        bridge_enabled=True,
    )

    task = ledger.get_task(lease.task_id)
    assert receipt.status == "failure_recorded"
    assert receipt.failure_recorded is True
    assert task["status"] == "READY"
    assert task["failure_fingerprint"] == "file_loop_weak_pc_output_quality"
    attempts = _rows(ledger, "SELECT status, failure_fingerprint, evidence FROM attempts")
    assert attempts[0]["status"] == "READY"
    assert attempts[0]["failure_fingerprint"] == "file_loop_weak_pc_output_quality"
    failure_receipt = json.loads(attempts[0]["evidence"])
    assert failure_receipt["schema_version"] == "polish_loop_failure_receipt_v0"
    assert failure_receipt["detail"]["bridge"] == "orchestrator_file_loop_reconciliation"
    assert _rows(ledger, "SELECT event_type FROM events ORDER BY id")[-1]["event_type"] == "TASK_REQUEUED"


def test_missing_phase_c_context_does_not_mutate_or_mark_success(tmp_path):
    ledger = _ledger(tmp_path)
    lease = _admit_and_claim(ledger)
    pc_output = _write_valid_pc_output(tmp_path / "loop" / "current" / "pc_output.md")

    receipt = orchestrator.reconcile_file_loop_result_with_ledger(
        {"status": "pc_turn", "pass": 1},
        result_kind="success",
        pc_output_path=pc_output,
        bridge_enabled=True,
    )

    assert receipt.status == "no_phase_c_context"
    assert receipt.evidence_recorded is False
    assert ledger.get_task(lease.task_id)["status"] == "LEASED"
    assert ledger.get_task(lease.task_id)["candidate_evidence"] is None


def test_conflicting_status_context_rejects_wrong_owner_nonce_and_attempt(tmp_path):
    ledger = _ledger(tmp_path)
    lease = _admit_and_claim(ledger)
    pc_output = _write_valid_pc_output(tmp_path / "loop" / "current" / "pc_output.md")

    for overrides, conflict_key in [
        ({"phase_c_owner": "other-owner"}, "owner"),
        ({"phase_c_lease_nonce": "wrong-nonce"}, "lease_nonce"),
        ({"phase_c_attempt_no": lease.attempt_no + 1}, "attempt_no"),
    ]:
        receipt = orchestrator.reconcile_file_loop_result_with_ledger(
            _status_for(ledger, lease, **overrides),
            result_kind="success",
            pc_output_path=pc_output,
            bridge_enabled=True,
        )
        assert receipt.status == "conflicting_sources"
        assert receipt.conflict_detail is not None
        assert conflict_key in receipt.conflict_detail

    task = ledger.get_task(lease.task_id)
    assert task["status"] == "LEASED"
    assert task["candidate_evidence"] is None


def test_expired_lease_is_rejected_without_success(tmp_path):
    ledger = _ledger(tmp_path)
    lease = _admit_and_claim(ledger)
    pc_output = _write_valid_pc_output(tmp_path / "loop" / "current" / "pc_output.md")
    with ledger.connect() as conn:
        conn.execute(
            "UPDATE tasks SET lease_expiry='2000-01-01T00:00:00+00:00' WHERE id=?",
            (lease.task_id,),
        )
        conn.commit()

    receipt = orchestrator.reconcile_file_loop_result_with_ledger(
        _status_for(ledger, lease),
        result_kind="success",
        pc_output_path=pc_output,
        bridge_enabled=True,
    )

    assert receipt.status == "stale_lease_result_rejected"
    assert ledger.get_task(lease.task_id)["status"] == "LEASED"
    assert ledger.get_task(lease.task_id)["candidate_evidence"] is None


def test_repeated_success_handling_is_idempotent(tmp_path):
    ledger = _ledger(tmp_path)
    lease = _admit_and_claim(ledger)
    pc_output = _write_valid_pc_output(tmp_path / "loop" / "current" / "pc_output.md")
    status = _status_for(ledger, lease)

    first = orchestrator.reconcile_file_loop_result_with_ledger(
        status,
        result_kind="success",
        pc_output_path=pc_output,
        bridge_enabled=True,
    )
    second = orchestrator.reconcile_file_loop_result_with_ledger(
        status,
        result_kind="success",
        pc_output_path=pc_output,
        bridge_enabled=True,
    )

    assert first.status == "candidate_submitted"
    assert second.status == "already_recorded"
    assert second.evidence_recorded is True
    submitted = _rows(ledger, "SELECT event_type FROM events WHERE event_type='CANDIDATE_SUBMITTED'")
    assert len(submitted) == 1


def test_bridge_does_not_launch_subprocess_or_model(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    lease = _admit_and_claim(ledger)
    pc_output = _write_valid_pc_output(tmp_path / "loop" / "current" / "pc_output.md")

    def forbidden_subprocess(*_args, **_kwargs):
        raise AssertionError("file-ledger bridge must not launch subprocesses")

    monkeypatch.setattr(subprocess, "run", forbidden_subprocess)

    receipt = orchestrator.reconcile_file_loop_result_with_ledger(
        _status_for(ledger, lease),
        result_kind="success",
        pc_output_path=pc_output,
        bridge_enabled=True,
    )

    assert receipt.status == "candidate_submitted"


def test_handle_pc_turn_flag_off_preserves_legacy_transition_without_ledger_mutation(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    lease = _admit_and_claim(ledger)
    loop_dir = tmp_path / "loop"
    status_file = loop_dir / "status.json"
    pc_output = _write_valid_pc_output(loop_dir / "current" / "pc_output.md")
    status = _status_for(ledger, lease)
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text(json.dumps(status), encoding="utf-8")

    monkeypatch.delenv(orchestrator.FILE_LEDGER_BRIDGE_FLAG, raising=False)
    monkeypatch.setattr(orchestrator, "LOOP_DIR", loop_dir)
    monkeypatch.setattr(orchestrator, "STATUS_FILE", status_file)
    monkeypatch.setattr(orchestrator, "PC_OUTPUT", pc_output)
    monkeypatch.setattr(orchestrator, "TASK_MD", loop_dir / "task.md")
    monkeypatch.setattr(orchestrator, "_TEST_SUPPRESS_FILE_LOGS", True)

    orchestrator.handle_pc_turn(status, elapsed=0)

    assert json.loads(status_file.read_text(encoding="utf-8"))["status"] == "mac_turn"
    assert ledger.get_task(lease.task_id)["status"] == "LEASED"
    assert ledger.get_task(lease.task_id)["candidate_evidence"] is None


def test_handle_pc_turn_flag_on_records_success_before_legacy_transition(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    lease = _admit_and_claim(ledger)
    loop_dir = tmp_path / "loop"
    status_file = loop_dir / "status.json"
    pc_output = _write_valid_pc_output(loop_dir / "current" / "pc_output.md")
    status = _status_for(ledger, lease)
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text(json.dumps(status), encoding="utf-8")

    monkeypatch.setenv(orchestrator.FILE_LEDGER_BRIDGE_FLAG, "1")
    monkeypatch.setattr(orchestrator, "LOOP_DIR", loop_dir)
    monkeypatch.setattr(orchestrator, "STATUS_FILE", status_file)
    monkeypatch.setattr(orchestrator, "PC_OUTPUT", pc_output)
    monkeypatch.setattr(orchestrator, "TASK_MD", loop_dir / "task.md")
    monkeypatch.setattr(orchestrator, "_TEST_SUPPRESS_FILE_LOGS", True)

    orchestrator.handle_pc_turn(status, elapsed=0)

    task = ledger.get_task(lease.task_id)
    assert task["status"] == "VERIFYING"
    assert task["candidate_evidence"]["bridge"] == "orchestrator_file_loop_reconciliation"
    assert json.loads(status_file.read_text(encoding="utf-8"))["status"] == "mac_turn"


def test_handle_pc_turn_flag_on_missing_context_blocks_false_success(tmp_path, monkeypatch):
    loop_dir = tmp_path / "loop"
    status_file = loop_dir / "status.json"
    pc_output = _write_valid_pc_output(loop_dir / "current" / "pc_output.md")
    status = {"status": "pc_turn", "task_name": "legacy-only", "pass": 1}
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text(json.dumps(status), encoding="utf-8")

    monkeypatch.setenv(orchestrator.FILE_LEDGER_BRIDGE_FLAG, "1")
    monkeypatch.setattr(orchestrator, "LOOP_DIR", loop_dir)
    monkeypatch.setattr(orchestrator, "STATUS_FILE", status_file)
    monkeypatch.setattr(orchestrator, "PC_OUTPUT", pc_output)
    monkeypatch.setattr(orchestrator, "TASK_MD", loop_dir / "task.md")
    monkeypatch.setattr(orchestrator, "_TEST_SUPPRESS_FILE_LOGS", True)

    orchestrator.handle_pc_turn(status, elapsed=0)

    written = json.loads(status_file.read_text(encoding="utf-8"))
    assert written["status"] == "blocked"
    assert written["block_reason"] == "file_ledger_bridge_no_phase_c_context"

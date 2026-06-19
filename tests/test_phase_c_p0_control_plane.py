from __future__ import annotations

from pathlib import Path

import pytest

from polish_loop.control_plane import (
    AcceptanceDecision,
    ControlPlaneLedger,
    InvalidTransition,
    SourceNotAllowed,
    TaskRejected,
    make_acceptance_ref,
    run_control_plane_once,
)


def _write_candidate(path: Path, pass_num: int = 1) -> Path:
    path.write_text(
        "\n".join(
            [
                f"PASS: {pass_num}",
                "STATUS: DONE",
                "",
                "CHANGES:",
                "- candidate evidence",
                "",
                "REASONING:",
                "- code-owned gate decides completion",
                "",
                "ROLLBACK PLAN:",
                "- revert candidate changes",
                "",
                "COST:",
                "- local test fixture",
                "",
                "TRUTH:",
                "- Verified: fixture was written by the test",
                "",
                "HEADROOM:",
                "- not applicable",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _ready_task(
    ledger: ControlPlaneLedger,
    tmp_path: Path,
    *,
    task_id: str = "task-1",
    max_attempts: int = 3,
) -> str:
    acceptance_file = tmp_path / f"{task_id}-acceptance.txt"
    acceptance_file.write_text("immutable acceptance\n", encoding="utf-8")
    return ledger.admit_task(
        task_id=task_id,
        source="human_intent",
        task_type="heal_task",
        requested_status="READY",
        payload={
            "source_surface": "cassandra",
            "bad_exchange": "stale answer",
            "expected_behavior": "answer from proof",
            "truth_inputs": ["registry"],
            "bounds": {"send_hold": True},
            "allowed_tools_class": "read_only",
            "pii_rules": "redact",
            "repro_prompts": ["what is broken?"],
            "acceptance_tests": ["green gate"],
            "rollback_no_send": "no external send",
        },
        acceptance_ref=make_acceptance_ref(acceptance_file, tmp_path / "green_gate.sh"),
        max_attempts=max_attempts,
    )


def test_empty_queue_is_quiescent_without_model_calls_dispatches_or_writes(tmp_path):
    ledger = ControlPlaneLedger(tmp_path / "phase-c.sqlite3")
    before = ledger.counts()
    dispatches: list[str] = []

    result = run_control_plane_once(
        ledger,
        owner="orchestrator",
        dispatch=lambda lease: dispatches.append(lease.task_id),
    )

    assert result.dispatched is False
    assert result.model_calls == 0
    assert dispatches == []
    assert ledger.counts() == before


def test_crash_restart_recovers_and_rejects_duplicate_claims_and_invalid_transitions(tmp_path):
    db_path = tmp_path / "phase-c.sqlite3"
    ledger = ControlPlaneLedger(db_path)
    task_id = _ready_task(ledger, tmp_path)

    lease = ledger.claim_task(task_id, owner="builder-a", lease_seconds=60)
    assert lease is not None
    assert ledger.claim_task(task_id, owner="builder-b", lease_seconds=60) is None

    restarted = ControlPlaneLedger(db_path)
    recovered = restarted.get_task(task_id)
    assert recovered["status"] == "LEASED"
    assert recovered["attempts"] == 1
    assert restarted.attempt_count(task_id) == 1

    with pytest.raises(InvalidTransition):
        restarted.transition(task_id, "READY", "DONE", actor="test")


def test_builder_source_can_only_create_ttl_proposed_non_dispatchable_tasks(tmp_path):
    ledger = ControlPlaneLedger(tmp_path / "phase-c.sqlite3")
    task_id = ledger.admit_task(
        task_id="builder-suggestion",
        source="builder",
        task_type="heal_task",
        requested_status="READY",
        payload={"source_surface": "chief", "expected_behavior": "fix later"},
        ttl_seconds=30,
    )

    row = ledger.get_task(task_id)
    assert row["status"] == "PROPOSED"
    assert row["dispatchable"] == 0
    assert row["proposed_expires_at"] is not None
    assert ledger.claim_task(task_id, owner="builder", lease_seconds=60) is None

    with pytest.raises(SourceNotAllowed):
        ledger.promote_to_ready(task_id, actor="builder", source="builder")

    with pytest.raises(TaskRejected):
        ledger.admit_task(
            task_id="detector-send",
            source="detector",
            task_type="heal_task",
            requested_status="READY",
            payload={"expected_behavior": "send payment reminder"},
        )


def test_budget_exhaustion_blocks_respawn_and_leaves_loop_quiescent(tmp_path):
    ledger = ControlPlaneLedger(tmp_path / "phase-c.sqlite3")
    task_id = _ready_task(ledger, tmp_path, max_attempts=1)
    lease = ledger.claim_task(task_id, owner="builder-a", lease_seconds=60)
    assert lease is not None

    ledger.record_failure(
        task_id,
        owner=lease.owner,
        lease_nonce=lease.lease_nonce,
        failure_fingerprint="same-stacktrace",
        budget_spent=1.0,
    )

    row = ledger.get_task(task_id)
    assert row["status"] == "BLOCKED"
    assert row["terminal_reason"] == "max_attempts_exhausted"
    assert ledger.claim_task(task_id, owner="builder-b", lease_seconds=60) is None

    before = ledger.counts()
    result = run_control_plane_once(ledger, owner="orchestrator", dispatch=lambda lease: None)
    assert result.dispatched is False
    assert result.model_calls == 0
    assert ledger.counts() == before


def test_builder_workspace_acceptance_edit_cannot_cause_done(tmp_path):
    trusted_repo = tmp_path / "trusted"
    builder_workspace = tmp_path / "builder"
    trusted_repo.mkdir()
    builder_workspace.mkdir()
    trusted_acceptance = trusted_repo / "acceptance.txt"
    builder_acceptance = builder_workspace / "acceptance.txt"
    trusted_acceptance.write_text("real failing acceptance\n", encoding="utf-8")
    builder_acceptance.write_text("builder edited to pass\n", encoding="utf-8")
    trusted_gate = trusted_repo / "green_gate.sh"
    trusted_gate.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")

    ledger = ControlPlaneLedger(tmp_path / "phase-c.sqlite3")
    task_id = ledger.admit_task(
        task_id="immutable-acceptance",
        source="human_intent",
        task_type="heal_task",
        requested_status="READY",
        payload={"source_surface": "chief", "acceptance_tests": ["trusted green gate"]},
        acceptance_ref=make_acceptance_ref(trusted_acceptance, trusted_gate),
    )
    lease = ledger.claim_task(task_id, owner="builder-a", lease_seconds=60)
    assert lease is not None
    candidate = _write_candidate(builder_workspace / "pc_output.md")
    ledger.submit_candidate_evidence(
        task_id,
        owner=lease.owner,
        lease_nonce=lease.lease_nonce,
        evidence={
            "pc_output_path": str(candidate),
            "builder_acceptance_path": str(builder_acceptance),
            "model_claim": "STATUS: DONE",
        },
    )

    calls: list[Path] = []

    def gate_runner(*, green_gate_path: Path, repo_ref: str, cwd: Path) -> AcceptanceDecision:
        calls.append(cwd)
        assert green_gate_path == trusted_gate
        assert cwd == trusted_repo
        return AcceptanceDecision(exit_code=1, stdout="", stderr="trusted gate failed")

    decision = ledger.decide_acceptance(
        task_id,
        gate_runner=gate_runner,
        trusted_repo=trusted_repo,
    )

    assert decision.exit_code == 1
    assert calls == [trusted_repo]
    assert ledger.get_task(task_id)["status"] == "BLOCKED"
    assert ledger.get_task(task_id)["status"] != "DONE"


def test_alive_only_packets_are_rejected(tmp_path):
    ledger = ControlPlaneLedger(tmp_path / "phase-c.sqlite3")

    with pytest.raises(TaskRejected):
        ledger.admit_task(
            task_id="heartbeat",
            source="human_intent",
            task_type="heartbeat",
            requested_status="READY",
            payload={"message": "alive."},
        )

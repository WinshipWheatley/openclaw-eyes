from __future__ import annotations

import json
import os
import subprocess
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


def test_ledger_mutations_render_legacy_status_json_view(tmp_path):
    status_view = tmp_path / "status.json"
    ledger = ControlPlaneLedger(
        tmp_path / "phase-c.sqlite3",
        status_view_path=status_view,
    )
    task_id = _ready_task(ledger, tmp_path, max_attempts=1)

    ready_view = json.loads(status_view.read_text(encoding="utf-8"))
    assert ready_view["status"] == "idle"
    assert ready_view["phase_c_status"] == "READY"
    assert ready_view["phase_c_task_id"] == task_id

    lease = ledger.claim_task(task_id, owner="builder-a", lease_seconds=60)
    assert lease is not None
    leased_view = json.loads(status_view.read_text(encoding="utf-8"))
    assert leased_view["status"] == "pc_turn"
    assert leased_view["phase_c_status"] == "LEASED"
    assert leased_view["phase_c_owner"] == "builder-a"

    ledger.record_failure(
        task_id,
        owner=lease.owner,
        lease_nonce=lease.lease_nonce,
        failure_fingerprint="boom",
    )
    blocked_view = json.loads(status_view.read_text(encoding="utf-8"))
    assert blocked_view["status"] == "blocked"
    assert blocked_view["phase_c_status"] == "BLOCKED"
    assert blocked_view["block_reason"] == "max_attempts_exhausted"


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

    def gate_runner(
        *,
        green_gate_path: Path,
        repo_ref: str,
        cwd: Path,
        **_: object,
    ) -> AcceptanceDecision:
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


def test_blocked_pc_output_is_terminal_valid_artifact(tmp_path, monkeypatch):
    from polish_loop import orchestrator

    pc_output = tmp_path / "pc_output.md"
    pc_output.write_text(
        "\n".join(
            [
                "PASS: 1",
                "STATUS: BLOCKED",
                "CHANGES:",
                "- none",
                "REASONING:",
                "- cannot proceed",
                "ROLLBACK PLAN:",
                "- no changes",
                "COST:",
                "- local",
                "TRUTH:",
                "- blocked is explicit",
                "HEADROOM:",
                "- none",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(orchestrator, "PC_OUTPUT", pc_output)

    valid, reason = orchestrator.pc_output_valid(1)

    assert valid is True
    assert reason == "blocked"


def test_builder_running_uses_pid_file_not_process_name_grep(tmp_path, monkeypatch):
    from polish_loop import orchestrator

    pid_file = tmp_path / "builder.pid"
    pid_file.write_text(str(os.getpid()), encoding="utf-8")
    monkeypatch.setattr(orchestrator, "BUILDER_PID_FILE", pid_file)
    monkeypatch.setattr(orchestrator, "_TEST_BUILDER_OVERRIDE", None)

    def forbidden_pgrep(*args, **kwargs):  # pragma: no cover - only called on regression
        raise AssertionError("builder_running must not use broad pgrep")

    monkeypatch.setattr(orchestrator.subprocess, "run", forbidden_pgrep)
    assert orchestrator.builder_running() is True

    pid_file.write_text("999999999", encoding="utf-8")
    assert orchestrator.builder_running() is False


def test_local_builder_read_dedup_uses_canonical_path_not_basename(tmp_path):
    from polish_loop import local_builder

    first = tmp_path / "a" / "config.json"
    second = tmp_path / "b" / "config.json"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text('{"name":"a"}', encoding="utf-8")
    second.write_text('{"name":"b"}', encoding="utf-8")

    local_builder._confirmed_files.clear()
    assert '"name":"a"' in local_builder._exec_read_file({"path": str(first)})
    assert '"name":"b"' in local_builder._exec_read_file({"path": str(second)})
    assert local_builder._exec_read_file({"path": str(first)}).startswith("BLOCKED:")


def test_failed_to_start_is_explicit_ledger_event(tmp_path):
    ledger = ControlPlaneLedger(tmp_path / "phase-c.sqlite3")
    task_id = _ready_task(ledger, tmp_path)
    lease = ledger.claim_task(task_id, owner="runner", lease_seconds=60)
    assert lease is not None

    ledger.record_failed_to_start(
        task_id,
        actor="runner",
        detail={"reason": "missing executable"},
    )

    row = ledger.get_task(task_id)
    assert row["status"] == "BLOCKED"
    assert row["terminal_reason"] == "failed_to_start"
    with ledger.connect() as conn:
        events = [
            event["event_type"]
            for event in conn.execute(
                "SELECT event_type FROM events WHERE task_id=? ORDER BY id",
                (task_id,),
            )
        ]
    assert "FAILED_TO_START" in events


def test_green_gate_restores_trusted_acceptance_tests_from_ref(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "OpenClaw Test"], cwd=repo, check=True)

    required = [
        "generated/read_models/helm_composer_contract.json",
        "generated/read_models/mac_controller_real_use_smoke_status.json",
        "generated/read_models/mac_dynamic_card_renderer_status.json",
        "generated/read_models/cassandra_human_edge_lab.json",
        "generated/read_models/proof_to_response_runtime_status.json",
        "generated/read_models/proof_to_response_schema_adapter_status.json",
    ]
    for rel in required:
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")

    test_file = repo / "tests" / "test_acceptance.py"
    test_file.parent.mkdir()
    test_file.write_text("def test_trusted_acceptance():\n    assert False\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "trusted acceptance"], cwd=repo, check=True)
    subprocess.run(["git", "branch", "trusted"], cwd=repo, check=True)

    test_file.write_text("def test_trusted_acceptance():\n    assert True\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "candidate weakens acceptance"], cwd=repo, check=True)

    env = os.environ.copy()
    env.update(
        {
            "OPENCLAW_REPO": str(repo),
            "OPENCLAW_VENV": "/home/openclaw/.venv/bin/python",
            "OPENCLAW_GREEN_GATE_WORKTREE_ROOT": str(tmp_path / "worktrees"),
            "OPENCLAW_TRUSTED_ACCEPTANCE_REF": "trusted",
            "OPENCLAW_TRUSTED_ACCEPTANCE_PATHS": "tests",
        }
    )
    script = Path(__file__).resolve().parents[1] / "scripts" / "green_gate.sh"
    completed = subprocess.run(
        [str(script), "HEAD"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    combined = completed.stdout + completed.stderr

    assert completed.returncode != 0
    assert "restoring trusted acceptance paths from trusted: tests" in combined
    assert "NOT green" in combined

"""End-to-end integration test: ONE worker flowing through ControlPlaneLedger.

Tests an ISOLATED temp ledger — never touches /home/openclaw/polish_loop/control_plane.sqlite3.

Flow:
  1. admit_task() -> READY (human_intent source, immediately dispatchable)
  2. claim_next_ready() -> TaskLease (LEASED)
  3. worker_runtime materializes task markdown from the lease (via _task_markdown directly)
  4. Worker stub produces pc_output.md (success path) or failure path
  5. submit_candidate_evidence() -> VERIFYING
  6. decide_acceptance() -> DONE (pass) or BLOCKED (fail)
  7. Assert all ledger state transitions and that the ledger is genuinely populated

The seam: in-process simulation of the local_builder invocation.  The real
run_local_builder_worker() calls subprocess; here we inject a fake 'runner'
callable to avoid spawning any process.  The _task_markdown() helper is called
directly from worker_runtime to prove materialization works.

This test is fully deterministic and hermetic.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
POLISH_LOOP = ROOT / "polish_loop"
if str(POLISH_LOOP) not in sys.path:
    sys.path.insert(0, str(POLISH_LOOP))

from polish_loop.control_plane import (
    AcceptanceDecision,
    ControlPlaneLedger,
    TaskLease,
    iso_now,
    make_acceptance_ref,
)
from polish_loop.worker_runtime import (
    WorkerRuntimeConfig,
    WorkerRuntimeResult,
    _task_markdown,
    run_local_builder_worker,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_PAYLOAD: dict[str, Any] = {
    "source_surface": "maestro",
    "bad_exchange": {"request": "how many agents online?", "answer": "5 agents online"},
    "expected_behavior": 6,
    "truth_inputs": ["/tmp/fake_read_model.json"],
    "bounds": {"OPENCLAW_TEST_MODE": "1", "OPENCLAW_SEND_HOLD": "1"},
    "allowed_tools_class": "read_only_readmodels",
    "pii_rules": "no vault, no LegalPrivate, no FinancePrivate, no .chief.env",
    "repro_prompts": ["how many agents are online?"],
    "acceptance_tests": ["tests/test_pc4_self_healing.py"],
    "rollback_no_send": True,
}


def _valid_pc_output_text() -> str:
    return "\n".join([
        "RUNNER: harness",
        "PASS: 1",
        "STATUS: DONE",
        "",
        "CHANGES:",
        "- Fixed the agent count reporting logic.",
        "",
        "REASONING:",
        "- Updated read-model parsing to return correct count.",
        "",
        "ROLLBACK PLAN:",
        "- Revert the patch if replay regresses.",
        "",
        "COST:",
        "- Local dry-run only, no provider credits consumed.",
        "",
        "TRUTH:",
        "- Read-model truth inputs validated.",
        "",
        "HEADROOM:",
        "- No provider headroom consumed.",
        "",
    ])


def _blocked_pc_output_text() -> str:
    return "\n".join([
        "RUNNER: harness",
        "PASS: 1",
        "STATUS: BLOCKED",
        "",
        "CHANGES:",
        "- No changes produced.",
        "",
    ])


def _make_fake_runner(*, exit_code: int, produce_output: bool, output_text: str | None = None):
    """Return a subprocess.run stub that writes pc_output.md at the config path."""

    def fake_runner(command, *, env, cwd, capture_output, text, timeout, check, **kwargs):
        pc_output_path = Path(env["PHASE_C_PC_OUTPUT"])
        if produce_output:
            pc_output_path.parent.mkdir(parents=True, exist_ok=True)
            pc_output_path.write_text(output_text or _valid_pc_output_text(), encoding="utf-8")
        result = subprocess.CompletedProcess(
            args=command,
            returncode=exit_code,
            stdout="",
            stderr="",
        )
        return result

    return fake_runner


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAdmitAndClaimFlow:
    """State machine transitions: READY -> LEASED."""

    def test_admit_task_inserts_ready_and_dispatchable(self, tmp_path):
        """admit_task(source=human_intent) must produce a READY+dispatchable row."""
        ledger = ControlPlaneLedger(tmp_path / "ledger.sqlite3", status_view_path=tmp_path / "status.json")

        task_id = ledger.admit_task(
            source="human_intent",
            task_type="agent_heal",
            requested_status="READY",
            payload=SAMPLE_PAYLOAD,
        )

        task = ledger.get_task(task_id)
        assert task["status"] == "READY"
        assert task["dispatchable"] == 1
        assert task["source"] == "human_intent"
        assert task["type"] == "agent_heal"
        assert ledger.counts()["tasks"] == 1

    def test_claim_next_ready_transitions_to_leased(self, tmp_path):
        """claim_next_ready() must return a valid lease and mark the task LEASED."""
        ledger = ControlPlaneLedger(tmp_path / "ledger.sqlite3", status_view_path=tmp_path / "status.json")
        task_id = ledger.admit_task(
            source="human_intent",
            task_type="agent_heal",
            requested_status="READY",
            payload=SAMPLE_PAYLOAD,
        )

        lease = ledger.claim_next_ready(owner="integration-test-worker")
        assert lease is not None
        assert lease.task_id == task_id
        assert lease.owner == "integration-test-worker"
        assert lease.attempt_no == 1
        assert lease.lease_nonce  # non-empty

        task = ledger.get_task(task_id)
        assert task["status"] == "LEASED"
        assert task["owner"] == "integration-test-worker"
        assert task["dispatchable"] == 0
        assert task["attempts"] == 1

    def test_claim_next_ready_returns_none_when_empty(self, tmp_path):
        """An empty ledger should return None without error."""
        ledger = ControlPlaneLedger(tmp_path / "ledger.sqlite3", status_view_path=tmp_path / "status.json")
        lease = ledger.claim_next_ready(owner="integration-test-worker")
        assert lease is None

    def test_task_markdown_materialization(self, tmp_path):
        """_task_markdown() must include task_id, task_type, source, payload JSON, and lease_owner."""
        ledger = ControlPlaneLedger(tmp_path / "ledger.sqlite3", status_view_path=tmp_path / "status.json")
        task_id = ledger.admit_task(
            source="human_intent",
            task_type="agent_heal",
            requested_status="READY",
            payload=SAMPLE_PAYLOAD,
        )
        lease = ledger.claim_next_ready(owner="integration-test-worker")
        assert lease is not None

        row = ledger.get_task(task_id)
        md = _task_markdown(row, lease)

        assert f"task_id: {task_id}" in md
        assert "task_type: agent_heal" in md
        assert "source: human_intent" in md
        assert "lease_owner: integration-test-worker" in md
        assert "attempt: 1" in md
        assert "Payload JSON:" in md
        # Payload content is embedded as JSON
        assert "maestro" in md


class TestWorkerRuntimeIntegration:
    """Full worker cycle: claim -> materialize -> produce output -> submit evidence -> accept/block."""

    def test_success_path_ready_to_done(self, tmp_path):
        """
        The golden path: worker produces a valid pc_output.md -> DONE.

        Flow:
          admit_task (READY) -> claim_next_ready (LEASED)
          -> fake runner writes valid pc_output.md and exits 0
          -> submit_candidate_evidence (VERIFYING)
          -> decide_acceptance with stub gate_runner returning ok=True -> DONE
        """
        ledger = ControlPlaneLedger(tmp_path / "ledger.sqlite3", status_view_path=tmp_path / "status.json")
        acceptance_file = tmp_path / "acceptance.py"
        acceptance_file.write_text("def test_ok():\n    assert True\n", encoding="utf-8")

        task_id = ledger.admit_task(
            source="human_intent",
            task_type="agent_heal",
            requested_status="READY",
            payload=SAMPLE_PAYLOAD,
            acceptance_ref=make_acceptance_ref(
                acceptance_file,
                ROOT / "scripts" / "green_gate.sh",
            ),
        )
        assert ledger.get_task(task_id)["status"] == "READY"

        # Claim
        lease = ledger.claim_next_ready(owner="integration-test-worker")
        assert lease is not None
        assert ledger.get_task(task_id)["status"] == "LEASED"

        # Verify materialization works before the worker runs
        row = ledger.get_task(task_id)
        md = _task_markdown(row, lease)
        assert lease.task_id in md

        # Configure worker runtime pointing at temp dirs
        pc_output_path = tmp_path / "current" / "pc_output.md"
        config = WorkerRuntimeConfig(
            python=sys.executable,
            local_builder_path=tmp_path / "fake_local_builder.py",
            loop_dir=tmp_path,
            task_path=tmp_path / "task.md",
            pc_output_path=pc_output_path,
            artifact_dir=tmp_path / "current",
            model="test-model",
            timeout_seconds=30,
            subprocess_timeout_seconds=60,
        )

        fake_runner = _make_fake_runner(exit_code=0, produce_output=True)
        result = run_local_builder_worker(ledger, lease, config=config, runner=fake_runner)

        # Worker submitted candidate evidence
        assert result.submitted_candidate is True
        assert result.failure_recorded is False
        assert result.exit_code == 0

        # Task is now VERIFYING
        assert ledger.get_task(task_id)["status"] == "VERIFYING"

        # decide_acceptance with a stub that returns green
        decision = ledger.decide_acceptance(
            task_id,
            gate_runner=lambda **_: AcceptanceDecision(0, "green", ""),
            trusted_repo=ROOT,
        )

        assert decision.ok is True
        assert decision.exit_code == 0
        assert ledger.get_task(task_id)["status"] == "DONE"
        assert ledger.counts()["attempts"] == 1

    def test_failure_path_ready_to_blocked_via_record_failure(self, tmp_path):
        """
        Worker exits non-zero (no pc_output.md) -> record_failure -> status depends on max_attempts.

        With max_attempts=1 + repeated failure -> BLOCKED after one attempt.
        """
        ledger = ControlPlaneLedger(tmp_path / "ledger.sqlite3", status_view_path=tmp_path / "status.json")

        task_id = ledger.admit_task(
            source="human_intent",
            task_type="agent_heal",
            requested_status="READY",
            payload=SAMPLE_PAYLOAD,
            max_attempts=1,
        )
        lease = ledger.claim_next_ready(owner="integration-test-worker")
        assert lease is not None

        pc_output_path = tmp_path / "current" / "pc_output.md"
        config = WorkerRuntimeConfig(
            python=sys.executable,
            local_builder_path=tmp_path / "fake_local_builder.py",
            loop_dir=tmp_path,
            task_path=tmp_path / "task.md",
            pc_output_path=pc_output_path,
            artifact_dir=tmp_path / "current",
            model="test-model",
            timeout_seconds=30,
            subprocess_timeout_seconds=60,
        )

        # Runner exits non-zero, doesn't write output
        fake_runner = _make_fake_runner(exit_code=1, produce_output=False)
        result = run_local_builder_worker(ledger, lease, config=config, runner=fake_runner)

        assert result.submitted_candidate is False
        assert result.failure_recorded is True
        assert result.exit_code == 1

        # max_attempts=1: exhausted -> BLOCKED
        task = ledger.get_task(task_id)
        assert task["status"] == "BLOCKED"
        assert task["terminal_reason"] == "max_attempts_exhausted"

    def test_blocked_pc_output_produces_blocked_after_acceptance(self, tmp_path):
        """
        Worker produces pc_output.md with STATUS: BLOCKED.
        validate_candidate_evidence returns invalid -> decide_acceptance -> BLOCKED.
        """
        ledger = ControlPlaneLedger(tmp_path / "ledger.sqlite3", status_view_path=tmp_path / "status.json")
        acceptance_file = tmp_path / "acceptance.py"
        acceptance_file.write_text("def test_ok():\n    assert True\n", encoding="utf-8")

        task_id = ledger.admit_task(
            source="human_intent",
            task_type="agent_heal",
            requested_status="READY",
            payload=SAMPLE_PAYLOAD,
            acceptance_ref=make_acceptance_ref(
                acceptance_file,
                ROOT / "scripts" / "green_gate.sh",
            ),
        )
        lease = ledger.claim_next_ready(owner="integration-test-worker")
        assert lease is not None

        pc_output_path = tmp_path / "current" / "pc_output.md"
        config = WorkerRuntimeConfig(
            python=sys.executable,
            local_builder_path=tmp_path / "fake_local_builder.py",
            loop_dir=tmp_path,
            task_path=tmp_path / "task.md",
            pc_output_path=pc_output_path,
            artifact_dir=tmp_path / "current",
            model="test-model",
            timeout_seconds=30,
            subprocess_timeout_seconds=60,
        )

        # Runner exits 0 but writes STATUS: BLOCKED output
        fake_runner = _make_fake_runner(exit_code=0, produce_output=True, output_text=_blocked_pc_output_text())
        result = run_local_builder_worker(ledger, lease, config=config, runner=fake_runner)

        # Worker sees exit_code=0 and pc_output exists, so it submits candidate evidence
        assert result.submitted_candidate is True
        assert ledger.get_task(task_id)["status"] == "VERIFYING"

        # But decide_acceptance sees STATUS: BLOCKED in the output -> BLOCKED
        decision = ledger.decide_acceptance(
            task_id,
            gate_runner=lambda **_: AcceptanceDecision(0, "green", ""),
            trusted_repo=ROOT,
        )

        assert decision.ok is False
        assert ledger.get_task(task_id)["status"] == "BLOCKED"


class TestWorkerRuntimeRetryAndExpiry:
    """Lease retry, expiry recovery, and multi-attempt flow."""

    def test_expired_lease_recovered_and_re_claimable(self, tmp_path):
        """
        A LEASED task whose lease_expiry has passed is recovered back to READY
        by recover_expired_leases(), and can then be claimed by a second worker.
        """
        import datetime as _dt

        ledger = ControlPlaneLedger(tmp_path / "ledger.sqlite3", status_view_path=tmp_path / "status.json")
        task_id = ledger.admit_task(
            source="human_intent",
            task_type="agent_heal",
            requested_status="READY",
            payload=SAMPLE_PAYLOAD,
        )

        # Claim with 1-second lease
        lease = ledger.claim_task(task_id, owner="slow-worker", lease_seconds=1)
        assert lease is not None
        assert ledger.get_task(task_id)["status"] == "LEASED"

        # Manually back-date lease_expiry to the past so expiry check fires
        import sqlite3
        conn = ledger.connect()
        past = (_dt.datetime.now(_dt.UTC) - _dt.timedelta(seconds=60)).isoformat()
        conn.execute(
            "UPDATE tasks SET lease_expiry=? WHERE id=?",
            (past, task_id),
        )
        conn.commit()
        conn.close()

        # Now recover_expired_leases() should put it back to READY
        recovered = ledger.recover_expired_leases()
        assert recovered == 1
        task = ledger.get_task(task_id)
        assert task["status"] == "READY"
        assert task["owner"] is None

        # A second worker can claim it
        lease2 = ledger.claim_next_ready(owner="recovery-worker")
        assert lease2 is not None
        assert lease2.owner == "recovery-worker"
        assert lease2.attempt_no == 2  # second attempt
        assert ledger.get_task(task_id)["status"] == "LEASED"

    def test_full_multi_attempt_success_after_one_failure(self, tmp_path):
        """
        Attempt 1: worker fails -> task re-queued READY.
        Attempt 2: worker succeeds -> VERIFYING -> DONE.
        max_attempts=2 allows this.
        """
        ledger = ControlPlaneLedger(tmp_path / "ledger.sqlite3", status_view_path=tmp_path / "status.json")
        acceptance_file = tmp_path / "acceptance.py"
        acceptance_file.write_text("def test_ok():\n    assert True\n", encoding="utf-8")

        task_id = ledger.admit_task(
            source="human_intent",
            task_type="agent_heal",
            requested_status="READY",
            payload=SAMPLE_PAYLOAD,
            max_attempts=2,
            acceptance_ref=make_acceptance_ref(
                acceptance_file,
                ROOT / "scripts" / "green_gate.sh",
            ),
        )

        def _config(tmp_path):
            return WorkerRuntimeConfig(
                python=sys.executable,
                local_builder_path=tmp_path / "fake_local_builder.py",
                loop_dir=tmp_path,
                task_path=tmp_path / "task.md",
                pc_output_path=tmp_path / "current" / "pc_output.md",
                artifact_dir=tmp_path / "current",
                model="test-model",
                timeout_seconds=30,
                subprocess_timeout_seconds=60,
            )

        # --- Attempt 1: fail ---
        lease1 = ledger.claim_next_ready(owner="worker-attempt-1")
        assert lease1 is not None
        assert lease1.attempt_no == 1

        result1 = run_local_builder_worker(
            ledger, lease1, config=_config(tmp_path),
            runner=_make_fake_runner(exit_code=1, produce_output=False),
        )
        assert result1.failure_recorded is True

        # With max_attempts=2 and attempt=1, task is re-queued READY
        task_after_fail = ledger.get_task(task_id)
        assert task_after_fail["status"] == "READY"
        assert task_after_fail["attempts"] == 1

        # --- Attempt 2: succeed ---
        lease2 = ledger.claim_next_ready(owner="worker-attempt-2")
        assert lease2 is not None
        assert lease2.attempt_no == 2

        result2 = run_local_builder_worker(
            ledger, lease2, config=_config(tmp_path),
            runner=_make_fake_runner(exit_code=0, produce_output=True),
        )
        assert result2.submitted_candidate is True
        assert ledger.get_task(task_id)["status"] == "VERIFYING"

        decision = ledger.decide_acceptance(
            task_id,
            gate_runner=lambda **_: AcceptanceDecision(0, "green", ""),
            trusted_repo=ROOT,
        )
        assert decision.ok is True
        assert ledger.get_task(task_id)["status"] == "DONE"
        assert ledger.counts()["attempts"] == 2

    def test_ledger_is_genuinely_populated(self, tmp_path):
        """
        Verify the temp SQLite file is actually written with the expected tables and rows
        — proving this is not a mock and a real ledger would behave identically.
        """
        import sqlite3 as _sqlite3

        ledger = ControlPlaneLedger(tmp_path / "ledger.sqlite3", status_view_path=tmp_path / "status.json")
        task_id = ledger.admit_task(
            source="human_intent",
            task_type="agent_heal",
            requested_status="READY",
            payload=SAMPLE_PAYLOAD,
        )
        lease = ledger.claim_next_ready(owner="integration-test-worker")
        assert lease is not None

        # Connect raw to the SQLite file and verify rows
        conn = _sqlite3.connect(str(tmp_path / "ledger.sqlite3"))
        conn.row_factory = _sqlite3.Row

        task_row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        assert task_row is not None
        assert task_row["status"] == "LEASED"
        assert task_row["owner"] == "integration-test-worker"

        event_rows = conn.execute("SELECT * FROM events ORDER BY id").fetchall()
        event_types = [r["event_type"] for r in event_rows]
        assert "TASK_ADMITTED" in event_types
        assert "TASK_CLAIMED" in event_types

        attempt_rows = conn.execute("SELECT * FROM attempts WHERE task_id=?", (task_id,)).fetchall()
        assert len(attempt_rows) == 1
        assert attempt_rows[0]["owner"] == "integration-test-worker"

        conn.close()

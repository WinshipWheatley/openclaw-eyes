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
from polish_loop import control_plane
from polish_loop.control_plane import (
    AcceptanceDecision,
    ControlPlaneLedger,
    SIZE_ROUTER_FLAG,
    make_acceptance_ref,
)
from polish_loop.task_routing import ROUTING_SCHEMA_VERSION
from polish_loop.worker_runtime import (
    TASK_PACKAGE_FLAG,
    WorkerRuntimeConfig,
    WorkerRuntimeResult,
    task_package_enabled,
)


def _rows(ledger: ControlPlaneLedger, sql: str, *params: object) -> list[dict]:
    with sqlite3.connect(ledger.path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _event_rows(ledger: ControlPlaneLedger) -> list[dict]:
    return _rows(
        ledger,
        """
        SELECT event_type, from_status, to_status, actor, detail
        FROM events
        ORDER BY id
        """,
    )


def _payload(tmp_path: Path) -> dict:
    return {
        "goal": "Prove one synthetic Polish Loop task reaches DONE unattended.",
        "scope": ["Exercise admit, claim, package, fake builder, fake acceptance, and DONE."],
        "success_criteria": [
            "routing receipt is stored",
            "task package contains the live lease",
            "fake builder is called exactly once",
            "fake acceptance marks DONE",
        ],
        "allowed_files": ["tests/test_polish_loop_e2e_unattended.py"],
        "forbidden_files": ["production ledgers", "production queues", "generated read-models"],
        "allowed_actions": ["write temp task package", "write temp candidate output"],
        "forbidden_actions": [
            "launch real builders",
            "call local or external LMs",
            "touch production systems",
        ],
        "tests_to_run": [
            "/home/openclaw/.venv/bin/python -m pytest tests/test_polish_loop_e2e_unattended.py -q"
        ],
        "stop_conditions": ["any production access would be required"],
        "output_contract": ["pc_output.md with PASS and STATUS DONE"],
        "help_or_escalation_route": ["mark task blocked and report to Opus"],
        "rollback_expectation": ["unset the three OPENCLAW_POLISH_LOOP_* test flags"],
        "production_prohibitions": ["no live loop", "no builders", "no LMs", "no systemd"],
        "repo_root": str(tmp_path / "repo"),
        "worktree": str(tmp_path / "repo"),
        "branch": "agy-codex/polish-e2e-unattended",
    }


def _config(tmp_path: Path) -> WorkerRuntimeConfig:
    loop_dir = tmp_path / "loop"
    return WorkerRuntimeConfig(
        local_builder_path=tmp_path / "never-run-local-builder.py",
        loop_dir=loop_dir,
        task_path=loop_dir / "task.md",
        pc_output_path=loop_dir / "current" / "pc_output.md",
        artifact_dir=loop_dir / "current",
        repo_root=tmp_path / "repo",
        worktree=tmp_path / "repo",
        branch="agy-codex/polish-e2e-unattended",
        subprocess_timeout_seconds=1,
    )


def test_synthetic_task_runs_admit_claim_package_fake_builder_acceptance_done_unattended(
    tmp_path,
    monkeypatch,
):
    flags = [
        SIZE_ROUTER_FLAG,
        TASK_PACKAGE_FLAG,
        orchestrator.FILE_LEDGER_BRIDGE_FLAG,
        orchestrator.LOCAL_BUILDER_FLAG,
    ]
    for name in flags:
        monkeypatch.delenv(name, raising=False)

    assert control_plane.size_router_v1_enabled() is False
    assert task_package_enabled() is False
    assert orchestrator._file_ledger_bridge_enabled() is False
    assert orchestrator._local_builder_enabled(None) is False

    monkeypatch.setenv(SIZE_ROUTER_FLAG, "1")
    monkeypatch.setenv(TASK_PACKAGE_FLAG, "1")
    monkeypatch.setenv(orchestrator.FILE_LEDGER_BRIDGE_FLAG, "1")
    monkeypatch.setenv(orchestrator.LOCAL_BUILDER_FLAG, "1")

    def forbidden_subprocess_run(*_args, **_kwargs):
        raise AssertionError("synthetic E2E must not launch subprocesses, builders, or models")

    monkeypatch.setattr(subprocess, "run", forbidden_subprocess_run)
    monkeypatch.setattr(orchestrator.subprocess, "run", forbidden_subprocess_run)
    monkeypatch.setattr(control_plane, "_post_acceptance_notify", lambda *_args, **_kwargs: None)

    ledger = ControlPlaneLedger(tmp_path / "control.sqlite3")
    acceptance_path = tmp_path / "synthetic_acceptance_ref.py"
    acceptance_path.write_text("def test_synthetic_acceptance_ref():\n    assert True\n", encoding="utf-8")
    green_gate = tmp_path / "green_gate.sh"
    green_gate.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    acceptance_ref = make_acceptance_ref(
        acceptance_path,
        green_gate,
        repo_ref="synthetic",
        trusted_acceptance_ref="synthetic-ref",
        trusted_acceptance_paths=("tests",),
    )

    task_id = ledger.admit_task(
        task_id="synthetic-e2e-unattended",
        source="human_intent",
        task_type="synthetic_polish_loop",
        requested_status="READY",
        payload=_payload(tmp_path),
        acceptance_ref=acceptance_ref,
        max_attempts=2,
    )

    admitted = ledger.get_task(task_id)
    routing = admitted["payload"]["routing"]
    assert admitted["status"] == "READY"
    assert admitted["dispatchable"] == 1
    assert routing["schema_version"] == ROUTING_SCHEMA_VERSION
    assert routing["readiness"] == "ready"
    assert routing["local_model_allowed"] is True

    config = _config(tmp_path)
    builder_calls: list[str] = []

    def fake_builder(ledger_arg, lease, *, config):
        builder_calls.append(lease.task_id)
        assert ledger_arg.path == ledger.path
        directive_paths = sorted((config.loop_dir / "to-pc").glob("FIX-*.md"))
        assert len(directive_paths) == 1
        directive_path = directive_paths[0]
        materialized = directive_path.read_text(encoding="utf-8")
        assert "schema_version: polish_loop_task_package_v1" in materialized
        assert f"task_id: {lease.task_id}" in materialized
        assert f"lease_owner: {lease.owner}" in materialized
        assert f"lease_nonce: {lease.lease_nonce}" in materialized
        assert f"attempt_no: {lease.attempt_no}" in materialized
        assert "launch real builders" in materialized

        config.pc_output_path.parent.mkdir(parents=True, exist_ok=True)
        config.pc_output_path.write_text(
            "\n".join(
                [
                    "PASS: 1",
                    "STATUS: DONE",
                    "",
                    "CHANGES:",
                    "- Synthetic E2E fake builder produced candidate output.",
                    "",
                    "TRUTH:",
                    "- No real builder, LM, production queue, or production ledger was touched.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        artifact_path = config.artifact_dir / f"{lease.task_id}.json"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(json.dumps({"synthetic": True}) + "\n", encoding="utf-8")
        return WorkerRuntimeResult(
            task_id=lease.task_id,
            exit_code=0,
            submitted_candidate=True,
            failure_recorded=False,
            artifact_path=artifact_path,
            pc_output_path=config.pc_output_path,
            task_md_path=directive_path,
        )

    dispatch = orchestrator.run_phase_c_once(
        ledger_path=ledger.path,
        owner="synthetic-e2e-worker",
        worker_config=config,
        builder_runner=fake_builder,
        enable_local_builder=True,
    )

    assert dispatch.dispatched is True
    assert dispatch.task_id == task_id
    assert builder_calls == [task_id]

    verifying = ledger.get_task(task_id)
    assert verifying["status"] == "VERIFYING"
    assert verifying["owner"] == "synthetic-e2e-worker"
    assert verifying["candidate_evidence"]["worker_runtime"] == "phase_c_closure_bridge"
    assert verifying["candidate_evidence"]["task_md_path"].endswith(
        "FIX-synthetic-e2e-unattended-attempt-1.md"
    )

    acceptance_calls: list[dict] = []

    def fake_gate_runner(**kwargs):
        acceptance_calls.append(kwargs)
        return AcceptanceDecision(0, "synthetic green gate ok", "")

    decision = ledger.decide_acceptance(
        task_id,
        gate_runner=fake_gate_runner,
        trusted_repo=tmp_path,
    )

    assert decision.ok is True
    assert len(acceptance_calls) == 1
    final = ledger.get_task(task_id)
    assert final["status"] == "DONE"
    assert final["owner"] is None
    assert final["lease_nonce"] is None
    assert final["dispatchable"] == 0
    assert ledger.claim_next_ready(owner="synthetic-e2e-worker") is None

    attempts = _rows(
        ledger,
        "SELECT attempt_no, owner, status, lease_nonce, evidence FROM attempts ORDER BY attempt_no",
    )
    assert len(attempts) == 1
    assert attempts[0]["attempt_no"] == 1
    assert attempts[0]["owner"] == "synthetic-e2e-worker"
    assert attempts[0]["status"] == "DONE"
    assert attempts[0]["lease_nonce"] == verifying["candidate_evidence"]["lease_nonce"]

    event_types = [row["event_type"] for row in _event_rows(ledger)]
    assert event_types == [
        "TASK_ADMITTED",
        "TASK_CLAIMED",
        "CANDIDATE_SUBMITTED",
        "TASK_ACCEPTED",
    ]
    admitted_detail = json.loads(_event_rows(ledger)[0]["detail"])
    assert admitted_detail["routing"]["schema_version"] == ROUTING_SCHEMA_VERSION
    assert admitted_detail["routing"]["readiness"] == "ready"

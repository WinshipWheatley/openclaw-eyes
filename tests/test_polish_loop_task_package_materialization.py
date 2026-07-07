from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polish_loop import orchestrator
from polish_loop.control_plane import ControlPlaneLedger, TaskLease
from polish_loop.worker_runtime import (
    TASK_PACKAGE_FLAG,
    TASK_PACKAGE_SCHEMA_VERSION,
    TaskPackageError,
    WorkerRuntimeConfig,
    build_task_package_markdown,
    run_local_builder_worker,
)


def _ledger(tmp_path: Path) -> ControlPlaneLedger:
    return ControlPlaneLedger(tmp_path / "control.sqlite3")


def _full_payload(**overrides) -> dict:
    payload = {
        "goal": "materialize a deterministic task package",
        "scope": ["worker_runtime.py", "orchestrator.py"],
        "success_criteria": ["package includes live lease identity", "fake runner sees fresh task"],
        "allowed_files": ["polish_loop/worker_runtime.py", "polish_loop/orchestrator.py"],
        "forbidden_files": ["builder_watcher.sh", "production ledgers"],
        "allowed_actions": ["write temp task package", "record synthetic receipt"],
        "forbidden_actions": ["launch builders", "call LMs", "touch production"],
        "tests_to_run": ["tests/test_polish_loop_task_package_materialization.py"],
        "stop_conditions": ["missing required package field", "stale lease"],
        "output_contract": ["pc_output.md candidate evidence"],
        "help_or_escalation_route": ["mark task blocked and report to Opus"],
        "rollback_expectation": ["unset OPENCLAW_POLISH_LOOP_TASK_PACKAGE_V1"],
        "production_prohibitions": ["no Telegram", "no email", "no systemd"],
        "repo_root": "/repo/root",
        "worktree": "/repo/worktree",
        "branch": "agy-codex/polish-task-package",
    }
    payload.update(overrides)
    return payload


def _admit_ready(ledger: ControlPlaneLedger, *, payload: dict | None = None, task_id: str = "task-package-synthetic") -> str:
    return ledger.admit_task(
        task_id=task_id,
        source="human_intent",
        task_type="synthetic_polish_package",
        requested_status="READY",
        payload=payload or _full_payload(),
        acceptance_ref={"acceptance_path": "tests/test_polish_loop_task_package_materialization.py"},
        max_attempts=3,
    )


def _claim(ledger: ControlPlaneLedger, task_id: str = "task-package-synthetic") -> TaskLease:
    lease = ledger.claim_task(task_id, owner="package-test", lease_seconds=600)
    assert lease is not None
    return lease


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
        branch="agy-codex/polish-task-package",
        subprocess_timeout_seconds=1,
    )


def _digest_line(markdown: str) -> str:
    match = re.search(r"^payload_digest: (.+)$", markdown, re.MULTILINE)
    assert match is not None
    return match.group(1)


def _rows(ledger: ControlPlaneLedger, sql: str) -> list[dict]:
    with sqlite3.connect(ledger.path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql).fetchall()]


def test_full_synthetic_payload_materializes_every_required_field(tmp_path):
    ledger = _ledger(tmp_path)
    task_id = _admit_ready(ledger)
    lease = _claim(ledger, task_id)
    row = ledger.get_task(task_id)
    row["_ledger_db"] = str(ledger.path)

    markdown = build_task_package_markdown(
        row,
        lease,
        repo_root=tmp_path / "repo",
        worktree=tmp_path / "repo",
        branch="agy-codex/polish-task-package",
    )

    for field in [
        "schema_version",
        "task_id",
        "task_type",
        "source",
        "ledger_db",
        "lease_owner",
        "lease_nonce",
        "attempt_no",
        "repo_root",
        "worktree",
        "branch",
        "payload_digest",
    ]:
        assert f"{field}:" in markdown
    for heading in [
        "## Goal",
        "## Scope",
        "## Success Criteria",
        "## Allowed Files",
        "## Forbidden Files",
        "## Allowed Actions",
        "## Forbidden Actions",
        "## Tests To Run",
        "## Acceptance Ref",
        "## Stop Conditions",
        "## Output Contract",
        "## Help Or Escalation Route",
        "## Rollback Expectation",
        "## Production Prohibitions",
    ]:
        assert heading in markdown
    assert f"schema_version: {TASK_PACKAGE_SCHEMA_VERSION}" in markdown
    assert f"lease_nonce: {lease.lease_nonce}" in markdown
    assert "tests/test_polish_loop_task_package_materialization.py" in markdown


def test_task_package_round_trips_class_scope_fields(tmp_path):
    ledger = _ledger(tmp_path)
    payload = _full_payload(
        failure_class="ledger_source_drift",
        class_scope="class",
        sibling_evidence=[
            {
                "agent_id": "cassandra",
                "packet_id": "cassandra_context_packet:one",
                "evidence": "receipt:cassandra",
            },
            {
                "agent_id": "maestro",
                "packet_id": "maestro_context_packet:two",
                "evidence": "receipt:maestro",
            },
        ],
    )
    task_id = _admit_ready(ledger, payload=payload)
    lease = _claim(ledger, task_id)
    row = ledger.get_task(task_id)

    markdown = build_task_package_markdown(
        row,
        lease,
        repo_root=tmp_path / "repo",
        worktree=tmp_path / "repo",
        branch="agy-codex/polish-task-package",
    )

    assert "failure_class: ledger_source_drift" in markdown
    assert "class_scope: class" in markdown
    assert "## Sibling Evidence" in markdown
    assert "cassandra_context_packet:one" in markdown
    payload_json = markdown.split("```json", 1)[1].split("```", 1)[0]
    round_tripped = json.loads(payload_json)
    assert round_tripped["failure_class"] == "ledger_source_drift"
    assert round_tripped["class_scope"] == "class"
    assert round_tripped["sibling_evidence"][1]["agent_id"] == "maestro"


def test_intake_prefers_class_scoped_package_for_same_gap(tmp_path):
    ledger = _ledger(tmp_path)
    instance_payload = _full_payload(
        self_improvement_gap_id="ledger_source_drift:abc123",
        failure_class="ledger_source_drift",
        class_scope="instance",
        sibling_evidence=[],
    )
    class_payload = _full_payload(
        goal="fix the ledger source drift class across sibling packet builders",
        self_improvement_gap_id="ledger_source_drift:abc123",
        failure_class="ledger_source_drift",
        class_scope="class",
        sibling_evidence=[
            {"agent_id": "cassandra", "packet_id": "cassandra_context_packet:one"},
            {"agent_id": "maestro", "packet_id": "maestro_context_packet:two"},
        ],
    )

    first_id = ledger.admit_task(
        source="detector",
        task_type="self_improvement",
        requested_status="READY",
        payload=instance_payload,
        acceptance_ref={"acceptance_path": "tests/test_polish_loop_task_package_materialization.py"},
    )
    returned_id = ledger.admit_task(
        source="detector",
        task_type="self_improvement",
        requested_status="READY",
        payload=class_payload,
        acceptance_ref={"acceptance_path": "tests/test_polish_loop_task_package_materialization.py"},
    )

    assert returned_id == first_id
    assert ledger.counts()["tasks"] == 1
    task = ledger.get_task(first_id)
    assert task["payload"]["class_scope"] == "class"
    assert task["payload"]["failure_class"] == "ledger_source_drift"
    assert "sibling packet builders" in task["payload"]["goal"]


def test_missing_required_field_fails_closed_before_builder_invocation(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    payload = _full_payload()
    payload.pop("success_criteria")
    task_id = _admit_ready(ledger, payload=payload)
    config = _config(tmp_path)
    calls: list[str] = []
    monkeypatch.setenv(TASK_PACKAGE_FLAG, "1")

    def fake_builder(_ledger, lease, *, config):
        calls.append(lease.task_id)
        raise AssertionError("builder must not run when task package validation fails")

    result = orchestrator.run_phase_c_once(
        ledger_path=ledger.path,
        owner="package-test",
        worker_config=config,
        builder_runner=fake_builder,
        enable_local_builder=True,
    )

    task = ledger.get_task(task_id)
    assert result.dispatched is True
    assert calls == []
    assert task["status"] == "READY"
    assert task["failure_fingerprint"].startswith("task_package_v1_missing_")
    attempts = _rows(ledger, "SELECT evidence FROM attempts")
    assert "success_criteria" in attempts[0]["evidence"]


def test_fake_runner_writes_fresh_package_with_live_lease_identity(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    task_id = _admit_ready(ledger)
    lease = _claim(ledger, task_id)
    config = _config(tmp_path)
    config.task_path.parent.mkdir(parents=True, exist_ok=True)
    config.task_path.write_text("stale task.md from a previous lease\n", encoding="utf-8")
    monkeypatch.setenv(TASK_PACKAGE_FLAG, "1")
    calls: list[str] = []

    def fake_runner(command, *, cwd, env, capture_output, text, timeout, check):
        calls.append(env["PHASE_C_TASK_ID"])
        materialized = config.task_path.read_text(encoding="utf-8")
        assert "stale task.md" not in materialized
        assert f"task_id: {lease.task_id}" in materialized
        assert f"lease_owner: {lease.owner}" in materialized
        assert f"lease_nonce: {lease.lease_nonce}" in materialized
        assert f"attempt_no: {lease.attempt_no}" in materialized
        assert "branch: agy-codex/polish-task-package" in materialized
        assert "## Tests To Run" in materialized
        assert "## Forbidden Actions" in materialized
        assert "## Stop Conditions" in materialized
        assert "## Help Or Escalation Route" in materialized
        config.pc_output_path.parent.mkdir(parents=True, exist_ok=True)
        config.pc_output_path.write_text("PASS: 1\nSTATUS: DONE\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="synthetic ok", stderr="")

    result = run_local_builder_worker(ledger, lease, config=config, runner=fake_runner)

    assert calls == [task_id]
    assert result.submitted_candidate is True
    assert result.task_md_path == config.task_path
    task = ledger.get_task(task_id)
    assert task["status"] == "VERIFYING"
    assert task["candidate_evidence"]["task_md_path"] == str(config.task_path)


def test_digest_is_stable_for_identical_payloads_and_changes_on_delta(tmp_path):
    ledger = _ledger(tmp_path)
    task_id = _admit_ready(ledger)
    lease = _claim(ledger, task_id)
    row = ledger.get_task(task_id)

    first = build_task_package_markdown(row, lease, repo_root="/repo", worktree="/repo", branch="branch")
    second = build_task_package_markdown(row, lease, repo_root="/repo", worktree="/repo", branch="branch")
    changed = dict(row)
    changed["payload"] = dict(row["payload"])
    changed["payload"]["goal"] = "changed package goal"
    third = build_task_package_markdown(changed, lease, repo_root="/repo", worktree="/repo", branch="branch")

    assert _digest_line(first) == _digest_line(second)
    assert _digest_line(first) != _digest_line(third)


def test_flag_off_preserves_existing_worker_task_markdown(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    task_id = _admit_ready(ledger)
    lease = _claim(ledger, task_id)
    config = _config(tmp_path)
    monkeypatch.delenv(TASK_PACKAGE_FLAG, raising=False)

    def fake_runner(command, *, cwd, env, capture_output, text, timeout, check):
        materialized = config.task_path.read_text(encoding="utf-8")
        assert "# Phase-C Worker Runtime Task" in materialized
        assert f"schema_version: {TASK_PACKAGE_SCHEMA_VERSION}" not in materialized
        config.pc_output_path.parent.mkdir(parents=True, exist_ok=True)
        config.pc_output_path.write_text("PASS: 1\nSTATUS: DONE\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    run_local_builder_worker(ledger, lease, config=config, runner=fake_runner)


def test_direct_missing_required_field_raises_task_package_error(tmp_path):
    ledger = _ledger(tmp_path)
    payload = _full_payload(tests_to_run=[])
    task_id = _admit_ready(ledger, payload=payload)
    lease = _claim(ledger, task_id)

    with pytest.raises(TaskPackageError) as excinfo:
        build_task_package_markdown(
            ledger.get_task(task_id),
            lease,
            repo_root="/repo",
            worktree="/repo",
            branch="branch",
        )

    assert "tests_to_run" in excinfo.value.missing_fields


def test_flag_on_directive_materializes_task_package(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    task_id = _admit_ready(ledger)
    lease = _claim(ledger, task_id)
    monkeypatch.setenv(TASK_PACKAGE_FLAG, "1")

    directive = orchestrator.write_phase_c_fix_directive(ledger, lease, loop_dir=tmp_path / "loop")
    text = directive.read_text(encoding="utf-8")

    assert f"schema_version: {TASK_PACKAGE_SCHEMA_VERSION}" in text
    assert f"task_id: {task_id}" in text
    assert f"lease_nonce: {lease.lease_nonce}" in text
    assert "Payload JSON" in text

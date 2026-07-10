import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from agent_presence import (
    AGENT_CONFIGS,
    NO_AUTHORITY_FLAGS,
    agent_presence_table_names,
    build_agent_presence_report,
    build_agent_presence_read_model,
    build_agent_presence_snapshot,
    approve_agent_recovery_clearance,
    build_agent_recovery_status_report,
    export_agent_presence_read_model,
    request_agent_recovery_clearance,
    recover_agent,
)
from scripts.approve_agent_recovery_clearance import main as approve_clearance_main
from scripts.check_agent_presence import main as check_main
from scripts.check_agent_recovery_status import AGENTS as RECOVERY_STATUS_AGENT_IDS
from scripts.check_agent_recovery_status import main as recovery_status_main
from scripts.export_agent_presence_read_model import main as export_main
from scripts.query_agent_recovery_clearances import main as query_clearances_main
from scripts.query_agent_presence import main as query_main
from scripts.request_cassandra_recovery_guardian_approval import run_guardian_clearance_flow
from scripts.recover_agent import AGENTS as RECOVERY_AGENT_IDS
from scripts.recover_agent import main as recover_main
from scripts.request_agent_recovery_clearance import main as request_clearance_main


CORE_AGENT_IDS = {"maestro", "chief", "cassandra", "guardian", "niles", "hermes"}


def _row(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _rows(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _write(path: Path, text: str = "fixture\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for config in AGENT_CONFIGS:
        for surface in config.surfaces:
            _write(root / surface.source_path)
        for metadata_path in config.metadata_available_paths:
            _write(root / metadata_path, "{}\n" if metadata_path.endswith(".json") else "fixture\n")
    return root


def _service_states(value: str = "inactive") -> dict[str, str]:
    return {
        surface.service_name: value
        for config in AGENT_CONFIGS
        for surface in config.surfaces
        if surface.service_name
    }


def _primary_service_names() -> set[str]:
    return {
        surface.service_name
        for config in AGENT_CONFIGS
        for surface in config.surfaces
        if surface.surface_id == config.primary_surface_id and surface.service_name
    }


def test_schema_initializes(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    assert {
        "agent_presence_runs",
        "agent_presence_agents",
        "agent_presence_checks",
        "agent_desired_states",
        "agent_recovery_actions",
        "agent_recovery_clearances",
        "agent_recovery_attempts",
        "agent_recovery_policies",
        "agent_recovery_receipts",
        "agent_presence_blockers",
        "agent_presence_runtime_surfaces",
    } <= set(agent_presence_table_names(db_path))


def test_core_agents_are_represented_and_lane_registry_alone_does_not_mark_online(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    assert {config.agent_id for config in AGENT_CONFIGS} == CORE_AGENT_IDS
    assert set(RECOVERY_AGENT_IDS) == CORE_AGENT_IDS
    assert set(RECOVERY_STATUS_AGENT_IDS) == CORE_AGENT_IDS
    assert all(
        sum(surface.surface_id == config.primary_surface_id for surface in config.surfaces) == 1
        for config in AGENT_CONFIGS
    )

    result = build_agent_presence_snapshot(
        db_path=db_path,
        repo_root=tmp_path / "empty_repo",
        run_id="presence_no_runtime_fixture",
        process_counts={},
        service_states={},
    )

    assert result.agent_count == 6
    rows = _rows(
        db_path,
        """
SELECT agent_id, desired_state, actual_state, runtime_surface_found, expected_online
FROM agent_presence_agents
WHERE run_id = 'presence_no_runtime_fixture'
ORDER BY agent_id
""",
    )
    assert {row["agent_id"] for row in rows} == CORE_AGENT_IDS
    assert all(row["actual_state"] != "online" for row in rows)
    assert all(row["runtime_surface_found"] == 0 for row in rows)
    assert _row(
        db_path,
        "SELECT actual_state FROM agent_presence_agents WHERE agent_id = 'maestro'",
    )["actual_state"] == "not_configured"
    assert _row(
        db_path,
        "SELECT actual_state FROM agent_presence_agents WHERE agent_id = 'report_bridge'",
    ) is None


def test_runtime_surfaces_are_recorded_without_secret_or_message_actions(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_root = _fixture_repo(tmp_path)

    build_agent_presence_snapshot(
        db_path=db_path,
        repo_root=repo_root,
        run_id="presence_surface_fixture",
        process_counts={},
        service_states=_service_states("inactive"),
    )

    surfaces = _rows(
        db_path,
        """
SELECT agent_id, surface_kind, source_path, service_name, surface_found,
       classification, service_state, recovery_allowed
FROM agent_presence_runtime_surfaces
WHERE run_id = 'presence_surface_fixture'
ORDER BY agent_id, source_path
""",
    )
    assert surfaces
    assert any(row["agent_id"] == "cassandra" and row["surface_kind"] == "telegram_bot" for row in surfaces)
    assert all(row["surface_found"] == 1 for row in surfaces)
    assert all(row["recovery_allowed"] == 0 for row in surfaces)
    actions = _rows(
        db_path,
        """
SELECT agent_id, action_kind, safe_to_attempt, command_argv_json
FROM agent_recovery_actions
ORDER BY agent_id
""",
    )
    assert CORE_AGENT_IDS <= {row["agent_id"] for row in actions}
    cassandra_action = [row for row in actions if row["agent_id"] == "cassandra"][0]
    assert cassandra_action["action_kind"] == "systemd_user_start"
    assert cassandra_action["safe_to_attempt"] == 0
    assert json.loads(cassandra_action["command_argv_json"])[:3] == ["systemctl", "--user", "start"]
    assert tuple(_row(
        db_path,
        """
SELECT SUM(raw_secret_accessed) AS secrets,
       SUM(message_sent) AS messages,
       SUM(command_executed) AS commands
FROM agent_presence_checks
WHERE run_id = 'presence_surface_fixture'
""",
    )) == (0, 0, 0)


def test_primary_service_is_authoritative_and_auxiliary_services_only_affect_detail(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_root = _fixture_repo(tmp_path)
    states = _service_states("inactive")
    states["cassandra-listener.service"] = "active"

    build_agent_presence_snapshot(
        db_path=db_path,
        repo_root=repo_root,
        run_id="presence_degraded_fixture",
        process_counts={},
        service_states=states,
    )

    cassandra = _row(
        db_path,
        "SELECT actual_state, presence_source, blocker FROM agent_presence_agents WHERE agent_id = 'cassandra'",
    )
    assert cassandra["actual_state"] == "online"
    assert cassandra["presence_source"] == "service_check"
    assert cassandra["blocker"] is None
    detail = build_agent_presence_read_model(db_path=db_path, repo_root=repo_root)
    cassandra_detail = next(item for item in detail["agents"] if item["agent_id"] == "cassandra")
    assert cassandra_detail["presence_detail_state"] == "degraded"
    assert cassandra_detail["active_auxiliary_count"] == 0

    states["cassandra-listener.service"] = "inactive"
    states["cassandra-watcher.service"] = "active"
    states["cassandra-briefing-scheduler.service"] = "active"
    build_agent_presence_snapshot(
        db_path=db_path,
        repo_root=repo_root,
        run_id="presence_auxiliary_only_fixture",
        process_counts={"cassandra_listener.py": 1},
        service_states=states,
    )
    cassandra = _row(
        db_path,
        "SELECT actual_state, reason FROM agent_presence_agents WHERE agent_id = 'cassandra'",
    )
    assert cassandra["actual_state"] == "offline"
    assert "primary" in cassandra["reason"].lower()


def test_desired_state_boundaries_prevent_recovery(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_root = _fixture_repo(tmp_path)

    for desired_state in ("hard_kill", "offline_intentional", "maintenance"):
        build_agent_presence_snapshot(
            db_path=db_path,
            repo_root=repo_root,
            run_id=f"presence_{desired_state}_fixture",
            desired_state_overrides={"cassandra": desired_state},
            recovery_policy_overrides={
                "cassandra": {
                    "recovery_allowed": True,
                    "recovery_kind": "systemd_restart",
                    "recovery_command_id": "fixture_restart",
                }
            },
            process_counts={},
            service_states=_service_states("inactive"),
        )
        row = _row(
            db_path,
            """
SELECT desired_state, autorecovery_allowed, recovery_status, blocker
FROM agent_presence_agents
WHERE agent_id = 'cassandra'
""",
        )
        assert row["desired_state"] == desired_state
        assert row["autorecovery_allowed"] == 0
        assert row["recovery_status"] == "blocked"


def test_expected_online_offline_without_enabled_policy_is_blocked_and_not_attempted(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_root = _fixture_repo(tmp_path)

    build_agent_presence_snapshot(
        db_path=db_path,
        repo_root=repo_root,
        run_id="presence_blocked_fixture",
        process_counts={},
        service_states=_service_states("inactive"),
    )

    chief = _row(
        db_path,
        """
SELECT actual_state, expected_online, autorecovery_allowed, recovery_status, blocker
FROM agent_presence_agents
WHERE agent_id = 'chief'
""",
    )
    assert chief["actual_state"] == "offline"
    assert chief["expected_online"] == 1
    assert chief["autorecovery_allowed"] == 0
    assert chief["recovery_status"] == "blocked"
    assert chief["blocker"] == "expected primary runtime evidence missing"
    assert _row(
        db_path,
        "SELECT SUM(attempted) AS attempted FROM agent_recovery_receipts WHERE run_id = 'presence_blocked_fixture'",
    )["attempted"] == 0


def test_recovery_status_report_is_deterministic_for_cassandra_chief_and_niles(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_root = _fixture_repo(tmp_path)
    build_agent_presence_snapshot(
        db_path=db_path,
        repo_root=repo_root,
        run_id="presence_recovery_status_fixture",
        process_counts={},
        service_states=_service_states("inactive"),
    )

    for agent in ("cassandra", "chief", "niles"):
        report = build_agent_recovery_status_report(
            db_path=db_path,
            agent=agent,
            refresh_presence=False,
        )
        item = report["items"][0]
        assert item["agent_id"] == agent
        assert item["safe_recovery_action_available"] is False
        assert item["recovery_action"]
        assert item["blocked_reason"]


def test_recover_agent_dry_run_does_not_execute(tmp_path, monkeypatch):
    db_path = tmp_path / "ledger.sqlite"
    repo_root = _fixture_repo(tmp_path)
    build_agent_presence_snapshot(
        db_path=db_path,
        repo_root=repo_root,
        run_id="presence_recovery_dry_run_fixture",
        process_counts={},
        service_states=_service_states("inactive"),
    )
    called = False

    def fake_runner(*_args, **_kwargs):
        nonlocal called
        called = True
        return subprocess.CompletedProcess(_args[0], 0, "ok", "")

    result = recover_agent(
        agent_id="cassandra",
        db_path=db_path,
        execute=False,
        refresh_presence=False,
        command_runner=fake_runner,
    )

    assert result.status == "blocked"
    assert result.attempted is False
    assert called is False
    assert _row(db_path, "SELECT COUNT(*) AS count FROM agent_recovery_attempts")["count"] == 0


def test_recover_agent_execute_requires_safe_allowed_policy(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_root = _fixture_repo(tmp_path)
    build_agent_presence_snapshot(
        db_path=db_path,
        repo_root=repo_root,
        run_id="presence_recovery_blocked_execute_fixture",
        process_counts={},
        service_states=_service_states("inactive"),
    )

    result = recover_agent(
        agent_id="cassandra",
        db_path=db_path,
        execute=True,
        refresh_presence=False,
        refresh_after=False,
    )

    assert result.status == "blocked"
    assert result.attempted is False
    assert "not safe_to_attempt" in result.blocker
    assert tuple(_row(
        db_path,
        "SELECT attempted, command_executed, shell_used, telegram_api_called, message_sent, secret_accessed FROM agent_recovery_attempts",
    )) == (0, 0, 0, 0, 0, 0)


def test_recovery_clearance_request_alone_does_not_allow_execution(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_root = _fixture_repo(tmp_path)
    request = request_agent_recovery_clearance(
        agent_id="cassandra",
        requested_by="operator",
        reason="test request without approval",
        db_path=db_path,
    )

    build_agent_presence_snapshot(
        db_path=db_path,
        repo_root=repo_root,
        run_id="presence_recovery_requested_fixture",
        process_counts={},
        service_states=_service_states("inactive"),
    )
    result = recover_agent(
        agent_id="cassandra",
        db_path=db_path,
        execute=True,
        refresh_presence=False,
        refresh_after=False,
    )

    assert request["status"] == "requested"
    assert result.status == "blocked"
    assert result.attempted is False
    assert "not safe_to_attempt" in result.blocker
    assert _row(
        db_path,
        "SELECT status FROM agent_recovery_clearances WHERE clearance_id = ?",
        (request["clearance_id"],),
    )["status"] == "requested"


def test_approved_cassandra_clearance_writes_receipt_and_blocks_reuse(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_root = _fixture_repo(tmp_path)
    request = request_agent_recovery_clearance(
        agent_id="cassandra",
        requested_by="operator",
        reason="test approved clearance",
        db_path=db_path,
    )
    approval = approve_agent_recovery_clearance(
        clearance_id=request["clearance_id"],
        approved_by="operator",
        approval_note="approve the fixed Cassandra start action for one attempt",
        confirm_agent="cassandra",
        confirm_action="cassandra_systemd_user_start",
        db_path=db_path,
    )
    build_agent_presence_snapshot(
        db_path=db_path,
        repo_root=repo_root,
        run_id="presence_recovery_clearance_execute_fixture",
        process_counts={},
        service_states=_service_states("inactive"),
    )
    calls = []

    def fake_runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, "started\n", "")

    first = recover_agent(
        agent_id="cassandra",
        db_path=db_path,
        execute=True,
        refresh_presence=False,
        refresh_after=False,
        command_runner=fake_runner,
    )
    second = recover_agent(
        agent_id="cassandra",
        db_path=db_path,
        execute=True,
        refresh_presence=False,
        refresh_after=False,
        command_runner=fake_runner,
    )

    assert approval["status"] == "approved"
    assert first.status == "succeeded"
    assert first.attempted is True
    assert first.receipt_id
    assert calls[0][0][:3] == ["systemctl", "--user", "start"]
    assert calls[0][1]["shell"] is False
    assert second.status == "blocked"
    assert second.attempted is False
    assert "not approved" in second.blocker or "cooldown prevents" in second.blocker
    clearance = _row(
        db_path,
        "SELECT status, used_attempts, receipt_id FROM agent_recovery_clearances WHERE clearance_id = ?",
        (request["clearance_id"],),
    )
    assert clearance["status"] == "used"
    assert clearance["used_attempts"] == 1
    assert clearance["receipt_id"] == first.receipt_id
    rows = _rows(db_path, "SELECT attempted, succeeded, shell_used, telegram_api_called, message_sent, secret_accessed FROM agent_recovery_attempts ORDER BY attempted_at")
    assert tuple(rows[0]) == (1, 1, 0, 0, 0, 0)
    assert tuple(rows[1]) == (0, 0, 0, 0, 0, 0)


def test_clearance_does_not_bypass_hard_kill_or_wrong_action(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_root = _fixture_repo(tmp_path)
    request = request_agent_recovery_clearance(
        agent_id="cassandra",
        requested_by="operator",
        reason="test hard kill boundary",
        db_path=db_path,
    )
    approve_agent_recovery_clearance(
        clearance_id=request["clearance_id"],
        approved_by="operator",
        approval_note="approve fixed action for boundary test",
        confirm_agent="cassandra",
        confirm_action="cassandra_systemd_user_start",
        db_path=db_path,
    )
    build_agent_presence_snapshot(
        db_path=db_path,
        repo_root=repo_root,
        run_id="presence_recovery_clearance_hard_kill_fixture",
        desired_state_overrides={"cassandra": "hard_kill"},
        process_counts={},
        service_states=_service_states("inactive"),
    )

    result = recover_agent(
        agent_id="cassandra",
        db_path=db_path,
        execute=True,
        refresh_presence=False,
        refresh_after=False,
    )

    assert result.status == "blocked"
    assert "hard_kill" in result.blocker
    assert _row(
        db_path,
        "SELECT status, used_attempts FROM agent_recovery_clearances WHERE clearance_id = ?",
        (request["clearance_id"],),
    )["used_attempts"] == 0
    try:
        approve_agent_recovery_clearance(
            clearance_id=request["clearance_id"],
            approved_by="operator",
            approval_note="wrong target",
            confirm_agent="cassandra",
            confirm_action="chief_systemd_user_start",
            db_path=db_path,
        )
    except ValueError as exc:
        assert "only available for Cassandra" in str(exc)
    else:
        raise AssertionError("wrong recovery action should not be accepted")


def test_approved_clearance_command_start_error_writes_blocked_receipt(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_root = _fixture_repo(tmp_path)
    request = request_agent_recovery_clearance(
        agent_id="cassandra",
        requested_by="operator",
        reason="test wrong host command boundary",
        db_path=db_path,
    )
    approve_agent_recovery_clearance(
        clearance_id=request["clearance_id"],
        approved_by="operator",
        approval_note="approve fixed action for command-start error test",
        confirm_agent="cassandra",
        confirm_action="cassandra_systemd_user_start",
        db_path=db_path,
    )
    build_agent_presence_snapshot(
        db_path=db_path,
        repo_root=repo_root,
        run_id="presence_recovery_clearance_oserror_fixture",
        process_counts={},
        service_states=_service_states("inactive"),
    )

    def missing_runner(*_args, **_kwargs):
        raise FileNotFoundError("systemctl")

    result = recover_agent(
        agent_id="cassandra",
        db_path=db_path,
        execute=True,
        refresh_presence=False,
        refresh_after=False,
        command_runner=missing_runner,
    )

    assert result.status == "blocked"
    assert result.attempted is False
    assert result.receipt_id
    assert "could not start" in result.blocker
    attempt = _row(
        db_path,
        "SELECT attempted, command_executed, blocker FROM agent_recovery_attempts WHERE receipt_id = ?",
        (result.receipt_id,),
    )
    assert attempt["attempted"] == 0
    assert attempt["command_executed"] == 0
    assert "FileNotFoundError" in attempt["blocker"]


def test_guardian_clearance_flow_approves_but_does_not_execute(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    payload = run_guardian_clearance_flow(
        db_path=str(db_path),
        requested_by="chief",
        reason="test guardian approval",
        approval_func=lambda *_args, **_kwargs: True,
    )

    assert payload["status"] == "guardian_approved"
    clearance = _row(
        db_path,
        "SELECT status, approved_by, used_attempts FROM agent_recovery_clearances WHERE clearance_id = ?",
        (payload["clearance_id"],),
    )
    assert clearance["status"] == "approved"
    assert clearance["approved_by"] == "guardian"
    assert clearance["used_attempts"] == 0
    assert _row(db_path, "SELECT COUNT(*) FROM agent_recovery_attempts")[0] == 0
    packet = _row(
        db_path,
        "SELECT event_type, actor, operator_visible_summary FROM events WHERE event_type = 'approval_request_record'",
    )
    assert packet["actor"] == "chief"
    assert "Cassandra recovery clearance" in packet["operator_visible_summary"]


def test_guardian_clearance_flow_denial_rejects_without_execution(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    payload = run_guardian_clearance_flow(
        db_path=str(db_path),
        requested_by="chief",
        reason="test guardian denial",
        approval_func=lambda *_args, **_kwargs: False,
    )

    assert payload["status"] == "guardian_denied"
    clearance = _row(
        db_path,
        "SELECT status, rejected_by, used_attempts FROM agent_recovery_clearances WHERE clearance_id = ?",
        (payload["clearance_id"],),
    )
    assert clearance["status"] == "rejected"
    assert clearance["rejected_by"] == "guardian"
    assert clearance["used_attempts"] == 0
    assert _row(db_path, "SELECT COUNT(*) FROM agent_recovery_attempts")[0] == 0


def test_report_bridge_can_be_metadata_available_without_fake_online(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_root = tmp_path / "repo"
    _write(repo_root / "report_bridge.py")
    _write(repo_root / "generated/read_models/report_bridge.json", "{}\n")

    build_agent_presence_snapshot(
        db_path=db_path,
        repo_root=repo_root,
        run_id="presence_report_bridge_fixture",
        process_counts={},
        service_states={},
    )

    assert _row(
        db_path,
        "SELECT actual_state FROM agent_presence_agents WHERE agent_id = 'report_bridge'",
    ) is None

    payload = build_agent_presence_read_model(db_path=db_path, repo_root=repo_root)
    assert payload["agent_count"] == 6
    assert {item["agent_id"] for item in payload["agents"]} == CORE_AGENT_IDS
    report_bridge = payload["supplemental_surfaces"][0]
    assert report_bridge["supplemental_id"] == "report_bridge"
    assert report_bridge["actual_state"] == "metadata_available"
    assert report_bridge["included_in_agent_denominator"] is False


def test_query_reports_and_scripts_work(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    repo_root = _fixture_repo(tmp_path)

    assert check_main(["--db", str(db_path), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["agent_count"] == 6

    build_agent_presence_snapshot(
        db_path=db_path,
        repo_root=repo_root,
        run_id="presence_query_fixture",
        process_counts={},
        service_states=_service_states("inactive"),
    )
    for agent in ("maestro", "cassandra", "chief", "guardian", "niles", "hermes"):
        assert query_main(["--db", str(db_path), "--agent", agent]) == 0
        out = capsys.readouterr().out
        assert f"Agent: `{agent}`" in out
        assert "Recovery status:" in out

    for report in ("summary", "offline", "expected-online", "recovery-available"):
        assert query_main(["--db", str(db_path), "--report", report, "--format", "json"]) == 0
        report_payload = json.loads(capsys.readouterr().out)
        assert report_payload["status"] == "ok"

    assert recovery_status_main(["--db", str(db_path), "--agent", "cassandra", "--format", "json"]) == 0
    recovery_payload = json.loads(capsys.readouterr().out)
    assert recovery_payload["items"][0]["agent_id"] == "cassandra"

    assert recover_main(["--db", str(db_path), "--agent", "cassandra", "--dry-run", "--format", "json"]) == 0
    recover_payload = json.loads(capsys.readouterr().out)
    assert recover_payload["status"] == "blocked"
    assert recover_payload["attempted"] is False

    assert request_clearance_main([
        "--db", str(db_path),
        "--agent", "cassandra",
        "--requested-by", "operator",
        "--reason", "script fixture",
        "--format", "json",
    ]) == 0
    clearance_payload = json.loads(capsys.readouterr().out)
    assert clearance_payload["status"] == "requested"
    assert query_clearances_main(["--db", str(db_path), "--agent", "cassandra", "--format", "json"]) == 0
    query_payload = json.loads(capsys.readouterr().out)
    assert query_payload["clearance_count"] >= 1
    assert approve_clearance_main([
        "--db", str(db_path),
        "--clearance-id", clearance_payload["clearance_id"],
        "--approved-by", "operator",
        "--approval-note", "script fixture approval",
        "--confirm-agent", "cassandra",
        "--confirm-action", "cassandra_systemd_user_start",
        "--format", "json",
    ]) == 0
    approval_payload = json.loads(capsys.readouterr().out)
    assert approval_payload["status"] == "approved"


def test_read_model_export_refreshes_presence_and_preserves_run_evidence(tmp_path, capsys, monkeypatch):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"
    repo_root = _fixture_repo(tmp_path)
    stale = build_agent_presence_snapshot(
        db_path=db_path,
        repo_root=repo_root,
        run_id="presence_export_stale_fixture",
        process_counts={},
        service_states=_service_states("inactive"),
    )

    monkeypatch.setattr(
        "agent_presence._systemd_user_state",
        lambda service_names: {
            name: "active" if name in _primary_service_names() else "inactive"
            for name in service_names
        },
    )
    monkeypatch.setattr("agent_presence._process_snapshot", lambda: {})
    summary = export_agent_presence_read_model(
        db_path=db_path,
        export_root=export_root,
        repo_root=repo_root,
    )
    assert export_main(["--db", str(db_path), "--export-root", str(export_root), "--format", "json"]) == 0
    script_summary = json.loads(capsys.readouterr().out)
    json_path = export_root / "agent_presence.json"
    operator_path = export_root / "agent_presence_OPERATOR.md"
    read_model = json.loads(json_path.read_text(encoding="utf-8"))

    assert summary["agent_count"] == 6
    assert script_summary["agent_count"] == 6
    assert summary["run_id"] != stale.run_id
    assert read_model["run_id"] != stale.run_id
    assert read_model["generated_at"] == read_model["observation_completed_at"]
    assert read_model["online_count"] == 6
    assert read_model["agent_count"] == 6
    assert {item["agent_id"] for item in read_model["agents"]} == CORE_AGENT_IDS
    assert all(surface["observed_at"] for surface in read_model["runtime_surfaces"])
    assert sum(1 for surface in read_model["runtime_surfaces"] if surface["presence_role"] == "primary") == 6
    assert read_model["cassandra_presence"]["agent_id"] == "cassandra"
    assert read_model["cassandra_presence"]["actual_state"] in {"offline", "degraded", "online"}
    assert operator_path.exists()
    assert "does not send Telegram messages" in operator_path.read_text(encoding="utf-8")
    for key, value in NO_AUTHORITY_FLAGS.items():
        assert read_model[key] is value
        assert read_model["no_authority_flags"][key] is value


def test_export_refuses_incoherent_run_before_replacing_existing_snapshot(tmp_path, monkeypatch):
    db_path = tmp_path / "ledger.sqlite"
    repo_root = _fixture_repo(tmp_path)
    export_root = tmp_path / "read_models"
    export_root.mkdir()
    json_path = export_root / "agent_presence.json"
    json_path.write_text('{"sentinel":"old"}\n', encoding="utf-8")

    monkeypatch.setattr(
        "agent_presence.build_agent_presence_read_model",
        lambda **_kwargs: {
            "run_id": "racing_run",
            "observation_completed_at": "2026-07-09T22:30:00+00:00",
            "generated_at": "2026-07-09T22:30:00+00:00",
            "agent_count": 0,
            "online_count": 0,
            "agents": [],
        },
    )

    with pytest.raises(RuntimeError, match="read back atomically"):
        export_agent_presence_read_model(
            db_path=db_path,
            export_root=export_root,
            repo_root=repo_root,
            process_counts={},
            service_states=_service_states("active"),
        )

    assert json_path.read_text(encoding="utf-8") == '{"sentinel":"old"}\n'
    assert not (export_root / "agent_presence_OPERATOR.md").exists()


def test_report_builder_can_answer_cassandra_question(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    repo_root = _fixture_repo(tmp_path)
    build_agent_presence_snapshot(
        db_path=db_path,
        repo_root=repo_root,
        run_id="presence_cassandra_answer_fixture",
        process_counts={},
        service_states=_service_states("inactive"),
    )

    report = build_agent_presence_report(db_path=db_path, agent="cassandra")
    cassandra = report["items"][0]
    assert cassandra["agent_id"] == "cassandra"
    assert cassandra["desired_state"] == "online"
    assert cassandra["actual_state"] == "offline"
    assert cassandra["expected_online"] is True
    assert cassandra["autorecovery_allowed"] is False
    assert cassandra["next_safe_move"].startswith("Inspect the documented service")


def test_source_has_no_forbidden_runtime_network_or_destructive_behavior():
    text = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "agent_presence.py",
            "scripts/check_agent_presence.py",
            "scripts/check_agent_recovery_status.py",
            "scripts/request_agent_recovery_clearance.py",
            "scripts/approve_agent_recovery_clearance.py",
            "scripts/query_agent_recovery_clearances.py",
            "scripts/request_cassandra_recovery_guardian_approval.py",
            "scripts/query_agent_presence.py",
            "scripts/recover_agent.py",
            "scripts/export_agent_presence_read_model.py",
        ]
    )
    forbidden = [
        "shell=true",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "telegram.bot",
        ".send_message",
        "docker run",
        "ollama run",
        "apt install",
        "npm install",
        "pip install",
        "shutil.move",
        "shutil.rmtree",
        "/mnt/c/openclaw",
        "c:\\openclaw",
    ]
    for token in forbidden:
        assert token not in text

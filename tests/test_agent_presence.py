import json
import sqlite3
from pathlib import Path

from agent_presence import (
    AGENT_CONFIGS,
    NO_AUTHORITY_FLAGS,
    agent_presence_table_names,
    build_agent_presence_report,
    build_agent_presence_snapshot,
    export_agent_presence_read_model,
)
from scripts.check_agent_presence import main as check_main
from scripts.export_agent_presence_read_model import main as export_main
from scripts.query_agent_presence import main as query_main


CORE_AGENT_IDS = {"chief", "cassandra", "guardian", "niles", "hermes", "report_bridge"}


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


def test_schema_initializes(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    assert {
        "agent_presence_runs",
        "agent_presence_agents",
        "agent_presence_checks",
        "agent_desired_states",
        "agent_recovery_policies",
        "agent_recovery_receipts",
        "agent_presence_blockers",
        "agent_presence_runtime_surfaces",
    } <= set(agent_presence_table_names(db_path))


def test_core_agents_are_represented_and_lane_registry_alone_does_not_mark_online(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

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
        "SELECT actual_state FROM agent_presence_agents WHERE agent_id = 'report_bridge'",
    )["actual_state"] == "not_configured"


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


def test_service_or_process_evidence_can_mark_online_or_degraded(tmp_path):
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
    assert cassandra["actual_state"] == "degraded"
    assert cassandra["presence_source"] == "service_check"
    assert "only some expected runtime surfaces" in cassandra["blocker"]

    states["cassandra-watcher.service"] = "active"
    states["cassandra-briefing-scheduler.service"] = "active"
    build_agent_presence_snapshot(
        db_path=db_path,
        repo_root=repo_root,
        run_id="presence_online_fixture",
        process_counts={},
        service_states=states,
    )
    assert _row(
        db_path,
        "SELECT actual_state FROM agent_presence_agents WHERE agent_id = 'cassandra'",
    )["actual_state"] == "online"


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
    assert chief["blocker"] == "expected runtime evidence missing"
    assert _row(
        db_path,
        "SELECT SUM(attempted) AS attempted FROM agent_recovery_receipts WHERE run_id = 'presence_blocked_fixture'",
    )["attempted"] == 0


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

    row = _row(
        db_path,
        """
SELECT desired_state, actual_state, expected_online, presence_source, runtime_surface_kind
FROM agent_presence_agents
WHERE agent_id = 'report_bridge'
""",
    )
    assert row["desired_state"] == "unknown_review"
    assert row["actual_state"] == "metadata_available"
    assert row["expected_online"] == 0
    assert row["presence_source"] == "read_model"
    assert row["runtime_surface_kind"] == "metadata_only"


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
    for agent in ("cassandra", "chief", "guardian", "niles", "hermes", "report_bridge"):
        assert query_main(["--db", str(db_path), "--agent", agent]) == 0
        out = capsys.readouterr().out
        assert f"Agent: `{agent}`" in out
        assert "Recovery status:" in out

    for report in ("summary", "offline", "expected-online", "recovery-available"):
        assert query_main(["--db", str(db_path), "--report", report, "--format", "json"]) == 0
        report_payload = json.loads(capsys.readouterr().out)
        assert report_payload["status"] == "ok"


def test_read_model_export_contains_cassandra_and_no_authority(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"
    repo_root = _fixture_repo(tmp_path)
    build_agent_presence_snapshot(
        db_path=db_path,
        repo_root=repo_root,
        run_id="presence_export_fixture",
        process_counts={},
        service_states=_service_states("inactive"),
    )

    summary = export_agent_presence_read_model(db_path=db_path, export_root=export_root, repo_root=tmp_path)
    assert export_main(["--db", str(db_path), "--export-root", str(export_root), "--format", "json"]) == 0
    script_summary = json.loads(capsys.readouterr().out)
    json_path = export_root / "agent_presence.json"
    operator_path = export_root / "agent_presence_OPERATOR.md"
    read_model = json.loads(json_path.read_text(encoding="utf-8"))

    assert summary["agent_count"] == 6
    assert script_summary["agent_count"] == 6
    assert read_model["cassandra_presence"]["agent_id"] == "cassandra"
    assert read_model["cassandra_presence"]["actual_state"] in {"offline", "degraded", "online"}
    assert operator_path.exists()
    assert "does not send Telegram messages" in operator_path.read_text(encoding="utf-8")
    for key, value in NO_AUTHORITY_FLAGS.items():
        assert read_model[key] is value
        assert read_model["no_authority_flags"][key] is value


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
            "scripts/query_agent_presence.py",
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

import json
import sqlite3
from pathlib import Path

from agent_lane_registry import (
    DEFAULT_AGENT_LANE_SEEDS,
    NO_AUTHORITY_FLAGS,
    agent_lane_table_names,
    build_agent_lane_report,
    export_agent_lanes_read_model,
    seed_agent_lane_registry,
)
from scripts.build_agent_lane_registry import main as build_main
from scripts.query_agent_lane_registry import main as query_main


def _row(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
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


def test_schema_initializes(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    assert {
        "agent_lane_registry_runs",
        "agent_lanes",
        "agent_lane_worlds",
        "agent_lane_allowed_inputs",
        "agent_lane_blocked_inputs",
        "agent_lane_allowed_outputs",
        "agent_lane_action_policies",
        "agent_lane_receipt_requirements",
        "agent_lane_aliases",
        "agent_lane_routing_hints",
        "agent_lane_source_kinds",
    } <= set(agent_lane_table_names(db_path))


def test_registry_build_is_idempotent_and_non_authorizing(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    first = seed_agent_lane_registry(db_path=db_path, run_id="agent_lane_fixture")
    second = seed_agent_lane_registry(db_path=db_path, run_id="agent_lane_fixture")

    assert first.agent_count == len(DEFAULT_AGENT_LANE_SEEDS)
    assert second.agent_count == len(DEFAULT_AGENT_LANE_SEEDS)
    assert _row(db_path, "SELECT COUNT(*) FROM agent_lanes")[0] == len(DEFAULT_AGENT_LANE_SEEDS)
    assert _row(
        db_path,
        """
SELECT COUNT(*)
FROM agent_lanes
WHERE can_execute != 0
   OR can_bypass_approval != 0
   OR can_read_no_go_raw != 0
   OR can_call_network != 0
   OR can_run_tools != 0
   OR can_call_models != 0
   OR runtime_authority != 0
   OR client_deployment_authority != 0
""",
    )[0] == 0
    assert _row(
        db_path,
        """
SELECT agent_activation_allowed, direct_execution_allowed,
       approval_bypass_allowed, no_go_raw_access_allowed,
       network_authority, tool_execution_allowed, model_execution_allowed,
       runtime_authority, client_deployment_allowed
FROM agent_lane_registry_runs
WHERE run_id = 'agent_lane_fixture'
""",
    ) == (0, 0, 0, 0, 0, 0, 0, 0, 0)


def test_required_agents_worlds_and_aliases_exist(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    seed_agent_lane_registry(db_path=db_path, run_id="agent_lane_fixture")

    agents = {row["agent_id"] for row in _rows(db_path, "SELECT agent_id FROM agent_lanes")}
    assert {"chief", "cassandra", "guardian", "niles", "hermes", "report_bridge"} <= agents
    niles_worlds = {
        row["world_binding"]
        for row in _rows(db_path, "SELECT world_binding FROM agent_lane_worlds WHERE agent_id = 'niles'")
    }
    chief_worlds = {
        row["world_binding"]
        for row in _rows(db_path, "SELECT world_binding FROM agent_lane_worlds WHERE agent_id = 'chief'")
    }
    guardian_worlds = {
        row["world_binding"]
        for row in _rows(db_path, "SELECT world_binding FROM agent_lane_worlds WHERE agent_id = 'guardian'")
    }
    aliases = {
        row["alias"]: row["agent_id"]
        for row in _rows(db_path, "SELECT alias, agent_id FROM agent_lane_aliases")
    }

    assert niles_worlds == {"music_art"}
    assert {"operations", "build", "cross_world"} <= chief_worlds
    assert "security" in guardian_worlds
    assert aliases["producer"] == "niles"
    assert aliases["creative_file_resolver"] == "niles"


def test_source_kinds_are_metadata_or_request_only_and_telegram_is_not_wired(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    seed_agent_lane_registry(db_path=db_path, run_id="agent_lane_fixture")

    source_rows = _rows(
        db_path,
        """
SELECT source_kind, source_posture, can_auto_execute, api_wired
FROM agent_lane_source_kinds
""",
    )

    assert source_rows
    assert {row["source_kind"] for row in source_rows} >= {
        "mission_control",
        "telegram",
        "cli",
        "report_bridge",
        "future_client_node",
    }
    assert all(row["can_auto_execute"] == 0 for row in source_rows)
    assert all(row["api_wired"] == 0 for row in source_rows)
    telegram = [row for row in source_rows if row["source_kind"] == "telegram"]
    assert telegram
    assert all(row["source_posture"] == "metadata_only" for row in telegram)


def test_reports_work_for_agents_worlds_sources_and_approval_required(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"

    assert build_main(
        [
            "--db",
            str(db_path),
            "--run-id",
            "agent_lane_fixture",
            "--export-root",
            str(tmp_path / "read_models"),
            "--format",
            "json",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["agents"] == len(DEFAULT_AGENT_LANE_SEEDS)
    assert payload["export"]["agent_count"] == len(DEFAULT_AGENT_LANE_SEEDS)

    for args, expected in (
        (["--agent", "chief"], "system_orchestration"),
        (["--agent", "producer"], "niles"),
        (["--report", "world", "--world", "music_art"], "niles"),
        (["--report", "source-kind", "--source-kind", "telegram"], "telegram"),
        (["--report", "approval-required"], "approval_required"),
    ):
        assert query_main(["--db", str(db_path), "--run-id", "agent_lane_fixture", *args]) == 0
        assert expected in capsys.readouterr().out


def test_read_model_export_contains_agents_and_no_authority_flags(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    seed_agent_lane_registry(db_path=db_path, run_id="agent_lane_fixture")

    summary = export_agent_lanes_read_model(
        db_path=db_path,
        run_id="agent_lane_fixture",
        export_root=tmp_path / "read_models",
    )
    json_path = tmp_path / "read_models" / "agent_lanes.json"
    operator_path = tmp_path / "read_models" / "agent_lanes_OPERATOR.md"
    read_model = json.loads(json_path.read_text(encoding="utf-8"))

    assert summary["agent_count"] == len(DEFAULT_AGENT_LANE_SEEDS)
    assert json_path.exists()
    assert operator_path.exists()
    assert read_model["agent_count"] == len(DEFAULT_AGENT_LANE_SEEDS)
    assert read_model["agents_by_world"]["music_art"] == ["niles"]
    assert "telegram" in read_model["agents_by_source_kind"]
    assert read_model["source_kind_posture"]["telegram"].startswith("metadata only")
    for key, value in NO_AUTHORITY_FLAGS.items():
        assert read_model[key] is value
        assert read_model["no_authority_flags"][key] is value
    assert "not agent activation" in operator_path.read_text(encoding="utf-8")


def test_agent_lane_registry_sources_have_no_runtime_network_or_tool_behavior():
    source_files = [
        Path("agent_lane_registry.py"),
        Path("scripts/build_agent_lane_registry.py"),
        Path("scripts/query_agent_lane_registry.py"),
    ]
    forbidden = [
        "import subprocess",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "paramiko",
        "docker run",
        "ollama run",
        "pip install",
        "npm install",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            assert token not in text

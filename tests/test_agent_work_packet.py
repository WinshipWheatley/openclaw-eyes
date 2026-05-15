import json
import sqlite3
from pathlib import Path

from agent_work_packet import (
    NO_AUTHORITY_FLAGS,
    agent_work_packet_table_names,
    build_agent_work_packet,
    build_agent_work_packet_report,
    build_sample_markdown_reorg_packet,
    export_agent_work_packets_read_model,
)
from file_event_queue import build_file_event_snapshot
from intent_router import route_operator_intent
from recent_file_context import build_recent_file_context
from scripts.build_agent_work_packet import main as build_main
from scripts.export_agent_work_packets_read_model import main as export_main
from scripts.query_agent_work_packets import main as query_main


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


def test_schema_initializes(tmp_path):
    tables = set(agent_work_packet_table_names(tmp_path / "ledger.sqlite"))

    assert {
        "agent_work_packet_runs",
        "agent_work_packets",
        "agent_work_packet_context_links",
        "agent_work_packet_allowed_surfaces",
        "agent_work_packet_blocked_surfaces",
        "agent_work_packet_command_candidates",
        "agent_work_packet_receipts",
    } <= tables


def test_packet_builds_from_intent_and_is_planning_only(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    route_operator_intent(
        text="Chief, organize my Markdown files.",
        source_kind="cli",
        source_channel="test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_markdown",
        run_id="run_markdown",
    )

    result = build_agent_work_packet(
        db_path=db_path,
        intent_id="intent_markdown",
        packet_id="packet_markdown",
        run_id="packet_run",
    )
    packet = _row(db_path, "SELECT * FROM agent_work_packets WHERE packet_id = ?", ("packet_markdown",))

    assert result.packet_id == "packet_markdown"
    assert result.routed_agent_id == "chief"
    assert result.execution_allowed is False
    assert packet["status"] == "draft"
    assert packet["approval_required"] == 1
    assert packet["execution_allowed"] == 0
    assert packet["action_created"] == 0
    assert "propose a markdown" in packet["goal"].lower()
    assert "Do not execute" in packet["exact_next_prompt_text"]


def test_packet_records_recent_file_context_links_without_raw_content(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    root = tmp_path / "openclaw"
    root.mkdir()
    (root / "song.logicx").mkdir()
    build_file_event_snapshot(root=root, root_id="fixture_root", db_path=db_path, run_id="file_run", allowed_roots=(root,))
    build_recent_file_context(db_path=db_path, run_id="recent_run")
    route_operator_intent(
        text="Niles, do something with that new Logic file.",
        source_kind="cli",
        source_channel="test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_logic",
        run_id="run_logic",
    )

    result = build_agent_work_packet(
        db_path=db_path,
        intent_id="intent_logic",
        packet_id="packet_logic",
        run_id="packet_logic_run",
    )
    link = _row(
        db_path,
        """
SELECT source_table, source_path, raw_content_read, raw_body_stored
FROM agent_work_packet_context_links
WHERE packet_id = ?
""",
        ("packet_logic",),
    )

    assert result.context_link_count == 1
    assert tuple(link) == ("recent_file_candidates", "song.logicx", 0, 0)


def test_candidate_action_is_candidate_only_and_not_created(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    route_operator_intent(
        text="Chief, refresh report bridge read-model.",
        source_kind="cli",
        source_channel="test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_refresh",
        run_id="run_refresh",
    )

    result = build_agent_work_packet(
        db_path=db_path,
        intent_id="intent_refresh",
        packet_id="packet_refresh",
        run_id="packet_refresh_run",
    )
    command = _row(db_path, "SELECT * FROM agent_work_packet_command_candidates WHERE packet_id = ?", ("packet_refresh",))

    assert result.command_candidate_count == 1
    assert command["candidate_action_type"] == "export_report_bridge_read_model"
    assert command["candidate_only"] == 1
    assert command["approval_required"] == 1
    assert command["execution_allowed"] == 0
    assert _row(db_path, "SELECT COUNT(*) AS count FROM operator_action_requests")["count"] == 0


def test_sample_packet_and_reports_work(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "exports"

    sample = build_sample_markdown_reorg_packet(db_path=db_path)
    assert sample.packet_id == "agent_work_packet_sample_markdown_reorg"

    report = build_agent_work_packet_report(db_path=db_path)
    assert report["counts"]["packet_count"] == 1
    assert report["counts"]["execution_allowed"] == 0
    assert report["counts"]["action_created"] == 0

    assert query_main(["--db", str(db_path), "--report", "summary", "--format", "operator"]) == 0
    assert "Agent Work Packet v0" in capsys.readouterr().out
    assert build_main(["--db", str(db_path), "--sample-markdown-reorg", "--format", "operator"]) == 0
    assert "Agent Work Packet v0" in capsys.readouterr().out

    export = export_agent_work_packets_read_model(db_path=db_path, export_root=export_root)
    payload = json.loads((export_root / "agent_work_packets.json").read_text(encoding="utf-8"))
    assert export["packet_count"] == 1
    assert payload["packet_count"] == 1
    assert payload["execution_allowed"] is False
    assert payload["agent_activation_allowed"] is False
    assert all(value is False for value in payload["no_authority_flags"].values())

    assert export_main(["--db", str(db_path), "--export-root", str(export_root), "--format", "operator"]) == 0
    assert "Agent Work Packets Read-Model Export v0" in capsys.readouterr().out


def test_prompt_is_bounded_and_blocks_private_no_go(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    route_operator_intent(
        text="Chief, organize my Markdown files.",
        source_kind="cli",
        source_channel="test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_prompt",
        run_id="run_prompt",
    )
    build_agent_work_packet(db_path=db_path, intent_id="intent_prompt", packet_id="packet_prompt")
    packet = _row(db_path, "SELECT exact_next_prompt_text, prompt_char_count FROM agent_work_packets")
    blocked = {
        row["surface_kind"]
        for row in _rows(db_path, "SELECT surface_kind FROM agent_work_packet_blocked_surfaces")
    }

    assert packet["prompt_char_count"] <= 3500
    assert "private/no-go raw content" in packet["exact_next_prompt_text"]
    assert "raw_private_content" in blocked
    assert "filesystem_mutation" in blocked


def test_static_boundaries():
    text = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "agent_work_packet.py",
            "scripts/build_agent_work_packet.py",
            "scripts/query_agent_work_packets.py",
            "scripts/export_agent_work_packets_read_model.py",
        ]
    )
    forbidden = [
        "subprocess.",
        "shell=true",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "paramiko",
        "rsync",
        "scp ",
        "ssh ",
        "docker run",
        "ollama run",
        "apt install",
        "npm install",
        "pip install",
        ".unlink(",
        ".remove(",
        ".rmdir(",
        ".rename(",
    ]
    for token in forbidden:
        assert token not in text
    assert all(value is False for value in NO_AUTHORITY_FLAGS.values())

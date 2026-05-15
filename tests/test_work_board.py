import json
import sqlite3
from pathlib import Path

import pytest

from agent_work_packet import build_agent_work_packet
from dropped_intent_registry import init_dropped_intent_schema
from intent_router import route_operator_intent
from operator_action import request_operator_action
from work_board import (
    NO_AUTHORITY_FLAGS,
    build_work_board,
    build_work_board_report,
    export_work_board_read_model,
    update_work_board_card,
    work_board_table_names,
)
from scripts.build_work_board import main as build_main
from scripts.export_work_board_read_model import main as export_main
from scripts.query_work_board import main as query_main
from scripts.update_work_board_card import main as update_main


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


def _insert_dropped_intent(db_path: Path, *, intent_id: str, status: str, title: str):
    init_dropped_intent_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
INSERT OR REPLACE INTO dropped_intent_runs (
  run_id, registry_version, created_at, completed_at, source_count,
  candidate_count, unresolved_count, built_count, deferred_count,
  rejected_count, superseded_count, unknown_review_count, raw_body_stored,
  notification_sent, action_created, execution_allowed, agent_activation_allowed,
  network_authority, model_call_allowed, raw_private_scan_allowed,
  file_move_allowed, file_delete_allowed, notes
) VALUES (
  'dropped_run', 'test', '2026-05-15T00:00:00+00:00',
  '2026-05-15T00:00:00+00:00', 1, 1, 1, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 'fixture'
)
""".strip()
        )
        conn.execute(
            """
INSERT OR REPLACE INTO dropped_intents (
  dropped_intent_id, title, short_summary, original_text_excerpt,
  source_path, source_ref, source_kind, source_hash, first_observed_at,
  observed_in_run_id, world_hint, agent_hint, lane_hint, intent_category,
  current_status, status_confidence, evidence_basis, suggested_next_question,
  suggested_next_lane, approval_required, action_created, notification_sent,
  raw_body_stored, created_at, updated_at
) VALUES (?, ?, ?, ?, NULL, ?, 'operator_note', 'hash', NULL,
  'dropped_run', 'build', 'chief', 'system_orchestration',
  'project_capsule_request', ?, 'high', 'fixture_safe_metadata',
  'Do you still want this?', 'Fixture Lane', 1, 0, 0, 0,
  '2026-05-15T00:00:00+00:00', '2026-05-15T00:00:00+00:00')
""".strip(),
            (intent_id, title, f"Summary for {title}", title, f"fixture:{intent_id}", status),
        )
        conn.commit()
    finally:
        conn.close()


def _make_completed_action(db_path: Path):
    result = request_operator_action(
        action_type="query_generated_read_model_mirror",
        requested_by="operator",
        reason="Check mirror status",
        action_id="action_completed_fixture",
        db_path=db_path,
    )
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE operator_action_requests SET status = 'completed', updated_at = ? WHERE action_id = ?",
            ("2026-05-15T00:00:00+00:00", result.action_id),
        )
        conn.execute(
            """
INSERT OR REPLACE INTO operator_action_receipts (
  receipt_id, action_id, execution_id, receipt_type, result, summary,
  stdout_excerpt, stderr_excerpt, payload_json, created_at,
  runtime_activation_allowed, agent_activation_allowed, arbitrary_shell_allowed,
  network_allowed, docker_allowed, ollama_allowed, remote_control_allowed,
  client_deployment_allowed, file_delete_allowed, file_move_allowed
) VALUES (
  'receipt_completed_fixture', ?, NULL, 'execution_receipt', 'completed',
  'Completed fixture action.', '', '', '{}', '2026-05-15T00:00:00+00:00',
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0
)
""".strip(),
            (result.action_id,),
        )
        conn.commit()
    finally:
        conn.close()


def test_schema_initializes(tmp_path):
    tables = set(work_board_table_names(tmp_path / "ledger.sqlite"))

    assert {
        "work_board_runs",
        "work_boards",
        "work_board_cards",
        "work_board_card_sources",
        "work_board_card_agents",
        "work_board_card_worlds",
        "work_board_card_dependencies",
        "work_board_card_status_history",
        "work_board_card_blockers",
        "work_board_card_receipts",
        "work_board_query_receipts",
    } <= tables


def test_build_creates_cards_from_intents_dropped_work_packets_and_actions(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    route_operator_intent(
        text="Chief, organize my Markdown files.",
        source_kind="cli",
        source_channel="test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_routed",
        run_id="run_routed",
    )
    route_operator_intent(
        text="Handle this unclear thing.",
        source_kind="cli",
        source_channel="test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_review",
        run_id="run_review",
    )
    build_agent_work_packet(
        db_path=db_path,
        intent_id="intent_routed",
        packet_id="packet_fixture",
        run_id="packet_run",
    )
    request_operator_action(
        action_type="export_report_bridge_read_model",
        requested_by="operator",
        reason="Refresh report bridge posture",
        action_id="action_pending_fixture",
        db_path=db_path,
    )
    _make_completed_action(db_path)
    _insert_dropped_intent(db_path, intent_id="drop_unresolved", status="unresolved", title="Dropped unresolved")
    _insert_dropped_intent(db_path, intent_id="drop_deferred", status="deferred", title="Dropped deferred")

    result = build_work_board(db_path=db_path, run_id="work_board_run")
    cards = _rows(
        db_path,
        "SELECT source_kind, source_id, board_column, execution_allowed, raw_body_stored FROM work_board_cards",
    )
    by_source = {(row["source_kind"], row["source_id"]): row["board_column"] for row in cards}

    assert result.card_count >= 7
    assert by_source[("intent_record", "intent_routed")] == "routed"
    assert by_source[("intent_record", "intent_review")] == "needs_review"
    assert by_source[("agent_work_packet", "packet_fixture")] == "planned"
    assert by_source[("operator_action", "action_pending_fixture")] == "pending_approval"
    assert by_source[("operator_action", "action_completed_fixture")] == "completed_with_receipt"
    assert by_source[("dropped_intent", "drop_unresolved")] == "needs_review"
    assert by_source[("dropped_intent", "drop_deferred")] == "deferred"
    assert all(row["execution_allowed"] == 0 for row in cards)
    assert all(row["raw_body_stored"] == 0 for row in cards)


def test_build_is_idempotent(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    route_operator_intent(
        text="Chief, organize my Markdown files.",
        source_kind="cli",
        source_channel="test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_once",
        run_id="run_once",
    )

    first = build_work_board(db_path=db_path, run_id="board_run_one")
    second = build_work_board(db_path=db_path, run_id="board_run_two")
    count = _row(db_path, "SELECT COUNT(*) AS count FROM work_board_cards")["count"]

    assert first.card_count == second.card_count
    assert count == first.card_count


def test_reports_scripts_and_read_model_export_work(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"
    route_operator_intent(
        text="Guardian, is this safe?",
        source_kind="cli",
        source_channel="test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_guardian",
        run_id="run_guardian",
    )
    build_work_board(db_path=db_path, run_id="board_report_run")

    report = build_work_board_report(db_path=db_path, report="summary")
    assert report["card_count"] >= 1
    assert report["counts_by_agent"]["guardian"] >= 1

    assert query_main(["--db", str(db_path), "--agent", "guardian", "--format", "operator"]) == 0
    assert "OpenClaw Work Board v0" in capsys.readouterr().out
    assert build_main(["--db", str(db_path), "--run-id", "board_script_run", "--format", "operator"]) == 0
    assert "Cards:" in capsys.readouterr().out

    summary = export_work_board_read_model(db_path=db_path, export_root=export_root)
    payload = json.loads((export_root / "work_board.json").read_text(encoding="utf-8"))
    assert summary["card_count"] >= 1
    assert payload["card_count"] >= 1
    assert payload["direct_execution_allowed"] is False
    assert payload["auto_approval_allowed"] is False
    assert all(value is False for value in payload["no_authority_flags"].values())

    assert export_main(["--db", str(db_path), "--export-root", str(export_root), "--format", "operator"]) == 0
    assert "Work Board Read-Model Export" in capsys.readouterr().out


def test_update_can_defer_reject_and_add_blocker_without_execution(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    _insert_dropped_intent(db_path, intent_id="drop_review", status="unresolved", title="Needs decision")
    _insert_dropped_intent(db_path, intent_id="drop_block", status="unresolved", title="Needs blocker")
    build_work_board(db_path=db_path, run_id="board_update_run")
    card = _row(
        db_path,
        "SELECT card_id FROM work_board_cards WHERE source_kind = 'dropped_intent' AND source_id = 'drop_review'",
    )
    block_card = _row(
        db_path,
        "SELECT card_id FROM work_board_cards WHERE source_kind = 'dropped_intent' AND source_id = 'drop_block'",
    )

    deferred = update_work_board_card(
        db_path=db_path,
        card_id=card["card_id"],
        board_column="deferred",
        status="deferred",
        metadata_only=True,
    )
    assert deferred.previous_column == "needs_review"
    assert deferred.board_column == "deferred"

    blocked = update_work_board_card(
        db_path=db_path,
        card_id=block_card["card_id"],
        blocker_reason="Waiting on operator priority.",
        metadata_only=True,
    )
    assert blocked.board_column == "blocked"
    row = _row(db_path, "SELECT board_column, execution_allowed FROM work_board_cards WHERE card_id = ?", (block_card["card_id"],))
    assert tuple(row) == ("blocked", 0)

    assert update_main(
        [
            "--db",
            str(db_path),
            "--card-id",
            block_card["card_id"],
            "--column",
            "superseded",
            "--metadata-only",
            "--format",
            "operator",
        ]
    ) == 0
    assert "Metadata-only update" in capsys.readouterr().out


def test_unsafe_transition_is_rejected(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    route_operator_intent(
        text="Chief, organize my Markdown files.",
        source_kind="cli",
        source_channel="test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_transition",
        run_id="run_transition",
    )
    build_work_board(db_path=db_path, run_id="board_transition_run")
    card = _row(
        db_path,
        "SELECT card_id FROM work_board_cards WHERE source_kind = 'intent_record' AND source_id = 'intent_transition'",
    )

    with pytest.raises(ValueError, match="unsupported board transition"):
        update_work_board_card(
            db_path=db_path,
            card_id=card["card_id"],
            board_column="completed_with_receipt",
            metadata_only=True,
        )


def test_no_forbidden_behavior_in_work_board_lane_files():
    text = "\n".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "work_board.py",
            "scripts/build_work_board.py",
            "scripts/query_work_board.py",
            "scripts/update_work_board_card.py",
            "scripts/export_work_board_read_model.py",
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

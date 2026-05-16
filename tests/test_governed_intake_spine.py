import json
from pathlib import Path

from governed_intake_spine import (
    build_governed_intake_spine_read_model,
    capture_governed_operator_intake,
    export_governed_intake_spine_read_model,
)
from scripts.export_governed_intake_spine_read_model import main as export_main
from scripts.query_governed_intake_spine import main as query_main


def _read_intent_row(db_path: Path, intent_id: str):
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM intent_records WHERE intent_id = ?", (intent_id,)).fetchone()
    finally:
        conn.close()


def test_raw_operator_text_becomes_governed_intent_and_work_board_card(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    result = capture_governed_operator_intake(
        raw_text="Cassandra, summarize what changed.",
        source_kind="cli",
        source_channel="governed_intake_spine_test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_governed_fixture",
        run_id="run_governed_fixture",
    )
    row = _read_intent_row(db_path, result.intent_id)

    assert result.intent_id == "intent_governed_fixture"
    assert result.route_status == "routed"
    assert result.routed_agent_id == "cassandra"
    assert result.routed_lane_id == "operator_comms"
    assert result.work_board_card_id
    assert result.execution_allowed is False
    assert result.action_created is False
    assert row["raw_text_stored"] == 0
    assert row["execution_allowed"] == 0
    assert row["action_request_created"] == 0


def test_unknown_intent_becomes_review_not_execution(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    result = capture_governed_operator_intake(
        raw_text="Handle that confusing thing later.",
        source_kind="cli",
        source_channel="governed_intake_spine_test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_unknown_fixture",
        run_id="run_unknown_fixture",
    )

    assert result.route_status == "needs_operator_review"
    assert result.routed_agent_id is None
    assert result.execution_allowed is False
    assert result.action_created is False


def test_agent_work_packet_projection_uses_existing_api_when_routed(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    result = capture_governed_operator_intake(
        raw_text="Guardian, is this safe?",
        source_kind="cli",
        source_channel="governed_intake_spine_test",
        requested_by="operator",
        db_path=db_path,
        intent_id="intent_packet_fixture",
        run_id="run_packet_fixture",
        create_agent_work_packet=True,
    )

    assert result.route_status == "routed"
    assert result.work_packet_id
    assert result.execution_allowed is False


def test_read_model_and_scripts_report_no_authority(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"
    capture_governed_operator_intake(
        raw_text="Chief, organize my Markdown files.",
        source_kind="cli",
        source_channel="governed_intake_spine_test",
        requested_by="operator",
        db_path=db_path,
    )

    read_model = build_governed_intake_spine_read_model(db_path=db_path)
    assert read_model["record_count"] == 1
    assert read_model["execution_allowed"] is False
    assert read_model["telegram_send_allowed"] is False
    assert read_model["capability_status"]["llm_classification_used"] is False

    summary = export_governed_intake_spine_read_model(db_path=db_path, export_root=export_root)
    payload = json.loads((export_root / "governed_intake_spine.json").read_text(encoding="utf-8"))
    assert summary["record_count"] == 1
    assert payload["runtime_authority"] is False
    assert (export_root / "governed_intake_spine_OPERATOR.md").is_file()

    query_exit = query_main(["--db", str(db_path), "--format", "operator"])
    assert query_exit == 0
    assert "Governed Intake Spine Read-Model v0" in capsys.readouterr().out

    export_exit = export_main(["--db", str(db_path), "--export-root", str(export_root), "--format", "operator"])
    assert export_exit == 0
    assert "Governed Intake Spine Read-Model v0" in capsys.readouterr().out


def test_governed_intake_sources_have_no_external_or_legacy_runtime_behavior():
    source_files = [
        Path("governed_intake_spine.py"),
        Path("scripts/query_governed_intake_spine.py"),
        Path("scripts/export_governed_intake_spine_read_model.py"),
    ]
    forbidden = [
        "/home/openclaw_external/openclaw-runtime",
        "import subprocess",
        "subprocess.",
        "os.system",
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "send_message",
        "reply_text",
        "smtplib",
        "shell=True",
        "eval(",
        "exec(",
    ]
    for path in source_files:
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for token in forbidden:
            assert token.lower() not in lowered

import ast
import json
import sqlite3
from pathlib import Path

from cassandra_runtime_wiring_audit import (
    NO_AUTHORITY_FLAGS,
    REPO_B_TARGET_FILES,
    build_cassandra_runtime_wiring_audit,
    build_cassandra_runtime_wiring_audit_read_model,
    build_cassandra_runtime_wiring_audit_report,
    cassandra_runtime_wiring_audit_table_names,
    export_cassandra_runtime_wiring_audit_read_model,
)
from scripts.build_cassandra_runtime_wiring_audit import main as build_main
from scripts.export_cassandra_runtime_wiring_audit_read_model import main as export_main
from scripts.query_cassandra_runtime_wiring_audit import main as query_main


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_repos(tmp_path: Path) -> tuple[Path, Path]:
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    for root in (repo_a, repo_b):
        root.mkdir()

    for name in (
        "telegram_agent_intake.py",
        "agent_presence.py",
        "intent_router.py",
        "agent_lane_registry.py",
        "operator_action_inbox.py",
        "work_board.py",
        "cassandra_identity.py",
        "capital_hilton_finance_fact_intake.py",
    ):
        _write(repo_a / name, "# governed fixture\n")

    _write(
        repo_a / "cassandra_listener.py",
        """
from telegram.ext import ApplicationBuilder, MessageHandler, filters
from telegram_agent_intake import record_telegram_listener_update_safe
BOT_TOKEN = 'fixture-name-only'
async def handle_message(update, context):
    record_telegram_listener_update_safe(text='hello', source_channel='cassandra_listener', agent_target='cassandra')
    await update.message.reply_text('ack')
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.run_polling()
""",
    )
    _write(repo_a / "cassandra_capability.py", "SAFE = True\n")

    for name in REPO_B_TARGET_FILES:
        _write(repo_b / name, "# placeholder\n")
    _write(
        repo_b / "cassandra_listener.py",
        """
import os
from telegram.ext import ApplicationBuilder, MessageHandler, filters
BOT_TOKEN = os.environ['CASSANDRA_BOT_TOKEN']
async def handle_message(update, context):
    await update.message.reply_text('ack')
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.run_polling()
""",
    )
    _write(
        repo_b / "cassandra_watcher.py",
        """
import subprocess
from cassandra_sender import send_message
def run():
    subprocess.run(['python', 'cassandra_sender.py', 'hi'])
""",
    )
    _write(repo_b / "cassandra_capability.py", "PAYMENT_EXTERNAL_CONNECTED = False\n")
    _write(repo_b / "cassandra_whisper_relay.py", "def relay_transcript(text, confidence): return {}\n")
    return repo_a, repo_b


def _service_facts(repo_a: Path) -> list[dict]:
    return [
        {
            "service_name": "cassandra-listener.service",
            "active_state": "active",
            "sub_state": "running",
            "main_pid": "101",
            "fragment_path": str(repo_a / ".config/systemd/user/cassandra-listener.service"),
            "working_directory": str(repo_a),
            "exec_entrypoints": [str(repo_a / "cassandra_listener.py")],
            "exec_log_paths": [],
            "env_file_sourced": True,
            "points_to_repo_a": True,
            "status_error": "",
        },
        {
            "service_name": "cassandra-watcher.service",
            "active_state": "active",
            "sub_state": "running",
            "main_pid": "102",
            "fragment_path": str(repo_a / ".config/systemd/user/cassandra-watcher.service"),
            "working_directory": str(repo_a),
            "exec_entrypoints": [str(repo_a / "cassandra_watcher.py")],
            "exec_log_paths": [],
            "env_file_sourced": True,
            "points_to_repo_a": True,
            "status_error": "",
        },
        {
            "service_name": "cassandra-briefing-scheduler.service",
            "active_state": "active",
            "sub_state": "running",
            "main_pid": "103",
            "fragment_path": str(repo_a / ".config/systemd/user/cassandra-briefing-scheduler.service"),
            "working_directory": str(repo_a),
            "exec_entrypoints": [str(repo_a / "cassandra_briefing_scheduler.py")],
            "exec_log_paths": [],
            "env_file_sourced": True,
            "points_to_repo_a": True,
            "status_error": "",
        },
    ]


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
    tables = set(cassandra_runtime_wiring_audit_table_names(tmp_path / "ledger.sqlite"))

    assert {
        "cassandra_runtime_wiring_runs",
        "cassandra_runtime_surfaces",
        "cassandra_runtime_comparison",
        "cassandra_roundtrip_steps",
        "cassandra_wiring_gaps",
        "cassandra_wiring_recommendations",
        "cassandra_wiring_query_receipts",
    } <= tables


def test_repo_b_files_classified_without_execution_and_send_env_flagged(tmp_path):
    repo_a, repo_b = _fixture_repos(tmp_path)
    db_path = tmp_path / "ledger.sqlite"

    build_cassandra_runtime_wiring_audit(
        db_path=db_path,
        repo_a_root=repo_a,
        repo_b_root=repo_b,
        run_id="audit",
        service_facts=_service_facts(repo_a),
        scan_app_logs=False,
    )
    listener = _row(
        db_path,
        """
SELECT classification_json, safe_port_posture, sends_telegram,
       reads_env_token, receives_telegram
FROM cassandra_runtime_comparison
WHERE repo_b_path = 'cassandra_listener.py'
""",
    )
    classes = set(json.loads(listener["classification_json"]))

    assert "useful_receive_logic" in classes
    assert "unsafe_direct_send" in classes
    assert "needs_operator_review" in classes
    assert listener["safe_port_posture"] == "candidate_to_wrap"
    assert tuple(listener)[2:] == (1, 1, 1)


def test_receive_ready_and_reply_ready_are_not_conflated(tmp_path):
    repo_a, repo_b = _fixture_repos(tmp_path)
    db_path = tmp_path / "ledger.sqlite"

    result = build_cassandra_runtime_wiring_audit(
        db_path=db_path,
        repo_a_root=repo_a,
        repo_b_root=repo_b,
        run_id="audit",
        service_facts=_service_facts(repo_a),
        scan_app_logs=False,
    )
    report = build_cassandra_runtime_wiring_audit_report(db_path=db_path, report="roundtrip")
    live_step = next(row for row in report["rows"] if row["step_name"] == "live_telegram_receive_to_governed_storage")
    ack_step = next(row for row in report["rows"] if row["step_name"] == "safe_acknowledgment_policy")

    assert result.live_receive_proven is False
    assert result.governed_storage_proven is True
    assert result.reply_ready is False
    assert live_step["status"] == "not_proven"
    assert live_step["blocker"] == "no_cassandra_listener_update_record"
    assert ack_step["status"] == "blocked_by_policy"
    assert ack_step["telegram_send_allowed"] == 0


def test_synthetic_you_online_yet_and_capital_hilton_route_store(tmp_path):
    repo_a, repo_b = _fixture_repos(tmp_path)
    db_path = tmp_path / "ledger.sqlite"

    build_cassandra_runtime_wiring_audit(
        db_path=db_path,
        repo_a_root=repo_a,
        repo_b_root=repo_b,
        run_id="audit",
        service_facts=_service_facts(repo_a),
        scan_app_logs=False,
    )
    updates = _rows(
        db_path,
        """
SELECT source_channel, agent_target, message_text_stored, raw_payload_stored,
       routed_to_intent_inbox, intent_record_id, telegram_send_allowed
FROM telegram_agent_update_records
WHERE source_channel LIKE 'synthetic_cassandra_wiring_audit%'
ORDER BY source_channel
""",
    )
    route_agents = [
        _row(db_path, "SELECT routed_agent_id FROM intent_records WHERE intent_id = ?", (row["intent_record_id"],))["routed_agent_id"]
        for row in updates
    ]

    assert len(updates) == 2
    assert all(row["agent_target"] == "cassandra" for row in updates)
    assert all(row["message_text_stored"] == 0 for row in updates)
    assert all(row["raw_payload_stored"] == 0 for row in updates)
    assert all(row["telegram_send_allowed"] == 0 for row in updates)
    assert route_agents == ["cassandra", "cassandra"]


def test_no_send_secret_repo_b_execution_authority_and_export(tmp_path):
    repo_a, repo_b = _fixture_repos(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"

    build_cassandra_runtime_wiring_audit(
        db_path=db_path,
        repo_a_root=repo_a,
        repo_b_root=repo_b,
        run_id="audit",
        service_facts=_service_facts(repo_a),
        scan_app_logs=False,
    )
    read_model = build_cassandra_runtime_wiring_audit_read_model(db_path=db_path)
    export = export_cassandra_runtime_wiring_audit_read_model(db_path=db_path, export_root=export_root)
    run = _row(
        db_path,
        """
SELECT telegram_send_allowed, arbitrary_command_allowed, repo_b_execution_allowed,
       secret_access_allowed, external_api_allowed, approval_bypass_allowed
FROM cassandra_runtime_wiring_runs
WHERE run_id = 'audit'
""",
    )

    assert tuple(run) == (0, 0, 0, 0, 0, 0)
    assert all(value is False for value in read_model["no_authority_flags"].values())
    assert read_model["counts"]["reply_ready"] is False
    assert Path(export_root / "cassandra_runtime_wiring_audit.json").exists()
    assert Path(export_root / "cassandra_runtime_wiring_audit_OPERATOR.md").exists()
    assert export["governed_storage_proven"] is True


def test_cli_build_query_and_export_work(tmp_path, capsys):
    repo_a, repo_b = _fixture_repos(tmp_path)
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"

    build_rc = build_main(
        [
            "--db",
            str(db_path),
            "--repo-a-root",
            str(repo_a),
            "--repo-b-root",
            str(repo_b),
            "--run-id",
            "cli_audit",
            "--no-log-scan",
            "--format",
            "operator",
        ]
    )
    query_rc = query_main(["--db", str(db_path), "--report", "summary", "--format", "operator"])
    roundtrip_rc = query_main(["--db", str(db_path), "--report", "roundtrip", "--format", "operator"])
    gaps_rc = query_main(["--db", str(db_path), "--report", "gaps", "--format", "operator"])
    export_rc = export_main(["--db", str(db_path), "--export-root", str(export_root), "--format", "operator"])
    output = capsys.readouterr().out

    assert (build_rc, query_rc, roundtrip_rc, gaps_rc, export_rc) == (0, 0, 0, 0, 0)
    assert "Cassandra Runtime Wiring Audit" in output
    assert "Live receive proven: `false`" in output
    assert Path(export_root / "cassandra_runtime_wiring_audit.json").exists()


def test_audit_module_has_no_telegram_or_secret_read_runtime_imports():
    source = Path("cassandra_runtime_wiring_audit.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert "from telegram import" not in source
    assert "from telegram.ext" not in source
    assert "ApplicationBuilder" not in source
    assert "os.environ" not in source
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            assert "cassandra_sender" not in ast.unparse(node)
    for node in ast.walk(tree):
        assert not (isinstance(node, ast.keyword) and node.arg == "shell" and getattr(node.value, "value", None) is True)
    assert all(value is False for value in NO_AUTHORITY_FLAGS.values())

import ast
import sqlite3
from pathlib import Path

from agent_lane_registry import seed_agent_lane_registry
from agent_presence import build_agent_presence_snapshot
from telegram_agent_intake import (
    NO_AUTHORITY_FLAGS,
    build_telegram_agent_intake_read_model,
    build_telegram_agent_intake_report,
    check_telegram_agent_intake,
    export_telegram_agent_intake_read_model,
    record_maestro_listener_text_update,
    record_cassandra_listener_text_update,
    record_telegram_listener_update_safe,
    record_telegram_update,
    telegram_agent_intake_table_names,
)
from scripts.check_telegram_agent_intake import main as check_main
from scripts.export_telegram_agent_intake_read_model import main as export_main
from scripts.query_telegram_agent_intake import main as query_main


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
    tables = set(telegram_agent_intake_table_names(tmp_path / "ledger.sqlite"))

    assert {
        "telegram_agent_intake_runs",
        "telegram_agent_update_records",
        "telegram_agent_intent_links",
        "telegram_agent_route_results",
        "telegram_agent_storage_receipts",
        "telegram_agent_blockers",
    } <= tables


def test_synthetic_message_stores_governed_sqlite_and_routes(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    seed_agent_lane_registry(db_path=db_path, run_id="agents")

    result = record_telegram_update(
        db_path=db_path,
        text="Chief, status check from gig.",
        source_channel="synthetic_dry_run",
        source_message_id="synthetic_message_1",
        agent_target="chief",
        run_id="telegram_run",
        create_work_board_card=True,
    )
    update = _row(
        db_path,
        """
SELECT agent_target, operator_message, message_text_stored, raw_payload_stored,
       chat_id_stored, routed_to_intent_inbox, intent_record_id,
       telegram_send_allowed, command_execution_allowed
FROM telegram_agent_update_records
WHERE update_record_id = ?
""",
        (result.update_record_id,),
    )
    intent = _row(db_path, "SELECT source_kind, routed_agent_id, execution_allowed FROM intent_records WHERE intent_id = ?", (result.intent_record_id,))
    receipt = _row(
        db_path,
        "SELECT raw_payload_stored, message_text_stored, command_execution_allowed, telegram_send_allowed FROM telegram_agent_storage_receipts WHERE update_record_id = ?",
        (result.update_record_id,),
    )

    assert result.routed_to_intent_inbox is True
    assert result.route_status == "routed"
    assert result.routed_agent_id == "chief"
    assert result.work_board_card_id is not None
    assert tuple(update) == ("chief", 1, 0, 0, 0, 1, result.intent_record_id, 0, 0)
    assert tuple(intent) == ("telegram", "chief", 0)
    assert tuple(receipt) == (0, 0, 0, 0)


def test_listener_target_prefix_routes_to_expected_agent_without_full_text_storage(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    seed_agent_lane_registry(db_path=db_path, run_id="agents")

    result = record_telegram_update(
        db_path=db_path,
        text="summarize what changed",
        source_channel="cassandra_listener",
        agent_target="cassandra",
        source_message_id="msg2",
        run_id="telegram_cassandra_run",
    )
    update = _row(
        db_path,
        "SELECT agent_target, message_text_hash, message_text_excerpt, message_text_stored, raw_payload_stored FROM telegram_agent_update_records WHERE update_record_id = ?",
        (result.update_record_id,),
    )
    intent = _row(db_path, "SELECT routed_agent_id, routed_lane_id, intent_text_preview FROM intent_records WHERE intent_id = ?", (result.intent_record_id,))

    assert result.routed_agent_id == "cassandra"
    assert tuple(intent)[:2] == ("cassandra", "operator_comms")
    assert intent["intent_text_preview"].startswith("Cassandra, summarize")
    assert update["agent_target"] == "cassandra"
    assert update["message_text_hash"]
    assert update["message_text_excerpt"] == "summarize what changed"
    assert update["message_text_stored"] == 0
    assert update["raw_payload_stored"] == 0


def test_cassandra_listener_text_helper_accepts_you_online_yet_without_send(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    seed_agent_lane_registry(db_path=db_path, run_id="agents")

    update_id = record_cassandra_listener_text_update(
        db_path=db_path,
        text="You online yet?",
        source_message_id="live_receive_fixture",
    )
    update = _row(
        db_path,
        """
SELECT source_channel, agent_target, operator_message, message_text_stored,
       raw_payload_stored, chat_id_stored, routed_to_intent_inbox,
       intent_record_id, telegram_send_allowed, command_execution_allowed
FROM telegram_agent_update_records
WHERE update_record_id = ?
""",
        (update_id,),
    )
    intent = _row(
        db_path,
        "SELECT routed_agent_id, routed_lane_id, execution_allowed FROM intent_records WHERE intent_id = ?",
        (update["intent_record_id"],),
    )

    assert tuple(update) == (
        "cassandra_listener",
        "cassandra",
        1,
        0,
        0,
        0,
        1,
        update["intent_record_id"],
        0,
        0,
    )
    assert tuple(intent) == ("cassandra", "operator_comms", 0)


def test_maestro_registry_and_listener_helper_are_metadata_only(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    update_id = record_maestro_listener_text_update(
        db_path=db_path,
        text="Maestro, what's going on?",
        source_message_id="maestro_live_fixture",
    )
    update = _row(
        db_path,
        """
SELECT source_channel, agent_target, operator_message, message_text_stored,
       raw_payload_stored, chat_id_stored, routed_to_intent_inbox,
       intent_record_id, blocked_reason, telegram_send_allowed,
       command_execution_allowed, external_api_send_allowed
FROM telegram_agent_update_records
WHERE update_record_id = ?
""",
        (update_id,),
    )
    read_model = build_telegram_agent_intake_read_model(db_path=db_path)
    maestro = next(row for row in read_model["agents"] if row["agent_id"] == "maestro")

    assert tuple(update) == (
        "maestro_listener",
        "maestro",
        1,
        0,
        0,
        0,
        0,
        None,
        "route_intent_disabled",
        0,
        0,
        0,
    )
    assert maestro["outward_name"] == "Maestro"
    assert maestro["telegram_surface"] == "maestro_listener.py"
    assert maestro["service_surface"] == "systemd/user/maestro-listener.service.in"
    assert maestro["governed_listener_hook_available"] is True
    assert maestro["telegram_send_allowed"] is False


def test_cassandra_unverified_listener_text_is_metadata_only(tmp_path):
    db_path = tmp_path / "ledger.sqlite"

    update_id = record_cassandra_listener_text_update(
        db_path=db_path,
        text="Cassandra, receive-only test from gig: You online yet?",
        source_message_id="unverified_fixture",
        source_user_label="unverified_sender",
        operator_message=False,
        route_intent=False,
    )
    update = _row(
        db_path,
        """
SELECT source_channel, agent_target, operator_message, routed_to_intent_inbox,
       intent_record_id, blocked_reason, raw_payload_stored, message_text_stored,
       telegram_send_allowed, command_execution_allowed
FROM telegram_agent_update_records
WHERE update_record_id = ?
""",
        (update_id,),
    )

    assert tuple(update) == (
        "cassandra_listener",
        "cassandra",
        0,
        0,
        None,
        "non_operator_message_metadata_only",
        0,
        0,
        0,
        0,
    )


def test_cassandra_live_report_distinguishes_live_synthetic_and_no_proof(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    seed_agent_lane_registry(db_path=db_path, run_id="agents")

    record_telegram_update(
        db_path=db_path,
        text="Cassandra, receive-only test from gig: You online yet?",
        source_channel="synthetic_cassandra_wiring_audit",
        source_message_id="synthetic_fixture",
        agent_target="cassandra",
    )
    synthetic_only = build_telegram_agent_intake_report(db_path=db_path, report="cassandra-live")
    assert synthetic_only["counts"]["cassandra_live_listener_count"] == 0
    assert synthetic_only["counts"]["cassandra_synthetic_count"] == 1
    assert synthetic_only["counts"]["cassandra_no_live_receive_proof"] is True

    record_cassandra_listener_text_update(
        db_path=db_path,
        text="Capital Hilton invoice fact update.",
        source_message_id="live_capital_fixture",
    )
    live_report = build_telegram_agent_intake_report(db_path=db_path, report="cassandra-live")

    assert live_report["counts"]["cassandra_live_listener_count"] == 1
    assert live_report["counts"]["cassandra_live_operator_count"] == 1
    assert live_report["counts"]["cassandra_synthetic_count"] == 1
    assert live_report["counts"]["cassandra_no_live_receive_proof"] is False
    assert any(row["source_channel"] == "cassandra_listener" for row in live_report["rows"])


def test_non_operator_message_is_metadata_only_and_not_routed(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    result = record_telegram_update(
        db_path=db_path,
        text="hello",
        source_channel="cassandra_listener",
        agent_target="cassandra",
        operator_message=False,
        route_intent=True,
        run_id="non_operator_run",
    )
    update = _row(
        db_path,
        "SELECT operator_message, routed_to_intent_inbox, intent_record_id, blocked_reason FROM telegram_agent_update_records WHERE update_record_id = ?",
        (result.update_record_id,),
    )

    assert result.intent_record_id is None
    assert tuple(update) == (0, 0, None, "non_operator_message_metadata_only")


def test_check_creates_dry_run_proof_blockers_and_cards(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    build_agent_presence_snapshot(db_path=db_path, run_id="presence_run")

    result = check_telegram_agent_intake(db_path=db_path, run_id="check_run")
    report = build_telegram_agent_intake_report(db_path=db_path, report="agents")
    cards = _rows(
        db_path,
        """
SELECT title, execution_allowed, auto_approval_allowed, auto_execute_allowed
FROM work_board_cards
WHERE source_id LIKE 'telegram_agent_intake:%'
ORDER BY title
""",
    )

    assert result.governed_storage_available is True
    assert result.dry_run_intent_id
    assert result.dry_run_status == "routed"
    assert result.agent_count == 6
    assert report["counts"]["update_count"] >= 1
    assert any(row["agent_id"] == "cassandra" and row["outward_name"] == "Clara Reid" for row in report["rows"])
    assert any(row["agent_id"] == "maestro" and row["telegram_surface"] == "maestro_listener.py" for row in report["rows"])
    assert cards
    assert all(row["execution_allowed"] == 0 for row in cards)
    assert all(row["auto_approval_allowed"] == 0 for row in cards)
    assert all(row["auto_execute_allowed"] == 0 for row in cards)


def test_read_model_export_and_cli_work(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "read_models"

    check_rc = check_main(["--db", str(db_path), "--run-id", "cli_check", "--format", "operator"])
    query_rc = query_main(["--db", str(db_path), "--report", "summary", "--format", "operator"])
    agents_rc = query_main(["--db", str(db_path), "--report", "agents", "--format", "operator"])
    cassandra_live_rc = query_main(["--db", str(db_path), "--report", "cassandra-live", "--format", "operator"])
    export_rc = export_main(["--db", str(db_path), "--export-root", str(export_root), "--format", "operator"])
    read_model = build_telegram_agent_intake_read_model(db_path=db_path)
    export = export_telegram_agent_intake_read_model(db_path=db_path, export_root=export_root)
    output = capsys.readouterr().out

    assert check_rc == 0
    assert query_rc == 0
    assert agents_rc == 0
    assert cassandra_live_rc == 0
    assert export_rc == 0
    assert "Telegram Agent Intake" in output
    assert Path(export_root / "telegram_agent_intake.json").exists()
    assert Path(export_root / "telegram_agent_intake_OPERATOR.md").exists()
    assert read_model["governed_storage_available"] is True
    assert read_model["no_authority_flags"]["telegram_send_allowed"] is False
    assert export["governed_storage_available"] is True


def test_safe_listener_hook_never_raises_or_prints_message_text(tmp_path, monkeypatch, capsys):
    import telegram_agent_intake

    def fail_record(**_kwargs):
        raise RuntimeError("secret failure text should not include message body")

    monkeypatch.setattr(telegram_agent_intake, "record_telegram_update", fail_record)
    result = record_telegram_listener_update_safe(
        text="Chief, this body should not be printed",
        source_channel="chief_listener",
        agent_target="chief",
    )
    output = capsys.readouterr().out

    assert result is None
    assert "Chief, this body" not in output
    assert "RuntimeError" in output


def test_listener_files_include_governed_hook_without_exposing_tokens():
    for path in (
        Path("chief_listener.py"),
        Path("cassandra_listener.py"),
        Path("producer_listener.py"),
        Path("chief_guardian_listener.py"),
        Path("maestro_listener.py"),
    ):
        source = path.read_text(encoding="utf-8")
        if path.name == "cassandra_listener.py":
            assert "record_cassandra_listener_text_update" in source
        elif path.name == "maestro_listener.py":
            assert "record_maestro_listener_text_update" in source
        else:
            assert "record_telegram_listener_update_safe" in source
        assert "BOT_TOKEN =" in source or "_token =" in source
        assert "print(BOT_TOKEN" not in source
        assert "print(_token" not in source
        if path.name == "cassandra_listener.py":
            assert "chat_id={sender_chat_id}" not in source
            assert "user_id={update.effective_user.id" not in source
            assert "recorded forward: {f_name} -> {f_id}" not in source


def test_static_forbids_send_network_secret_or_command_execution_in_intake_module():
    source = Path("telegram_agent_intake.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        assert not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "system")
        assert not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"run", "Popen", "call", "check_call", "check_output"}
        )
        assert not (isinstance(node, ast.keyword) and node.arg == "shell" and getattr(node.value, "value", None) is True)
    lowered = source.lower()
    for token in ("requests", "httpx", "urllib", "socket", "send_message", "reply_text", "applicationbuilder", "bot_token"):
        assert token not in lowered
    assert all(value is False for value in NO_AUTHORITY_FLAGS.values())

import ast
import json
import re
import sqlite3
from pathlib import Path

import cassandra_listener_governed_intake_synthetic_proof as proof
from scripts.export_cassandra_listener_governed_intake_synthetic_proof import main as cli_main


FIXED_NOW = "2026-05-17T12:00:00+00:00"


def _row(db_path: Path, sql: str, params=()):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def test_synthetic_receive_creates_governed_intake_metadata(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    payload = proof.build_cassandra_listener_governed_intake_synthetic_proof(
        db_path=db_path,
        generated_at=FIXED_NOW,
    )
    route = payload["route_summary"]

    assert payload["schema_version"] == "cassandra_listener_governed_intake_synthetic_proof_v0"
    assert payload["synthetic_receive_proven"] is True
    assert route["routed_agent_id"] == "cassandra"
    assert route["routed_lane_id"] == "operator_comms"
    assert route["intent_record_id"]
    assert route["work_board_card_id"]
    assert route["agent_work_packet_id"]
    assert payload["blockers"] == []


def test_raw_full_body_is_not_stored_and_bounded_excerpt_hash_rules_are_respected(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    payload = proof.build_cassandra_listener_governed_intake_synthetic_proof(db_path=db_path)
    update = _row(
        db_path,
        """
SELECT message_text_hash, message_text_excerpt, message_text_stored,
       raw_payload_stored, raw_payload_storage_allowed
FROM telegram_agent_update_records
WHERE source_channel = ?
""",
        (proof.SOURCE_CHANNEL,),
    )
    serialized = json.dumps(payload, sort_keys=True)

    assert update["message_text_hash"] == proof._message_hash(proof.SYNTHETIC_MESSAGE)
    assert update["message_text_stored"] == 0
    assert update["raw_payload_stored"] == 0
    assert update["raw_payload_storage_allowed"] == 0
    assert len(update["message_text_excerpt"]) < len(proof.SYNTHETIC_MESSAGE)
    assert proof.SYNTHETIC_MESSAGE not in serialized
    assert payload["message_proof"]["stored_excerpt_truncated"] is True
    assert payload["raw_body_stored"] is False


def test_no_send_reply_network_runtime_or_repo_b_authority_is_added(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    payload = proof.build_cassandra_listener_governed_intake_synthetic_proof(db_path=db_path)
    update = _row(
        db_path,
        """
SELECT telegram_send_allowed, command_execution_allowed,
       action_auto_execute_allowed, approval_bypass_allowed,
       external_api_send_allowed
FROM telegram_agent_update_records
WHERE source_channel = ?
""",
        (proof.SOURCE_CHANNEL,),
    )

    assert tuple(update) == (0, 0, 0, 0, 0)
    assert payload["send_authority_added"] is False
    assert payload["reply_authority_added"] is False
    assert payload["runtime_authority_changed"] is False
    assert payload["repo_b_executed"] is False
    assert payload["network_called"] is False
    assert payload["live_listener_imported_or_executed"] is False


def test_path_observes_intent_work_board_and_agent_packet_without_actions(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    payload = proof.build_cassandra_listener_governed_intake_synthetic_proof(db_path=db_path)
    stages = {stage["stage"]: stage for stage in payload["governed_path_observed"]}
    packet = _row(
        db_path,
        "SELECT execution_allowed, action_created, approval_required FROM agent_work_packets WHERE packet_id = ?",
        (payload["route_summary"]["agent_work_packet_id"],),
    )
    card = _row(
        db_path,
        """
SELECT execution_allowed, auto_approval_allowed, auto_execute_allowed, agent_activation_allowed
FROM work_board_cards
WHERE card_id = ?
""",
        (payload["route_summary"]["work_board_card_id"],),
    )

    assert stages["telegram_agent_intake"]["observed"] is True
    assert stages["intent_records"]["observed"] is True
    assert stages["work_board"]["observed"] is True
    assert stages["agent_work_packet"]["observed"] is True
    assert stages["operator_action_guardian_hitl_if_actionable"]["observed"] is False
    assert tuple(packet) == (0, 0, 1)
    assert tuple(card) == (0, 0, 0, 0)


def test_export_writes_json_and_operator_packet_with_live_verification_instructions(tmp_path):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "generated" / "read_models"
    summary = proof.export_cassandra_listener_governed_intake_synthetic_proof(
        db_path=db_path,
        export_root=export_root,
        generated_at=FIXED_NOW,
    )
    payload = json.loads((export_root / "cassandra_listener_governed_intake_synthetic_proof.json").read_text(encoding="utf-8"))
    operator = (export_root / "cassandra_listener_governed_intake_synthetic_proof_OPERATOR.md").read_text(
        encoding="utf-8"
    )

    assert summary["synthetic_receive_proven"] is True
    assert payload["live_receive_proven"] is False
    assert payload["exact_live_test_message"] == proof.LIVE_TEST_MESSAGE
    assert "scripts/query_telegram_agent_intake.py --report cassandra-live --format operator" in "\n".join(
        payload["exact_verification_commands"]
    )
    assert "Live Test For Winship" in operator
    assert proof.LIVE_TEST_MESSAGE in operator


def test_cli_outputs_json_and_operator(tmp_path, capsys):
    db_path = tmp_path / "ledger.sqlite"
    export_root = tmp_path / "generated" / "read_models"

    assert cli_main(["--db", str(db_path), "--export-root", str(export_root), "--format", "json"]) == 0
    json_output = json.loads(capsys.readouterr().out)
    assert json_output["synthetic_receive_proven"] is True

    assert cli_main(["--db", str(db_path), "--export-root", str(export_root), "--format", "operator"]) == 0
    operator_output = capsys.readouterr().out
    assert "Cassandra Governed Intake Synthetic Proof" in operator_output
    assert "Raw body stored: `false`" in operator_output


def test_source_does_not_import_listener_repo_b_subprocess_network_or_shell_tools():
    source_paths = [
        Path("cassandra_listener_governed_intake_synthetic_proof.py"),
        Path("scripts/export_cassandra_listener_governed_intake_synthetic_proof.py"),
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)
    for path in source_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            assert not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"run", "Popen", "call", "check_call", "check_output", "system"}
            )
    forbidden_patterns = [
        r"^\s*import\s+cassandra_listener\b",
        r"^\s*from\s+cassandra_listener\b",
        r"__import__\(",
        r"^\s*import\s+subprocess\b",
        r"^\s*from\s+subprocess\b",
        r"^\s*import\s+requests\b",
        r"^\s*from\s+requests\b",
        r"^\s*import\s+socket\b",
        r"os\.system\s*\(",
        r"subprocess\.",
        r"Popen\s*\(",
        r"shell\s*=\s*True",
        r"/home/openclaw_external/openclaw-runtime",
    ]
    for pattern in forbidden_patterns:
        assert re.search(pattern, source, flags=re.MULTILINE) is None

import ast
import json
import re
import sqlite3
from pathlib import Path

import pytest

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
    assert payload["live_receive_wired"] is True
    assert payload["live_test_required"] is True
    assert route["routed_agent_id"] == "cassandra"
    assert route["routed_lane_id"] == "operator_comms"
    assert route["intent_record_id"]
    assert route["work_board_card_id"]
    assert route["agent_work_packet_id"]
    assert payload["blockers"] == []


def test_live_listener_receive_path_is_wired_before_reply_or_runtime_paths():
    wiring = proof.inspect_cassandra_listener_receive_wiring()

    assert wiring["live_receive_wired"] is True
    assert wiring["hook_imported"] is True
    assert wiring["claim_imported"] is True
    assert wiring["hook_call_present"] is True
    assert wiring["claim_call_present"] is True
    assert wiring["authorization_rejection_present"] is True
    assert wiring["hook_after_text_strip"] is True
    assert wiring["authorization_rejection_before_claim"] is True
    assert wiring["claim_before_governed_intake"] is True
    assert wiring["claim_before_any_reply"] is True
    assert wiring["claim_before_any_runtime"] is True
    assert wiring["operator_message_gates_routing"] is True
    assert wiring["unverified_sender_dropped_before_metadata"] is True
    assert wiring["unverified_sender_metadata_only"] is False
    assert wiring["source_channel"] == "cassandra_listener"
    assert wiring["listener_imported_or_executed"] is False
    assert wiring["service_restarted"] is False
    assert wiring["send_authority_added"] is False
    assert wiring["reply_authority_added"] is False
    assert wiring["runtime_authority_changed"] is False


_LISTENER_PROOF_STATEMENTS = {
    "reject": """if not is_authorized_user and not is_designated_contact:\n    return""",
    "claim": """if not claim_listener_update(update, role=\"cassandra\", source_channel=\"cassandra_listener\"):\n    return""",
    "text": "text = update.message.text.strip()",
    "hook": """record_cassandra_listener_text_update(
    text=text,
    source_user_label=source_user_label,
    operator_message=is_authorized_user,
    route_intent=is_authorized_user,
)""",
    "reply": "await update.message.reply_text(\"ok\")",
    "runtime": "await _run_request_with_timeout_contract(text=text)",
}


def _write_listener_proof_fixture(tmp_path: Path, order: tuple[str, ...]) -> Path:
    body = "\n".join(
        "\n".join(f"    {line}" for line in _LISTENER_PROOF_STATEMENTS[statement].splitlines())
        for statement in order
    )
    target = tmp_path / "cassandra_listener.py"
    target.write_text(
        """from telegram_agent_intake import (
    claim_listener_update,
    record_cassandra_listener_text_update,
)

async def handle_message(update, context):
    is_authorized_user = True
    is_designated_contact = False
    source_user_label = "operator"
"""
        + body
        + "\n",
        encoding="utf-8",
    )
    return target


def test_ast_wiring_proof_accepts_grouped_import_and_required_security_order(tmp_path):
    target = _write_listener_proof_fixture(
        tmp_path,
        ("reject", "claim", "text", "hook", "reply", "runtime"),
    )

    wiring = proof.inspect_cassandra_listener_receive_wiring(target)

    assert wiring["hook_imported"] is True
    assert wiring["claim_imported"] is True
    assert wiring["authorization_rejection_before_claim"] is True
    assert wiring["claim_before_governed_intake"] is True
    assert wiring["claim_before_any_reply"] is True
    assert wiring["claim_before_any_runtime"] is True
    assert wiring["unverified_sender_dropped_before_metadata"] is True
    assert wiring["live_receive_wired"] is True


@pytest.mark.parametrize(
    ("order", "failed_assertion"),
    (
        (("claim", "reject", "text", "hook", "reply", "runtime"), "authorization_rejection_before_claim"),
        (("text", "hook", "reject", "claim", "reply", "runtime"), "unverified_sender_dropped_before_metadata"),
        (("reject", "reply", "claim", "text", "hook", "runtime"), "claim_before_any_reply"),
        (("reject", "runtime", "claim", "text", "hook", "reply"), "claim_before_any_runtime"),
    ),
)
def test_ast_wiring_proof_rejects_each_unsafe_order(tmp_path, order, failed_assertion):
    target = _write_listener_proof_fixture(tmp_path, order)

    wiring = proof.inspect_cassandra_listener_receive_wiring(target)

    assert wiring[failed_assertion] is False
    assert wiring["live_receive_wired"] is False
    if failed_assertion == "unverified_sender_dropped_before_metadata":
        assert wiring["unverified_sender_metadata_only"] is True


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
    assert summary["live_receive_wired"] is True
    assert summary["live_test_required"] is True
    assert payload["live_receive_proven"] is False
    assert payload["live_listener_wiring"]["live_receive_wired"] is True
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
    assert "Cassandra Governed Intake Receive Wiring Proof" in operator_output
    assert "Live receive wired: `true`" in operator_output
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

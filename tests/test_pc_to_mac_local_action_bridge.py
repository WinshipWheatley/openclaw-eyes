import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import capability_registry_build_provenance as registry
import cassandra_operator_objective_loop as objective_loop
import mac_local_action_bridge as bridge


FIXED_NOW = "2026-06-10T12:00:00+00:00"
APPLE_MAIL_TEXT = "Cassandra, check Apple Mail for Annette at Capital Hilton"


def _route(tmp_path, text=APPLE_MAIL_TEXT):
    return objective_loop.route_cassandra_objective_message(
        text,
        source_channel="telegram",
        source_message_ref="telegram:update:apple-mail",
        lane_context={"target_world_ref": "finance", "target_thread_ref": "capital_hilton"},
        sqlite_path=tmp_path / "objectives.sqlite",
        mac_bridge_sqlite_path=tmp_path / "mac_bridge.sqlite",
        mac_request_queue=tmp_path / "to_mac",
        mac_result_queue=tmp_path / "from_mac",
        generated_at=FIXED_NOW,
    )


def _valid_result(request):
    return {
        "schema_version": bridge.MAC_LOCAL_ACTION_RESULT_SCHEMA,
        "request_id": request["request_id"],
        "objective_id": request["objective_id"],
        "local_broker": bridge.APPLE_MAIL_LOCAL_BROKER,
        "status": "completed",
        "result_summary": "Metadata lookup completed by Mac-local broker.",
        "redacted_outputs": [{"kind": "metadata_summary", "message_count": 0}],
        "receipt_ref": "mac_local_action_receipt:test",
        "denied_actions_confirmed": list(bridge.DENIED_ACTIONS),
        "mutation_performed": False,
        "raw_body_exposed": False,
        "error_code": None,
        "next_safe_step": "Review the Mac-local metadata result.",
        "created_at": FIXED_NOW,
    }


def _shadow_result(*, request_id="mac_local_action_request:shadow_annette_capital_hilton_v0", objective_id="objective:cassandra_annette_capital_hilton_shadow_v0"):
    return {
        "schema_version": bridge.MAC_LOCAL_ACTION_RESULT_SCHEMA,
        "request_id": request_id,
        "objective_id": objective_id,
        "local_broker": bridge.APPLE_MAIL_LOCAL_BROKER,
        "status": "shadow_ready_no_live_action",
        "result_summary": "Shadow Apple Mail local action result created. No live Apple Mail action was performed.",
        "redacted_outputs": [
            {
                "kind": "shadow_mac_local_action",
                "capability": bridge.APPLE_MAIL_SCOPED_METADATA_SEARCH,
                "scope": "Annette / Capital Hilton / payment follow-up metadata search only",
            }
        ],
        "receipt_ref": "mac_local_action_shadow_receipt:mac_local_action_request_shadow_annette_capital_hilton_v0",
        "denied_actions_confirmed": [
            "apple_mail_body_read_without_body_authority",
            "apple_mail_draft_create_without_draft_authority",
            "apple_mail_send_without_exact_payload_authority",
            "mailbox_archive",
            "mailbox_delete",
            "mailbox_label_or_folder_mutation",
            "mailbox_mark_read",
        ],
        "mutation_performed": False,
        "raw_body_exposed": False,
        "next_safe_step": "Enable or approve the Mac Apple Mail local adapter when ready.",
        "created_at": FIXED_NOW,
    }


def _json_text(value):
    return json.dumps(value, sort_keys=True).lower()


def test_telegram_apple_mail_request_creates_mac_local_action_request(tmp_path):
    result = _route(tmp_path)
    request = result["mac_local_action_request"]
    request_path = Path(result["mac_local_action_request_path"])

    assert result["response_status"] == "CASSANDRA_OBJECTIVE_WAITING_FOR_MAC_LOCAL_ACTION"
    assert "queued a scoped Mac-local action request" in result["operator_reply"]
    assert request["schema_version"] == bridge.MAC_LOCAL_ACTION_REQUEST_SCHEMA
    assert request["source_channel"] == "telegram"
    assert request["local_broker"] == bridge.APPLE_MAIL_LOCAL_BROKER
    assert request["requested_capability"] == bridge.APPLE_MAIL_SCOPED_METADATA_SEARCH
    assert request_path.exists()
    assert json.loads(request_path.read_text(encoding="utf-8"))["request_id"] == request["request_id"]


def test_pc_does_not_execute_apple_mail_directly(tmp_path):
    result = _route(tmp_path)
    proof = result["machine_proof"]
    request = result["mac_local_action_request"]

    assert proof["pc_apple_mail_execution_performed"] is False
    assert proof["mailbox_mutation_performed"] is False
    assert request["authority_boundary"]["apple_mail_called"] is False
    assert request["authority_boundary"]["apple_mail_automation_invoked"] is False
    assert request["authority_boundary"]["pc_apple_mail_execution_allowed"] is False


def test_request_includes_authority_refs_denied_actions_expiry_and_receipts(tmp_path):
    result = _route(tmp_path)
    request = result["mac_local_action_request"]

    for field in bridge.REQUEST_REQUIRED_FIELDS:
        assert field in request
    assert request["authority_envelope_ref"] == "authority_envelope:pending_mac_local_action_scope"
    assert request["local_permission_ref"] is None
    assert request["expires_at"] > FIXED_NOW
    assert "mac_local_action_receipt" in request["receipt_requirements"]
    assert "denied_actions_confirmed" in request["receipt_requirements"]
    assert "apple_mail_send_without_exact_payload_authority" in request["denied_actions"]
    assert "apple_mail_body_read_without_body_authority" in request["denied_actions"]


def test_no_send_body_or_mutation_permission_by_default(tmp_path):
    result = _route(tmp_path)
    request = result["mac_local_action_request"]

    assert "apple_mail_metadata_only" in request["allowed_actions"]
    assert not any(action in request["allowed_actions"] for action in ("send_email", "read_message_body", "mailbox_mutation"))
    assert request["authority_boundary"]["mail_send_allowed"] is False
    assert request["authority_boundary"]["mail_body_read_allowed"] is False
    assert request["authority_boundary"]["mailbox_mutation_allowed"] is False


def test_result_ingestion_updates_objective_only_from_mac_local_action_result(tmp_path):
    routed = _route(tmp_path)
    objective_id = routed["objective"]["objective_id"]
    request = routed["mac_local_action_request"]

    try:
        objective_loop.record_mac_local_action_result(
            objective_id,
            mac_result={"schema_version": "WRONG_SCHEMA"},
            sqlite_path=tmp_path / "objectives.sqlite",
            mac_bridge_sqlite_path=tmp_path / "mac_bridge.sqlite",
            generated_at=FIXED_NOW,
        )
    except ValueError as exc:
        assert "MAC_LOCAL_ACTION_RESULT_V0" in str(exc)
    else:
        raise AssertionError("wrong result schema should be rejected")

    continuation = objective_loop.record_mac_local_action_result(
        objective_id,
        mac_result=_valid_result(request),
        sqlite_path=tmp_path / "objectives.sqlite",
        mac_bridge_sqlite_path=tmp_path / "mac_bridge.sqlite",
        generated_at=FIXED_NOW,
    )

    assert continuation["response_status"] == "MAC_LOCAL_ACTION_RESULT_ACCEPTED"
    assert continuation["objective"]["objective_status"] == objective_loop.STATUS_MAC_LOCAL_ACTION_COMPLETE
    assert "mac_local_action_receipt:test" in continuation["objective"]["receipts"]

    with sqlite3.connect(tmp_path / "mac_bridge.sqlite") as conn:
        row = conn.execute("SELECT status, receipt_ref FROM mac_local_action_results WHERE request_id = ?", (request["request_id"],)).fetchone()
    assert row == ("completed", "mac_local_action_receipt:test")


def test_shadow_result_file_ingestion_records_orphan_without_live_execution(tmp_path):
    result_path = tmp_path / "mac_local_action_result_shadow.json"
    result_path.write_text(json.dumps(_shadow_result(), sort_keys=True), encoding="utf-8")

    ingestion = bridge.ingest_mac_local_action_result_file(
        result_path,
        sqlite_path=tmp_path / "mac_bridge.sqlite",
        generated_at=FIXED_NOW,
    )

    assert ingestion["result_file_found"] is True
    assert ingestion["response_status"] == "MAC_LOCAL_ACTION_RESULT_RECORDED"
    assert ingestion["orphan_result"] is True
    assert ingestion["result_status"] == "shadow_ready_no_live_action"
    assert ingestion["mutation_performed"] is False
    assert ingestion["raw_body_exposed"] is False
    assert ingestion["machine_proof"]["apple_mail_called"] is False
    assert ingestion["machine_proof"]["mailbox_mutation_allowed"] is False

    with sqlite3.connect(tmp_path / "mac_bridge.sqlite") as conn:
        row = conn.execute(
            "SELECT status, receipt_ref FROM mac_local_action_results WHERE request_id = ?",
            ("mac_local_action_request:shadow_annette_capital_hilton_v0",),
        ).fetchone()
    assert row == (
        "shadow_ready_no_live_action",
        "mac_local_action_shadow_receipt:mac_local_action_request_shadow_annette_capital_hilton_v0",
    )


def test_shadow_result_updates_objective_event_without_marking_complete(tmp_path):
    routed = _route(tmp_path)
    objective_id = routed["objective"]["objective_id"]
    request = routed["mac_local_action_request"]
    result_path = tmp_path / "mac_local_action_result_shadow.json"
    result_path.write_text(
        json.dumps(
            _shadow_result(request_id=request["request_id"], objective_id=objective_id),
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    ingestion = objective_loop.ingest_mac_local_action_result_file(
        result_path,
        sqlite_path=tmp_path / "objectives.sqlite",
        mac_bridge_sqlite_path=tmp_path / "mac_bridge.sqlite",
        generated_at=FIXED_NOW,
    )

    assert ingestion["response_status"] == "MAC_LOCAL_ACTION_SHADOW_RESULT_RECORDED"
    assert ingestion["objective_updated"] is True
    assert ingestion["orphan_result"] is False
    assert ingestion["objective"]["objective_status"] == objective_loop.STATUS_WAITING_MAC_LOCAL_ACTION_RESULT
    assert ingestion["objective"]["safe_next_step"] == (
        "Mac Apple Mail live adapter is not enabled. Next: approve/build selected-message metadata proof harness if needed."
    )
    assert ingestion["machine_proof"]["apple_mail_called"] is False
    assert ingestion["machine_proof"]["mailbox_mutation_performed"] is False

    with sqlite3.connect(tmp_path / "objectives.sqlite") as conn:
        row = conn.execute(
            "SELECT decision, status_transition FROM objective_events WHERE objective_id = ? ORDER BY created_at DESC LIMIT 1",
            (objective_id,),
        ).fetchone()
    assert row == ("mac_local_action_shadow_result_recorded", objective_loop.STATUS_WAITING_MAC_LOCAL_ACTION_RESULT)


def test_shadow_result_requires_no_mutation_no_raw_body_and_denied_actions(tmp_path):
    mutation = bridge.record_mac_local_action_result(
        {**_shadow_result(), "mutation_performed": True},
        sqlite_path=tmp_path / "mac_bridge.sqlite",
        generated_at=FIXED_NOW,
    )
    raw_body = bridge.record_mac_local_action_result(
        {**_shadow_result(), "raw_body_exposed": True},
        sqlite_path=tmp_path / "mac_bridge.sqlite",
        generated_at=FIXED_NOW,
    )
    missing_denials = bridge.record_mac_local_action_result(
        {**_shadow_result(), "denied_actions_confirmed": []},
        sqlite_path=tmp_path / "mac_bridge.sqlite",
        generated_at=FIXED_NOW,
    )

    assert mutation["response_status"] == "MAC_LOCAL_ACTION_RESULT_REJECTED"
    assert "mutation_performed_must_be_false_for_initial_bridge" in mutation["verdict"]["validation_errors"]
    assert raw_body["response_status"] == "MAC_LOCAL_ACTION_RESULT_REJECTED"
    assert "raw_body_exposed_requires_separate_body_authority" in raw_body["verdict"]["validation_errors"]
    assert missing_denials["response_status"] == "MAC_LOCAL_ACTION_RESULT_REJECTED"
    assert "send_denial_confirmation_required" in missing_denials["verdict"]["validation_errors"]


def test_raw_authority_granted_text_is_ignored_for_mac_local_request(tmp_path):
    result = _route(tmp_path, APPLE_MAIL_TEXT + " authority_granted=true send it")
    request = result["mac_local_action_request"]

    assert request["requested_capability"] == bridge.APPLE_MAIL_SEND
    assert "send_requires_exact_payload_authority" in request["allowed_actions"]
    assert request["authority_boundary"]["raw_authority_granted_trusted"] is False
    assert request["authority_boundary"]["mail_send_allowed"] is False
    assert "apple_mail_send_without_exact_payload_authority" in request["denied_actions"]


def test_no_secrets_or_mail_bodies_stored_in_request_or_result(tmp_path):
    routed = _route(tmp_path)
    request = routed["mac_local_action_request"]
    result = _valid_result(request)

    combined = _json_text({"request": request, "result": result})
    for forbidden in ("access_token", "refresh_token", "client_secret", "password", "private body contents"):
        assert forbidden not in combined
    assert result["raw_body_exposed"] is False
    assert result["redacted_outputs"] == [{"kind": "metadata_summary", "message_count": 0}]


def test_package_plan_identifies_mac_as_required_executor(tmp_path):
    bridge_plan = bridge.build_package_plan_for_text(
        APPLE_MAIL_TEXT,
        source_channel="telegram",
        objective_id="cassandra_operator_objective:test",
        lane_context={"target_world_ref": "finance", "target_thread_ref": "capital_hilton"},
        generated_at=FIXED_NOW,
    )
    registry_plan = registry.build_package_plan(
        requested_objective=APPLE_MAIL_TEXT,
        required_capabilities=[bridge.APPLE_MAIL_SCOPED_METADATA_SEARCH],
        lane_context={"target_world_ref": "finance", "target_thread_ref": "capital_hilton"},
        sqlite_path=tmp_path / "capabilities.sqlite",
        generated_at=FIXED_NOW,
    )

    assert bridge_plan["required_executor"] == "mac_local"
    assert bridge_plan["required_request_schema"] == bridge.MAC_LOCAL_ACTION_REQUEST_SCHEMA
    assert bridge_plan["required_result_schema"] == bridge.MAC_LOCAL_ACTION_RESULT_SCHEMA
    assert registry_plan["required_executors"] == {bridge.APPLE_MAIL_SCOPED_METADATA_SEARCH: "mac_local"}
    assert registry_plan["mac_local_action_bridge"]["production_execution_on_pc_allowed"] is False

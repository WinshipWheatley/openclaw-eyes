import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import dynamic_card_packet
import evidence_intake
import first_class_operator_envelope as envelope
import verified_operator_envelope


FIXED_NOW = "2026-06-04T21:15:00+00:00"


def _base_controller_request(*, authority_requested=()):
    return envelope.attach_verified_authority_envelope(
        {
            "request_type": "OPERATOR_CONTROLLER_ACTION_V0",
            "plain_text": "Show details for the current card.",
        },
        operator_ref="operator:winship",
        app_instance_ref="mission_control:mac",
        device_ref="device:macbook",
        device_class="mac",
        session_ref="session:first-class-test",
        source_surface="card",
        current_world_ref="finance",
        current_thread_ref="live_arts_md",
        active_entity_ref="dynamic_card.finance.live_arts_md.evidence_intake.payment_processing",
        controller_action_type="show_details",
        authority_requested=authority_requested,
        created_at=FIXED_NOW,
    )


def _assert_no_unsafe_true(payload):
    assert envelope.unsafe_true_grants(payload) == []


def test_verified_mac_envelope_accepted():
    request = _base_controller_request()

    result = envelope.validate_operator_authority_envelope(request)

    assert result["verification_status"] == "verified"
    assert result["verified"] is True
    assert result["operator_ref"] == "operator:winship"
    assert result["device_class"] == "mac"
    assert result["request_hash"] == envelope.compute_request_hash(request)
    assert result["request_hash_checked"] is True
    assert result["authority_granted"] == []
    assert result["machine_proof"]["envelope_proves_identity_not_business_permission"] is True
    _assert_no_unsafe_true(result)


def test_missing_device_ref_blocks():
    request = _base_controller_request()
    request["operator_authority_envelope"]["device_ref"] = ""
    request["operator_authority_envelope"]["device_verified"] = False
    request["operator_authority_envelope"]["request_hash"] = envelope.compute_request_hash(request)

    result = envelope.validate_operator_authority_envelope(request)

    assert result["verification_status"] == "needs_verification"
    assert result["verified"] is False
    assert "device_ref_missing" in result["blockers"]
    assert "device_verified_false_or_missing" in result["blockers"]


def test_missing_request_hash_blocks():
    request = _base_controller_request()
    request["operator_authority_envelope"]["request_hash"] = ""

    result = envelope.validate_operator_authority_envelope(request)

    assert result["verification_status"] == "needs_verification"
    assert "request_hash_missing" in result["blockers"]
    assert result["authority_granted"] == []


def test_incoming_authority_granted_is_rejected_and_not_trusted():
    request = _base_controller_request()
    request["authority_granted"] = ["email_send"]
    request["operator_authority_envelope"]["request_hash"] = envelope.compute_request_hash(request)

    result = envelope.validate_operator_authority_envelope(request)

    assert result["verification_status"] == "rejected"
    assert "incoming_backend_only_authority_fields_not_accepted" in result["rejected_reasons"]
    assert result["authority_granted"] == []
    assert result["incoming_authority_granted_accepted"] is False


def test_authority_requested_does_not_imply_authority_granted():
    request = _base_controller_request(authority_requested=["stage_plan"])

    result = envelope.validate_operator_authority_envelope(request)

    assert result["verification_status"] == "verified"
    assert result["authority_requested"] == ["stage_plan"]
    assert result["authority_granted"] == []
    assert result["gate_decision_ref"] == ""
    assert result["approval_receipt_ref"] == ""


def _evidence_request(tmp_path: Path):
    artifact = tmp_path / "payment_processing_invoice_2026-1001.png"
    artifact.write_bytes(b"fake payment processing screenshot")
    payload = {
        "request_type": evidence_intake.REQUEST_TYPE,
        "original_request_type": evidence_intake.REQUEST_TYPE,
        "source_surface": "mission_control",
        "current_world_ref": "finance",
        "current_thread_ref": "live_arts_md",
        "claimed_client_ref": "live_arts_md",
        "claimed_workflow_ref": "live_arts_md_payment_watch",
        "artifact_path": str(artifact),
        "artifact_kind": "screenshot",
        "operator_note": "Live Arts MD screenshot shows payment processing for invoice 2026-1001.",
        "privacy_class": "financial_sensitive",
        "intended_use": "payment_proof",
        "authority_boundary": dict(evidence_intake.AUTHORITY_BOUNDARY),
    }
    request = verified_operator_envelope.attach_verified_operator_envelope(
        payload,
        operator_ref="operator:winship",
        app_instance_ref="mission_control:mac",
        device_ref="device:macbook",
        session_ref="session:evidence-with-first-class-envelope",
        created_at=FIXED_NOW,
    )
    request = envelope.attach_verified_authority_envelope(
        request,
        operator_ref="operator:winship",
        app_instance_ref="mission_control:mac",
        device_ref="device:macbook",
        device_class="mac",
        session_ref="session:evidence-with-first-class-envelope",
        source_surface="dropzone",
        current_world_ref="finance",
        current_thread_ref="live_arts_md",
        active_entity_ref="dynamic_card.finance.live_arts_md.evidence_intake.payment_processing",
        controller_action_type="attach_proof",
        authority_requested=[],
        created_at=FIXED_NOW,
    )
    request["operator_envelope"]["request_hash"] = verified_operator_envelope.compute_request_hash(request)
    request["operator_authority_envelope"]["request_hash"] = envelope.compute_request_hash(request)
    return request


def test_evidence_intake_can_reference_verified_authority_envelope(tmp_path):
    request = _evidence_request(tmp_path)

    authority_result = envelope.validate_operator_authority_envelope(request)
    record = evidence_intake.build_intake_record(request, generated_at=FIXED_NOW)

    assert authority_result["verification_status"] == "verified"
    assert record["status"] == "EVIDENCE_INTAKE_READY"
    assert record["operator_authority_envelope"]["envelope_id"] == authority_result["envelope_id"]
    assert record["operator_authority_envelope"]["authority_granted"] == []
    assert record["dynamic_card"]["actions"][0]["requires_operator_authority_envelope"] is True
    assert record["dynamic_card"]["actions"][0]["operator_authority_envelope_ref"] == authority_result["envelope_id"]


def test_dynamic_card_actions_reference_envelope_requirement():
    packet = dynamic_card_packet.build_latest_packet(generated_at=FIXED_NOW)
    cards = {card["card_id"]: card for card in packet["cards"]}
    card = cards["dynamic_card.finance.live_arts_md.evidence_intake.payment_processing"]

    assert card["actions"]
    assert all(action["requires_operator_authority_envelope"] is True for action in card["actions"])
    assert all(
        action["operator_authority_envelope_contract_ref"]
        == "generated/read_models/first_class_operator_envelope_contract.json"
        for action in card["actions"]
    )
    assert all(action["authority_granted_by_action"] is False for action in card["actions"])
    assert dynamic_card_packet.unsafe_true_grants(packet) == []


def test_export_writes_json_bridge_sqlite_and_wiki(tmp_path):
    result = envelope.export_first_class_operator_envelope(
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "First Class Operator Envelope.md",
        sqlite_path=tmp_path / "system_knowledge" / "first_class_operator_envelope.sqlite",
        generated_at=FIXED_NOW,
    )

    contract = json.loads(Path(result["contract_read_model_path"]).read_text(encoding="utf-8"))
    status = json.loads(Path(result["status_read_model_path"]).read_text(encoding="utf-8"))
    bridge_contract = json.loads(Path(result["bridge_contract_read_model_path"]).read_text(encoding="utf-8"))
    bridge_status = json.loads(Path(result["bridge_status_read_model_path"]).read_text(encoding="utf-8"))

    assert contract == bridge_contract
    assert status == bridge_status
    assert contract["status"] == "FIRST_CLASS_OPERATOR_ENVELOPE_READY"
    assert status["status"] == "FIRST_CLASS_OPERATOR_ENVELOPE_READY"
    assert status["latest_record"]["verification_status"] == "verified"
    assert status["latest_record"]["authority_granted"] == []
    conn = sqlite3.connect(result["sqlite_path"])
    try:
        row = conn.execute(
            """
            SELECT device_class, verification_status, authority_granted_json,
                   gate_decision_ref, approval_receipt_ref
            FROM first_class_operator_envelopes
            """
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "mac"
    assert row[1] == "verified"
    assert json.loads(row[2]) == []
    assert row[3:] == ("", "")
    assert Path(result["wiki_path"]).exists()
    _assert_no_unsafe_true(contract)
    _assert_no_unsafe_true(status)


def test_unsafe_true_grant_scan_clean(tmp_path):
    request = _base_controller_request()
    result = envelope.validate_operator_authority_envelope(request)
    record = envelope.build_envelope_record(request, generated_at=FIXED_NOW)
    contract = envelope.build_contract_read_model(generated_at=FIXED_NOW)
    status = envelope.build_status_read_model(
        sqlite_path=tmp_path / "first_class_operator_envelope.sqlite",
        generated_at=FIXED_NOW,
    )

    assert envelope.unsafe_true_grants(result) == []
    assert envelope.unsafe_true_grants(record) == []
    assert envelope.unsafe_true_grants(contract) == []
    assert envelope.unsafe_true_grants(status) == []

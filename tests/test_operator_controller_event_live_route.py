import json
import shutil
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import first_class_operator_envelope as operator_authority
import openclaw_request_processor as processor
import openclaw_request_response_service as service
import operator_controller_event_router as controller_router


FIXED_NOW = "2026-06-05T13:00:00+00:00"


def _seed_read_models(export_root: Path) -> None:
    export_root.mkdir(parents=True, exist_ok=True)
    for filename in [
        "operator_controller_protocol.json",
        "first_class_operator_envelope_status.json",
        "dynamic_card_packet_latest.json",
        "dynamic_card_lifecycle_policy.json",
        "evidence_intake_status.json",
        "operator_action_payloads.json",
        "system_question_answer_contract.json",
        "workroom_review_decision_status.json",
        "workroom_review_packet_index.json",
        "workroom_review_decision_contract.json",
        "package_event_index.json",
    ]:
        shutil.copy2(ROOT / "generated/read_models" / filename, export_root / filename)


def _controller_event_request(
    *,
    event_type: str,
    world: str,
    thread: str,
    suffix: str,
    selected_card_id: str = "",
    selected_action_id: str = "",
    active_entity_ref: str = "",
    operator_text: str = "",
    artifact_ref: str = "",
    envelope_event_type: str | None = None,
) -> dict:
    controller_action_type = envelope_event_type or event_type
    request = {
        "request_id": f"live_controller_event_{suffix}",
        "request_type": controller_router.REQUEST_TYPE,
        "source_surface": "mission_control",
        "controller_event_type": event_type,
        "controller_action_type": controller_action_type,
        "current_world_ref": world,
        "current_thread_ref": thread,
        "active_entity_ref": active_entity_ref or selected_card_id,
        "selected_card_id": selected_card_id,
        "selected_action_id": selected_action_id,
        "operator_text": operator_text,
        "artifact_ref": artifact_ref,
        "authority_requested": [],
        "authority_boundary": dict(controller_router.AUTHORITY_BOUNDARY),
    }
    envelope = {
        "envelope_id": f"operator_envelope:live:{suffix}",
        "operator_ref": "operator:winship",
        "app_instance_ref": "mission_control:mac",
        "device_ref": "device:macbook",
        "device_class": "mac",
        "session_ref": f"session:live-controller-event:{suffix}",
        "request_hash": "",
        "created_at": FIXED_NOW,
        "source_surface": "dropzone" if event_type == "attach_proof" else "card",
        "current_world_ref": world,
        "current_thread_ref": thread,
        "active_entity_ref": active_entity_ref or selected_card_id,
        "controller_action_type": controller_action_type,
        "authority_requested": [],
        "operator_verified": True,
        "app_instance_verified": True,
        "device_verified": True,
        "session_verified": True,
        "verification_status": operator_authority.VERIFICATION_STATUS_VERIFIED,
        "proof_refs": ["controller_surface:mission_control", "test:first_class_operator_envelope"],
    }
    request["operator_envelope"] = envelope
    request["operator_envelope"]["request_hash"] = operator_authority.compute_request_hash(request)
    return request


def _run_live(tmp_path: Path, request: dict, *, filename_suffix: str) -> tuple[dict, dict, Path]:
    inbox = tmp_path / "inbox"
    response_dir = tmp_path / "responses"
    export_root = tmp_path / "read_models"
    inbox.mkdir(parents=True)
    response_dir.mkdir(parents=True)
    _seed_read_models(export_root)
    request_path = inbox / f"mission_control_controller_event_request_{filename_suffix}.json"
    request_path.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = service.process_one_pending_request(
        inbox=inbox,
        response_dir=response_dir,
        export_root=export_root,
        generated_at=FIXED_NOW,
        mac_handoff_dir=tmp_path / "handoffs",
    )
    assert result.processed_count == 1
    assert result.latest_response
    response_path = Path(result.latest_response["response_file"])
    response = json.loads(response_path.read_text(encoding="utf-8"))
    return response, result.latest_response, export_root


def _router_receipt(response: dict) -> dict:
    receipt = response["detail_disclosure"]["operator_controller_event_router"]
    assert receipt["dynamic_card_response"]
    return receipt


def _unsafe_true_grants(value, path="$"):
    unsafe_names = set(controller_router.UNSAFE_TRUE_KEYS) | {
        "paid",
        "sent",
        "authority_granted",
        "business_action",
    }
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in unsafe_names and child is True:
                found.append(child_path)
            found.extend(_unsafe_true_grants(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_unsafe_true_grants(child, f"{path}[{index}]"))
    return found


def test_live_ask_why_finance_capital_hilton_returns_payment_watch_card(tmp_path):
    response, _published, _export_root = _run_live(
        tmp_path,
        _controller_event_request(
            event_type="ask_why",
            world="finance",
            thread="capital_hilton",
            suffix="ask_why",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            operator_text="Why am I here?",
        ),
        filename_suffix="ask_why",
    )

    receipt = _router_receipt(response)
    assert response["internal_status"] == controller_router.RESPONSE_READY
    assert receipt["backend_route"] == "system_question_answer.contextual_answer"
    assert receipt["current_world_ref"] == "finance"
    assert receipt["current_thread_ref"] == "capital_hilton"
    assert receipt["route_result"]["package_staged"] is False
    assert "Coupa is processing" in response["visible_cards"][0]["plain_summary"]
    assert not _unsafe_true_grants(response)


def test_live_attach_proof_routes_to_evidence_intake_without_marking_paid(tmp_path):
    response, _published, _export_root = _run_live(
        tmp_path,
        _controller_event_request(
            event_type="attach_proof",
            world="finance",
            thread="live_arts_md",
            suffix="attach_proof",
            selected_card_id="dynamic_card.finance.live_arts_md.evidence_intake.payment_processing",
            operator_text="Payment processing screenshot for invoice 2026-1001.",
            artifact_ref="mission_control_drop:live_arts_md_payment_processing_screenshot",
        ),
        filename_suffix="attach_proof",
    )

    receipt = _router_receipt(response)
    assert response["internal_status"] == controller_router.RESPONSE_READY
    assert response["operator_headline"] == "Payment proof received"
    assert receipt["backend_route"] == "evidence_intake.record_candidate_evidence"
    assert receipt["route_result"]["privacy"]["privacy_class"] == "financial_sensitive"
    assert receipt["route_result"]["privacy"]["processing_location"] == "local_only"
    assert receipt["route_result"]["payment"]["paid"] is False
    assert receipt["route_result"]["payment"]["ledger_mutation_performed"] is False
    assert "Ledger remains untouched until payment is confirmed" in response["visible_cards"][0]["plain_summary"]

    conn = sqlite3.connect(tmp_path / "system_knowledge" / "evidence_intake.sqlite")
    row = conn.execute(
        """
        select current_world_ref, current_thread_ref, privacy_class, processing_location,
               paid, ledger_mutation_performed, raw_ocr_text_stored
        from evidence_intake_records
        order by created_at desc limit 1
        """
    ).fetchone()
    conn.close()
    assert row == ("finance", "live_arts_md", "financial_sensitive", "local_only", 0, 0, 0)
    assert not _unsafe_true_grants(response)


def test_live_mark_informational_routes_to_workroom_review_decision_consumer(tmp_path):
    response, _published, _export_root = _run_live(
        tmp_path,
        _controller_event_request(
            event_type="mark_informational",
            world="build",
            thread="build_openclaw_backend",
            suffix="mark_informational",
            selected_card_id="dynamic_card.build.review_packet.current",
            selected_action_id="review_packet.review_packet_c4ec166103f9aa35.mark_review_packet_informational",
            operator_text="Close this as informational.",
        ),
        filename_suffix="mark_informational",
    )

    receipt = _router_receipt(response)
    assert response["internal_status"] == controller_router.RESPONSE_READY
    assert receipt["backend_route"] == "workroom_review_decision_consumer.record_decision_only"
    assert receipt["route_result"]["decision_action"] == "mark_review_packet_informational"
    assert receipt["route_result"]["decision_recorded"] is True
    assert receipt["route_result"]["merge_performed"] is False
    assert receipt["route_result"]["git_push_performed"] is False
    assert not _unsafe_true_grants(response)


def test_live_do_it_capital_hilton_payment_watch_navigates_only(tmp_path):
    response, _published, _export_root = _run_live(
        tmp_path,
        _controller_event_request(
            event_type="do_it",
            world="finance",
            thread="capital_hilton",
            suffix="do_it_payment_watch",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            operator_text="Do it.",
        ),
        filename_suffix="do_it_payment_watch",
    )

    receipt = _router_receipt(response)
    assert response["internal_status"] == controller_router.RESPONSE_READY
    assert receipt["backend_route"] == "operator_action_payloads.navigate"
    assert receipt["route_ref"] == "capital_hilton.payment.open_finance"
    assert receipt["route_result"]["navigation"]["business_action"] is False
    assert receipt["machine_proof"]["navigation_only"] is True
    assert receipt["machine_proof"]["ledger_mutation_performed"] is False
    assert receipt["machine_proof"]["paid_marking_performed"] is False
    assert not _unsafe_true_grants(response)


def test_live_protected_do_it_stages_approval_or_blocks_without_execution(tmp_path):
    response, _published, _export_root = _run_live(
        tmp_path,
        _controller_event_request(
            event_type="do_it",
            world="finance",
            thread="capital_hilton",
            suffix="protected_do_it",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            operator_text="Submit this in Coupa.",
        ),
        filename_suffix="protected_do_it",
    )

    receipt = _router_receipt(response)
    assert response["internal_status"] == controller_router.RESPONSE_READY
    assert receipt["route_status"] == "PROTECTED_ACTION_STAGED_OR_BLOCKED"
    assert receipt["backend_route"] == "approval_request_queue.stage_only"
    assert receipt["machine_proof"]["protected_action_staged_only"] is True
    assert receipt["machine_proof"]["coupa_access_performed"] is False
    assert receipt["machine_proof"]["browser_access_performed"] is False
    assert receipt["machine_proof"]["submit_performed"] is False
    assert not _unsafe_true_grants(response)


def test_live_incoming_authority_granted_rejected_or_ignored(tmp_path):
    request = _controller_event_request(
        event_type="do_it",
        world="finance",
        thread="capital_hilton",
        suffix="incoming_grant",
        operator_text="Do it.",
    )
    request["authority_granted"] = ["email_send"]
    response, _published, _export_root = _run_live(tmp_path, request, filename_suffix="incoming_grant")

    receipt = _router_receipt(response)
    assert response["internal_status"] == controller_router.BLOCKED_WITH_REASON
    assert receipt["incoming_authority_granted_accepted"] is False
    assert receipt["authority_granted"] == []
    assert "incoming_authority_granted_or_backend_gate_fields_not_accepted" in receipt["rejected_reasons"]
    assert response["visible_cards"][0]["status_label"] in {"Blocked", "Needs verification"}
    assert not _unsafe_true_grants(response)


def test_live_missing_verified_envelope_blocks(tmp_path):
    request = {
        "request_id": "live_controller_event_missing_envelope",
        "request_type": controller_router.REQUEST_TYPE,
        "source_surface": "mission_control",
        "controller_event_type": "ask_why",
        "controller_action_type": "ask_why",
        "current_world_ref": "finance",
        "current_thread_ref": "capital_hilton",
        "authority_requested": [],
        "authority_boundary": dict(controller_router.AUTHORITY_BOUNDARY),
    }
    response, _published, _export_root = _run_live(tmp_path, request, filename_suffix="missing_envelope")

    receipt = _router_receipt(response)
    assert response["internal_status"] == controller_router.BLOCKED_WITH_REASON
    assert receipt["route_status"] == "NEEDS_VERIFICATION"
    assert "verified_operator_envelope_required" in receipt["blockers"]
    assert response["visible_cards"][0]["status_label"] == "Needs verification"
    assert not _unsafe_true_grants(response)


def test_live_unknown_event_fails_closed(tmp_path):
    response, _published, _export_root = _run_live(
        tmp_path,
        _controller_event_request(
            event_type="spin_around",
            envelope_event_type="show_details",
            world="finance",
            thread="capital_hilton",
            suffix="unknown_event",
        ),
        filename_suffix="unknown_event",
    )

    receipt = _router_receipt(response)
    assert response["internal_status"] == controller_router.BLOCKED_WITH_REASON
    assert receipt["route_status"] == "UNKNOWN_EVENT_BLOCKED"
    assert "unknown_controller_event_type" in receipt["blockers"]
    assert response["visible_cards"][0]
    assert not _unsafe_true_grants(response)


def test_live_show_details_emits_dynamic_card_and_proof_refs(tmp_path):
    response, _published, _export_root = _run_live(
        tmp_path,
        _controller_event_request(
            event_type="show_details",
            world="finance",
            thread="capital_hilton",
            suffix="show_details",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
        ),
        filename_suffix="show_details",
    )

    receipt = _router_receipt(response)
    assert response["internal_status"] == controller_router.RESPONSE_READY
    assert receipt["backend_route"] == "dynamic_card_packet.proof_drawer"
    assert response["visible_cards"][0]["headline"].startswith("Details:")
    assert receipt["proof_refs"]
    assert not _unsafe_true_grants(response)


def test_live_router_exports_bridge_json_and_sqlite_row(tmp_path):
    response, _published, export_root = _run_live(
        tmp_path,
        _controller_event_request(
            event_type="show_details",
            world="finance",
            thread="capital_hilton",
            suffix="exports",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
        ),
        filename_suffix="exports",
    )
    receipt = _router_receipt(response)

    local_contract = json.loads((export_root / controller_router.CONTRACT_JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    local_status = json.loads((export_root / controller_router.STATUS_JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    bridge_contract = json.loads((tmp_path / "bridge" / controller_router.CONTRACT_JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    bridge_status = json.loads((tmp_path / "bridge" / controller_router.STATUS_JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    assert local_contract == bridge_contract
    assert local_status == bridge_status
    assert local_status["latest_receipt"]["receipt_id"] == receipt["receipt_id"]

    conn = sqlite3.connect(tmp_path / "system_knowledge" / "operator_controller_event_router.sqlite")
    row = conn.execute(
        """
        select controller_event_type, route_status, raw_internal_status,
               ledger_mutation_performed, paid_marking_performed,
               submit_performed, business_action_performed
        from controller_event_receipts
        where receipt_id=?
        """,
        (receipt["receipt_id"],),
    ).fetchone()
    conn.close()
    assert row == ("show_details", "ROUTED", controller_router.RESPONSE_READY, 0, 0, 0, 0)
    assert not _unsafe_true_grants(local_contract)
    assert not _unsafe_true_grants(local_status)

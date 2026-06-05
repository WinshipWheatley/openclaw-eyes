import json
import shutil
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import first_class_operator_envelope as operator_authority
import operator_controller_event_router as router


FIXED_NOW = "2026-06-05T12:00:00+00:00"


def _seed_read_models(tmp_path: Path) -> Path:
    read_model_root = tmp_path / "read_models"
    read_model_root.mkdir(parents=True, exist_ok=True)
    required = [
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
    ]
    for filename in required:
        shutil.copy2(ROOT / "generated/read_models" / filename, read_model_root / filename)
    return read_model_root


def _event_request(
    *,
    event_type: str,
    world: str,
    thread: str,
    selected_card_id: str = "",
    selected_action_id: str = "",
    active_entity_ref: str = "",
    operator_text: str = "",
    artifact_ref: str = "",
    envelope_event_type: str | None = None,
) -> dict:
    payload = {
        "request_id": f"controller_event_test_{event_type}_{world}_{thread}",
        "request_type": router.REQUEST_TYPE,
        "controller_event_type": event_type,
        "controller_action_type": envelope_event_type or event_type,
        "current_world_ref": world,
        "current_thread_ref": thread,
        "active_entity_ref": active_entity_ref,
        "selected_card_id": selected_card_id,
        "selected_action_id": selected_action_id,
        "operator_text": operator_text,
        "artifact_ref": artifact_ref,
        "authority_requested": [],
        "authority_boundary": dict(router.AUTHORITY_BOUNDARY),
    }
    return operator_authority.attach_verified_authority_envelope(
        payload,
        operator_ref="operator:winship",
        app_instance_ref="mission_control:mac",
        device_ref="device:macbook",
        device_class="mac",
        session_ref=f"session:test:{event_type}",
        source_surface="dropzone" if event_type == "attach_proof" else "card",
        current_world_ref=world,
        current_thread_ref=thread,
        active_entity_ref=active_entity_ref or selected_card_id,
        controller_action_type=envelope_event_type or event_type,
        authority_requested=[],
        proof_refs=["controller_surface:mission_control", "test:first_class_operator_envelope"],
        created_at=FIXED_NOW,
    )


def _mac_dispatcher_request(
    *,
    event_type: str = "open_lane",
    controller_action_type: str | None = None,
    selected_card_id: str = "dynamic_card.finance.capital_hilton.payment_watch",
    selected_action_id: str = "capital_hilton.payment.open_finance",
    request_id: str = "finance_open_lane_capital_hilton_payment_open_finance_20260605T161818Z_3a8c5dbcc6c0",
    verification_overrides: dict | None = None,
) -> dict:
    authority_boundary = dict(router.AUTHORITY_BOUNDARY)
    current_context = {
        "active_surface_ref": "helm_dynamic_card",
        "current_thread_ref": "capital_hilton",
        "current_world_ref": "finance",
        "requested_mode": "operator",
        "selected_entity_ref": "capital_hilton",
        "source_surface": "mission_control",
        "visible_lane_ref": "capital_hilton",
    }
    request = {
        "active_surface_ref": "helm_dynamic_card",
        "app_instance_ref": "sha256:b7efb2d5f3ec5e0b0f1a77589c9c276612600550161e555f4fe5384f98fd3e07",
        "app_instance_verified": True,
        "authority_boundary": authority_boundary,
        "authority_requested": [],
        "browser_access_performed": False,
        "business_action_performed": False,
        "business_state_mutation_performed": False,
        "child_agent_run_performed": False,
        "context": dict(current_context),
        "controller_event_type": event_type,
        "controller_action_type": controller_action_type or event_type,
        "coupa_access_performed": False,
        "created_at": "2026-06-05T16:18:18Z",
        "current_context": dict(current_context),
        "current_thread_ref": "capital_hilton",
        "current_world_ref": "finance",
        "device_class": "mac",
        "device_ref": "sha256:b191fdb712c2c5d281944b1ab6435791fae47f1ca78fdd184cfb0fc36dd2b2d7",
        "device_verified": True,
        "email_send_performed": False,
        "event": {
            "authority_boundary": authority_boundary,
            "authority_requested": [],
            "controller_event_type": event_type,
            "selected_action_id": selected_action_id,
            "selected_card_id": selected_card_id,
        },
        "external_provider_connected": False,
        "git_push_performed": False,
        "gmail_access_performed": False,
        "incoming_authority_granted_accepted": False,
        "incoming_authority_granted_fields": [],
        "input_surface": "helm_dynamic_card",
        "kind": router.REQUEST_TYPE,
        "ledger_mutation_performed": False,
        "ledger_posting_performed": False,
        "mac_wrote_request_only": True,
        "merge_performed": False,
        "no_external_action": True,
        "operator_authority_envelope": {
            "app_instance_ref": "sha256:b7efb2d5f3ec5e0b0f1a77589c9c276612600550161e555f4fe5384f98fd3e07",
            "app_instance_verified": True,
            "device_class": "mac",
            "device_ref": "sha256:b191fdb712c2c5d281944b1ab6435791fae47f1ca78fdd184cfb0fc36dd2b2d7",
            "device_verified": True,
            "operator_ref": "hwinshipwheatley",
            "operator_verified": True,
            "request_hash": "sha256:3a8c5dbcc6c0ec3a64a4ebcb304bfa00bf064ca17fe479d0b6f302e579ed1245",
            "session_ref": "sha256:49fe9e9d6dba9ac5fc5acfff73769d92c69ae58c2a38881305132ffe2d0fe340",
            "session_verified": True,
            "verification_status": operator_authority.VERIFICATION_STATUS_VERIFIED,
        },
        "operator_ref": "hwinshipwheatley",
        "operator_verified": True,
        "origin_surface": "mission_control_mac",
        "paid_marking_performed": False,
        "payload_hash": "sha256:47f21d9686398741a48e014ca6de2b57326260aa3a1893f8de8e8ff91b4d8a7c",
        "pdf_export_performed": False,
        "portal_submit_performed": False,
        "request_hash": "sha256:3a8c5dbcc6c0ec3a64a4ebcb304bfa00bf064ca17fe479d0b6f302e579ed1245",
        "request_hash_checked": True,
        "request_id": request_id,
        "request_type": router.REQUEST_TYPE,
        "requested_mode": "operator",
        "result_receipt_required": True,
        "schema_version": "operator_controller_event_request_v0",
        "selected_action_id": selected_action_id,
        "selected_card_id": selected_card_id,
        "selected_entity_ref": "capital_hilton",
        "session_ref": "sha256:49fe9e9d6dba9ac5fc5acfff73769d92c69ae58c2a38881305132ffe2d0fe340",
        "session_verified": True,
        "source_channel": "mission_control_dynamic_card",
        "source_request_id": request_id,
        "source_surface": "mission_control",
        "type": router.REQUEST_TYPE,
        "verification_status": operator_authority.VERIFICATION_STATUS_VERIFIED,
        "visible_lane_ref": "capital_hilton",
        "workbook_body_read": False,
        "workbook_mutation_performed": False,
        "workbook_source_mutation_performed": False,
        "worker_spawn_performed": False,
    }
    if verification_overrides:
        for key, value in verification_overrides.items():
            request[key] = value
            request["operator_authority_envelope"][key] = value
    return request


def _mac_review_dispatcher_request(
    *,
    request_id: str = "build_mark_informational_review_packet_review_packet_c4ec166103f9aa35_mark_review_packet_informational_20260605T172815Z_ec1066ebe6c0",
    event_type: str = "mark_informational",
    selected_card_id: str = "dynamic_card.build.review_packet.current",
    selected_action_id: str = "review_packet.review_packet_c4ec166103f9aa35.mark_review_packet_informational",
    include_top_level_thread: bool = False,
    nested_thread: str = "",
    review_packet_id: str = "",
    verification_overrides: dict | None = None,
) -> dict:
    authority_boundary = dict(router.AUTHORITY_BOUNDARY)
    current_context = {
        "active_surface_ref": "world_dynamic_card",
        "current_world_ref": "build",
        "requested_mode": "operator",
        "source_surface": "mission_control",
    }
    if nested_thread:
        current_context["current_thread_ref"] = nested_thread
    request = {
        "active_surface_ref": "world_dynamic_card",
        "app_instance_ref": "sha256:b7efb2d5f3ec5e0b0f1a77589c9c276612600550161e555f4fe5384f98fd3e07",
        "app_instance_verified": True,
        "authority_boundary": authority_boundary,
        "authority_requested": [],
        "browser_access_performed": False,
        "business_action_performed": False,
        "business_state_mutation_performed": False,
        "child_agent_run_performed": False,
        "context": dict(current_context),
        "controller_event_type": event_type,
        "controller_action_type": event_type,
        "coupa_access_performed": False,
        "created_at": "2026-06-05T17:28:15Z",
        "current_context": dict(current_context),
        "current_world_ref": "build",
        "device_class": "mac",
        "device_ref": "sha256:b191fdb712c2c5d281944b1ab6435791fae47f1ca78fdd184cfb0fc36dd2b2d7",
        "device_verified": True,
        "email_send_performed": False,
        "event": {
            "authority_boundary": authority_boundary,
            "authority_requested": [],
            "controller_event_type": event_type,
            "selected_action_id": selected_action_id,
            "selected_card_id": selected_card_id,
        },
        "external_provider_connected": False,
        "git_push_performed": False,
        "gmail_access_performed": False,
        "incoming_authority_granted_accepted": False,
        "incoming_authority_granted_fields": [],
        "input_surface": "world_dynamic_card",
        "kind": router.REQUEST_TYPE,
        "ledger_mutation_performed": False,
        "ledger_posting_performed": False,
        "mac_wrote_request_only": True,
        "merge_performed": False,
        "no_external_action": True,
        "operator_authority_envelope": {
            "app_instance_ref": "sha256:b7efb2d5f3ec5e0b0f1a77589c9c276612600550161e555f4fe5384f98fd3e07",
            "app_instance_verified": True,
            "device_class": "mac",
            "device_ref": "sha256:b191fdb712c2c5d281944b1ab6435791fae47f1ca78fdd184cfb0fc36dd2b2d7",
            "device_verified": True,
            "operator_ref": "hwinshipwheatley",
            "operator_verified": True,
            "request_hash": "sha256:ec1066ebe6c0a487d1eb219237bd53018f3db2166a825f9288bd5c22d110d69b",
            "session_ref": "sha256:5d9dcf1bd6a56c9afdae80aed5fdf1a3b06c5f6d9f4654fd0425bef43ae2a8a1",
            "session_verified": True,
            "verification_status": operator_authority.VERIFICATION_STATUS_VERIFIED,
        },
        "operator_ref": "hwinshipwheatley",
        "operator_verified": True,
        "origin_surface": "mission_control_mac",
        "paid_marking_performed": False,
        "payload_hash": "sha256:99454287f65596ecbd3c3d9cb185ab6d76bd410efae561818acde8738c85b8f7",
        "pdf_export_performed": False,
        "portal_submit_performed": False,
        "request_hash": "sha256:ec1066ebe6c0a487d1eb219237bd53018f3db2166a825f9288bd5c22d110d69b",
        "request_hash_checked": True,
        "request_id": request_id,
        "request_type": router.REQUEST_TYPE,
        "requested_mode": "operator",
        "result_receipt_required": True,
        "schema_version": "operator_controller_event_request_v0",
        "selected_action_id": selected_action_id,
        "selected_card_id": selected_card_id,
        "session_ref": "sha256:5d9dcf1bd6a56c9afdae80aed5fdf1a3b06c5f6d9f4654fd0425bef43ae2a8a1",
        "session_verified": True,
        "source_channel": "mission_control_dynamic_card",
        "source_request_id": request_id,
        "source_surface": "mission_control",
        "type": router.REQUEST_TYPE,
        "verification_status": operator_authority.VERIFICATION_STATUS_VERIFIED,
        "workbook_body_read": False,
        "workbook_mutation_performed": False,
        "workbook_source_mutation_performed": False,
        "worker_spawn_performed": False,
    }
    if include_top_level_thread:
        request["current_thread_ref"] = "build_openclaw_backend"
    if review_packet_id:
        request["review_packet_id"] = review_packet_id
    if verification_overrides:
        for key, value in verification_overrides.items():
            request[key] = value
            request["operator_authority_envelope"][key] = value
    return request


def _route(tmp_path: Path, request: dict) -> dict:
    read_model_root = _seed_read_models(tmp_path)
    return router.route_controller_event(
        request,
        source_request_filename=f"{request.get('request_id', 'request')}.json",
        read_model_root=read_model_root,
        export_root=read_model_root,
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "wiki" / "Operator Controller Event Router.md",
        workroom_wiki_path=tmp_path / "wiki" / "Workroom Review Decision Consumer.md",
        sqlite_path=tmp_path / "operator_controller_event_router.sqlite",
        evidence_sqlite_path=tmp_path / "evidence_intake.sqlite",
        artifact_lineage_sqlite_path=tmp_path / "artifact_lineage_registry.sqlite",
        generated_at=FIXED_NOW,
    )


def _unsafe_true_grants(value, path="$"):
    unsafe_names = set(router.UNSAFE_TRUE_KEYS) | {
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


def test_ask_why_finance_capital_hilton_returns_payment_watch_context(tmp_path):
    receipt = _route(
        tmp_path,
        _event_request(
            event_type="ask_why",
            world="finance",
            thread="capital_hilton",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            operator_text="Why am I here?",
        ),
    )

    assert receipt["raw_internal_status"] == router.RESPONSE_READY
    assert receipt["backend_route"] == "system_question_answer.contextual_answer"
    assert receipt["route_result"]["package_staged"] is False
    assert "Coupa is processing" in receipt["dynamic_card_response"]["plain_summary"]
    assert "ledger" in receipt["dynamic_card_response"]["plain_summary"].lower()
    assert receipt["dynamic_card_response"]
    assert not _unsafe_true_grants(receipt)


def test_exact_observed_mac_open_lane_compact_envelope_is_accepted(tmp_path):
    receipt = _route(tmp_path, _mac_dispatcher_request())

    assert receipt["raw_internal_status"] == router.RESPONSE_READY
    assert receipt["backend_route"] == "operator_action_payloads.navigate"
    assert receipt["route_status"] == "ROUTED"
    assert receipt["dynamic_card_response"]["headline"] == "Lane navigation ready"
    assert receipt["operator_authority_envelope"]["verified"] is True
    assert receipt["operator_authority_envelope"]["source_surface"] == "card"
    assert receipt["operator_envelope_normalization"]["applied"] is True
    assert receipt["incoming_authority_granted_accepted"] is False
    assert receipt["authority_granted"] == []
    assert all(value is False for value in receipt["authority_boundary"].values())
    assert receipt["machine_proof"]["business_action_performed"] is False
    assert receipt["machine_proof"]["ledger_mutation_performed"] is False
    assert receipt["machine_proof"]["paid_marking_performed"] is False
    assert not _unsafe_true_grants(receipt)


def test_mac_dispatcher_ask_why_compact_envelope_is_accepted(tmp_path):
    request = _mac_dispatcher_request(
        event_type="ask_why",
        selected_action_id="",
        request_id="finance_ask_why_capital_hilton_20260605T161818Z_3a8c5dbcc6c0",
    )
    request["operator_text"] = "Why am I here?"
    receipt = _route(tmp_path, request)

    assert receipt["raw_internal_status"] == router.RESPONSE_READY
    assert receipt["backend_route"] == "system_question_answer.contextual_answer"
    assert "Coupa is processing" in receipt["dynamic_card_response"]["plain_summary"]
    assert receipt["operator_authority_envelope"]["verified"] is True
    assert not _unsafe_true_grants(receipt)


def test_mac_dispatcher_inline_mission_control_source_surface_normalizes_to_card(tmp_path):
    request = _mac_dispatcher_request(request_id="mac_dispatcher_inline_source_surface")
    request["operator_authority_envelope"]["source_surface"] = "mission_control"
    receipt = _route(tmp_path, request)

    assert receipt["raw_internal_status"] == router.RESPONSE_READY
    assert receipt["operator_authority_envelope"]["source_surface"] == "card"
    assert "source_surface" in receipt["operator_envelope_normalization"]["lifted_fields"]
    assert not _unsafe_true_grants(receipt)


def test_mac_dispatcher_false_verification_blocks(tmp_path):
    for verification_field in ("operator_verified", "device_verified", "session_verified"):
        receipt = _route(
            tmp_path,
            _mac_dispatcher_request(
                request_id=f"mac_dispatcher_false_{verification_field}",
                verification_overrides={verification_field: False},
            ),
        )
        assert receipt["raw_internal_status"] == router.BLOCKED_WITH_REASON
        assert "verified_operator_envelope_required" in receipt["blockers"]
        assert f"{verification_field}_false_or_missing" in receipt["operator_authority_envelope"]["blockers"]
        assert not _unsafe_true_grants(receipt)


def test_mac_dispatcher_incoming_authority_granted_rejected(tmp_path):
    request = _mac_dispatcher_request(request_id="mac_dispatcher_incoming_authority_granted")
    request["authority_granted"] = ["email_send"]
    receipt = _route(tmp_path, request)

    assert receipt["raw_internal_status"] == router.BLOCKED_WITH_REASON
    assert receipt["incoming_authority_granted_accepted"] is False
    assert receipt["authority_granted"] == []
    assert receipt["incoming_authority_granted_fields"]
    assert "incoming_authority_granted_or_backend_gate_fields_not_accepted" in receipt["rejected_reasons"]
    assert not _unsafe_true_grants(receipt)


def test_exact_observed_mac_mark_informational_review_request_routes(tmp_path):
    receipt = _route(tmp_path, _mac_review_dispatcher_request())

    assert receipt["raw_internal_status"] == router.RESPONSE_READY
    assert receipt["backend_route"] == "workroom_review_decision_consumer.record_decision_only"
    assert receipt["current_world_ref"] == "build"
    assert receipt["current_thread_ref"] == "build_openclaw_backend"
    assert receipt["context_normalization"]["applied"] is True
    assert "current_thread_ref:selected_action_payload" in receipt["context_normalization"]["inferred_fields"]
    assert receipt["route_result"]["decision_action"] == "mark_review_packet_informational"
    assert receipt["route_result"]["decision_recorded"] is True
    assert receipt["route_result"]["merge_performed"] is False
    assert receipt["route_result"]["git_push_performed"] is False
    assert receipt["machine_proof"]["merge_performed"] is False
    assert receipt["machine_proof"]["git_push_performed"] is False
    assert receipt["machine_proof"]["worker_spawn_performed"] is False
    assert receipt["machine_proof"]["business_action_performed"] is False
    assert all(value is False for value in receipt["authority_boundary"].values())
    assert not _unsafe_true_grants(receipt)


def test_review_request_with_nested_current_context_routes(tmp_path):
    receipt = _route(
        tmp_path,
        _mac_review_dispatcher_request(
            request_id="build_review_nested_context",
            selected_action_id="",
            nested_thread="build_openclaw_backend",
        ),
    )

    assert receipt["raw_internal_status"] == router.RESPONSE_READY
    assert receipt["current_thread_ref"] == "build_openclaw_backend"
    assert receipt["route_result"]["decision_recorded"] is True
    assert receipt["machine_proof"]["merge_performed"] is False
    assert receipt["machine_proof"]["git_push_performed"] is False
    assert not _unsafe_true_grants(receipt)


def test_review_packet_id_without_thread_infers_build_thread(tmp_path):
    receipt = _route(
        tmp_path,
        _mac_review_dispatcher_request(
            request_id="build_review_packet_id_infers_context",
            selected_action_id="",
            review_packet_id="review_packet:c4ec166103f9aa35",
        ),
    )

    assert receipt["raw_internal_status"] == router.RESPONSE_READY
    assert receipt["current_thread_ref"] == "build_openclaw_backend"
    assert receipt["context_normalization"]["review_packet_id"] == "review_packet:c4ec166103f9aa35"
    assert "current_thread_ref:workroom_review_packet_index" in receipt["context_normalization"]["inferred_fields"]
    assert receipt["route_result"]["decision_recorded"] is True
    assert not _unsafe_true_grants(receipt)


def test_unresolvable_review_context_returns_needs_lane_context_card(tmp_path):
    receipt = _route(
        tmp_path,
        _mac_review_dispatcher_request(
            request_id="build_review_context_unresolvable",
            selected_card_id="dynamic_card.build.review_packet.unknown",
            selected_action_id="",
            review_packet_id="review_packet:unknown",
        ),
    )

    assert receipt["raw_internal_status"] == router.BLOCKED_WITH_REASON
    assert receipt["route_status"] == "NEEDS_LANE_CONTEXT"
    assert receipt["dynamic_card_response"]["headline"] == "Needs lane context"
    assert "Build lane" in receipt["dynamic_card_response"]["plain_summary"]
    assert "current_thread_ref_missing" in receipt["blockers"]
    assert not _unsafe_true_grants(receipt)


def test_review_request_incoming_authority_granted_rejected(tmp_path):
    request = _mac_review_dispatcher_request(request_id="build_review_incoming_authority_granted")
    request["authority_granted"] = ["merge"]
    receipt = _route(tmp_path, request)

    assert receipt["raw_internal_status"] == router.BLOCKED_WITH_REASON
    assert receipt["incoming_authority_granted_accepted"] is False
    assert receipt["authority_granted"] == []
    assert "incoming_authority_granted_or_backend_gate_fields_not_accepted" in receipt["rejected_reasons"]
    assert not _unsafe_true_grants(receipt)


def test_attach_proof_routes_to_evidence_intake_without_marking_paid(tmp_path):
    receipt = _route(
        tmp_path,
        _event_request(
            event_type="attach_proof",
            world="finance",
            thread="live_arts_md",
            selected_card_id="dynamic_card.finance.live_arts_md.evidence_intake.payment_processing",
            operator_text="Payment processing screenshot for invoice 2026-1001.",
            artifact_ref="mission_control_drop:live_arts_md_payment_processing_screenshot",
        ),
    )

    assert receipt["raw_internal_status"] == router.RESPONSE_READY
    assert receipt["backend_route"] == "evidence_intake.record_candidate_evidence"
    assert receipt["dynamic_card_response"]["headline"] == "Payment proof received"
    assert "Ledger remains untouched until payment is confirmed" in receipt["dynamic_card_response"]["plain_summary"]
    assert receipt["route_result"]["current_world_ref"] == "finance"
    assert receipt["route_result"]["current_thread_ref"] == "live_arts_md"
    assert receipt["route_result"]["privacy"]["privacy_class"] == "financial_sensitive"
    assert receipt["route_result"]["privacy"]["processing_location"] == "local_only"
    assert receipt["route_result"]["payment"]["paid"] is False
    assert receipt["route_result"]["payment"]["ledger_mutation_performed"] is False
    assert receipt["machine_proof"]["ledger_mutation_performed"] is False
    assert receipt["machine_proof"]["paid_marking_performed"] is False

    conn = sqlite3.connect(tmp_path / "evidence_intake.sqlite")
    row = conn.execute(
        """
        select current_world_ref, current_thread_ref, privacy_class, processing_location,
               intended_use, paid, ledger_mutation_performed, raw_ocr_text_stored
        from evidence_intake_records
        order by created_at desc limit 1
        """
    ).fetchone()
    conn.close()
    assert row == ("finance", "live_arts_md", "financial_sensitive", "local_only", "payment_proof", 0, 0, 0)
    assert not _unsafe_true_grants(receipt)


def test_mark_informational_routes_to_review_decision_consumer(tmp_path):
    receipt = _route(
        tmp_path,
        _event_request(
            event_type="mark_informational",
            world="build",
            thread="build_openclaw_backend",
            selected_card_id="dynamic_card.build.review_packet.current",
            selected_action_id="review_packet.review_packet_c4ec166103f9aa35.mark_review_packet_informational",
            operator_text="Close this as informational.",
        ),
    )

    assert receipt["raw_internal_status"] == router.RESPONSE_READY
    assert receipt["backend_route"] == "workroom_review_decision_consumer.record_decision_only"
    assert receipt["route_result"]["decision_action"] == "mark_review_packet_informational"
    assert receipt["route_result"]["decision_recorded"] is True
    assert receipt["route_result"]["merge_performed"] is False
    assert receipt["route_result"]["git_push_performed"] is False
    assert receipt["machine_proof"]["merge_performed"] is False
    assert receipt["machine_proof"]["git_push_performed"] is False
    assert receipt["dynamic_card_response"]
    assert not _unsafe_true_grants(receipt)


def test_do_it_capital_hilton_payment_watch_navigates_only(tmp_path):
    receipt = _route(
        tmp_path,
        _event_request(
            event_type="do_it",
            world="finance",
            thread="capital_hilton",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            operator_text="Do it.",
        ),
    )

    assert receipt["raw_internal_status"] == router.RESPONSE_READY
    assert receipt["backend_route"] == "operator_action_payloads.navigate"
    assert receipt["route_ref"] == "capital_hilton.payment.open_finance"
    assert receipt["route_result"]["navigation"]["business_action"] is False
    assert receipt["machine_proof"]["navigation_only"] is True
    assert receipt["machine_proof"]["ledger_mutation_performed"] is False
    assert receipt["machine_proof"]["paid_marking_performed"] is False
    assert "No business action" in receipt["dynamic_card_response"]["plain_summary"]
    assert not _unsafe_true_grants(receipt)


def test_do_it_protected_coupa_submit_stages_approval_only(tmp_path):
    receipt = _route(
        tmp_path,
        _event_request(
            event_type="do_it",
            world="finance",
            thread="capital_hilton",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
            operator_text="Submit this in Coupa.",
        ),
    )

    assert receipt["raw_internal_status"] == router.RESPONSE_READY
    assert receipt["route_status"] == "PROTECTED_ACTION_STAGED_OR_BLOCKED"
    assert receipt["backend_route"] == "approval_request_queue.stage_only"
    assert receipt["route_ref"] == "guardian_gate.coupa_submit.stage_approval_request"
    assert receipt["machine_proof"]["protected_action_staged_only"] is True
    assert receipt["machine_proof"]["coupa_access_performed"] is False
    assert receipt["machine_proof"]["browser_access_performed"] is False
    assert receipt["machine_proof"]["submit_performed"] is False
    assert "No Coupa" in receipt["dynamic_card_response"]["plain_summary"]
    assert not _unsafe_true_grants(receipt)


def test_incoming_authority_granted_is_rejected_or_ignored(tmp_path):
    request = _event_request(
        event_type="do_it",
        world="finance",
        thread="capital_hilton",
        operator_text="Do it.",
    )
    request["authority_granted"] = ["email_send"]

    receipt = _route(tmp_path, request)

    assert receipt["raw_internal_status"] == router.BLOCKED_WITH_REASON
    assert receipt["incoming_authority_granted_accepted"] is False
    assert receipt["authority_granted"] == []
    assert receipt["incoming_authority_granted_fields"]
    assert "incoming_authority_granted_or_backend_gate_fields_not_accepted" in receipt["rejected_reasons"]
    assert receipt["dynamic_card_response"]
    assert not _unsafe_true_grants(receipt)


def test_missing_verified_envelope_blocks(tmp_path):
    request = {
        "request_id": "controller_event_missing_envelope",
        "request_type": router.REQUEST_TYPE,
        "controller_event_type": "ask_why",
        "current_world_ref": "finance",
        "current_thread_ref": "capital_hilton",
        "authority_requested": [],
        "authority_boundary": dict(router.AUTHORITY_BOUNDARY),
    }

    receipt = _route(tmp_path, request)

    assert receipt["raw_internal_status"] == router.BLOCKED_WITH_REASON
    assert receipt["route_status"] == "NEEDS_VERIFICATION"
    assert "verified_operator_envelope_required" in receipt["blockers"]
    assert receipt["dynamic_card_response"]["status_label"] == "Needs verification"
    assert not _unsafe_true_grants(receipt)


def test_unknown_event_fails_closed_even_with_verified_envelope(tmp_path):
    receipt = _route(
        tmp_path,
        _event_request(
            event_type="spin_around",
            envelope_event_type="show_details",
            world="finance",
            thread="capital_hilton",
        ),
    )

    assert receipt["raw_internal_status"] == router.BLOCKED_WITH_REASON
    assert receipt["route_status"] == "UNKNOWN_EVENT_BLOCKED"
    assert "unknown_controller_event_type" in receipt["blockers"]
    assert receipt["dynamic_card_response"]
    assert not _unsafe_true_grants(receipt)


def test_missing_action_payload_returns_needs_verification(tmp_path):
    receipt = _route(
        tmp_path,
        _event_request(
            event_type="do_it",
            world="finance",
            thread="unknown_client",
            selected_action_id="missing.action.payload",
            operator_text="Do it.",
        ),
    )

    assert receipt["raw_internal_status"] == router.BLOCKED_WITH_REASON
    assert receipt["route_status"] == "NEEDS_VERIFICATION"
    assert "missing_action_payload" in receipt["blockers"]
    assert receipt["dynamic_card_response"]["status_label"] == "Needs verification"
    assert not _unsafe_true_grants(receipt)


def test_router_exports_json_bridge_sqlite_and_clean_unsafe_scan(tmp_path):
    receipt = _route(
        tmp_path,
        _event_request(
            event_type="show_details",
            world="finance",
            thread="capital_hilton",
            selected_card_id="dynamic_card.finance.capital_hilton.payment_watch",
        ),
    )
    read_model_root = tmp_path / "read_models"
    local_contract = json.loads((read_model_root / router.CONTRACT_JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    local_status = json.loads((read_model_root / router.STATUS_JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    bridge_contract = json.loads((tmp_path / "bridge" / router.CONTRACT_JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    bridge_status = json.loads((tmp_path / "bridge" / router.STATUS_JSON_EXPORT_NAME).read_text(encoding="utf-8"))

    assert local_contract == bridge_contract
    assert local_status == bridge_status
    assert local_contract["status"] == router.READY_STATUS
    assert local_status["status"] == router.READY_STATUS
    assert local_status["latest_receipt"]["receipt_id"] == receipt["receipt_id"]
    assert local_status["latest_receipt"]["dynamic_card_response"]
    assert not _unsafe_true_grants(local_contract)
    assert not _unsafe_true_grants(local_status)

    conn = sqlite3.connect(tmp_path / "operator_controller_event_router.sqlite")
    row = conn.execute(
        """
        select controller_event_type, route_status, raw_internal_status,
               ledger_mutation_performed, paid_marking_performed,
               submit_performed, business_action_performed
        from controller_event_receipts
        order by generated_at desc limit 1
        """
    ).fetchone()
    conn.close()
    assert row == ("show_details", "ROUTED", router.RESPONSE_READY, 0, 0, 0, 0)

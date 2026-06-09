import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import capability_authority_loop as loop
import first_class_operator_envelope as operator_authority
import operator_controller_event_router as controller_router
import operator_conversation_router as conversation_router
import proof_to_response_verifier


FIXED_NOW = "2026-06-08T12:00:00+00:00"


def _request(text, world="finance", thread="capital_hilton", **extra):
    request = {
        "request_id": f"capability_loop_test_{world}_{thread}",
        "request_type": conversation_router.REQUEST_TYPE,
        "controller_event_type": "chat_goal",
        "operator_text": text,
        "current_world_ref": world,
        "current_thread_ref": thread,
        "selected_card_id": "dynamic_card.test",
        "selected_action_id": "",
        "authority_boundary": dict(conversation_router.AUTHORITY_BOUNDARY),
        "authority_requested": [],
    }
    request.update(extra)
    return request


def _controller_request(text, world="finance", thread="capital_hilton", **extra):
    request = {
        "request_id": f"controller_capability_loop_test_{world}_{thread}_{abs(hash(text))}",
        "request_type": controller_router.REQUEST_TYPE,
        "controller_event_type": "chat_goal",
        "operator_text": text,
        "current_world_ref": world,
        "current_thread_ref": thread,
        "selected_card_id": "dynamic_card.capability_loop_test",
        "selected_action_id": "",
        "authority_boundary": dict(controller_router.AUTHORITY_BOUNDARY),
        "authority_requested": [],
    }
    request.update(extra)
    return operator_authority.attach_verified_authority_envelope(
        request,
        operator_ref="operator:winship",
        app_instance_ref="mission_control:mac",
        device_ref="device:macbook",
        device_class="mac",
        session_ref="session:capability-authority-loop-test",
        source_surface="chat",
        current_world_ref=world,
        current_thread_ref=thread,
        active_entity_ref=request.get("selected_card_id", ""),
        controller_action_type="chat_goal",
        authority_requested=[],
        proof_refs=["controller_surface:mission_control", "test:capability_authority_real_path"],
        created_at=FIXED_NOW,
    )


def _route_controller(request, tmp_path):
    return controller_router.route_controller_event(
        request,
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        sqlite_path=tmp_path / "controller.sqlite",
        proof_to_response_sqlite_path=tmp_path / "conversation.sqlite",
        wiki_path=tmp_path / "Operator Controller Event Router.md",
        generated_at=FIXED_NOW,
    )


def _unsafe_true_grants(value, path="$"):
    found = []
    unsafe = set(loop.UNSAFE_TRUE_KEYS) | set(conversation_router.UNSAFE_TRUE_KEYS) | {"paid", "sent", "submitted"}
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in unsafe and child is True:
                found.append(child_path)
            found.extend(_unsafe_true_grants(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_unsafe_true_grants(child, f"{path}[{index}]"))
    return found


def test_email_lookup_request_without_authority_emits_capability_gap_and_request():
    response = loop.build_email_lookup_gap_response(
        "Have we received any emails from Annette?",
        world_ref="finance",
        thread_ref="capital_hilton",
        generated_at=FIXED_NOW,
    )

    assert response["response_status"] == "CAPABILITY_GAP_AUTHORITY_REQUEST_READY"
    assert response["capability_gap"]["schema_version"] == loop.CAPABILITY_GAP_SCHEMA
    assert response["capability_gap"]["capability_id"] == loop.READ_ONLY_EMAIL_LOOKUP
    assert response["operator_authority_request"]["schema_version"] == loop.AUTHORITY_REQUEST_SCHEMA
    assert response["operator_authority_request"]["requested_capability_id"] == loop.READ_ONLY_EMAIL_LOOKUP


def test_primary_response_names_read_only_email_gap_not_payment_watch_copy():
    response = loop.build_email_lookup_gap_response(
        "Have we received any emails from Annette? If not, make a follow-up email for tomorrow.",
        world_ref="finance",
        thread_ref="capital_hilton",
        generated_at=FIXED_NOW,
    )
    display = response["operator_display"]

    assert "I don't have read-only email lookup yet." in display["plain_summary"]
    assert "Grant read-only email lookup" in display["plain_summary"]
    assert "payment evidence needed" not in json.dumps(response).lower()
    assert response["safe_fallback"]["can_prepare_draft"] is True
    assert response["safe_fallback"]["can_send"] is False


def test_response_lists_allowed_and_denied_actions():
    response = loop.build_email_lookup_gap_response(
        "Did Glenn acknowledge St. Anne's?",
        world_ref="finance",
        thread_ref="st_annes",
        generated_at=FIXED_NOW,
    )
    request = response["operator_authority_request"]

    assert "search_relevant_email_evidence" in request["requested_actions"]
    assert "read_relevant_email_evidence" in request["requested_actions"]
    for denied in ("send_email", "delete_email", "archive_email", "mark_email_read", "open_gmail_ui", "open_browser", "mutate_ledger", "mark_paid", "coupa_submit"):
        assert denied in request["denied_actions"]


def test_natural_language_grant_links_only_to_active_request():
    response = loop.build_email_lookup_gap_response(
        "Have we received any emails from Annette?",
        world_ref="finance",
        thread_ref="capital_hilton",
        generated_at=FIXED_NOW,
    )
    grant = loop.compile_authority_grant(
        "OK, I grant you access to do that.",
        active_authority_request=response["operator_authority_request"],
        generated_at=FIXED_NOW,
    )

    assert grant["schema_version"] == loop.AUTHORITY_GRANT_SCHEMA
    assert grant["authority_grant_created"] is True
    assert grant["request_id"] == response["operator_authority_request"]["request_id"]
    assert grant["granted_capability_id"] == loop.READ_ONLY_EMAIL_LOOKUP


def test_grant_preserves_denied_actions_and_false_boundaries():
    response = loop.build_email_lookup_gap_response(
        "Look in Gmail for payment update.",
        world_ref="finance",
        thread_ref="capital_hilton",
        generated_at=FIXED_NOW,
    )
    grant = loop.compile_authority_grant(
        "Yes, grant read-only email lookup.",
        active_authority_request=response["operator_authority_request"],
        generated_at=FIXED_NOW,
    )

    for denied in ("send_email", "open_gmail_ui", "open_browser", "delete_email", "archive_email", "mark_email_read", "coupa_submit", "mark_paid", "mutate_ledger"):
        assert denied in grant["denied_actions"]
    assert grant["authority_boundary"]["email_send_allowed"] is False
    assert grant["authority_boundary"]["gmail_ui_allowed"] is False
    assert grant["authority_boundary"]["browser_access_allowed"] is False
    assert grant["authority_boundary"]["ledger_mutation_allowed"] is False
    assert grant["authority_boundary"]["paid_marking_allowed"] is False


def test_vague_grant_with_no_active_request_does_not_create_authority():
    grant = loop.compile_authority_grant(
        "OK, I grant you access to do that.",
        active_authority_request=None,
        generated_at=FIXED_NOW,
    )

    assert grant["grant_status"] == "NEEDS_ACTIVE_AUTHORITY_REQUEST"
    assert grant["authority_grant_created"] is False


def test_build_permission_and_data_access_permission_are_separate():
    response = loop.build_email_lookup_gap_response(
        "Have we received any emails from Capital Hilton?",
        world_ref="finance",
        thread_ref="capital_hilton",
        generated_at=FIXED_NOW,
    )
    data_grant = loop.compile_authority_grant(
        "OK, I grant you access to do that.",
        active_authority_request=response["operator_authority_request"],
        generated_at=FIXED_NOW,
    )
    build_request = loop.build_capability_build_request(
        capability_id=loop.READ_ONLY_EMAIL_LOOKUP,
        build_authority_grant=data_grant,
        generated_at=FIXED_NOW,
    )

    assert build_request["build_request_status"] == "BUILD_AUTHORITY_REQUIRED"
    assert build_request["build_request_created"] is False


def test_build_request_can_be_created_only_with_explicit_build_grant():
    build_authority_request = {
        "schema_version": loop.AUTHORITY_REQUEST_SCHEMA,
        "request_id": "operator_authority_request:build-test",
        "requested_capability_id": loop.READ_ONLY_EMAIL_LOOKUP,
        "requested_scope": {"target_world_ref": "build", "target_thread_ref": "capabilities"},
        "requested_actions": list(loop.BUILD_ACTIONS),
        "denied_actions": list(loop.PROHIBITED_EMAIL_ACTIONS),
        "duration_scope": "single_build_packet",
    }
    build_grant = loop.compile_authority_grant(
        "You can build that capability.",
        active_authority_request=build_authority_request,
        generated_at=FIXED_NOW,
    )
    build_request = loop.build_capability_build_request(
        capability_id=loop.READ_ONLY_EMAIL_LOOKUP,
        build_authority_grant=build_grant,
        generated_at=FIXED_NOW,
    )

    assert build_request["build_request_created"] is True
    assert "write_local_adapter_code" in build_request["allowed_build_actions"]
    assert "send_email" in build_request["denied_build_actions"]


def test_raw_incoming_authority_granted_field_is_not_trusted(tmp_path):
    result = conversation_router.route_conversation_text(
        _request("Have we received any emails from Annette?", authority_granted=True),
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "proof.sqlite",
    )

    assert result["route_status"] == conversation_router.ROUTE_STATUS_MAKE_IT_SO_AUTHORITY_REQUEST
    assert result["capability_authority"]["raw_authority_granted_trusted"] is False
    assert result["capability_authority"]["operator_authority_request"]["requested_capability_id"] == loop.READ_ONLY_EMAIL_LOOKUP
    assert result["workflow_package_staged"] is False
    assert result["workflow_request_type_emitted"] == ""


def test_annette_live_arts_and_glenn_route_to_same_reusable_email_gap(tmp_path):
    prompts = [
        ("Have we received any emails from Annette?", "finance", "capital_hilton"),
        ("Can you check my email and see the new accountant's name, email, and role?", "finance", "live_arts_md"),
        ("Did Glenn acknowledge the invoice or payment timing?", "finance", "st_annes"),
    ]
    for text, world, thread in prompts:
        result = conversation_router.route_conversation_text(
            _request(text, world=world, thread=thread),
            generated_at=FIXED_NOW,
            sqlite_path=tmp_path / "proof.sqlite",
        )
        assert result["route_status"] == conversation_router.ROUTE_STATUS_MAKE_IT_SO_AUTHORITY_REQUEST
        assert result["backend_route"] == "make_it_so_objective_loop.start_email_lookup_objective"
        assert result["capability_authority"]["capability_gap"]["capability_id"] == loop.READ_ONLY_EMAIL_LOOKUP
        assert result["workflow_request_type_emitted"] == ""
        assert "WORKFLOW_PACKAGE_REQUEST_V0" not in json.dumps(result)


def test_real_controller_turn1_capital_hilton_emits_gap_and_persists_active_request(tmp_path):
    receipt = _route_controller(
        _controller_request("Have we received any emails from Annette? If not, make a follow-up email for tomorrow."),
        tmp_path,
    )

    route = receipt["route_result"]
    card = receipt["dynamic_card_response"]
    authority = route["capability_authority"]
    assert receipt["backend_route"] == "operator_conversation_router.route_conversation_text"
    assert receipt["route_status"] == conversation_router.ROUTE_STATUS_MAKE_IT_SO_AUTHORITY_REQUEST
    assert route["backend_route"] == "make_it_so_objective_loop.start_email_lookup_objective"
    assert route["operator_display"]["headline"] == "Make-it-so authority needed"
    assert "payment evidence needed" not in json.dumps(receipt).lower()
    assert authority["capability_gap"]["schema_version"] == loop.CAPABILITY_GAP_SCHEMA
    assert authority["operator_authority_request"]["schema_version"] == loop.AUTHORITY_REQUEST_SCHEMA
    assert route["make_it_so_objective"]["make_it_so_authority_request"]["status"] == "pending"
    assert card["capability_authority"]["operator_authority_request"]["requested_capability_id"] == loop.READ_ONLY_EMAIL_LOOKUP
    assert card["trust_state"] == "needs_verification"
    assert receipt["machine_proof"]["workflow_package_request_v0_emitted"] is False


def test_real_controller_turn2_grant_resolves_from_persisted_active_request(tmp_path):
    first = _route_controller(
        _controller_request("Have we received any emails from Annette? If not, make a follow-up email for tomorrow."),
        tmp_path,
    )
    second = _route_controller(
        _controller_request("OK, I grant you access to do that."),
        tmp_path,
    )
    grant = second["route_result"]["make_it_so_objective"]["make_it_so_authority_grant"]

    assert first["route_status"] == conversation_router.ROUTE_STATUS_MAKE_IT_SO_AUTHORITY_REQUEST
    assert second["route_status"] == conversation_router.ROUTE_STATUS_MAKE_IT_SO_GRANT_COMPILED
    assert grant["schema_version"] == "MAKE_IT_SO_AUTHORITY_GRANT_V0"
    assert grant["request_id"] == first["route_result"]["make_it_so_objective"]["make_it_so_authority_request"]["request_id"]
    assert loop.READ_ONLY_EMAIL_LOOKUP in grant["granted_capabilities"]
    assert "send_email" in grant["denied_actions"]
    assert grant["authority_boundary"]["email_send_allowed"] is False


def test_real_controller_live_arts_lane_scoped_grant_from_persisted_request(tmp_path):
    first = _route_controller(
        _controller_request("Can you check my email and see the new accountant's name, email, and role?", world="finance", thread="live_arts_md"),
        tmp_path,
    )
    second = _route_controller(
        _controller_request("Yes, grant it for this lane only.", world="finance", thread="live_arts_md"),
        tmp_path,
    )
    grant = second["route_result"]["make_it_so_objective"]["make_it_so_authority_grant"]

    assert first["route_result"]["capability_authority"]["capability_gap"]["capability_id"] == loop.READ_ONLY_EMAIL_LOOKUP
    assert grant["scope"]["target_world_ref"] == "finance"
    assert grant["scope"]["target_thread_ref"] == "live_arts_md"
    assert "contact saved" not in json.dumps(second).lower()


def test_real_controller_st_annes_never_mind_draft_only_does_not_grant(tmp_path):
    first = _route_controller(
        _controller_request("Did Glenn acknowledge the invoice or payment timing?", world="finance", thread="st_annes"),
        tmp_path,
    )
    second = _route_controller(
        _controller_request("Never mind, just draft what I should ask Glenn.", world="finance", thread="st_annes"),
        tmp_path,
    )

    assert first["route_status"] == conversation_router.ROUTE_STATUS_MAKE_IT_SO_AUTHORITY_REQUEST
    assert second["route_status"] == conversation_router.ROUTE_STATUS_TEXT_RESPONSE
    assert second["route_result"]["backend_route"] == "capability_authority_loop.draft_only_safe_fallback"
    assert "authority_grant" not in json.dumps(second["route_result"].get("capability_authority", {})).lower()
    assert second["route_result"]["authority_boundary"]["email_send_allowed"] is False


def test_vague_grant_with_no_persisted_active_request_does_not_create_authority_in_controller(tmp_path):
    receipt = _route_controller(
        _controller_request("I grant all access."),
        tmp_path,
    )
    grant = receipt["route_result"]["capability_authority"]["operator_authority_grant"]

    assert receipt["route_status"] == conversation_router.ROUTE_STATUS_NEEDS_VERIFICATION
    assert grant["grant_status"] == "NEEDS_ACTIVE_AUTHORITY_REQUEST"
    assert grant["authority_grant_created"] is False


def test_unsupported_email_claims_are_blocked_for_verifier_compatibility():
    bad = {
        "draft_headline": "Annette replied",
        "draft_body": "I checked Gmail and received an email from Annette. I sent the draft and updated the ledger.",
        "draft_next_step": "Done.",
    }

    assert loop.unsupported_email_lookup_claims(bad) == [
        "draft_sent",
        "email_checked",
        "email_received",
        "ledger_updated",
    ]


def test_proof_to_response_verifier_blocks_unsupported_email_contact_claims():
    response = {
        "draft_headline": "Annette replied",
        "draft_body": "I checked Gmail, received an email, Annette replied, accountant identified, contact saved, and Coupa submitted.",
        "draft_next_step": "Done.",
    }
    failures = proof_to_response_verifier.unsupported_completion_claims(response)

    assert "checked gmail" in failures
    assert "received an email" in failures
    assert "annette replied" in failures
    assert "accountant identified" in failures
    assert "contact saved" in failures
    assert "coupa submitted" in failures


def test_export_contract_bridge_equality_and_no_unsafe_true_grants(tmp_path):
    result = loop.export_first_class_capability_authority_loop(
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "First Class Capability Authority Loop.md",
        sqlite_path=tmp_path / "capability.sqlite",
        generated_at=FIXED_NOW,
    )

    assert result["status"] == loop.READY_STATUS
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_path"]).read_text(encoding="utf-8"))
    assert local == bridge
    assert not _unsafe_true_grants(local)

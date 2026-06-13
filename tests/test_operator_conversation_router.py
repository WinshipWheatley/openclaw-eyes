import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import first_class_operator_envelope as operator_authority
import operator_controller_event_router as controller_router
import operator_conversation_router as router

FIXED_NOW = "2026-06-07T17:00:00+00:00"


def _request(text, world="finance", thread="capital_hilton", **extra):
    request = {
        "request_id": f"conversation_router_test_{world}_{thread}",
        "request_type": router.REQUEST_TYPE,
        "controller_event_type": "chat_goal",
        "operator_text": text,
        "current_world_ref": world,
        "current_thread_ref": thread,
        "selected_card_id": extra.pop("selected_card_id", "dynamic_card.test"),
        "selected_action_id": extra.pop("selected_action_id", ""),
        "authority_boundary": dict(router.AUTHORITY_BOUNDARY),
        "authority_requested": [],
    }
    request.update(extra)
    return request


def _controller_request(text, world="finance", thread="capital_hilton", **extra):
    request = _request(text, world=world, thread=thread, **extra)
    request["authority_boundary"] = dict(controller_router.AUTHORITY_BOUNDARY)
    return operator_authority.attach_verified_authority_envelope(
        request,
        operator_ref="operator:winship",
        app_instance_ref="mission_control:mac",
        device_ref="device:macbook",
        device_class="mac",
        session_ref="session:conversation-router-test",
        source_surface="chat",
        current_world_ref=world,
        current_thread_ref=thread,
        active_entity_ref=request.get("selected_card_id", ""),
        controller_action_type="chat_goal",
        authority_requested=[],
        proof_refs=["controller_surface:mission_control", "test:conversation_router"],
        created_at=FIXED_NOW,
    )


def _unsafe_true_grants(value, path="$"):
    found = []
    unsafe = set(router.UNSAFE_TRUE_KEYS) | {"paid", "sent", "submitted", "authority_granted"}
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


def test_helm_what_should_i_do_routes_text_first_not_package(tmp_path):
    result = router.route_conversation_text(
        _request("What should I do?", world="helm", thread="overview"),
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "proof.sqlite",
    )

    assert result["route_status"] == router.ROUTE_STATUS_TEXT_RESPONSE
    assert result["request_type"] == router.REQUEST_TYPE
    assert result["input_controller_event_type"] == "chat_goal"
    assert result["workflow_package_staged"] is False
    assert result["workflow_request_type_emitted"] == ""
    assert result["operator_display"]["headline"] in {"Needs lane context", "No urgent action"}


def test_capital_hilton_what_should_i_do_here_payment_evidence_needed(tmp_path):
    result = router.route_conversation_text(
        _request("What should I do here?"),
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "proof.sqlite",
    )
    display = result["operator_display"]

    assert result["backend_route"] == "proof_to_response_runtime.publish_response"
    assert display["speaker_ref"] == "chief"
    assert display["headline"] == "Payment evidence needed"
    assert "payment evidence" in display["plain_summary"].lower()
    assert display["next_safe_action"] == "Attach payment evidence."
    assert result["workflow_package_staged"] is False
    assert result["authority_boundary"]["ledger_mutation_allowed"] is False
    assert result["authority_boundary"]["paid_marking_allowed"] is False
    assert result["machine_proof"]["coupa_access_performed"] is False


def test_capital_hilton_messy_coworker_help_routes_to_next_step(tmp_path):
    result = router.route_conversation_text(
        _request("I don't know what to do here. Can you talk to me like a coworker and tell me the next safe move?"),
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "proof.sqlite",
    )
    display = result["operator_display"]

    assert result["backend_route"] == "proof_to_response_runtime.publish_response"
    assert result["conversation_intent_class"] == "payment_watch_next_step"
    assert display["headline"] == "Payment evidence needed"
    assert "payment evidence" in display["plain_summary"].lower()
    assert "stronger proof" not in display["plain_summary"].lower()
    assert result["workflow_package_staged"] is False
    assert result["machine_proof"]["external_api_called"] is False


def test_capital_hilton_why_cannot_mark_paid_blocks_paid_and_ledger(tmp_path):
    result = router.route_conversation_text(
        _request("Why can't this be marked paid?"),
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "proof.sqlite",
    )
    text = json.dumps(result).lower()

    assert "payment evidence" in text
    assert "paid marking" in text
    assert "ledger" in text
    assert result["operator_display"]["speaker_ref"] == "chief"
    assert result["workflow_package_staged"] is False


def test_attach_proof_hypothetical_does_not_stage_package(tmp_path):
    result = router.route_conversation_text(
        _request("What happens if I attach proof?"),
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "proof.sqlite",
    )
    summary = result["operator_display"]["plain_summary"].lower()

    assert "candidate" in summary
    assert "payment-processing" in summary
    assert "does not mark paid" in summary
    assert "ledger stays untouched" in summary
    assert result["workflow_package_staged"] is False
    assert result["suggested_controller_event"] == "attach_proof"


def test_business_development_send_followup_is_blocked_text_response(tmp_path):
    result = router.route_conversation_text(
        _request("Can you send the follow-up?", world="business_development", thread="capital_hilton"),
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "proof.sqlite",
    )
    summary = result["operator_display"]["plain_summary"].lower()

    assert result["operator_display"]["speaker_ref"] == "cassandra"
    assert "stage" in summary
    assert "will not send" in summary or "cannot send" in summary
    assert result["route_status"] == router.ROUTE_STATUS_PROTECTED_BLOCKED
    assert result["workflow_package_staged"] is False
    assert result["authority_boundary"]["email_send_allowed"] is False


def test_live_arts_proof_question_does_not_stage_package(tmp_path):
    result = router.route_conversation_text(
        _request("What does this proof mean?", world="finance", thread="live_arts_md"),
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "proof.sqlite",
    )
    text = json.dumps(result).lower()

    assert "candidate" in text
    assert "not_paid_truth" in text or "not mark" in text or "not paid" in text
    assert "ledger" in text
    assert result["workflow_package_staged"] is False


def test_build_workroom_question_no_merge_push_or_worker(tmp_path):
    result = router.route_conversation_text(
        _request("What should I do here?", world="build", thread="workrooms"),
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "proof.sqlite",
    )
    text = json.dumps(result).lower()

    assert result["operator_display"]["speaker_ref"] == "chief"
    assert "merge" in text
    assert "push" in text
    assert result["authority_boundary"]["merge_allowed"] is False
    assert result["authority_boundary"]["git_push_allowed"] is False
    assert result["authority_boundary"]["worker_spawn_allowed"] is False


def test_music_niles_controller_mapping_asks_for_target_context(tmp_path):
    result = router.route_conversation_text(
        _request("How would you map this controller idea?", world="music", thread="niles"),
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "proof.sqlite",
    )
    display = result["operator_display"]

    assert display["speaker_ref"] == "niles"
    assert "target software" in display["plain_summary"].lower()
    assert "controller" in display["plain_summary"].lower()
    assert result["workflow_package_staged"] is False
    assert result["machine_proof"]["invented_file_truth"] is False


def test_missing_context_returns_needs_lane_context_not_package(tmp_path):
    request = _request("What should I do here?", world="", thread="")
    result = router.route_conversation_text(request, generated_at=FIXED_NOW, sqlite_path=tmp_path / "proof.sqlite")

    assert result["route_status"] == router.ROUTE_STATUS_NEEDS_LANE_CONTEXT
    assert result["operator_display"]["headline"] == "Needs lane context"
    assert result["workflow_package_staged"] is False


def test_stale_context_returns_needs_verification(tmp_path):
    result = router.route_conversation_text(
        _request("What should I do here?", context_freshness_state="stale"),
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "proof.sqlite",
    )

    assert result["route_status"] == router.ROUTE_STATUS_NEEDS_VERIFICATION
    assert result["operator_display"]["headline"] == "Needs verification"
    assert result["workflow_package_staged"] is False


def test_protected_merge_request_blocked_as_text_response(tmp_path):
    result = router.route_conversation_text(
        _request("Can you merge and push this?", world="build", thread="workrooms"),
        generated_at=FIXED_NOW,
        sqlite_path=tmp_path / "proof.sqlite",
    )
    text = json.dumps(result).lower()

    assert result["operator_display"]["speaker_ref"] == "guardian"
    assert "merge" in text
    assert "push" in text
    assert "blocked" in text
    assert result["workflow_package_staged"] is False
    assert result["authority_boundary"]["merge_allowed"] is False
    assert result["authority_boundary"]["git_push_allowed"] is False


def test_chat_goal_controller_event_routes_to_conversation_router_not_workflow_package(tmp_path):
    request = _controller_request("What happens if I attach proof?")
    receipt = controller_router.route_controller_event(
        request,
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        sqlite_path=tmp_path / "controller.sqlite",
        proof_to_response_sqlite_path=tmp_path / "proof.sqlite",
        wiki_path=tmp_path / "Operator Controller Event Router.md",
        generated_at=FIXED_NOW,
    )

    assert receipt["backend_route"] == "operator_conversation_router.route_conversation_text"
    assert receipt["route_result"]["workflow_package_staged"] is False
    assert receipt["route_result"]["workflow_request_type_emitted"] == ""
    assert "WORKFLOW_PACKAGE_REQUEST_V0" not in json.dumps(receipt)
    assert receipt["dynamic_card_response"]["headline"] == "Proof can be recorded"


def test_contract_exports_bridge_equality_and_no_authority_grants(tmp_path):
    result = router.export_operator_conversation_router(
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Operator Conversation Router.md",
        generated_at=FIXED_NOW,
    )

    assert result["status"] == router.READY_STATUS
    for local_key, bridge_key in [("contract_path", "bridge_contract_path"), ("status_path", "bridge_status_path")]:
        local = json.loads(Path(result[local_key]).read_text(encoding="utf-8"))
        bridge = json.loads(Path(result[bridge_key]).read_text(encoding="utf-8"))
        assert local == bridge
        assert not _unsafe_true_grants(local)


def test_unsafe_true_grant_scan_clean(tmp_path):
    samples = [
        router.route_conversation_text(_request("What should I do here?"), generated_at=FIXED_NOW, sqlite_path=tmp_path / "proof.sqlite"),
        router.build_contract_read_model(generated_at=FIXED_NOW),
        router.build_status_read_model(generated_at=FIXED_NOW, sqlite_path=tmp_path / "proof.sqlite"),
    ]
    for sample in samples:
        assert not _unsafe_true_grants(sample)

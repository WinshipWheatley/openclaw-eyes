import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import capability_authority_loop as capability_loop
import first_class_operator_envelope as operator_authority
import global_run_mode_context as run_mode
import openclaw_request_processor
import operator_controller_event_router as controller_router


FIXED_NOW = "2026-06-08T22:00:00+00:00"


def _attach_envelope(request, *, action_type=None, world=None, thread=None):
    world = world if world is not None else str(request.get("current_world_ref") or "system")
    thread = thread if thread is not None else str(request.get("current_thread_ref") or "run_mode")
    return operator_authority.attach_verified_authority_envelope(
        request,
        operator_ref="operator:winship",
        app_instance_ref="mission_control:mac",
        device_ref="device:macbook",
        device_class="mac",
        session_ref="session:global-run-mode-context-test",
        source_surface="chat",
        current_world_ref=world,
        current_thread_ref=thread,
        active_entity_ref=str(request.get("selected_card_id") or ""),
        controller_action_type=action_type or str(request.get("controller_event_type") or ""),
        authority_requested=[],
        proof_refs=["controller_surface:mission_control", "test:global_run_mode_context"],
        created_at=FIXED_NOW,
    )


def _controller_request(text, *, world="finance", thread="capital_hilton", **extra):
    request = {
        "request_id": f"global_run_mode_controller_{world}_{thread}_{abs(hash(text))}",
        "request_type": controller_router.REQUEST_TYPE,
        "controller_event_type": "chat_goal",
        "operator_text": text,
        "current_world_ref": world,
        "current_thread_ref": thread,
        "selected_card_id": "dynamic_card.global_run_mode_test",
        "selected_action_id": "",
        "authority_boundary": dict(controller_router.AUTHORITY_BOUNDARY),
        "authority_requested": [],
    }
    request.update(extra)
    return _attach_envelope(request, world=world, thread=thread, action_type="chat_goal")


def _set_mode_request(requested_run_mode, *, scope="session", **extra):
    request = {
        "request_id": f"global_run_mode_set_{requested_run_mode}_{scope}",
        "request_type": run_mode.RUN_MODE_SET_REQUEST_SCHEMA,
        "requested_run_mode": requested_run_mode,
        "requested_scope": scope,
        "controller_event_type": run_mode.RUN_MODE_SET_EVENT_TYPE,
        "controller_action_type": run_mode.RUN_MODE_SET_EVENT_TYPE,
        "authority_boundary": dict(controller_router.AUTHORITY_BOUNDARY),
        "authority_requested": [],
    }
    if scope != "session":
        request["current_world_ref"] = extra.pop("current_world_ref", "finance")
        request["current_thread_ref"] = extra.pop("current_thread_ref", "capital_hilton")
    request.update(extra)
    return _attach_envelope(request, action_type=run_mode.RUN_MODE_SET_EVENT_TYPE)


def _route(request, tmp_path):
    return controller_router.route_controller_event(
        request,
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        sqlite_path=tmp_path / "controller.sqlite",
        proof_to_response_sqlite_path=tmp_path / "conversation.sqlite",
        wiki_path=tmp_path / "Operator Controller Event Router.md",
        generated_at=FIXED_NOW,
    )


def _run_context(active_run_mode):
    state = run_mode.build_run_mode_state(
        run_mode=active_run_mode,
        scope={"scope": "session", "target_world_ref": "", "target_thread_ref": "", "target_project_ref": ""},
        generated_at=FIXED_NOW,
    )
    return run_mode.context_from_state(state, source="test_fixture", generated_at=FIXED_NOW)


def _unsafe_true_grants(value, path="$"):
    unsafe = {
        "email_send_allowed",
        "gmail_allowed",
        "gmail_ui_allowed",
        "browser_access_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "ledger_posting_allowed",
        "ledger_mutation_allowed",
        "paid_marking_allowed",
        "workbook_mutation_allowed",
        "pdf_export_allowed",
        "git_push_allowed",
        "merge_allowed",
        "worker_spawn_allowed",
        "authority_granted",
        "paid",
        "sent",
        "submitted",
    }
    found = []
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


def test_request_with_no_run_mode_defaults_to_production(tmp_path):
    context = run_mode.resolve_run_mode_context(tmp_path / "run_mode.sqlite", {}, generated_at=FIXED_NOW)

    assert context["schema_version"] == run_mode.RUN_MODE_CONTEXT_SCHEMA
    assert context["run_mode"] == run_mode.PRODUCTION
    assert context["test_mode"] is False
    assert context["resolution_status"] == "resolved"


def test_run_mode_set_request_can_enter_test_dry_run_and_persist(tmp_path):
    receipt = _route(_set_mode_request(run_mode.TEST_DRY_RUN), tmp_path)
    state = run_mode.load_active_run_mode_state(tmp_path / "controller.sqlite")

    assert receipt["route_status"] == "RUN_MODE_SET"
    assert receipt["run_mode_state"]["active_run_mode"] == run_mode.TEST_DRY_RUN
    assert receipt["dynamic_card_response"]["run_mode"] == run_mode.TEST_DRY_RUN
    assert state["active_run_mode"] == run_mode.TEST_DRY_RUN
    assert state["test_marker"] == run_mode.TEST_MARKER


def test_controller_events_resolve_against_active_backend_run_mode(tmp_path):
    _route(_set_mode_request(run_mode.TEST_DRY_RUN), tmp_path)
    receipt = _route(_controller_request("Have we received any emails from Annette?"), tmp_path)

    assert receipt["run_mode"] == run_mode.TEST_DRY_RUN
    assert receipt["route_status"] == "MAKE_IT_SO_AUTHORITY_REQUEST_READY"
    assert receipt["route_result"]["make_it_so_objective"]["capability_authority"]["capability_gap"]["run_mode_context"]["run_mode"] == run_mode.TEST_DRY_RUN


def test_test_dry_run_response_carries_run_mode_context(tmp_path):
    _route(_set_mode_request(run_mode.TEST_DRY_RUN), tmp_path)
    receipt = _route(_controller_request("Write a test SQLite row for this dry run."), tmp_path)

    assert receipt["run_mode"] == run_mode.TEST_DRY_RUN
    assert receipt["route_result"]["test_execution_receipt"]["status"] == "DRY_RUN_RECORDED"
    assert receipt["route_result"]["test_execution_receipt"]["production_write_performed"] is False
    assert receipt["dynamic_card_response"]["run_mode_context"]["test_marker"] == run_mode.TEST_MARKER


def test_test_live_requires_explicit_test_authority_and_raw_grant_is_rejected(tmp_path):
    receipt = _route(
        _set_mode_request(
            run_mode.TEST_LIVE,
            allowlisted_recipients=[run_mode.ALLOWLISTED_TEST_EMAIL],
            authority_granted=True,
        ),
        tmp_path,
    )

    assert receipt["route_status"] in {"NEEDS_VERIFICATION", "REJECTED", "RUN_MODE_SET_BLOCKED"}
    assert receipt["run_mode"] == run_mode.PRODUCTION
    assert "authority_granted" in json.dumps(receipt).lower()
    assert receipt["machine_proof"]["incoming_authority_granted_accepted"] is False


def test_valid_test_live_authority_can_enter_test_live(tmp_path):
    receipt = _route(
        _set_mode_request(
            run_mode.TEST_LIVE,
            allowlisted_recipients=[run_mode.ALLOWLISTED_TEST_EMAIL],
            test_execution_authority={
                "schema_version": run_mode.TEST_EXECUTION_AUTHORITY_SCHEMA,
                "verifier_status": "VERIFIED_TEST_AUTHORITY",
                "live_external_effects_allowed": True,
            },
        ),
        tmp_path,
    )

    assert receipt["route_status"] == "RUN_MODE_SET"
    assert receipt["run_mode"] == run_mode.TEST_LIVE
    assert receipt["run_mode_state"]["allowlisted_recipients"] == [run_mode.ALLOWLISTED_TEST_EMAIL]


def test_test_marker_in_production_is_rejected(tmp_path):
    request = _controller_request(
        "Use this proof.",
        attached_artifact={"artifact_ref": "artifact:test", "test_marker": run_mode.TEST_MARKER},
    )
    receipt = _route(request, tmp_path)

    assert receipt["route_status"] == "RUN_MODE_CONTEXT_REJECTED"
    assert "test_artifact_marker_rejected_in_production" in receipt["blockers"]


def test_test_artifacts_cannot_become_production_proof(tmp_path):
    artifact = {"artifact_ref": "proof:test-sqlite", "test_run_id": "test_run:1", "test_marker": run_mode.TEST_MARKER}
    rejection = run_mode.reject_test_artifact_in_production(
        tmp_path / "run_mode.sqlite",
        artifact,
        rejected_by="test",
        generated_at=FIXED_NOW,
    )

    assert rejection["schema_version"] == run_mode.TEST_ARTIFACT_REJECTION_SCHEMA
    assert run_mode.production_claim_accepts_artifact(artifact, claim_kind="client_was_emailed") is False
    assert run_mode.production_claim_accepts_artifact(artifact, claim_kind="paid") is False


def test_production_mode_cannot_use_test_adapters(tmp_path):
    context = run_mode.default_run_mode_context(generated_at=FIXED_NOW)
    receipt = run_mode.build_test_execution_receipt(
        tmp_path / "run_mode.sqlite",
        run_mode_context=context,
        action_kind="dry_run_email_receipt",
        target_ref=run_mode.ALLOWLISTED_TEST_EMAIL,
        generated_at=FIXED_NOW,
    )

    assert receipt["status"] == "TEST_ADAPTER_BLOCKED_IN_PRODUCTION"
    assert receipt["email_send_performed"] is False
    assert receipt["production_write_performed"] is False


def test_test_mode_keeps_protected_production_paths_blocked(tmp_path):
    _route(_set_mode_request(run_mode.TEST_DRY_RUN), tmp_path)
    receipt = _route(_controller_request("Submit Coupa and mark this paid in the ledger as a test."), tmp_path)

    assert receipt["run_mode"] == run_mode.TEST_DRY_RUN
    assert receipt["authority_boundary"]["coupa_allowed"] is False
    assert receipt["authority_boundary"]["ledger_mutation_allowed"] is False
    assert receipt["authority_boundary"]["paid_marking_allowed"] is False
    assert receipt["machine_proof"]["business_action_performed"] is False


def test_capability_gap_and_authority_request_include_run_mode():
    context = _run_context(run_mode.TEST_DRY_RUN)
    response = capability_loop.build_email_lookup_gap_response(
        "Have we received any emails from Annette?",
        world_ref="finance",
        thread_ref="capital_hilton",
        run_mode_context=context,
        generated_at=FIXED_NOW,
    )

    assert response["run_mode_context"]["run_mode"] == run_mode.TEST_DRY_RUN
    assert response["capability_gap"]["requested_scope"]["run_mode"] == run_mode.TEST_DRY_RUN
    assert response["operator_authority_request"]["requested_scope"]["run_mode"] == run_mode.TEST_DRY_RUN


def test_grant_in_test_mode_is_test_scoped_only():
    context = _run_context(run_mode.TEST_DRY_RUN)
    response = capability_loop.build_email_lookup_gap_response(
        "Did Glenn acknowledge the invoice?",
        world_ref="finance",
        thread_ref="st_annes",
        run_mode_context=context,
        generated_at=FIXED_NOW,
    )
    grant = capability_loop.compile_authority_grant(
        "OK, I grant you access to do that.",
        active_authority_request=response["operator_authority_request"],
        generated_at=FIXED_NOW,
    )

    assert grant["authority_grant_created"] is True
    assert grant["granted_scope"]["run_mode"] == run_mode.TEST_DRY_RUN
    assert "send_email" in grant["denied_actions"]


def test_switching_back_to_production_prevents_test_artifact_reuse(tmp_path):
    _route(_set_mode_request(run_mode.TEST_DRY_RUN), tmp_path)
    _route(_set_mode_request(run_mode.PRODUCTION), tmp_path)
    receipt = _route(
        _controller_request("Use this test proof.", attached_artifact={"test_marker": run_mode.TEST_MARKER}),
        tmp_path,
    )

    assert receipt["run_mode"] == run_mode.PRODUCTION
    assert receipt["route_status"] == "RUN_MODE_CONTEXT_REJECTED"


def test_vague_grant_all_access_does_not_grant_without_active_request(tmp_path):
    receipt = _route(_controller_request("I grant all access.", world="finance", thread="capital_hilton"), tmp_path)

    # Integrated evolution (141, 2026-07-09): the refusal guard may claim the
    # contextless blanket grant before the authority loop sees it. Invariant
    # unchanged: nothing is granted.
    rr = receipt.get("route_result") or {}
    if receipt.get("route_status") == "NEEDS_VERIFICATION" and "capability_authority" in rr:
        assert rr["capability_authority"]["operator_authority_grant"]["grant_status"] == "NEEDS_ACTIVE_AUTHORITY_REQUEST"
        assert rr["machine_proof"]["authority_grant_compiled"] is False
    else:
        blob = str(receipt).lower()
        assert "refus" in blob or "never run" in blob or "cannot" in blob
    assert not _unsafe_true_grants(receipt)

def test_mac_style_controller_fixture_produces_run_mode_aware_response(tmp_path):
    receipt = _route(_controller_request("Have we received any emails from Annette?"), tmp_path)

    assert receipt["request_type"] == controller_router.REQUEST_TYPE
    assert receipt["run_mode"] == run_mode.PRODUCTION
    assert receipt["dynamic_card_response"]["run_mode"] == run_mode.PRODUCTION
    assert receipt["route_status"] == "MAKE_IT_SO_AUTHORITY_REQUEST_READY"
    assert receipt["route_result"]["workflow_request_type_emitted"] == ""


def test_existing_email_lookup_scenarios_still_use_shared_capability_gap(tmp_path):
    cases = [
        ("Have we received any emails from Annette?", "finance", "capital_hilton"),
        ("Can you check my email and see the new accountant's name, email, and role?", "finance", "live_arts_md"),
        ("Did Glenn acknowledge the invoice or payment timing?", "finance", "st_annes"),
    ]
    for text, world, thread in cases:
        receipt = _route(_controller_request(text, world=world, thread=thread), tmp_path)
        assert receipt["route_status"] == "MAKE_IT_SO_AUTHORITY_REQUEST_READY"
        assert receipt["route_result"]["make_it_so_objective"]["capability_authority"]["capability_gap"]["capability_id"] == capability_loop.READ_ONLY_EMAIL_LOOKUP
        assert receipt["route_result"]["workflow_request_type_emitted"] == ""


def test_run_mode_set_envelope_is_classified_by_request_processor():
    request = {"request_type": run_mode.RUN_MODE_SET_REQUEST_SCHEMA}

    assert openclaw_request_processor.is_operator_controller_event_request(request) is True


def test_unsafe_true_grant_scan_clean_for_representative_outputs(tmp_path):
    _route(_set_mode_request(run_mode.TEST_DRY_RUN), tmp_path)
    dry_receipt = _route(_controller_request("Send a dry-run email to winshiplive@gmail.com."), tmp_path)
    capability_receipt = _route(_controller_request("Have we received any emails from Annette?"), tmp_path)

    assert dry_receipt["route_result"]["test_execution_receipt"]["status"] == "DRY_RUN_RECORDED"
    assert dry_receipt["route_result"]["test_execution_receipt"]["email_send_performed"] is False
    assert capability_receipt["route_result"]["workflow_request_type_emitted"] == ""
    assert not _unsafe_true_grants(dry_receipt)
    assert not _unsafe_true_grants(capability_receipt)

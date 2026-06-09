import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import make_it_so_objective_loop as make_loop
import operator_conversation_router
import proof_to_response_verifier
import read_only_email_lookup_connector as connector


FIXED_NOW = "2026-06-09T18:00:00+00:00"


def _authority(scope=None):
    return {
        "schema_version": "OPERATOR_AUTHORITY_GRANT_V0",
        "grant_id": "operator_authority_grant:test-read-only-email",
        "granted_capability_id": connector.CAPABILITY_ID,
        "granted_actions": list(connector.READ_ONLY_EMAIL_ACTIONS),
        "granted_scope": scope
        or {
            "target_world_ref": "finance",
            "target_thread_ref": "capital_hilton",
            "target_project_ref": "",
        },
        "denied_actions": list(connector.DENIED_ACTIONS),
        "verifier_status": "VERIFIED_READ_ONLY_SCOPE",
    }


def _lookup_request(text="Have we received any emails from Annette?", *, run_mode="production"):
    return connector.build_lookup_request_from_operator_context(
        operator_text=text,
        world_ref="finance",
        thread_ref="capital_hilton",
        run_mode_context={"run_mode": run_mode, "test_run_id": "test_run:email-lookup", "test_marker": "OPENCLAW_TEST_ONLY_DO_NOT_USE_AS_PROOF_V0"},
        generated_at=FIXED_NOW,
    )


def _route(text, tmp_path, *, world="finance", thread="capital_hilton"):
    return operator_conversation_router.route_conversation_text(
        {
            "request_id": f"read_only_email_connector_{world}_{thread}_{abs(hash(text))}",
            "request_type": operator_conversation_router.REQUEST_TYPE,
            "controller_event_type": "chat_goal",
            "operator_text": text,
            "current_world_ref": world,
            "current_thread_ref": thread,
            "selected_card_id": "dynamic_card.read_only_email_connector",
            "selected_action_id": "",
            "authority_boundary": dict(operator_conversation_router.AUTHORITY_BOUNDARY),
        },
        sqlite_path=tmp_path / "conversation.sqlite",
        generated_at=FIXED_NOW,
    )


def _unsafe_true_grants(value, path="$"):
    unsafe = set(connector.UNSAFE_TRUE_KEYS) | {"authority_granted", "sent", "paid", "submitted"}
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


def test_connector_status_reports_not_configured_without_external_credential():
    status = connector.get_connector_status(env={}, operator_config_path="", generated_at=FIXED_NOW)

    assert status["schema_version"] == connector.EMAIL_CONNECTOR_STATUS_SCHEMA
    assert status["capability_id"] == connector.CAPABILITY_ID
    assert status["configured"] is False
    assert status["credential_source"] == "none"
    assert connector.READ_ONLY_GMAIL_SCOPE in status["scopes"]
    assert status["missing_setup"]
    assert status["authority_boundary"]["email_send_allowed"] is False


def test_missing_credential_setup_requirement_contract_is_precise_and_no_repo_secret():
    status = connector.get_connector_status(env={}, generated_at=FIXED_NOW)
    requirement = connector.build_setup_requirement(status, generated_at=FIXED_NOW)

    assert requirement["schema_version"] == connector.EMAIL_CONNECTOR_SETUP_REQUIREMENT_SCHEMA
    assert requirement["no_repo_secret_policy"] is True
    assert requirement["required_scope"] == connector.READ_ONLY_GMAIL_SCOPE
    assert set(connector.FORBIDDEN_GMAIL_SCOPES) <= set(requirement["denied_scopes"])
    assert "outside the repo" in " ".join(requirement["human_setup_steps"]).lower()


def test_missing_credential_becomes_objective_blocker_not_generic_failure():
    objective = make_loop.build_objective_request(
        operator_goal_text="Have we received any emails from Annette?",
        requested_outcome="answer from email evidence",
        capability_id=connector.CAPABILITY_ID,
        world_ref="finance",
        thread_ref="capital_hilton",
        generated_at=FIXED_NOW,
    )
    status = connector.get_connector_status(env={}, generated_at=FIXED_NOW)
    blocker = connector.produce_missing_credential_blocker(objective, status, generated_at=FIXED_NOW)

    assert blocker["schema_version"] == make_loop.OBJECTIVE_BLOCKER_SCHEMA
    assert blocker["blocker_kind"] == "missing_read_only_email_connector"
    assert blocker["requires_human_secret_or_external_login"] is True
    assert "gmail.readonly" in blocker["required_next_input"]


def test_test_dry_run_lookup_records_dry_run_without_real_email_access():
    request = _lookup_request(run_mode="test_dry_run")
    result = connector.perform_read_only_lookup(
        request,
        connector_status=connector.get_connector_status(env={}, generated_at=FIXED_NOW),
        authority_grant=None,
        generated_at=FIXED_NOW,
    )

    assert result["schema_version"] == connector.READ_ONLY_EMAIL_LOOKUP_RESULT_SCHEMA
    assert result["status"] == "LOOKUP_DRY_RUN"
    assert result["real_email_access_performed"] is False
    assert result["result_count"] == 0
    assert result["denied_actions_preserved"] is True
    assert result["authority_boundary"]["email_send_allowed"] is False


def test_production_lookup_without_authority_is_blocked():
    result = connector.perform_read_only_lookup(
        _lookup_request(run_mode="production"),
        connector_status=connector.get_connector_status(env={}, generated_at=FIXED_NOW),
        authority_grant=None,
        generated_at=FIXED_NOW,
    )

    assert result["status"] == "BLOCKED_BY_AUTHORITY"
    assert result["result_count"] == 0
    assert result["email_checked"] is False


def test_production_lookup_with_authority_but_no_credential_returns_connector_blocker():
    result = connector.perform_read_only_lookup(
        _lookup_request(run_mode="production"),
        connector_status=connector.get_connector_status(env={}, generated_at=FIXED_NOW),
        authority_grant=_authority(),
        generated_at=FIXED_NOW,
    )

    assert result["status"] == "CONNECTOR_MISSING_CREDENTIAL"
    assert result["setup_requirement"]["schema_version"] == connector.EMAIL_CONNECTOR_SETUP_REQUIREMENT_SCHEMA
    assert result["email_checked"] is False
    assert result["real_email_access_performed"] is False


def test_connector_only_requests_gmail_readonly_and_denies_write_scopes():
    scopes = connector.requested_gmail_scopes()

    assert scopes == [connector.READ_ONLY_GMAIL_SCOPE]
    for forbidden in connector.FORBIDDEN_GMAIL_SCOPES:
        assert forbidden not in scopes
    assert connector.validate_requested_scopes(scopes)["valid"] is True
    assert connector.validate_requested_scopes([connector.READ_ONLY_GMAIL_SCOPE, "https://www.googleapis.com/auth/gmail.send"])["valid"] is False


def test_denied_actions_cover_email_mutation_gmail_ui_browser_and_business_actions():
    denied = set(connector.DENIED_ACTIONS)

    assert {
        "send_email",
        "compose_email",
        "delete_email",
        "archive_email",
        "mark_email_read",
        "mark_email_unread",
        "modify_email_labels",
        "open_gmail_ui",
        "open_browser",
        "coupa_submit",
        "mark_paid",
        "mutate_ledger",
        "mutate_workbook",
        "export_pdf",
        "git_push",
        "git_merge",
    } <= denied


def test_evidence_summary_is_redacted_and_raw_body_is_not_exposed():
    summary = connector.summarize_email_evidence(
        {
            "message_id": "msg-123",
            "thread_id": "thread-456",
            "from": "annette@example.com",
            "to": "winship@example.com",
            "subject": "Payment update for Capital Hilton",
            "date": "2026-06-09T10:00:00+00:00",
            "snippet": "Here is the payment update. Full private body should not pass through.",
            "body": "private body that must not be exposed",
        },
        matched_terms=["Annette", "payment"],
        proof_scope={"target_world_ref": "finance", "target_thread_ref": "capital_hilton"},
        generated_at=FIXED_NOW,
    )

    encoded = json.dumps(summary).lower()
    assert summary["schema_version"] == connector.EMAIL_EVIDENCE_SUMMARY_SCHEMA
    assert summary["message_id_hash"] != "msg-123"
    assert summary["thread_id_hash"] != "thread-456"
    assert summary["from_redacted"] != "annette@example.com"
    assert summary["to_redacted"] != "winship@example.com"
    assert summary["raw_body_available"] is False
    assert "private body" not in encoded


def test_verifier_blocks_unsupported_email_claims_without_lookup_result():
    claims = {
        "draft_headline": "Email checked",
        "draft_body": "I checked email and Annette replied.",
        "draft_next_step": "Save contact.",
    }

    unsupported = proof_to_response_verifier.unsupported_completion_claims(claims)
    assert "checked email" in unsupported
    assert "annette replied" in unsupported


def test_lookup_result_with_synthetic_fixture_supports_redacted_evidence_only():
    request = _lookup_request(run_mode="test_live")
    result = connector.perform_read_only_lookup(
        request,
        connector_status=connector.get_connector_status(env={}, generated_at=FIXED_NOW),
        authority_grant=_authority(),
        fixture_messages=[
            {
                "message_id": "fixture-msg-1",
                "thread_id": "fixture-thread-1",
                "from": "annette@example.com",
                "to": "winship@example.com",
                "subject": "Capital Hilton payment processing",
                "date": "2026-06-09T10:00:00+00:00",
                "snippet": "Payment is processing.",
                "body": "synthetic private body",
            }
        ],
        generated_at=FIXED_NOW,
    )

    assert result["status"] == "LOOKUP_TEST_FIXTURE_USED"
    assert result["result_count"] == 1
    assert result["evidence_summaries"][0]["raw_body_available"] is False
    assert "synthetic private body" not in json.dumps(result).lower()


def test_make_it_so_status_includes_connector_setup_requirement_after_package_result(tmp_path):
    first = _route("Have we received any emails from Annette?", tmp_path)
    assert first["route_status"] == "MAKE_IT_SO_AUTHORITY_REQUEST_READY"
    grant = _route("Make it so.", tmp_path)
    assert grant["route_status"] == "MAKE_IT_SO_GRANT_COMPILED"

    repeat = _route("Have we received any emails from Annette?", tmp_path)
    payload = repeat["make_it_so_objective"]

    assert payload["email_connector_status"]["schema_version"] == connector.EMAIL_CONNECTOR_STATUS_SCHEMA
    assert payload["email_connector_status"]["configured"] is False
    assert payload["email_connector_setup_requirement"]["schema_version"] == connector.EMAIL_CONNECTOR_SETUP_REQUIREMENT_SCHEMA
    assert repeat["primary_next_step"]["next_step_kind"] in {"configure_connector", "request_authority", "pick_up_work_package"}
    assert repeat["workflow_request_type_emitted"] == ""


def test_annette_live_arts_and_glenn_route_to_same_connector_setup_path_once_authority_exists(tmp_path):
    cases = [
        ("Have we received any emails from Annette?", "finance", "capital_hilton"),
        ("Can you check my email and see the new accountant's name, email, and role?", "finance", "live_arts_md"),
        ("Did Glenn acknowledge the invoice or payment timing?", "finance", "st_annes"),
    ]

    for text, world, thread in cases:
        case_dir = tmp_path / thread
        first = _route(text, case_dir, world=world, thread=thread)
        assert first["make_it_so_objective"]["objective_request"]["capability_id"] == connector.CAPABILITY_ID
        _route("Make it so.", case_dir, world=world, thread=thread)
        repeat = _route(text, case_dir, world=world, thread=thread)
        assert repeat["make_it_so_objective"]["email_connector_status"]["capability_id"] == connector.CAPABILITY_ID
        assert repeat["workflow_request_type_emitted"] == ""


def test_exported_connector_read_model_contains_no_secret_material(tmp_path):
    payload = connector.export_read_only_email_lookup_connector(
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Read Only Email Lookup Connector.md",
        generated_at=FIXED_NOW,
    )
    local = tmp_path / "read_models" / "read_only_email_lookup_connector.json"
    bridge = tmp_path / "bridge" / "read_only_email_lookup_connector.json"

    assert payload["status"] == connector.READY_STATUS
    assert local.exists()
    assert bridge.exists()
    assert json.loads(local.read_text()) == json.loads(bridge.read_text())
    encoded = json.dumps(payload).lower()
    for forbidden in ("refresh_token", "access_token", "client_secret", "password=", "api_key="):
        assert forbidden not in encoded


def test_connector_payload_has_no_unsafe_true_grants():
    result = connector.perform_read_only_lookup(
        _lookup_request(run_mode="production"),
        connector_status=connector.get_connector_status(env={}, generated_at=FIXED_NOW),
        authority_grant=_authority(),
        generated_at=FIXED_NOW,
    )

    assert _unsafe_true_grants(result) == []


def test_existing_gmail_broker_discovery_classifies_wrapper_as_restrictable_not_direct_safe():
    candidate = connector.discover_existing_gmail_broker_candidate()

    assert candidate["classification"] == "RESTRICTABLE_BROKER"
    assert candidate["candidate_path"].endswith("google_broker_readonly_wrapper.py")
    assert candidate["runtime_language"] == "python"
    assert candidate["fixture_readback_available"] is True
    assert candidate["live_bridge_allowed"] is False
    assert candidate["safe_read_only_direct"] is False
    assert connector.READ_ONLY_GMAIL_SCOPE in candidate["allowed_scopes"]
    assert "https://www.googleapis.com/auth/gmail.compose" in candidate["denied_scope_refs_found"]
    assert candidate["credential_paths_inside_repo"]


def test_existing_broker_candidate_is_reported_in_connector_status_without_reading_credentials():
    status = connector.get_connector_status(env={}, generated_at=FIXED_NOW, include_broker_discovery=True)

    assert status["configured"] is False
    assert status["credential_file_read"] is False
    assert status["secret_material_loaded"] is False
    assert status["existing_broker_candidate"]["classification"] == "RESTRICTABLE_BROKER"
    assert status["existing_broker_candidate"]["live_bridge_allowed"] is False


def test_test_live_can_use_existing_broker_fixture_without_real_email_access():
    result = connector.perform_read_only_lookup(
        _lookup_request(run_mode="test_live"),
        connector_status=connector.get_connector_status(env={}, generated_at=FIXED_NOW),
        authority_grant=_authority(),
        existing_broker_candidate=connector.discover_existing_gmail_broker_candidate(),
        use_existing_broker_fixture=True,
        generated_at=FIXED_NOW,
    )

    assert result["status"] == "LOOKUP_TEST_FIXTURE_USED"
    assert result["existing_broker_fixture_used"] is True
    assert result["real_email_access_performed"] is False
    assert result["email_checked"] is False
    assert result["result_count"] >= 1
    assert result["evidence_summaries"][0]["raw_body_available"] is False
    assert "Fixture metadata subject" not in json.dumps(result)


def test_production_with_authority_refuses_restrictable_broker_live_bridge_without_safe_credential():
    result = connector.perform_read_only_lookup(
        _lookup_request(run_mode="production"),
        connector_status=connector.get_connector_status(env={}, generated_at=FIXED_NOW),
        authority_grant=_authority(),
        existing_broker_candidate=connector.discover_existing_gmail_broker_candidate(),
        generated_at=FIXED_NOW,
    )

    assert result["status"] == "CONNECTOR_MISSING_CREDENTIAL"
    assert result["existing_broker_candidate"]["classification"] == "RESTRICTABLE_BROKER"
    assert result["broker_live_bridge_allowed"] is False
    assert result["email_checked"] is False
    assert result["real_email_access_performed"] is False

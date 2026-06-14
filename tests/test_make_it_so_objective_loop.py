import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import capability_authority_loop
import global_run_mode_context
import make_it_so_objective_loop as make_loop
import operator_conversation_router
import test_effect_adapters


FIXED_NOW = "2026-06-09T12:00:00+00:00"


def _request(text, *, world="finance", thread="capital_hilton", **extra):
    request = {
        "request_id": f"make_it_so_test_{world}_{thread}_{abs(hash(text))}",
        "request_type": operator_conversation_router.REQUEST_TYPE,
        "controller_event_type": "chat_goal",
        "operator_text": text,
        "current_world_ref": world,
        "current_thread_ref": thread,
        "selected_card_id": "dynamic_card.make_it_so_test",
        "selected_action_id": "",
        "authority_boundary": dict(operator_conversation_router.AUTHORITY_BOUNDARY),
        "authority_requested": [],
    }
    request.update(extra)
    return request


def _route(text, tmp_path, *, world="finance", thread="capital_hilton", **extra):
    return operator_conversation_router.route_conversation_text(
        _request(text, world=world, thread=thread, **extra),
        sqlite_path=tmp_path / "conversation.sqlite",
        generated_at=FIXED_NOW,
    )


def _unsafe_true_grants(value, path="$"):
    unsafe = (
        set(operator_conversation_router.UNSAFE_TRUE_KEYS)
        | set(make_loop.AUTHORITY_BOUNDARY)
        | {"sent", "paid", "submitted", "authority_granted"}
    )
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


def test_real_router_email_lookup_creates_objective_and_make_it_so_request(tmp_path):
    result = _route("Have we received any emails from Annette?", tmp_path)

    assert result["route_status"] == "MAKE_IT_SO_AUTHORITY_REQUEST_READY"
    assert result["backend_route"] == "make_it_so_objective_loop.start_email_lookup_objective"
    assert result["make_it_so_objective"]["objective_request"]["schema_version"] == make_loop.OBJECTIVE_REQUEST_SCHEMA
    assert result["make_it_so_objective"]["capability_requirement"]["schema_version"] == make_loop.OBJECTIVE_CAPABILITY_REQUIREMENT_SCHEMA
    assert result["make_it_so_objective"]["make_it_so_authority_request"]["schema_version"] == make_loop.MAKE_AUTHORITY_REQUEST_SCHEMA
    assert result["make_it_so_objective"]["capability_authority"]["capability_gap"]["capability_id"] == make_loop.READ_ONLY_EMAIL_LOOKUP
    assert result["workflow_request_type_emitted"] == ""


def test_missing_capability_creates_objective_request_requirement_and_blocker(tmp_path):
    result = make_loop.start_email_lookup_objective(
        "Have we received any emails from Annette?",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=tmp_path / "loop.sqlite",
        generated_at=FIXED_NOW,
    )

    assert result["response_status"] == "MAKE_IT_SO_AUTHORITY_REQUEST_READY"
    assert result["objective_request"]["schema_version"] == make_loop.OBJECTIVE_REQUEST_SCHEMA
    assert result["capability_requirement"]["schema_version"] == make_loop.OBJECTIVE_CAPABILITY_REQUIREMENT_SCHEMA
    assert result["objective_blocker"]["schema_version"] == make_loop.OBJECTIVE_BLOCKER_SCHEMA
    assert result["objective_blocker"]["blocker_kind"] == "missing_capability"


def test_repeating_same_blocked_request_returns_objective_status_not_generic_blocker(tmp_path):
    db = tmp_path / "loop.sqlite"
    first = make_loop.start_email_lookup_objective(
        "Have we received any emails from Annette?",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )
    second = make_loop.start_email_lookup_objective(
        "Have we received any emails from Annette?",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )

    assert first["response_status"] == "MAKE_IT_SO_AUTHORITY_REQUEST_READY"
    assert second["response_status"] == "OBJECTIVE_STATUS_READY"
    assert second["objective_blocker"]["already_explained"] is True


def test_make_it_so_with_active_request_creates_grant_plan_package_and_receipt(tmp_path):
    db = tmp_path / "loop.sqlite"
    first = make_loop.start_email_lookup_objective(
        "Have we received any emails from Annette?",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )
    grant = make_loop.handle_make_it_so_grant(
        "Make it so.",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )

    assert grant["response_status"] == "MAKE_IT_SO_GRANT_COMPILED"
    assert grant["make_it_so_authority_grant"]["schema_version"] == make_loop.MAKE_AUTHORITY_GRANT_SCHEMA
    assert grant["make_it_so_authority_grant"]["request_id"] == first["make_it_so_authority_request"]["request_id"]
    assert grant["capability_enablement_plan"]["schema_version"] == make_loop.ENABLEMENT_PLAN_SCHEMA
    assert grant["codex_work_package"]["schema_version"] == make_loop.CODEX_WORK_PACKAGE_SCHEMA
    assert grant["objective_execution_receipt"]["schema_version"] == make_loop.EXECUTION_RECEIPT_SCHEMA


def test_read_only_email_connector_package_scope_allows_connector_boundary_files(tmp_path):
    db = tmp_path / "loop.sqlite"
    make_loop.start_email_lookup_objective(
        "Have we received any emails from Annette?",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )
    result = make_loop.handle_make_it_so_grant(
        "Make it so.",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )
    package = result["codex_work_package"]

    assert "read_only_email_lookup_connector.py" in package["allowed_file_paths"]
    assert "tests/test_read_only_email_lookup_connector.py" in package["allowed_file_paths"]
    assert "python3 -m pytest tests/test_read_only_email_lookup_connector.py -q -s" in package["validation_commands"]
    assert "python3 -m json.tool generated/read_models/read_only_email_lookup_connector.json" in package["validation_commands"]
    assert "git push" in package["denied_commands"]
    assert "send email" in package["denied_commands"]


def test_make_it_so_with_no_active_request_creates_no_authority(tmp_path):
    result = make_loop.handle_make_it_so_grant(
        "Make it so.",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=tmp_path / "loop.sqlite",
        generated_at=FIXED_NOW,
    )

    assert result["response_status"] == "NEEDS_ACTIVE_MAKE_IT_SO_REQUEST"
    assert result["authority_grant_created"] is False


def test_broad_make_it_so_grant_is_narrowed_to_active_scope(tmp_path):
    db = tmp_path / "loop.sqlite"
    make_loop.start_email_lookup_objective(
        "Can you check my email and see the new accountant's name, email, and role?",
        world_ref="finance",
        thread_ref="live_arts_md",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )
    result = make_loop.handle_make_it_so_grant(
        "Go ahead and grant all access.",
        world_ref="finance",
        thread_ref="live_arts_md",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )

    grant = result["make_it_so_authority_grant"]
    assert grant["scope"]["target_world_ref"] == "finance"
    assert grant["scope"]["target_thread_ref"] == "live_arts_md"
    assert "send_email" in grant["denied_actions"]


def test_denied_actions_remain_denied_after_make_it_so_grant(tmp_path):
    db = tmp_path / "loop.sqlite"
    make_loop.start_email_lookup_objective(
        "Did Glenn acknowledge the invoice or payment timing?",
        world_ref="finance",
        thread_ref="st_annes",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )
    result = make_loop.handle_make_it_so_grant(
        "Yes, build it.",
        world_ref="finance",
        thread_ref="st_annes",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )

    denied = set(result["make_it_so_authority_grant"]["denied_actions"])
    assert {"send_email", "mutate_ledger", "mark_paid", "open_gmail_ui", "open_browser"} <= denied
    assert result["authority_boundary"]["email_send_allowed"] is False
    assert result["authority_boundary"]["paid"] is False


def test_adapter_missing_becomes_objective_human_blocker_not_dead_end(tmp_path):
    db = tmp_path / "loop.sqlite"
    make_loop.start_email_lookup_objective(
        "Have we received any emails from Annette?",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )
    result = make_loop.handle_make_it_so_grant(
        "Make it so.",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )

    blocker = result["objective_blocker"]
    assert blocker["blocker_kind"] == "missing_connector"
    assert blocker["requires_human_secret_or_external_login"] is True
    assert "connector" in blocker["human_summary"].lower()
    assert "store secrets" in blocker["human_summary"].lower()


def test_missing_email_connector_is_explained_once_and_status_is_reused(tmp_path):
    db = tmp_path / "loop.sqlite"
    make_loop.start_email_lookup_objective(
        "Have we received any emails from Annette?",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )
    make_loop.handle_make_it_so_grant(
        "Make it so.",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )
    repeat = make_loop.start_email_lookup_objective(
        "Have we received any emails from Annette?",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )

    assert repeat["response_status"] == "OBJECTIVE_STATUS_READY"
    assert repeat["objective_blocker"]["already_explained"] is True


def test_sqlite_test_effect_adapter_can_run_under_objective_plan(tmp_path):
    result = make_loop.run_test_effect_objective(
        effect_kind=test_effect_adapters.SQLITE_WRITE,
        target="test/sqlite",
        sqlite_path=tmp_path / "loop.sqlite",
        effect_sqlite_path=tmp_path / "effects.sqlite",
        generated_at=FIXED_NOW,
    )

    assert result["response_status"] == "TEST_EFFECT_OBJECTIVE_RAN"
    assert result["test_effect_receipt"]["status"] == test_effect_adapters.TEST_LIVE_EXECUTED
    assert result["objective_execution_receipt"]["status"] == make_loop.STATUS_TEST_PASSED


def test_logic_copy_test_effect_creates_test_copy_without_mutating_original(tmp_path):
    original = tmp_path / "song.logicx"
    original.write_text("fixture project", encoding="utf-8")
    before = original.read_text(encoding="utf-8")
    result = make_loop.run_test_effect_objective(
        effect_kind=test_effect_adapters.LOGIC_PROJECT_COPY,
        target=str(original),
        source_path=str(original),
        sqlite_path=tmp_path / "loop.sqlite",
        effect_sqlite_path=tmp_path / "effects.sqlite",
        workspace_root=tmp_path / "workspaces",
        generated_at=FIXED_NOW,
    )

    receipt = result["test_effect_receipt"]
    assert receipt["status"] == test_effect_adapters.TEST_LIVE_EXECUTED
    assert "__OPENCLAW_TEST__" in receipt["workspace_artifact"]["test_copy_path"]
    assert original.read_text(encoding="utf-8") == before


def test_capability_registry_records_status_transitions(tmp_path):
    db = tmp_path / "loop.sqlite"
    result = make_loop.run_test_effect_objective(
        effect_kind=test_effect_adapters.SQLITE_WRITE,
        target="test/sqlite",
        sqlite_path=db,
        effect_sqlite_path=tmp_path / "effects.sqlite",
        generated_at=FIXED_NOW,
    )

    con = sqlite3.connect(db)
    try:
        row = con.execute(
            "select status from capability_registry where capability_id = ?",
            (result["objective_request"]["capability_id"],),
        ).fetchone()
    finally:
        con.close()
    assert row[0] == make_loop.STATUS_TEST_PASSED


def test_ready_registry_without_connector_does_not_bypass_connector_gate(tmp_path):
    db = tmp_path / "loop.sqlite"
    scope = {"target_world_ref": "finance", "target_thread_ref": "capital_hilton", "target_project_ref": ""}
    with sqlite3.connect(db) as con:
        make_loop._ensure_tables(con)
        make_loop._store_registry(
            con,
            make_loop._registry_record(
                capability_id=make_loop.READ_ONLY_EMAIL_LOOKUP,
                status="production_ready",
                scope=scope,
                generated_at=FIXED_NOW,
            ),
            scope,
        )
        con.commit()
    result = make_loop.start_email_lookup_objective(
        "Have we received any emails from Annette?",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )

    assert result["response_status"] == "MAKE_IT_SO_AUTHORITY_REQUEST_READY"
    assert result["email_connector_status"]["configured"] is False
    assert result["email_connector_setup_requirement"]["no_repo_secret_policy"] is True
    assert result["capability_requirement"]["production_available"] is False


def test_ready_registry_with_unvalidated_connector_does_not_route_to_lookup(tmp_path, monkeypatch):
    db = tmp_path / "loop.sqlite"
    scope = {"target_world_ref": "finance", "target_thread_ref": "capital_hilton", "target_project_ref": ""}
    with sqlite3.connect(db) as con:
        make_loop._ensure_tables(con)
        make_loop._store_registry(
            con,
            make_loop._registry_record(
                capability_id=make_loop.READ_ONLY_EMAIL_LOOKUP,
                status="production_ready",
                scope=scope,
                generated_at=FIXED_NOW,
            ),
            scope,
        )
        con.commit()

    def unvalidated_status(*, generated_at=None):
        return {
            "schema_version": "EMAIL_CONNECTOR_STATUS_V0",
            "connector_id": "email_connector:gmail_readonly_v0",
            "capability_id": make_loop.READ_ONLY_EMAIL_LOOKUP,
            "configured": True,
            "setup_status": "credential_present_unvalidated",
            "granted_scopes_status": "unknown",
            "validated_readonly": False,
            "missing_setup": [],
            "denied_scopes": ["https://www.googleapis.com/auth/gmail.send"],
            "denied_actions": ["send_email"],
            "receipt_ref": "email_connector_status_receipt:test",
        }

    monkeypatch.setattr(make_loop.read_only_email_lookup_connector, "get_connector_status", unvalidated_status)

    result = make_loop.start_email_lookup_objective(
        "Have we received any emails from Annette?",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )

    assert result["response_status"] == "MAKE_IT_SO_AUTHORITY_REQUEST_READY"
    assert result["email_connector_status"]["configured"] is True
    assert result["email_connector_status"]["validated_readonly"] is False
    assert result["operator_display"]["next_safe_action"] == "Say: Make it so."


def test_read_email_grant_does_not_grant_send_or_ledger_or_test_live_production_authority(tmp_path):
    db = tmp_path / "loop.sqlite"
    make_loop.start_email_lookup_objective(
        "Have we received any emails from Annette?",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )
    result = make_loop.handle_make_it_so_grant(
        "Make it so.",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=db,
        generated_at=FIXED_NOW,
    )
    grant = result["make_it_so_authority_grant"]

    assert capability_authority_loop.READ_ONLY_EMAIL_LOOKUP in grant["granted_capabilities"]
    assert "send_email" in grant["denied_actions"]
    assert "mutate_ledger" in grant["denied_actions"]
    assert "test authority does not become production authority" in json.dumps(result).lower()


def test_raw_authority_granted_remains_rejected_in_router(tmp_path):
    result = _route(
        "Have we received any emails from Annette?",
        tmp_path,
        authority_granted=True,
    )

    assert result["machine_proof"]["incoming_raw_authority_granted_accepted"] is False
    assert result["machine_proof"]["raw_authority_granted_trusted"] is False
    assert result["route_status"] == "MAKE_IT_SO_AUTHORITY_REQUEST_READY"


def test_annette_live_arts_and_glenn_prompts_route_through_objective_path(tmp_path):
    cases = [
        ("Have we received any emails from Annette?", "finance", "capital_hilton"),
        ("Can you check my email and see the new accountant's name, email, and role?", "finance", "live_arts_md"),
        ("Did Glenn acknowledge the invoice or payment timing?", "finance", "st_annes"),
    ]
    for text, world, thread in cases:
        result = _route(text, tmp_path, world=world, thread=thread)
        assert result["route_status"] == "MAKE_IT_SO_AUTHORITY_REQUEST_READY"
        assert result["backend_route"] == "make_it_so_objective_loop.start_email_lookup_objective"
        assert result["workflow_request_type_emitted"] == ""
        assert "WORKFLOW_PACKAGE_REQUEST_V0" not in json.dumps(result)


def test_verifier_blocks_unsupported_email_claims_without_receipts():
    bad = {
        "draft_headline": "Email checked",
        "draft_body": "I checked Gmail, Annette replied, the draft was sent, the contact was saved, paid was marked, and the ledger was updated.",
    }

    blocked = capability_authority_loop.unsupported_email_lookup_claims(bad)
    assert {"email_checked", "email_received", "draft_sent", "contact_saved", "paid_marked", "ledger_updated"} <= set(blocked)


def test_no_workflow_package_request_for_make_it_so_chat_goals(tmp_path):
    result = _route("Have we received any emails from Annette?", tmp_path)

    assert result["workflow_package_staged"] is False
    assert result["workflow_request_type_emitted"] == ""
    assert result["machine_proof"]["workflow_package_request_v0_emitted"] is False


def test_vague_non_make_grant_with_no_active_request_does_not_create_make_authority(tmp_path):
    result = make_loop.handle_make_it_so_grant(
        "I grant all access.",
        world_ref="finance",
        thread_ref="capital_hilton",
        sqlite_path=tmp_path / "loop.sqlite",
        generated_at=FIXED_NOW,
    )

    assert result["response_status"] == "NOT_MAKE_IT_SO_GRANT_INTENT"
    assert result["authority_grant_created"] is False


def test_make_it_so_outputs_have_no_unsafe_true_grants(tmp_path):
    first = _route("Have we received any emails from Annette?", tmp_path)
    second = _route("Make it so.", tmp_path)

    assert _unsafe_true_grants(first) == []
    assert _unsafe_true_grants(second) == []

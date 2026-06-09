import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import active_next_step_policy
import codex_work_package_lifecycle
import operator_conversation_router


FIXED_NOW = "2026-06-09T16:00:00+00:00"


def _request(text, *, world="finance", thread="capital_hilton", **extra):
    payload = {
        "request_id": f"active_next_step_{world}_{thread}_{abs(hash(text))}",
        "request_type": operator_conversation_router.REQUEST_TYPE,
        "controller_event_type": "chat_goal",
        "operator_text": text,
        "current_world_ref": world,
        "current_thread_ref": thread,
        "selected_card_id": "dynamic_card.active_next_step",
        "selected_action_id": "",
        "authority_boundary": dict(operator_conversation_router.AUTHORITY_BOUNDARY),
    }
    payload.update(extra)
    return payload


def _route(text, tmp_path, *, world="finance", thread="capital_hilton", **extra):
    return operator_conversation_router.route_conversation_text(
        _request(text, world=world, thread=thread, **extra),
        sqlite_path=tmp_path / "conversation.sqlite",
        generated_at=FIXED_NOW,
    )


def _unsafe_true_grants(value, path="$"):
    unsafe = set(operator_conversation_router.UNSAFE_TRUE_KEYS) | {
        "email_send_allowed",
        "gmail_allowed",
        "browser_access_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "ledger_posting_allowed",
        "ledger_mutation_allowed",
        "workbook_mutation_allowed",
        "pdf_export_allowed",
        "paid_marking_allowed",
        "git_push_allowed",
        "merge_allowed",
        "worker_spawn_allowed",
        "external_model_allowed",
        "lm2_tool_expansion_allowed",
        "authority_granted",
        "sent",
        "paid",
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


def test_missing_email_lookup_response_includes_active_make_it_so_next_step(tmp_path):
    result = _route("Have we received any emails from Annette?", tmp_path)

    step = result["primary_next_step"]
    assert step["schema_version"] == active_next_step_policy.NEXT_STEP_SCHEMA
    assert step["next_step_kind"] == "request_authority"
    assert step["actor"] == "operator"
    assert step["actionability"] == "needs_operator_authority"
    assert step["required_capability_id"] == "read_only_email_lookup"
    assert "Make it so" in step["exact_operator_input_needed"]
    assert result["next_step_status_receipt"]["schema_version"] == active_next_step_policy.STATUS_RECEIPT_SCHEMA


def test_annette_live_arts_and_glenn_share_email_lookup_active_next_step(tmp_path):
    cases = [
        ("Have we received any emails from Annette?", "finance", "capital_hilton"),
        ("Can you check my email and see the new accountant's name, email, and role?", "finance", "live_arts_md"),
        ("Did Glenn acknowledge the invoice or payment timing?", "finance", "st_annes"),
    ]

    for text, world, thread in cases:
        result = _route(text, tmp_path / thread, world=world, thread=thread)
        step = result["primary_next_step"]
        assert step["required_capability_id"] == "read_only_email_lookup"
        assert step["next_step_kind"] == "request_authority"
        assert result["workflow_request_type_emitted"] == ""


def test_make_it_so_grant_next_step_picks_up_bounded_work_package(tmp_path):
    _route("Have we received any emails from Annette?", tmp_path)
    result = _route("Make it so.", tmp_path)

    step = result["primary_next_step"]
    package = result["make_it_so_objective"]["codex_work_package"]
    assert step["next_step_kind"] == "pick_up_work_package"
    assert step["actor"] == "codex_worker"
    assert step["actionability"] == "needs_worker_pickup"
    assert step["related_package_id"] == package["package_id"]
    assert package["package_id"] in step["exact_operator_input_needed"]


def test_worker_bridge_missing_next_step_is_not_wait(tmp_path):
    _route("Have we received any emails from Annette?", tmp_path)
    result = _route("Make it so.", tmp_path)

    step = result["primary_next_step"]
    text = json.dumps(step).lower()
    assert step["next_step_kind"] == "pick_up_work_package"
    assert "approved codex worker bridge" in text
    assert "wait" not in step["label"].lower()
    assert "check later" not in step["human_summary"].lower()


def test_missing_email_connector_next_step_is_exact_human_setup(tmp_path):
    _route("Have we received any emails from Annette?", tmp_path)
    grant = _route("Make it so.", tmp_path)
    package = grant["make_it_so_objective"]["codex_work_package"]
    lifecycle_sqlite = tmp_path / "codex_work_package_lifecycle.sqlite"
    result = {
        "package_id": package["package_id"],
        "objective_id": package["objective_id"],
        "capability_id": package["capability_id"],
        "worker_kind": "manual_codex_handoff",
        "status": "completed",
        "authority_grant_ref": package["authority_grant_ref"],
        "files_changed": [],
        "commands_run": package["validation_commands"],
        "validation_run": package["validation_commands"],
        "unsafe_scan_summary": {"passed": True, "hits": []},
        "capability_status": "human_setup_required",
        "blocker_kind": "missing_read_only_email_connector",
        "blocker_summary": "missing_read_only_email_connector",
        "denied_actions_reported": [],
        "introduced_strings": [],
        "receipt_refs": [],
        "submitted_at": FIXED_NOW,
    }
    codex_work_package_lifecycle.ingest_worker_result(result, sqlite_path=lifecycle_sqlite, generated_at=FIXED_NOW)

    repeat = _route("Have we received any emails from Annette?", tmp_path)
    step = repeat["primary_next_step"]
    assert step["next_step_kind"] == "configure_connector"
    assert step["actor"] == "operator"
    assert step["actionability"] == "needs_human_setup"
    assert "read-only email connector" in step["exact_operator_input_needed"]
    assert "outside the repo" in step["exact_operator_input_needed"]


def test_missing_payment_proof_next_step_names_exact_proof(tmp_path):
    result = _route("What should I do here?", tmp_path)

    step = result["primary_next_step"]
    assert step["next_step_kind"] == "provide_proof"
    assert step["actor"] == "operator"
    assert "payment evidence" in step["label"].lower()
    assert "bank" in step["exact_operator_input_needed"].lower()
    assert "ledger" in json.dumps(step["denied_actions"]).lower()


def test_external_payment_wait_has_active_companion_step(tmp_path):
    result = _route("Do we just wait for payment?", tmp_path)

    step = result["primary_next_step"]
    assert step["next_step_kind"] in {"draft_only", "schedule_or_monitor", "provide_proof"}
    assert step["actionability"] != "blocked_no_safe_path"
    assert step["human_summary"].strip()
    assert step["exact_operator_input_needed"].strip()


def test_draft_only_followup_has_draft_next_step(tmp_path):
    result = _route("Never mind, just draft what I should ask Glenn.", tmp_path, thread="st_annes")

    step = result["primary_next_step"]
    assert step["next_step_kind"] == "draft_only"
    assert step["actor"] == "openclaw"
    assert "draft" in step["label"].lower()
    assert "send_email" in step["denied_actions"]


def test_do_that_with_active_next_step_resolves_to_make_it_so_grant(tmp_path):
    first = _route("Have we received any emails from Annette?", tmp_path)
    assert first["primary_next_step"]["next_step_kind"] == "request_authority"

    result = _route("Do that.", tmp_path)
    assert result["route_status"] == "MAKE_IT_SO_GRANT_COMPILED"
    assert result["resolved_active_next_step"]["next_step_id"] == first["primary_next_step"]["next_step_id"]
    assert result["primary_next_step"]["next_step_kind"] == "pick_up_work_package"


def test_do_that_with_no_active_next_step_does_not_create_authority(tmp_path):
    result = _route("Do that.", tmp_path)

    assert result["route_status"] == "NEEDS_VERIFICATION"
    assert result["primary_next_step"]["next_step_kind"] == "no_safe_action_available"
    assert result["machine_proof"]["make_it_so_authority_grant_compiled"] is False
    assert result["machine_proof"]["raw_authority_granted_trusted"] is False


def test_no_primary_response_contains_passive_only_next_step_text(tmp_path):
    prompts = [
        ("Have we received any emails from Annette?", "finance", "capital_hilton"),
        ("What should I do here?", "finance", "capital_hilton"),
        ("Do we just wait for payment?", "finance", "capital_hilton"),
        ("Never mind, just draft what I should ask Glenn.", "finance", "st_annes"),
    ]

    for text, world, thread in prompts:
        result = _route(text, tmp_path / str(abs(hash(text))), world=world, thread=thread)
        display = result["operator_display"]
        step = result["primary_next_step"]
        combined = " ".join(
            [
                str(display.get("next_safe_action") or ""),
                str(step.get("label") or ""),
                str(step.get("human_summary") or ""),
            ]
        ).lower()
        passive = any(phrase in combined for phrase in ("sit tight", "check later", "no action available"))
        assert not passive
        if "wait" in combined:
            assert step["next_step_kind"] in {"draft_only", "schedule_or_monitor", "provide_proof"}


def test_protected_actions_and_raw_authority_remain_denied(tmp_path):
    result = _route(
        "Have we received any emails from Annette?",
        tmp_path,
        authority_granted=True,
    )

    assert result["machine_proof"]["raw_authority_granted_trusted"] is False
    assert _unsafe_true_grants(result) == []

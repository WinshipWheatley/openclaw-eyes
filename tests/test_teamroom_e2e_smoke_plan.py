import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PATH = ROOT / "generated" / "read_models" / "teamroom_e2e_smoke_plan.json"
BRIDGE_PATH = Path("/mnt/e/openclaw/generated/read_models/teamroom_e2e_smoke_plan.json")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _walk_values(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _walk_values(value)


def _assert_no_unsafe_true_grants(payload: dict) -> None:
    unsafe_keys = {
        "email_send_allowed",
        "ledger_posting_allowed",
        "browser_access_allowed",
        "gmail_allowed",
        "coupa_allowed",
        "portal_submit_allowed",
        "worker_spawn_allowed",
        "worker_execution_allowed",
        "business_action_performed",
        "smoke_executed",
        "sent",
        "paid",
    }
    assert not [key for key, value in _walk_values(payload) if key in unsafe_keys and value is True]


def test_teamroom_e2e_smoke_plan_parses_and_is_planning_only():
    plan = _load(LOCAL_PATH)

    assert plan["schema_version"] == "teamroom_e2e_smoke_plan_v0"
    assert plan["status"] == "TEAMROOM_E2E_SMOKE_PLAN_READY"
    assert plan["planning_only"] is True
    assert plan["machine_proof"]["smoke_executed"] is False
    assert plan["machine_proof"]["business_action_performed"] is False
    _assert_no_unsafe_true_grants(plan)


def test_smoke_scenario_contains_required_teamroom_steps():
    plan = _load(LOCAL_PATH)
    step_refs = [step["step_ref"] for step in plan["smoke_scenario"]]

    assert step_refs == [
        "cassandra_st_annes_intake",
        "cassandra_records_work_log_package",
        "operator_confirms_or_marks_test",
        "hermes_recommends_next_rail",
        "chief_stages_worker_package",
        "worker_fixture_result_becomes_review_packet",
        "operator_records_review_decision",
        "homecoming_brief_summarizes_result",
        "guardian_confirms_no_protected_action",
    ]


def test_plan_lists_expected_artifacts_gates_validation_and_cleanup():
    plan = _load(LOCAL_PATH)

    assert plan["expected_request_response_files"]
    assert plan["expected_read_models"]
    assert plan["expected_workroom_posts"]
    assert plan["expected_review_packets"]
    assert {
        "send_email",
        "coupa_submit",
        "ledger_post",
        "workbook_mutation",
        "pdf_export",
        "worker_spawn",
        "git_push",
    }.issubset(set(plan["expected_blocked_gates"]))
    assert plan["validation_commands"]
    assert plan["rollback_cleanup_plan"]
    assert plan["no_business_action_proof"]["business_action_performed"] is False
    _assert_no_unsafe_true_grants(plan)


def test_bridge_equals_local():
    assert _load(LOCAL_PATH) == _load(BRIDGE_PATH)

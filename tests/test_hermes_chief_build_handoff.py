import json

import hermes_chief_build_handoff as handoff
from scripts.export_hermes_chief_build_handoff import main as export_main


FIXED_NOW = "2026-05-28T15:01:54-04:00"


def _build(access_class: str = "WINSHIP_DEVELOPER") -> dict:
    return handoff.build_hermes_chief_build_handoff(generated_at=FIXED_NOW, access_class=access_class)


def test_hermes_produces_chief_handoff_for_urgent_live_arts_mission():
    payload = _build()

    assert payload["read_model_id"] == handoff.READ_MODEL_ID
    assert payload["mission_ref"] == "hermes_mission:live_arts_md_invoice_4pm_cutoff"
    assert payload["urgent_goal"] == "Send the Live Arts MD invoice today before the 4:00 PM cutoff, or manually send it."
    assert payload["access_class"] == "WINSHIP_DEVELOPER"
    assert payload["current_mode"]["urgency"] == "URGENT_DEADLINE"
    assert payload["button_label"] == "Ask Chief to build the critical path"
    assert payload["button_enabled"] is True


def test_chief_tasks_are_right_sized_and_receipt_test_oriented():
    tasks = _build()["recommended_chief_tasks"]

    assert len(tasks) >= 5
    for task in tasks:
        assert task["task_ref"].startswith("chief_task:")
        assert task["exact_files_to_inspect"]
        assert task["allowed_changes"]
        assert task["forbidden_changes"]
        assert task["expected_output"]
        assert task["validation_required"]
        assert task["done_definition"]
        assert task["resolved_model_class_alias"] == "STRONG_STRUCTURED_ROLE_REASONER"
        assert task["model_policy_ref"] == "generated/read_models/model_router_policy.json"


def test_handoff_distinguishes_pc_tasks_from_mac_tasks():
    payload = _build()
    pc_refs = {task["task_ref"] for task in payload["recommended_pc_tasks"]}
    mac_refs = {task["task_ref"] for task in payload["recommended_mac_tasks"]}

    assert "chief_task:clara_send_ready_draft" in pc_refs
    assert "chief_task:live_arts_invoice_candidate_selection" in pc_refs
    assert "chief_task:live_arts_invoice_candidate_selection" in mac_refs
    assert "chief_task:manual_artifact_attach_link" in mac_refs
    assert payload["next_prompt_for_mac_codex"]
    assert payload["next_prompt_for_pc_codex"]


def test_handoff_includes_manual_fallback_plan_before_cutoff():
    plan = _build()["manual_fallback_plan"]

    assert plan["fallback_required_by"] == "2026-05-28T15:45:00-04:00"
    assert "Winship manually sends" in plan["operator_action"]
    assert "manual send receipt" in plan["proof_to_capture"]
    assert "payment watch" in plan["after_manual_send"]


def test_customer_mode_hides_developer_tasks():
    payload = _build(access_class="CUSTOMER_OPERATOR")

    assert payload["access_class"] == "CUSTOMER_OPERATOR"
    assert payload["button_enabled"] is False
    assert payload["button_label"] is None
    assert payload["button_hidden_request_payload"] is None
    assert payload["recommended_chief_tasks"] == ()
    assert payload["customer_mode_projection"]["developer_tasks_visible"] is False
    assert "developer" not in payload["customer_mode_projection"]["operator_copy"].lower()


def test_winship_developer_mode_exposes_chief_prompts():
    payload = _build()

    assert payload["next_prompt_for_chief"]
    assert "shortest Live Arts MD critical path" in payload["next_prompt_for_chief"]
    assert "Do not execute business actions" in payload["next_prompt_for_pc_codex"]
    assert "Do not send email" in payload["next_prompt_for_mac_codex"]
    assert payload["machine_proof"]["developer_mode_only"] is True


def test_button_payload_is_developer_only_and_no_production_action():
    payload = _build()
    button = payload["button_hidden_request_payload"]

    assert button["request_type"] == "CHIEF_BUILD_HANDOFF_REQUEST"
    assert button["access_class"] == "WINSHIP_DEVELOPER"
    assert button["mission_ref"] == payload["mission_ref"]
    assert button["handoff_ref"] == payload["handoff_ref"]
    assert button["no_production_action"] is True
    assert button["no_external_action"] is True
    assert button["no_business_state_mutation"] is True
    assert button["email_send_allowed"] is False
    assert button["workbook_cell_read_allowed"] is False


def test_handoff_does_not_enable_send_coupa_email_ledger_or_workbook_read_authority():
    payload = _build()

    assert payload["machine_proof"]["read_model_only"] is True
    assert payload["machine_proof"]["no_production_authority"] is True
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert all(value is False for value in payload["authority_boundary"].values())


def test_orchestrator_summary_is_concise_and_usable():
    summary = _build()["orchestrator_summary"]

    assert "Live Arts MD" in summary
    assert "not send-ready" in summary
    assert "candidate selection" in summary
    assert "manual-send proof capture" in summary
    assert len(summary) < 500


def test_parallel_and_serial_tasks_are_classified():
    payload = _build()

    assert "chief_task:manual_artifact_attach_link" in payload["serial_tasks"]
    assert "chief_task:clara_send_ready_draft" in payload["serial_tasks"]
    assert "chief_task:recipient_confirmation" in payload["parallelizable_tasks"]
    assert payload["collision_risks"]


def test_export_writes_parseable_read_model_and_bridge(tmp_path):
    export_root = tmp_path / "read_models"
    bridge_root = tmp_path / "bridge"

    assert export_main(
        [
            "--export-root",
            export_root.as_posix(),
            "--bridge-export-root",
            bridge_root.as_posix(),
            "--generated-at",
            FIXED_NOW,
        ]
    ) == 0
    source = export_root / handoff.JSON_EXPORT_NAME
    operator = export_root / handoff.OPERATOR_EXPORT_NAME
    bridge = bridge_root / handoff.JSON_EXPORT_NAME

    assert source.is_file()
    assert operator.is_file()
    assert bridge.is_file()
    assert json.loads(source.read_text(encoding="utf-8"))["read_model_id"] == handoff.READ_MODEL_ID
    assert source.read_bytes() == bridge.read_bytes()

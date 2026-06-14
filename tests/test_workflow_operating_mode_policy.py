import json

import workflow_operating_mode_policy as policy
from scripts.export_workflow_operating_mode_policy import main as export_main


FIXED_NOW = "2026-05-28T12:00:00+00:00"


def _build() -> dict:
    return policy.build_workflow_operating_mode_policy(generated_at=FIXED_NOW)


def test_policy_is_read_model_only_and_authority_false():
    payload = _build()

    assert payload["schema_version"] == policy.SCHEMA_VERSION
    assert payload["read_model_id"] == policy.READ_MODEL_ID
    assert payload["contract_status"] == policy.CONTRACT_STATUS
    assert payload["machine_proof"]["read_model_only"] is True
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert all(value is False for value in payload["authority_boundary"].values())


def test_telegram_live_arts_runtime_response_includes_facts_not_just_app_handoff():
    example = _build()["example_classifications"]["telegram_live_arts_send_invoice"]

    assert example["access_class"] == "WINSHIP_OPERATOR"
    assert example["mode"] == "OPERATOR_RUNTIME"
    assert example["channel"] == "TELEGRAM"
    assert example["should_handoff_to_app"] is False
    assert "Invoice: 2026-1001" in example["operator_copy"]
    assert "Amount: $900" in example["operator_copy"]
    assert "Dane pending confirmation" in example["operator_copy"]
    assert "Open Mission Control" not in example["operator_copy"]


def test_telegram_app_handoff_only_when_specific_limitation_present():
    normal = policy.classify_operating_context(
        operator_intent="Send the Live Arts invoice",
        access_class="WINSHIP_OPERATOR",
        channel="TELEGRAM",
        client_ref="live_arts_md",
        workflow_ref="live_arts_md_invoice_workflow",
    )
    preview = policy.classify_operating_context(
        operator_intent="Open artifact preview for the Live Arts invoice",
        access_class="WINSHIP_OPERATOR",
        channel="TELEGRAM",
        client_ref="live_arts_md",
        workflow_ref="live_arts_md_invoice_workflow",
    )

    assert normal["should_handoff_to_app"] is False
    assert normal["app_handoff_reason"] is None
    assert preview["should_handoff_to_app"] is True
    assert preview["app_handoff_reason"] == "high_fidelity_artifact_review_required"


def test_untested_telegram_features_are_marked_untested_not_impossible():
    telegram = _build()["channel_capability_policy"]["TELEGRAM"]

    assert "telegram_artifact_preview" in telegram["untested_capabilities"]
    assert "telegram_guardian_approval" in telegram["untested_capabilities"]
    assert "Telegram artifact review is not proven yet" in _build()["example_classifications"][
        "telegram_live_arts_send_invoice"
    ]["operator_copy"]


def test_mission_control_app_supports_rich_artifact_review():
    app = _build()["channel_capability_policy"]["APP"]

    assert app["supports_file_preview"] is True
    assert app["supports_pdf_preview"] is True
    assert app["supports_local_file_picker"] is True
    assert app["supports_artifact_open_or_reveal"] is True
    assert app["supports_guardian_approval"] is True


def test_file_picker_requires_app_unless_telegram_upload_rail_exists():
    telegram = _build()["channel_capability_policy"]["TELEGRAM"]

    assert telegram["supports_local_file_picker"] is False
    assert "local_file_picker_required" in telegram["handoff_required_when"]
    assert "telegram_file_upload" in telegram["untested_capabilities"]


def test_approval_through_telegram_blocked_until_proven():
    telegram = _build()["channel_capability_policy"]["TELEGRAM"]
    result = policy.classify_operating_context(
        operator_intent="Approve and send the Live Arts invoice",
        access_class="WINSHIP_OPERATOR",
        channel="TELEGRAM",
        client_ref="live_arts_md",
        workflow_ref="live_arts_md_invoice_workflow",
    )

    assert telegram["supports_guardian_approval"] is False
    assert "guardian_approval_from_telegram_until_proven" in telegram["blocked_actions"]
    assert result["should_handoff_to_app"] is True
    assert result["app_handoff_reason"] == "guardian_approval_requires_rich_proof"


def test_runtime_mode_does_not_ask_setup_questions_unless_required():
    result = policy.classify_operating_context(
        operator_intent="Send the Live Arts invoice",
        access_class="WINSHIP_OPERATOR",
        channel="APP",
        client_ref="live_arts_md",
        workflow_ref="live_arts_md_invoice_workflow",
    )

    assert result["mode"] == "OPERATOR_RUNTIME"
    assert result["should_surface_dev_task"] is False
    assert "build task" not in result["operator_copy"].lower()
    assert result["safe_next_step"] == "Choose or confirm the invoice candidate, then link the invoice artifact and confirm recipients."


def test_workflow_setup_can_produce_right_sized_build_tasks_for_winship_developer():
    result = policy.classify_operating_context(
        operator_intent="Help me build the Live Arts invoice workflow",
        access_class="WINSHIP_DEVELOPER",
        channel="CLI",
        client_ref="live_arts_md",
        workflow_ref="live_arts_md_invoice_workflow",
        missing_capabilities=("manual artifact link rail",),
    )

    assert result["mode"] == "CAPABILITY_GAP"
    assert result["should_surface_dev_task"] is True
    assert result["workflow_response_mode"] == "DEV_MODE_REQUIRED"
    assert "Produce a bounded developer task" in result["safe_next_step"]


def test_customer_operator_never_receives_developer_build_prompts():
    result = policy.classify_operating_context(
        operator_intent="Help me build the Live Arts invoice workflow",
        access_class="CUSTOMER_OPERATOR",
        channel="APP",
        client_ref="live_arts_md",
        workflow_ref="live_arts_md_invoice_workflow",
        module_ref="simple_invoice_module",
        missing_capabilities=("module setup",),
    )

    assert result["access_class"] == "CUSTOMER_OPERATOR"
    assert result["mode"] == "CAPABILITY_GAP"
    assert result["should_surface_dev_task"] is False
    assert result["workflow_response_mode"] == "BLOCKED"
    assert "developer" not in result["operator_copy"].lower()
    assert "Codex" not in result["operator_copy"]


def test_capability_gap_copy_differs_for_developer_and_customer():
    dev = _build()["example_classifications"]["winship_build_live_arts"]
    customer = _build()["example_classifications"]["customer_runtime_module"]

    assert dev["should_surface_dev_task"] is True
    assert "bounded developer task" in dev["safe_next_step"]
    assert customer["should_surface_dev_task"] is False
    assert customer["operator_copy"] == "This module needs setup before that feature can run. No action was taken."


def test_operator_correction_supersedes_local_assumption_safely():
    result = _build()["example_classifications"]["wrong_workbook"]

    assert result["mode"] == "OPERATOR_CORRECTION"
    assert result["should_request_operator_input"] is True
    assert "choose or confirm the correct source workbook" in result["safe_next_step"]
    assert "will not delete files" in result["operator_copy"]
    assert result["authority_boundary"]["file_delete_allowed"] is False


def test_right_sized_package_plan_is_bounded_and_receipt_oriented():
    result = _build()["example_classifications"]["telegram_live_arts_send_invoice"]
    plan = result["right_sized_package_plan"]

    assert plan["bounded"] is True
    assert plan["receipt_oriented"] is True
    assert plan["giant_vague_model_call_allowed"] is False
    assert len(plan["package_steps"]) >= 3
    for step in plan["package_steps"]:
        assert step["task"]
        assert step["expected_receipt"]
        assert step["stop_condition"]
        assert "email/Gmail" in step["forbidden_context"] or "Gmail send" in step["forbidden_context"] or "email send" in step["forbidden_context"]


def test_generate_pdf_without_authority_is_capability_gap_not_fake_artifact():
    result = _build()["example_classifications"]["generate_invoice_pdf"]

    assert result["mode"] == "CAPABILITY_GAP"
    assert "selected-sheet export rail authorization" in result["missing_capabilities"]
    assert "No action was taken" not in result["operator_copy"]
    assert result["authority_boundary"]["invoice_generation_allowed"] is False


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
    source = export_root / policy.JSON_EXPORT_NAME
    operator = export_root / policy.OPERATOR_EXPORT_NAME
    bridge = bridge_root / policy.JSON_EXPORT_NAME

    assert source.is_file()
    assert operator.is_file()
    assert bridge.is_file()
    payload = json.loads(source.read_text(encoding="utf-8"))
    assert payload["read_model_id"] == policy.READ_MODEL_ID
    assert source.read_bytes() == bridge.read_bytes()

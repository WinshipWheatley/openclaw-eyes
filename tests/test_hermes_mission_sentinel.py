import json

import hermes_mission_sentinel as sentinel
from scripts.export_hermes_mission_sentinel import main as export_main


FIXED_NOW = "2026-05-28T15:01:54-04:00"


def _build() -> dict:
    return sentinel.build_hermes_mission_sentinel(generated_at=FIXED_NOW)


def test_hermes_identifies_live_arts_4pm_deadline():
    payload = _build()

    assert payload["mission_ref"] == "hermes_mission:live_arts_md_invoice_4pm_cutoff"
    assert payload["client_ref"] == "live_arts_md"
    assert payload["workflow_ref"] == "live_arts_md_invoice_workflow"
    assert payload["deadline_local"] == "2026-05-28T16:00:00-04:00"
    assert payload["time_remaining"]["bucket"] == "UNDER_75_MINUTES"
    assert payload["urgent_goal"] == "Send the Live Arts MD invoice today before the 4:00 PM cutoff, or manually send it."


def test_hermes_classifies_mode_as_urgent_runtime_with_developer_context():
    mode = _build()["current_mode"]

    assert mode["primary"] == "OPERATOR_RUNTIME"
    assert mode["urgency"] == "URGENT_DEADLINE"
    assert mode["developer_context_available"] is True
    assert mode["human_trial_if_testing_in_app"] is True


def test_hermes_recommends_manual_fallback_near_cutoff():
    payload = sentinel.build_hermes_mission_sentinel(generated_at="2026-05-28T15:46:00-04:00")

    assert payload["time_remaining"]["bucket"] == "FINAL_15_MINUTES"
    assert payload["manual_fallback_required_by"] == "2026-05-28T15:45:00-04:00"
    assert "Manually send the invoice" in payload["recommended_human_action"]


def test_hermes_lists_critical_blockers_without_fake_completion():
    payload = _build()

    assert payload["automation_ready_status"] == "NOT_SEND_READY"
    assert "invoice artifact/attachment not ready" in payload["current_blockers"]
    assert "recipient details unconfirmed" in payload["current_blockers"]
    assert "approval/send readiness disabled" in payload["current_blockers"]
    assert payload["live_arts_md_state"]["source_workbook_confirmed"] is True
    assert payload["live_arts_md_state"]["attachment_ready"] is False
    assert payload["live_arts_md_state"]["approval_ready"] is False
    assert payload["live_arts_md_state"]["send_ready"] is False


def test_hermes_produces_next_right_sized_package_recommendations():
    packages = _build()["next_right_sized_packages"]

    assert {item["package_ref"] for item in packages} == {
        "live_arts_md_select_invoice_candidate",
        "live_arts_md_link_invoice_artifact",
        "live_arts_md_confirm_recipients",
        "live_arts_md_manual_send_receipt_after_fallback",
    }
    for item in packages:
        assert item["prompt"]
        assert item["expected_receipt"]
        assert item["stop_condition"]


def test_hermes_manual_send_checklist_contains_required_proof():
    checklist = _build()["proof_to_capture_after_manual_send"]

    assert "recipient list" in checklist
    assert "subject" in checklist
    assert "attachment/file name" in checklist
    assert "send timestamp" in checklist
    assert "invoice id" in checklist
    assert "amount" in checklist
    assert "payment watch target" in checklist
    assert "manual send receipt" in checklist


def test_hermes_does_not_enable_action_authority():
    payload = _build()

    assert payload["machine_proof"]["read_model_only"] is True
    assert payload["machine_proof"]["hermes_executes"] is False
    assert payload["machine_proof"]["hermes_approves"] is False
    assert payload["machine_proof"]["hermes_sends"] is False
    assert payload["machine_proof"]["all_authority_flags_false"] is True
    assert all(value is False for value in payload["authority_boundary"].values())


def test_operator_summary_contains_no_backend_sludge():
    summary = sentinel.render_operator_summary(_build()).lower()

    forbidden = ("sqlite", "source_request_id", "gate 2", "gate 3", "request-response", "backend execution")
    for term in forbidden:
        assert term not in summary
    assert "manual send proof to capture" in summary
    assert "hermes observes only" in summary


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
    source = export_root / sentinel.JSON_EXPORT_NAME
    operator = export_root / sentinel.OPERATOR_EXPORT_NAME
    bridge = bridge_root / sentinel.JSON_EXPORT_NAME

    assert source.is_file()
    assert operator.is_file()
    assert bridge.is_file()
    assert json.loads(source.read_text(encoding="utf-8"))["read_model_id"] == sentinel.READ_MODEL_ID
    assert source.read_bytes() == bridge.read_bytes()

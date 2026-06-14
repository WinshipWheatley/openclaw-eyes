import json
import re
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import hermes_gravity_controller as gravity

FIXED_NOW = "2026-05-28T10:00:00+00:00"
FUTURE_DEADLINE = "2026-05-28T16:00:00-04:00"


def _evaluate(payload: dict, *, access_class: str = "WINSHIP_DEVELOPER") -> dict:
    payload.setdefault("module_enabled", payload.get("module_enabled", True))
    return gravity.evaluate_purpose_bound_capability(
        payload,
        access_class=access_class,
        generated_at=FIXED_NOW,
        deadline_local=FUTURE_DEADLINE,
    )


def test_gig_location_check_is_ok_only_in_event_window():
    inside = _evaluate(
        {
            "module_ref": "gig_manager",
            "workflow_ref": "gig_manager_workflow",
            "action": "capture_checkin_checkout_proof",
            "purpose": "gig_arrival",
            "observation_window": "event_window",
        }
    )
    outside = _evaluate(
        {
            "module_ref": "gig_manager",
            "workflow_ref": "gig_manager_workflow",
            "action": "capture_checkin_checkout_proof",
            "purpose": "gig_arrival",
            "observation_window": "all_day",
        }
    )

    assert inside["gravity_status"] == "PURPOSE_BOUND_OK"
    assert outside["gravity_status"] in {"NEEDS_NARROWING", "SURVEILLANCE_RISK"}
    assert "LOCATION_WINDOW_MUST_BE_DECLARED" in outside["reason_codes"]


def test_general_continuous_location_tracking_defaults_to_surveillance_risk():
    decision = _evaluate(
        {
            "module_ref": "phone_location_proof",
            "workflow_ref": "phone_location_proof_workflow",
            "action": "continuous_location_tracking",
            "purpose": "track_for_proof",
            "observation_window": "event_window",
            "raw_data_retention": "none",
        }
    )

    assert decision["gravity_status"] == "SURVEILLANCE_RISK"
    assert "CONTINUOUS_LOCATION_TRACKING" in decision["reason_codes"]


def test_gig_outfit_laundry_allowed_when_tied_to_gig_module():
    decision = _evaluate(
        {
            "module_ref": "gig_outfit",
            "workflow_ref": "gig_outfit_workflow",
            "action": "send_outfit_reminder",
        }
    )

    assert decision["gravity_status"] == "PURPOSE_BOUND_OK"
    assert "GIG_OUTFIT_SURVEILLANCE" not in decision["reason_codes"]


def test_general_laundry_surveillance_is_narrowed():
    decision = _evaluate(
        {
            "module_ref": "gig_outfit",
            "workflow_ref": "gig_outfit_workflow",
            "action": "monitor_clothing_habit_patterns",
        }
    )

    assert decision["gravity_status"] in {"NEEDS_NARROWING", "SURVEILLANCE_RISK"}
    assert "GIG_OUTFIT_SURVEILLANCE" in decision["reason_codes"]


def test_client_comms_thread_watch_allowed_for_clara_owned_threads():
    decision = _evaluate(
        {
            "module_ref": "client_comms",
            "workflow_ref": "client_comms_workflow",
            "action": "watch_clara_owned_threads",
            "thread_scope": "clara_owned",
            "thread_owner": "Clara",
            "module_enabled": True,
        },
        access_class="CUSTOMER_OPERATOR",
    )

    assert decision["gravity_status"] == "CUSTOMER_SAFE"
    assert "UNOWNED_EMAIL_SURVEILLANCE" not in decision["reason_codes"]


def test_read_all_email_is_blocked_or_narrowed_without_owned_scope():
    decision = _evaluate(
        {
            "module_ref": "client_comms",
            "workflow_ref": "client_comms_workflow",
            "action": "read_all_client_email",
            "thread_scope": "all_client_email",
        }
    )

    assert decision["gravity_status"] == "NEEDS_NARROWING"
    assert "UNOWNED_EMAIL_SURVEILLANCE" in decision["reason_codes"]
    assert "General inbox watching is blocked." in decision["not_allowed_reasons"]


def test_phone_location_proof_requires_purpose_window_and_retention_controls():
    decision = _evaluate(
        {
            "module_ref": "phone_location_proof",
            "workflow_ref": "phone_location_proof_workflow",
            "action": "capture_arrival_point",
        }
    )

    assert decision["gravity_status"] == "NEEDS_OPERATOR_OPT_IN"
    assert "MISSING_LOCATION_PURPOSE" in decision["reason_codes"]
    assert "MISSING_LOCATION_WINDOW" in decision["reason_codes"]
    assert "MISSING_RAW_RETENTION_CONTROL" in decision["reason_codes"]


def test_customer_mode_hides_developer_task_language():
    decision = _evaluate(
        {
            "module_ref": "gig_manager",
            "workflow_ref": "gig_manager_workflow",
            "action": "capture_checkin_checkout_proof",
            "purpose": "arrival proof",
            "observation_window": "event_window",
        },
        access_class="CUSTOMER_OPERATOR",
    )

    assert decision["gravity_status"] == "CUSTOMER_SAFE"
    assert "Pause" in decision["operator_summary"]
    assert "Inspect" in decision["operator_summary"]
    assert "Turn off" in decision["operator_summary"]
    assert "Decision rationale" not in decision["operator_summary"]
    assert "charter_gig_manager_v0" not in decision["operator_summary"]


def test_winship_developer_mode_sees_gravity_details():
    decision = _evaluate(
        {
            "module_ref": "client_comms",
            "workflow_ref": "client_comms_workflow",
            "action": "read_all_client_email",
            "thread_scope": "all_client_email",
        },
        access_class="WINSHIP_DEVELOPER",
    )

    assert "charter_client_comms_clara_v0" in decision["operator_summary"]
    assert decision["reason_codes"]
    assert "UNOWNED_EMAIL_SURVEILLANCE" in decision["reason_codes"]


def test_default_on_allowed_only_when_module_enabled():
    disabled = _evaluate(
        {
            "module_ref": "gig_manager",
            "workflow_ref": "gig_manager_workflow",
            "action": "capture_checkin_checkout_proof",
            "purpose": "arrival proof",
            "observation_window": "event_window",
            "module_enabled": False,
        }
    )
    enabled = _evaluate(
        {
            "module_ref": "gig_manager",
            "workflow_ref": "gig_manager_workflow",
            "action": "capture_checkin_checkout_proof",
            "purpose": "arrival proof",
            "observation_window": "event_window",
            "module_enabled": True,
        }
    )

    assert disabled["gravity_status"] == "NEEDS_OPERATOR_OPT_IN"
    assert disabled["allowed_default_on"] is False
    assert enabled["gravity_status"] == "PURPOSE_BOUND_OK"
    assert enabled["allowed_default_on"] is True


def test_device_integration_requires_approved_path():
    rejected = _evaluate(
        {
            "module_ref": "washer_dryer_integration",
            "workflow_ref": "washer_dryer_workflow",
            "action": "read_device_state",
            "integration_source": "scraper",
            "module_enabled": True,
        }
    )
    approved = _evaluate(
        {
            "module_ref": "washer_dryer_integration",
            "workflow_ref": "washer_dryer_workflow",
            "action": "read_device_state",
            "integration_source": "homekit",
            "module_enabled": True,
        }
    )

    assert rejected["gravity_status"] == "NEEDS_OPERATOR_OPT_IN"
    assert "UNAPPROVED_INTEGRATION_PATH" in rejected["reason_codes"]
    assert approved["gravity_status"] == "PURPOSE_BOUND_OK"


def test_hermes_provides_safer_alternative_for_broad_request():
    decision = _evaluate(
        {
            "module_ref": "phone_location_proof",
            "workflow_ref": "phone_location_proof_workflow",
            "action": "continuous_location_tracking",
            "purpose": "all_day_tracking",
            "observation_window": "all_day",
            "module_enabled": True,
        }
    )

    assert decision["gravity_status"] == "SURVEILLANCE_RISK"
    assert "event-window" in decision["safer_alternative"]
    assert "declared" in decision["safer_alternative"]


def test_gravity_decision_shape_matches_contract_fields():
    decision = _evaluate(
        {
            "module_ref": "gig_manager",
            "workflow_ref": "gig_manager_workflow",
            "action": "start_prep_reminders",
            "purpose": "prep",
            "observation_window": "event_window",
        }
    )

    for field in gravity.GRAVITY_DECISION_REQUIRED_FIELDS:
        assert field in decision


def test_time_constraint_status_is_embedded_in_decision():
    decision = _evaluate(
        {
            "module_ref": "gig_outfit",
            "workflow_ref": "gig_outfit_workflow",
            "action": "send_outfit_reminder",
        },
        access_class="WINSHIP_OPERATOR",
    )

    assert decision["time_constraint_status"] in gravity.TIME_CONSTRAINT_STATUSES
    assert decision["do_not_spend_time_on"]
    assert decision["manual_fallback_required_by"] is None


def test_build_and_export_artifacts_parse(tmp_path):
    payload = gravity.build_hermes_gravity_controller(generated_at=FIXED_NOW, deadline_local=FUTURE_DEADLINE)
    required = set(gravity.GRAVITY_DECISION_REQUIRED_FIELDS)
    for field in required:
        assert field in payload["required_decision_fields"]

    json_payload = json.dumps(payload)
    assert "SURVEILLANCE" in json_payload
    assert isinstance(payload["example_decisions"], tuple)
    assert len(payload["example_decisions"]) == 7
    for example in payload["example_decisions"]:
        assert "gravity_status" in example


def test_source_does_not_import_runtime_authority_or_network_modules():
    source = Path("hermes_gravity_controller.py").read_text(encoding="utf-8").lower()
    forbidden = (
        r"^\s*import\s+requests\b",
        r"^\s*import\s+httpx\b",
        r"^\s*import\s+socket\b",
        r"^\s*from\s+requests\s+import\b",
        r"^\s*from\s+httpx\s+import\b",
        r"^\s*from\s+socket\s+import\b",
        r"^\s*import\s+subprocess\b",
        r"^\s*from\s+subprocess\s+import\b",
        r"os\.system",
        r"playwright",
        r"selenium",
        r"\bcoupa\b",
        r"\bgmail\b",
    )
    for token in forbidden:
        assert re.search(token, source, re.MULTILINE) is None

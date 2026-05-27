import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import operator_readiness_surface as surface


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def _payload() -> dict:
    return surface.build_payload(generated_at=FIXED_NOW)


def test_surface_aggregates_lm_readiness_dashboard_v2():
    payload = _payload()
    surface_payload = payload["surface_payload"]

    assert payload["machine_proof"]["aggregates_lm_readiness_dashboard"] is True
    assert surface_payload["proof_shelf"]["lm1_shadow_status"] == "READY"
    assert surface_payload["proof_shelf"]["lm2_shadow_status"] == "READY"
    assert surface_payload["proof_shelf"]["provider_policy_status"] == "SEEDED"


def test_surface_exposes_private_mode_choices_without_enabling_them():
    payload = _payload()
    card = payload["surface_payload"]["private_mode_card"]
    labels = [button["label"] for button in payload["surface_payload"]["suggested_buttons"]]

    assert card["available"] is True
    assert card["active"] is False
    assert card["strict_available"] is True
    assert card["strict_active"] is False
    assert "Enable Private Mode" in labels
    assert "Enable Strict Private Mode" in labels
    assert payload["machine_proof"]["private_mode_active"] is False


def test_surface_says_live_lm_is_not_active():
    payload = _payload()

    assert payload["machine_proof"]["live_lm_status"] == "NOT_ACTIVE"
    assert "Live models are not active." in payload["surface_payload"]["operator_summary"]


def test_operator_summary_hides_backend_jargon():
    payload = _payload()
    summary = " ".join(payload["surface_payload"]["operator_summary"]).lower()

    for term in surface.BACKEND_JARGON_TERMS:
        assert term not in summary
    assert payload["machine_proof"]["operator_summary_backend_jargon_free"] is True


def test_proof_shelf_keeps_machine_fields_available():
    payload = _payload()
    proof = payload["surface_payload"]["proof_shelf"]

    for key in (
        "gate_chain_status",
        "gate1_privacy_status",
        "lm1_shadow_status",
        "lm2_shadow_status",
        "tokenization_status",
        "request_response_bridge_status",
        "production_live_blocker_status",
        "provider_activation_receipt_status",
        "private_mode_policy_status",
        "read_model_visibility_status",
        "provider_policy_status",
        "guardian_gate_status",
        "trust_ramp_candidate_level",
        "active_trust_level",
        "live_lm_blockers",
    ):
        assert key in proof
    assert "generated/read_models/lm_readiness_dashboard.json" in proof["read_model_refs"]
    assert "generated/read_models/gate1_privacy_request_readiness.json" in proof["read_model_refs"]
    assert "generated/read_models/request_response_bridge_readiness.json" in proof["read_model_refs"]
    assert "generated/read_models/live_lm_activation_requirements.json" in proof["read_model_refs"]
    assert "generated/read_models/private_mode_policy_readiness.json" in proof["read_model_refs"]
    assert "generated/read_models/read_model_mirror_visibility.json" in proof["read_model_refs"]


def test_suggested_buttons_only_represent_human_decisions():
    payload = _payload()
    buttons = payload["surface_payload"]["suggested_buttons"]
    labels = {button["label"] for button in buttons}

    assert labels == set(surface.BUTTON_LABELS)
    assert all(button["safe_to_show_now"] is True for button in buttons)
    assert all(button["enables_live_lm"] is False for button in buttons)
    assert all(button["enables_tool_action"] is False for button in buttons)
    assert not any("run" in button["label"].lower() and "processor" in button["label"].lower() for button in buttons)


def test_surface_does_not_enable_action_tool_or_model_authority():
    payload = _payload()

    assert payload["machine_proof"]["live_model_call_performed"] is False
    assert payload["machine_proof"]["model_api_call_performed"] is False
    assert payload["machine_proof"]["tool_execution_performed"] is False
    assert payload["machine_proof"]["external_action_performed"] is False
    assert payload["machine_proof"]["all_live_authority_false"] is True


def test_exported_readmodel_parses(tmp_path):
    payload = _payload()
    json_path, operator_path = surface.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == surface.READ_MODEL_ID
    assert parsed["surface_payload"]["private_mode_card"]["plain_language_description"].startswith("Private Mode")
    operator_text = operator_path.read_text(encoding="utf-8")
    assert "Suggested buttons:" in operator_text
    assert "Enable Private Mode" in operator_text

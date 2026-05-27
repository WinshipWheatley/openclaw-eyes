import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import guardian_output_gate
import intent_ingest_gate
import lm_readiness_dashboard as dashboard
import model_router_policy
import role_package_gate
import universal_intake_contract


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def _payload() -> dict:
    return dashboard.build_payload(generated_at=FIXED_NOW)


def test_readiness_dashboard_aggregates_all_seeded_lanes():
    payload = _payload()
    lanes = payload["aggregated_lanes"]

    for lane in (
        "gate_chain_harness",
        "guardian_trust_ramp_simulator",
        "model_router_policy",
        "live_lm_readiness_gate",
        "shadow_lm_mode",
        "token_vault_status",
        "universal_intake_contract",
    ):
        assert lane in lanes
    assert payload["machine_proof"]["dashboard_aggregates_seeded_lanes"] is True
    assert payload["dashboard_summary"]["lm1_shadow"] == "READY"
    assert payload["dashboard_summary"]["lm2_package_shadow"] == "READY"


def test_lm1_thread_context_package_includes_universal_intake_and_token_declarations():
    package = dashboard.build_lm1_thread_context_package(source_request_id="test_lm1_context")

    assert package["source_request_id"] == "test_lm1_context"
    assert package["universal_intake_inference"]["client_ref"] == "capital_hilton"
    assert package["privacy"]["tokenization_applied"] is True
    assert package["privacy"]["raw_values_included"] is False
    assert package["raw_values_included"] is False
    assert "MachineIntentCandidate" not in package["output_schema"]
    assert "source_request_id" in package["output_schema"]
    assert package["tools_allowed"] == ()


def test_gate3_role_package_includes_tokenization_fields():
    payload = _payload()
    package = payload["representative_flow"]["gate3_package_summary"]

    assert package["package_status"] == role_package_gate.PACKAGE_COMPILED
    assert package["tokenization_applied"] is True
    assert package["raw_values_included"] is False
    assert package["token_vault_ref"] == "generated/read_models/token_vault_status.json"
    assert package["detokenization_policy_ref"] == "detokenization_denied_without_explicit_policy_receipt"
    assert package["privacy_level"] == "metadata_only_tokenized_refs"
    assert package["model_may_see_raw_values"] is False


def test_model_router_integration_selects_lm1_and_lm2_model_classes():
    payload = _payload()

    assert payload["representative_flow"]["lm1_model_decision"]["selected_model_class"] == model_router_policy.FAST_STRUCTURED_INTENT_SMALL
    assert payload["representative_flow"]["lm2_model_decision"]["selected_model_class"] in {
        model_router_policy.STRONG_STRUCTURED_ROLE_REASONER,
        model_router_policy.CONSERVATIVE_SENSITIVE_STRUCTURED,
    }


def test_model_router_returns_no_safe_model_when_privacy_is_insufficient():
    decision = model_router_policy.select_for_lm2_role_package(
        {
            "package_id": "unsafe_raw_package",
            "role_identity": "CASSANDRA",
            "task": "Prepare response.",
            "tokenization_applied": False,
            "raw_values_included": True,
            "privacy_level": "protected",
        }
    )

    assert decision["selected_model_class"] == model_router_policy.NO_SAFE_MODEL
    assert "RAW_SENSITIVE_VALUES_REQUIRE_TOKENIZATION" in decision["blocked_reasons"]


def test_universal_intake_fixture_stays_draft_source_only():
    inference = universal_intake_contract.infer_universal_intake(
        {
            "source_request_id": "test_universal",
            "file_display_name": "Invoice Capitol Hilton Running.xlsx",
            "file_extension": ".xlsx",
            "file_type": "spreadsheet",
            "user_note": "these are invoice workbooks for the clients named in the files",
            "current_world_ref": "finance",
        }
    )

    assert inference["artifact_kind"] == "running_draft_invoice_workbook"
    assert inference["submitted"] is False
    assert inference["paid"] is False
    assert inference["ledger_posted"] is False
    assert inference["final"] is False
    assert inference["proposed_facts_only"] is True


def test_representative_flow_reaches_gate2_gate3_gate4_without_live_status():
    payload = _payload()
    flow = payload["representative_flow"]

    assert flow["gate2_result_summary"]["outcome"] == intent_ingest_gate.ACCEPTED_INTENT
    assert flow["gate3_package_summary"]["package_status"] == role_package_gate.PACKAGE_COMPILED
    assert flow["gate4_result_summary"]["verdict"] == guardian_output_gate.VALIDATED
    assert payload["dashboard_summary"]["lm1_live"] == "NOT_ACTIVE"
    assert payload["dashboard_summary"]["lm2_live"] == "NOT_ACTIVE"


def test_exported_readmodel_parses(tmp_path):
    payload = _payload()
    json_path, operator_path = dashboard.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == dashboard.READ_MODEL_ID
    assert parsed["machine_proof"]["model_call_performed"] is False
    assert parsed["machine_proof"]["workbook_body_read_performed"] is False
    assert "Live LM calls remain off" in operator_path.read_text(encoding="utf-8")

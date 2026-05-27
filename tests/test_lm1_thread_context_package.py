import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lm1_thread_context_package as lm1_package
import model_router_policy


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def test_lm1_package_is_standalone_and_chain_compatible():
    payload = lm1_package.build_payload(generated_at=FIXED_NOW, source_request_id="test_lm1_standalone")
    package = payload["lm1_thread_context_package"]

    assert package["source_request_id"] == "test_lm1_standalone"
    assert package["gate1_operational_snapshot_ref"].startswith("gate1_operational_snapshot:")
    assert package["gate1_safe_to_package_for_lm1"] is True
    assert package["gate1_privacy_flags"]["privacy_class"] == "CLIENT_FINANCE_FILE_METADATA"
    assert package["universal_intake_inference"]["client_ref"] == "capital_hilton"
    assert package["universal_intake_chain_contract"]["candidate_may_enter_gate_2_after_lm1_proposal"] is True
    assert package["privacy_classification"] == "CLIENT_FINANCE_FILE_METADATA"
    assert package["tokenization_required"] is True
    assert package["raw_values_included"] is False
    assert package["tools_allowed"] == ()
    assert payload["chain_contract"]["output_to"] == "Gate 2 intent ingest"


def test_lm1_package_model_router_and_authority_are_bounded():
    payload = lm1_package.build_payload(generated_at=FIXED_NOW)
    summary = payload["package_summary"]
    proof = payload["machine_proof"]

    assert summary["selected_model_class"] == model_router_policy.FAST_STRUCTURED_INTENT_SMALL
    assert summary["ready_for_shadow"] is True
    assert proof["package_has_model_router_result"] is True
    assert proof["package_consumes_gate1_snapshot"] is True
    assert proof["gate1_snapshot_safe_to_package"] is True
    assert proof["authority_granted_any"] is False
    assert proof["live_model_call_performed"] is False
    assert proof["workbook_body_read_performed"] is False
    assert proof["spreadsheet_cell_read_performed"] is False
    assert proof["all_live_authority_false"] is True


def test_lm1_package_exported_readmodel_parses(tmp_path):
    payload = lm1_package.build_payload(generated_at=FIXED_NOW)
    json_path, operator_path = lm1_package.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == lm1_package.READ_MODEL_ID
    assert parsed["package_summary"]["output_schema_ref"] == "MachineIntentCandidate"
    assert "shadow package only" in operator_path.read_text(encoding="utf-8")

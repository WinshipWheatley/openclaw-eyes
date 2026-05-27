import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gate1_privacy_request_readiness as gate1


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def test_gate1_privacy_fixtures_cover_required_classes():
    fixtures = gate1.gate1_privacy_trigger_fixtures()
    by_input = {item["input_class"]: item for item in fixtures}

    assert by_input["normal"]["privacy_class"] == "LOW_METADATA"
    assert by_input["client_finance"]["privacy_class"] == "CLIENT_FINANCE_FILE_METADATA"
    assert by_input["client_finance"]["tokenization_required"] is True
    assert by_input["legal_confidential"]["strict_local_only_required"] is True
    assert by_input["personal_private"]["private_mode_recommended"] is True
    assert by_input["strict_local_only"]["privacy_class"] == "STRICT_PRIVATE_CLIENT_METADATA"
    assert all(item["lm1_raw_values_allowed"] is False for item in fixtures)


def test_gate1_classifies_finance_metadata_without_read_authority():
    result = gate1.classify_gate1_privacy_request(
        {
            "input_class": "file_metadata",
            "world_ref": "finance",
            "file_type": "spreadsheet",
            "user_note": "invoice workbook",
        }
    )

    assert result["privacy_class"] == "CLIENT_FINANCE_FILE_METADATA"
    assert result["tokenization_required"] is True
    assert result["lm1_raw_values_allowed"] is False
    assert "spreadsheet cells" in result["forbidden_context_classes"]


def test_gate1_payload_exports_chain_contract_and_no_live_authority(tmp_path):
    payload = gate1.build_payload(generated_at=FIXED_NOW)
    json_path, operator_path = gate1.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == gate1.READ_MODEL_ID
    assert parsed["chain_contract"]["gate_1_output_can_feed_lm1_package"] is True
    assert parsed["chain_contract"]["lm1_may_receive_raw_values"] is False
    assert parsed["machine_proof"]["file_body_read_performed"] is False
    assert parsed["machine_proof"]["spreadsheet_cell_read_performed"] is False
    assert parsed["machine_proof"]["all_live_authority_false"] is True
    assert "Live models, tools, file reads, and external actions remain off" in operator_path.read_text(encoding="utf-8")

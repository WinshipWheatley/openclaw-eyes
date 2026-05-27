import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gate1_operational_snapshot as snapshot


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def test_gate1_snapshot_classifies_client_finance_request():
    item = snapshot.build_gate1_operational_snapshot(
        {
            "source_request_id": "test_gate1_finance",
            "user_message": "what's next for the Capital Hilton invoice?",
            "file_display_name": "Invoice Capitol Hilton Running.xlsx",
            "file_extension": ".xlsx",
            "file_type": "spreadsheet",
            "world_ref": "finance",
        }
    )

    assert item["source_request_id"] == "test_gate1_finance"
    assert item["world_ref"] == "finance"
    assert item["client_ref"] == "capital_hilton"
    assert item["workflow_ref"] == "capital_hilton_invoice_workflow"
    assert item["privacy_class"] == "CLIENT_FINANCE_FILE_METADATA"
    assert item["tokenization_required"] is True
    assert item["safe_to_package_for_lm1"] is True
    assert item["raw_values_included"] is False
    assert item["universal_intake_inference"]["artifact_kind"] == "running_invoice_workbook"


def test_gate1_snapshot_blocks_lm1_packaging_if_privacy_policy_is_insufficient():
    item = snapshot.build_gate1_operational_snapshot(
        {
            "source_request_id": "test_gate1_privacy_missing",
            "user_message": "handle this private client finance workbook",
            "file_display_name": "Invoice Capitol Hilton Running.xlsx",
            "file_extension": ".xlsx",
            "file_type": "spreadsheet",
            "world_ref": "finance",
            "tokenization_policy_available": False,
        }
    )

    assert item["tokenization_required"] is True
    assert item["safe_to_package_for_lm1"] is False
    assert item["unsafe_reason"] == "TOKENIZATION_POLICY_REQUIRED"
    assert item["next_safe_move"].startswith("Ask one clarification")


def test_gate1_snapshot_carries_only_safe_metadata_and_no_live_authority():
    item = snapshot.build_gate1_operational_snapshot()

    artifact = item["artifact_metadata"]
    assert artifact["body_read"] is False
    assert artifact["workbook_body_read"] is False
    assert artifact["spreadsheet_cell_read"] is False
    assert artifact["ocr_performed"] is False
    assert all(value is False for value in item["authority_boundary"].values())
    assert "raw workbook body" in item["forbidden_context_classes"]


def test_exported_readmodel_parses(tmp_path):
    payload = snapshot.build_payload(generated_at=FIXED_NOW)
    json_path, operator_path = snapshot.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == snapshot.READ_MODEL_ID
    assert parsed["machine_proof"]["capital_hilton_snapshot_safe_for_lm1"] is True
    assert parsed["machine_proof"]["privacy_policy_missing_blocks_lm1"] is True
    assert parsed["machine_proof"]["all_live_authority_false"] is True
    assert "Gate 1 Operational Snapshot" in operator_path.read_text(encoding="utf-8")

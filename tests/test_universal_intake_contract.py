import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import universal_intake_contract as intake


def test_universal_intake_infers_capital_hilton_running_invoice_workbook():
    candidate = intake.infer_universal_intake(
        {
            "source_request_id": "test_capital_hilton",
            "file_display_name": "Invoice Capitol Hilton Running.xlsx",
            "file_extension": ".xlsx",
            "file_type": "spreadsheet",
            "user_note": "this new workbook is the real Capital Hilton workbook",
            "current_world_ref": "finance",
        }
    )

    assert candidate["world_ref"] == "finance"
    assert candidate["client_ref"] == "capital_hilton"
    assert candidate["artifact_kind"] == "running_invoice_workbook"
    assert candidate["intended_use"] == "register_or_resolve_invoice_workbook_artifact"
    assert candidate["confidence"] == "HIGH"
    assert candidate["privacy_class"] == "CLIENT_FINANCE_FILE_METADATA"
    assert candidate["lm1_chain_ready"] is True
    assert candidate["chain_contract"]["candidate_may_enter_gate_2_after_lm1_proposal"] is True
    assert candidate["chain_contract"]["lm1_may_receive_raw_values"] is False
    assert candidate["submitted"] is False
    assert candidate["paid"] is False
    assert candidate["ledger_posted"] is False
    assert candidate["final"] is False
    assert candidate["proposed_facts_only"] is True


def test_universal_intake_asks_one_question_for_ambiguous_file_note():
    candidate = intake.infer_universal_intake(
        {
            "source_request_id": "test_ambiguous",
            "file_display_name": "Invoice Running.xlsx",
            "file_extension": ".xlsx",
            "file_type": "spreadsheet",
            "user_note": "use this",
            "current_world_ref": "finance",
        }
    )

    assert candidate["confidence"] == "MEDIUM"
    assert candidate["client_ref"] == "unknown"
    assert candidate["clarification_question"] == "Which client or workflow should this workbook belong to?"
    assert candidate["lm1_chain_ready"] is False


def test_universal_intake_batch_classifies_three_running_invoice_workbooks_as_draft_source_only():
    batch = intake.infer_universal_intake_batch(
        {
            "source_request_id": "test_batch",
            "user_note": "these are the invoice workbooks for the clients named in the files",
            "current_world_ref": "finance",
            "files": (
                "Invoice Capitol Hilton Running.xlsx",
                "Invoice Live Arts MD! Running.xlsx",
                "Invoice St. Anne's Running.xlsx",
            ),
        }
    )

    clients = {candidate["client_ref"] for candidate in batch["candidates"]}
    assert clients == {"capital_hilton", "live_arts_md", "st_annes"}
    assert batch["needs_clarification"] is False
    assert batch["batch_confidence"] == "HIGH"
    for candidate in batch["candidates"]:
        assert candidate["world_ref"] == "finance"
        assert candidate["artifact_kind"] == "running_invoice_workbook"
        assert candidate["submitted"] is False
        assert candidate["paid"] is False
        assert candidate["ledger_posted"] is False
        assert candidate["final"] is False
        assert candidate["proposed_facts_only"] is True


def test_universal_intake_operator_text_has_no_backend_path_language():
    candidate = intake.infer_universal_intake(
        {
            "source_request_id": "test_capital_hilton",
            "file_display_name": "Invoice Capitol Hilton Running.xlsx",
            "file_extension": ".xlsx",
            "file_type": "spreadsheet",
            "user_note": "real workbook",
            "current_world_ref": "finance",
        }
    )

    operator_text = f"{candidate['operator_headline']} {candidate['operator_message']} {candidate['next_safe_action']}"
    assert "/mnt/" not in operator_text
    assert "PC-readable" not in operator_text
    assert "backend path" not in operator_text.lower()


def test_universal_intake_unknown_non_invoice_artifact_asks_clarification():
    candidate = intake.infer_universal_intake(
        {
            "source_request_id": "test_unknown_artifact",
            "file_display_name": "stage_plot_notes.txt",
            "file_extension": ".txt",
            "file_type": "text",
            "user_note": "handle this later",
            "current_world_ref": "music",
        }
    )

    assert candidate["artifact_kind"] == "unknown_file_reference"
    assert candidate["intended_use"] == "needs_clarification"
    assert candidate["confidence"] == "LOW"
    assert candidate["clarification_question"] == "What workflow should this file support?"
    assert candidate["lm1_chain_ready"] is False
    assert candidate["backend_paths_exposed"] is False


def test_exported_readmodel_parses(tmp_path):
    payload = intake.build_payload()
    json_path, operator_path = intake.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == intake.READ_MODEL_ID
    assert parsed["machine_proof"]["capital_hilton_fixture_inferred"] is True
    assert parsed["machine_proof"]["fixture_submitted_false"] is True
    assert parsed["machine_proof"]["batch_fixture_count"] == 3
    assert parsed["machine_proof"]["batch_fixture_all_draft_source_only"] is True
    assert parsed["machine_proof"]["capital_hilton_chain_ready"] is True
    assert parsed["machine_proof"]["unknown_artifact_asks_clarification"] is True
    assert parsed["machine_proof"]["unknown_artifact_not_invoice"] is True
    assert "metadata-only" in operator_path.read_text(encoding="utf-8")

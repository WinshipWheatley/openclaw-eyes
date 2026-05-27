import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import live_lm_shadow_trial as trial


FIXED_NOW = "2026-05-26T00:00:00+00:00"


def _responses():
    candidate = trial._expected_candidate(trial._fixture_context())
    response = {
        "source_request_id": "live_shadow_capital_hilton_next_safe_move",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "client_ref": "capital_hilton",
        "response_author": "CHIEF",
        "selected_model_backend": "LIVE_SHADOW_LOCAL_OLLAMA",
        "allowed_tools_plugins": [],
        "headline": "Capital Hilton next step",
        "one_line_answer": "OpenClaw can prepare a safe next-step readback.",
        "eliwinship": "OpenClaw can explain the next safe move from bounded fixture context. No delivery, posting, workbook read, or file change occurred.",
        "next_action": "Next: review the safe readback.",
    }
    return [json.dumps(candidate), json.dumps(response)]


def test_live_shadow_not_run_by_default_is_safe(tmp_path):
    payload = trial.build_payload(generated_at=FIXED_NOW, allow_live=False, db_path=tmp_path / "shadow.sqlite")

    assert payload["trial_status"] == trial.TRIAL_NOT_RUN
    assert payload["machine_proof"]["live_model_call_performed"] is False
    assert payload["machine_proof"]["raw_sensitive_data_included"] is False
    assert payload["machine_proof"]["all_production_authority_false"] is True


def test_mocked_live_shadow_trial_passes_gates_and_persists(tmp_path):
    responses = _responses()

    def runner(prompt: str) -> str:
        return responses.pop(0)

    db_path = tmp_path / "live_shadow.sqlite"
    payload = trial.build_payload(
        generated_at=FIXED_NOW,
        allow_live=True,
        db_path=db_path,
        runner=runner,
    )

    assert payload["trial_status"] == trial.TRIAL_PASSED
    proof = payload["machine_proof"]
    assert proof["live_model_call_performed"] is True
    assert proof["provider_class"] == trial.DEFAULT_PROVIDER_CLASS
    assert proof["model_ref"] == trial.DEFAULT_MODEL_REF
    assert proof["network_scope"] == "localhost_ollama_only"
    assert proof["tokenized_or_minimized"] is True
    assert proof["raw_sensitive_data_included"] is False
    assert proof["lm1_parse_ok"] is True
    assert proof["lm1_expected_match"] is True
    assert proof["gate2_accepted"] is True
    assert proof["gate3_compiled"] is True
    assert proof["lm2_parse_ok"] is True
    assert proof["gate4_validated"] is True
    assert proof["live_shadow_receipt_valid"] is True
    assert db_path.exists()
    assert "live_lm_shadow_trials" in payload["isolated_sqlite"]["tables"]


def test_bad_live_shadow_output_fails_without_authority(tmp_path):
    def runner(prompt: str) -> str:
        return "not json"

    payload = trial.build_payload(
        generated_at=FIXED_NOW,
        allow_live=True,
        db_path=tmp_path / "bad.sqlite",
        runner=runner,
    )

    assert payload["trial_status"] == trial.TRIAL_PARSE_FAILED
    assert payload["machine_proof"]["live_shadow_receipt_valid"] is False
    assert payload["machine_proof"]["production_state_mutation_performed"] is False
    assert payload["machine_proof"]["tool_execution_performed"] is False
    assert payload["machine_proof"]["external_action_performed"] is False
    assert payload["machine_proof"]["send_submit_performed"] is False


def test_exported_readmodel_parses(tmp_path):
    responses = _responses()

    def runner(prompt: str) -> str:
        return responses.pop(0)

    payload = trial.build_payload(
        generated_at=FIXED_NOW,
        allow_live=True,
        db_path=tmp_path / "export.sqlite",
        runner=runner,
    )
    json_path, operator_path = trial.write_exports(payload, tmp_path)

    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["read_model_id"] == trial.READ_MODEL_ID
    assert parsed["machine_proof"]["live_shadow_receipt_valid"] is True
    assert parsed["machine_proof"]["all_production_authority_false"] is True
    assert "Production authority remains off" in operator_path.read_text(encoding="utf-8")

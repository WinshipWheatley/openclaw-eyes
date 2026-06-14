import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lm2_room_backed_worker_pilot_postmortem as postmortem
import lm2_room_backed_worker_one_time_pilot as pilot_runner
import proof_to_response_runtime as runtime
import proof_to_response_schema_adapter as schema_adapter


FIXED_NOW = "2026-06-08T14:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _pilot_payload() -> dict:
    return {
        "status": pilot_runner.READY_STATUS,
        "approval_usage": {
            "approval_required": True,
            "approval_matched": True,
            "approval_unused_before_run": True,
            "approval_used": True,
            "approval_used_at": FIXED_NOW,
        },
        "pilot_scope": {"attempt_count": 1, "attempt_limit": 1},
        "room_backed_package_summary": {"package_matches_scope": True},
        "project_room_gate": {"project_room_ready": True},
        "redacted_proof_bundle_summary": {"freshness_allowed": True},
        "forbidden_fields_absent": True,
        "invocation_attempt": {
            "attempted": True,
            "attempt_number": 1,
            "runtime_ref": "ollama",
            "model_name": "qwen3:8b-q4_K_M",
            "stdout_hash": "sha256:stdout",
            "stderr_hash": "sha256:stderr",
        },
        "schema_adapter_result": {
            "parse_status": "PARSE_ERROR",
            "adapter_errors": ["json_parse_error:Expecting value"],
            "verifier_ready": False,
            "verifier_failure_reasons": [],
        },
        "publication_decision": "safe_fallback_published",
        "published_response": {
            "headline": "Payment evidence needed",
            "body": "Coupa is processing. I can't mark this paid until payment evidence is attached. The ledger stays untouched.",
            "next_step": "Attach payment evidence.",
            "verification_status": "fallback",
            "fallback_reason": "json_parse_error:Expecting value",
        },
        "implementation_boundary": {
            "business_action_performed": False,
            "tool_authority": False,
            "tool_execution_performed": False,
            "browser_opened": False,
            "gmail_opened": False,
            "coupa_opened": False,
            "email_send_performed": False,
            "submit_performed": False,
            "ledger_mutation_performed": False,
            "workbook_mutation_performed": False,
            "pdf_export_performed": False,
            "paid_marking_performed": False,
            "memory_promotion_performed": False,
            "git_push_performed": False,
            "git_merge_performed": False,
            "raw_financial_proof_sent": False,
            "operator_device_session_secret_sent": False,
        },
        "authority_boundary": {
            "business_action_authority": False,
            "business_action_allowed": False,
            "tool_authority": False,
            "tool_authority_allowed": False,
            "protected_actions_allowed": False,
            "authority_granted": False,
        },
    }


def _latest_payload() -> dict:
    return {
        "status": runtime.READY_STATUS,
        "read_model_id": runtime.LATEST_READ_MODEL_ID,
        "proof_to_response_status": "fallback",
        "latest_receipt_ref": "lm2_room_backed_worker_pilot:fallback_receipt",
    }


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(root / pilot_runner.JSON_EXPORT_NAME, _pilot_payload())
    _write_json(root / runtime.LATEST_JSON_EXPORT_NAME, _latest_payload())
    _write_json(root / schema_adapter.STATUS_JSON_EXPORT_NAME, {"status": schema_adapter.READY_STATUS})
    _write_json(root / runtime.STATUS_JSON_EXPORT_NAME, {"status": runtime.READY_STATUS})
    _write_json(root / "project_room_package_compiler_integration.json", {"status": "PROJECT_ROOM_PACKAGE_COMPILER_INTEGRATION_READY"})
    _write_json(root / "lm2_room_backed_worker_pilot_boundary.json", {"status": "LM2_ROOM_BACKED_WORKER_PILOT_BOUNDARY_READY"})
    return root


def _sqlite_path(tmp_path: Path) -> Path:
    path = tmp_path / "pilot.sqlite"
    rows = [
        "operator_approval_receipt",
        "room_backed_package_receipt",
        "project_room_readiness_receipt",
        "worker_package_boundary_receipt",
        "model_invocation_boundary_receipt",
        "redacted_proof_bundle_receipt",
        "no_external_provider_receipt",
        "no_tool_authority_receipt",
        "worker_started_receipt",
        "model_invocation_attempt_receipt",
        "raw_draft_captured_receipt",
        "worker_stopped_receipt",
        "verifier_pass_fail_receipt",
        "fallback_receipt",
        "no_business_action_receipt",
    ]
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
CREATE TABLE lm2_room_backed_worker_pilot_receipts (
  receipt_id TEXT PRIMARY KEY,
  receipt_ref TEXT NOT NULL,
  receipt_status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  phase TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  proof_summary TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  receipt_json TEXT NOT NULL
)
"""
        )
        for idx, ref in enumerate(rows):
            conn.execute(
                "INSERT INTO lm2_room_backed_worker_pilot_receipts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"receipt:{idx}",
                    ref,
                    "present",
                    FIXED_NOW,
                    "after_future_attempt" if idx >= 8 else "before_future_attempt",
                    "",
                    f"{ref} present",
                    "",
                    "{}",
                ),
            )
        conn.commit()
    return path


def _read_model(tmp_path: Path) -> dict:
    return postmortem.build_read_model(
        read_model_root=_fixture_root(tmp_path),
        sqlite_path=_sqlite_path(tmp_path),
        generated_at=FIXED_NOW,
    )


def test_postmortem_records_non_json_as_output_shape_failure(tmp_path):
    read_model = _read_model(tmp_path)
    analysis = read_model["postmortem"]

    assert read_model["status"] == postmortem.READY_STATUS
    assert analysis["failure_class"] == "non_json_model_output"
    assert analysis["secondary_failure_class"] == "structured_output_boundary_failure"
    assert analysis["adapter_parse_status"] == "PARSE_ERROR"
    assert analysis["question_answers"]["problem_classification"]["output_shape_problem"] is True
    assert analysis["question_answers"]["problem_classification"]["context_problem"] is False
    assert read_model["machine_proof"]["non_json_recorded_as_output_shape_failure"] is True


def test_postmortem_confirms_no_forbidden_fields_sent(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["postmortem"]["question_answers"]["did_model_receive_forbidden_fields"] is False
    assert read_model["postmortem"]["forbidden_fields_absent"] is True
    assert read_model["machine_proof"]["no_forbidden_fields_sent"] is True


def test_postmortem_confirms_no_protected_action_occurred(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["postmortem"]["question_answers"]["did_model_attempt_protected_action"] is False
    assert read_model["postmortem"]["protected_action_occurred"] is False
    assert read_model["machine_proof"]["no_protected_action_occurred"] is True


def test_postmortem_confirms_fallback_and_receipts(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["postmortem"]["question_answers"]["did_fallback_publish_correctly"] is True
    assert read_model["postmortem"]["question_answers"]["were_receipts_complete"] is True
    assert read_model["sqlite_receipt_summary"]["row_count"] == 15
    assert "fallback_receipt" in read_model["sqlite_receipt_summary"]["receipt_refs"]
    assert read_model["machine_proof"]["fallback_and_receipts_confirmed"] is True
    assert read_model["machine_proof"]["sqlite_row_count_matches_receipts"] is True


def test_postmortem_confirms_approval_used_exactly_once(tmp_path):
    read_model = _read_model(tmp_path)

    assert read_model["postmortem"]["question_answers"]["was_approval_used_exactly_once"] is True
    assert read_model["postmortem"]["approval_used_exactly_once"] is True
    assert read_model["machine_proof"]["approval_used_exactly_once"] is True


def test_postmortem_requires_structured_output_plan_before_retry(tmp_path):
    read_model = _read_model(tmp_path)
    plan = read_model["structured_output_plan"]

    assert plan["plan_status"] == "required_before_any_retry"
    assert plan["current_invocation"]["method"] == "ollama_cli_run_via_subprocess"
    assert plan["current_invocation"]["used_api_format_schema"] is False
    assert plan["next_invocation"]["should_use_ollama_api_format_with_json_schema"] is True
    assert plan["next_invocation"]["response_json_schema"] == schema_adapter.strict_json_draft_schema()
    assert plan["mandatory_gates"]["verifier_mandatory"] is True
    assert plan["mandatory_gates"]["fallback_mandatory"] is True
    assert plan["mandatory_gates"]["one_attempt_approval_boundary_mandatory"] is True
    assert plan["mandatory_gates"]["truth_checks_loosened"] is False
    assert plan["mandatory_gates"]["authority_checks_loosened"] is False
    assert read_model["machine_proof"]["structured_output_plan_required_before_retry"] is True


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _read_model(tmp_path)

    assert postmortem.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_and_wiki(tmp_path):
    result = postmortem.export_lm2_room_backed_worker_pilot_postmortem(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "LM2 Room Backed Worker Pilot Postmortem.md",
        sqlite_path=_sqlite_path(tmp_path),
        generated_at=FIXED_NOW,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == postmortem.READY_STATUS
    assert result["sqlite_row_count"] == "15"
    assert local == bridge
    assert postmortem.unsafe_true_grants(local) == []
    assert wiki.startswith("# LM2 Room Backed Worker Pilot Postmortem")

import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import lm2_room_backed_worker_one_time_pilot as pilot
import proof_bundle_builder as bundles
import proof_to_response_runtime as runtime


FIXED_NOW = "2026-06-08T13:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _freshness_gate_row() -> dict:
    return {
        "context_ref": "context:finance:capital_hilton:payment_watch",
        "world_ref": "finance",
        "thread_ref": "capital_hilton",
        "objective_ref": "objective:finance:capital_hilton:payment_watch",
        "source_refs": ["generated/read_models/proof_bundle_freshness_trace_status.json"],
        "receipt_refs": ["receipt:capital_hilton_payment_watch_current"],
        "decision_trace_refs": ["trace:capital_hilton_payment_watch"],
        "latest_receipt_ref": "receipt:capital_hilton_payment_watch_current",
        "superseded_receipt_refs": [],
        "freshness_state": "current",
        "confidence_class": "receipt_backed",
        "confidence_score": 0.95,
        "stale_reason": "",
        "decision_trace_summary": "Current receipt says Coupa is processing, payment evidence is missing, and ledger remains untouched.",
        "prior_attempts": [{"attempt_ref": "coupa_payment_watch"}],
        "prior_rejections": [],
        "operator_decisions": [],
        "allowed_for_lm_bundle": True,
        "required_refresh_action": "",
        "safe_human_response_if_blocked": "",
        "canonical_claims": {
            "coupa_state": "processing",
            "payment_evidence": "missing",
            "ledger_state": "untouched",
        },
        "blocked_claims": [],
    }


def _project_room_contract() -> dict:
    return {
        "status": "PROJECT_ROOM_SOURCESET_CONTRACT_READY",
        "project_rooms": [
            {
                "project_room_id": "finance_capital_hilton_payment_watch",
                "source_inventory_ref": "source_inventory:finance_capital_hilton_payment_watch",
                "conflict_log_ref": "conflict_log:finance_capital_hilton_payment_watch",
                "missing_context_ref": "missing_context:finance_payment_evidence",
                "duplicate_report_ref": "version_family:finance_payment_watch",
                "decision_trace_ref": "decision_trace:finance_capital_hilton_payment_watch",
                "freshness_gate_ref": "freshness_gate:receipt_current_or_needs_verification",
                "inventory_gate": "passed_with_limited_scope",
                "synthesis_allowed": True,
                "synthesis_scope": "explanation_and_next_step_only",
                "source_disagreement_detected": False,
                "missing_context_blocks": ["paid claim", "ledger action"],
                "blocked_next_steps": ["mark paid", "mutate ledger"],
            }
        ],
        "source_inventory": [
            {
                "project_room_id": "finance_capital_hilton_payment_watch",
                "source_inventory_ref": "source_inventory:finance_capital_hilton_payment_watch",
                "source_ref": "source:finance_payment_watch_state",
                "apparent_authority": "current_receipts_and_proof",
                "freshness_state": "current_receipt",
                "confidence_class": "receipt_backed",
                "claims_supported": ["Coupa processing is still in progress.", "paid=false", "ledger untouched"],
                "limitations": ["Does not prove payment completion."],
            },
            {
                "project_room_id": "finance_capital_hilton_payment_watch",
                "source_inventory_ref": "source_inventory:finance_capital_hilton_payment_watch",
                "source_ref": "source:finance_generated_summary",
                "apparent_authority": "generated_summaries",
                "freshness_state": "support_only",
            },
        ],
        "conflict_log": [],
        "missing_context_list": [
            {
                "project_room_id": "finance_capital_hilton_payment_watch",
                "missing_context_ref": "missing_context:finance_payment_evidence",
                "gap_summary": "Payment evidence is missing.",
                "safe_wording_if_unresolved": "Payment evidence is missing; I can explain the watch state and next step, but cannot mark paid.",
            }
        ],
        "duplicate_version_report": [
            {
                "project_room_id": "finance_capital_hilton_payment_watch",
                "version_family_ref": "version_family:finance_payment_watch",
                "candidate_source_refs": ["source:finance_payment_watch_state", "source:finance_generated_summary"],
                "likely_current_source_ref": "source:finance_payment_watch_state",
                "older_or_superseded_refs": ["source:finance_generated_summary"],
                "deletion_allowed": False,
                "operator_review_required": True,
            }
        ],
    }


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "generated" / "read_models"
    _write_json(
        root / "lm2_room_backed_worker_pilot_operator_approval.json",
        {
            "status": "LM2_ROOM_BACKED_WORKER_PILOT_OPERATOR_APPROVAL_READY",
            "operator_decision": "approve_one_time_room_backed_lm2_worker_pilot",
            "approved_for_one_future_attempt_only": True,
            "approval_scope": {
                "approved_for_one_future_attempt_only": True,
                "attempt_limit": 1,
                "fallback_required": True,
                "lane": "finance/capital_hilton",
                "mode": "proof_to_response_only",
                "model_name": "qwen3:8b-q4_K_M",
                "model_ref": "local_model:ollama:qwen3_8b-q4_k_m",
                "objective": "payment_watch_response",
                "package_type": "room-backed worker package",
                "pilot_question": "What should I do here?",
                "runtime_ref": "ollama",
                "verifier_required": True,
                "worker_class": "lm2_bounded_worker",
            },
        },
    )
    _write_json(root / "lm2_room_backed_worker_pilot_approval_packet.json", {"status": "LM2_ROOM_BACKED_WORKER_PILOT_APPROVAL_PACKET_READY"})
    _write_json(root / "lm2_room_backed_worker_pilot_boundary.json", {"status": "LM2_ROOM_BACKED_WORKER_PILOT_BOUNDARY_READY"})
    _write_json(root / "project_room_sourceset_contract.json", _project_room_contract())
    _write_json(root / "project_room_package_compiler_integration.json", {"status": "PROJECT_ROOM_PACKAGE_COMPILER_INTEGRATION_READY"})
    _write_json(root / "proof_bundle_freshness_trace_status.json", {"status": "PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY"})
    _write_json(root / bundles.REDACTION_STATUS_JSON_EXPORT_NAME, {"status": bundles.REDACTION_READY_STATUS})
    _write_json(
        root / "context_freshness_decision_trace_gate.json",
        {"status": "CONTEXT_FRESHNESS_DECISION_TRACE_GATE_READY", "gate_rows": [_freshness_gate_row()]},
    )
    _write_json(root / "context_compaction_preview_policy.json", {"status": "CONTEXT_COMPACTION_PREVIEW_POLICY_READY"})
    _write_json(root / "proof_to_response_schema_adapter_status.json", {"status": "PROOF_TO_RESPONSE_SCHEMA_ADAPTER_READY"})
    _write_json(root / runtime.STATUS_JSON_EXPORT_NAME, {"status": runtime.READY_STATUS})
    _write_json(root / "local_model_selection_for_proof_response.json", {"status": "LOCAL_MODEL_SELECTION_FOR_PROOF_RESPONSE_READY"})
    return root


def _safe_invoker(prompt: str) -> dict:
    assert "raw_ledger_rows" not in prompt
    assert "operator_device_session_verification_secrets" not in prompt
    assert "workbook_email_or_ledger_bodies" not in prompt
    return {
        "attempted": True,
        "runtime_ref": "ollama",
        "model_name": "qwen3:8b-q4_K_M",
        "returncode": 0,
        "stdout": json.dumps(
            {
                "headline": "Payment evidence needed",
                "body": "Coupa is processing. I can't mark this paid until payment evidence is attached. The ledger stays untouched.",
                "next_step": "Attach payment evidence.",
                "missing_input": ["payment_evidence"],
                "can_do_now": ["explain the payment-watch state", "accept payment evidence"],
                "cannot_do_yet": ["mark paid", "post to the ledger", "submit anything"],
                "claimed_facts": ["payment_evidence_missing", "processor_processing", "ledger_untouched", "paid_false"],
                "requested_controls": ["attach_proof"],
                "uncertainty_notes": [],
            }
        ),
        "stderr": "",
        "timed_out": False,
    }


def _bad_invoker(prompt: str) -> dict:
    return {
        "attempted": True,
        "runtime_ref": "ollama",
        "model_name": "qwen3:8b-q4_K_M",
        "returncode": 0,
        "stdout": "The invoice is paid and submitted.",
        "stderr": "",
        "timed_out": False,
    }


def _run(tmp_path: Path, invoker=_safe_invoker) -> dict:
    return pilot.run_one_time_pilot(
        read_model_root=_fixture_root(tmp_path),
        generated_at=FIXED_NOW,
        invoker=invoker,
        invoke_model=True,
        sqlite_path=tmp_path / "pilot.sqlite",
    )


def test_exactly_one_worker_attempt(tmp_path):
    calls = []

    def invoker(prompt: str) -> dict:
        calls.append(prompt)
        return _safe_invoker(prompt)

    read_model = _run(tmp_path, invoker=invoker)

    assert len(calls) == 1
    assert read_model["pilot_scope"]["attempt_limit"] == 1
    assert read_model["pilot_scope"]["attempt_count"] == 1
    assert read_model["machine_proof"]["exactly_one_worker_attempt"] is True
    assert read_model["implementation_boundary"]["additional_worker_spawn_performed"] is False


def test_approval_required_and_marked_used(tmp_path):
    read_model = _run(tmp_path)

    assert read_model["approval_usage"]["approval_required"] is True
    assert read_model["approval_usage"]["approval_matched"] is True
    assert read_model["approval_usage"]["approval_unused_before_run"] is True
    assert read_model["approval_usage"]["approval_used"] is True
    assert read_model["machine_proof"]["approval_required_and_marked_used"] is True


def test_runtime_model_match_approval(tmp_path):
    read_model = _run(tmp_path)

    assert read_model["pilot_scope"]["runtime_ref"] == "ollama"
    assert read_model["pilot_scope"]["model_ref"] == "local_model:ollama:qwen3_8b-q4_k_m"
    assert read_model["pilot_scope"]["model_name"] == "qwen3:8b-q4_K_M"
    assert read_model["machine_proof"]["runtime_model_match_approval"] is True


def test_room_backed_package_required(tmp_path):
    read_model = _run(tmp_path)

    assert read_model["room_backed_package_summary"]["room_backed_package_required"] is True
    assert read_model["room_backed_package_summary"]["project_room_id"] == "finance_capital_hilton_payment_watch"
    assert read_model["machine_proof"]["room_backed_package_required"] is True


def test_project_room_readiness_checked(tmp_path):
    read_model = _run(tmp_path)
    gate = read_model["project_room_gate"]

    assert gate["project_room_ready"] is True
    assert gate["source_inventory_exists"] is True
    assert gate["unresolved_critical_conflict"] is False
    assert gate["missing_context_blocks_supported_answer"] is False
    assert read_model["machine_proof"]["project_room_readiness_checked"] is True


def test_freshness_gate_checked(tmp_path):
    read_model = _run(tmp_path)

    assert read_model["redacted_proof_bundle_summary"]["freshness_gate_checked"] is True
    assert read_model["redacted_proof_bundle_summary"]["freshness_allowed"] is True
    assert read_model["redacted_proof_bundle_summary"]["freshness_state"] == "current"
    assert read_model["machine_proof"]["freshness_gate_checked"] is True


def test_forbidden_fields_absent(tmp_path):
    read_model = _run(tmp_path)

    assert read_model["forbidden_fields_absent"] is True
    assert read_model["redacted_proof_bundle_summary"]["forbidden_fields_absent"] is True
    assert read_model["machine_proof"]["forbidden_fields_absent"] is True


def test_external_provider_unused(tmp_path):
    read_model = _run(tmp_path)

    assert read_model["implementation_boundary"]["external_provider_used"] is False
    assert read_model["machine_proof"]["external_provider_unused"] is True


def test_tool_authority_false(tmp_path):
    read_model = _run(tmp_path)

    assert read_model["authority_boundary"]["tool_authority"] is False
    assert read_model["authority_boundary"]["tool_authority_allowed"] is False
    assert read_model["implementation_boundary"]["tool_execution_performed"] is False
    assert read_model["machine_proof"]["tool_authority_false"] is True


def test_business_action_flags_false(tmp_path):
    read_model = _run(tmp_path)
    boundary = read_model["implementation_boundary"]

    assert boundary["business_action_performed"] is False
    assert boundary["ledger_mutation_performed"] is False
    assert boundary["workbook_mutation_performed"] is False
    assert boundary["pdf_export_performed"] is False
    assert boundary["paid_marking_performed"] is False
    assert read_model["machine_proof"]["business_action_flags_false"] is True


def test_schema_adapter_runs_before_verifier(tmp_path):
    read_model = _run(tmp_path)
    steps = read_model["pipeline_steps"]

    assert steps.index("schema_adapter_ran") < steps.index("verifier_ran")
    assert read_model["schema_adapter_result"]["parse_status"] == "PARSED"
    assert read_model["machine_proof"]["schema_adapter_runs_before_verifier"] is True


def test_verifier_gates_publication(tmp_path):
    read_model = _run(tmp_path)

    assert read_model["schema_adapter_result"]["verifier_ready"] is True
    assert read_model["verifier_result"]["publishable"] is True
    assert read_model["publication_decision"] == "verified_text_published"
    assert read_model["proof_to_response_latest"]["latest_response"]["headline"] == "Payment evidence needed"
    assert read_model["machine_proof"]["verifier_gates_publication"] is True


def test_fallback_works_if_adapter_or_verifier_fails(tmp_path):
    read_model = _run(tmp_path, invoker=_bad_invoker)

    assert read_model["schema_adapter_result"]["parse_status"] == "PARSE_ERROR"
    assert read_model["publication_decision"] == "safe_fallback_published"
    assert read_model["published_response"]["verification_status"] == "fallback"
    assert read_model["published_response"]["headline"] == "Payment evidence needed"
    assert any(row["receipt_ref"] == "fallback_receipt" for row in read_model["receipts"])


def test_sqlite_receipts_recorded(tmp_path):
    sqlite_path = tmp_path / "pilot.sqlite"
    read_model = pilot.run_one_time_pilot(
        read_model_root=_fixture_root(tmp_path),
        generated_at=FIXED_NOW,
        invoker=_safe_invoker,
        invoke_model=True,
        sqlite_path=sqlite_path,
    )
    with sqlite3.connect(sqlite_path) as conn:
        row_count = conn.execute("SELECT COUNT(*) FROM lm2_room_backed_worker_pilot_receipts").fetchone()[0]

    assert row_count == len(read_model["receipts"])
    assert row_count == 15
    assert read_model["sqlite_row_count"] == read_model["sqlite_expected_row_count"]
    assert read_model["machine_proof"]["sqlite_receipts_recorded"] is True


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _run(tmp_path)

    assert pilot.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_latest_and_wiki(tmp_path):
    result = pilot.export_one_time_pilot(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "LM2 Room Backed Worker One Time Pilot.md",
        sqlite_path=tmp_path / "pilot.sqlite",
        generated_at=FIXED_NOW,
        invoker=_safe_invoker,
        invoke_model=True,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    latest = json.loads(Path(result["latest_path"]).read_text(encoding="utf-8"))
    bridge_latest = json.loads(Path(result["bridge_latest_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == pilot.READY_STATUS
    assert result["attempt_count"] == "1"
    assert local == bridge
    assert latest == bridge_latest
    assert latest["world_ref"] == "finance"
    assert latest["thread_ref"] == "capital_hilton"
    assert pilot.unsafe_true_grants(local) == []
    assert wiki.startswith("# LM2 Room Backed Worker One Time Pilot")

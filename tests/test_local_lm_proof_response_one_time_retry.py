import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_lm_proof_response_one_time_retry as retry
import proof_bundle_builder as bundles
import proof_to_response_runtime as runtime


FIXED_NOW = "2026-06-07T22:15:00+00:00"


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


def _fixture_root(tmp_path: Path, *, include_approval: bool = True) -> Path:
    root = tmp_path / "generated" / "read_models"
    if include_approval:
        _write_json(
            root / "local_lm_proof_response_retry_operator_approval.json",
            {
                "status": "LOCAL_LM_PROOF_RESPONSE_RETRY_OPERATOR_APPROVAL_READY",
                "operator_decision": "approve_one_time_local_lm_retry_with_schema_adapter",
                "approval_scope": {
                    "attempt_limit": 1,
                    "lane": "finance/capital_hilton",
                    "question": "What should I do here?",
                    "runtime": "ollama",
                    "model": "qwen3:8b-q4_K_M",
                    "prompt_mode": "JSON-only",
                    "schema_adapter_required": True,
                    "valid_example_required": True,
                    "verifier_required": True,
                    "fallback_required": True,
                },
                "approval_limits": {
                    "one_retry_attempt_only": True,
                    "model_must_match": "qwen3:8b-q4_K_M",
                    "runtime_must_match": "ollama",
                },
            },
        )
    _write_json(root / "local_lm_proof_response_retry_approval_packet.json", {"status": "LOCAL_LM_PROOF_RESPONSE_RETRY_APPROVAL_PACKET_READY"})
    _write_json(root / "local_lm_proof_response_pilot_postmortem.json", {"status": "LOCAL_LM_PROOF_RESPONSE_PILOT_POSTMORTEM_READY"})
    _write_json(root / "proof_to_response_schema_adapter_status.json", {"status": "PROOF_TO_RESPONSE_SCHEMA_ADAPTER_READY"})
    _write_json(root / "local_model_selection_for_proof_response.json", {"status": "LOCAL_MODEL_SELECTION_FOR_PROOF_RESPONSE_READY"})
    _write_json(root / "proof_bundle_freshness_trace_status.json", {"status": "PROOF_BUNDLE_FRESHNESS_TRACE_INTEGRATION_READY"})
    _write_json(root / bundles.REDACTION_STATUS_JSON_EXPORT_NAME, {"status": bundles.REDACTION_READY_STATUS})
    _write_json(root / runtime.STATUS_JSON_EXPORT_NAME, {"status": runtime.READY_STATUS})
    _write_json(root / runtime.LATEST_JSON_EXPORT_NAME, {"status": runtime.READY_STATUS, "stale_if_context_mismatch": True})
    _write_json(
        root / "context_freshness_decision_trace_gate.json",
        {
            "status": "CONTEXT_FRESHNESS_DECISION_TRACE_GATE_READY",
            "gate_rows": [_freshness_gate_row()],
        },
    )
    _write_json(
        root / "local_lm_proof_response_invocation_boundary_packet.json",
        {
            "status": "LOCAL_LM_PROOF_RESPONSE_INVOCATION_BOUNDARY_PACKET_READY",
            "invocation_boundary_packet": {
                "selected_runtime_ref": "ollama",
                "selected_model_ref": "local_model:ollama:qwen3_8b-q4_k_m",
                "selected_model_name": "qwen3:8b-q4_K_M",
            },
        },
    )
    return root


def _safe_invoker(prompt: str) -> dict:
    assert "raw_ledger_rows" not in prompt
    assert "operator_device_session_verification_secrets" not in prompt
    assert "valid_example" in prompt
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
                "claimed_facts": ["payment_evidence_missing", "coupa_processing", "ledger_untouched"],
                "requested_controls": ["Attach payment evidence"],
                "uncertainty_notes": [],
            }
        ),
        "stderr": "",
        "timed_out": False,
    }


def _bad_paid_invoker(prompt: str) -> dict:
    return {
        "attempted": True,
        "runtime_ref": "ollama",
        "model_name": "qwen3:8b-q4_K_M",
        "returncode": 0,
        "stdout": json.dumps(
            {
                "headline": "Invoice is paid",
                "body": "The invoice is paid and the ledger was updated.",
                "next_step": "Mark it paid.",
                "missing_input": [],
                "can_do_now": ["mark paid"],
                "cannot_do_yet": [],
                "claimed_facts": ["paid"],
                "requested_controls": ["Mark paid"],
                "uncertainty_notes": [],
            }
        ),
        "stderr": "",
        "timed_out": False,
    }


def _run(tmp_path: Path, invoker=_safe_invoker, *, include_approval: bool = True) -> dict:
    return retry.run_one_time_retry(
        read_model_root=_fixture_root(tmp_path, include_approval=include_approval),
        generated_at=FIXED_NOW,
        invoker=invoker,
        invoke_model=True,
        sqlite_path=tmp_path / "retry.sqlite",
    )


def test_invocation_attempt_count_is_exactly_one(tmp_path):
    calls = []

    def invoker(prompt: str) -> dict:
        calls.append(prompt)
        return _safe_invoker(prompt)

    read_model = _run(tmp_path, invoker=invoker)

    assert len(calls) == 1
    assert read_model["retry_scope"]["attempt_limit"] == 1
    assert read_model["retry_scope"]["attempt_count"] == 1
    assert read_model["machine_proof"]["one_invocation_attempt_only"] is True
    assert read_model["implementation_boundary"]["repeated_invocation_performed"] is False


def test_approval_required_and_marked_used(tmp_path):
    read_model = _run(tmp_path)

    assert read_model["approval_usage"]["unused_before_run"] is True
    assert read_model["approval_usage"]["marked_used"] is True
    assert read_model["machine_proof"]["approval_required"] is True
    assert read_model["machine_proof"]["approval_marked_used"] is True
    assert "approval_used_receipt" in [row["receipt_ref"] for row in read_model["receipts"]]


def test_missing_approval_blocks_invocation(tmp_path):
    calls = []

    def invoker(prompt: str) -> dict:
        calls.append(prompt)
        return _safe_invoker(prompt)

    read_model = _run(tmp_path, invoker=invoker, include_approval=False)

    assert calls == []
    assert read_model["status"] == retry.NOT_READY_STATUS
    assert read_model["retry_scope"]["attempt_count"] == 0


def test_runtime_model_match_approval(tmp_path):
    read_model = _run(tmp_path)

    assert read_model["retry_scope"]["runtime_ref"] == "ollama"
    assert read_model["retry_scope"]["model_ref"] == "local_model:ollama:qwen3_8b-q4_k_m"
    assert read_model["retry_scope"]["model_name"] == "qwen3:8b-q4_K_M"
    assert read_model["approval_boundary_matched"] is True
    assert read_model["machine_proof"]["runtime_model_match_approval"] is True


def test_proof_bundle_is_redacted_and_freshness_gated(tmp_path):
    read_model = _run(tmp_path)
    summary = read_model["redacted_proof_bundle_summary"]

    assert summary["freshness_state"] == "current"
    assert summary["confidence_class"] == "receipt_backed"
    assert summary["trusted_current"] is True
    assert summary["redaction_validation_errors"] == []
    assert summary["forbidden_fields_absent"] is True
    assert read_model["machine_proof"]["proof_bundle_redacted_and_freshness_gated"] is True


def test_external_provider_unused(tmp_path):
    read_model = _run(tmp_path)

    assert read_model["implementation_boundary"]["external_provider_used"] is False
    assert read_model["machine_proof"]["external_provider_unused"] is True


def test_tool_authority_false(tmp_path):
    read_model = _run(tmp_path)

    assert read_model["authority_boundary"]["tool_authority"] is False
    assert read_model["implementation_boundary"]["tool_execution_performed"] is False
    assert read_model["machine_proof"]["tool_authority_false"] is True


def test_business_action_flags_false(tmp_path):
    read_model = _run(tmp_path)
    boundary = read_model["implementation_boundary"]

    assert boundary["business_action_performed"] is False
    assert boundary["ledger_mutation_performed"] is False
    assert boundary["paid_marking_performed"] is False
    assert boundary["email_send_performed"] is False
    assert read_model["machine_proof"]["business_action_flags_false"] is True


def test_schema_adapter_runs_before_verifier(tmp_path):
    read_model = _run(tmp_path)

    assert read_model["pipeline"]["schema_adapter_runs_before_verifier"] is True
    assert read_model["pipeline"]["adapter_parse_status"] == "PARSED"
    assert read_model["receipts"][8]["receipt_ref"] == "schema_adapter_receipt"
    assert read_model["receipts"][9]["receipt_ref"] == "verifier_pass_fail_receipt"


def test_verifier_gates_publication(tmp_path):
    read_model = _run(tmp_path)

    assert read_model["schema_adapter_result"]["verifier_ready"] is True
    assert read_model["verifier_result"]["publishable"] is True
    assert read_model["publication_decision"] == "verified_text_published"
    assert read_model["proof_to_response_latest"]["latest_response"]["headline"] == "Payment evidence needed"
    assert read_model["machine_proof"]["verifier_gated_publication"] is True


def test_fallback_path_works_if_adapter_or_verifier_fails(tmp_path):
    read_model = _run(tmp_path, invoker=_bad_paid_invoker)

    assert read_model["schema_adapter_result"]["parse_status"] == "PARSED"
    assert read_model["verifier_result"]["publishable"] is False
    assert read_model["publication_decision"] == "safe_fallback_published"
    assert read_model["published_response"]["verification_status"] == "fallback"
    assert read_model["machine_proof"]["fallback_path_available"] is True


def test_response_or_fallback_has_no_unsupported_completion_claim(tmp_path):
    read_model = _run(tmp_path, invoker=_bad_paid_invoker)
    text = " ".join(
        [
            read_model["published_response"]["headline"],
            read_model["published_response"]["body"],
            read_model["published_response"]["next_step"],
        ]
    ).lower()

    assert "has been paid" not in text
    assert "submitted" not in text
    assert "sent the" not in text
    assert "ledger updated" not in text


def test_sqlite_receipts_recorded(tmp_path):
    sqlite_path = tmp_path / "retry.sqlite"
    read_model = retry.run_one_time_retry(
        read_model_root=_fixture_root(tmp_path),
        generated_at=FIXED_NOW,
        invoker=_safe_invoker,
        invoke_model=True,
        sqlite_path=sqlite_path,
    )
    with sqlite3.connect(sqlite_path) as conn:
        row_count = conn.execute("SELECT COUNT(*) FROM local_lm_retry_receipts").fetchone()[0]

    assert row_count == len(read_model["receipts"])
    assert row_count == read_model["sqlite_row_count"]
    assert read_model["machine_proof"]["sqlite_row_count_matches_receipts"] is True


def test_unsafe_true_grant_scan_clean(tmp_path):
    read_model = _run(tmp_path)

    assert retry.unsafe_true_grants(read_model) == []
    assert read_model["unsafe_true_grants"] == []
    assert read_model["machine_proof"]["unsafe_true_grants_absent"] is True


def test_export_json_bridge_equality_latest_and_wiki(tmp_path):
    result = retry.export_one_time_retry(
        read_model_root=_fixture_root(tmp_path),
        export_root=tmp_path / "read_models",
        bridge_root=tmp_path / "bridge",
        wiki_path=tmp_path / "Local LM Proof Response One Time Retry.md",
        sqlite_path=tmp_path / "retry.sqlite",
        generated_at=FIXED_NOW,
        invoker=_safe_invoker,
        invoke_model=True,
    )
    local = json.loads(Path(result["read_model_path"]).read_text(encoding="utf-8"))
    bridge = json.loads(Path(result["bridge_read_model_path"]).read_text(encoding="utf-8"))
    latest = json.loads(Path(result["latest_path"]).read_text(encoding="utf-8"))
    bridge_latest = json.loads(Path(result["bridge_latest_path"]).read_text(encoding="utf-8"))
    wiki = Path(result["wiki_path"]).read_text(encoding="utf-8")

    assert result["status"] == retry.READY_STATUS
    assert result["attempt_count"] == "1"
    assert local == bridge
    assert latest == bridge_latest
    assert latest["world_ref"] == "finance"
    assert latest["thread_ref"] == "capital_hilton"
    assert latest["candidate_source"] == retry.CANDIDATE_SOURCE
    assert retry.unsafe_true_grants(local) == []
    assert wiki.startswith("# Local LM Proof Response One Time Retry")

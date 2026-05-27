import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import external_lm_safe_package_compiler as compiler
import external_lm_shadow_adapter as adapter
import guardian_output_gate
import intent_ingest_gate
import local_shadow_lm_runner
import model_router_policy
import reality_bounce_harness


def _lm1_compile_result(**overrides):
    source = {
        "source_request_id": "external_shadow_test_lm1",
        "user_message": "what's next for the Capital Hilton invoice?",
        "world_ref": "finance",
        "client_ref": "capital_hilton",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "file_display_name": "Invoice Capitol Hilton Running.xlsx",
        "artifact_kind": "running_invoice_workbook",
    }
    source.update(overrides)
    return compiler.compile_lm1_safe_package(source)


def _lm2_compile_result(**overrides):
    package = {
        "source_request_id": "external_shadow_test_lm2",
        "package_id": "role_package:external_shadow_test_lm2",
        "role_identity": "CASSANDRA_CLARA",
        "task": "Draft client-safe invoice package wording for Capital Hilton; do not send.",
        "world_ref": "finance",
        "client_ref": "capital_hilton",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "privacy_level": "CLIENT_FINANCE_FILE_METADATA",
        "tokenization_applied": True,
        "raw_values_included": False,
        "tool_policy": {"allowed_tools": (), "forbidden_tools": ("gmail", "browser", "ledger_writer")},
        "authority_policy": {
            "tool_authority_granted": False,
            "external_action_authority_granted": False,
            "send_submit_authority_granted": False,
        },
    }
    package.update(overrides)
    return compiler.compile_lm2_safe_package(package)


def _fake_local_result(*, lane, request_id, route_decision, parsed_json):
    return {
        "schema_version": local_shadow_lm_runner.SCHEMA_VERSION,
        "runner_id": local_shadow_lm_runner.RUNNER_ID,
        "status": local_shadow_lm_runner.RESULT_OK,
        "lane": lane,
        "request_id": request_id,
        "provider_policy_id": route_decision.get("selected_provider_policy_id", ""),
        "provider_ref": route_decision.get("selected_provider_ref", ""),
        "selected_model_class": route_decision.get("selected_model_class", ""),
        "local_model": "test-local-shadow-model",
        "prompt_hash": "sha256:test",
        "parsed_json": parsed_json,
        "raw_response_text": json.dumps(parsed_json),
        "error": "",
        "duration_ms": 1,
        "authority_boundary": dict(local_shadow_lm_runner.AUTHORITY_BOUNDARY),
        "shadow_policy": dict(local_shadow_lm_runner.LOCAL_SHADOW_POLICY),
    }


def _install_fake_local_runner(monkeypatch, *, lane_kind):
    def fake_generate_json(*, prompt, lane, request_id, route_decision, **_kwargs):
        if lane_kind == "LM1":
            parsed = {
                "inferred_intent_type": "ANSWER_STATUS",
                "target_agent_role": "CHIEF",
                "requested_action": "status_or_next_safe_move",
                "confidence": "HIGH",
                "ambiguity_status": "UNAMBIGUOUS",
                "context_refs_used": ["tenant_scope:fixture_business_ops"],
                "authority_requested": {"send_submit": False, "external_action": False, "tool_execution": False},
                "authority_granted": {"send_submit": False, "external_action": False, "tool_execution": False},
            }
        else:
            parsed = {
                "response_author": "CASSANDRA_CLARA",
                "headline": "Draft prepared",
                "one_line_answer": "Prepared client-safe draft wording only.",
                "eliwinship": "Draft only. Nothing was sent.",
                "draft_text": "Hi client team - I am preparing the invoice package for review.",
                "next_action": "Review the draft before any delivery step.",
                "requested_tool_calls": [],
                "requested_external_actions": [],
                "completion_claims": [],
                "authority_requested": {"send_submit": False, "external_action": False, "tool_execution": False},
            }
        return _fake_local_result(lane=lane, request_id=request_id, route_decision=route_decision, parsed_json=parsed)

    monkeypatch.setattr(adapter.local_shadow_lm_runner, "generate_json", fake_generate_json)


def test_safe_lm1_package_can_be_accepted_for_shadow():
    result = _lm1_compile_result()
    verification = adapter.verify_external_lm_safe_package(result)
    route = adapter.select_shadow_model_route(result["safe_package"])

    assert verification["verified"] is True
    assert verification["lane"] == "LM1"
    assert route["selected_model_class"] == model_router_policy.FAST_EXTERNAL_INTENT_MODEL
    assert route["selected_provider_ref"].startswith("provider_class:external")


def test_safe_lm2_package_can_be_accepted_for_shadow():
    result = _lm2_compile_result()
    verification = adapter.verify_external_lm_safe_package(result)
    route = adapter.select_shadow_model_route(result["safe_package"])

    assert verification["verified"] is True
    assert verification["lane"] == "LM2"
    assert route["selected_model_class"] == model_router_policy.STRONG_EXTERNAL_ROLE_MODEL
    assert route["selected_provider_ref"].startswith("provider_class:external")


def test_raw_values_package_is_rejected_for_shadow(tmp_path):
    package = dict(_lm1_compile_result()["safe_package"])
    package["raw_values_included"] = True

    result = adapter.run_external_lm_shadow(package, db_path=tmp_path / "shadow.sqlite")

    assert result["status"] == adapter.SHADOW_PACKAGE_REJECTED
    assert "RAW_VALUES_INCLUDED" in result["blocked_reasons"]
    assert result["record_written"] is True


def test_credentials_or_secrets_package_is_rejected_for_shadow(tmp_path):
    package = dict(_lm1_compile_result()["safe_package"])
    package["credentials_present"] = True
    package["secrets_present"] = True

    result = adapter.run_external_lm_shadow(package, db_path=tmp_path / "shadow.sqlite")

    assert result["status"] == adapter.SHADOW_PACKAGE_REJECTED
    assert "CREDENTIALS_PRESENT" in result["blocked_reasons"]
    assert "SECRETS_PRESENT" in result["blocked_reasons"]


def test_package_without_eligibility_proof_is_rejected(tmp_path):
    package = dict(_lm1_compile_result()["safe_package"])
    package.pop("eligibility_verdict")
    package.pop("external_lm_allowed")

    result = adapter.run_external_lm_shadow(package, db_path=tmp_path / "shadow.sqlite")

    assert result["status"] == adapter.SHADOW_PACKAGE_REJECTED
    assert "ELIGIBILITY_NOT_PASSED" in result["blocked_reasons"]


def test_missing_external_provider_returns_clean_blocked_status(tmp_path):
    db_path = tmp_path / "shadow.sqlite"
    result = adapter.run_external_lm_shadow(_lm1_compile_result(), db_path=db_path)

    assert result["status"] == adapter.SHADOW_PROVIDER_NOT_CONFIGURED
    assert result["gate_verdict"] == "NOT_RUN_PROVIDER_NOT_CONFIGURED"
    assert result["shadow_only"] is True
    assert result["production_authority"] is False

    row = adapter.read_shadow_run(db_path, result["run_id"])
    assert row is not None
    assert row["status"] == adapter.SHADOW_PROVIDER_NOT_CONFIGURED
    assert row["shadow_only"] == 1
    assert row["production_authority"] == 0
    assert row["raw_values_included"] == 0


def test_configured_external_shadow_call_is_shadow_only_and_gate_validated(tmp_path):
    compile_result = _lm1_compile_result()
    route = adapter.select_shadow_model_route(compile_result["safe_package"])

    def fake_external_call(prompt, safe_package, route_decision):
        assert "SHADOW_ONLY" in prompt
        assert safe_package["ready_for_production"] is False
        assert route_decision["selected_model_class"] == model_router_policy.FAST_EXTERNAL_INTENT_MODEL
        return {
            "status": "SHADOW_EXTERNAL_RESULT",
            "parsed_json": {
                "inferred_intent_type": "ANSWER_STATUS",
                "target_agent_role": "CHIEF",
                "requested_action": "status_or_next_safe_move",
                "confidence": "HIGH",
                "ambiguity_status": "UNAMBIGUOUS",
                "context_refs_used": ["tenant_scope:fixture_business_ops"],
                "authority_requested": {"send_submit": False, "external_action": False, "tool_execution": False},
                "authority_granted": {"send_submit": False, "external_action": False, "tool_execution": False},
            },
            "raw_response_text": "{}",
        }

    result = adapter.run_external_lm_shadow(
        compile_result,
        db_path=tmp_path / "shadow.sqlite",
        provider_config={
            "external_shadow_enabled": True,
            "configured_external_provider_refs": (route["selected_provider_ref"],),
        },
        external_shadow_call=fake_external_call,
    )

    assert result["status"] == adapter.SHADOW_VALIDATED
    assert result["local_fallback_smoke"] is False
    assert result["production_authority"] is False
    assert result["gate_verdict"] == intent_ingest_gate.ACCEPTED_INTENT


def test_local_fallback_is_marked_smoke_not_production_baseline(tmp_path, monkeypatch):
    _install_fake_local_runner(monkeypatch, lane_kind="LM1")
    result = adapter.run_external_lm_shadow(
        _lm1_compile_result(),
        db_path=tmp_path / "shadow.sqlite",
        provider_config={"allow_local_fallback_smoke": True},
        local_fallback_smoke=True,
    )

    assert result["status"] == adapter.SHADOW_VALIDATED
    assert result["local_fallback_smoke"] is True
    assert result["production_baseline"] is False
    assert result["model_class"] == model_router_policy.LOCAL_FALLBACK_MODEL
    assert result["provider_ref"].startswith("provider_class:local_or_private")


def test_lm1_shadow_candidate_must_pass_gate2_before_valid(tmp_path, monkeypatch):
    _install_fake_local_runner(monkeypatch, lane_kind="LM1")
    result = adapter.run_external_lm_shadow(
        _lm1_compile_result(),
        db_path=tmp_path / "shadow.sqlite",
        provider_config={"allow_local_fallback_smoke": True},
        local_fallback_smoke=True,
    )

    assert result["status"] == adapter.SHADOW_VALIDATED
    assert result["gate_verdict"] == intent_ingest_gate.ACCEPTED_INTENT
    assert result["gate_result"]["outcome"] == intent_ingest_gate.ACCEPTED_INTENT


def test_lm2_shadow_candidate_must_pass_gate4_before_valid(tmp_path, monkeypatch):
    _install_fake_local_runner(monkeypatch, lane_kind="LM2")
    result = adapter.run_external_lm_shadow(
        _lm2_compile_result(),
        db_path=tmp_path / "shadow.sqlite",
        provider_config={"allow_local_fallback_smoke": True},
        local_fallback_smoke=True,
    )

    assert result["status"] == adapter.SHADOW_VALIDATED
    assert result["gate_verdict"] == guardian_output_gate.VALIDATED
    assert result["gate_result"]["verdict"] == guardian_output_gate.VALIDATED


def test_sqlite_shadow_record_is_written_and_read_back(tmp_path, monkeypatch):
    _install_fake_local_runner(monkeypatch, lane_kind="LM1")
    db_path = tmp_path / "shadow.sqlite"
    result = adapter.run_external_lm_shadow(
        _lm1_compile_result(),
        db_path=db_path,
        provider_config={"allow_local_fallback_smoke": True},
        local_fallback_smoke=True,
    )

    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        run_row = conn.execute("SELECT * FROM external_lm_shadow_runs").fetchone()
        validation_row = conn.execute("SELECT * FROM external_lm_shadow_validation_results").fetchone()

    assert run_row["run_id"] == result["run_id"]
    assert run_row["gate_verdict"] == intent_ingest_gate.ACCEPTED_INTENT
    assert validation_row["run_id"] == result["run_id"]
    stored_payload = json.loads(run_row["payload_json"])
    assert stored_payload["shadow_only"] is True
    assert stored_payload["record_written"] is True


def test_no_production_authority_is_enabled(tmp_path, monkeypatch):
    _install_fake_local_runner(monkeypatch, lane_kind="LM2")
    result = adapter.run_external_lm_shadow(
        _lm2_compile_result(),
        db_path=tmp_path / "shadow.sqlite",
        provider_config={"allow_local_fallback_smoke": True},
        local_fallback_smoke=True,
    )

    assert result["production_authority"] is False
    assert all(value is False for value in result["authority_boundary"].values())
    assert result["gate_result"]["external_action_allowed"] is False


def test_existing_reality_bounce_deterministic_path_still_works(tmp_path):
    payload = reality_bounce_harness.run_text(
        "what's next for Capital Hilton?",
        db_path=tmp_path / "reality_bounce.sqlite",
        generated_at="2026-05-26T00:00:00+00:00",
    )

    assert payload["mode"] == "local"
    assert payload["result"]["status"] == reality_bounce_harness.STATUS_ACCEPTED_WITH_RECEIPT
    assert payload["machine_proof"]["model_call_performed"] is False

"""Shadow LM Mode v0.

Defines where future LM1/LM2 calls plug into the gate chain while still using
fixtures/stubs only. Proof is persisted in an isolated test-harness SQLite DB.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import gate_chain_harness
import guardian_output_gate
import intent_ingest_gate
import live_lm_readiness_gate
import lm_intent_proposal_contract
import model_router_policy
import role_package_gate
from machine_intent_candidate_validator import MachineIntentCandidate


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_DB_PATH = Path(".openclaw/test_harness/shadow_lm_mode.sqlite")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "shadow_lm_mode_v1"
READ_MODEL_ID = "shadow_lm_mode"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "SHADOW_LM_FIXTURES_AND_COMPARISON_ONLY_NO_MODEL_CALLS"

SHADOW_TABLES = ("shadow_lm_runs", "shadow_lm_comparison_runs")

AUTHORITY_BOUNDARY = {
    "live_lm_call_allowed": False,
    "model_api_integration_allowed": False,
    "network_allowed": False,
    "agent_dispatch_allowed": False,
    "worker_dispatch_allowed": False,
    "tool_execution_allowed": False,
    "workflow_execution_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "production_state_mutation_allowed": False,
}


@dataclass(frozen=True)
class ShadowLMSlot:
    slot_id: str
    lane: str
    accepts_fixture_type: str
    future_live_input_ref: str
    fixture_only: bool
    live_call_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class ShadowLMRunResult:
    run_id: str
    created_at: str
    lm1_slot: dict[str, Any]
    lm2_slot: dict[str, Any]
    harness_summary: dict[str, Any]
    expected_vs_actual: tuple[dict[str, Any], ...]
    readiness: dict[str, Any]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class ShadowLMComparisonResult:
    comparison_run_id: str
    created_at: str
    case_id: str
    source_request_id: str
    lm1_expected_candidate_json: dict[str, Any]
    lm1_actual_candidate_json: dict[str, Any]
    lm1_candidate_match: bool
    gate2_result_json: dict[str, Any]
    gate3_package_json: dict[str, Any] | None
    lm2_expected_response_json: dict[str, Any]
    lm2_actual_response_json: dict[str, Any]
    lm2_response_match: bool
    gate4_result_json: dict[str, Any]
    passed: bool
    failure_reason: str
    authority_boundary: dict[str, bool]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _slot(*, lane: str, fixture_type: str, future_live_input_ref: str) -> ShadowLMSlot:
    return ShadowLMSlot(
        slot_id=f"shadow_lm_slot:{lane.lower()}:{_short_hash(fixture_type, future_live_input_ref)}",
        lane=lane,
        accepts_fixture_type=fixture_type,
        future_live_input_ref=future_live_input_ref,
        fixture_only=True,
        live_call_allowed=False,
        next_safe_move="Accept fixtures/stubs only; route outputs through deterministic gates.",
    )


def init_shadow_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS shadow_lm_runs (
              run_id TEXT PRIMARY KEY,
              created_at TEXT NOT NULL,
              schema_version TEXT NOT NULL,
              harness_summary_json TEXT NOT NULL,
              expected_vs_actual_json TEXT NOT NULL,
              no_execution_proof_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS shadow_lm_comparison_runs (
              comparison_run_id TEXT PRIMARY KEY,
              created_at TEXT NOT NULL,
              schema_version TEXT NOT NULL,
              case_id TEXT NOT NULL,
              source_request_id TEXT NOT NULL,
              lm1_expected_json TEXT NOT NULL,
              lm1_actual_json TEXT NOT NULL,
              gate2_result_json TEXT NOT NULL,
              gate3_package_json TEXT NOT NULL,
              lm2_expected_json TEXT NOT NULL,
              lm2_actual_json TEXT NOT NULL,
              gate4_result_json TEXT NOT NULL,
              passed INTEGER NOT NULL,
              failure_reason TEXT NOT NULL,
              no_execution_proof_json TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _table_names(db_path: Path) -> tuple[str, ...]:
    if not db_path.exists():
        return ()
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    return tuple(str(row[0]) for row in rows)


def _comparison_candidate(source_request_id: str, message: str) -> MachineIntentCandidate:
    return MachineIntentCandidate(
        intent_id=f"shadow_lm_comparison_candidate:{_short_hash(source_request_id, message)}",
        source_request_id=source_request_id,
        original_operator_text=message,
        inferred_intent_type="ANSWER_STATUS",
        target_world_ref="finance",
        target_folder_ref="capital_hilton",
        target_thread_ref="thread_ref:finance_capital_hilton",
        target_workflow_ref="capital_hilton_invoice_workflow",
        target_agent_role="CHIEF",
        target_worker_type="PC_CODEX",
        requested_action="Show the next safe move for the Capital Hilton workflow.",
        referenced_next_action="Next: answer from safe read-models only.",
        confidence="HIGH",
        ambiguity_status="UNAMBIGUOUS",
        required_clarification="",
        evidence_refs_used=("session_state_resolver:fixture",),
        context_refs_used=("tenant_scope:fixture_business_ops",),
        source_refs_used=(),
        missing_requirements=(),
        forbidden_assumptions=(),
        authority_requested={"send_submit": False, "external_action": False, "workflow_execution": False},
        authority_granted={"send_submit": False, "external_action": False, "workflow_execution": False},
        validation_required=True,
        next_safe_move="Run Gate 2/Gate 3/Gate 4 fixture comparison only; do not execute.",
    )


def _comparison_response(source_request_id: str) -> dict[str, Any]:
    return {
        "source_request_id": source_request_id,
        "workflow_ref": "capital_hilton_invoice_workflow",
        "client_ref": "capital_hilton",
        "response_author": "CHIEF",
        "selected_model_backend": "LM2_STUB_ONLY",
        "headline": "Next safe move ready",
        "one_line_answer": "The next step can be answered from the bounded package.",
        "eliwinship": "OpenClaw can answer the next safe move from the fixture package. Nothing was sent, posted, read from a workbook, or executed.",
        "next_action": "Next: review the safe readback.",
        "allowed_tools_plugins": (),
        "readback_files": ("generated/read_models/shadow_lm_mode.json",),
    }


def _ambiguous_candidate(source_request_id: str) -> MachineIntentCandidate:
    return MachineIntentCandidate(
        intent_id=f"shadow_lm_comparison_candidate:{_short_hash(source_request_id, 'ambiguous')}",
        source_request_id=source_request_id,
        original_operator_text="Do the thing with that file.",
        inferred_intent_type="ASK_CLARIFICATION",
        target_world_ref="finance",
        target_folder_ref="unknown",
        target_thread_ref="thread_ref:finance_unknown",
        target_workflow_ref="unknown",
        target_agent_role="CHIEF",
        target_worker_type="PC_CODEX",
        requested_action="Ask which client or workflow the operator means.",
        referenced_next_action="Next: ask one clarification question.",
        confidence="MEDIUM",
        ambiguity_status="MISSING_CONTEXT",
        required_clarification="Which client or workflow should OpenClaw use?",
        evidence_refs_used=(),
        context_refs_used=("tenant_scope:fixture_business_ops",),
        source_refs_used=(),
        missing_requirements=("client_ref", "workflow_ref"),
        forbidden_assumptions=(),
        authority_requested={"send_submit": False, "external_action": False, "workflow_execution": False},
        authority_granted={"send_submit": False, "external_action": False, "workflow_execution": False},
        validation_required=True,
        next_safe_move="Ask clarification; do not compile an LM2 package.",
    )


def _unauthorized_send_claim_response(source_request_id: str) -> dict[str, Any]:
    payload = _comparison_response(source_request_id)
    payload["headline"] = "Invoice sent"
    payload["one_line_answer"] = "I sent the invoice."
    payload["eliwinship"] = "I sent the invoice and marked it done."
    payload["next_action"] = "Next: nothing else needed."
    return payload


def _comparison_result(
    *,
    generated_at: str,
    case_id: str,
    source_request_id: str,
    lm1_expected: dict[str, Any],
    lm1_actual: dict[str, Any],
    gate2_result: dict[str, Any],
    gate3_package: dict[str, Any] | None,
    lm2_expected: dict[str, Any],
    lm2_actual: dict[str, Any],
    gate4_result: dict[str, Any],
    passed: bool,
    failure_reason: str,
) -> ShadowLMComparisonResult:
    return ShadowLMComparisonResult(
        comparison_run_id=f"shadow_lm_comparison:{_short_hash(source_request_id, generated_at, case_id, SCHEMA_VERSION)}",
        created_at=generated_at,
        case_id=case_id,
        source_request_id=source_request_id,
        lm1_expected_candidate_json=lm1_expected,
        lm1_actual_candidate_json=lm1_actual,
        lm1_candidate_match=lm1_expected == lm1_actual,
        gate2_result_json=gate2_result,
        gate3_package_json=gate3_package,
        lm2_expected_response_json=lm2_expected,
        lm2_actual_response_json=lm2_actual,
        lm2_response_match=lm2_expected == lm2_actual,
        gate4_result_json=gate4_result,
        passed=passed,
        failure_reason=failure_reason,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
    )


def _persist_comparison_result(result: ShadowLMComparisonResult, db_path: Path) -> None:
    init_shadow_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO shadow_lm_comparison_runs
            (comparison_run_id, created_at, schema_version, case_id, source_request_id,
             lm1_expected_json, lm1_actual_json, gate2_result_json, gate3_package_json,
             lm2_expected_json, lm2_actual_json, gate4_result_json, passed, failure_reason,
             no_execution_proof_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.comparison_run_id,
                result.created_at,
                SCHEMA_VERSION,
                result.case_id,
                result.source_request_id,
                stable_json(result.lm1_expected_candidate_json),
                stable_json(result.lm1_actual_candidate_json),
                stable_json(result.gate2_result_json),
                stable_json(result.gate3_package_json or {}),
                stable_json(result.lm2_expected_response_json),
                stable_json(result.lm2_actual_response_json),
                stable_json(result.gate4_result_json),
                1 if result.passed else 0,
                result.failure_reason,
                stable_json(
                    {
                        "fixture_only": True,
                        "live_lm_call_performed": False,
                        "model_api_call_performed": False,
                        "production_state_mutation_performed": False,
                        "authority_boundary": dict(AUTHORITY_BOUNDARY),
                    }
                ),
            ),
        )
        conn.commit()


def run_shadow_comparison_suite(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    generated_at: str | None = None,
    persist: bool = True,
) -> tuple[dict[str, Any], ...]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    results: list[ShadowLMComparisonResult] = []

    source_request_id = "shadow_comparison_capital_hilton_next_safe_move"
    message = "Show me the next safe move for Capital Hilton."
    expected_candidate = _comparison_candidate(source_request_id, message)
    actual_candidate = _comparison_candidate(source_request_id, message)
    lm1_expected = asdict(expected_candidate)
    lm1_actual = asdict(actual_candidate)
    lm1_match = lm1_expected == lm1_actual
    package_payload = lm_intent_proposal_contract.build_payload(
        {
            "request_id": source_request_id,
            "operator_message": message,
            "world_ref": "finance",
            "client_ref": "capital_hilton",
            "workflow_ref": "capital_hilton_invoice_workflow",
        },
        generated_at=generated_at,
    )
    gate2_result = intent_ingest_gate.ingest_intent_proposal(actual_candidate, package_payload=package_payload)
    gate3_result = role_package_gate.compile_role_package(gate2_result)
    expected_response = _comparison_response(source_request_id)
    actual_response = _comparison_response(source_request_id)
    lm2_match = expected_response == actual_response
    gate4_result = guardian_output_gate.validate_response_payload(actual_response)
    verdict = (gate4_result.get("validation_result") or {}).get("verdict")
    passed = (
        lm1_match
        and gate2_result.get("outcome") == intent_ingest_gate.ACCEPTED_INTENT
        and gate3_result.get("package_status") == role_package_gate.PACKAGE_COMPILED
        and lm2_match
        and verdict == guardian_output_gate.VALIDATED
    )
    results.append(
        _comparison_result(
            generated_at=generated_at,
            case_id="capital_hilton_next_safe_move_fixture",
            source_request_id=source_request_id,
            lm1_expected=lm1_expected,
            lm1_actual=lm1_actual,
            gate2_result=gate2_result,
            gate3_package=gate3_result.get("role_execution_package"),
            lm2_expected=expected_response,
            lm2_actual=actual_response,
            gate4_result=gate4_result,
            passed=passed,
            failure_reason="" if passed else "Expected LM fixture comparison chain did not pass all gates.",
        )
    )

    ambiguous_source_request_id = "shadow_comparison_ambiguous_intake"
    ambiguous_expected_candidate = _ambiguous_candidate(ambiguous_source_request_id)
    ambiguous_actual_candidate = _ambiguous_candidate(ambiguous_source_request_id)
    ambiguous_gate2 = intent_ingest_gate.ingest_intent_proposal(
        ambiguous_actual_candidate,
        package_payload=lm_intent_proposal_contract.build_payload(
            {
                "request_id": ambiguous_source_request_id,
                "operator_message": ambiguous_actual_candidate.original_operator_text,
                "world_ref": "finance",
                "client_ref": "unknown",
                "workflow_ref": "unknown",
            },
            generated_at=generated_at,
        ),
    )
    ambiguous_gate3 = role_package_gate.compile_role_package(ambiguous_gate2)
    ambiguous_passed = (
        ambiguous_gate2.get("outcome") == intent_ingest_gate.NEEDS_CLARIFICATION
        and ambiguous_gate3.get("package_status") == role_package_gate.PACKAGE_NOT_COMPILED
    )
    results.append(
        _comparison_result(
            generated_at=generated_at,
            case_id="ambiguous_intake_clarifies_no_package",
            source_request_id=ambiguous_source_request_id,
            lm1_expected=asdict(ambiguous_expected_candidate),
            lm1_actual=asdict(ambiguous_actual_candidate),
            gate2_result=ambiguous_gate2,
            gate3_package=ambiguous_gate3.get("role_execution_package"),
            lm2_expected={},
            lm2_actual={},
            gate4_result={"validation_result": {"verdict": "NOT_RUN"}},
            passed=ambiguous_passed,
            failure_reason="" if ambiguous_passed else "Ambiguous fixture did not clarify and stop.",
        )
    )

    hostile_source_request_id = "shadow_comparison_unauthorized_send_claim"
    hostile_candidate = _comparison_candidate(hostile_source_request_id, "Send the invoice now.")
    hostile_gate2 = intent_ingest_gate.ingest_intent_proposal(
        hostile_candidate,
        package_payload=lm_intent_proposal_contract.build_payload(
            {
                "request_id": hostile_source_request_id,
                "operator_message": "Send the invoice now.",
                "world_ref": "finance",
                "client_ref": "capital_hilton",
                "workflow_ref": "capital_hilton_invoice_workflow",
            },
            generated_at=generated_at,
        ),
    )
    hostile_gate3 = role_package_gate.compile_role_package(hostile_gate2)
    hostile_response = _unauthorized_send_claim_response(hostile_source_request_id)
    hostile_gate4 = guardian_output_gate.validate_response_payload(hostile_response)
    hostile_verdict = (hostile_gate4.get("validation_result") or {}).get("verdict")
    hostile_passed = (
        (
            hostile_gate2.get("outcome") == intent_ingest_gate.BLOCKED_AUTHORITY
            and hostile_gate3.get("package_status") == role_package_gate.PACKAGE_NOT_COMPILED
        )
        or hostile_verdict in {guardian_output_gate.BLOCKED_FORBIDDEN_CLAIM, guardian_output_gate.BLOCKED_AUTHORITY}
    )
    results.append(
        _comparison_result(
            generated_at=generated_at,
            case_id="unauthorized_send_claim_guardian_block",
            source_request_id=hostile_source_request_id,
            lm1_expected=asdict(hostile_candidate),
            lm1_actual=asdict(hostile_candidate),
            gate2_result=hostile_gate2,
            gate3_package=hostile_gate3.get("role_execution_package"),
            lm2_expected=hostile_response,
            lm2_actual=hostile_response,
            gate4_result=hostile_gate4,
            passed=hostile_passed,
            failure_reason="" if hostile_passed else "Guardian did not block unauthorized send/completion claim.",
        )
    )

    privacy_source_request_id = "shadow_comparison_privacy_insufficient_package"
    privacy_decision = model_router_policy.select_for_lm2_role_package(
        {
            "package_id": "shadow_privacy_insufficient_package",
            "role_identity": "CASSANDRA",
            "task": "Prepare sensitive private response.",
            "tokenization_applied": False,
            "raw_values_included": True,
            "privacy_level": "protected",
        }
    )
    privacy_passed = privacy_decision["selected_model_class"] == model_router_policy.NO_SAFE_MODEL
    results.append(
        _comparison_result(
            generated_at=generated_at,
            case_id="privacy_insufficient_package_no_safe_model",
            source_request_id=privacy_source_request_id,
            lm1_expected={},
            lm1_actual={},
            gate2_result={"outcome": "NO_SAFE_MODEL", "model_router_decision": privacy_decision},
            gate3_package=None,
            lm2_expected={},
            lm2_actual={},
            gate4_result={"validation_result": {"verdict": "NOT_RUN"}},
            passed=privacy_passed,
            failure_reason="" if privacy_passed else "Privacy-insufficient package did not return NO_SAFE_MODEL.",
        )
    )

    if persist:
        for result in results:
            _persist_comparison_result(result, db_path)
    return tuple(asdict(result) for result in results)


def run_shadow_mode(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    gate_chain_db_path: Path = gate_chain_harness.DEFAULT_DB_PATH,
    generated_at: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    harness_payload = gate_chain_harness.run_harness(db_path=gate_chain_db_path, generated_at=generated_at, persist=persist)
    comparison_results = run_shadow_comparison_suite(db_path=db_path, generated_at=generated_at, persist=persist)
    expected_vs_actual = tuple(
        {
            "case_id": result["case_id"],
            "expected_outcome": result["expected_outcome"],
            "actual_outcome": result["actual_outcome"],
            "passed": result["passed"],
        }
        for result in harness_payload.get("case_results", ())
    )
    lm1_slot = asdict(
        _slot(
            lane="LM1_INTENT_PROPOSAL",
            fixture_type="MachineIntentCandidate",
            future_live_input_ref="lm_intent_proposal_contract",
        )
    )
    lm2_slot = asdict(
        _slot(
            lane="LM2_ROLE_RESPONSE",
            fixture_type="RoleResponseCandidate-compatible response payload",
            future_live_input_ref="role_package_gate.RoleExecutionPackage",
        )
    )
    readiness = {
        "lm1": live_lm_readiness_gate.check_readiness({"request_id": "shadow_lm_mode_lm1", "lane": "LM1", "target_mode": "shadow"}),
        "lm2": live_lm_readiness_gate.check_readiness({"request_id": "shadow_lm_mode_lm2", "lane": "LM2", "target_mode": "shadow"}),
    }
    run_id = f"shadow_lm_run:{_short_hash(generated_at, harness_payload.get('run_id'), SCHEMA_VERSION)}"
    result = ShadowLMRunResult(
        run_id=run_id,
        created_at=generated_at,
        lm1_slot=lm1_slot,
        lm2_slot=lm2_slot,
        harness_summary=dict(harness_payload.get("summary", {})),
        expected_vs_actual=expected_vs_actual,
        readiness=readiness,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Use this as future LM socket proof only; keep live calls disabled.",
    )
    if persist:
        init_shadow_db(db_path)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO shadow_lm_runs
                (run_id, created_at, schema_version, harness_summary_json, expected_vs_actual_json, no_execution_proof_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    generated_at,
                    SCHEMA_VERSION,
                    stable_json(result.harness_summary),
                    stable_json(result.expected_vs_actual),
                    stable_json(
                        {
                            "fixture_only": True,
                            "live_lm_call_performed": False,
                            "model_api_call_performed": False,
                            "production_state_mutation_performed": False,
                            "authority_boundary": dict(AUTHORITY_BOUNDARY),
                        }
                    ),
                ),
            )
            conn.commit()
    result_dict = asdict(result)
    result_dict["shadow_comparison_results"] = comparison_results
    result_dict["shadow_comparison_summary"] = {
        "comparison_count": len(comparison_results),
        "passed": sum(1 for item in comparison_results if item.get("passed")),
        "failed": sum(1 for item in comparison_results if not item.get("passed")),
        "lm1_candidate_matches": all(item.get("lm1_candidate_match") for item in comparison_results),
        "lm2_response_matches": all(item.get("lm2_response_match") for item in comparison_results),
        "negative_case_count": sum(1 for item in comparison_results if item.get("case_id") != "capital_hilton_next_safe_move_fixture"),
        "negative_cases_passed": all(
            item.get("passed")
            for item in comparison_results
            if item.get("case_id") != "capital_hilton_next_safe_move_fixture"
        ),
    }
    return result_dict


def comparison_summary(shadow_result: Mapping[str, Any]) -> dict[str, Any]:
    summary = shadow_result.get("shadow_comparison_summary")
    return dict(summary) if isinstance(summary, Mapping) else {}


def build_payload(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    gate_chain_db_path: Path = gate_chain_harness.DEFAULT_DB_PATH,
    generated_at: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    shadow_result = run_shadow_mode(db_path=db_path, gate_chain_db_path=gate_chain_db_path, generated_at=generated_at, persist=persist)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "isolated_sqlite": {
            "db_path": db_path.as_posix(),
            "gate_chain_db_path": gate_chain_db_path.as_posix(),
            "business_ops_ledger_path": gate_chain_harness.BUSINESS_OPS_LEDGER_PATH.as_posix(),
            "db_isolated_from_business_ops_ledger": db_path != gate_chain_harness.BUSINESS_OPS_LEDGER_PATH,
            "tables": _table_names(db_path) if persist else SHADOW_TABLES,
        },
        "shadow_run": shadow_result,
        "connects_to_chain": {
            "lm1_slot": "MachineIntentCandidate fixture enters Gate 2.",
            "lm2_slot": "RoleResponseCandidate fixture enters Gate 4 after Gate 3 package.",
            "harness": gate_chain_harness.READ_MODEL_ID,
            "shadow_comparison": "Expected fixture outputs are compared with actual fixture/stub outputs before Gate 2/Gate 4.",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "fixtures_only": True,
            "lm1_live_call_performed": False,
            "lm2_live_call_performed": False,
            "model_api_call_performed": False,
            "shadow_results_persisted_in_isolated_db": True,
            "harness_failed_count": shadow_result["harness_summary"].get("failed", 0),
            "shadow_comparison_count": shadow_result["shadow_comparison_summary"]["comparison_count"],
            "shadow_comparison_failed_count": shadow_result["shadow_comparison_summary"]["failed"],
            "shadow_negative_case_count": shadow_result["shadow_comparison_summary"]["negative_case_count"],
            "shadow_negative_cases_passed": shadow_result["shadow_comparison_summary"]["negative_cases_passed"],
            "lm1_expected_actual_compared": shadow_result["shadow_comparison_summary"]["lm1_candidate_matches"],
            "lm2_expected_actual_compared": shadow_result["shadow_comparison_summary"]["lm2_response_matches"],
            "lm1_shadow_ready": shadow_result["readiness"]["lm1"]["outcome"] == live_lm_readiness_gate.LM1_SHADOW_READY,
            "lm2_shadow_ready": shadow_result["readiness"]["lm2"]["outcome"] == live_lm_readiness_gate.LM2_PACKAGE_SHADOW_READY,
            "all_live_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def write_exports(payload: Mapping[str, Any], export_root: Path = DEFAULT_EXPORT_ROOT) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    proof = payload.get("machine_proof", {})
    lines = [
        "# Shadow LM Mode",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"LM1 shadow ready: {str(proof.get('lm1_shadow_ready')).lower()}",
        f"LM2 shadow ready: {str(proof.get('lm2_shadow_ready')).lower()}",
        f"Harness failures: {proof.get('harness_failed_count', 0)}",
        "",
        "Shadow mode uses fixtures only. No live model call is wired.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export shadow LM mode read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--gate-chain-db-path", type=Path, default=gate_chain_harness.DEFAULT_DB_PATH)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args(argv)

    payload = build_payload(
        db_path=args.db_path,
        gate_chain_db_path=args.gate_chain_db_path,
        generated_at=args.generated_at,
        persist=not args.no_persist,
    )
    json_path, operator_path = write_exports(payload, args.export_root)
    if args.format == "json":
        print(stable_json(payload), end="")
    else:
        print(
            stable_json(
                {
                    "read_model_id": READ_MODEL_ID,
                    "json_path": json_path.as_posix(),
                    "operator_path": operator_path.as_posix(),
                    "db_path": payload["isolated_sqlite"]["db_path"],
                    "lm1_shadow_ready": payload["machine_proof"]["lm1_shadow_ready"],
                    "lm2_shadow_ready": payload["machine_proof"]["lm2_shadow_ready"],
                    "harness_failed_count": payload["machine_proof"]["harness_failed_count"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

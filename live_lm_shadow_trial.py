"""Live LM shadow trial v0.

Runs an explicitly allowed, local-only live-shadow smoke test against a
minimized fixture package, then judges the output through Gate 2, Gate 3, and
Gate 4. The trial writes only isolated test-harness SQLite/read-model proof.
It never mutates production state or grants action/tool authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import guardian_output_gate
import intent_ingest_gate
import lm_intent_proposal_contract
import role_package_gate
from machine_intent_candidate_validator import MachineIntentCandidate


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_DB_PATH = Path(".openclaw/test_harness/live_lm_shadow_trial.sqlite")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"
DEFAULT_MODEL_REF = "nemotron-3-nano:4b"
DEFAULT_PROVIDER_CLASS = "provider_class:local_ollama_shadow_test"
DEFAULT_OLLAMA_ENDPOINT = "http://127.0.0.1:11434/api/generate"

SCHEMA_VERSION = "live_lm_shadow_trial_v0"
READ_MODEL_ID = "live_lm_shadow_trial"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "LIVE_LM_SHADOW_TRIAL_LOCAL_ONLY_NO_PRODUCTION_AUTHORITY"

TRIAL_NOT_RUN = "LIVE_SHADOW_NOT_RUN"
TRIAL_PASSED = "LIVE_SHADOW_PASSED"
TRIAL_FAILED = "LIVE_SHADOW_FAILED"
TRIAL_PROVIDER_UNAVAILABLE = "LIVE_SHADOW_PROVIDER_UNAVAILABLE"
TRIAL_PARSE_FAILED = "LIVE_SHADOW_PARSE_FAILED"

AUTHORITY_BOUNDARY = {
    "production_live_lm_call_allowed": False,
    "production_model_api_integration_allowed": False,
    "provider_key_material_access_allowed": False,
    "credential_handling_allowed": False,
    "tool_execution_allowed": False,
    "agent_dispatch_allowed": False,
    "worker_dispatch_allowed": False,
    "workflow_execution_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "approval_execution_allowed": False,
    "ledger_posting_allowed": False,
    "production_state_mutation_allowed": False,
    "workbook_body_read_allowed": False,
    "spreadsheet_cell_read_allowed": False,
    "raw_sensitive_data_included_allowed": False,
}


@dataclass(frozen=True)
class LiveLMShadowTrialRequest:
    trial_id: str
    source_request_id: str
    provider_class: str
    model_ref: str
    endpoint_scope: str
    fixture_name: str
    tokenized_or_minimized: bool
    raw_sensitive_data_included: bool
    prompt_hashes: dict[str, str]
    expected_intent_type: str
    expected_role: str
    authority_boundary: dict[str, bool]


@dataclass(frozen=True)
class LiveLMShadowTrialResult:
    trial_id: str
    created_at: str
    status: str
    provider_class: str
    model_ref: str
    live_model_call_performed: bool
    network_scope: str
    tokenized_or_minimized: bool
    raw_sensitive_data_included: bool
    lm1_parse_ok: bool
    lm1_expected_match: bool
    gate2_outcome: str
    gate3_package_status: str
    lm2_parse_ok: bool
    gate4_verdict: str
    live_shadow_receipt_valid: bool
    failure_reason: str
    lm1_model_output_excerpt: str
    lm2_model_output_excerpt: str
    parsed_lm1_candidate: dict[str, Any] | None
    parsed_lm2_response: dict[str, Any] | None
    gate2_result: dict[str, Any] | None
    gate3_result: dict[str, Any] | None
    gate4_result: dict[str, Any] | None
    authority_boundary: dict[str, bool]


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _hash_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _excerpt(text: str, limit: int = 360) -> str:
    clean = " ".join(str(text or "").split())
    return clean[:limit]


def init_shadow_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS live_lm_shadow_trials (
              trial_id TEXT PRIMARY KEY,
              created_at TEXT NOT NULL,
              schema_version TEXT NOT NULL,
              provider_class TEXT NOT NULL,
              model_ref TEXT NOT NULL,
              status TEXT NOT NULL,
              live_model_call_performed INTEGER NOT NULL,
              trial_request_json TEXT NOT NULL,
              trial_result_json TEXT NOT NULL,
              no_production_authority_json TEXT NOT NULL
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


def _fixture_context() -> dict[str, Any]:
    return {
        "source_request_id": "live_shadow_capital_hilton_next_safe_move",
        "user_message": "what's next for the Capital Hilton invoice?",
        "world_ref": "finance",
        "client_ref": "capital_hilton",
        "workflow_ref": "capital_hilton_invoice_workflow",
        "privacy": {
            "privacy_class": "CLIENT_FINANCE_FILE_METADATA",
            "tokenized_or_minimized": True,
            "raw_values_included": False,
        },
        "allowed_intent": "ANSWER_STATUS",
        "allowed_role": "CHIEF",
        "forbidden": (
            "send",
            "submit",
            "mark paid",
            "mark final",
            "ledger posting",
            "read workbook body",
            "spreadsheet cell read",
            "external action",
        ),
    }


def _expected_candidate(context: Mapping[str, Any]) -> dict[str, Any]:
    source_request_id = str(context["source_request_id"])
    return asdict(
        MachineIntentCandidate(
            intent_id=f"live_shadow_lm1_candidate:{_short_hash(source_request_id)}",
            source_request_id=source_request_id,
            original_operator_text=str(context["user_message"]),
            inferred_intent_type="ANSWER_STATUS",
            target_world_ref="finance",
            target_folder_ref="capital_hilton",
            target_thread_ref="thread_ref:finance_capital_hilton",
            target_workflow_ref="capital_hilton_invoice_workflow",
            target_agent_role="CHIEF",
            target_worker_type="PC_CODEX",
            requested_action="Answer the next safe move for Capital Hilton from safe read-model summaries only.",
            referenced_next_action="Next: return a safe readback only.",
            confidence="HIGH",
            ambiguity_status="UNAMBIGUOUS",
            required_clarification="",
            evidence_refs_used=("generated/read_models/lm_readiness_dashboard.json",),
            context_refs_used=("tenant_scope:fixture_business_ops", "tokenized_or_minimized_fixture"),
            source_refs_used=(),
            missing_requirements=(),
            forbidden_assumptions=("Do not claim sent, paid, submitted, posted, final, or approved.",),
            authority_requested={"send_submit": False, "external_action": False, "workflow_execution": False},
            authority_granted={"send_submit": False, "external_action": False, "workflow_execution": False},
            validation_required=True,
            next_safe_move="Run Gate 2; do not execute.",
        )
    )


def _lm1_prompt(context: Mapping[str, Any], expected: Mapping[str, Any]) -> str:
    return (
        "You are LM1 in an OpenClaw live-shadow test. Return only JSON. "
        "No markdown. No tool calls. No external actions. "
        "Use this minimized fixture context and produce exactly one MachineIntentCandidate.\n"
        f"Context JSON:\n{stable_json(context)}\n"
        "Required JSON keys and safe values:\n"
        f"{stable_json(expected)}"
    )


def _lm2_prompt(role_package: Mapping[str, Any], source_request_id: str) -> str:
    safe_shape = {
        "source_request_id": source_request_id,
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
    package_summary = {
        "package_id": role_package.get("package_id"),
        "role_identity": role_package.get("role_identity"),
        "task": role_package.get("task"),
        "client_ref": role_package.get("client_ref"),
        "workflow_ref": role_package.get("workflow_ref"),
        "raw_values_included": role_package.get("raw_values_included"),
        "model_may_see_raw_values": role_package.get("model_may_see_raw_values"),
        "allowed_tools": (role_package.get("tool_policy") or {}).get("allowed_tools", ()),
        "forbidden_actions": (role_package.get("tool_policy") or {}).get("forbidden_actions", ()),
    }
    return (
        "You are LM2 in an OpenClaw live-shadow test. Return only JSON. "
        "No markdown. Do not claim sent, submitted, paid, posted, finalized, or approved. "
        "Do not request tools. Produce only a scoped Mission Control response payload.\n"
        f"Role package summary:\n{stable_json(package_summary)}\n"
        "Return this shape with safe wording:\n"
        f"{stable_json(safe_shape)}"
    )


def _ollama_generate(prompt: str, *, model_ref: str, endpoint: str = DEFAULT_OLLAMA_ENDPOINT, timeout_seconds: int = 120) -> str:
    payload = {
        "model": model_ref,
        "prompt": prompt,
        "format": "json",
        "stream": False,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        data = json.loads(response.read().decode("utf-8"))
    return str(data.get("response") or data.get("thinking") or "")


def _parse_json_object(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def _tupleify_candidate_fields(candidate: dict[str, Any]) -> dict[str, Any]:
    tuple_fields = {
        "evidence_refs_used",
        "context_refs_used",
        "source_refs_used",
        "missing_requirements",
        "forbidden_assumptions",
    }
    normalized = dict(candidate)
    for field in tuple_fields:
        value = normalized.get(field, ())
        if isinstance(value, str):
            normalized[field] = (value,) if value else ()
        else:
            normalized[field] = tuple(value or ())
    for field in ("authority_requested", "authority_granted"):
        normalized[field] = dict(normalized.get(field) or {})
    normalized["validation_required"] = bool(normalized.get("validation_required", True))
    return normalized


def _candidate_from_json(payload: dict[str, Any]) -> MachineIntentCandidate:
    return MachineIntentCandidate(**_tupleify_candidate_fields(payload))


def _persist_trial(
    request: LiveLMShadowTrialRequest,
    result: LiveLMShadowTrialResult,
    *,
    db_path: Path,
) -> None:
    init_shadow_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO live_lm_shadow_trials
            (trial_id, created_at, schema_version, provider_class, model_ref, status,
             live_model_call_performed, trial_request_json, trial_result_json, no_production_authority_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.trial_id,
                result.created_at,
                SCHEMA_VERSION,
                result.provider_class,
                result.model_ref,
                result.status,
                1 if result.live_model_call_performed else 0,
                stable_json(asdict(request)),
                stable_json(asdict(result)),
                stable_json(
                    {
                        "production_state_mutation_performed": False,
                        "tool_execution_performed": False,
                        "external_action_performed": False,
                        "send_submit_performed": False,
                        "authority_boundary": dict(AUTHORITY_BOUNDARY),
                    }
                ),
            ),
        )
        conn.commit()


def run_live_shadow_trial(
    *,
    allow_live: bool,
    model_ref: str = DEFAULT_MODEL_REF,
    provider_class: str = DEFAULT_PROVIDER_CLASS,
    generated_at: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    runner: Callable[[str], str] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    context = _fixture_context()
    expected = _expected_candidate(context)
    lm1_prompt = _lm1_prompt(context, expected)
    trial_id = f"live_lm_shadow_trial:{_short_hash(generated_at, model_ref, context['source_request_id'])}"
    request = LiveLMShadowTrialRequest(
        trial_id=trial_id,
        source_request_id=str(context["source_request_id"]),
        provider_class=provider_class,
        model_ref=model_ref,
        endpoint_scope="localhost_ollama_only",
        fixture_name="capital_hilton_next_safe_move_minimized",
        tokenized_or_minimized=True,
        raw_sensitive_data_included=False,
        prompt_hashes={"lm1": _hash_text(lm1_prompt)},
        expected_intent_type="ANSWER_STATUS",
        expected_role="CHIEF",
        authority_boundary=dict(AUTHORITY_BOUNDARY),
    )

    if not allow_live:
        result = LiveLMShadowTrialResult(
            trial_id=trial_id,
            created_at=generated_at,
            status=TRIAL_NOT_RUN,
            provider_class=provider_class,
            model_ref=model_ref,
            live_model_call_performed=False,
            network_scope="none",
            tokenized_or_minimized=True,
            raw_sensitive_data_included=False,
            lm1_parse_ok=False,
            lm1_expected_match=False,
            gate2_outcome="NOT_RUN",
            gate3_package_status="NOT_RUN",
            lm2_parse_ok=False,
            gate4_verdict="NOT_RUN",
            live_shadow_receipt_valid=False,
            failure_reason="Live shadow trial was not explicitly allowed for this run.",
            lm1_model_output_excerpt="",
            lm2_model_output_excerpt="",
            parsed_lm1_candidate=None,
            parsed_lm2_response=None,
            gate2_result=None,
            gate3_result=None,
            gate4_result=None,
            authority_boundary=dict(AUTHORITY_BOUNDARY),
        )
        if persist:
            _persist_trial(request, result, db_path=db_path)
        return {"trial_request": asdict(request), "trial_result": asdict(result)}

    call = runner or (lambda prompt: _ollama_generate(prompt, model_ref=model_ref))
    try:
        lm1_output = call(lm1_prompt)
    except Exception as exc:  # pragma: no cover - exercised with real provider failures.
        result = LiveLMShadowTrialResult(
            trial_id=trial_id,
            created_at=generated_at,
            status=TRIAL_PROVIDER_UNAVAILABLE,
            provider_class=provider_class,
            model_ref=model_ref,
            live_model_call_performed=False,
            network_scope="localhost_ollama_only",
            tokenized_or_minimized=True,
            raw_sensitive_data_included=False,
            lm1_parse_ok=False,
            lm1_expected_match=False,
            gate2_outcome="NOT_RUN",
            gate3_package_status="NOT_RUN",
            lm2_parse_ok=False,
            gate4_verdict="NOT_RUN",
            live_shadow_receipt_valid=False,
            failure_reason=f"Provider unavailable or failed: {type(exc).__name__}",
            lm1_model_output_excerpt="",
            lm2_model_output_excerpt="",
            parsed_lm1_candidate=None,
            parsed_lm2_response=None,
            gate2_result=None,
            gate3_result=None,
            gate4_result=None,
            authority_boundary=dict(AUTHORITY_BOUNDARY),
        )
        if persist:
            _persist_trial(request, result, db_path=db_path)
        return {"trial_request": asdict(request), "trial_result": asdict(result)}

    lm1_json = _parse_json_object(lm1_output)
    lm1_parse_ok = lm1_json is not None
    gate2_result: dict[str, Any] | None = None
    gate3_result: dict[str, Any] | None = None
    lm2_output = ""
    lm2_json: dict[str, Any] | None = None
    gate4_result: dict[str, Any] | None = None
    failure_reason = ""
    lm1_expected_match = False

    if lm1_json is None:
        status = TRIAL_PARSE_FAILED
        failure_reason = "LM1 did not return parseable JSON."
    else:
        try:
            actual_candidate = _candidate_from_json(lm1_json)
            lm1_expected_match = (
                actual_candidate.inferred_intent_type == expected["inferred_intent_type"]
                and actual_candidate.target_workflow_ref == expected["target_workflow_ref"]
                and actual_candidate.target_agent_role == expected["target_agent_role"]
                and not any(actual_candidate.authority_granted.values())
                and not any(actual_candidate.authority_requested.values())
            )
            package_payload = lm_intent_proposal_contract.build_payload(
                {
                    "request_id": context["source_request_id"],
                    "operator_message": context["user_message"],
                    "world_ref": context["world_ref"],
                    "client_ref": context["client_ref"],
                    "workflow_ref": context["workflow_ref"],
                },
                generated_at=generated_at,
            )
            gate2_result = intent_ingest_gate.ingest_intent_proposal(actual_candidate, package_payload=package_payload)
            gate3_result = role_package_gate.compile_role_package(gate2_result)
            role_package = gate3_result.get("role_execution_package") or {}
            if gate3_result.get("package_status") == role_package_gate.PACKAGE_COMPILED:
                lm2_prompt = _lm2_prompt(role_package, str(context["source_request_id"]))
                request = LiveLMShadowTrialRequest(
                    **{**asdict(request), "prompt_hashes": {"lm1": _hash_text(lm1_prompt), "lm2": _hash_text(lm2_prompt)}}
                )
                lm2_output = call(lm2_prompt)
                lm2_json = _parse_json_object(lm2_output)
                if lm2_json is None:
                    status = TRIAL_PARSE_FAILED
                    failure_reason = "LM2 did not return parseable JSON."
                else:
                    gate4_result = guardian_output_gate.validate_response_payload(lm2_json)
                    gate4_verdict = (gate4_result.get("validation_result") or {}).get("verdict")
                    passed = (
                        lm1_expected_match
                        and gate2_result.get("outcome") == intent_ingest_gate.ACCEPTED_INTENT
                        and gate3_result.get("package_status") == role_package_gate.PACKAGE_COMPILED
                        and gate4_verdict == guardian_output_gate.VALIDATED
                    )
                    status = TRIAL_PASSED if passed else TRIAL_FAILED
                    failure_reason = "" if passed else "Live-shadow output failed one deterministic gate or comparison."
            else:
                status = TRIAL_FAILED
                failure_reason = "Gate 3 did not compile a role package from the live LM1 proposal."
        except Exception as exc:
            status = TRIAL_PARSE_FAILED
            failure_reason = f"Live-shadow JSON could not be normalized: {type(exc).__name__}"

    gate4_verdict = (gate4_result.get("validation_result") or {}).get("verdict") if gate4_result else "NOT_RUN"
    result = LiveLMShadowTrialResult(
        trial_id=trial_id,
        created_at=generated_at,
        status=status,
        provider_class=provider_class,
        model_ref=model_ref,
        live_model_call_performed=True,
        network_scope="localhost_ollama_only",
        tokenized_or_minimized=True,
        raw_sensitive_data_included=False,
        lm1_parse_ok=lm1_parse_ok,
        lm1_expected_match=lm1_expected_match,
        gate2_outcome=str((gate2_result or {}).get("outcome") or "NOT_RUN"),
        gate3_package_status=str((gate3_result or {}).get("package_status") or "NOT_RUN"),
        lm2_parse_ok=lm2_json is not None,
        gate4_verdict=str(gate4_verdict),
        live_shadow_receipt_valid=status == TRIAL_PASSED,
        failure_reason=failure_reason,
        lm1_model_output_excerpt=_excerpt(lm1_output),
        lm2_model_output_excerpt=_excerpt(lm2_output),
        parsed_lm1_candidate=lm1_json,
        parsed_lm2_response=lm2_json,
        gate2_result=gate2_result,
        gate3_result=gate3_result,
        gate4_result=gate4_result,
        authority_boundary=dict(AUTHORITY_BOUNDARY),
    )
    if persist:
        _persist_trial(request, result, db_path=db_path)
    return {"trial_request": asdict(request), "trial_result": asdict(result)}


def load_generated_payload(path: Path = DEFAULT_EXPORT_ROOT / JSON_EXPORT_NAME) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict) and payload.get("read_model_id") == READ_MODEL_ID:
            return payload
    except (OSError, json.JSONDecodeError):
        return None
    return None


def latest_or_ready_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    existing = load_generated_payload()
    if existing and ((existing.get("trial") or {}).get("trial_result") or {}).get("live_model_call_performed"):
        return existing
    return build_payload(generated_at=generated_at, allow_live=False, persist=False)


def build_payload(
    *,
    generated_at: str | None = None,
    allow_live: bool = False,
    model_ref: str = DEFAULT_MODEL_REF,
    provider_class: str = DEFAULT_PROVIDER_CLASS,
    db_path: Path = DEFAULT_DB_PATH,
    persist: bool = True,
    runner: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    trial = run_live_shadow_trial(
        allow_live=allow_live,
        model_ref=model_ref,
        provider_class=provider_class,
        generated_at=generated_at,
        db_path=db_path,
        runner=runner,
        persist=persist,
    )
    result = trial["trial_result"]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "trial_status": result["status"],
        "trial": trial,
        "isolated_sqlite": {
            "db_path": db_path.as_posix(),
            "business_ops_ledger_path": ".openclaw/business_ops.sqlite",
            "db_isolated_from_business_ops_ledger": db_path.as_posix() != ".openclaw/business_ops.sqlite",
            "tables": _table_names(db_path) if persist else ("live_lm_shadow_trials",),
        },
        "operator_summary": (
            "OpenClaw can run a local-only live-shadow model test against minimized fixture context.",
            "The result is judged by Gate 2, Gate 3, and Guardian before it counts as proof.",
            "This does not enable production models, tools, sends, ledger actions, or workflow execution.",
        ),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "live_shadow_trial_present": True,
            "live_model_call_performed": result["live_model_call_performed"],
            "provider_class": result["provider_class"],
            "model_ref": result["model_ref"],
            "network_scope": result["network_scope"],
            "tokenized_or_minimized": result["tokenized_or_minimized"],
            "raw_sensitive_data_included": result["raw_sensitive_data_included"],
            "lm1_parse_ok": result["lm1_parse_ok"],
            "lm1_expected_match": result["lm1_expected_match"],
            "gate2_accepted": result["gate2_outcome"] == intent_ingest_gate.ACCEPTED_INTENT,
            "gate3_compiled": result["gate3_package_status"] == role_package_gate.PACKAGE_COMPILED,
            "lm2_parse_ok": result["lm2_parse_ok"],
            "gate4_validated": result["gate4_verdict"] == guardian_output_gate.VALIDATED,
            "live_shadow_receipt_valid": result["live_shadow_receipt_valid"],
            "production_state_mutation_performed": False,
            "tool_execution_performed": False,
            "external_action_performed": False,
            "send_submit_performed": False,
            "all_production_authority_false": all(value is False for value in AUTHORITY_BOUNDARY.values()),
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
        "# Live LM Shadow Trial",
        "",
        f"Status: {payload.get('trial_status')}",
        f"Provider class: {proof.get('provider_class')}",
        f"Model: {proof.get('model_ref')}",
        f"Live model call performed: {str(proof.get('live_model_call_performed')).lower()}",
        f"Gate 2 accepted: {str(proof.get('gate2_accepted')).lower()}",
        f"Gate 3 compiled: {str(proof.get('gate3_compiled')).lower()}",
        f"Gate 4 validated: {str(proof.get('gate4_validated')).lower()}",
        "",
        "This is isolated test/shadow proof only. Production authority remains off.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run/export local-only live LM shadow trial.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--model-ref", default=DEFAULT_MODEL_REF)
    parser.add_argument("--provider-class", default=DEFAULT_PROVIDER_CLASS)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)

    payload = build_payload(
        generated_at=args.generated_at,
        allow_live=args.allow_live,
        model_ref=args.model_ref,
        provider_class=args.provider_class,
        db_path=args.db_path,
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
                    "trial_status": payload["trial_status"],
                    "live_model_call_performed": payload["machine_proof"]["live_model_call_performed"],
                    "live_shadow_receipt_valid": payload["machine_proof"]["live_shadow_receipt_valid"],
                    "all_production_authority_false": payload["machine_proof"]["all_production_authority_false"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

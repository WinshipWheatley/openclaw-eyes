"""External LM shadow adapter v0.

Takes an eligibility-approved ``ExternalLmSafePackage`` and attempts a
shadow/test model pass under provider policy. This adapter does not activate
production models, load API keys, execute tools, or grant authority.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import external_lm_eligibility_policy
import external_lm_safe_package_compiler
import external_shadow_provider_config
import guardian_output_gate
import intent_ingest_gate
import local_shadow_lm_runner
import machine_intent_candidate_validator
import model_router_policy


DEFAULT_DB_PATH = Path(".openclaw/test_harness/external_lm_shadow_adapter.sqlite")

SCHEMA_VERSION = "external_lm_shadow_adapter_v0"
ADAPTER_ID = "external_lm_shadow_adapter.shadow_only_v0"

SHADOW_ONLY = "SHADOW_ONLY"
SHADOW_PACKAGE_REJECTED = "SHADOW_PACKAGE_REJECTED"
SHADOW_PROVIDER_NOT_CONFIGURED = "SHADOW_PROVIDER_NOT_CONFIGURED"
SHADOW_PROVIDER_CALL_FAILED = "SHADOW_PROVIDER_CALL_FAILED"
SHADOW_LM_OUTPUT_INVALID = "SHADOW_LM_OUTPUT_INVALID"
SHADOW_VALIDATED = "SHADOW_VALIDATED"

LM1 = external_lm_safe_package_compiler.LM1
LM2 = external_lm_safe_package_compiler.LM2

AUTHORITY_BOUNDARY = {
    "production_live_lm_authority_allowed": False,
    "provider_key_material_access_allowed": False,
    "tool_execution_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "ledger_posting_allowed": False,
    "workflow_execution_allowed": False,
    "production_state_mutation_allowed": False,
    "credential_handling_allowed": False,
}

ExternalShadowCall = Callable[[str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True)
class ShadowProviderConfig:
    configured_external_provider_refs: tuple[str, ...] = ()
    allow_local_fallback_smoke: bool = False
    local_fallback_provider_refs: tuple[str, ...] = ("provider_class:local_or_private_fallback_model",)
    external_shadow_enabled: bool = False


@dataclass(frozen=True)
class ShadowPackageVerification:
    verified: bool
    rejected_reasons: tuple[str, ...]
    lane: str
    source_request_id: str
    package_id: str


@dataclass(frozen=True)
class ExternalLmShadowRunResult:
    schema_version: str
    adapter_id: str
    run_id: str
    source_request_id: str
    lane: str
    status: str
    shadow_only: bool
    production_authority: bool
    local_fallback_smoke: bool
    production_baseline: bool
    model_class: str
    provider_ref: str
    provider_policy_id: str
    package_hash: str
    package_summary: dict[str, Any]
    prompt_hash: str
    prompt_summary: dict[str, Any]
    output_hash: str
    output_summary: dict[str, Any]
    model_call_result: dict[str, Any] | None
    gate_verdict: str
    gate_result: dict[str, Any] | None
    sqlite_db_path: str
    sqlite_run_record_id: str
    sqlite_validation_record_id: str
    record_written: bool
    blocked_reasons: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _json_hash(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _normalize_lane(value: object) -> str:
    lane = str(value or "").upper()
    return LM1 if lane in {"LM1", "LM1_INTENT_PROPOSAL"} else LM2


def _safe_package_from_input(package_or_result: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(package_or_result.get("safe_package"), Mapping):
        return dict(package_or_result["safe_package"])
    return dict(package_or_result)


def verify_external_lm_safe_package(package_or_result: Mapping[str, Any]) -> dict[str, Any]:
    package = _safe_package_from_input(package_or_result)
    reasons: list[str] = []
    package_id = str(package.get("package_id") or "")
    lane = _normalize_lane(package.get("lane"))
    source_request_id = str(package.get("source_request_id") or "")

    if not package_id.startswith("external_lm_safe_package:"):
        reasons.append("NOT_EXTERNAL_LM_SAFE_PACKAGE")
    if not source_request_id:
        reasons.append("MISSING_SOURCE_REQUEST_ID")
    if str(package.get("eligibility_verdict") or "") != "EXTERNAL_ALLOWED" or not bool(package.get("external_lm_allowed")):
        reasons.append("ELIGIBILITY_NOT_PASSED")
    if not bool(package.get("leak_scan_passed")):
        reasons.append("LEAK_SCAN_NOT_PASSED")
    if bool(package.get("tokenization_required")) and not bool(package.get("tokenization_applied")):
        reasons.append("TOKENIZATION_REQUIRED_BUT_MISSING")
    if bool(package.get("raw_values_included")):
        reasons.append("RAW_VALUES_INCLUDED")
    if bool(package.get("credentials_present")):
        reasons.append("CREDENTIALS_PRESENT")
    if bool(package.get("secrets_present")):
        reasons.append("SECRETS_PRESENT")
    if not bool(package.get("package_minimized")):
        reasons.append("PACKAGE_NOT_MINIMIZED")
    if bool(package.get("detokenization_required_inside_model")):
        reasons.append("DETOKENIZATION_INSIDE_MODEL")
    if not bool(package.get("ready_for_external_shadow")):
        reasons.append("NOT_READY_FOR_EXTERNAL_SHADOW")
    if bool(package.get("ready_for_production")):
        reasons.append("READY_FOR_PRODUCTION_MUST_BE_FALSE")
    if any(bool(value) for value in dict(package.get("authority_boundary") or {}).values()):
        reasons.append("PACKAGE_AUTHORITY_NOT_FALSE")

    return asdict(
        ShadowPackageVerification(
            verified=not reasons,
            rejected_reasons=tuple(dict.fromkeys(reasons)),
            lane=lane,
            source_request_id=source_request_id,
            package_id=package_id,
        )
    )


def _provider_config(config: Mapping[str, Any] | ShadowProviderConfig | None) -> ShadowProviderConfig:
    if isinstance(config, ShadowProviderConfig):
        return config
    if config is None:
        config = external_shadow_provider_config.adapter_provider_config_from_environment()
    else:
        config = dict(config)
        if isinstance(config.get("adapter_provider_config"), Mapping):
            config = dict(config["adapter_provider_config"])
        elif "provider_configs" in config:
            config = external_shadow_provider_config.adapter_provider_config(config)
    return ShadowProviderConfig(
        configured_external_provider_refs=tuple(str(item) for item in config.get("configured_external_provider_refs", ())),
        allow_local_fallback_smoke=bool(config.get("allow_local_fallback_smoke", False)),
        local_fallback_provider_refs=tuple(
            str(item) for item in config.get("local_fallback_provider_refs", ("provider_class:local_or_private_fallback_model",))
        ),
        external_shadow_enabled=bool(config.get("external_shadow_enabled", False)),
    )


def _routing_sensitivity(package: Mapping[str, Any]) -> str:
    privacy = str(package.get("privacy_level") or "").upper()
    if privacy == "CLIENT_FINANCE_FILE_METADATA" and package.get("tokenization_applied") and not package.get("raw_values_included"):
        return "tokenized_client_finance_metadata"
    if privacy == "PERSONAL_FINANCE_METADATA" and package.get("tokenization_applied") and not package.get("raw_values_included"):
        return "tokenized_personal_finance_metadata"
    if privacy in {"LEGAL_DISCOVERY_METADATA", "LEGAL_PRIVILEGED_METADATA"} and package.get("tokenization_applied"):
        return "tokenized_legal_discovery_metadata"
    if privacy in {"SENSITIVE_METADATA", "HEALTH_METADATA"} and package.get("tokenization_applied"):
        return "tokenized_sensitive_metadata"
    if str(package.get("sensitivity_class") or "").upper() in {"CLIENT_FINANCE", "PERSONAL_FINANCE"}:
        return "tokenized_client_finance_metadata"
    return "low"


def select_shadow_model_route(
    safe_package: Mapping[str, Any],
    *,
    local_fallback_smoke: bool = False,
) -> dict[str, Any]:
    lane = _normalize_lane(safe_package.get("lane"))
    chain_lane = "LM1_INTENT_PROPOSAL" if lane == LM1 else "LM2_ROLE_RESPONSE"
    recommended_model = str(safe_package.get("model_class_recommended") or "")
    route_request = {
        "request_id": f"{safe_package.get('package_id', 'external_lm_safe_package')}:shadow_model_route",
        "chain_lane": chain_lane,
        "task_type": "external_lm_shadow_intent" if lane == LM1 else "external_lm_shadow_role_response",
        "role": "OPENCLAW_SYSTEM" if lane == LM1 else "ROLE_PACKAGE",
        "risk_level": "low" if lane == LM1 else "medium",
        "sensitivity_level": _routing_sensitivity(safe_package),
        "context_size": "small" if lane == LM1 else "medium",
        "requires_structured_output": True,
        "creative_posture_allowed": False,
        "tokenization_applied": bool(safe_package.get("tokenization_applied")),
        "raw_values_included": bool(safe_package.get("raw_values_included")),
        "requested_live_authority": False,
        "external_lm_allowed": bool(safe_package.get("external_lm_allowed")) and not local_fallback_smoke,
        "local_lm_required": bool(local_fallback_smoke),
        "offline_mode": bool(local_fallback_smoke),
        "strict_private_mode_active": False,
        "credentials_or_secrets_present": bool(safe_package.get("credentials_present") or safe_package.get("secrets_present")),
        "package_minimized": bool(safe_package.get("package_minimized")),
        "baseline_external_passed": False,
        "downgrade_testing_requested": bool(local_fallback_smoke),
    }
    decision = model_router_policy.select_model_class(route_request)
    if not local_fallback_smoke and recommended_model and decision["selected_model_class"] != recommended_model:
        decision = {
            **decision,
            "risk_notes": tuple(dict.fromkeys(tuple(decision.get("risk_notes") or ()) + ("ROUTE_DIFFERS_FROM_PACKAGE_RECOMMENDATION",))),
        }
    if local_fallback_smoke:
        decision = {
            **decision,
            "selection_reason": f"{decision.get('selection_reason', '')} Local fallback is smoke/test only, not a production baseline.",
        }
    return decision


def _prompt_summary(safe_package: Mapping[str, Any], route_decision: Mapping[str, Any]) -> dict[str, Any]:
    lm_input = safe_package.get("lm_input_payload") if isinstance(safe_package.get("lm_input_payload"), Mapping) else {}
    return {
        "source_request_id": safe_package.get("source_request_id"),
        "lane": safe_package.get("lane"),
        "model_class": route_decision.get("selected_model_class"),
        "provider_ref": route_decision.get("selected_provider_ref"),
        "allowed_context_classes": safe_package.get("allowed_context_classes", ()),
        "forbidden_context_classes": safe_package.get("forbidden_context_classes", ()),
        "output_schema": lm_input.get("output_schema"),
        "raw_values_included": False,
        "tools_allowed": (),
        "authority": False,
    }


def _build_prompt(safe_package: Mapping[str, Any], route_decision: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    summary = _prompt_summary(safe_package, route_decision)
    lane = _normalize_lane(safe_package.get("lane"))
    lm_input = safe_package.get("lm_input_payload") if isinstance(safe_package.get("lm_input_payload"), Mapping) else {}
    if lane == LM1:
        instruction = (
            "Return a MachineIntentCandidate JSON object only. You propose intent; Gate 2 decides. "
            "No tools, no authority, no execution."
        )
    else:
        instruction = (
            "Return a RoleResponseCandidate-shaped JSON object only. Use only the bounded role package. "
            "No tools, no sends, no completion claims, no authority."
        )
    prompt = "\n".join(
        (
            "OpenClaw external LM shadow/test package.",
            "This is SHADOW_ONLY and cannot grant production authority.",
            instruction,
            "",
            "Prompt summary:",
            stable_json(summary).strip(),
            "",
            "Minimized package input:",
            stable_json(lm_input).strip(),
        )
    )
    return prompt, summary


def _all_false_authority() -> dict[str, bool]:
    return {
        "external_action": False,
        "send_submit": False,
        "tool_execution": False,
        "workflow_execution": False,
        "ledger_posting": False,
        "file_mutation": False,
        "credential_handling": False,
        "raw_body_ingestion": False,
    }


def _tuple_str(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)


def _dict_bool(value: object) -> dict[str, bool]:
    defaults = _all_false_authority()
    if isinstance(value, Mapping):
        defaults.update({str(key): bool(flag) for key, flag in value.items()})
    return defaults


def _coerce_lm1_candidate(parsed: Mapping[str, Any], safe_package: Mapping[str, Any], route_decision: Mapping[str, Any]) -> Any:
    source_request_id = str(safe_package.get("source_request_id") or "external_lm_shadow_source")
    lm_input = safe_package.get("lm_input_payload") if isinstance(safe_package.get("lm_input_payload"), Mapping) else {}
    intent_type = str(parsed.get("inferred_intent_type") or parsed.get("intent_type") or "").upper()
    if not intent_type:
        return None
    confidence = str(parsed.get("confidence") or "MEDIUM").upper()
    ambiguity = str(parsed.get("ambiguity_status") or "UNAMBIGUOUS").upper()
    if confidence not in machine_intent_candidate_validator.CONFIDENCE_VALUES:
        confidence = "MEDIUM"
    if ambiguity not in machine_intent_candidate_validator.AMBIGUITY_STATUSES:
        ambiguity = "UNKNOWN_FAIL_CLOSED"
    return machine_intent_candidate_validator.MachineIntentCandidate(
        intent_id=f"external_lm_shadow_lm1_candidate:{_short_hash(source_request_id, stable_json(dict(parsed)))}",
        source_request_id=source_request_id,
        original_operator_text="minimized external shadow package request",
        inferred_intent_type=intent_type,
        target_world_ref=str(parsed.get("target_world_ref") or lm_input.get("current_world_ref") or "shadow_world"),
        target_folder_ref=str(parsed.get("target_folder_ref") or "shadow_scope"),
        target_thread_ref=str(parsed.get("target_thread_ref") or lm_input.get("current_thread_ref") or "thread_ref:shadow"),
        target_workflow_ref=str(parsed.get("target_workflow_ref") or "external_lm_shadow_workflow"),
        target_agent_role=str(parsed.get("target_agent_role") or "CHIEF").upper(),
        target_worker_type="GPT"
        if str(route_decision.get("selected_provider_ref") or "").startswith("provider_class:external")
        else "LOCAL_OLLAMA",
        requested_action=str(parsed.get("requested_action") or "status_or_next_safe_move"),
        referenced_next_action=str(parsed.get("referenced_next_action") or ""),
        confidence=confidence,
        ambiguity_status=ambiguity,
        required_clarification=str(parsed.get("required_clarification") or ""),
        evidence_refs_used=("generated/read_models/external_lm_safe_package.json", "machine_intent_validation"),
        context_refs_used=_tuple_str(parsed.get("context_refs_used")) or ("tenant_scope:fixture_business_ops",),
        source_refs_used=_tuple_str(parsed.get("source_refs_used")),
        missing_requirements=_tuple_str(parsed.get("missing_requirements")),
        forbidden_assumptions=_tuple_str(parsed.get("forbidden_assumptions"))
        or ("do_not_send", "do_not_submit", "do_not_mark_paid", "do_not_grant_authority"),
        authority_requested=_dict_bool(parsed.get("authority_requested")),
        authority_granted=_dict_bool(parsed.get("authority_granted")),
        validation_required=True,
        next_safe_move=str(parsed.get("next_safe_move") or "Validate through Gate 2; do not execute."),
    )


def _guardian_package(safe_package: Mapping[str, Any], route_decision: Mapping[str, Any]) -> guardian_output_gate.RoleExecutionPackage:
    lm_input = safe_package.get("lm_input_payload") if isinstance(safe_package.get("lm_input_payload"), Mapping) else {}
    role_package = lm_input.get("role_execution_package") if isinstance(lm_input.get("role_execution_package"), Mapping) else {}
    role = str(role_package.get("role_identity") or role_package.get("actor_label") or "OPENCLAW_SYSTEM").upper()
    return guardian_output_gate.RoleExecutionPackage(
        package_id=str(safe_package.get("package_id") or ""),
        source_request_id=str(safe_package.get("source_request_id") or ""),
        source_intent_ref="external_lm_shadow_lm2_response",
        role=role,
        model_backend=str(route_decision.get("selected_model_class") or "SHADOW_MODEL"),
        device_response_target="mission_control_scoped_response",
        workflow_ref=str(role_package.get("workflow_ref") or ""),
        client_ref=str(role_package.get("client_ref") or ""),
        allowed_tools=(),
        allowed_actions=("respond_to_originating_device",),
        forbidden_actions=guardian_output_gate.FORBIDDEN_ACTIONS,
        proof_refs=(str(safe_package.get("package_id") or ""),),
        authority_boundary=dict(guardian_output_gate.AUTHORITY_BOUNDARY),
        output_contract=(
            "shadow response only",
            "do not request tools or external actions",
            "do not claim send/submit/paid/posted/completed",
            "do not expose raw values or credentials",
        ),
        validation_required=True,
        next_safe_move="Validate shadow LM2 output before any scoped response candidate.",
    )


def _coerce_lm2_candidate(parsed: Mapping[str, Any], package: guardian_output_gate.RoleExecutionPackage) -> guardian_output_gate.RoleResponseCandidate:
    raw_text = " ".join(
        str(parsed.get(key) or "")
        for key in ("headline", "one_line_answer", "eliwinship", "draft_text", "next_action")
    )
    return guardian_output_gate.RoleResponseCandidate(
        candidate_id=f"external_lm_shadow_lm2_candidate:{_short_hash(package.source_request_id, stable_json(dict(parsed)))}",
        source_package_id=package.package_id,
        source_request_id=package.source_request_id,
        response_author=package.role,
        target_device_ref=package.device_response_target,
        target_thread_ref=package.source_request_id,
        headline=str(parsed.get("headline") or "Shadow response candidate"),
        one_line_answer=str(parsed.get("one_line_answer") or "Shadow response candidate."),
        eliwinship=str(parsed.get("eliwinship") or parsed.get("draft_text") or "Shadow-only response candidate. Nothing was executed."),
        next_action=str(parsed.get("next_action") or "Review this shadow-only candidate."),
        requested_tool_calls=_tuple_str(parsed.get("requested_tool_calls")),
        requested_external_actions=_tuple_str(parsed.get("requested_external_actions")),
        completion_claims=_tuple_str(parsed.get("completion_claims")) or guardian_output_gate._unnegated_claims(raw_text),
        proof_refs=package.proof_refs,
        authority_requested=_dict_bool(parsed.get("authority_requested")),
        raw_output_text=raw_text,
        next_safe_move=str(parsed.get("next_safe_move") or "Validate through Guardian; do not execute."),
    )


def _call_model(
    *,
    prompt: str,
    safe_package: Mapping[str, Any],
    route_decision: Mapping[str, Any],
    config: ShadowProviderConfig,
    external_shadow_call: ExternalShadowCall | None,
) -> dict[str, Any]:
    lane = _normalize_lane(safe_package.get("lane"))
    chain_lane = "LM1_INTENT_PROPOSAL" if lane == LM1 else "LM2_ROLE_RESPONSE"
    provider_ref = str(route_decision.get("selected_provider_ref") or "")
    source_request_id = str(safe_package.get("source_request_id") or "")
    is_external = provider_ref.startswith("provider_class:external")
    if is_external:
        if not config.external_shadow_enabled or provider_ref not in set(config.configured_external_provider_refs):
            return {
                "status": SHADOW_PROVIDER_NOT_CONFIGURED,
                "lane": chain_lane,
                "request_id": source_request_id,
                "provider_ref": provider_ref,
                "selected_model_class": route_decision.get("selected_model_class", ""),
                "parsed_json": {},
                "raw_response_text": "",
                "error": "Approved external shadow provider is not configured.",
                "shadow_only": True,
                "production_authority": False,
            }
        if external_shadow_call is None:
            return {
                "status": SHADOW_PROVIDER_NOT_CONFIGURED,
                "lane": chain_lane,
                "request_id": source_request_id,
                "provider_ref": provider_ref,
                "selected_model_class": route_decision.get("selected_model_class", ""),
                "parsed_json": {},
                "raw_response_text": "",
                "error": "External shadow call adapter is not configured.",
                "shadow_only": True,
                "production_authority": False,
            }
        try:
            result = dict(external_shadow_call(prompt, safe_package, route_decision))
        except Exception as exc:  # pragma: no cover - defensive boundary
            return {
                "status": SHADOW_PROVIDER_CALL_FAILED,
                "lane": chain_lane,
                "request_id": source_request_id,
                "provider_ref": provider_ref,
                "selected_model_class": route_decision.get("selected_model_class", ""),
                "parsed_json": {},
                "raw_response_text": "",
                "error": str(exc),
                "shadow_only": True,
                "production_authority": False,
            }
        return {
            **result,
            "status": str(result.get("status") or local_shadow_lm_runner.RESULT_OK),
            "shadow_only": True,
            "production_authority": False,
            "provider_ref": provider_ref,
            "selected_model_class": route_decision.get("selected_model_class", ""),
        }

    if provider_ref not in set(config.local_fallback_provider_refs):
        return {
            "status": SHADOW_PROVIDER_NOT_CONFIGURED,
            "lane": chain_lane,
            "request_id": source_request_id,
            "provider_ref": provider_ref,
            "selected_model_class": route_decision.get("selected_model_class", ""),
            "parsed_json": {},
            "raw_response_text": "",
            "error": "Local fallback smoke provider is not configured.",
            "shadow_only": True,
            "production_authority": False,
        }
    return local_shadow_lm_runner.generate_json(
        prompt=prompt,
        lane=chain_lane,
        request_id=source_request_id,
        route_decision=route_decision,
    )


def _validate_output(
    *,
    safe_package: Mapping[str, Any],
    route_decision: Mapping[str, Any],
    model_call_result: Mapping[str, Any],
) -> tuple[str, dict[str, Any] | None, dict[str, Any]]:
    parsed = model_call_result.get("parsed_json") if isinstance(model_call_result.get("parsed_json"), Mapping) else {}
    if not parsed:
        return (SHADOW_LM_OUTPUT_INVALID, None, {"blocked_reasons": ("MODEL_OUTPUT_EMPTY_OR_NOT_JSON",)})
    lane = _normalize_lane(safe_package.get("lane"))
    if lane == LM1:
        candidate = _coerce_lm1_candidate(parsed, safe_package, route_decision)
        if candidate is None:
            return (SHADOW_LM_OUTPUT_INVALID, None, {"blocked_reasons": ("MISSING_INTENT_TYPE",)})
        gate2 = intent_ingest_gate.ingest_intent_proposal(candidate)
        return (str(gate2.get("outcome") or ""), gate2, candidate.__dict__)

    package = _guardian_package(safe_package, route_decision)
    candidate = _coerce_lm2_candidate(parsed, package)
    validation = guardian_output_gate.validate_role_output(candidate, package)
    return (validation.verdict, asdict(validation), asdict(candidate))


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
CREATE TABLE IF NOT EXISTS external_lm_shadow_runs (
  run_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  source_request_id TEXT NOT NULL,
  lane TEXT NOT NULL,
  status TEXT NOT NULL,
  model_class TEXT NOT NULL,
  provider_ref TEXT NOT NULL,
  provider_policy_id TEXT NOT NULL,
  package_hash TEXT NOT NULL,
  prompt_hash TEXT NOT NULL,
  output_hash TEXT NOT NULL,
  gate_verdict TEXT NOT NULL,
  shadow_only INTEGER NOT NULL CHECK (shadow_only = 1),
  production_authority INTEGER NOT NULL CHECK (production_authority = 0),
  raw_values_included INTEGER NOT NULL CHECK (raw_values_included = 0),
  payload_json TEXT NOT NULL
)
"""
    )
    conn.execute(
        """
CREATE TABLE IF NOT EXISTS external_lm_shadow_validation_results (
  validation_record_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  source_request_id TEXT NOT NULL,
  lane TEXT NOT NULL,
  gate_verdict TEXT NOT NULL,
  validation_json TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES external_lm_shadow_runs(run_id)
)
"""
    )


def _write_shadow_record(db_path: Path, result: ExternalLmShadowRunResult) -> ExternalLmShadowRunResult:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**asdict(result), "record_written": True}
    with sqlite3.connect(db_path) as conn:
        _create_schema(conn)
        conn.execute(
            """
INSERT OR REPLACE INTO external_lm_shadow_runs
  (run_id, created_at, source_request_id, lane, status, model_class, provider_ref,
   provider_policy_id, package_hash, prompt_hash, output_hash, gate_verdict,
   shadow_only, production_authority, raw_values_included, payload_json)
VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0, ?)
""",
            (
                result.run_id,
                result.source_request_id,
                result.lane,
                result.status,
                result.model_class,
                result.provider_ref,
                result.provider_policy_id,
                result.package_hash,
                result.prompt_hash,
                result.output_hash,
                result.gate_verdict,
                stable_json(payload),
            ),
        )
        conn.execute(
            """
INSERT OR REPLACE INTO external_lm_shadow_validation_results
  (validation_record_id, run_id, source_request_id, lane, gate_verdict, validation_json)
VALUES (?, ?, ?, ?, ?, ?)
""",
            (
                result.sqlite_validation_record_id,
                result.run_id,
                result.source_request_id,
                result.lane,
                result.gate_verdict,
                stable_json(result.gate_result or {}),
            ),
        )
        conn.commit()
    return ExternalLmShadowRunResult(**payload)


def run_external_lm_shadow(
    package_or_result: Mapping[str, Any],
    *,
    db_path: Path = DEFAULT_DB_PATH,
    provider_config: Mapping[str, Any] | ShadowProviderConfig | None = None,
    external_shadow_call: ExternalShadowCall | None = None,
    local_fallback_smoke: bool = False,
    write_record: bool = True,
) -> dict[str, Any]:
    safe_package = _safe_package_from_input(package_or_result)
    verification = verify_external_lm_safe_package(safe_package)
    config = _provider_config(provider_config)
    lane = verification["lane"]
    source_request_id = verification["source_request_id"] or str(safe_package.get("source_request_id") or "unknown_source")
    route_decision = (
        select_shadow_model_route(safe_package, local_fallback_smoke=local_fallback_smoke)
        if verification["verified"]
        else {}
    )
    prompt = ""
    prompt_summary: dict[str, Any] = {}
    model_call_result: dict[str, Any] | None = None
    gate_verdict = ""
    gate_result: dict[str, Any] | None = None
    output_summary: dict[str, Any] = {}
    blocked = list(verification["rejected_reasons"])
    local_fallback = False

    if verification["verified"]:
        prompt, prompt_summary = _build_prompt(safe_package, route_decision)
        selected_model = str(route_decision.get("selected_model_class") or "")
        if selected_model == model_router_policy.NO_SAFE_MODEL:
            blocked.extend(str(item) for item in route_decision.get("blocked_reasons") or ("NO_SAFE_MODEL",))
            status = SHADOW_PROVIDER_NOT_CONFIGURED
            gate_verdict = "NO_SAFE_MODEL"
        else:
            provider_ref = str(route_decision.get("selected_provider_ref") or "")
            local_fallback = provider_ref.startswith("provider_class:local_or_private")
            model_call_result = _call_model(
                prompt=prompt,
                safe_package=safe_package,
                route_decision=route_decision,
                config=config,
                external_shadow_call=external_shadow_call,
            )
            call_status = str(model_call_result.get("status") or "")
            if call_status in {local_shadow_lm_runner.RESULT_OK, "SHADOW_EXTERNAL_RESULT"}:
                gate_verdict, gate_result, output_summary = _validate_output(
                    safe_package=safe_package,
                    route_decision=route_decision,
                    model_call_result=model_call_result,
                )
                valid_gate = (
                    gate_verdict == intent_ingest_gate.ACCEPTED_INTENT
                    if lane == LM1
                    else gate_verdict == guardian_output_gate.VALIDATED
                )
                status = SHADOW_VALIDATED if valid_gate else SHADOW_LM_OUTPUT_INVALID
            elif call_status == SHADOW_PROVIDER_NOT_CONFIGURED:
                status = SHADOW_PROVIDER_NOT_CONFIGURED
                gate_verdict = "NOT_RUN_PROVIDER_NOT_CONFIGURED"
                blocked.append(str(model_call_result.get("error") or SHADOW_PROVIDER_NOT_CONFIGURED))
            else:
                status = SHADOW_PROVIDER_CALL_FAILED
                gate_verdict = "MODEL_CALL_NOT_VALIDATED"
                blocked.append(str(model_call_result.get("error") or call_status or "shadow call failed"))
    else:
        status = SHADOW_PACKAGE_REJECTED
        gate_verdict = "PACKAGE_REJECTED"

    route_decision = route_decision or {}
    package_summary = {
        "package_id": safe_package.get("package_id", ""),
        "source_request_id": source_request_id,
        "lane": lane,
        "privacy_level": safe_package.get("privacy_level", ""),
        "sensitivity_class": safe_package.get("sensitivity_class", ""),
        "model_class_recommended": safe_package.get("model_class_recommended", ""),
        "ready_for_external_shadow": bool(safe_package.get("ready_for_external_shadow", False)),
        "ready_for_production": bool(safe_package.get("ready_for_production", False)),
        "raw_values_included": bool(safe_package.get("raw_values_included", False)),
    }
    output_summary = output_summary or {
        "status": status,
        "model_call_status": str((model_call_result or {}).get("status") or ""),
        "error": str((model_call_result or {}).get("error") or ""),
    }
    run_id = f"external_lm_shadow_run:{_short_hash(source_request_id, lane, _json_hash(safe_package), _json_hash(output_summary))}"
    validation_record_id = f"external_lm_shadow_validation:{_short_hash(run_id, gate_verdict)}"
    result = ExternalLmShadowRunResult(
        schema_version=SCHEMA_VERSION,
        adapter_id=ADAPTER_ID,
        run_id=run_id,
        source_request_id=source_request_id,
        lane=lane,
        status=status,
        shadow_only=True,
        production_authority=False,
        local_fallback_smoke=bool(local_fallback or local_fallback_smoke),
        production_baseline=False,
        model_class=str(route_decision.get("selected_model_class") or safe_package.get("model_class_recommended") or ""),
        provider_ref=str(route_decision.get("selected_provider_ref") or ""),
        provider_policy_id=str(route_decision.get("selected_provider_policy_id") or ""),
        package_hash=_json_hash(safe_package),
        package_summary=package_summary,
        prompt_hash=_json_hash({"prompt": prompt}),
        prompt_summary=prompt_summary,
        output_hash=_json_hash(output_summary),
        output_summary=output_summary,
        model_call_result=dict(model_call_result or {}),
        gate_verdict=gate_verdict,
        gate_result=gate_result,
        sqlite_db_path=db_path.as_posix(),
        sqlite_run_record_id=run_id,
        sqlite_validation_record_id=validation_record_id,
        record_written=False,
        blocked_reasons=tuple(dict.fromkeys(str(item) for item in blocked if str(item))),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move=(
            "Shadow result validated by the downstream gate; keep production authority off."
            if status == SHADOW_VALIDATED
            else "Do not treat this as production. Resolve provider/package/output blockers before another shadow pass."
        ),
    )
    if write_record:
        result = _write_shadow_record(db_path, result)
    return asdict(result)


def read_shadow_run(db_path: Path, run_id: str) -> dict[str, Any] | None:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM external_lm_shadow_runs WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    return dict(row)


__all__ = [
    "ADAPTER_ID",
    "DEFAULT_DB_PATH",
    "SCHEMA_VERSION",
    "SHADOW_LM_OUTPUT_INVALID",
    "SHADOW_PACKAGE_REJECTED",
    "SHADOW_PROVIDER_NOT_CONFIGURED",
    "SHADOW_VALIDATED",
    "ShadowProviderConfig",
    "read_shadow_run",
    "run_external_lm_shadow",
    "select_shadow_model_route",
    "verify_external_lm_safe_package",
]

"""Model Router Policy v0.

Model-agnostic routing policy for future LM1/LM2 selection. This contract
chooses model classes, not vendors, and never calls models or grants authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import provider_policy_registry


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "model_router_policy_v1"
READ_MODEL_ID = "model_router_policy"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "PROVIDER_POLICY_AWARE_MODEL_ROUTER_NO_LIVE_CALLS"

NO_SAFE_MODEL = "NO_SAFE_MODEL"
FAST_EXTERNAL_INTENT_MODEL = "FAST_EXTERNAL_INTENT_MODEL"
STRONG_EXTERNAL_ROLE_MODEL = "STRONG_EXTERNAL_ROLE_MODEL"
LOCAL_FALLBACK_MODEL = "LOCAL_FALLBACK_MODEL"
LOCAL_ONLY_MODEL = "LOCAL_ONLY_MODEL"
FAST_STRUCTURED_INTENT_SMALL = "FAST_STRUCTURED_INTENT_SMALL"
STRONG_STRUCTURED_ROLE_REASONER = "STRONG_STRUCTURED_ROLE_REASONER"
CONSERVATIVE_SENSITIVE_STRUCTURED = "CONSERVATIVE_SENSITIVE_STRUCTURED"

AUTHORITY_BOUNDARY = {
    "live_model_call_allowed": False,
    "model_api_integration_allowed": False,
    "network_allowed": False,
    "provider_key_material_access_allowed": False,
    "authority_grant_allowed": False,
    "tool_execution_allowed": False,
    "external_action_allowed": False,
    "send_submit_allowed": False,
    "workflow_execution_allowed": False,
    "production_state_mutation_allowed": False,
}


@dataclass(frozen=True)
class ModelCandidateClass:
    model_class_id: str
    lane_fit: tuple[str, ...]
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    default_posture: str
    structured_output_reliability: str
    cost_latency_class: str
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class ModelRoutingRequest:
    request_id: str
    chain_lane: str
    task_type: str
    role: str
    risk_level: str
    sensitivity_level: str
    context_size: str
    requires_structured_output: bool
    creative_posture_allowed: bool
    tokenization_applied: bool
    raw_values_included: bool
    requested_live_authority: bool
    external_lm_allowed: bool
    local_lm_required: bool
    offline_mode: bool
    strict_private_mode_active: bool
    credentials_or_secrets_present: bool
    package_minimized: bool
    baseline_external_passed: bool
    downgrade_testing_requested: bool


@dataclass(frozen=True)
class ModelRoutingDecision:
    decision_id: str
    request_id: str
    selected_model_class: str
    selected_provider_ref: str
    selected_model_ref: str
    selected_provider_policy_id: str
    fallback_provider_policy_id: str
    chain_lane: str
    selection_reason: str
    conservative_posture: bool
    structured_output_required: bool
    tokenization_required_before_live: bool
    rejected_model_classes: tuple[str, ...]
    rejected_provider_candidates: tuple[dict[str, Any], ...]
    risk_notes: tuple[str, ...]
    expected_failure_modes: tuple[str, ...]
    confidence: str
    blocked_reasons: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _short_hash(*parts: object) -> str:
    return hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def model_candidate_classes() -> tuple[ModelCandidateClass, ...]:
    return (
        ModelCandidateClass(
            model_class_id=FAST_EXTERNAL_INTENT_MODEL,
            lane_fit=("LM1_INTENT_PROPOSAL",),
            strengths=("fast external reasoning", "strict MachineIntentCandidate JSON", "low latency", "low cost"),
            weaknesses=("requires minimized/tokenized package", "provider receipts required before production", "no tools or authority"),
            default_posture="conservative_intent_only",
            structured_output_reliability="high_required",
            cost_latency_class="fast_external_low_cost",
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Use only for LM1 intent proposal after Gate 1 privacy packaging and receipt review.",
        ),
        ModelCandidateClass(
            model_class_id=STRONG_EXTERNAL_ROLE_MODEL,
            lane_fit=("LM2_ROLE_RESPONSE",),
            strengths=("strong role reasoning", "nuanced response drafting", "bounded package synthesis", "structured response"),
            weaknesses=("higher cost", "must be Guardian-gated", "requires minimized/tokenized package"),
            default_posture="bounded_role_reasoning",
            structured_output_reliability="high_required",
            cost_latency_class="strong_external_use_when_needed",
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Use only after Gate 3 compiles a bounded role package; validate with Gate 4.",
        ),
        ModelCandidateClass(
            model_class_id=LOCAL_FALLBACK_MODEL,
            lane_fit=("LM1_INTENT_PROPOSAL", "LM2_ROLE_RESPONSE"),
            strengths=("offline fallback", "local shadow smoke", "credit-saving mode", "policy-blocked fallback"),
            weaknesses=("not the production-quality target", "weaker reasoning than preferred external classes"),
            default_posture="fallback_conservative",
            structured_output_reliability="high_required",
            cost_latency_class="local_variable",
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Use when external policy is blocked, offline mode is active, or local smoke is enough.",
        ),
        ModelCandidateClass(
            model_class_id=LOCAL_ONLY_MODEL,
            lane_fit=("LM1_INTENT_PROPOSAL", "LM2_ROLE_RESPONSE"),
            strengths=("strict private/local-only", "no cloud exposure", "conservative handling"),
            weaknesses=("not the external baseline", "may underperform stronger external role models"),
            default_posture="strict_local_only",
            structured_output_reliability="strict_required",
            cost_latency_class="local_variable",
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Use only when strict/private/local policy requires local-only handling.",
        ),
        ModelCandidateClass(
            model_class_id=FAST_STRUCTURED_INTENT_SMALL,
            lane_fit=("LM1_INTENT_PROPOSAL",),
            strengths=("cheap", "low latency", "strict JSON proposal", "narrow classification"),
            weaknesses=("limited long-context reasoning", "not suitable for high-risk role response"),
            default_posture="conservative",
            structured_output_reliability="high_required",
            cost_latency_class="fast_low_cost",
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Use only to propose MachineIntentCandidate JSON for Gate 2.",
        ),
        ModelCandidateClass(
            model_class_id=STRONG_STRUCTURED_ROLE_REASONER,
            lane_fit=("LM2_ROLE_RESPONSE",),
            strengths=("role reasoning", "package following", "nuanced operator wording", "structured response"),
            weaknesses=("more expensive", "must be Guardian-gated", "no direct authority"),
            default_posture="bounded_role_reasoning",
            structured_output_reliability="high_required",
            cost_latency_class="medium_cost_medium_latency",
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Use only after Gate 3 compiles a bounded package; validate with Gate 4.",
        ),
        ModelCandidateClass(
            model_class_id=CONSERVATIVE_SENSITIVE_STRUCTURED,
            lane_fit=("LM1_INTENT_PROPOSAL", "LM2_ROLE_RESPONSE"),
            strengths=("sensitive context caution", "policy-heavy reasoning", "fail-closed behavior"),
            weaknesses=("higher latency", "may over-clarify", "still cannot receive raw secrets"),
            default_posture="strict_conservative",
            structured_output_reliability="strict_required",
            cost_latency_class="higher_cost_higher_latency",
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Use only for tokenized/high-risk packages when policy allows shadow/live candidate mode.",
        ),
    )


def _provider_privacy_level(request: ModelRoutingRequest) -> str:
    sensitivity = request.sensitivity_level.lower()
    if sensitivity == "tokenized_client_finance_metadata":
        return "TOKENIZED_CLIENT_FINANCE_METADATA"
    if sensitivity == "tokenized_personal_finance_metadata":
        return "TOKENIZED_PERSONAL_FINANCE_METADATA"
    if sensitivity == "tokenized_legal_discovery_metadata":
        return "TOKENIZED_LEGAL_DISCOVERY_METADATA"
    if sensitivity == "tokenized_sensitive_metadata":
        return "TOKENIZED_SENSITIVE_METADATA"
    if sensitivity == "client_finance_file_metadata":
        if request.tokenization_applied and not request.raw_values_included and request.package_minimized:
            return "TOKENIZED_CLIENT_FINANCE_METADATA"
        return "CLIENT_FINANCE_FILE_METADATA"
    if sensitivity == "personal_finance_metadata":
        if request.tokenization_applied and not request.raw_values_included and request.package_minimized:
            return "TOKENIZED_PERSONAL_FINANCE_METADATA"
        return "RAW_PRIVATE_BODY"
    if sensitivity in {"legal_discovery_metadata", "legal_privileged_metadata"}:
        if request.tokenization_applied and not request.raw_values_included and request.package_minimized:
            return "TOKENIZED_LEGAL_DISCOVERY_METADATA"
        return "RAW_PRIVATE_BODY"
    if sensitivity in {"sensitive_metadata", "health_metadata"}:
        if request.tokenization_applied and not request.raw_values_included and request.package_minimized:
            return "TOKENIZED_SENSITIVE_METADATA"
        return "RAW_PRIVATE_BODY"
    if sensitivity == "strict_private_client_metadata":
        return "STRICT_PRIVATE_CLIENT_METADATA"
    if sensitivity in {"high", "protected"} and (request.raw_values_included or not request.tokenization_applied):
        return "RAW_PRIVATE_BODY"
    if sensitivity in {"medium", "high", "protected"}:
        return "TOKENIZED_METADATA"
    return "LOW_METADATA"


def select_model_class(request: ModelRoutingRequest | Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(request, ModelRoutingRequest):
        request = ModelRoutingRequest(
            request_id=str(request.get("request_id") or "model_route_request"),
            chain_lane=str(request.get("chain_lane") or ""),
            task_type=str(request.get("task_type") or ""),
            role=str(request.get("role") or ""),
            risk_level=str(request.get("risk_level") or "medium").lower(),
            sensitivity_level=str(request.get("sensitivity_level") or "low").lower(),
            context_size=str(request.get("context_size") or "small").lower(),
            requires_structured_output=bool(request.get("requires_structured_output", True)),
            creative_posture_allowed=bool(request.get("creative_posture_allowed", False)),
            tokenization_applied=bool(request.get("tokenization_applied", False)),
            raw_values_included=bool(request.get("raw_values_included", False)),
            requested_live_authority=bool(request.get("requested_live_authority", False)),
            external_lm_allowed=bool(request.get("external_lm_allowed", False)),
            local_lm_required=bool(request.get("local_lm_required", False)),
            offline_mode=bool(request.get("offline_mode", False)),
            strict_private_mode_active=bool(request.get("strict_private_mode_active", False)),
            credentials_or_secrets_present=bool(
                request.get("credentials_or_secrets_present", False) or request.get("secrets_present", False)
            ),
            package_minimized=bool(request.get("package_minimized", True)),
            baseline_external_passed=bool(request.get("baseline_external_passed", False)),
            downgrade_testing_requested=bool(request.get("downgrade_testing_requested", False)),
        )

    blocked: list[str] = []
    if request.requested_live_authority:
        blocked.append("MODEL_ROUTER_CANNOT_GRANT_AUTHORITY")
    if request.credentials_or_secrets_present:
        blocked.append("CREDENTIALS_OR_SECRETS_NOT_ALLOWED_IN_MODEL_PACKAGE")
    if request.raw_values_included and request.sensitivity_level in {"high", "protected"}:
        blocked.append("RAW_SENSITIVE_VALUES_REQUIRE_TOKENIZATION")
    if not request.requires_structured_output:
        blocked.append("STRUCTURED_OUTPUT_REQUIRED_FOR_GATE_CHAIN")

    lane = request.chain_lane.upper()
    selected = NO_SAFE_MODEL
    reason = "No safe model class matched the request."
    conservative = True
    tokenization_required = request.sensitivity_level in {"high", "protected"} and not request.tokenization_applied
    risk_notes: list[str] = []
    expected_failure_modes: list[str] = []
    confidence = "MEDIUM"

    if request.risk_level in {"high", "critical"}:
        risk_notes.append("HIGH_RISK_REQUEST")
        expected_failure_modes.append("over-permissive model suggestion")
    if request.sensitivity_level in {"medium", "high", "protected"}:
        risk_notes.append("SENSITIVE_CONTEXT")
        expected_failure_modes.append("raw value leakage if package is miscompiled")
    if request.context_size in {"large", "huge"}:
        risk_notes.append("LARGE_CONTEXT")
        expected_failure_modes.append("context omission or instruction drift")
    if request.creative_posture_allowed:
        risk_notes.append("CREATIVE_POSTURE_ALLOWED")
    if not request.tokenization_applied and request.sensitivity_level in {"high", "protected"}:
        expected_failure_modes.append("privacy gate blocks live model route")
    if request.downgrade_testing_requested and not request.baseline_external_passed:
        risk_notes.append("LOCAL_DOWNGRADE_TESTING_BLOCKED_UNTIL_EXTERNAL_BASELINE_PASSES")
        expected_failure_modes.append("weak local baseline masks external-model quality problems")

    if blocked:
        selected = NO_SAFE_MODEL
        reason = "Blocked before model class selection."
    elif tokenization_required:
        selected = NO_SAFE_MODEL
        reason = "Sensitive context needs tokenization before any live LM candidate."
        blocked.append("TOKENIZATION_REQUIRED")
    elif request.strict_private_mode_active:
        selected = LOCAL_ONLY_MODEL
        reason = "Strict Private Mode requires local-only model handling."
        risk_notes.append("STRICT_PRIVATE_MODE_LOCAL_ONLY")
    elif request.local_lm_required or request.offline_mode:
        selected = LOCAL_FALLBACK_MODEL
        reason = "Local fallback selected because external policy is blocked, offline, private, or explicitly requested."
        risk_notes.append("LOCAL_FALLBACK_SELECTED")
    elif request.external_lm_allowed and not request.package_minimized:
        selected = LOCAL_FALLBACK_MODEL
        reason = "External LM blocked because the package is not minimized; local fallback is the only candidate."
        risk_notes.append("PACKAGE_NOT_MINIMIZED")
    elif lane == "LM1_INTENT_PROPOSAL" and request.risk_level in {"low", "medium"} and request.context_size in {"tiny", "small"}:
        selected = FAST_EXTERNAL_INTENT_MODEL if request.external_lm_allowed else LOCAL_FALLBACK_MODEL
        reason = (
            "LM1 intent proposal is privacy-safe; prefer the fast external intent model class."
            if request.external_lm_allowed
            else "LM1 intent proposal has no external eligibility proof; use local fallback."
        )
        confidence = "HIGH"
    elif lane == "LM2_ROLE_RESPONSE" and request.risk_level in {"low", "medium"}:
        selected = STRONG_EXTERNAL_ROLE_MODEL if request.external_lm_allowed else LOCAL_FALLBACK_MODEL
        reason = (
            "LM2 role response is privacy-safe; prefer the strongest external role model class."
            if request.external_lm_allowed
            else "LM2 role response has no external eligibility proof; use local fallback."
        )
        conservative = not request.creative_posture_allowed
        confidence = "HIGH" if request.tokenization_applied and not request.raw_values_included else "MEDIUM"
    elif request.risk_level in {"high", "critical"} or request.sensitivity_level in {"medium", "high", "protected"}:
        selected = LOCAL_ONLY_MODEL if request.strict_private_mode_active else LOCAL_FALLBACK_MODEL
        reason = "High-risk or sensitive package requires conservative structured reasoning."
        confidence = "MEDIUM"
    else:
        blocked.append("UNKNOWN_OR_UNSUPPORTED_MODEL_LANE")

    candidate_ids = (
        FAST_EXTERNAL_INTENT_MODEL,
        STRONG_EXTERNAL_ROLE_MODEL,
        LOCAL_FALLBACK_MODEL,
        LOCAL_ONLY_MODEL,
        FAST_STRUCTURED_INTENT_SMALL,
        STRONG_STRUCTURED_ROLE_REASONER,
        CONSERVATIVE_SENSITIVE_STRUCTURED,
    )
    rejected_model_classes = tuple(model_class for model_class in candidate_ids if model_class != selected)
    if selected == NO_SAFE_MODEL:
        rejected_model_classes = candidate_ids
        confidence = "HIGH" if blocked else "MEDIUM"
    if not expected_failure_modes:
        expected_failure_modes.append("malformed structured output")

    provider_privacy_level = _provider_privacy_level(request)
    provider_selection = provider_policy_registry.select_provider_candidate(
        {
            "request_id": f"{request.request_id}:provider_policy",
            "chain_lane": request.chain_lane,
            "desired_model_class": selected,
            "privacy_level": provider_privacy_level,
            "context_classes": (
                provider_privacy_level,
                "MACHINE_INTENT_PROPOSAL_SCHEMA" if lane == "LM1_INTENT_PROPOSAL" else "MINIMIZED_ROLE_PACKAGE",
            ),
            "tokenization_applied": request.tokenization_applied,
            "raw_values_included": request.raw_values_included,
            "local_only_required": request.local_lm_required
            or request.offline_mode
            or request.strict_private_mode_active
            or provider_privacy_level in {"STRICT_PRIVATE_CLIENT_METADATA"},
            "private_mode_active": request.local_lm_required and provider_privacy_level in {"STRICT_PRIVATE_CLIENT_METADATA"},
            "strict_private_mode_active": request.strict_private_mode_active,
            "requires_structured_output": request.requires_structured_output,
        }
    )
    if selected != NO_SAFE_MODEL and provider_selection["no_safe_model"]:
        selected = NO_SAFE_MODEL
        reason = "Provider policy blocked all model candidates for this request."
        blocked.append("PROVIDER_POLICY_BLOCKED")
    if provider_selection["risk_notes"]:
        risk_notes.extend(str(note) for note in provider_selection["risk_notes"])
    if provider_selection["expected_failure_modes"]:
        expected_failure_modes.extend(str(mode) for mode in provider_selection["expected_failure_modes"])

    decision = ModelRoutingDecision(
        decision_id=f"model_routing_decision:{_short_hash(request.request_id, selected, tuple(blocked))}",
        request_id=request.request_id,
        selected_model_class=selected,
        selected_provider_ref=str(provider_selection.get("selected_provider_ref") or ""),
        selected_model_ref=str(provider_selection.get("selected_model_ref") or ""),
        selected_provider_policy_id=str(provider_selection.get("selected_policy_id") or ""),
        fallback_provider_policy_id=str(provider_selection.get("fallback_policy_id") or ""),
        chain_lane=request.chain_lane,
        selection_reason=f"{reason} Provider policy: {provider_selection['selection_reason']}",
        conservative_posture=conservative,
        structured_output_required=True,
        tokenization_required_before_live=tokenization_required,
        rejected_model_classes=rejected_model_classes,
        rejected_provider_candidates=tuple(provider_selection.get("rejected_candidates") or ()),
        risk_notes=tuple(dict.fromkeys(risk_notes)),
        expected_failure_modes=tuple(dict.fromkeys(expected_failure_modes)),
        confidence=confidence,
        blocked_reasons=tuple(blocked),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move=(
            "Use this model class only as a future candidate route; no model call is allowed in v0."
            if selected != NO_SAFE_MODEL
            else "Do not call a model; resolve the blocked model routing condition first."
        ),
    )
    return asdict(decision)


def select_for_lm1_thread_package(thread_package: Mapping[str, Any]) -> dict[str, Any]:
    privacy = thread_package.get("privacy") if isinstance(thread_package.get("privacy"), Mapping) else {}
    inference = thread_package.get("universal_intake_inference") if isinstance(thread_package.get("universal_intake_inference"), Mapping) else {}
    eligibility = (
        thread_package.get("external_lm_eligibility")
        if isinstance(thread_package.get("external_lm_eligibility"), Mapping)
        else {}
    )
    tokenization_applied = bool(privacy.get("tokenization_applied"))
    raw_values_included = bool(privacy.get("raw_values_included"))
    confidence = str(inference.get("confidence") or "MEDIUM").upper()
    risk = "low" if confidence == "HIGH" and not raw_values_included else "medium"
    sensitivity = str(privacy.get("privacy_level") or "low").lower()
    if eligibility.get("safe_data_classes"):
        safe_classes = {str(item).upper() for item in eligibility.get("safe_data_classes", ())}
        if "TOKENIZED_CLIENT_FINANCE_METADATA" in safe_classes:
            sensitivity = "tokenized_client_finance_metadata"
    if sensitivity in {"tokenized_fixture", "metadata_only_tokenized_refs"}:
        sensitivity = "low"
    return select_model_class(
        {
            "request_id": f"{thread_package.get('package_id', 'lm1_thread_package')}:model_route",
            "chain_lane": "LM1_INTENT_PROPOSAL",
            "task_type": "intent_proposal_from_thread_context",
            "role": "OPENCLAW_SYSTEM",
            "risk_level": risk,
            "sensitivity_level": sensitivity,
            "context_size": "small",
            "requires_structured_output": True,
            "tokenization_applied": tokenization_applied,
            "raw_values_included": raw_values_included,
            "requested_live_authority": False,
            "external_lm_allowed": bool(eligibility.get("external_lm_allowed")),
            "local_lm_required": bool(eligibility.get("local_lm_required")),
            "package_minimized": bool(eligibility.get("package_minimized", True)),
        }
    )


def select_for_lm2_role_package(role_package: Mapping[str, Any]) -> dict[str, Any]:
    role = str(role_package.get("role_identity") or role_package.get("actor_label") or "OPENCLAW_SYSTEM")
    raw_values_included = bool(role_package.get("raw_values_included"))
    tokenization_applied = bool(role_package.get("tokenization_applied"))
    privacy_level = str(role_package.get("privacy_level") or "low").lower()
    eligibility = (
        role_package.get("external_lm_eligibility")
        if isinstance(role_package.get("external_lm_eligibility"), Mapping)
        else {}
    )
    task = str(role_package.get("task") or "").lower()
    risk = "high" if any(term in task for term in ("send", "submit", "paid", "ledger", "approval")) else "medium"
    sensitivity = "high" if privacy_level in {"protected", "sensitive_raw"} else "low"
    if eligibility.get("safe_data_classes"):
        safe_classes = {str(item).upper() for item in eligibility.get("safe_data_classes", ())}
        if "TOKENIZED_CLIENT_FINANCE_METADATA" in safe_classes:
            sensitivity = "tokenized_client_finance_metadata"
    if raw_values_included:
        sensitivity = "protected"
    return select_model_class(
        {
            "request_id": f"{role_package.get('package_id', 'lm2_role_package')}:model_route",
            "chain_lane": "LM2_ROLE_RESPONSE",
            "task_type": "role_response_from_gate3_package",
            "role": role,
            "risk_level": risk,
            "sensitivity_level": sensitivity,
            "context_size": "medium",
            "requires_structured_output": True,
            "tokenization_applied": tokenization_applied,
            "raw_values_included": raw_values_included,
            "requested_live_authority": False,
            "external_lm_allowed": bool(eligibility.get("external_lm_allowed")),
            "local_lm_required": bool(eligibility.get("local_lm_required")),
            "package_minimized": bool(eligibility.get("package_minimized", True)),
        }
    )


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    examples = {
        "lm1_low_risk_intent": select_model_class(
            {
                "request_id": "model_router_fixture_lm1",
                "chain_lane": "LM1_INTENT_PROPOSAL",
                "task_type": "intent_proposal",
                "role": "OPENCLAW_SYSTEM",
                "risk_level": "low",
                "sensitivity_level": "tokenized_client_finance_metadata",
                "context_size": "small",
                "requires_structured_output": True,
                "tokenization_applied": True,
                "raw_values_included": False,
                "external_lm_allowed": True,
                "package_minimized": True,
            }
        ),
        "lm2_role_package": select_model_class(
            {
                "request_id": "model_router_fixture_lm2",
                "chain_lane": "LM2_ROLE_RESPONSE",
                "task_type": "role_response",
                "role": "CASSANDRA",
                "risk_level": "medium",
                "sensitivity_level": "tokenized_client_finance_metadata",
                "context_size": "medium",
                "requires_structured_output": True,
                "tokenization_applied": True,
                "raw_values_included": False,
                "external_lm_allowed": True,
                "package_minimized": True,
            }
        ),
        "local_fallback_when_external_blocked": select_model_class(
            {
                "request_id": "model_router_fixture_local_fallback",
                "chain_lane": "LM2_ROLE_RESPONSE",
                "task_type": "role_response",
                "role": "CASSANDRA",
                "risk_level": "medium",
                "sensitivity_level": "client_finance_file_metadata",
                "context_size": "medium",
                "requires_structured_output": True,
                "tokenization_applied": False,
                "raw_values_included": False,
                "local_lm_required": True,
            }
        ),
        "downgrade_testing_before_baseline": select_model_class(
            {
                "request_id": "model_router_fixture_downgrade_block",
                "chain_lane": "LM2_ROLE_RESPONSE",
                "task_type": "role_response",
                "role": "CASSANDRA",
                "risk_level": "medium",
                "sensitivity_level": "tokenized_client_finance_metadata",
                "context_size": "medium",
                "requires_structured_output": True,
                "tokenization_applied": True,
                "raw_values_included": False,
                "external_lm_allowed": True,
                "package_minimized": True,
                "downgrade_testing_requested": True,
                "baseline_external_passed": False,
            }
        ),
        "sensitive_without_tokenization": select_model_class(
            {
                "request_id": "model_router_fixture_sensitive",
                "chain_lane": "LM2_ROLE_RESPONSE",
                "task_type": "protected_boundary_response",
                "role": "GUARDIAN",
                "risk_level": "high",
                "sensitivity_level": "high",
                "context_size": "medium",
                "requires_structured_output": True,
                "tokenization_applied": False,
            }
        ),
        "lm1_thread_package": select_for_lm1_thread_package(
            {
                "package_id": "model_router_fixture_lm1_thread_package",
                "universal_intake_inference": {"confidence": "HIGH"},
                "privacy": {
                    "tokenization_applied": True,
                    "raw_values_included": False,
                    "privacy_level": "CLIENT_FINANCE_FILE_METADATA",
                },
                "external_lm_eligibility": {
                    "external_lm_allowed": True,
                    "local_lm_required": False,
                    "package_minimized": True,
                    "safe_data_classes": ("TOKENIZED_CLIENT_FINANCE_METADATA",),
                },
            }
        ),
        "lm2_role_package_integrated": select_for_lm2_role_package(
            {
                "package_id": "model_router_fixture_lm2_role_package",
                "role_identity": "CASSANDRA_CLARA",
                "task": "Prepare invoice package readback only.",
                "tokenization_applied": True,
                "raw_values_included": False,
                "privacy_level": "CLIENT_FINANCE_FILE_METADATA",
                "external_lm_eligibility": {
                    "external_lm_allowed": True,
                    "local_lm_required": False,
                    "package_minimized": True,
                    "safe_data_classes": ("TOKENIZED_CLIENT_FINANCE_METADATA",),
                },
            }
        ),
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "model_candidate_classes": tuple(asdict(item) for item in model_candidate_classes()),
        "provider_policy_registry_ref": "generated/read_models/provider_policy_registry.json",
        "provider_policy_examples": provider_policy_registry.build_payload(generated_at=generated_at)["examples"],
        "examples": examples,
        "connects_to_chain": {
            "lm1": "Model class selection may feed a future LM1 proposal socket before Gate 2.",
            "lm2": "Model class selection may feed a future LM2 role package socket after Gate 3.",
            "authority": "The router cannot grant authority; Gate 2/Gate 4 still decide boundaries.",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "model_call_performed": False,
            "network_performed": False,
            "provider_key_material_access_performed": False,
            "authority_granted": False,
            "provider_policy_consulted": bool(examples["lm1_low_risk_intent"]["selected_provider_policy_id"]),
            "lm1_example_selects_fast_class": examples["lm1_low_risk_intent"]["selected_model_class"] == FAST_EXTERNAL_INTENT_MODEL,
            "lm2_example_selects_stronger_class": examples["lm2_role_package"]["selected_model_class"] == STRONG_EXTERNAL_ROLE_MODEL,
            "lm1_provider_policy_selected": bool(examples["lm1_low_risk_intent"]["selected_provider_ref"]),
            "lm2_provider_policy_selected": bool(examples["lm2_role_package"]["selected_provider_ref"]),
            "local_fallback_selected_when_external_blocked": examples["local_fallback_when_external_blocked"][
                "selected_model_class"
            ]
            == LOCAL_FALLBACK_MODEL,
            "downgrade_testing_blocked_before_baseline": "LOCAL_DOWNGRADE_TESTING_BLOCKED_UNTIL_EXTERNAL_BASELINE_PASSES"
            in examples["downgrade_testing_before_baseline"]["risk_notes"],
            "lm1_thread_package_selects_fast_class": examples["lm1_thread_package"]["selected_model_class"] == FAST_EXTERNAL_INTENT_MODEL,
            "lm2_role_package_integrated_selects_class": examples["lm2_role_package_integrated"]["selected_model_class"]
            in {STRONG_EXTERNAL_ROLE_MODEL, LOCAL_FALLBACK_MODEL},
            "sensitive_example_blocks_without_tokenization": examples["sensitive_without_tokenization"]["selected_model_class"] == NO_SAFE_MODEL,
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
        "# Model Router Policy",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"LM1 fast class selected: {str(proof.get('lm1_example_selects_fast_class')).lower()}",
        f"LM2 strong class selected: {str(proof.get('lm2_example_selects_stronger_class')).lower()}",
        f"Sensitive no-tokenization block: {str(proof.get('sensitive_example_blocks_without_tokenization')).lower()}",
        "",
        "This is a model-class policy only. It does not call models or grant authority.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export model router policy read-model.")
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)

    payload = build_payload(generated_at=args.generated_at)
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
                    "lm1_model_class": payload["examples"]["lm1_low_risk_intent"]["selected_model_class"],
                    "lm2_model_class": payload["examples"]["lm2_role_package"]["selected_model_class"],
                    "sensitive_model_class": payload["examples"]["sensitive_without_tokenization"]["selected_model_class"],
                    "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

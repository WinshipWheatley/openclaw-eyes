"""Provider Policy Registry v0.

Deterministic registry for future LM provider/model-class candidates. This file
does not name vendor dependencies, call models, load API keys, or grant
authority. It only describes which provider classes are policy-compatible with
LM1/LM2 package shapes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import provider_lanes


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT = "2026-05-26T00:00:00+00:00"

SCHEMA_VERSION = "provider_policy_registry_v0"
READ_MODEL_ID = "provider_policy_registry"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "PROVIDER_POLICY_REGISTRY_NO_LIVE_CALLS"

NO_SAFE_MODEL = "NO_SAFE_MODEL"
FAST_EXTERNAL_INTENT_MODEL = "FAST_EXTERNAL_INTENT_MODEL"
STRONG_EXTERNAL_ROLE_MODEL = "STRONG_EXTERNAL_ROLE_MODEL"
LOCAL_FALLBACK_MODEL = "LOCAL_FALLBACK_MODEL"
LOCAL_ONLY_MODEL = "LOCAL_ONLY_MODEL"
FAST_STRUCTURED_INTENT_SMALL = "FAST_STRUCTURED_INTENT_SMALL"
STRONG_STRUCTURED_ROLE_REASONER = "STRONG_STRUCTURED_ROLE_REASONER"
CONSERVATIVE_SENSITIVE_STRUCTURED = "CONSERVATIVE_SENSITIVE_STRUCTURED"

PROVIDER_CLASS_FAST_INTENT = "provider_class:external_privacy_safe_fast_intent"
PROVIDER_CLASS_ROLE_REASONER = "provider_class:external_privacy_safe_role_reasoner"
PROVIDER_CLASS_LOCAL = "provider_class:local_or_private_fallback_model"
PROVIDER_CLASS_NONE = ""

SENSITIVE_REQUIRE_LOCAL = frozenset(
    {
        "RAW_PRIVATE_BODY",
        "RAW_SECRET",
        "CREDENTIAL_MATERIAL",
        "STRICT_PRIVATE_CLIENT_METADATA",
        "LEGAL_PRIVILEGED_RAW",
        "HEALTH_RAW",
    }
)

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
class ProviderPolicyRecord:
    policy_id: str
    provider_ref: str
    model_ref: str
    model_class_ref: str
    lane_allowed: tuple[str, ...]
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    structured_output_reliability: str
    long_context_strength: str
    creative_strength: str
    conservative_reasoning_strength: str
    privacy_risk_level: str
    allowed_context_classes: tuple[str, ...]
    forbidden_context_classes: tuple[str, ...]
    cloud_allowed: bool
    local_only: bool
    cost_tier: str
    latency_tier: str
    default_use_cases: tuple[str, ...]
    blocked_use_cases: tuple[str, ...]
    expected_failure_modes: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class ProviderCandidateEvaluation:
    policy_id: str
    provider_ref: str
    model_ref: str
    model_class_ref: str
    usable: bool
    reject_reasons: tuple[str, ...]
    expected_failure_modes: tuple[str, ...]
    weaknesses: tuple[str, ...]


@dataclass(frozen=True)
class ProviderPolicySelection:
    selection_id: str
    request_id: str
    selected_policy_id: str
    selected_provider_ref: str
    selected_model_ref: str
    selected_model_class: str
    fallback_policy_id: str
    selected_lane_id: str
    fallback_lane_id: str
    selected_candidate_id: str
    rejected_candidates: tuple[dict[str, Any], ...]
    selection_reason: str
    risk_notes: tuple[str, ...]
    expected_failure_modes: tuple[str, ...]
    no_safe_model: bool
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


def provider_policy_records() -> tuple[ProviderPolicyRecord, ...]:
    return (
        ProviderPolicyRecord(
            policy_id="provider_policy:external_fast_intent_privacy_safe",
            provider_ref="provider_class:external_privacy_safe_fast_intent",
            model_ref="model_class:fast_external_intent_model",
            model_class_ref=FAST_EXTERNAL_INTENT_MODEL,
            lane_allowed=("LM1_INTENT_PROPOSAL",),
            strengths=("fast intent proposal", "strong structured JSON", "cheap external reasoning", "narrow classification"),
            weaknesses=("must receive minimized/tokenized context", "no tools", "no direct authority", "provider receipts required before production"),
            structured_output_reliability="high_required",
            long_context_strength="low",
            creative_strength="low",
            conservative_reasoning_strength="medium",
            privacy_risk_level="acceptable_only_when_tokenized_minimized",
            allowed_context_classes=(
                "LOW_METADATA",
                "TOKENIZED_METADATA",
                "TOKENIZED_CLIENT_FINANCE_METADATA",
                "TOKENIZED_PERSONAL_FINANCE_METADATA",
                "TOKENIZED_LEGAL_DISCOVERY_METADATA",
                "TOKENIZED_SENSITIVE_METADATA",
                "MACHINE_INTENT_PROPOSAL_SCHEMA",
            ),
            forbidden_context_classes=(
                "CLIENT_FINANCE_FILE_METADATA",
                "STRICT_PRIVATE_CLIENT_METADATA",
                "RAW_PRIVATE_BODY",
                "RAW_SECRET",
                "CREDENTIAL_MATERIAL",
                "UNMINIMIZED_CLIENT_CONTEXT",
                "UNRELATED_CLIENT_DATA",
            ),
            cloud_allowed=True,
            local_only=False,
            cost_tier="low",
            latency_tier="low",
            default_use_cases=("future LM1 MachineIntentCandidate proposal", "privacy-safe intent classification"),
            blocked_use_cases=("tool execution", "authority grant", "raw private body reasoning", "strict private mode"),
            expected_failure_modes=("malformed MachineIntentCandidate", "under-specified intent", "privacy-policy refusal"),
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Use as the preferred future LM1 class only after Gate 1 minimizes/tokenizes the package and receipts exist.",
        ),
        ProviderPolicyRecord(
            policy_id="provider_policy:external_strong_role_privacy_safe",
            provider_ref="provider_class:external_privacy_safe_role_reasoner",
            model_ref="model_class:strong_external_role_model",
            model_class_ref=STRONG_EXTERNAL_ROLE_MODEL,
            lane_allowed=("LM2_ROLE_RESPONSE",),
            strengths=("strong package reasoning", "nuanced role voice", "structured response", "longer context synthesis"),
            weaknesses=("higher cost", "must be Guardian-gated", "must receive minimized/tokenized package", "provider receipts required before production"),
            structured_output_reliability="high_required",
            long_context_strength="high",
            creative_strength="medium",
            conservative_reasoning_strength="high",
            privacy_risk_level="acceptable_only_when_tokenized_minimized",
            allowed_context_classes=(
                "LOW_METADATA",
                "TOKENIZED_METADATA",
                "TOKENIZED_CLIENT_FINANCE_METADATA",
                "TOKENIZED_PERSONAL_FINANCE_METADATA",
                "TOKENIZED_LEGAL_DISCOVERY_METADATA",
                "TOKENIZED_SENSITIVE_METADATA",
                "MINIMIZED_ROLE_PACKAGE",
            ),
            forbidden_context_classes=(
                "CLIENT_FINANCE_FILE_METADATA",
                "STRICT_PRIVATE_CLIENT_METADATA",
                "RAW_PRIVATE_BODY",
                "RAW_SECRET",
                "CREDENTIAL_MATERIAL",
                "UNMINIMIZED_CLIENT_CONTEXT",
                "UNRELATED_CLIENT_DATA",
            ),
            cloud_allowed=True,
            local_only=False,
            cost_tier="higher",
            latency_tier="medium",
            default_use_cases=("future LM2 role response", "Cassandra/Clara/Chief bounded package reasoning"),
            blocked_use_cases=("send/submit", "ledger posting", "credential use", "raw private body reasoning"),
            expected_failure_modes=("over-helpful completion claim", "role drift", "tool request outside package"),
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Use as the preferred future LM2 class only after Gate 3 compiles a minimized package and Gate 4 remains required.",
        ),
        ProviderPolicyRecord(
            policy_id="provider_policy:local_fallback_structured",
            provider_ref="provider_class:local_or_private_fallback_model",
            model_ref="model_class:local_fallback_model",
            model_class_ref=LOCAL_FALLBACK_MODEL,
            lane_allowed=("LM1_INTENT_PROPOSAL", "LM2_ROLE_RESPONSE"),
            strengths=("offline fallback", "credit-saving smoke tests", "local shadow comparison", "private-mode fallback"),
            weaknesses=("not the production-quality target", "weaker reasoning than preferred external classes"),
            structured_output_reliability="high_required",
            long_context_strength="medium",
            creative_strength="low",
            conservative_reasoning_strength="medium",
            privacy_risk_level="low_when_local_only",
            allowed_context_classes=(
                "LOW_METADATA",
                "CLIENT_FINANCE_FILE_METADATA",
                "TOKENIZED_METADATA",
                "TOKENIZED_CLIENT_FINANCE_METADATA",
                "MINIMIZED_ROLE_PACKAGE",
            ),
            forbidden_context_classes=("RAW_SECRET", "CREDENTIAL_MATERIAL", "UNRELATED_CLIENT_DATA"),
            cloud_allowed=False,
            local_only=True,
            cost_tier="low_local",
            latency_tier="variable_local",
            default_use_cases=("offline fallback", "local shadow smoke", "external policy blocked package"),
            blocked_use_cases=("production-quality external baseline replacement", "credential use", "direct execution"),
            expected_failure_modes=("lower-quality reasoning", "malformed JSON candidate", "over-clarification"),
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Use only as fallback/offline/shadow path; prefer external classes when privacy controls allow them.",
        ),
        ProviderPolicyRecord(
            policy_id="provider_policy:local_only_private",
            provider_ref="provider_class:local_or_private_strict_local_model",
            model_ref="model_class:local_only_model",
            model_class_ref=LOCAL_ONLY_MODEL,
            lane_allowed=("LM1_INTENT_PROPOSAL", "LM2_ROLE_RESPONSE"),
            strengths=("strict local handling", "private-mode posture", "no cloud exposure"),
            weaknesses=("not the production-quality external target", "may underperform strong external reasoning"),
            structured_output_reliability="strict_required",
            long_context_strength="medium",
            creative_strength="low",
            conservative_reasoning_strength="high",
            privacy_risk_level="lowest_when_local_only",
            allowed_context_classes=(
                "LOW_METADATA",
                "CLIENT_FINANCE_FILE_METADATA",
                "TOKENIZED_METADATA",
                "STRICT_PRIVATE_CLIENT_METADATA",
                "LEGAL_PRIVILEGED_METADATA",
            ),
            forbidden_context_classes=("RAW_SECRET", "CREDENTIAL_MATERIAL", "UNRELATED_CLIENT_DATA"),
            cloud_allowed=False,
            local_only=True,
            cost_tier="low_local",
            latency_tier="variable_local",
            default_use_cases=("strict private mode", "legal/local-only posture", "policy-blocked external context"),
            blocked_use_cases=("cloud route", "provider API call", "credential use", "direct execution"),
            expected_failure_modes=("false block", "unnecessary clarification", "weaker synthesis"),
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Use when policy requires local-only handling; still no live production authority.",
        ),
        ProviderPolicyRecord(
            policy_id="provider_policy:local_fixture_fast_intent",
            provider_ref="provider_class:local_or_private_structured_stub",
            model_ref="model_class:fast_structured_intent_small",
            model_class_ref=FAST_STRUCTURED_INTENT_SMALL,
            lane_allowed=("LM1_INTENT_PROPOSAL",),
            strengths=("low latency", "cheap", "strict JSON", "narrow intent proposal"),
            weaknesses=("not enough for nuanced role voice", "not for broad context synthesis"),
            structured_output_reliability="high_required",
            long_context_strength="low",
            creative_strength="low",
            conservative_reasoning_strength="medium",
            privacy_risk_level="low_when_tokenized",
            allowed_context_classes=("LOW_METADATA", "CLIENT_FINANCE_FILE_METADATA", "TOKENIZED_METADATA"),
            forbidden_context_classes=("RAW_PRIVATE_BODY", "RAW_SECRET", "UNRELATED_CLIENT_DATA"),
            cloud_allowed=False,
            local_only=True,
            cost_tier="low",
            latency_tier="low",
            default_use_cases=("LM1 intent proposal", "classification", "contract-shaped JSON"),
            blocked_use_cases=("send authority", "direct execution", "raw private body reasoning"),
            expected_failure_modes=("under-specified intent", "malformed JSON candidate"),
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Use as future LM1 candidate only after Gate 1 packages metadata safely.",
        ),
        ProviderPolicyRecord(
            policy_id="provider_policy:local_fixture_strong_role",
            provider_ref="provider_class:local_or_private_role_reasoner_stub",
            model_ref="model_class:strong_structured_role_reasoner",
            model_class_ref=STRONG_STRUCTURED_ROLE_REASONER,
            lane_allowed=("LM2_ROLE_RESPONSE",),
            strengths=("role reasoning", "operator wording", "bounded package following", "structured response"),
            weaknesses=("higher latency than LM1 class", "requires Guardian output gate"),
            structured_output_reliability="high_required",
            long_context_strength="medium",
            creative_strength="medium",
            conservative_reasoning_strength="medium",
            privacy_risk_level="low_when_tokenized",
            allowed_context_classes=("LOW_METADATA", "CLIENT_FINANCE_FILE_METADATA", "TOKENIZED_METADATA"),
            forbidden_context_classes=("RAW_PRIVATE_BODY", "RAW_SECRET", "UNRELATED_CLIENT_DATA"),
            cloud_allowed=False,
            local_only=True,
            cost_tier="medium",
            latency_tier="medium",
            default_use_cases=("LM2 role response", "Cassandra/Chief/Niles wording", "package readback"),
            blocked_use_cases=("tool execution", "send/submit", "ledger posting"),
            expected_failure_modes=("over-helpful completion claim", "tool request outside package"),
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Use as future LM2 package candidate only after Gate 3 compiles bounded context.",
        ),
        ProviderPolicyRecord(
            policy_id="provider_policy:local_fixture_conservative_sensitive",
            provider_ref="provider_class:local_or_private_conservative_stub",
            model_ref="model_class:conservative_sensitive_structured",
            model_class_ref=CONSERVATIVE_SENSITIVE_STRUCTURED,
            lane_allowed=("LM1_INTENT_PROPOSAL", "LM2_ROLE_RESPONSE"),
            strengths=("policy-heavy reasoning", "privacy caution", "fail-closed posture"),
            weaknesses=("may over-clarify", "higher latency", "less warm voice"),
            structured_output_reliability="strict_required",
            long_context_strength="medium",
            creative_strength="low",
            conservative_reasoning_strength="high",
            privacy_risk_level="lowest_when_local_only",
            allowed_context_classes=("LOW_METADATA", "CLIENT_FINANCE_FILE_METADATA", "TOKENIZED_METADATA", "STRICT_PRIVATE_CLIENT_METADATA"),
            forbidden_context_classes=("RAW_PRIVATE_BODY", "RAW_SECRET", "UNRELATED_CLIENT_DATA"),
            cloud_allowed=False,
            local_only=True,
            cost_tier="medium",
            latency_tier="medium_high",
            default_use_cases=("strict private candidate", "protected boundary explanation", "sensitive clarification"),
            blocked_use_cases=("direct execution", "external action authority", "credential use"),
            expected_failure_modes=("false block", "unnecessary clarification"),
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Use only for tokenized/private packages; still no live call in this lane.",
        ),
        ProviderPolicyRecord(
            policy_id="provider_policy:future_cloud_structured_candidate",
            provider_ref="provider_class:future_cloud_structured_candidate",
            model_ref="model_class:cloud_structured_candidate",
            model_class_ref=STRONG_STRUCTURED_ROLE_REASONER,
            lane_allowed=("LM1_INTENT_PROPOSAL", "LM2_ROLE_RESPONSE"),
            strengths=("large ecosystem", "possible strong reasoning", "possible long context"),
            weaknesses=("privacy policy must be explicit", "network/API key path required", "cannot be used in private mode by default"),
            structured_output_reliability="unknown_until_shadowed",
            long_context_strength="unknown_until_policy_receipt",
            creative_strength="unknown_until_policy_receipt",
            conservative_reasoning_strength="unknown_until_policy_receipt",
            privacy_risk_level="high_without_explicit_policy",
            allowed_context_classes=("LOW_METADATA", "TOKENIZED_METADATA"),
            forbidden_context_classes=("CLIENT_FINANCE_FILE_METADATA", "STRICT_PRIVATE_CLIENT_METADATA", "RAW_PRIVATE_BODY", "RAW_SECRET"),
            cloud_allowed=True,
            local_only=False,
            cost_tier="unknown",
            latency_tier="unknown",
            default_use_cases=("future shadow comparison only",),
            blocked_use_cases=("private mode", "strict private mode", "client finance metadata without future policy"),
            expected_failure_modes=("privacy policy block", "provider unavailability", "schema drift"),
            authority_boundary=dict(AUTHORITY_BOUNDARY),
            next_safe_move="Keep parked until provider/privacy policy receipts exist; do not call.",
        ),
    )


def _normalize_context_classes(context: Mapping[str, Any]) -> tuple[str, ...]:
    values = context.get("context_classes", ())
    if isinstance(values, str):
        return (values.upper(),)
    if isinstance(values, (list, tuple)):
        return tuple(str(value).upper() for value in values if value)
    privacy = str(context.get("privacy_level") or context.get("sensitivity_level") or "LOW_METADATA").upper()
    return (privacy,)


def _evaluate_record(record: ProviderPolicyRecord, request: Mapping[str, Any]) -> ProviderCandidateEvaluation:
    lane = str(request.get("chain_lane") or "").upper()
    desired_class = str(request.get("desired_model_class") or request.get("selected_model_class") or "").upper()
    privacy_level = str(request.get("privacy_level") or request.get("sensitivity_level") or "LOW_METADATA").upper()
    context_classes = set(_normalize_context_classes({**request, "privacy_level": privacy_level}))
    raw_values_included = bool(request.get("raw_values_included", False))
    private_mode_active = bool(request.get("private_mode_active", False))
    strict_private_mode_active = bool(request.get("strict_private_mode_active", False))
    local_only_required = bool(request.get("local_only_required", False))
    requires_structured_output = bool(request.get("requires_structured_output", True))

    reasons: list[str] = []
    if lane not in record.lane_allowed:
        reasons.append("LANE_NOT_ALLOWED")
    if desired_class and desired_class != NO_SAFE_MODEL and desired_class != record.model_class_ref:
        reasons.append("MODEL_CLASS_NOT_REQUESTED")
    if requires_structured_output and record.structured_output_reliability not in {"high_required", "strict_required"}:
        reasons.append("STRUCTURED_OUTPUT_RELIABILITY_NOT_PROVEN")
    if raw_values_included:
        reasons.append("RAW_VALUES_NOT_ALLOWED")
    if local_only_required and not record.local_only:
        reasons.append("LOCAL_ONLY_REQUIRED")
    if private_mode_active and record.cloud_allowed:
        reasons.append("PRIVATE_MODE_BLOCKS_CLOUD")
    if strict_private_mode_active and not record.local_only:
        reasons.append("STRICT_PRIVATE_REQUIRES_LOCAL_ONLY")
    if privacy_level in record.forbidden_context_classes:
        reasons.append("PRIVACY_CLASS_FORBIDDEN")
    if context_classes.intersection(set(record.forbidden_context_classes)):
        reasons.append("CONTEXT_CLASS_FORBIDDEN")
    if not context_classes.intersection(set(record.allowed_context_classes)):
        reasons.append("NO_ALLOWED_CONTEXT_CLASS_MATCH")

    return ProviderCandidateEvaluation(
        policy_id=record.policy_id,
        provider_ref=record.provider_ref,
        model_ref=record.model_ref,
        model_class_ref=record.model_class_ref,
        usable=not reasons,
        reject_reasons=tuple(dict.fromkeys(reasons)),
        expected_failure_modes=record.expected_failure_modes,
        weaknesses=record.weaknesses,
    )


def select_provider_candidate(request: Mapping[str, Any]) -> dict[str, Any]:
    request_id = str(request.get("request_id") or "provider_policy_request")
    lane = str(request.get("chain_lane") or "").upper()
    desired_class = str(request.get("desired_model_class") or request.get("selected_model_class") or "").upper()
    privacy_level = str(request.get("privacy_level") or request.get("sensitivity_level") or "LOW_METADATA").upper()
    context_classes = _normalize_context_classes({**request, "privacy_level": privacy_level})
    tokenization_applied = bool(request.get("tokenization_applied", False))
    raw_values_included = bool(request.get("raw_values_included", False))
    local_only_required = bool(request.get("local_only_required", False))
    private_mode_active = bool(request.get("private_mode_active", False))
    strict_private_mode_active = bool(request.get("strict_private_mode_active", False))
    requires_structured_output = bool(request.get("requires_structured_output", True))

    risk_notes: list[str] = []
    if raw_values_included:
        risk_notes.append("RAW_VALUES_INCLUDED")
    if private_mode_active:
        risk_notes.append("PRIVATE_MODE_ACTIVE")
    if strict_private_mode_active:
        risk_notes.append("STRICT_PRIVATE_MODE_ACTIVE")
    if privacy_level in {"CLIENT_FINANCE_FILE_METADATA", "STRICT_PRIVATE_CLIENT_METADATA"}:
        risk_notes.append("CLIENT_PRIVACY_POLICY")

    def _base_selection(
        *,
        selected_provider_ref: str,
        selected_model_ref: str,
        selected_model_class: str,
        selected_lane_id: str,
        selected_candidate_id: str,
        fallback_lane_id: str = "",
        fallback_candidate_id: str = "",
        rejected_candidates: tuple[dict[str, Any], ...] = (),
        selection_reason: str,
        expected_failure_modes: tuple[str, ...],
        no_safe_model: bool = False,
    ) -> dict[str, Any]:
        selected_policy_id = f"provider_policy:{selected_lane_id}:{privacy_level}" if not no_safe_model else ""
        fallback_policy_id = f"provider_policy:{fallback_lane_id}:{privacy_level}" if fallback_lane_id else ""
        return {
            "selection_id": f"provider_policy_selection:{_short_hash(request_id, selected_policy_id or selected_model_class)}",
            "request_id": request_id,
            "selected_policy_id": selected_policy_id,
            "selected_provider_ref": selected_provider_ref,
            "selected_model_ref": selected_model_ref,
            "selected_model_class": selected_model_class,
            "fallback_policy_id": fallback_policy_id,
            "selected_lane_id": selected_lane_id,
            "fallback_lane_id": fallback_lane_id,
            "selected_candidate_id": selected_candidate_id,
            "fallback_candidate_id": fallback_candidate_id,
            "rejected_candidates": rejected_candidates,
            "selection_reason": selection_reason,
            "risk_notes": tuple(dict.fromkeys(risk_notes)),
            "expected_failure_modes": expected_failure_modes,
            "no_safe_model": no_safe_model,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
            "next_safe_move": (
                "Do not call a model; resolve provider/privacy policy first."
                if no_safe_model
                else "Expose this as candidate policy only; no live model call is allowed."
            ),
        }

    def _local_selection(reason: str, rejected: tuple[dict[str, Any], ...] = ()) -> dict[str, Any]:
        return _base_selection(
            selected_provider_ref=PROVIDER_CLASS_LOCAL,
            selected_model_ref="",
            selected_model_class=LOCAL_FALLBACK_MODEL,
            selected_lane_id="local_only",
            selected_candidate_id=provider_lanes.LOCAL_FLOOR_CANDIDATE,
            selection_reason=reason,
            rejected_candidates=rejected,
            expected_failure_modes=("lower-quality local reasoning", "malformed structured output"),
        )

    def _no_safe(reason: str, rejected: tuple[dict[str, Any], ...] = ()) -> dict[str, Any]:
        return _base_selection(
            selected_provider_ref=PROVIDER_CLASS_NONE,
            selected_model_ref="",
            selected_model_class=NO_SAFE_MODEL,
            selected_lane_id="",
            selected_candidate_id="",
            selection_reason=reason,
            rejected_candidates=rejected,
            expected_failure_modes=("privacy gate blocks live provider route", "provider policy block"),
            no_safe_model=True,
        )

    external_desired = desired_class in {FAST_EXTERNAL_INTENT_MODEL, STRONG_EXTERNAL_ROLE_MODEL}
    if desired_class == NO_SAFE_MODEL:
        return _no_safe(
            "Requested model class is NO_SAFE_MODEL.",
            rejected=({"candidate_id": "all", "reason": "NO_SAFE_MODEL_REQUESTED"},),
        )

    force_local = (
        privacy_level in SENSITIVE_REQUIRE_LOCAL
        or privacy_level not in provider_lanes.KNOWN_EXTERNAL_OK_LEVELS
        or local_only_required
        or strict_private_mode_active
        or desired_class in {LOCAL_FALLBACK_MODEL, LOCAL_ONLY_MODEL}
    )
    if force_local:
        reason = (
            "FORCED_LOCAL_LABEL_NOT_ALLOWLISTED"
            if privacy_level not in provider_lanes.KNOWN_EXTERNAL_OK_LEVELS and desired_class not in {LOCAL_FALLBACK_MODEL, LOCAL_ONLY_MODEL}
            else "FORCED_LOCAL_SENSITIVE_OR_PRIVATE"
        )
        rejected: list[dict[str, Any]] = []
        if external_desired:
            lane_id = "fast" if desired_class == FAST_EXTERNAL_INTENT_MODEL else "balanced"
            for candidate_id in provider_lanes.lane_candidates(lane_id):
                cand = provider_lanes.get_candidate(candidate_id)
                if cand and cand.is_cloud:
                    rejected.append({"candidate_id": candidate_id, "reason": "PRIVACY_CEILING_EXCEEDED"})
        return _local_selection(reason, tuple(rejected))

    if external_desired and not tokenization_applied and privacy_level != "LOW_METADATA":
        return _no_safe(
            "TOKENIZATION_REQUIRED_BEFORE_PROVIDER",
            rejected=({"candidate_id": "external_provider_class", "reason": "TOKENIZATION_REQUIRED_BEFORE_PROVIDER"},),
        )

    if desired_class in {LOCAL_FALLBACK_MODEL, LOCAL_ONLY_MODEL}:
        return _local_selection("FORCED_LOCAL_MODEL_CLASS_REQUESTED")

    if desired_class == FAST_EXTERNAL_INTENT_MODEL:
        selected_provider_ref = PROVIDER_CLASS_FAST_INTENT
        selected_model_class = FAST_EXTERNAL_INTENT_MODEL
        lane_id = "fast"
        ordered = (
            provider_lanes.DEFAULT_FAST_EXTERNAL_CANDIDATE,
            "codex_exec",
            "local_qwen_fast",
        )
    elif desired_class == STRONG_EXTERNAL_ROLE_MODEL:
        selected_provider_ref = PROVIDER_CLASS_ROLE_REASONER
        selected_model_class = STRONG_EXTERNAL_ROLE_MODEL
        code_hint = requires_structured_output and any("CODE" in value.upper() for value in context_classes)
        lane_id = "code" if code_hint else "balanced"
        ordered = (
            provider_lanes.DEFAULT_CODE_CANDIDATE,
            "claude_cli",
            "local_deep",
        ) if code_hint else (
            provider_lanes.DEFAULT_STRONG_EXTERNAL_CANDIDATE,
            "kimi_openrouter",
            "local_qwen_strong",
        )
    else:
        return _local_selection("UNRECOGNIZED_CLASS_FALLS_BACK_LOCAL")

    selected_candidate_id = ""
    for candidate_id in ordered:
        cand = provider_lanes.get_candidate(candidate_id)
        if cand and provider_lanes.rank(privacy_level) <= provider_lanes.rank(cand.max_privacy_level):
            selected_candidate_id = candidate_id
            break
    if not selected_candidate_id:
        return _local_selection(
            "CLOUD_CEILING_REJECTED_ALL_CANDIDATES",
            tuple({"candidate_id": candidate_id, "reason": "PRIVACY_CEILING_EXCEEDED"} for candidate_id in ordered),
        )

    selected_candidate = provider_lanes.get_candidate(selected_candidate_id)
    assert selected_candidate is not None
    if not selected_candidate.is_cloud:
        selected_provider_ref = PROVIDER_CLASS_LOCAL
        selected_model_class = LOCAL_FALLBACK_MODEL

    rejected: list[dict[str, Any]] = []
    for candidate_id in ordered:
        cand = provider_lanes.get_candidate(candidate_id)
        if cand is None:
            continue
        if provider_lanes.rank(privacy_level) > provider_lanes.rank(cand.max_privacy_level):
            rejected.append({"candidate_id": candidate_id, "reason": "PRIVACY_CEILING_EXCEEDED"})
            continue
        if candidate_id == selected_candidate_id:
            if cand.is_cloud and not cand.dispatch_enabled:
                rejected.append({"candidate_id": candidate_id, "reason": "DISPATCH_DISABLED_P0"})
            continue
        rejected.append({"candidate_id": candidate_id, "reason": "NOT_PRIMARY_PICK"})

    fallback_candidate_id = ""
    for candidate_id in ordered:
        if candidate_id != selected_candidate_id:
            fallback_candidate_id = candidate_id
            break

    return _base_selection(
        selected_provider_ref=selected_provider_ref,
        selected_model_ref=selected_candidate.model_ref if selected_candidate.is_cloud else "",
        selected_model_class=selected_model_class,
        selected_lane_id=lane_id,
        selected_candidate_id=selected_candidate_id,
        fallback_lane_id=lane_id if fallback_candidate_id else "",
        fallback_candidate_id=fallback_candidate_id,
        rejected_candidates=tuple(rejected),
        selection_reason="Selected model-agnostic lane candidate by privacy ceiling and policy class.",
        expected_failure_modes=("malformed structured output", "provider refusal", "local fallback lower quality"),
    )


def build_payload(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or DEFAULT_GENERATED_AT
    examples = {
        "lm1_intent_policy": select_provider_candidate(
            {
                "request_id": "provider_policy_fixture_lm1",
                "chain_lane": "LM1_INTENT_PROPOSAL",
                "desired_model_class": FAST_EXTERNAL_INTENT_MODEL,
                "privacy_level": "TOKENIZED_CLIENT_FINANCE_METADATA",
                "context_classes": ("TOKENIZED_CLIENT_FINANCE_METADATA", "MACHINE_INTENT_PROPOSAL_SCHEMA"),
                "tokenization_applied": True,
                "raw_values_included": False,
                "local_only_required": False,
                "requires_structured_output": True,
            }
        ),
        "lm2_role_policy": select_provider_candidate(
            {
                "request_id": "provider_policy_fixture_lm2",
                "chain_lane": "LM2_ROLE_RESPONSE",
                "desired_model_class": STRONG_EXTERNAL_ROLE_MODEL,
                "privacy_level": "TOKENIZED_CLIENT_FINANCE_METADATA",
                "context_classes": ("TOKENIZED_CLIENT_FINANCE_METADATA", "MINIMIZED_ROLE_PACKAGE"),
                "tokenization_applied": True,
                "raw_values_included": False,
                "local_only_required": False,
                "requires_structured_output": True,
            }
        ),
        "local_fallback_policy": select_provider_candidate(
            {
                "request_id": "provider_policy_fixture_local_fallback",
                "chain_lane": "LM2_ROLE_RESPONSE",
                "desired_model_class": LOCAL_FALLBACK_MODEL,
                "privacy_level": "CLIENT_FINANCE_FILE_METADATA",
                "context_classes": ("CLIENT_FINANCE_FILE_METADATA",),
                "tokenization_applied": False,
                "raw_values_included": False,
                "local_only_required": True,
                "requires_structured_output": True,
            }
        ),
        "private_cloud_block": select_provider_candidate(
            {
                "request_id": "provider_policy_fixture_private_cloud_block",
                "chain_lane": "LM2_ROLE_RESPONSE",
                "desired_model_class": STRONG_EXTERNAL_ROLE_MODEL,
                "privacy_level": "STRICT_PRIVATE_CLIENT_METADATA",
                "context_classes": ("STRICT_PRIVATE_CLIENT_METADATA",),
                "tokenization_applied": True,
                "raw_values_included": False,
                "private_mode_active": True,
                "strict_private_mode_active": True,
                "local_only_required": True,
                "requires_structured_output": True,
            }
        ),
        "raw_values_block": select_provider_candidate(
            {
                "request_id": "provider_policy_fixture_raw_block",
                "chain_lane": "LM2_ROLE_RESPONSE",
                "desired_model_class": STRONG_EXTERNAL_ROLE_MODEL,
                "privacy_level": "TOKENIZED_CLIENT_FINANCE_METADATA",
                "context_classes": ("TOKENIZED_CLIENT_FINANCE_METADATA",),
                "tokenization_applied": False,
                "raw_values_included": True,
                "requires_structured_output": True,
            }
        ),
        "unknown_label_force_local": select_provider_candidate(
            {
                "request_id": "provider_policy_fixture_unknown_label",
                "chain_lane": "LM1_INTENT_PROPOSAL",
                "desired_model_class": FAST_EXTERNAL_INTENT_MODEL,
                "privacy_level": "CLIENT_FINANCE_FILE_METADATA",
                "context_classes": ("CLIENT_FINANCE_FILE_METADATA",),
                "tokenization_applied": True,
                "raw_values_included": False,
                "requires_structured_output": True,
            }
        ),
    }
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at,
        "provider_policy_records": tuple(asdict(record) for record in provider_policy_records()),
        "examples": examples,
        "lanes_snapshot": provider_lanes.public_lane_table(),
        "connects_to_chain": {
            "model_router": "Router asks this registry for a policy-compatible provider/model-class candidate.",
            "lm1": "LM1 may only receive a candidate after provider/privacy policy passes.",
            "lm2": "LM2 may only receive a package after Gate 3 and provider/privacy policy pass.",
            "authority": "Provider policy cannot grant execution or live model authority.",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "machine_proof": {
            "live_model_call_performed": False,
            "network_performed": False,
            "provider_key_material_access_performed": False,
            "lm1_policy_selects_fast_candidate": examples["lm1_intent_policy"]["selected_model_class"] == FAST_EXTERNAL_INTENT_MODEL,
            "lm2_policy_selects_strong_candidate": examples["lm2_role_policy"]["selected_model_class"] == STRONG_EXTERNAL_ROLE_MODEL,
            "local_fallback_selects_local_candidate": examples["local_fallback_policy"]["selected_candidate_id"] == provider_lanes.LOCAL_FLOOR_CANDIDATE,
            "private_cloud_candidate_rejected": any(
                item.get("reason") in {"PRIVACY_CEILING_EXCEEDED", "FORCED_LOCAL_SENSITIVE_OR_PRIVATE"}
                for item in examples["private_cloud_block"]["rejected_candidates"]
            ),
            "raw_values_block_no_safe_model": examples["raw_values_block"]["selected_model_class"] == NO_SAFE_MODEL,
            "unknown_label_forces_local": examples["unknown_label_force_local"]["selected_candidate_id"] == provider_lanes.LOCAL_FLOOR_CANDIDATE,
            "lane_table_contains_no_live_authority": True,
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
        "# Provider Policy Registry",
        "",
        f"Status: {CONTRACT_STATUS}",
        f"LM1 fast candidate: {str(proof.get('lm1_policy_selects_fast_candidate')).lower()}",
        f"LM2 strong candidate: {str(proof.get('lm2_policy_selects_strong_candidate')).lower()}",
        f"Private cloud blocked: {str(proof.get('private_cloud_candidate_rejected')).lower()}",
        f"Raw values blocked: {str(proof.get('raw_values_block_no_safe_model')).lower()}",
        "",
        "Provider policies are candidate-only. No model call, network call, key access, or authority grant is wired.",
    ]
    operator_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return json_path, operator_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export provider policy registry read-model.")
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
                    "lm1_selected_provider": payload["examples"]["lm1_intent_policy"]["selected_provider_ref"],
                    "lm2_selected_provider": payload["examples"]["lm2_role_policy"]["selected_provider_ref"],
                    "raw_values_model_class": payload["examples"]["raw_values_block"]["selected_model_class"],
                    "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
                }
            ),
            end="",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

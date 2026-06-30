"""Portable Capability Discovery Index v0.

This deterministic read-model maps OpenClaw capabilities without executing
them. It indexes generic capability definitions separately from workflow-scoped
bindings and fixture examples so future intent interpretation can query what is
available, missing, blocked, or future-gated without promoting a task-specific
fixture into core product taxonomy.

The index does not call models, dispatch agents, mutate registries, run
workflows, access external systems, handle credentials, or ingest raw bodies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_EXPORT_ROOT = Path("generated/read_models")
DEFAULT_GENERATED_AT: str | None = None

SCHEMA_VERSION = "openclaw_capability_index_v0"
READ_MODEL_ID = "openclaw_capability_index"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_PORTABLE_CAPABILITY_INDEX_NO_EXECUTION"

TAXONOMY_TYPES = (
    "REQUEST_PROCESSING",
    "FILE_METADATA_INTAKE",
    "SECRET_INTAKE",
    "STATUS_READBACK",
    "WORKFLOW_PACKAGE_COMPILATION",
    "OUTBOUND_MESSAGE_DRAFT",
    "OUTBOUND_MESSAGE_SEND_GATE",
    "PORTAL_TRANSACTION_PACKAGE",
    "PORTAL_TRANSACTION_SUBMIT_GATE",
    "DRY_RUN",
    "COMPLETION_PROOF_AGGREGATION",
    "TTS_VOICE_COMPILATION",
    "SPOKEN_SCRIPT_GENERATION",
    "VISUAL_EVENT_COMPILATION",
    "WORKER_ROUTING",
    "CLIENT_COCKPIT_HANDOFF",
    "PII_TOKENIZATION",
    "INTENT_VALIDATION",
    "CONTEXT_PACKAGE",
    "SOURCE_REF_MANAGEMENT",
    "APPROVAL_GATE",
    "RECORD_KEEPING_WRITE",
    "DOCUMENT_OCR_EXTRACTION",
    "UNKNOWN_FAIL_CLOSED",
)

CAPABILITY_LIFECYCLE_STATUSES = (
    "KNOWN_GENERIC",
    "WORKFLOW_BOUND",
    "FIXTURE_ONLY",
    "PROPOSED_CANDIDATE",
    "BUILT_UNVALIDATED",
    "VALIDATED_NON_EXECUTING",
    "LIVE_IMPLEMENTED",
    "FUTURE_GATED",
    "BLOCKED_UNSAFE",
    "RETIRED",
)

CAPABILITY_STATUSES = (
    "LIVE_IMPLEMENTED",
    "IMPLEMENTED_NON_EXECUTING",
    "CONTRACT_ONLY",
    "READ_MODEL_ONLY",
    "FIXTURE_ONLY",
    "FUTURE_GATED",
    "BLOCKED_UNSAFE",
    "UNKNOWN_FAIL_CLOSED",
)

PORTABILITY_SCOPES = (
    "USER_AGNOSTIC",
    "TENANT_SCOPED",
    "CLIENT_SCOPED",
    "WORKFLOW_SCOPED",
    "FIXTURE_ONLY",
    "UNKNOWN_FAIL_CLOSED",
)

INPUT_TYPES = (
    "OPERATOR_TEXT",
    "SOURCE_REF",
    "FILE_METADATA_REF",
    "PROTECTED_SECRET_REF",
    "APPROVAL_RECEIPT",
    "GUARDIAN_APPROVAL_REF",
    "OPERATOR_APPROVAL_REF",
    "WORKFLOW_REF",
    "CLIENT_REF",
    "TENANT_REF",
    "ARTIFACT_REF",
    "PROOF_REF",
    "CONTEXT_PACKAGE_REF",
    "TRANSACTION_METADATA",
    "UNKNOWN_FAIL_CLOSED",
)

ACCEPTED_SOURCES = (
    "CHAT_REQUEST",
    "MAC_FILE_INTAKE",
    "SQLITE_RECEIPT",
    "GENERATED_READMODEL",
    "PROTECTED_VAULT_REF",
    "OPERATOR_TYPED_VALUE",
    "FUTURE_ADAPTER",
    "UNKNOWN_FAIL_CLOSED",
)

OUTPUT_TYPES = (
    "MAC_RESPONSE_PAYLOAD",
    "GENERATED_READMODEL",
    "OPERATOR_MARKDOWN",
    "SQLITE_RECEIPT",
    "LOCAL_ARTIFACT_REF",
    "OUTBOUND_MESSAGE_DRAFT_ARTIFACT",
    "VISUAL_EVENT_PACKAGE",
    "SPOKEN_RESPONSE_PACKET",
    "HEARTBEAT_PAYLOAD",
    "MACHINE_INTENT_CANDIDATE",
    "BUILD_CUE_CANDIDATE",
    "CONTEXT_GAP_CANDIDATE",
    "UNKNOWN_FAIL_CLOSED",
)

BLOCKER_TYPES = (
    "RAW_PRIVATE_BODY_SCAN_ATTEMPTED",
    "CREDENTIAL_SCAN_ATTEMPTED",
    "EXTERNAL_SYSTEM_ACCESS_ATTEMPTED",
    "CAPABILITY_CLAIMS_UNPROVEN_AUTHORITY",
    "CONTRACT_ONLY_CLAIMS_LIVE_EXECUTION",
    "USER_SPECIFIC_FIXTURE_USED_AS_GENERIC_CAPABILITY",
    "TASK_SPECIFIC_FIXTURE_USED_AS_GENERIC_CAPABILITY",
    "PROPOSED_CANDIDATE_USED_AS_LIVE_CAPABILITY",
    "CANDIDATE_SELF_PROMOTION_ATTEMPTED",
    "UNKNOWN_AUTHORITY",
    "CROSS_CLIENT_LEAK_RISK",
    "UNSAFE_PROVIDER_CLAIM",
    "UNKNOWN_FAIL_CLOSED",
)

CANDIDATE_STATUSES = (
    "PROPOSED_UNVERIFIED",
    "NEEDS_OPERATOR_REVIEW",
    "NEEDS_DEVELOPER_BUILD",
    "NEEDS_TESTS",
    "NEEDS_GUARDIAN_REVIEW",
    "REJECTED",
    "PROMOTED_AFTER_VALIDATION",
    "UNKNOWN_FAIL_CLOSED",
)

READBACK_STATUSES = (
    "CAPABILITY_INDEX_READY",
    "CAPABILITY_INDEX_PARTIAL",
    "CAPABILITY_INDEX_BLOCKED",
    "UNKNOWN_FAIL_CLOSED",
)

AUTHORITY_BOUNDARY = {
    "live_capability_execution_allowed": False,
    "live_registry_mutation_allowed": False,
    "live_model_call_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_workflow_run_allowed": False,
    "live_external_action_allowed": False,
    "live_secret_reveal_allowed": False,
    "live_candidate_promotion_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "network_allowed": False,
    "live_browser_allowed": False,
    "live_email_send_allowed": False,
    "live_portal_access_allowed": False,
    "live_portal_submit_allowed": False,
    "live_visual_generation_allowed": False,
    "live_speech_synthesis_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

SAFE_TENANT_SCOPES = (
    "tenant_scope:fixture_business_ops",
    "tenant_scope:fixture_creative_project",
)

WORKFLOW_SPECIFIC_TERMS = (
    "winship",
    "capital hilton",
    "capital_hilton",
    "coupa",
    "x32",
    "struna",
)


@dataclass(frozen=True)
class CapabilityIndexCompiler:
    compiler_id: str
    doctrine: tuple[str, ...]
    source_scan_policy: tuple[str, ...]
    portability_policy: tuple[str, ...]
    tenant_scope_policy: tuple[str, ...]
    capability_record_policy: tuple[str, ...]
    workflow_binding_policy: tuple[str, ...]
    fixture_policy: tuple[str, ...]
    proposal_candidate_policy: tuple[str, ...]
    lifecycle_policy: tuple[str, ...]
    promotion_gate_policy: tuple[str, ...]
    authority_policy: tuple[str, ...]
    intent_interpreter_policy: tuple[str, ...]
    doctrine_gate_policy: tuple[str, ...]
    privacy_boundary: tuple[str, ...]
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class GenericCapability:
    capability_id: str
    capability_name: str
    taxonomy_type: str
    description: str
    lifecycle_status: str
    portability_scope: str
    capability_status: str
    applicable_task_types: tuple[str, ...]
    applicable_world_types: tuple[str, ...]
    input_requirements: tuple[str, ...]
    output_artifacts: tuple[str, ...]
    authority_profile: str
    owning_worker_role: str
    target_machine_type: str
    source_modules: tuple[str, ...]
    source_scripts: tuple[str, ...]
    source_tests: tuple[str, ...]
    generated_readmodels: tuple[str, ...]
    intent_types_supported: tuple[str, ...]
    search_keywords: tuple[str, ...]
    response_surfaces: tuple[str, ...]
    validation_requirements: tuple[str, ...]
    future_gates: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    privacy_class: str
    sensitivity_class: str
    doctrine_gates: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class WorkflowCapabilityBinding:
    binding_id: str
    capability_ref: str
    workflow_ref: str
    workflow_type: str
    world_ref: str
    tenant_scope: str
    client_scope: str
    active_implementation_ref: str
    source_modules: tuple[str, ...]
    generated_readmodels: tuple[str, ...]
    input_binding_notes: tuple[str, ...]
    output_binding_notes: tuple[str, ...]
    authority_profile_ref: str
    fixture_refs: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class CapabilityFixture:
    fixture_id: str
    binding_ref: str
    fixture_name: str
    fixture_purpose: str
    mock_data_policy: str
    proven_receipt_mocks: tuple[str, ...]
    expected_result: str
    blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class CapabilityInputRequirement:
    requirement_id: str
    capability_ref: str
    input_name: str
    input_type: str
    required: bool
    accepted_source: str
    tenant_scope_required: bool
    privacy_class: str
    validation_rule: str
    missing_behavior: str
    next_safe_move: str


@dataclass(frozen=True)
class CapabilityOutputArtifact:
    output_id: str
    capability_ref: str
    output_name: str
    output_type: str
    output_location_policy: str
    safe_for_lm_context: bool
    safe_for_mac_render: bool
    proof_status: str
    next_safe_move: str


@dataclass(frozen=True)
class CapabilityAuthorityProfile:
    authority_profile_id: str
    capability_ref: str
    live_authority_allowed: bool
    live_execution_allowed: bool
    live_external_action_allowed: bool
    live_model_call_allowed: bool
    live_agent_dispatch_allowed: bool
    live_outbound_message_send_allowed: bool
    live_portal_access_allowed: bool
    live_portal_submit_allowed: bool
    live_browser_allowed: bool
    live_secret_reveal_allowed: bool
    raw_body_ingestion_allowed: bool
    credential_handling_allowed: bool
    authority_notes: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class DoctrineGateRef:
    doctrine_gate_id: str
    doctrine_ref: str
    applies_to_capability_types: tuple[str, ...]
    decision_check_required: bool
    operator_review_required: bool
    blocked_patterns: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class CapabilityProposalCandidate:
    proposal_id: str
    source_request_id: str
    proposed_capability_name: str
    proposed_taxonomy_type: str
    proposed_task_type: str
    description: str
    reason_needed: str
    nearest_existing_capabilities: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    required_receipts: tuple[str, ...]
    required_tests: tuple[str, ...]
    required_authority_review: tuple[str, ...]
    suggested_worker: str
    suggested_module_name: str
    suggested_build_lane: str
    evidence_refs: tuple[str, ...]
    blocker_severity: str
    reconciliation_instructions: tuple[str, ...]
    risk_level: str
    tenant_scope: str
    client_scope: str
    candidate_status: str
    validation_required: bool
    authority_boundary: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class CapabilityPromotionGate:
    promotion_gate_id: str
    proposal_ref: str
    required_code_refs: tuple[str, ...]
    required_tests: tuple[str, ...]
    required_readmodels: tuple[str, ...]
    required_receipts: tuple[str, ...]
    required_authority_profile: str
    required_doctrine_checks: tuple[str, ...]
    operator_approval_required: bool
    developer_review_required: bool
    guardian_review_required: bool
    promotion_allowed: bool
    promotion_status: str
    next_safe_move: str


@dataclass(frozen=True)
class CapabilityLifecycleRecord:
    lifecycle_id: str
    capability_ref: str
    lifecycle_status: str
    source: str
    validation_status: str
    test_status: str
    authority_status: str
    doctrine_status: str
    promoted_at_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class CapabilityGapRecord:
    gap_id: str
    missing_capability: str
    requested_intent_type: str
    affected_task_type: str
    affected_workflow_type: str
    affected_world_type: str
    affected_example_workflow_ref: str
    reason_missing: str
    nearest_existing_capabilities: tuple[str, ...]
    suggested_build_lane: str
    suggested_worker: str
    risk_level: str
    candidate_only: bool
    validation_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class CapabilityIndexQueryExample:
    query_id: str
    operator_text: str
    interpreted_need: str
    generic_task_type: str
    example_context: str
    matched_capabilities: tuple[str, ...]
    missing_capabilities: tuple[str, ...]
    recommended_intent_type: str
    validation_required: bool
    next_safe_move: str


@dataclass(frozen=True)
class CapabilityIndexReadback:
    readback_id: str
    status: str
    operator_headline: str
    operator_message: str
    capability_count: int
    live_implemented_count: int
    contract_only_count: int
    future_gated_count: int
    blocked_count: int
    portable_capability_count: int
    workflow_scoped_count: int
    fixture_only_count: int
    proposal_candidate_count: int
    top_generic_capabilities: tuple[str, ...]
    workflow_bindings: tuple[str, ...]
    top_gaps: tuple[str, ...]
    proposed_capabilities: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class CapabilityIndexBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    fail_closed: bool
    next_safe_move: str


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _stable_id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha256("\0".join(str(part) for part in parts).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest[:16]}"


def _utc_generated_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _present(path: str) -> bool:
    return Path(path).exists()


def _source_module(path: str) -> tuple[str, ...]:
    return (path,) if _present(path) else ()


def _source_script(path: str) -> tuple[str, ...]:
    return (path,) if _present(path) else ()


def _source_test(path: str) -> tuple[str, ...]:
    return (path,) if _present(path) else ()


def _readmodel(path: str) -> tuple[str, ...]:
    return (path,) if _present(path) else ()


def _model_schemas() -> dict[str, tuple[str, ...]]:
    return {
        "CapabilityIndexCompiler": tuple(field.name for field in fields(CapabilityIndexCompiler)),
        "GenericCapability": tuple(field.name for field in fields(GenericCapability)),
        "WorkflowCapabilityBinding": tuple(field.name for field in fields(WorkflowCapabilityBinding)),
        "CapabilityFixture": tuple(field.name for field in fields(CapabilityFixture)),
        "CapabilityInputRequirement": tuple(field.name for field in fields(CapabilityInputRequirement)),
        "CapabilityOutputArtifact": tuple(field.name for field in fields(CapabilityOutputArtifact)),
        "CapabilityAuthorityProfile": tuple(field.name for field in fields(CapabilityAuthorityProfile)),
        "DoctrineGateRef": tuple(field.name for field in fields(DoctrineGateRef)),
        "CapabilityProposalCandidate": tuple(field.name for field in fields(CapabilityProposalCandidate)),
        "CapabilityPromotionGate": tuple(field.name for field in fields(CapabilityPromotionGate)),
        "CapabilityLifecycleRecord": tuple(field.name for field in fields(CapabilityLifecycleRecord)),
        "CapabilityGapRecord": tuple(field.name for field in fields(CapabilityGapRecord)),
        "CapabilityIndexQueryExample": tuple(field.name for field in fields(CapabilityIndexQueryExample)),
        "CapabilityIndexReadback": tuple(field.name for field in fields(CapabilityIndexReadback)),
        "CapabilityIndexBlocker": tuple(field.name for field in fields(CapabilityIndexBlocker)),
    }


def _blocked_actions() -> tuple[str, ...]:
    return (
        "live external action",
        "live model call",
        "agent dispatch",
        "workflow execution",
        "credential handling",
        "raw body ingestion",
    )


def _authority_profile(capability_ref: str, *, notes: tuple[str, ...] = ()) -> CapabilityAuthorityProfile:
    return CapabilityAuthorityProfile(
        authority_profile_id=f"authority:{capability_ref}",
        capability_ref=capability_ref,
        live_authority_allowed=False,
        live_execution_allowed=False,
        live_external_action_allowed=False,
        live_model_call_allowed=False,
        live_agent_dispatch_allowed=False,
        live_outbound_message_send_allowed=False,
        live_portal_access_allowed=False,
        live_portal_submit_allowed=False,
        live_browser_allowed=False,
        live_secret_reveal_allowed=False,
        raw_body_ingestion_allowed=False,
        credential_handling_allowed=False,
        authority_notes=notes
        or (
            "This index is discovery/read-model only.",
            "False is the default for every live authority flag.",
        ),
        next_safe_move="Use this profile for validation; do not execute the capability from the index.",
    )


def _candidate_authority_boundary() -> dict[str, bool]:
    return {
        "live_capability_execution_allowed": False,
        "live_registry_mutation_allowed": False,
        "live_model_call_allowed": False,
        "live_agent_dispatch_allowed": False,
        "live_workflow_run_allowed": False,
        "live_external_action_allowed": False,
        "live_secret_reveal_allowed": False,
        "live_candidate_promotion_allowed": False,
        "credential_handling_allowed": False,
        "raw_body_ingestion_allowed": False,
        "live_browser_allowed": False,
        "live_outbound_message_send_allowed": False,
        "live_portal_access_allowed": False,
        "live_portal_submit_allowed": False,
        "live_visual_generation_allowed": False,
        "live_audio_playback_allowed": False,
        "file_mutation_allowed": False,
        "network_allowed": False,
    }


def _lifecycle_from_capability_status(status: str) -> str:
    return {
        "LIVE_IMPLEMENTED": "LIVE_IMPLEMENTED",
        "IMPLEMENTED_NON_EXECUTING": "VALIDATED_NON_EXECUTING",
        "CONTRACT_ONLY": "KNOWN_GENERIC",
        "READ_MODEL_ONLY": "VALIDATED_NON_EXECUTING",
        "FIXTURE_ONLY": "FIXTURE_ONLY",
        "FUTURE_GATED": "FUTURE_GATED",
        "BLOCKED_UNSAFE": "BLOCKED_UNSAFE",
        "UNKNOWN_FAIL_CLOSED": "BLOCKED_UNSAFE",
    }.get(status, "BLOCKED_UNSAFE")


def _input(
    capability_ref: str,
    input_name: str,
    input_type: str,
    *,
    required: bool = True,
    accepted_source: str = "GENERATED_READMODEL",
    tenant_scope_required: bool = True,
    privacy_class: str = "METADATA_ONLY",
    validation_rule: str = "Reference must be present and scoped before use.",
    missing_behavior: str = "Fail closed with a human-readable missing input.",
) -> CapabilityInputRequirement:
    return CapabilityInputRequirement(
        requirement_id=_stable_id("input", capability_ref, input_name),
        capability_ref=capability_ref,
        input_name=input_name,
        input_type=input_type,
        required=required,
        accepted_source=accepted_source,
        tenant_scope_required=tenant_scope_required,
        privacy_class=privacy_class,
        validation_rule=validation_rule,
        missing_behavior=missing_behavior,
        next_safe_move="Resolve the input as a safe ref or ask for clarification.",
    )


def _output(
    capability_ref: str,
    output_name: str,
    output_type: str,
    *,
    safe_for_lm_context: bool = True,
    safe_for_mac_render: bool = True,
    proof_status: str = "read-model proof only",
    output_location_policy: str = "generated read-model or Mac response payload",
) -> CapabilityOutputArtifact:
    return CapabilityOutputArtifact(
        output_id=_stable_id("output", capability_ref, output_name),
        capability_ref=capability_ref,
        output_name=output_name,
        output_type=output_type,
        output_location_policy=output_location_policy,
        safe_for_lm_context=safe_for_lm_context,
        safe_for_mac_render=safe_for_mac_render,
        proof_status=proof_status,
        next_safe_move="Use the artifact as metadata/readback only unless a separate gate grants authority.",
    )


def _capability(
    *,
    capability_id: str,
    capability_name: str,
    taxonomy_type: str,
    description: str,
    status: str,
    lifecycle_status: str | None = None,
    input_refs: tuple[str, ...],
    output_refs: tuple[str, ...],
    owning_worker_role: str,
    target_machine_type: str,
    intent_types_supported: tuple[str, ...],
    search_keywords: tuple[str, ...],
    source_modules: tuple[str, ...] = (),
    source_scripts: tuple[str, ...] = (),
    source_tests: tuple[str, ...] = (),
    generated_readmodels: tuple[str, ...] = (),
    applicable_task_types: tuple[str, ...] = (),
    applicable_world_types: tuple[str, ...] = ("business", "creative", "operations", "software"),
    future_gates: tuple[str, ...] = (),
    doctrine_gates: tuple[str, ...] = ("SENSITIVE_DATA_POLICY", "TENANT_SCOPE_POLICY"),
    privacy_class: str = "METADATA_ONLY",
    sensitivity_class: str = "LOW_TO_MEDIUM",
    next_safe_move: str = "Use this capability only through its validator or existing readback rail.",
) -> GenericCapability:
    return GenericCapability(
        capability_id=capability_id,
        capability_name=capability_name,
        taxonomy_type=taxonomy_type,
        description=description,
        lifecycle_status=lifecycle_status or _lifecycle_from_capability_status(status),
        portability_scope="USER_AGNOSTIC",
        capability_status=status,
        applicable_task_types=applicable_task_types or (taxonomy_type.lower(),),
        applicable_world_types=applicable_world_types,
        input_requirements=input_refs,
        output_artifacts=output_refs,
        authority_profile=f"authority:{capability_id}",
        owning_worker_role=owning_worker_role,
        target_machine_type=target_machine_type,
        source_modules=source_modules,
        source_scripts=source_scripts,
        source_tests=source_tests,
        generated_readmodels=generated_readmodels,
        intent_types_supported=intent_types_supported,
        search_keywords=search_keywords,
        response_surfaces=("Mac chat", "operator markdown", "generated read-model"),
        validation_requirements=(
            "tenant scope must be known or intentionally generic",
            "required inputs must be refs, receipts, or metadata only",
            "authority boundary must remain explicit",
        ),
        future_gates=future_gates,
        blocked_actions=_blocked_actions(),
        privacy_class=privacy_class,
        sensitivity_class=sensitivity_class,
        doctrine_gates=doctrine_gates,
        next_safe_move=next_safe_move,
    )


def build_input_requirements() -> tuple[CapabilityInputRequirement, ...]:
    data = [
        ("request_processing", "request file", "SOURCE_REF", "CHAT_REQUEST", False),
        ("request_response_service", "approved inbox request", "SOURCE_REF", "CHAT_REQUEST", False),
        ("route_aware_heartbeat", "source request identity", "WORKFLOW_REF", "CHAT_REQUEST", False),
        ("file_metadata_intake", "file metadata payload", "FILE_METADATA_REF", "MAC_FILE_INTAKE", True),
        ("protected_secret_intake", "protected secret intent", "OPERATOR_TEXT", "CHAT_REQUEST", True),
        ("status_readback", "status source read-model", "PROOF_REF", "GENERATED_READMODEL", True),
        ("workflow_package_compilation", "workflow ref", "WORKFLOW_REF", "GENERATED_READMODEL", True),
        ("dry_run", "run package ref", "WORKFLOW_REF", "GENERATED_READMODEL", True),
        ("completion_proof_aggregation", "completion receipts", "PROOF_REF", "GENERATED_READMODEL", True),
        ("outbound_message_draft", "draft package refs", "CONTEXT_PACKAGE_REF", "GENERATED_READMODEL", True),
        ("outbound_message_send_gate", "approval and send receipts", "APPROVAL_RECEIPT", "GENERATED_READMODEL", True),
        ("portal_transaction_package", "transaction metadata refs", "TRANSACTION_METADATA", "GENERATED_READMODEL", True),
        ("portal_transaction_submit_gate", "approval and submit refs", "APPROVAL_RECEIPT", "GENERATED_READMODEL", True),
        ("agent_voice_compilation", "truth payload ref", "PROOF_REF", "GENERATED_READMODEL", False),
        ("spoken_script_generation", "layered response payload", "PROOF_REF", "GENERATED_READMODEL", False),
        ("visual_event_compilation", "truth state ref", "PROOF_REF", "GENERATED_READMODEL", False),
        ("worker_routing", "operator request text", "OPERATOR_TEXT", "CHAT_REQUEST", False),
        ("scoped_context_package", "context graph refs", "CONTEXT_PACKAGE_REF", "GENERATED_READMODEL", True),
        ("machine_intent_validation", "machine intent candidate", "CONTEXT_PACKAGE_REF", "GENERATED_READMODEL", False),
        ("human_dignity_doctrine_gate", "decision context", "CONTEXT_PACKAGE_REF", "GENERATED_READMODEL", False),
        ("private_hmac_pii_tokenization", "private value ref", "SOURCE_REF", "PROTECTED_VAULT_REF", True),
        ("client_cockpit_handoff", "handoff request metadata", "SOURCE_REF", "CHAT_REQUEST", True),
        ("record_keeping_write", "approved local record receipt", "OPERATOR_APPROVAL_REF", "SQLITE_RECEIPT", True),
        ("document_ocr_extraction", "body extraction approval", "APPROVAL_RECEIPT", "FUTURE_ADAPTER", True),
        ("source_ref_management", "source metadata ref", "SOURCE_REF", "GENERATED_READMODEL", True),
        ("approval_gate", "approval packet ref", "GUARDIAN_APPROVAL_REF", "GENERATED_READMODEL", True),
    ]
    return tuple(
        _input(cap, name, input_type, accepted_source=source, tenant_scope_required=tenant_required)
        for cap, name, input_type, source, tenant_required in data
    )


def build_output_artifacts() -> tuple[CapabilityOutputArtifact, ...]:
    data = [
        ("request_processing", "Mac terminal response", "MAC_RESPONSE_PAYLOAD"),
        ("request_response_service", "Mac response files", "MAC_RESPONSE_PAYLOAD"),
        ("route_aware_heartbeat", "processing heartbeat", "HEARTBEAT_PAYLOAD"),
        ("file_metadata_intake", "file metadata readback", "GENERATED_READMODEL"),
        ("protected_secret_intake", "secret intake contract", "GENERATED_READMODEL"),
        ("status_readback", "operator status response", "MAC_RESPONSE_PAYLOAD"),
        ("workflow_package_compilation", "workflow run package", "GENERATED_READMODEL"),
        ("dry_run", "dry-run readback", "GENERATED_READMODEL"),
        ("completion_proof_aggregation", "completion proof set", "GENERATED_READMODEL"),
        ("outbound_message_draft", "reviewable draft artifact", "OUTBOUND_MESSAGE_DRAFT_ARTIFACT"),
        ("outbound_message_send_gate", "send readiness receipt model", "GENERATED_READMODEL"),
        ("portal_transaction_package", "portal transaction package", "GENERATED_READMODEL"),
        ("portal_transaction_submit_gate", "submit readiness receipt model", "GENERATED_READMODEL"),
        ("agent_voice_compilation", "voice-bound response packet", "MAC_RESPONSE_PAYLOAD"),
        ("spoken_script_generation", "spoken response packet", "SPOKEN_RESPONSE_PACKET"),
        ("visual_event_compilation", "visual event package", "VISUAL_EVENT_PACKAGE"),
        ("worker_routing", "route decision readback", "GENERATED_READMODEL"),
        ("scoped_context_package", "scoped context package", "GENERATED_READMODEL"),
        ("machine_intent_validation", "validation result", "MACHINE_INTENT_CANDIDATE"),
        ("human_dignity_doctrine_gate", "dignity decision check", "GENERATED_READMODEL"),
        ("private_hmac_pii_tokenization", "private match token ref", "GENERATED_READMODEL"),
        ("client_cockpit_handoff", "client cockpit handoff package", "GENERATED_READMODEL"),
        ("record_keeping_write", "future local record receipt", "SQLITE_RECEIPT"),
        ("document_ocr_extraction", "future extraction artifact ref", "LOCAL_ARTIFACT_REF"),
        ("source_ref_management", "source ref readback", "GENERATED_READMODEL"),
        ("approval_gate", "approval gate readback", "GENERATED_READMODEL"),
    ]
    return tuple(_output(cap, name, output_type) for cap, name, output_type in data)


def _refs_by_capability(items: tuple[CapabilityInputRequirement | CapabilityOutputArtifact, ...]) -> dict[str, tuple[str, ...]]:
    refs: dict[str, list[str]] = {}
    for item in items:
        cap = item.capability_ref
        ref = item.requirement_id if isinstance(item, CapabilityInputRequirement) else item.output_id
        refs.setdefault(cap, []).append(ref)
    return {key: tuple(value) for key, value in refs.items()}


def build_generic_capabilities(
    inputs: tuple[CapabilityInputRequirement, ...],
    outputs: tuple[CapabilityOutputArtifact, ...],
) -> tuple[GenericCapability, ...]:
    input_refs = _refs_by_capability(inputs)
    output_refs = _refs_by_capability(outputs)
    caps = [
        _capability(
            capability_id="request_processing",
            capability_name="Bounded request processor",
            taxonomy_type="REQUEST_PROCESSING",
            description="Parse one approved local request and produce a terminal operator readback.",
            status="LIVE_IMPLEMENTED",
            input_refs=input_refs["request_processing"],
            output_refs=output_refs["request_processing"],
            owning_worker_role="OPENCLAW_SYSTEM",
            target_machine_type="PC_WSL",
            source_modules=_source_module("openclaw_request_processor.py"),
            source_scripts=_source_script("scripts/process_openclaw_requests.py"),
            source_tests=_source_test("tests/test_openclaw_request_processor.py"),
            generated_readmodels=_readmodel("generated/read_models/openclaw_request_processor_status.json"),
            intent_types_supported=("ANSWER_STATUS", "ATTACH_SOURCE_REF", "ASK_CLARIFICATION"),
            search_keywords=("request", "processor", "chat", "file metadata", "terminal response"),
        ),
        _capability(
            capability_id="request_response_service",
            capability_name="Local request response service",
            taxonomy_type="REQUEST_PROCESSING",
            description="Bounded local service that notices approved request files and publishes Mac-readable responses.",
            status="LIVE_IMPLEMENTED",
            input_refs=input_refs["request_response_service"],
            output_refs=output_refs["request_response_service"],
            owning_worker_role="OPENCLAW_SYSTEM",
            target_machine_type="PC_WSL",
            source_modules=_source_module("openclaw_request_response_service.py"),
            source_scripts=_source_script("scripts/run_openclaw_request_response_service.py"),
            source_tests=_source_test("tests/test_openclaw_request_response_service.py"),
            generated_readmodels=_readmodel("generated/read_models/openclaw_request_response_service_status.json"),
            intent_types_supported=("ANSWER_STATUS", "ATTACH_SOURCE_REF"),
            search_keywords=("service", "watch", "Mac response", "bounded polling"),
        ),
        _capability(
            capability_id="route_aware_heartbeat",
            capability_name="Route-aware processing heartbeat",
            taxonomy_type="REQUEST_PROCESSING",
            description="Immediate non-terminal processing status for PC, Mac, or future-worker routes.",
            status="LIVE_IMPLEMENTED",
            input_refs=input_refs["route_aware_heartbeat"],
            output_refs=output_refs["route_aware_heartbeat"],
            owning_worker_role="OPENCLAW_SYSTEM",
            target_machine_type="PC_WSL",
            source_modules=_source_module("openclaw_request_response_service.py"),
            source_tests=_source_test("tests/test_openclaw_request_response_service.py"),
            generated_readmodels=_readmodel("generated/read_models/openclaw_request_response_service_status.json"),
            intent_types_supported=("ANSWER_STATUS", "ROUTE_TO_AGENT"),
            search_keywords=("heartbeat", "routing status", "processing", "worker target"),
        ),
        _capability(
            capability_id="file_metadata_intake",
            capability_name="File metadata intake",
            taxonomy_type="FILE_METADATA_INTAKE",
            description="Capture metadata/source refs without reading file bodies.",
            status="LIVE_IMPLEMENTED",
            input_refs=input_refs["file_metadata_intake"],
            output_refs=output_refs["file_metadata_intake"],
            owning_worker_role="OPENCLAW_SYSTEM",
            target_machine_type="PC_WSL",
            source_modules=_source_module("operator_file_metadata_intake.py"),
            generated_readmodels=_readmodel("generated/read_models/operator_file_metadata_readback.json"),
            intent_types_supported=("ATTACH_SOURCE_REF", "CAPTURE_MISSING_INPUT"),
            search_keywords=("file ref", "metadata", "source reference", "attachment ref"),
        ),
        _capability(
            capability_id="protected_secret_intake",
            capability_name="Protected secret intake contract",
            taxonomy_type="SECRET_INTAKE",
            description="Model future secret-ref intake without capturing or exposing raw secret values.",
            status="CONTRACT_ONLY",
            input_refs=input_refs["protected_secret_intake"],
            output_refs=output_refs["protected_secret_intake"],
            owning_worker_role="GUARDIAN",
            target_machine_type="LOCAL_ONLY",
            source_modules=_source_module("protected_secret_intake_contract.py"),
            source_scripts=_source_script("scripts/export_protected_secret_intake_contract.py"),
            generated_readmodels=_readmodel("generated/read_models/protected_secret_intake_contract.json"),
            intent_types_supported=("CAPTURE_MISSING_INPUT", "REQUEST_APPROVAL"),
            search_keywords=("secret ref", "protected ref", "credential boundary"),
            future_gates=("protected local secret storage and use policy must be explicitly implemented",),
            doctrine_gates=("SENSITIVE_DATA_POLICY", "APPROVAL_GATE_POLICY", "HUMAN_DIGNITY_DOCTRINE"),
            sensitivity_class="HIGH",
        ),
        _capability(
            capability_id="status_readback",
            capability_name="Unified status readback",
            taxonomy_type="STATUS_READBACK",
            description="Summarize existing read-model truth into an operator-facing status response.",
            status="IMPLEMENTED_NON_EXECUTING",
            input_refs=input_refs["status_readback"],
            output_refs=output_refs["status_readback"],
            owning_worker_role="CHIEF",
            target_machine_type="PC_WSL",
            intent_types_supported=("ANSWER_STATUS", "CONTINUE_CURRENT_WORKFLOW"),
            search_keywords=("status", "what is blocked", "what is missing", "next safe move"),
            future_gates=("workflow-specific status modules bind this generic interface",),
        ),
        _capability(
            capability_id="workflow_package_compilation",
            capability_name="Workflow package compilation",
            taxonomy_type="WORKFLOW_PACKAGE_COMPILATION",
            description="Compile workflow readiness/package metadata without running the workflow.",
            status="IMPLEMENTED_NON_EXECUTING",
            input_refs=input_refs["workflow_package_compilation"],
            output_refs=output_refs["workflow_package_compilation"],
            owning_worker_role="CHIEF",
            target_machine_type="PC_WSL",
            source_modules=_source_module("invoice_delivery_run_package_assembler.py"),
            generated_readmodels=_readmodel("generated/read_models/invoice_delivery_run_package_assembler.json"),
            intent_types_supported=("RUN_DRY_RUN", "ANSWER_STATUS"),
            search_keywords=("workflow package", "readiness package", "run package"),
        ),
        _capability(
            capability_id="dry_run",
            capability_name="Dry-run readiness harness",
            taxonomy_type="DRY_RUN",
            description="Run deterministic readiness modeling without external action.",
            status="IMPLEMENTED_NON_EXECUTING",
            input_refs=input_refs["dry_run"],
            output_refs=output_refs["dry_run"],
            owning_worker_role="CHIEF",
            target_machine_type="PC_WSL",
            source_modules=_source_module("invoice_delivery_dry_run_harness.py"),
            generated_readmodels=_readmodel("generated/read_models/invoice_delivery_dry_run_harness.json"),
            intent_types_supported=("RUN_DRY_RUN", "ANSWER_STATUS"),
            search_keywords=("dry run", "readiness", "simulate", "no execution"),
        ),
        _capability(
            capability_id="completion_proof_aggregation",
            capability_name="Completion proof aggregation",
            taxonomy_type="COMPLETION_PROOF_AGGREGATION",
            description="Determine whether completion labels are proof-backed by receipts.",
            status="IMPLEMENTED_NON_EXECUTING",
            input_refs=input_refs["completion_proof_aggregation"],
            output_refs=output_refs["completion_proof_aggregation"],
            owning_worker_role="GUARDIAN",
            target_machine_type="PC_WSL",
            source_modules=_source_module("invoice_delivery_completion_proof_aggregator.py"),
            generated_readmodels=_readmodel("generated/read_models/invoice_delivery_completion_proof_aggregator.json"),
            intent_types_supported=("ANSWER_STATUS", "REQUEST_APPROVAL"),
            search_keywords=("completion proof", "receipt", "final label", "proof aggregation"),
            doctrine_gates=("APPROVAL_GATE_POLICY", "SENSITIVE_DATA_POLICY", "HUMAN_DIGNITY_DOCTRINE"),
        ),
        _capability(
            capability_id="outbound_message_draft",
            capability_name="Outbound message draft",
            taxonomy_type="OUTBOUND_MESSAGE_DRAFT",
            description="Prepare reviewable outbound communication draft artifacts without sending.",
            status="IMPLEMENTED_NON_EXECUTING",
            input_refs=input_refs["outbound_message_draft"],
            output_refs=output_refs["outbound_message_draft"],
            owning_worker_role="CASSANDRA",
            target_machine_type="PC_WSL",
            source_modules=_source_module("gated_email_draft_adapter.py"),
            generated_readmodels=_readmodel("generated/read_models/gated_email_draft_adapter.json"),
            intent_types_supported=("PREPARE_DRAFT", "ANSWER_STATUS"),
            search_keywords=("draft", "reviewable message", "communication prep"),
            doctrine_gates=("APPROVAL_GATE_POLICY", "SENSITIVE_DATA_POLICY"),
        ),
        _capability(
            capability_id="outbound_message_send_gate",
            capability_name="Outbound message send gate",
            taxonomy_type="OUTBOUND_MESSAGE_SEND_GATE",
            description="Model send readiness and required receipts without sending.",
            status="IMPLEMENTED_NON_EXECUTING",
            input_refs=input_refs["outbound_message_send_gate"],
            output_refs=output_refs["outbound_message_send_gate"],
            owning_worker_role="GUARDIAN",
            target_machine_type="PC_WSL",
            source_modules=_source_module("gated_email_send_adapter.py"),
            generated_readmodels=_readmodel("generated/read_models/gated_email_send_adapter.json"),
            intent_types_supported=("REQUEST_APPROVAL", "ANSWER_STATUS"),
            search_keywords=("send gate", "outbound send", "approval", "receipt"),
            future_gates=("live provider send adapter remains future gated",),
            doctrine_gates=("APPROVAL_GATE_POLICY", "SENSITIVE_DATA_POLICY", "HUMAN_DIGNITY_DOCTRINE"),
            sensitivity_class="HIGH",
        ),
        _capability(
            capability_id="portal_transaction_package",
            capability_name="Portal transaction package",
            taxonomy_type="PORTAL_TRANSACTION_PACKAGE",
            description="Compile portal transaction metadata/package refs without portal access.",
            status="IMPLEMENTED_NON_EXECUTING",
            input_refs=input_refs["portal_transaction_package"],
            output_refs=output_refs["portal_transaction_package"],
            owning_worker_role="CHIEF",
            target_machine_type="PC_WSL",
            intent_types_supported=("ANSWER_STATUS", "CAPTURE_MISSING_INPUT"),
            search_keywords=("portal package", "transaction package", "reference package"),
            future_gates=("workflow-specific portal adapters must bind this generic interface",),
            doctrine_gates=("APPROVAL_GATE_POLICY", "SENSITIVE_DATA_POLICY", "HUMAN_DIGNITY_DOCTRINE"),
            sensitivity_class="HIGH",
        ),
        _capability(
            capability_id="portal_transaction_submit_gate",
            capability_name="Portal transaction submit gate",
            taxonomy_type="PORTAL_TRANSACTION_SUBMIT_GATE",
            description="Model portal submit readiness and proof requirements without portal access.",
            status="IMPLEMENTED_NON_EXECUTING",
            input_refs=input_refs["portal_transaction_submit_gate"],
            output_refs=output_refs["portal_transaction_submit_gate"],
            owning_worker_role="GUARDIAN",
            target_machine_type="PC_WSL",
            intent_types_supported=("REQUEST_APPROVAL", "ANSWER_STATUS"),
            search_keywords=("portal submit gate", "submit readiness", "protected transaction"),
            future_gates=("live portal/browser submit adapters remain future gated",),
            doctrine_gates=("APPROVAL_GATE_POLICY", "SENSITIVE_DATA_POLICY", "HUMAN_DIGNITY_DOCTRINE"),
            sensitivity_class="HIGH",
        ),
        _capability(
            capability_id="agent_voice_compilation",
            capability_name="Agent voice compilation",
            taxonomy_type="TTS_VOICE_COMPILATION",
            description="Attach deterministic author/voice metadata to truth-preserving responses.",
            status="READ_MODEL_ONLY",
            input_refs=input_refs["agent_voice_compilation"],
            output_refs=output_refs["agent_voice_compilation"],
            owning_worker_role="OPENCLAW_SYSTEM",
            target_machine_type="PC_WSL",
            source_modules=_source_module("agent_voice_response_layer.py"),
            generated_readmodels=_readmodel("generated/read_models/agent_voice_response_layer.json"),
            intent_types_supported=("ANSWER_STATUS", "ROUTE_TO_AGENT"),
            search_keywords=("voice", "author", "vibe", "response style"),
        ),
        _capability(
            capability_id="spoken_script_generation",
            capability_name="Spoken script generation",
            taxonomy_type="SPOKEN_SCRIPT_GENERATION",
            description="Compile local-playback-safe spoken scripts from the same truth payload as visual responses.",
            status="IMPLEMENTED_NON_EXECUTING",
            input_refs=input_refs["spoken_script_generation"],
            output_refs=output_refs["spoken_script_generation"],
            owning_worker_role="OPENCLAW_SYSTEM",
            target_machine_type="PC_WSL",
            source_modules=_source_module("openclaw_request_processor.py"),
            source_tests=_source_test("tests/test_openclaw_request_processor.py"),
            generated_readmodels=_readmodel("generated/read_models/openclaw_response_for_mac.json"),
            intent_types_supported=("READ_ALOUD", "ANSWER_STATUS"),
            search_keywords=("read aloud", "spoken packet", "local TTS", "script"),
            future_gates=("Mac playback is a separate renderer; this index does not synthesize audio",),
        ),
        _capability(
            capability_id="visual_event_compilation",
            capability_name="Visual event compilation",
            taxonomy_type="VISUAL_EVENT_COMPILATION",
            description="Compile sanitized visual event packages from proof-backed workflow state.",
            status="IMPLEMENTED_NON_EXECUTING",
            input_refs=input_refs["visual_event_compilation"],
            output_refs=output_refs["visual_event_compilation"],
            owning_worker_role="OPENCLAW_SYSTEM",
            target_machine_type="PC_WSL",
            source_modules=_source_module("chat_workflow_visual_event_package_compiler.py"),
            source_scripts=_source_script("scripts/export_chat_workflow_visual_event_package_compiler.py"),
            source_tests=_source_test("tests/test_chat_workflow_visual_event_package_compiler.py"),
            generated_readmodels=_readmodel("generated/read_models/chat_workflow_visual_event_package_compiler.json"),
            intent_types_supported=("SHOW_VISUAL_WORKSPACE", "ANSWER_STATUS"),
            search_keywords=("visual", "animation", "event package", "status cue"),
            future_gates=("live image/video generation remains blocked unless future gated",),
        ),
        _capability(
            capability_id="worker_routing",
            capability_name="Worker routing",
            taxonomy_type="WORKER_ROUTING",
            description="Choose a safe worker target or blocked route without dispatching the worker.",
            status="IMPLEMENTED_NON_EXECUTING",
            input_refs=input_refs["worker_routing"],
            output_refs=output_refs["worker_routing"],
            owning_worker_role="CHIEF",
            target_machine_type="PC_WSL",
            source_modules=_source_module("worker_routing_intelligence.py"),
            source_scripts=_source_script("scripts/export_worker_routing_intelligence.py"),
            source_tests=_source_test("tests/test_worker_routing_intelligence.py"),
            generated_readmodels=_readmodel("generated/read_models/worker_routing_intelligence.json"),
            intent_types_supported=("ROUTE_TO_AGENT", "CREATE_BUILD_CUE", "CREATE_CONTEXT_GAP"),
            search_keywords=("route", "worker", "machine", "handoff"),
        ),
        _capability(
            capability_id="scoped_context_package",
            capability_name="Scoped context package",
            taxonomy_type="CONTEXT_PACKAGE",
            description="Package role-specific refs and exclusions without raw transcript or file-body ingestion.",
            status="CONTRACT_ONLY",
            input_refs=input_refs["scoped_context_package"],
            output_refs=output_refs["scoped_context_package"],
            owning_worker_role="OPENCLAW_SYSTEM",
            target_machine_type="PC_WSL",
            source_modules=_source_module("scoped_context_package_compiler_contract.py"),
            source_scripts=_source_script("scripts/export_scoped_context_package_compiler_contract.py"),
            generated_readmodels=_readmodel("generated/read_models/scoped_context_package_compiler_contract.json"),
            intent_types_supported=("ROUTE_TO_AGENT", "CREATE_CONTEXT_GAP"),
            search_keywords=("context package", "source refs", "scoped refs", "context gap"),
            future_gates=("live context assembly and dispatch remains future gated",),
        ),
        _capability(
            capability_id="machine_intent_validation",
            capability_name="Machine intent validation",
            taxonomy_type="INTENT_VALIDATION",
            description="Validate proposed machine intent before any request becomes canonical.",
            status="IMPLEMENTED_NON_EXECUTING",
            input_refs=input_refs["machine_intent_validation"],
            output_refs=output_refs["machine_intent_validation"],
            owning_worker_role="OPENCLAW_SYSTEM",
            target_machine_type="PC_WSL",
            source_modules=_source_module("machine_intent_candidate_validator.py"),
            source_scripts=_source_script("scripts/export_machine_intent_candidate_validator.py"),
            source_tests=_source_test("tests/test_machine_intent_candidate_validator.py"),
            generated_readmodels=_readmodel("generated/read_models/machine_intent_candidate_validator.json"),
            intent_types_supported=("CONTINUE_CURRENT_WORKFLOW", "PREPARE_DRAFT", "ROUTE_TO_AGENT", "ASK_CLARIFICATION"),
            search_keywords=("intent", "validator", "next", "clarification", "missing requirement"),
        ),
        _capability(
            capability_id="human_dignity_doctrine_gate",
            capability_name="Human dignity doctrine gate",
            taxonomy_type="APPROVAL_GATE",
            description="Apply human dignity, common-good, and anti-domination checks around consequential automation.",
            status="READ_MODEL_ONLY",
            input_refs=input_refs["human_dignity_doctrine_gate"],
            output_refs=output_refs["human_dignity_doctrine_gate"],
            owning_worker_role="GUARDIAN",
            target_machine_type="PC_WSL",
            source_modules=_source_module("human_dignity_doctrine_contract.py"),
            source_scripts=_source_script("scripts/export_human_dignity_doctrine_contract.py"),
            source_tests=_source_test("tests/test_human_dignity_doctrine_contract.py"),
            generated_readmodels=_readmodel("generated/read_models/human_dignity_doctrine_contract.json"),
            intent_types_supported=("ASK_CLARIFICATION", "REQUEST_APPROVAL"),
            search_keywords=("dignity", "common good", "automation impact", "labor", "appeal"),
            doctrine_gates=("HUMAN_DIGNITY_DOCTRINE", "TENANT_SCOPE_POLICY"),
        ),
        _capability(
            capability_id="private_hmac_pii_tokenization",
            capability_name="Private HMAC and PII tokenization",
            taxonomy_type="PII_TOKENIZATION",
            description="Purpose-bound private value matching primitive; raw values stay out of read-models.",
            status="IMPLEMENTED_NON_EXECUTING",
            input_refs=input_refs["private_hmac_pii_tokenization"],
            output_refs=output_refs["private_hmac_pii_tokenization"],
            owning_worker_role="GUARDIAN",
            target_machine_type="LOCAL_ONLY",
            source_modules=_source_module("openclaw_private_value_hash.py"),
            source_scripts=_source_script("scripts/export_private_value_hash_policy.py"),
            source_tests=_source_test("tests/test_private_value_hash.py"),
            generated_readmodels=_readmodel("generated/read_models/private_value_hash_policy.json"),
            intent_types_supported=("ATTACH_SOURCE_REF", "CAPTURE_MISSING_INPUT"),
            search_keywords=("private matching", "HMAC", "tokenization", "PII"),
            future_gates=("live key integration must use protected local key refs only",),
            doctrine_gates=("SENSITIVE_DATA_POLICY", "HUMAN_DIGNITY_DOCTRINE"),
            sensitivity_class="HIGH",
        ),
        _capability(
            capability_id="client_cockpit_handoff",
            capability_name="Client cockpit handoff package",
            taxonomy_type="CLIENT_COCKPIT_HANDOFF",
            description="Package Mac-owned work for a Mac-readable handoff without executing it.",
            status="IMPLEMENTED_NON_EXECUTING",
            input_refs=input_refs["client_cockpit_handoff"],
            output_refs=output_refs["client_cockpit_handoff"],
            owning_worker_role="OPENCLAW_SYSTEM",
            target_machine_type="PC_WSL_TO_MAC",
            source_modules=_source_module("mac_worker_handoff_package.py"),
            source_scripts=_source_script("scripts/export_mac_worker_handoff_package.py"),
            source_tests=_source_test("tests/test_mac_worker_handoff_package.py"),
            generated_readmodels=_readmodel("generated/read_models/mac_worker_handoff_package.json"),
            intent_types_supported=("ROUTE_TO_AGENT", "SHOW_VISUAL_WORKSPACE", "READ_ALOUD"),
            search_keywords=("Mac handoff", "UI validation", "local playback", "client cockpit"),
            future_gates=("Mac-side watcher/execution lane remains separate",),
        ),
        _capability(
            capability_id="source_ref_management",
            capability_name="Source reference management",
            taxonomy_type="SOURCE_REF_MANAGEMENT",
            description="Represent safe metadata/source refs for future context and proof flows.",
            status="IMPLEMENTED_NON_EXECUTING",
            input_refs=input_refs["source_ref_management"],
            output_refs=output_refs["source_ref_management"],
            owning_worker_role="OPENCLAW_SYSTEM",
            target_machine_type="PC_WSL",
            source_modules=_source_module("operator_file_metadata_intake.py"),
            generated_readmodels=_readmodel("generated/read_models/operator_file_metadata_readback.json"),
            intent_types_supported=("ATTACH_SOURCE_REF", "CAPTURE_MISSING_INPUT"),
            search_keywords=("source ref", "file metadata", "proof ref", "artifact ref"),
        ),
        _capability(
            capability_id="approval_gate",
            capability_name="Approval gate",
            taxonomy_type="APPROVAL_GATE",
            description="Represent exact approval/proof gates for high-consequence action readiness.",
            status="CONTRACT_ONLY",
            input_refs=input_refs["approval_gate"],
            output_refs=output_refs["approval_gate"],
            owning_worker_role="GUARDIAN",
            target_machine_type="PC_WSL",
            source_modules=_source_module("guardian_approval_request_wrapper.py"),
            generated_readmodels=_readmodel("generated/read_models/guardian_approval_request_wrapper.json"),
            intent_types_supported=("REQUEST_APPROVAL", "ANSWER_STATUS"),
            search_keywords=("approval", "guardian", "exact approval", "proof gate"),
            future_gates=("exact approval receipt creation remains separately gated",),
            doctrine_gates=("APPROVAL_GATE_POLICY", "SENSITIVE_DATA_POLICY", "HUMAN_DIGNITY_DOCTRINE"),
            sensitivity_class="HIGH",
        ),
        _capability(
            capability_id="record_keeping_write",
            capability_name="Record keeping write",
            taxonomy_type="RECORD_KEEPING_WRITE",
            description="Future local record write rail requiring explicit receipt-backed authority.",
            status="FUTURE_GATED",
            input_refs=input_refs["record_keeping_write"],
            output_refs=output_refs["record_keeping_write"],
            owning_worker_role="GUARDIAN",
            target_machine_type="PC_WSL",
            intent_types_supported=("REQUEST_APPROVAL", "ANSWER_STATUS"),
            search_keywords=("record", "ledger", "write receipt", "completion write"),
            future_gates=("approved local write adapter and reversal policy required",),
            doctrine_gates=("APPROVAL_GATE_POLICY", "HUMAN_DIGNITY_DOCTRINE"),
            sensitivity_class="HIGH",
        ),
        _capability(
            capability_id="document_ocr_extraction",
            capability_name="Document OCR extraction",
            taxonomy_type="DOCUMENT_OCR_EXTRACTION",
            description="Blocked/future document body extraction rail; metadata refs are preferred until approval exists.",
            status="BLOCKED_UNSAFE",
            input_refs=input_refs["document_ocr_extraction"],
            output_refs=output_refs["document_ocr_extraction"],
            owning_worker_role="GUARDIAN",
            target_machine_type="LOCAL_ONLY",
            intent_types_supported=("CREATE_BUILD_CUE", "ASK_CLARIFICATION"),
            search_keywords=("OCR", "document extraction", "body extraction", "private body"),
            future_gates=("explicit raw-body approval and protected local parser lane required",),
            doctrine_gates=("SENSITIVE_DATA_POLICY", "HUMAN_DIGNITY_DOCTRINE"),
            sensitivity_class="HIGH",
            next_safe_move="Use file metadata/source refs until a protected extraction lane exists.",
        ),
    ]
    return tuple(caps)


def build_authority_profiles(capabilities: tuple[GenericCapability, ...]) -> tuple[CapabilityAuthorityProfile, ...]:
    return tuple(
        _authority_profile(
            capability.capability_id,
            notes=(
                f"Capability status: {capability.capability_status}.",
                "This index does not grant live use or execution.",
            ),
        )
        for capability in capabilities
    )


def build_workflow_bindings() -> tuple[WorkflowCapabilityBinding, ...]:
    return (
        WorkflowCapabilityBinding(
            binding_id="binding:fixture:capital_hilton:status_readback",
            capability_ref="status_readback",
            workflow_ref="workflow:fixture:capital_hilton_invoice",
            workflow_type="invoice_delivery",
            world_ref="world:fixture:business_ops",
            tenant_scope="tenant_scope:fixture_business_ops",
            client_scope="client_scope:fixture_capital_hilton",
            active_implementation_ref="capital_hilton_invoice_operator_readback",
            source_modules=("capital_hilton_invoice_operator_readback.py",),
            generated_readmodels=("generated/read_models/capital_hilton_invoice_operator_readback.json",),
            input_binding_notes=("workflow-scoped fixture facts only", "does not rewrite the generic status capability"),
            output_binding_notes=("operator-facing status readback", "completion remains proof gated"),
            authority_profile_ref="authority:status_readback",
            fixture_refs=("fixture:capital_hilton:not_ready_status",),
            next_safe_move="Keep this as a workflow binding; do not promote client fixture text into the generic taxonomy.",
        ),
        WorkflowCapabilityBinding(
            binding_id="binding:fixture:capital_hilton:portal_package",
            capability_ref="portal_transaction_package",
            workflow_ref="workflow:fixture:capital_hilton_invoice",
            workflow_type="invoice_delivery",
            world_ref="world:fixture:business_ops",
            tenant_scope="tenant_scope:fixture_business_ops",
            client_scope="client_scope:fixture_capital_hilton",
            active_implementation_ref="coupa_supplier_portal_package_compiler",
            source_modules=("coupa_supplier_portal_package_compiler.py",),
            generated_readmodels=("generated/read_models/coupa_supplier_portal_package_compiler.json",),
            input_binding_notes=("PO/reference is workflow-scoped", "raw portal credentials are not accepted"),
            output_binding_notes=("package/readiness metadata only",),
            authority_profile_ref="authority:portal_transaction_package",
            fixture_refs=("fixture:capital_hilton:missing_portal_reference",),
            next_safe_move="Confirm the workflow-scoped portal reference before any submit gate can be considered.",
        ),
        WorkflowCapabilityBinding(
            binding_id="binding:fixture:capital_hilton:outbound_message",
            capability_ref="outbound_message_draft",
            workflow_ref="workflow:fixture:capital_hilton_invoice",
            workflow_type="invoice_delivery",
            world_ref="world:fixture:business_ops",
            tenant_scope="tenant_scope:fixture_business_ops",
            client_scope="client_scope:fixture_capital_hilton",
            active_implementation_ref="gated_email_draft_adapter",
            source_modules=("gated_email_draft_adapter.py", "gated_email_send_adapter.py"),
            generated_readmodels=(
                "generated/read_models/gated_email_draft_adapter.json",
                "generated/read_models/gated_email_send_adapter.json",
            ),
            input_binding_notes=("recipient/contact refs are workflow-scoped", "attachment refs and hashes are required"),
            output_binding_notes=("draft/readiness only; send remains blocked without exact approvals and receipts"),
            authority_profile_ref="authority:outbound_message_draft",
            fixture_refs=("fixture:capital_hilton:draft_send_blocked",),
            next_safe_move="Review the draft fixture without granting send authority.",
        ),
        WorkflowCapabilityBinding(
            binding_id="binding:fixture:x32:creative_context",
            capability_ref="worker_routing",
            workflow_ref="workflow:fixture:x32_source_refs",
            workflow_type="creative_project_context",
            world_ref="world:fixture:creative_project",
            tenant_scope="tenant_scope:fixture_creative_project",
            client_scope="client_scope:fixture_niles_x32",
            active_implementation_ref="worker_routing_intelligence",
            source_modules=("worker_routing_intelligence.py",),
            generated_readmodels=("generated/read_models/worker_routing_intelligence.json",),
            input_binding_notes=("source refs are required before creative/project routing can use detailed context",),
            output_binding_notes=("route/context gap only",),
            authority_profile_ref="authority:worker_routing",
            fixture_refs=("fixture:niles:x32_missing_source_refs",),
            next_safe_move="Ask for source refs; do not imply file mutation authority.",
        ),
        WorkflowCapabilityBinding(
            binding_id="binding:fixture:struna:project_capsule",
            capability_ref="scoped_context_package",
            workflow_ref="workflow:fixture:struna_project_capsule",
            workflow_type="creative_project_context",
            world_ref="world:fixture:creative_project",
            tenant_scope="tenant_scope:fixture_creative_project",
            client_scope="client_scope:fixture_struna_project",
            active_implementation_ref="project_capsule_read_model",
            source_modules=("project_capsule_read_model.py",),
            generated_readmodels=("generated/read_models/struna_obscura_project_capsule.json",),
            input_binding_notes=("project facts are fixture-scoped",),
            output_binding_notes=("context package/read-model only",),
            authority_profile_ref="authority:scoped_context_package",
            fixture_refs=("fixture:struna:project_capsule_context",),
            next_safe_move="Use as fixture context only; do not promote project-specific labels into generic capability IDs.",
        ),
    )


def build_fixtures() -> tuple[CapabilityFixture, ...]:
    return (
        CapabilityFixture(
            fixture_id="fixture:capital_hilton:not_ready_status",
            binding_ref="binding:fixture:capital_hilton:status_readback",
            fixture_name="Capital Hilton invoice operator readback",
            fixture_purpose="Proves workflow-scoped status aggregation with missing inputs and locked external actions.",
            mock_data_policy="fixture metadata only; no raw private bodies, emails, credentials, or portal access",
            proven_receipt_mocks=("delivery basis modeled", "draft/readiness rails modeled"),
            expected_result="not ready; missing workflow-scoped portal reference and approvals",
            blocked_actions=("send", "submit", "completion claim", "browser access"),
            next_safe_move="Resolve the missing workflow-scoped reference and approval receipts.",
        ),
        CapabilityFixture(
            fixture_id="fixture:capital_hilton:missing_portal_reference",
            binding_ref="binding:fixture:capital_hilton:portal_package",
            fixture_name="Capital Hilton portal transaction package",
            fixture_purpose="Proves a workflow binding can require a portal reference without making it generic taxonomy.",
            mock_data_policy="portal reference is modeled as missing; no credential value requested",
            proven_receipt_mocks=("invoice value refs modeled", "artifact/hash refs modeled"),
            expected_result="blocked missing workflow-scoped portal reference",
            blocked_actions=("portal login", "portal submit", "browser automation"),
            next_safe_move="Attach or type the workflow-scoped reference as a source ref.",
        ),
        CapabilityFixture(
            fixture_id="fixture:capital_hilton:draft_send_blocked",
            binding_ref="binding:fixture:capital_hilton:outbound_message",
            fixture_name="Capital Hilton outbound draft and send gate",
            fixture_purpose="Proves draft preparation and send-gate separation.",
            mock_data_policy="metadata-only draft fixture; no raw email address or attachment body",
            proven_receipt_mocks=("draft package modeled", "send receipt absent"),
            expected_result="draft may be reviewable; send remains blocked",
            blocked_actions=("message send", "attachment send", "generic approval promotion"),
            next_safe_move="Review draft metadata and require exact approval receipts for any future send lane.",
        ),
        CapabilityFixture(
            fixture_id="fixture:niles:x32_missing_source_refs",
            binding_ref="binding:fixture:x32:creative_context",
            fixture_name="X32 creative/project missing source refs",
            fixture_purpose="Proves creative routing can create a context gap without file mutation authority.",
            mock_data_policy="fixture label only; no show-file body or device data",
            proven_receipt_mocks=("route target modeled",),
            expected_result="context gap created until source refs are attached",
            blocked_actions=("DAW mutation", "device control", "file mutation"),
            next_safe_move="Attach the source ref or clarify the creative/project context.",
        ),
        CapabilityFixture(
            fixture_id="fixture:struna:project_capsule_context",
            binding_ref="binding:fixture:struna:project_capsule",
            fixture_name="Struna project capsule example",
            fixture_purpose="Proves project capsule bindings remain fixture-scoped.",
            mock_data_policy="project label only; no raw creative files",
            proven_receipt_mocks=("project capsule read-model exists",),
            expected_result="context package fixture only",
            blocked_actions=("creative file mutation", "external publication", "agent dispatch"),
            next_safe_move="Use generic context package capability; keep fixture labels scoped.",
        ),
    )


def build_doctrine_gates() -> tuple[DoctrineGateRef, ...]:
    return (
        DoctrineGateRef(
            doctrine_gate_id="doctrine_gate:human_dignity",
            doctrine_ref="HUMAN_DIGNITY_DOCTRINE",
            applies_to_capability_types=(
                "SECRET_INTAKE",
                "OUTBOUND_MESSAGE_SEND_GATE",
                "PORTAL_TRANSACTION_SUBMIT_GATE",
                "RECORD_KEEPING_WRITE",
                "DOCUMENT_OCR_EXTRACTION",
            ),
            decision_check_required=True,
            operator_review_required=True,
            blocked_patterns=("hidden automation", "authority without appeal", "labor erasure"),
            next_safe_move="Run dignity/impact review before consequential automation or data extraction.",
        ),
        DoctrineGateRef(
            doctrine_gate_id="doctrine_gate:sensitive_data",
            doctrine_ref="SENSITIVE_DATA_POLICY",
            applies_to_capability_types=(
                "FILE_METADATA_INTAKE",
                "SECRET_INTAKE",
                "PII_TOKENIZATION",
                "CONTEXT_PACKAGE",
                "DOCUMENT_OCR_EXTRACTION",
            ),
            decision_check_required=True,
            operator_review_required=True,
            blocked_patterns=("raw private body ingestion", "credential exposure", "cross-client leak"),
            next_safe_move="Use refs, tokens, and metadata only unless a protected lane explicitly permits more.",
        ),
        DoctrineGateRef(
            doctrine_gate_id="doctrine_gate:approval",
            doctrine_ref="APPROVAL_GATE_POLICY",
            applies_to_capability_types=(
                "OUTBOUND_MESSAGE_SEND_GATE",
                "PORTAL_TRANSACTION_SUBMIT_GATE",
                "APPROVAL_GATE",
                "RECORD_KEEPING_WRITE",
            ),
            decision_check_required=True,
            operator_review_required=True,
            blocked_patterns=("generic approval", "proofless send", "proofless submit"),
            next_safe_move="Require exact approval receipts and proof refs before any future action adapter.",
        ),
        DoctrineGateRef(
            doctrine_gate_id="doctrine_gate:tenant_scope",
            doctrine_ref="TENANT_SCOPE_POLICY",
            applies_to_capability_types=TAXONOMY_TYPES,
            decision_check_required=True,
            operator_review_required=False,
            blocked_patterns=("cross-tenant readback", "fixture promoted as generic", "client-scope leak"),
            next_safe_move="Filter workflow bindings by tenant/client scope and expose only safe generic definitions.",
        ),
    )


def build_proposal_candidates() -> tuple[CapabilityProposalCandidate, ...]:
    return (
        CapabilityProposalCandidate(
            proposal_id="proposal:client_cockpit_visual_event_renderer",
            source_request_id="fixture_request:missing_visual_renderer",
            proposed_capability_name="CLIENT_COCKPIT_VISUAL_EVENT_RENDERER",
            proposed_taxonomy_type="CLIENT_COCKPIT_HANDOFF",
            proposed_task_type="render local visual feedback",
            description="Future Mac-local renderer for sanitized visual event packages.",
            reason_needed="Visual event packages exist, but local Mac rendering/playback is not an active capability in this index.",
            nearest_existing_capabilities=("visual_event_compilation", "client_cockpit_handoff"),
            missing_inputs=("Mac renderer lifecycle contract", "local asset policy", "screenshot/render validation receipts"),
            expected_outputs=("local visual render receipt", "Mac-render-safe status readback"),
            required_receipts=("focused Mac renderer tests", "operator visual-readback approval", "authority boundary receipt"),
            required_tests=("unit tests for package parsing", "renderer fixture test", "privacy prompt exclusion test"),
            required_authority_review=("developer review", "operator review", "Guardian review if external/media provider is introduced"),
            suggested_worker="MAC_CODEX",
            suggested_module_name="mac_visual_event_renderer_future",
            suggested_build_lane="Mac-local visual renderer lane",
            evidence_refs=("generated/read_models/chat_workflow_visual_event_package_compiler.json",),
            blocker_severity="medium",
            reconciliation_instructions=(
                "Keep this candidate out of generic_capabilities.",
                "Implement Mac renderer separately and prove local-only behavior before promotion.",
            ),
            risk_level="medium",
            tenant_scope="tenant_scope:generic",
            client_scope="client_scope:none",
            candidate_status="NEEDS_DEVELOPER_BUILD",
            validation_required=True,
            authority_boundary=_candidate_authority_boundary(),
            next_safe_move="Queue a Mac renderer build lane; do not render, generate, or play media from this index.",
        ),
        CapabilityProposalCandidate(
            proposal_id="proposal:outbound_message_draft_binding_adapter",
            source_request_id="fixture_request:missing_draft_adapter",
            proposed_capability_name="OUTBOUND_MESSAGE_DRAFT_BINDING_ADAPTER",
            proposed_taxonomy_type="OUTBOUND_MESSAGE_DRAFT",
            proposed_task_type="prepare outbound message draft for a new workflow binding",
            description="Future workflow binding adapter for reviewable outbound drafts when no wrapper exists for the current workflow.",
            reason_needed="The generic draft capability exists, but a workflow-specific binding may be absent for a new tenant/workflow.",
            nearest_existing_capabilities=("outbound_message_draft", "worker_routing", "machine_intent_validation"),
            missing_inputs=("workflow-specific recipient refs", "draft package compiler refs", "attachment/ref policy"),
            expected_outputs=("reviewable draft artifact", "operator draft readback"),
            required_receipts=("draft package fixture", "no-send authority receipt", "privacy scan receipt"),
            required_tests=("missing recipient blocks", "send authority remains false", "no raw contact data output"),
            required_authority_review=("developer review", "Cassandra/Guardian review for communications boundary"),
            suggested_worker="PC_CODEX",
            suggested_module_name="outbound_message_draft_binding_adapter_future",
            suggested_build_lane="workflow-specific outbound draft binding lane",
            evidence_refs=("generated/read_models/gated_email_draft_adapter.json",),
            blocker_severity="high",
            reconciliation_instructions=(
                "Candidate may create a build cue only.",
                "Candidate must never grant send authority or imply a message was sent.",
            ),
            risk_level="high",
            tenant_scope="tenant_scope:generic",
            client_scope="client_scope:none",
            candidate_status="NEEDS_TESTS",
            validation_required=True,
            authority_boundary=_candidate_authority_boundary(),
            next_safe_move="Build a workflow binding adapter with tests; keep send authority false.",
        ),
        CapabilityProposalCandidate(
            proposal_id="proposal:source_ref_parser_fixture_binding",
            source_request_id="fixture_request:missing_source_ref_parser",
            proposed_capability_name="SOURCE_REF_PARSER_FIXTURE_BINDING",
            proposed_taxonomy_type="SOURCE_REF_MANAGEMENT",
            proposed_task_type="parse device/source context from approved refs",
            description="Future parser binding for device/project source refs; raw body ingestion remains blocked by default.",
            reason_needed="Creative/project routing can identify a missing source-ref parser, but parser capability is not live.",
            nearest_existing_capabilities=("source_ref_management", "scoped_context_package", "worker_routing"),
            missing_inputs=("approved source ref", "parser privacy policy", "local parse fixture"),
            expected_outputs=("sanitized source summary ref", "context gap resolution readback"),
            required_receipts=("raw-body approval decision", "local parser fixture test", "no-file-mutation receipt"),
            required_tests=("raw body blocked by default", "metadata-only fixture passes", "cross-project scope blocked"),
            required_authority_review=("developer review", "Guardian review if raw body parsing is requested"),
            suggested_worker="PC_CODEX",
            suggested_module_name="source_ref_parser_fixture_binding_future",
            suggested_build_lane="protected source-ref parser binding lane",
            evidence_refs=("generated/read_models/scoped_context_package_compiler_contract.json",),
            blocker_severity="high",
            reconciliation_instructions=(
                "Do not parse source bodies unless a protected parser lane exists.",
                "Keep parser candidates scoped to fixtures/bindings until validated.",
            ),
            risk_level="high",
            tenant_scope="tenant_scope:generic",
            client_scope="client_scope:none",
            candidate_status="NEEDS_GUARDIAN_REVIEW",
            validation_required=True,
            authority_boundary=_candidate_authority_boundary(),
            next_safe_move="Collect source refs and create a parser build cue; do not ingest raw bodies.",
        ),
    )


def build_promotion_gates(candidates: tuple[CapabilityProposalCandidate, ...]) -> tuple[CapabilityPromotionGate, ...]:
    gates: list[CapabilityPromotionGate] = []
    for candidate in candidates:
        external_action = candidate.proposed_taxonomy_type in {
            "OUTBOUND_MESSAGE_SEND_GATE",
            "PORTAL_TRANSACTION_SUBMIT_GATE",
            "RECORD_KEEPING_WRITE",
            "DOCUMENT_OCR_EXTRACTION",
        }
        gates.append(
            CapabilityPromotionGate(
                promotion_gate_id=_stable_id("promotion_gate", candidate.proposal_id),
                proposal_ref=candidate.proposal_id,
                required_code_refs=(candidate.suggested_module_name,),
                required_tests=candidate.required_tests,
                required_readmodels=(f"generated/read_models/{candidate.suggested_module_name}.json",),
                required_receipts=candidate.required_receipts,
                required_authority_profile=f"authority:{candidate.proposal_id}:required_before_promotion",
                required_doctrine_checks=(
                    "TENANT_SCOPE_POLICY",
                    "SENSITIVE_DATA_POLICY",
                    "APPROVAL_GATE_POLICY" if external_action else "candidate_non_execution_policy",
                    "HUMAN_DIGNITY_DOCTRINE" if candidate.risk_level in {"high", "critical"} else "human_dignity_screen",
                ),
                operator_approval_required=True,
                developer_review_required=True,
                guardian_review_required=candidate.risk_level in {"high", "critical"} or external_action,
                promotion_allowed=False,
                promotion_status="BLOCKED_UNTIL_VALIDATED",
                next_safe_move="Keep the proposal quarantined until code, tests, receipts, authority profile, and reviews exist.",
            )
        )
    return tuple(gates)


def build_lifecycle_records(
    capabilities: tuple[GenericCapability, ...],
    candidates: tuple[CapabilityProposalCandidate, ...],
) -> tuple[CapabilityLifecycleRecord, ...]:
    records: list[CapabilityLifecycleRecord] = []
    for capability in capabilities:
        records.append(
            CapabilityLifecycleRecord(
                lifecycle_id=_stable_id("lifecycle", capability.capability_id),
                capability_ref=capability.capability_id,
                lifecycle_status=capability.lifecycle_status,
                source="generic capability index definition",
                validation_status="deterministic read-model validation",
                test_status="covered by capability index focused tests",
                authority_status="explicit false authority profile",
                doctrine_status="doctrine gates listed on capability",
                promoted_at_policy="not promoted by this lane",
                next_safe_move="Use as a generic capability definition only; bind through scoped workflow records.",
            )
        )
    for candidate in candidates:
        records.append(
            CapabilityLifecycleRecord(
                lifecycle_id=_stable_id("lifecycle", candidate.proposal_id),
                capability_ref=candidate.proposal_id,
                lifecycle_status="PROPOSED_CANDIDATE",
                source="quarantined capability proposal candidate",
                validation_status="unverified candidate",
                test_status="tests required before promotion",
                authority_status="zero execution authority",
                doctrine_status="promotion gate required before use",
                promoted_at_policy="cannot be promoted from candidate or LM output alone",
                next_safe_move="Review, build, test, and receipt the lane before any promotion attempt.",
            )
        )
    return tuple(records)


def build_gaps() -> tuple[CapabilityGapRecord, ...]:
    return (
        CapabilityGapRecord(
            gap_id="gap:live_lm_intent_interpreter",
            missing_capability="live natural-language intent interpreter",
            requested_intent_type="CONTINUE_CURRENT_WORKFLOW",
            affected_task_type="natural language to machine intent",
            affected_workflow_type="all",
            affected_world_type="cross_world",
            affected_example_workflow_ref="fixture:generic_next",
            reason_missing="Only deterministic schema/validator exists; live LM interpretation is not approved in this lane.",
            nearest_existing_capabilities=("machine_intent_validation", "worker_routing", "scoped_context_package"),
            suggested_build_lane="future gated LM intent interpreter wrapper",
            suggested_worker="PC_CODEX",
            risk_level="high",
            candidate_only=True,
            validation_required=True,
            next_safe_move="Keep using deterministic fixtures until a gated interpreter can propose candidates only.",
        ),
        CapabilityGapRecord(
            gap_id="gap:live_portal_submit_adapter",
            missing_capability="live portal submit adapter",
            requested_intent_type="REQUEST_APPROVAL",
            affected_task_type="external portal transaction",
            affected_workflow_type="invoice_delivery",
            affected_world_type="business_ops",
            affected_example_workflow_ref="workflow:fixture:capital_hilton_invoice",
            reason_missing="Readiness gates exist; live portal/browser provider call remains future gated.",
            nearest_existing_capabilities=("portal_transaction_package", "portal_transaction_submit_gate"),
            suggested_build_lane="gated provider adapter with exact approvals and receipts",
            suggested_worker="PC_CODEX",
            risk_level="critical",
            candidate_only=True,
            validation_required=True,
            next_safe_move="Model readiness only; do not access the portal.",
        ),
        CapabilityGapRecord(
            gap_id="gap:live_video_generation",
            missing_capability="live visual/video provider generation",
            requested_intent_type="SHOW_VISUAL_WORKSPACE",
            affected_task_type="visual feedback",
            affected_workflow_type="status_readback",
            affected_world_type="all",
            affected_example_workflow_ref="fixture:generic_visual_feedback",
            reason_missing="Visual event packages exist; provider calls and generated media remain blocked.",
            nearest_existing_capabilities=("visual_event_compilation", "client_cockpit_handoff"),
            suggested_build_lane="future local/static renderer before any cloud video provider",
            suggested_worker="MAC_CODEX",
            risk_level="medium",
            candidate_only=True,
            validation_required=True,
            next_safe_move="Render only local/static cues from sanitized visual packages.",
        ),
    )


def build_query_examples() -> tuple[CapabilityIndexQueryExample, ...]:
    return (
        CapabilityIndexQueryExample(
            query_id="query:generic_next",
            operator_text="next",
            interpreted_need="continue the current workflow or ask which workflow if scope is ambiguous",
            generic_task_type="continue current workflow",
            example_context="Capital Hilton appears only as a fixture for a missing workflow-scoped reference.",
            matched_capabilities=("machine_intent_validation", "status_readback"),
            missing_capabilities=(),
            recommended_intent_type="CONTINUE_CURRENT_WORKFLOW",
            validation_required=True,
            next_safe_move="Resolve latest scoped next action if exactly one active workflow is in scope.",
        ),
        CapabilityIndexQueryExample(
            query_id="query:generic_missing_input",
            operator_text="here is the portal reference",
            interpreted_need="capture a missing workflow-scoped input as a safe source ref",
            generic_task_type="capture missing required input",
            example_context="Coupa PO/reference is an example binding value, not a generic capability.",
            matched_capabilities=("file_metadata_intake", "source_ref_management", "machine_intent_validation"),
            missing_capabilities=(),
            recommended_intent_type="CAPTURE_MISSING_INPUT",
            validation_required=True,
            next_safe_move="Create or attach a source ref; do not submit anything.",
        ),
        CapabilityIndexQueryExample(
            query_id="query:generic_draft",
            operator_text="ask the communications agent to prep the message",
            interpreted_need="prepare an outbound communication draft for review",
            generic_task_type="prepare outbound communication draft",
            example_context="Cassandra/email draft is a fixture-style example of the generic draft capability.",
            matched_capabilities=("outbound_message_draft", "worker_routing"),
            missing_capabilities=("live outbound send authority",),
            recommended_intent_type="PREPARE_DRAFT",
            validation_required=True,
            next_safe_move="Prepare draft/readback only; keep send authority false.",
        ),
        CapabilityIndexQueryExample(
            query_id="query:generic_read_aloud",
            operator_text="read this aloud",
            interpreted_need="use an existing spoken response packet for local playback",
            generic_task_type="speak response",
            example_context="Mac local TTS renderer is the expected future surface; no microphone or cloud STT.",
            matched_capabilities=("spoken_script_generation", "client_cockpit_handoff"),
            missing_capabilities=("live Mac playback watcher",),
            recommended_intent_type="READ_ALOUD",
            validation_required=True,
            next_safe_move="Use the spoken packet; do not synthesize audio on PC.",
        ),
        CapabilityIndexQueryExample(
            query_id="query:generic_blocking_status",
            operator_text="show me what is blocking it",
            interpreted_need="answer blocking status from proof/readiness read-models",
            generic_task_type="answer what is blocked",
            example_context="Any workflow may bind to status readback if tenant scope is valid.",
            matched_capabilities=("status_readback", "completion_proof_aggregation", "dry_run"),
            missing_capabilities=(),
            recommended_intent_type="ANSWER_STATUS",
            validation_required=True,
            next_safe_move="Return a compact status readback with blockers and next safe move.",
        ),
        CapabilityIndexQueryExample(
            query_id="query:generic_creative_project",
            operator_text="Niles, let's work on the X32 thing",
            interpreted_need="route to creative/project context or create a context gap for missing source refs",
            generic_task_type="route to creative/project agent",
            example_context="Niles/X32 is a fixture binding; source refs are required before detailed work.",
            matched_capabilities=("worker_routing", "scoped_context_package", "machine_intent_validation"),
            missing_capabilities=("source refs if absent",),
            recommended_intent_type="ROUTE_TO_AGENT",
            validation_required=True,
            next_safe_move="Ask for source refs or create a context gap; do not mutate files.",
        ),
        CapabilityIndexQueryExample(
            query_id="query:generic_send_submit",
            operator_text="send it",
            interpreted_need="external communication or portal submission request requiring exact approval gates",
            generic_task_type="send or submit request",
            example_context="Workflow-specific send/submit adapters stay blocked without exact proof and approval receipts.",
            matched_capabilities=("outbound_message_send_gate", "portal_transaction_submit_gate", "approval_gate"),
            missing_capabilities=("live external action authority", "exact approval receipt", "provider receipt"),
            recommended_intent_type="REQUEST_APPROVAL",
            validation_required=True,
            next_safe_move="Block generic send/submit phrasing and require exact approval/proof receipts.",
        ),
        CapabilityIndexQueryExample(
            query_id="query:generic_visual_video",
            operator_text="make a video of the workflow state",
            interpreted_need="represent workflow state visually from sanitized proof-backed metadata",
            generic_task_type="visual feedback",
            example_context="Visual event packages are metadata; no image/video provider call is made.",
            matched_capabilities=("visual_event_compilation",),
            missing_capabilities=("live video generation provider",),
            recommended_intent_type="SHOW_VISUAL_WORKSPACE",
            validation_required=True,
            next_safe_move="Compile a visual event package or create a build cue; do not call a provider.",
        ),
        CapabilityIndexQueryExample(
            query_id="query:generic_dignity_labor",
            operator_text="automate this work so people are no longer needed",
            interpreted_need="run an automation impact and dignity review before any consequential automation",
            generic_task_type="automation impact and dignity check",
            example_context="Human dignity doctrine is a gate/wrapper, not a task-specific capability.",
            matched_capabilities=("human_dignity_doctrine_gate", "approval_gate"),
            missing_capabilities=(),
            recommended_intent_type="ASK_CLARIFICATION",
            validation_required=True,
            next_safe_move="Ask who is affected, what consent exists, and what appeal/reversal path is available.",
        ),
        CapabilityIndexQueryExample(
            query_id="query:missing_visual_renderer",
            operator_text="show the status with a local animation",
            interpreted_need="render local visual feedback from a sanitized visual event package",
            generic_task_type="render local visual feedback",
            example_context="If a Mac renderer is absent, create a quarantined proposal candidate only.",
            matched_capabilities=("visual_event_compilation", "client_cockpit_handoff"),
            missing_capabilities=("CLIENT_COCKPIT_VISUAL_EVENT_RENDERER",),
            recommended_intent_type="CREATE_BUILD_CUE",
            validation_required=True,
            next_safe_move="Create proposal:client_cockpit_visual_event_renderer; do not render, generate, or play visuals.",
        ),
        CapabilityIndexQueryExample(
            query_id="query:missing_cassandra_draft_adapter",
            operator_text="ask Cassandra to prep the email for this new workflow",
            interpreted_need="prepare outbound communication draft when a workflow binding is missing",
            generic_task_type="prepare outbound message draft",
            example_context="Cassandra is an example author/role; candidate remains a draft binding proposal with no send authority.",
            matched_capabilities=("outbound_message_draft", "worker_routing", "machine_intent_validation"),
            missing_capabilities=("OUTBOUND_MESSAGE_DRAFT_BINDING_ADAPTER",),
            recommended_intent_type="PREPARE_DRAFT",
            validation_required=True,
            next_safe_move="Create a draft-binding proposal only; do not send or imply send readiness.",
        ),
        CapabilityIndexQueryExample(
            query_id="query:missing_source_ref_parser",
            operator_text="parse the X32 source ref",
            interpreted_need="parse device/source context from approved source refs",
            generic_task_type="parse source reference context",
            example_context="X32 is a fixture binding example; raw body ingestion remains blocked by default.",
            matched_capabilities=("source_ref_management", "scoped_context_package", "worker_routing"),
            missing_capabilities=("SOURCE_REF_PARSER_FIXTURE_BINDING",),
            recommended_intent_type="CREATE_CONTEXT_GAP",
            validation_required=True,
            next_safe_move="Create a parser proposal/context gap; do not ingest source bodies by default.",
        ),
    )


def build_blockers() -> tuple[CapabilityIndexBlocker, ...]:
    return tuple(
        CapabilityIndexBlocker(
            blocker_id=_stable_id("capability_blocker", blocker_type),
            blocker_type=blocker_type,
            condition={
                "RAW_PRIVATE_BODY_SCAN_ATTEMPTED": "Capability discovery must inspect safe module/read-model names only.",
                "CREDENTIAL_SCAN_ATTEMPTED": "Credential or secret files are outside the discovery boundary.",
                "EXTERNAL_SYSTEM_ACCESS_ATTEMPTED": "Capability discovery cannot verify live external systems.",
                "CAPABILITY_CLAIMS_UNPROVEN_AUTHORITY": "Capability records must not imply live authority from file presence.",
                "CONTRACT_ONLY_CLAIMS_LIVE_EXECUTION": "Contract-only records cannot be treated as executable.",
                "USER_SPECIFIC_FIXTURE_USED_AS_GENERIC_CAPABILITY": "Operator-specific fixtures must remain scoped examples.",
                "TASK_SPECIFIC_FIXTURE_USED_AS_GENERIC_CAPABILITY": "Workflow examples cannot rewrite generic taxonomy.",
                "PROPOSED_CANDIDATE_USED_AS_LIVE_CAPABILITY": "Proposal candidates are quarantined and cannot satisfy live capability lookup.",
                "CANDIDATE_SELF_PROMOTION_ATTEMPTED": "Candidates, agents, or LM output cannot promote capability status.",
                "UNKNOWN_AUTHORITY": "Unknown authority fails closed.",
                "CROSS_CLIENT_LEAK_RISK": "Client-specific bindings require tenant/client filtering.",
                "UNSAFE_PROVIDER_CLAIM": "Provider availability must be proven by a separate gated adapter.",
                "UNKNOWN_FAIL_CLOSED": "Unknown capability state fails closed.",
            }[blocker_type],
            severity="critical"
            if blocker_type
            in {
                "RAW_PRIVATE_BODY_SCAN_ATTEMPTED",
                "CREDENTIAL_SCAN_ATTEMPTED",
                "EXTERNAL_SYSTEM_ACCESS_ATTEMPTED",
                "UNKNOWN_AUTHORITY",
            }
            else "high",
            elioperator_warning=f"ELIOPERATOR: {blocker_type} blocks capability promotion.",
            fail_closed=True,
            next_safe_move="Return a blocked/missing capability readback or create a build cue; do not execute.",
        )
        for blocker_type in BLOCKER_TYPES
    )


def build_compiler() -> CapabilityIndexCompiler:
    return CapabilityIndexCompiler(
        compiler_id="capability_index_compiler:v0",
        doctrine=(
            "Generic capabilities are reusable interfaces, not workflow fixtures.",
            "Workflow bindings carry tenant/client/workflow scope.",
            "Fixtures prove behavior but have no execution authority.",
            "The index is discovery/read-model only.",
        ),
        source_scan_policy=(
            "Use safe file/module name inspection and existing deterministic definitions.",
            "Do not inspect private bodies, credentials, external systems, or runtime queues.",
            "Do not infer live authority from a filename or read-model.",
        ),
        portability_policy=(
            "Generic definitions must be user-agnostic and task-agnostic.",
            "Workflow/client examples stay in binding or fixture records.",
            "Task-specific labels must not become core taxonomy.",
        ),
        tenant_scope_policy=(
            "Generic capability definitions may be visible when safe.",
            "Workflow bindings and fixtures require tenant/client filtering.",
            "Invalid tenant scope returns no tenant/client-specific bindings.",
        ),
        capability_record_policy=(
            "Every capability declares inputs, outputs, status, authority, and next safe move.",
            "Future-gated and contract-only records cannot claim live execution.",
        ),
        workflow_binding_policy=(
            "Bindings map generic capability refs to concrete workflow implementations.",
            "Bindings may include client/workflow fixture labels and must keep scope explicit.",
        ),
        fixture_policy=(
            "Fixtures are examples only.",
            "Fixtures cannot satisfy authority gates or prove live provider availability.",
        ),
        proposal_candidate_policy=(
            "Proposal candidates are quarantined suggestions for missing capability.",
            "Candidates are not generic capabilities, not executable, and not trusted.",
            "Candidates are ignored by active routing until promotion gates pass.",
        ),
        lifecycle_policy=(
            "LM-created proposals enter PROPOSED_CANDIDATE only.",
            "Generated code without tests enters BUILT_UNVALIDATED.",
            "Passing tests without authority remains VALIDATED_NON_EXECUTING.",
            "LIVE_IMPLEMENTED requires explicit authority profile and receipt-backed validation.",
        ),
        promotion_gate_policy=(
            "Promotion is false by default.",
            "Promotion requires code refs, tests, read-models, receipts, authority profile, and doctrine checks.",
            "No candidate can promote itself or become live from LM output alone.",
        ),
        authority_policy=(
            "All live authority flags default false.",
            "Unknown authority fails closed.",
            "This index never grants send, submit, browser, model, worker, or workflow authority.",
        ),
        intent_interpreter_policy=(
            "Future LM interpreters may query this map but cannot write canonical truth.",
            "Machine intent candidates still require deterministic validation.",
        ),
        doctrine_gate_policy=(
            "Human dignity, sensitive data, approval, and tenant-scope policies wrap consequential capabilities.",
            "Automation/labor/pricing/data extraction contexts require doctrine checks.",
        ),
        privacy_boundary=(
            "No raw private bodies.",
            "No credentials or secret values.",
            "No raw contact data.",
            "No broad folder scans or external system probes.",
        ),
        authority_boundary=dict(AUTHORITY_BOUNDARY),
        next_safe_move="Use this index to route questions, identify gaps, and validate candidate intent without executing anything.",
    )


def _generic_capability_policy_violations(capabilities: tuple[GenericCapability, ...]) -> tuple[str, ...]:
    violations: list[str] = []
    for capability in capabilities:
        serialized = json.dumps(asdict(capability), sort_keys=True).lower()
        for term in WORKFLOW_SPECIFIC_TERMS:
            if term in serialized:
                violations.append(f"{capability.capability_id} contains workflow-specific term {term}")
        if capability.portability_scope not in {"USER_AGNOSTIC", "TENANT_SCOPED"}:
            violations.append(f"{capability.capability_id} has non-portable scope {capability.portability_scope}")
    return tuple(violations)


def capability_is_live_usable(capability: GenericCapability, profile: CapabilityAuthorityProfile) -> bool:
    if capability.lifecycle_status in {"PROPOSED_CANDIDATE", "BUILT_UNVALIDATED", "FUTURE_GATED", "BLOCKED_UNSAFE", "RETIRED"}:
        return False
    if capability.capability_status in {"CONTRACT_ONLY", "READ_MODEL_ONLY", "FIXTURE_ONLY", "FUTURE_GATED", "BLOCKED_UNSAFE", "UNKNOWN_FAIL_CLOSED"}:
        return False
    if capability.future_gates:
        return False
    return profile.live_execution_allowed


def filter_index_for_tenant(payload: dict[str, Any], tenant_scope: str) -> dict[str, Any]:
    """Return generic definitions plus scoped bindings only for a valid tenant."""

    valid = tenant_scope in SAFE_TENANT_SCOPES
    generic = [
        cap
        for cap in payload.get("generic_capabilities", [])
        if cap.get("portability_scope") in {"USER_AGNOSTIC", "TENANT_SCOPED"}
    ]
    bindings = [
        binding
        for binding in payload.get("workflow_bindings", [])
        if valid and binding.get("tenant_scope") == tenant_scope
    ]
    binding_refs = {binding.get("binding_id") for binding in bindings}
    fixtures = [
        fixture
        for fixture in payload.get("fixtures", [])
        if valid and fixture.get("binding_ref") in binding_refs
    ]
    return {
        "tenant_scope": tenant_scope,
        "valid_tenant_scope": valid,
        "generic_capabilities": generic,
        "workflow_bindings": bindings,
        "fixtures": fixtures,
    }


def _clone_json(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True))


def _normalized_text(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _record_identifier(record: Mapping[str, Any]) -> str:
    for key in ("capability_id", "proposal_id", "fixture_id", "binding_id", "gap_id"):
        value = record.get(key)
        if value:
            return str(value)
    return "unknown"


def _workflow_aliases(workflow_ref: str) -> set[str]:
    normalized = _normalized_text(workflow_ref)
    aliases = {str(workflow_ref), normalized}
    if normalized in {
        "capital_hilton_invoice_workflow",
        "workflow:fixture:capital_hilton_invoice",
        "workflow_fixture_capital_hilton_invoice",
    }:
        aliases.update(
            {
                "capital_hilton_invoice_workflow",
                "workflow:fixture:capital_hilton_invoice",
            }
        )
    if normalized in {"x32_source_refs", "workflow:fixture:x32_source_refs", "workflow_fixture_x32_source_refs"}:
        aliases.update({"workflow:fixture:x32_source_refs", "x32_source_refs"})
    if normalized in {
        "struna_project_capsule",
        "workflow:fixture:struna_project_capsule",
        "workflow_fixture_struna_project_capsule",
    }:
        aliases.update({"workflow:fixture:struna_project_capsule", "struna_project_capsule"})
    return aliases


class CapabilityIndexQuery:
    """Read-only deterministic query helper for the portable capability index."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload: dict[str, Any] = _clone_json(dict(payload))

    @classmethod
    def load_index_from_generated_readmodel(cls, path: str | Path | None = None) -> "CapabilityIndexQuery":
        read_model_path = Path(path) if path is not None else DEFAULT_EXPORT_ROOT / JSON_EXPORT_NAME
        if read_model_path.exists():
            return cls(json.loads(read_model_path.read_text(encoding="utf-8")))
        return cls(build_payload())

    def find_by_intent_type(self, intent_type: str, tenant_scope: str | None = None) -> list[dict[str, Any]]:
        """Return safe generic capabilities supporting an intent type."""

        normalized_intent = str(intent_type or "").strip().upper()
        records = []
        for capability in self._visible_generic_capabilities(tenant_scope):
            intents = {str(value).upper() for value in capability.get("intent_types_supported", [])}
            if normalized_intent in intents:
                records.append(_clone_json(capability))
        return records

    def find_by_task_type(self, task_type: str, tenant_scope: str | None = None) -> list[dict[str, Any]]:
        """Return safe generic capabilities matching a task type or known task phrase."""

        normalized_task = _normalized_text(task_type)
        intent_hints = {
            "capture_missing_input": ("CAPTURE_MISSING_INPUT",),
            "capture_missing_required_input": ("CAPTURE_MISSING_INPUT",),
            "missing_input": ("CAPTURE_MISSING_INPUT",),
            "source_ref": ("ATTACH_SOURCE_REF", "CAPTURE_MISSING_INPUT"),
            "make_video": ("SHOW_VISUAL_WORKSPACE",),
            "video_generation": ("SHOW_VISUAL_WORKSPACE",),
            "visual_feedback": ("SHOW_VISUAL_WORKSPACE",),
            "send_or_submit_request": ("REQUEST_APPROVAL",),
            "send_submit": ("REQUEST_APPROVAL",),
        }
        matched: dict[str, dict[str, Any]] = {}
        for intent in intent_hints.get(normalized_task, ()):
            for record in self.find_by_intent_type(intent, tenant_scope=tenant_scope):
                matched[record["capability_id"]] = record

        for capability in self._visible_generic_capabilities(tenant_scope):
            haystack = " ".join(
                (
                    _normalized_text(capability.get("taxonomy_type")),
                    " ".join(_normalized_text(item) for item in capability.get("applicable_task_types", [])),
                    " ".join(_normalized_text(item) for item in capability.get("search_keywords", [])),
                    _normalized_text(capability.get("capability_name")),
                    _normalized_text(capability.get("description")),
                )
            )
            if normalized_task and normalized_task in haystack:
                matched[str(capability["capability_id"])] = _clone_json(capability)

        return list(matched.values())

    def get_workflow_bindings(self, tenant_scope: str, workflow_ref: str) -> list[dict[str, Any]]:
        """Return workflow-scoped bindings only when tenant scope and workflow match."""

        if tenant_scope not in SAFE_TENANT_SCOPES:
            return []
        aliases = _workflow_aliases(workflow_ref)
        records: list[dict[str, Any]] = []
        for binding in self.payload.get("workflow_bindings", []):
            if binding.get("tenant_scope") != tenant_scope:
                continue
            if binding.get("workflow_ref") not in aliases:
                continue
            record = _clone_json(binding)
            record["scope_type"] = "WORKFLOW_SCOPED"
            record["usable_as_generic_capability"] = False
            records.append(record)
        return records

    def find_missing_requirements(
        self,
        capability_id: str,
        provided_inputs: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return required capability inputs that are absent from provided inputs."""

        capability = self._capability_by_id(capability_id)
        if capability is None:
            return []
        provided = {_normalized_text(key) for key in (provided_inputs or {})}
        provided_values = {_normalized_text(value) for value in (provided_inputs or {}).values()}
        requirements_by_id = {
            requirement.get("requirement_id"): requirement
            for requirement in self.payload.get("input_requirements", [])
        }
        missing: list[dict[str, Any]] = []
        for requirement_id in capability.get("input_requirements", []):
            requirement = requirements_by_id.get(requirement_id)
            if not requirement or not requirement.get("required", False):
                continue
            accepted_keys = {
                _normalized_text(requirement.get("requirement_id")),
                _normalized_text(requirement.get("input_name")),
                _normalized_text(requirement.get("input_type")),
            }
            if accepted_keys & provided or accepted_keys & provided_values:
                continue
            missing.append(_clone_json(requirement))
        return missing

    def validate_authority_profile(self, capability_id: str, requested_authority: dict[str, Any]) -> dict[str, Any]:
        """Validate requested authority against the capability profile, failing closed."""

        profile = self._authority_profile_for(capability_id)
        requested = {str(key): bool(value) for key, value in (requested_authority or {}).items()}
        authority_granted = {key: False for key in requested}
        reasons: list[str] = []
        if profile is None:
            reasons.append("unknown authority profile fails closed")
        else:
            for key, requested_value in requested.items():
                if not requested_value:
                    continue
                if key not in profile:
                    reasons.append(f"unknown authority key {key} fails closed")
                    continue
                if profile.get(key) is not True:
                    reason = f"requested {key} but profile has false live authority"
                    if "send" in key or "submit" in key or "external_action" in key:
                        reason += "; exact approval and proof receipt required"
                    reasons.append(reason)

        capability = self._capability_by_id(capability_id)
        if capability and capability.get("capability_status") in {"FUTURE_GATED", "BLOCKED_UNSAFE", "UNKNOWN_FAIL_CLOSED"}:
            reasons.append(f"capability status {capability.get('capability_status')} is not live-action usable")
        if capability_id.startswith("proposal:"):
            reasons.append("proposed candidates cannot grant authority")

        allowed = not reasons
        return {
            "capability_id": capability_id,
            "authority_profile_id": str(profile.get("authority_profile_id")) if profile else "",
            "allowed": allowed,
            "reason": "; ".join(reasons) if reasons else "No live authority requested; safe read/query only.",
            "requested_authority": _clone_json(requested),
            "authority_granted": authority_granted,
            "live_authority_allowed": bool(profile and profile.get("live_authority_allowed") is True),
            "missing_exact_approval": any(
                bool(value) and ("send" in key or "submit" in key or "external_action" in key)
                for key, value in requested.items()
            ),
        }

    def reject_unusable_capabilities(
        self,
        records: list[Mapping[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Split records into query-usable records and rejected/unusable records."""

        usable: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for record in records:
            clone = _clone_json(dict(record))
            reasons = self._rejection_reasons(clone)
            if reasons:
                rejected.append(
                    {
                        "record_id": _record_identifier(clone),
                        "record": clone,
                        "rejection_reasons": reasons,
                    }
                )
            else:
                usable.append(clone)
        return usable, rejected

    def _visible_generic_capabilities(self, tenant_scope: str | None) -> list[dict[str, Any]]:
        if tenant_scope is not None and tenant_scope not in SAFE_TENANT_SCOPES:
            scoped = filter_index_for_tenant(self.payload, tenant_scope)
            return _clone_json(scoped["generic_capabilities"])
        return [
            _clone_json(capability)
            for capability in self.payload.get("generic_capabilities", [])
            if capability.get("portability_scope") in {"USER_AGNOSTIC", "TENANT_SCOPED"}
        ]

    def _capability_by_id(self, capability_id: str) -> dict[str, Any] | None:
        for capability in self.payload.get("generic_capabilities", []):
            if capability.get("capability_id") == capability_id:
                return _clone_json(capability)
        return None

    def _authority_profile_for(self, capability_id: str) -> dict[str, Any] | None:
        for profile in self.payload.get("authority_profiles", []):
            if profile.get("capability_ref") == capability_id:
                return _clone_json(profile)
        return None

    def _rejection_reasons(self, record: Mapping[str, Any]) -> list[str]:
        reasons: list[str] = []
        if record.get("proposal_id") or record.get("candidate_status"):
            reasons.append("PROPOSED_CANDIDATE_USED_AS_LIVE_CAPABILITY")
        if record.get("fixture_id"):
            reasons.append("FIXTURE_ONLY_RECORD_NOT_USABLE_AS_GENERIC_CAPABILITY")
        if record.get("binding_id") and record.get("scope_type") != "WORKFLOW_SCOPED":
            reasons.append("WORKFLOW_BINDING_REQUIRES_MATCHING_SCOPE")

        lifecycle_status = str(record.get("lifecycle_status") or "")
        capability_status = str(record.get("capability_status") or "")
        if lifecycle_status in {"PROPOSED_CANDIDATE", "BUILT_UNVALIDATED", "FUTURE_GATED", "BLOCKED_UNSAFE", "RETIRED"}:
            reasons.append(f"LIFECYCLE_{lifecycle_status}_UNUSABLE")
        if capability_status in {"FIXTURE_ONLY", "FUTURE_GATED", "BLOCKED_UNSAFE", "UNKNOWN_FAIL_CLOSED"}:
            reasons.append(f"STATUS_{capability_status}_UNUSABLE")
        return reasons


def build_readback(
    capabilities: tuple[GenericCapability, ...],
    bindings: tuple[WorkflowCapabilityBinding, ...],
    fixtures: tuple[CapabilityFixture, ...],
    gaps: tuple[CapabilityGapRecord, ...],
    candidates: tuple[CapabilityProposalCandidate, ...],
) -> CapabilityIndexReadback:
    live_count = sum(1 for cap in capabilities if cap.capability_status == "LIVE_IMPLEMENTED")
    contract_count = sum(1 for cap in capabilities if cap.capability_status == "CONTRACT_ONLY")
    future_count = sum(1 for cap in capabilities if cap.capability_status == "FUTURE_GATED")
    blocked_count = sum(1 for cap in capabilities if cap.capability_status == "BLOCKED_UNSAFE")
    portable_count = sum(1 for cap in capabilities if cap.portability_scope in {"USER_AGNOSTIC", "TENANT_SCOPED"})
    return CapabilityIndexReadback(
        readback_id="readback:openclaw_capability_index:v0",
        status="CAPABILITY_INDEX_READY",
        operator_headline="Portable capability index ready",
        operator_message=(
            "OpenClaw indexed generic capabilities separately from workflow bindings and fixtures. "
            "The index is safe for intent validation and gap discovery, but it grants no live authority."
        ),
        capability_count=len(capabilities),
        live_implemented_count=live_count,
        contract_only_count=contract_count,
        future_gated_count=future_count,
        blocked_count=blocked_count,
        portable_capability_count=portable_count,
        workflow_scoped_count=len(bindings),
        fixture_only_count=len(fixtures),
        proposal_candidate_count=len(candidates),
        top_generic_capabilities=tuple(cap.capability_id for cap in capabilities[:10]),
        workflow_bindings=tuple(binding.binding_id for binding in bindings),
        top_gaps=tuple(gap.gap_id for gap in gaps),
        proposed_capabilities=tuple(candidate.proposal_id for candidate in candidates),
        next_safe_move="Use tenant-filtered query results when binding capabilities to real workflow context.",
    )


def _all_authority_false(
    profiles: tuple[CapabilityAuthorityProfile, ...],
    candidates: tuple[CapabilityProposalCandidate, ...] = (),
) -> bool:
    authority_profiles_false = all(
        not any(
            (
                profile.live_authority_allowed,
                profile.live_execution_allowed,
                profile.live_external_action_allowed,
                profile.live_model_call_allowed,
                profile.live_agent_dispatch_allowed,
                profile.live_outbound_message_send_allowed,
                profile.live_portal_access_allowed,
                profile.live_portal_submit_allowed,
                profile.live_browser_allowed,
                profile.live_secret_reveal_allowed,
                profile.raw_body_ingestion_allowed,
                profile.credential_handling_allowed,
            )
        )
        for profile in profiles
    )
    candidate_authority_false = all(
        all(value is False for value in candidate.authority_boundary.values())
        for candidate in candidates
    )
    boundary_false = all(value is False for value in AUTHORITY_BOUNDARY.values())
    return authority_profiles_false and candidate_authority_false and boundary_false


def build_payload(*, generated_at: str | None = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    generated_at = generated_at or _utc_generated_at()
    inputs = build_input_requirements()
    outputs = build_output_artifacts()
    capabilities = build_generic_capabilities(inputs, outputs)
    profiles = build_authority_profiles(capabilities)
    bindings = build_workflow_bindings()
    fixtures = build_fixtures()
    doctrine_gates = build_doctrine_gates()
    proposal_candidates = build_proposal_candidates()
    promotion_gates = build_promotion_gates(proposal_candidates)
    lifecycle_records = build_lifecycle_records(capabilities, proposal_candidates)
    gaps = build_gaps()
    query_examples = build_query_examples()
    blockers = build_blockers()
    generic_violations = _generic_capability_policy_violations(capabilities)
    readback = build_readback(capabilities, bindings, fixtures, gaps, proposal_candidates)

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "generated_at": generated_at,
        "contract_status": CONTRACT_STATUS,
        "taxonomy_types": TAXONOMY_TYPES,
        "capability_lifecycle_statuses": CAPABILITY_LIFECYCLE_STATUSES,
        "capability_statuses": CAPABILITY_STATUSES,
        "candidate_statuses": CANDIDATE_STATUSES,
        "portability_scopes": PORTABILITY_SCOPES,
        "input_types": INPUT_TYPES,
        "accepted_sources": ACCEPTED_SOURCES,
        "output_types": OUTPUT_TYPES,
        "compiler": asdict(build_compiler()),
        "model_schemas": _model_schemas(),
        "generic_capabilities": [asdict(capability) for capability in capabilities],
        "workflow_bindings": [asdict(binding) for binding in bindings],
        "fixtures": [asdict(fixture) for fixture in fixtures],
        "input_requirements": [asdict(requirement) for requirement in inputs],
        "output_artifacts": [asdict(output) for output in outputs],
        "authority_profiles": [asdict(profile) for profile in profiles],
        "doctrine_gates": [asdict(gate) for gate in doctrine_gates],
        "proposal_candidates": [asdict(candidate) for candidate in proposal_candidates],
        "promotion_gates": [asdict(gate) for gate in promotion_gates],
        "lifecycle_records": [asdict(record) for record in lifecycle_records],
        "capability_gaps": [asdict(gap) for gap in gaps],
        "query_examples": [asdict(example) for example in query_examples],
        "readback": asdict(readback),
        "blockers": [asdict(blocker) for blocker in blockers],
        "tenant_safety": {
            "valid_tenant_scopes": SAFE_TENANT_SCOPES,
            "invalid_tenant_behavior": "return generic safe definitions and zero tenant/client-specific bindings",
            "fixture_isolation": "fixtures require matching binding tenant scope and never become generic taxonomy",
            "invalid_tenant_query_example": filter_index_for_tenant(
                {
                    "generic_capabilities": [asdict(capability) for capability in capabilities],
                    "workflow_bindings": [asdict(binding) for binding in bindings],
                    "fixtures": [asdict(fixture) for fixture in fixtures],
                },
                "tenant_scope:invalid",
            ),
        },
        "machine_proof": {
            "all_live_authority_false": _all_authority_false(profiles, proposal_candidates),
            "generic_capability_policy_violations": generic_violations,
            "generic_capabilities_user_agnostic": not generic_violations,
            "workflow_specific_terms_allowed_only_in_bindings_fixtures_examples": True,
            "external_system_access_performed": False,
            "registry_mutation_performed": False,
            "candidate_promotion_performed": False,
            "self_modifying_code_performed": False,
            "model_call_performed": False,
            "agent_dispatch_performed": False,
            "workflow_run_performed": False,
            "credential_scan_performed": False,
            "raw_body_scan_performed": False,
            "mac_swift_change_performed": False,
            "git_push_pull_fetch_performed": False,
            "content_hash": "",
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    readback = payload["readback"]
    lines = [
        "# OpenClaw Capability Index",
        "",
        f"Status: {readback['status']}",
        f"Headline: {readback['operator_headline']}",
        "",
        readback["operator_message"],
        "",
        "## Counts",
        f"- Generic capabilities: {readback['capability_count']}",
        f"- Live implemented local rails: {readback['live_implemented_count']}",
        f"- Contract only: {readback['contract_only_count']}",
        f"- Future gated: {readback['future_gated_count']}",
        f"- Blocked unsafe: {readback['blocked_count']}",
        f"- Workflow bindings: {readback['workflow_scoped_count']}",
        f"- Fixture/example records: {readback['fixture_only_count']}",
        f"- Proposal candidates: {readback['proposal_candidate_count']}",
        "",
        "## Top Generic Capabilities",
    ]
    lines.extend(f"- {capability}" for capability in readback["top_generic_capabilities"])
    lines.extend(
        [
            "",
            "## Top Gaps",
        ]
    )
    lines.extend(f"- {gap}" for gap in readback["top_gaps"])
    lines.extend(
        [
            "",
            "## Quarantined Proposals",
        ]
    )
    lines.extend(f"- {proposal}" for proposal in readback["proposed_capabilities"])
    lines.extend(
        [
            "",
            "## Boundary",
            "- No live capability execution.",
            "- No registry mutation.",
            "- No model call or agent dispatch.",
            "- No workflow run or external action.",
            "- No secret reveal, credential handling, or raw-body ingestion.",
            "",
            f"Next safe move: {readback['next_safe_move']}",
            "",
        ]
    )
    return "\n".join(lines)


def write_exports(
    export_root: Path = DEFAULT_EXPORT_ROOT,
    *,
    generated_at: str | None = DEFAULT_GENERATED_AT,
) -> tuple[Path, Path, dict[str, Any]]:
    payload = build_payload(generated_at=generated_at)
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path, payload


def build_summary(payload: dict[str, Any], json_path: Path, operator_path: Path) -> dict[str, Any]:
    readback = payload["readback"]
    return {
        "read_model_id": payload["read_model_id"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path),
        "operator_path": str(operator_path),
        "generic_capability_count": readback["capability_count"],
        "workflow_binding_count": readback["workflow_scoped_count"],
        "fixture_count": readback["fixture_only_count"],
        "live_implemented_count": readback["live_implemented_count"],
        "contract_only_count": readback["contract_only_count"],
        "future_gated_count": readback["future_gated_count"],
        "blocked_count": readback["blocked_count"],
        "proposal_candidate_count": readback["proposal_candidate_count"],
        "query_example_count": len(payload["query_examples"]),
        "all_live_authority_false": payload["machine_proof"]["all_live_authority_false"],
        "generic_policy_violations": payload["machine_proof"]["generic_capability_policy_violations"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the OpenClaw portable capability index.")
    parser.add_argument("--format", choices=("json", "summary"), default="json")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    args = parser.parse_args(argv)

    json_path, operator_path, payload = write_exports(Path(args.export_root), generated_at=args.generated_at)
    output: dict[str, Any] = payload if args.format == "json" else build_summary(payload, json_path, operator_path)
    sys.stdout.write(stable_json(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

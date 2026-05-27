"""Automation Readiness / Feasibility Evaluator Contract v0.

This read-model identifies automation bottlenecks before OpenClaw invests in
polished workflow rails. It models manual fallback, assisted capture, supervised
automation, read-only automation, infrastructure needs, and dead-on-arrival
criteria. It does not run automation, access external systems, handle
credentials, generate invoices, send email, submit approvals, write ledgers, or
grant live execution authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "automation_readiness_feasibility_evaluator_contract_v0"
READ_MODEL_ID = "automation_readiness_feasibility_evaluator_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_AUTOMATION_FEASIBILITY_CONTRACT"

AUTOMATION_FEASIBILITY = (
    "LOW_HANGING_FRUIT",
    "ASSISTED_CAPTURE_FEASIBLE",
    "SUPERVISED_AUTOMATION_FEASIBLE",
    "READ_ONLY_AUTOMATION_FEASIBLE",
    "HIGH_RISK_BUT_POSSIBLE",
    "BLOCKED_PENDING_SECURITY",
    "BLOCKED_PENDING_CREDENTIAL_BROKER",
    "BLOCKED_PENDING_EXTERNAL_TERMS",
    "NOT_WORTH_AUTOMATING",
    "UNKNOWN_FAIL_CLOSED",
)

AUTOMATION_RISK = (
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
    "UNKNOWN_FAIL_CLOSED",
)

AUTOMATION_RECOMMENDATIONS = (
    "DO_MANUAL_FALLBACK_NOW",
    "BUILD_ASSISTED_CAPTURE_NEXT",
    "BUILD_SUPERVISED_AUTOMATION_TRIAL",
    "BUILD_READ_ONLY_AUTOMATION_TRIAL",
    "BUILD_PROTECTED_CREDENTIAL_BROKER_FIRST",
    "REQUIRES_SECURITY_DELTA",
    "REQUIRES_TERMS_REVIEW",
    "DEFER_NOT_WORTH_IT",
    "BLOCKED_DEAD_ON_ARRIVAL",
    "UNKNOWN_FAIL_CLOSED",
)

OPEN_SOURCE_SCOUT_RECOMMENDATIONS = (
    "REUSE",
    "WRAP",
    "ADAPT",
    "MINE_FOR_TESTS",
    "BUILD_CUSTOM",
    "AVOID",
)

OPEN_SOURCE_SCOUT_LICENSE_POSTURES = (
    "PERMISSIVE_OK",
    "WEAK_COPYLEFT_REVIEW",
    "COPYLEFT_REVIEW_REQUIRED",
    "COMMERCIAL_TERMS_REVIEW_REQUIRED",
    "LICENSE_UNKNOWN_FAIL_CLOSED",
)

INFRASTRUCTURE_TYPES = (
    "APPROVED_SITE_REGISTRY",
    "PROTECTED_CREDENTIAL_BROKER",
    "SUPERVISED_BROWSER_SESSION",
    "READ_ONLY_PORTAL_LOOKUP",
    "CAPTURE_ARTIFACT_STORE",
    "RECEIPT_WRITER",
    "APPROVAL_BUS",
    "WORKFLOW_SESSION_STORE",
    "SOURCE_CARD_REGISTRY",
    "PROTECTED_EVIDENCE_STORE",
    "UNKNOWN_FAIL_CLOSED",
)

REQUIRED_BOTTLENECK_ASSESSMENT_FIELDS = (
    "assessment_id",
    "display_name",
    "workflow_ref",
    "world",
    "lane",
    "bottleneck_step_id",
    "bottleneck_description",
    "manual_burden",
    "automation_value",
    "automation_feasibility",
    "automation_risk",
    "current_fallback",
    "best_near_term_path",
    "best_future_path",
    "dead_on_arrival_conditions",
    "required_gates",
    "required_receipts",
    "required_infrastructure",
    "operator_decision_needed",
    "next_safe_move",
)

REQUIRED_READINESS_EVALUATION_FIELDS = (
    "evaluation_id",
    "target_workflow",
    "target_step",
    "external_system",
    "current_stage",
    "recommended_next_stage",
    "manual_fallback_available",
    "assisted_path_available",
    "supervised_path_candidate",
    "autonomous_path_candidate",
    "missing_infrastructure",
    "missing_security_gates",
    "missing_operator_approvals",
    "missing_receipts",
    "terms_or_compliance_unknown",
    "technical_feasibility_unknown",
    "payoff_if_solved",
    "waste_risk_if_ignored",
    "recommendation",
    "next_safe_move",
)

REQUIRED_INFRASTRUCTURE_CANDIDATE_FIELDS = (
    "candidate_id",
    "display_name",
    "infrastructure_type",
    "supports_workflows",
    "supports_steps",
    "why_it_makes_life_easier",
    "required_before",
    "required_gates",
    "required_receipts",
    "build_priority",
    "current_authority_granted",
    "blocked_actions",
    "next_safe_move",
)

REQUIRED_DEAD_ON_ARRIVAL_FIELDS = (
    "criterion_id",
    "display_name",
    "applies_to",
    "condition",
    "why_it_blocks",
    "can_be_mitigated",
    "mitigation_candidate",
    "operator_visibility",
    "next_safe_move",
)

REQUIRED_OPEN_SOURCE_CAPABILITY_SCOUT_FIELDS = (
    "scout_id",
    "capability_needed",
    "target_runtime",
    "privacy_security_requirements",
    "acceptable_licenses",
    "dependency_weight_limit",
    "candidate_projects",
    "license_summary",
    "security_risk",
    "integration_plan",
    "code_can_be_used_directly",
    "ideas_tests_docs_only",
    "recommendation",
    "recommended_next_step",
)

AUTHORITY_BOUNDARY = {
    "automation_execution_allowed": False,
    "supervised_browser_execution_allowed": False,
    "read_only_portal_lookup_allowed": False,
    "credential_broker_active": False,
    "credential_handling_allowed": False,
    "network_operation_allowed": False,
    "open_source_package_download_allowed": False,
    "dependency_install_allowed": False,
    "license_evasion_allowed": False,
    "code_laundering_allowed": False,
    "coupa_access_allowed": False,
    "browser_automation_allowed": False,
    "email_send_allowed": False,
    "invoice_generation_allowed": False,
    "ledger_write_allowed": False,
    "approval_submission_allowed": False,
    "file_move_delete_cleanup_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "workflow_execution_allowed": False,
    "operator_input_persistence_allowed": False,
    "receipt_write_allowed": False,
    "protected_evidence_write_allowed": False,
    "session_state_write_allowed": False,
    "channel_message_send_allowed": False,
    "telegram_send_allowed": False,
    "raw_body_ingestion_allowed": False,
    "raw_private_body_ingestion_allowed": False,
    "stable_map_refresh_allowed_by_contract": False,
    "mac_sync_import_allowed": False,
    "mission_control_swift_change_allowed": False,
    "git_push_pull_fetch_allowed": False,
}

COMMON_BLOCKED_ACTIONS = (
    "automation execution",
    "supervised browser execution",
    "read-only portal lookup",
    "network or Coupa access",
    "credential handling",
    "invoice generation",
    "email send",
    "approval submission",
    "ledger write",
    "model/tool/agent/runtime/queue execution",
)

PRIOR_LANE_REFS = {
    "operator_work_mode_schema_bandwidth_policy": (
        "generated/read_models/operator_work_mode_schema_bandwidth_policy.json"
    ),
    "operator_solve_path_decision_node_contract": (
        "generated/read_models/operator_solve_path_decision_node_contract.json"
    ),
    "guided_capture_protected_evidence_path_contract": (
        "generated/read_models/guided_capture_protected_evidence_path_contract.json"
    ),
    "workflow_session_channel_projection_approval_bus_contract": (
        "generated/read_models/workflow_session_channel_projection_approval_bus_contract.json"
    ),
    "capital_hilton_coupa_po_retrieval_automation_candidate": (
        "generated/read_models/capital_hilton_coupa_po_retrieval_automation_candidate.json"
    ),
    "capital_hilton_proof_resolution_batch": (
        "generated/read_models/capital_hilton_proof_resolution_batch_manifest.json"
    ),
    "openclaw_work_terrain_reconciliation_batch": (
        "generated/read_models/openclaw_work_terrain_reconciliation_batch_manifest.json"
    ),
    "security_pass_contract": "generated/read_models/security_pass_contract.json",
    "protected_access_broker_concept": "generated/read_models/protected_access_broker_concept.json",
}


@dataclass(frozen=True)
class AutomationBottleneckAssessment:
    assessment_id: str
    display_name: str
    workflow_ref: str
    world: str
    lane: str
    bottleneck_step_id: str
    bottleneck_description: str
    manual_burden: str
    automation_value: str
    automation_feasibility: str
    automation_risk: str
    current_fallback: str
    best_near_term_path: str
    best_future_path: str
    dead_on_arrival_conditions: tuple[str, ...]
    required_gates: tuple[str, ...]
    required_receipts: tuple[str, ...]
    required_infrastructure: tuple[str, ...]
    operator_decision_needed: str
    next_safe_move: str


@dataclass(frozen=True)
class AutomationReadinessEvaluation:
    evaluation_id: str
    target_workflow: str
    target_step: str
    external_system: str
    current_stage: str
    recommended_next_stage: str
    manual_fallback_available: bool
    assisted_path_available: bool
    supervised_path_candidate: bool
    autonomous_path_candidate: bool
    missing_infrastructure: tuple[str, ...]
    missing_security_gates: tuple[str, ...]
    missing_operator_approvals: tuple[str, ...]
    missing_receipts: tuple[str, ...]
    terms_or_compliance_unknown: bool
    technical_feasibility_unknown: bool
    payoff_if_solved: str
    waste_risk_if_ignored: str
    recommendation: str
    next_safe_move: str


@dataclass(frozen=True)
class AutomationInfrastructureCandidate:
    candidate_id: str
    display_name: str
    infrastructure_type: str
    supports_workflows: tuple[str, ...]
    supports_steps: tuple[str, ...]
    why_it_makes_life_easier: str
    required_before: str
    required_gates: tuple[str, ...]
    required_receipts: tuple[str, ...]
    build_priority: str
    current_authority_granted: bool
    blocked_actions: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class AutomationDeadOnArrivalCriterion:
    criterion_id: str
    display_name: str
    applies_to: tuple[str, ...]
    condition: str
    why_it_blocks: str
    can_be_mitigated: bool
    mitigation_candidate: str
    operator_visibility: str
    next_safe_move: str


@dataclass(frozen=True)
class OpenSourceCandidateProject:
    project_ref: str
    project_name: str
    project_home: str
    license: str
    license_posture: str
    trust_basis: tuple[str, ...]
    security_risks: tuple[str, ...]
    dependency_weight: str
    integration_mode: str
    code_can_be_used_directly: bool
    ideas_tests_docs_only: bool
    attribution_required: bool
    commercial_implication: str
    recommendation: str
    rationale: str


@dataclass(frozen=True)
class OpenSourceCapabilityScout:
    scout_id: str
    capability_needed: str
    target_runtime: str
    privacy_security_requirements: tuple[str, ...]
    acceptable_licenses: tuple[str, ...]
    dependency_weight_limit: str
    candidate_projects: tuple[OpenSourceCandidateProject, ...]
    license_summary: str
    security_risk: str
    integration_plan: str
    code_can_be_used_directly: bool
    ideas_tests_docs_only: bool
    recommendation: str
    recommended_next_step: str


@dataclass(frozen=True)
class AutomationReadinessExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    bottleneck_assessment_count: int
    readiness_evaluation_count: int
    infrastructure_candidate_count: int
    dead_on_arrival_criteria_count: int
    open_source_scout_count: int
    action_authority_granted: bool


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _generated_at(value: str | None) -> str:
    return value or datetime.now(timezone.utc).isoformat(timespec="seconds")


def _all_authority_flags_false() -> bool:
    return all(value is False for value in AUTHORITY_BOUNDARY.values())


def default_dead_on_arrival_criteria() -> tuple[AutomationDeadOnArrivalCriterion, ...]:
    return (
        AutomationDeadOnArrivalCriterion(
            criterion_id="credentials_cannot_be_handled_safely",
            display_name="Credentials Cannot Be Handled Safely",
            applies_to=("external portals", "browser automation", "Coupa / PO lookup"),
            condition="automation requires credentials without an approved protected credential broker",
            why_it_blocks="OpenClaw must not store, reveal, scrape, or replay credentials through an unapproved path.",
            can_be_mitigated=True,
            mitigation_candidate="BUILD_PROTECTED_CREDENTIAL_BROKER_FIRST",
            operator_visibility="Show as a security blocker, not as a workflow problem Winship should manually solve forever.",
            next_safe_move="Use guided manual capture or stop before account access.",
        ),
        AutomationDeadOnArrivalCriterion(
            criterion_id="external_terms_prohibit_automation",
            display_name="External Terms Prohibit Automation",
            applies_to=("external portals", "Coupa / PO lookup", "email systems"),
            condition="terms, contract, or policy prohibits scripted or automated access",
            why_it_blocks="A technically feasible bot is still blocked if the external system does not allow it.",
            can_be_mitigated=False,
            mitigation_candidate="REQUIRES_TERMS_REVIEW",
            operator_visibility="Show terms review needed before building.",
            next_safe_move="Do manual fallback or request terms/legal review.",
        ),
        AutomationDeadOnArrivalCriterion(
            criterion_id="no_safe_read_only_path_exists",
            display_name="No Safe Read-Only Path Exists",
            applies_to=("portal lookup", "diagnostic repair", "workflow state checks"),
            condition="the step cannot be inspected without risking mutation or submission",
            why_it_blocks="Automation must prove it can observe without changing the external system.",
            can_be_mitigated=True,
            mitigation_candidate="SUPERVISED_BROWSER_SESSION",
            operator_visibility="Show read-only proof missing.",
            next_safe_move="Keep the step manual or supervised until read-only proof exists.",
        ),
        AutomationDeadOnArrivalCriterion(
            criterion_id="portal_requires_uncontrolled_mutation_risk",
            display_name="Portal Requires Uncontrolled Mutation Risk",
            applies_to=("browser automation", "approval portals", "finance portals"),
            condition="navigation or lookup can unintentionally submit, edit, or approve",
            why_it_blocks="OpenClaw cannot automate paths where observation and mutation are not cleanly separated.",
            can_be_mitigated=True,
            mitigation_candidate="APPROVED_SITE_REGISTRY",
            operator_visibility="Show mutation risk as a stop condition.",
            next_safe_move="Require site map, read-only mode, and Guardian gate before trial.",
        ),
        AutomationDeadOnArrivalCriterion(
            criterion_id="no_receipt_can_prove_no_mutation_occurred",
            display_name="No Receipt Can Prove No Mutation Occurred",
            applies_to=("browser automation", "portal lookup", "email send"),
            condition="the system cannot write or verify a no-mutation receipt",
            why_it_blocks="Without receipt proof, the operator cannot trust that automation only looked.",
            can_be_mitigated=True,
            mitigation_candidate="RECEIPT_WRITER",
            operator_visibility="Show receipt gap before automation trial.",
            next_safe_move="Build or reuse a receipt writer before supervised automation.",
        ),
        AutomationDeadOnArrivalCriterion(
            criterion_id="privacy_leakage_cannot_be_bounded",
            display_name="Privacy Leakage Cannot Be Bounded",
            applies_to=("screenshots", "email threads", "browser windows", "protected content"),
            condition="capture scope may include unrelated private data, credentials, tokens, or raw bodies",
            why_it_blocks="OpenClaw must not capture broad private context as a side effect.",
            can_be_mitigated=True,
            mitigation_candidate="PROTECTED_EVIDENCE_STORE",
            operator_visibility="Show as protected evidence / Guardian blocker.",
            next_safe_move="Use targeted capture policy or stop.",
        ),
        AutomationDeadOnArrivalCriterion(
            criterion_id="operator_approval_cannot_be_made_atomic",
            display_name="Operator Approval Cannot Be Made Atomic",
            applies_to=("Telegram approvals", "Mission Control approvals", "email send", "invoice submit"),
            condition="two channels can approve the same action or stale mirrors can remain visible",
            why_it_blocks="Split approval state can create duplicate send/submit risk.",
            can_be_mitigated=True,
            mitigation_candidate="APPROVAL_BUS",
            operator_visibility="Show approval bus required before live approvals.",
            next_safe_move="Use one canonical approval object with stale mirror invalidation.",
        ),
        AutomationDeadOnArrivalCriterion(
            criterion_id="cost_complexity_exceeds_workflow_payoff",
            display_name="Cost / Complexity Exceeds Workflow Payoff",
            applies_to=("low-frequency workflows", "one-off repairs", "narrow client work"),
            condition="automation build and maintenance cost exceeds the manual burden saved",
            why_it_blocks="Polishing a low-value rail wastes time better spent on true bottlenecks.",
            can_be_mitigated=False,
            mitigation_candidate="DEFER_NOT_WORTH_IT",
            operator_visibility="Show as not worth automating, not as failure.",
            next_safe_move="Keep manual fallback and do not overbuild.",
        ),
        AutomationDeadOnArrivalCriterion(
            criterion_id="external_system_changes_too_often",
            display_name="External System Changes Too Often",
            applies_to=("web portals", "Coupa screens", "third-party workflows"),
            condition="external screens or behavior change often enough to break deterministic automation",
            why_it_blocks="A fragile automation path can add more operator burden than it removes.",
            can_be_mitigated=True,
            mitigation_candidate="READ_ONLY_PORTAL_LOOKUP",
            operator_visibility="Show maintenance risk before build.",
            next_safe_move="Prefer assisted capture until stability is proven.",
        ),
        AutomationDeadOnArrivalCriterion(
            criterion_id="legal_compliance_review_required",
            display_name="Legal / Compliance Review Required",
            applies_to=("credentials", "finance portals", "customer/private data", "external account access"),
            condition="automation touches regulated, contractual, financial, or protected material",
            why_it_blocks="Compliance may decide the path, regardless of technical feasibility.",
            can_be_mitigated=True,
            mitigation_candidate="REQUIRES_TERMS_REVIEW",
            operator_visibility="Show compliance review required before build.",
            next_safe_move="Keep current workflow non-executing and route to review.",
        ),
    )


def default_open_source_capability_scouts() -> tuple[OpenSourceCapabilityScout, ...]:
    """Seed scout decisions for known capability classes.

    These are governance/evaluation records only. They do not fetch packages,
    import third-party code, install dependencies, or grant runtime authority.
    """

    safe_preview_candidates = (
        OpenSourceCandidateProject(
            project_ref="dangerzone_backend_sanitizer",
            project_name="Dangerzone",
            project_home="https://github.com/freedomofpress/dangerzone",
            license="AGPL-3.0",
            license_posture="COPYLEFT_REVIEW_REQUIRED",
            trust_basis=("Freedom of the Press Foundation project", "purpose-built document sanitization workflow"),
            security_risks=(
                "container/sandbox dependency must be verified on target runtime",
                "AGPL/commercial packaging implications must be reviewed before bundling",
                "untrusted documents must stay isolated from production workflow state",
            ),
            dependency_weight="MEDIUM_HEAVY",
            integration_mode="WRAP_AS_BACKEND_PROVIDER_AFTER_LICENSE_SECURITY_REVIEW",
            code_can_be_used_directly=False,
            ideas_tests_docs_only=False,
            attribution_required=True,
            commercial_implication="Copyleft obligations require legal review before app/backend distribution.",
            recommendation="WRAP",
            rationale="Best fit for future untrusted/legal/discovery safe preview if installed as an isolated provider with receipts.",
        ),
        OpenSourceCandidateProject(
            project_ref="libreoffice_headless_converter",
            project_name="LibreOffice headless",
            project_home="https://www.libreoffice.org/",
            license="MPL-2.0 / LGPL family components",
            license_posture="WEAK_COPYLEFT_REVIEW",
            trust_basis=("mature office suite", "common headless conversion path"),
            security_risks=(
                "not primarily a malware sanitizer",
                "must run sandboxed for untrusted input",
                "document conversion can be heavyweight for low-latency client flows",
            ),
            dependency_weight="HEAVY",
            integration_mode="ADAPT_ONLY_FOR_SANDBOXED_OFFICE_TO_PDF_CONVERSION",
            code_can_be_used_directly=False,
            ideas_tests_docs_only=False,
            attribution_required=True,
            commercial_implication="Weak-copyleft/distribution terms need packaging review.",
            recommendation="ADAPT",
            rationale="Useful for trusted or sandboxed office conversion, but not sufficient alone for untrusted discovery-grade previews.",
        ),
        OpenSourceCandidateProject(
            project_ref="mac_quicklook_client_preview",
            project_name="macOS Quick Look",
            project_home="https://developer.apple.com/documentation/quicklook",
            license="Platform API / Apple SDK terms",
            license_posture="COMMERCIAL_TERMS_REVIEW_REQUIRED",
            trust_basis=("native platform preview surface", "no backend document renderer required"),
            security_risks=(
                "Mac-only client surface",
                "does not create backend safe-preview proof by itself",
                "not a cross-platform server-side sanitizer",
            ),
            dependency_weight="LIGHT",
            integration_mode="REUSE_CLIENT_API_FOR_CURRENT_MAC_INSPECTION",
            code_can_be_used_directly=False,
            ideas_tests_docs_only=False,
            attribution_required=False,
            commercial_implication="Use is governed by Apple platform terms, not open-source reuse.",
            recommendation="REUSE",
            rationale="Best current path for Mac invoice candidate inspection because it avoids backend rendering and keeps latency low.",
        ),
        OpenSourceCandidateProject(
            project_ref="onlyoffice_document_server",
            project_name="ONLYOFFICE Document Server",
            project_home="https://github.com/ONLYOFFICE/DocumentServer",
            license="AGPL-3.0 / commercial editions",
            license_posture="COPYLEFT_REVIEW_REQUIRED",
            trust_basis=("known document server project", "browser-based viewing/editing capability"),
            security_risks=(
                "long-running network-facing service",
                "heavy operational footprint",
                "wider attack surface than needed for v0 preview",
            ),
            dependency_weight="TOO_HEAVY_FOR_V0",
            integration_mode="AVOID_FOR_NOW",
            code_can_be_used_directly=False,
            ideas_tests_docs_only=True,
            attribution_required=True,
            commercial_implication="AGPL/commercial edition choice requires legal and product review.",
            recommendation="AVOID",
            rationale="Too heavy for current low-latency Mission Control preview needs.",
        ),
    )
    return (
        OpenSourceCapabilityScout(
            scout_id="safe_preview_provider_open_source_scout_v0",
            capability_needed="safe preview provider for invoice, legal, discovery, and untrusted document artifacts",
            target_runtime="PC/OpenClaw backend plus lightweight native Mission Control clients",
            privacy_security_requirements=(
                "no raw private document bodies in read-models",
                "untrusted documents isolated before conversion",
                "no long-running network-facing viewer unless explicitly approved",
                "conversion receipts must record hashes and provider without exposing private content",
                "Mac invoice candidate inspection should remain low-latency and client-native when possible",
            ),
            acceptable_licenses=("MIT", "Apache-2.0", "BSD", "MPL-2.0/LGPL with review", "AGPL-3.0 only with legal/commercial review"),
            dependency_weight_limit="LIGHT_FOR_CURRENT_MAC_PREVIEW_MEDIUM_ALLOWED_FOR_FUTURE_BACKEND_SANITIZER",
            candidate_projects=safe_preview_candidates,
            license_summary="Quick Look is the current client-native path; Dangerzone is promising but AGPL; LibreOffice needs sandboxing and license review; ONLYOFFICE is too heavy for v0.",
            security_risk="MEDIUM until backend sanitizer sandbox, license review, and conversion receipts are approved.",
            integration_plan="Reuse Mac Quick Look now; wrap Dangerzone later behind safe_preview_provider readiness, receipts, sandbox checks, and production_ready=false until approved.",
            code_can_be_used_directly=False,
            ideas_tests_docs_only=False,
            recommendation="WRAP",
            recommended_next_step="Keep current Mac Quick Look path; continue Dangerzone backend provider only through the existing safe_preview_provider readiness lane.",
        ),
    )


def default_infrastructure_candidates() -> tuple[AutomationInfrastructureCandidate, ...]:
    return (
        AutomationInfrastructureCandidate(
            candidate_id="approved_site_registry",
            display_name="Approved Site Registry",
            infrastructure_type="APPROVED_SITE_REGISTRY",
            supports_workflows=("Capital Hilton invoice", "automation trial session"),
            supports_steps=("Coupa / PO lookup", "read-only portal lookup"),
            why_it_makes_life_easier="OpenClaw can know which external sites are allowed, which pages are read-only, and when to stop.",
            required_before="any supervised or read-only portal automation trial",
            required_gates=("Guardian review", "terms review if external system policy is unknown"),
            required_receipts=("site approval receipt", "no-mutation proof receipt"),
            build_priority="HIGH_FOR_COUPA_AUTOMATION",
            current_authority_granted=False,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Model site rules before any portal automation.",
        ),
        AutomationInfrastructureCandidate(
            candidate_id="protected_credential_broker",
            display_name="Protected Credential Broker",
            infrastructure_type="PROTECTED_CREDENTIAL_BROKER",
            supports_workflows=("Capital Hilton invoice", "future client delivery portals"),
            supports_steps=("credential-gated lookup", "supervised browser session"),
            why_it_makes_life_easier="Winship should not paste credentials into workflow rails or make the app remember unsafe secrets.",
            required_before="any credential-gated automation",
            required_gates=("Security Pass delta", "Guardian credential handling review"),
            required_receipts=("credential broker approval receipt",),
            build_priority="BLOCKING_FOR_CREDENTIAL_GATED_AUTOMATION",
            current_authority_granted=False,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Keep credential-gated automation blocked until this exists and is approved.",
        ),
        AutomationInfrastructureCandidate(
            candidate_id="supervised_browser_session",
            display_name="Supervised Browser Session",
            infrastructure_type="SUPERVISED_BROWSER_SESSION",
            supports_workflows=("Capital Hilton invoice", "automation trial session"),
            supports_steps=("Coupa / PO lookup", "protected evidence capture"),
            why_it_makes_life_easier="OpenClaw could eventually guide and observe a bounded session without pretending it owns the account.",
            required_before="supervised automation trial",
            required_gates=("approved site registry", "protected credential broker if credentials are required", "Guardian review"),
            required_receipts=("session start receipt", "no-mutation receipt", "capture artifact receipt"),
            build_priority="AFTER_ASSISTED_CAPTURE",
            current_authority_granted=False,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Build assisted capture first; then evaluate supervised trial.",
        ),
        AutomationInfrastructureCandidate(
            candidate_id="read_only_portal_lookup",
            display_name="Read-Only Portal Lookup",
            infrastructure_type="READ_ONLY_PORTAL_LOOKUP",
            supports_workflows=("Capital Hilton invoice", "client project delivery"),
            supports_steps=("PO/reference lookup", "status lookup"),
            why_it_makes_life_easier="A proven read-only path could remove repeated manual portal checking.",
            required_before="autonomous or semi-autonomous lookup",
            required_gates=("read-only proof", "terms review", "Guardian review"),
            required_receipts=("lookup receipt", "no-mutation receipt"),
            build_priority="FUTURE_AFTER_SUPERVISED_PROOF",
            current_authority_granted=False,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Treat as future candidate, not current authority.",
        ),
        AutomationInfrastructureCandidate(
            candidate_id="capture_artifact_store",
            display_name="Capture Artifact Store",
            infrastructure_type="CAPTURE_ARTIFACT_STORE",
            supports_workflows=("Capital Hilton invoice", "Check Engine diagnostic", "draft review"),
            supports_steps=("guided capture", "diagnostic screenshot", "source-card reference"),
            why_it_makes_life_easier="The operator should confirm the moment; OpenClaw should handle storage policy later.",
            required_before="file-producing capture lanes",
            required_gates=("protected evidence policy", "Guardian review for sensitive captures"),
            required_receipts=("artifact receipt", "hash receipt"),
            build_priority="HIGH_FOR_GUIDED_CAPTURE",
            current_authority_granted=False,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Keep capture modeled until storage and receipts are approved.",
        ),
        AutomationInfrastructureCandidate(
            candidate_id="receipt_writer",
            display_name="Receipt Writer",
            infrastructure_type="RECEIPT_WRITER",
            supports_workflows=("all work modes",),
            supports_steps=("operator confirmation", "capture outcome", "approval invalidation", "automation trial"),
            why_it_makes_life_easier="Winship answers once; receipts let the rest of the system update without manual bookkeeping.",
            required_before="workflow advancement or automation trial",
            required_gates=("SQLite receipt policy",),
            required_receipts=("writer validation receipt",),
            build_priority="FOUNDATIONAL",
            current_authority_granted=False,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Keep this contract as target-only until writer lane is approved.",
        ),
        AutomationInfrastructureCandidate(
            candidate_id="approval_bus",
            display_name="Approval Bus",
            infrastructure_type="APPROVAL_BUS",
            supports_workflows=("Capital Hilton invoice", "Cassandra draft send", "automation trial"),
            supports_steps=("single approval", "stale mirror invalidation", "send/submit gate"),
            why_it_makes_life_easier="Approving once should close every mirror and prevent duplicate approvals.",
            required_before="live approval surfaces or send/submit actions",
            required_gates=("workflow session store", "Guardian review for protected payloads"),
            required_receipts=("approval receipt", "invalidation receipt"),
            build_priority="FOUNDATIONAL_FOR_APPROVALS",
            current_authority_granted=False,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Use approval bus model before any live approval control.",
        ),
        AutomationInfrastructureCandidate(
            candidate_id="workflow_session_store",
            display_name="Workflow Session Store",
            infrastructure_type="WORKFLOW_SESSION_STORE",
            supports_workflows=("all active workflow sessions",),
            supports_steps=("canonical state", "channel projection", "staleness", "reopen"),
            why_it_makes_life_easier="Every surface reads one workflow state instead of making Winship reconcile duplicates.",
            required_before="multi-channel workflow control",
            required_gates=("receipt-backed session state policy",),
            required_receipts=("session state receipt", "reopen receipt"),
            build_priority="FOUNDATIONAL",
            current_authority_granted=False,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Keep session state modeled until writer authority exists.",
        ),
        AutomationInfrastructureCandidate(
            candidate_id="source_card_registry",
            display_name="Source Card Registry",
            infrastructure_type="SOURCE_CARD_REGISTRY",
            supports_workflows=("work terrain reconciliation", "Capital Hilton rate source", "creative project context"),
            supports_steps=("source note reference", "proof/source pointer", "context carry-forward"),
            why_it_makes_life_easier="A source card lets OpenClaw point to proof without throwing raw source walls into the helm.",
            required_before="source-card proof rendering",
            required_gates=("metadata-only proof policy",),
            required_receipts=("source-card receipt",),
            build_priority="MEDIUM",
            current_authority_granted=False,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Use source-card refs as proof/detail, not action authority.",
        ),
        AutomationInfrastructureCandidate(
            candidate_id="protected_evidence_store",
            display_name="Protected Evidence Store",
            infrastructure_type="PROTECTED_EVIDENCE_STORE",
            supports_workflows=("Capital Hilton invoice", "security review", "client project delivery"),
            supports_steps=("protected screenshot", "PDF reference", "email thread reference"),
            why_it_makes_life_easier="Sensitive evidence gets a safe reference instead of a raw body pasted into the app.",
            required_before="protected evidence writes",
            required_gates=("Guardian review", "protected storage policy"),
            required_receipts=("protected evidence receipt", "hash receipt"),
            build_priority="HIGH_FOR_PROTECTED_CAPTURE",
            current_authority_granted=False,
            blocked_actions=COMMON_BLOCKED_ACTIONS,
            next_safe_move="Keep evidence references metadata-only until store exists.",
        ),
    )


def default_bottleneck_assessments() -> tuple[AutomationBottleneckAssessment, ...]:
    return (
        AutomationBottleneckAssessment(
            assessment_id="capital_hilton_coupa_po_lookup_bottleneck",
            display_name="Capital Hilton Coupa / PO Lookup Bottleneck",
            workflow_ref="capital_hilton_invoice_workflow_session",
            world="Finance",
            lane="Capital Hilton",
            bottleneck_step_id="coupa_po_payment_reference_lookup",
            bottleneck_description="Coupa / PO / payment reference lookup is the repeated external-system step blocking clean invoice completion.",
            manual_burden="operator must find the right screen, avoid credentials leakage, confirm PO/reference metadata, and capture proof safely",
            automation_value="high, because it removes repeated portal searching and proof bookkeeping",
            automation_feasibility="ASSISTED_CAPTURE_FEASIBLE",
            automation_risk="HIGH",
            current_fallback="guided manual capture",
            best_near_term_path="build assisted capture first",
            best_future_path="evaluate supervised/read-only automation after site, credential, receipt, and Guardian gates exist",
            dead_on_arrival_conditions=(
                "credentials_cannot_be_handled_safely",
                "external_terms_prohibit_automation",
                "privacy_leakage_cannot_be_bounded",
                "no_receipt_can_prove_no_mutation_occurred",
            ),
            required_gates=("Guardian review", "terms review if unknown", "operator final authority"),
            required_receipts=("capture artifact receipt", "no-mutation receipt", "automation trial receipt"),
            required_infrastructure=(
                "APPROVED_SITE_REGISTRY",
                "PROTECTED_CREDENTIAL_BROKER",
                "SUPERVISED_BROWSER_SESSION",
                "RECEIPT_WRITER",
            ),
            operator_decision_needed="Choose manual capture now or authorize future investigation of a supervised automation path.",
            next_safe_move="Use guided manual capture now. Do not access Coupa or automate.",
        ),
        AutomationBottleneckAssessment(
            assessment_id="capital_hilton_invoice_pdf_generation_bottleneck",
            display_name="Capital Hilton Invoice PDF Generation Bottleneck",
            workflow_ref="capital_hilton_invoice_workflow_session",
            world="Finance",
            lane="Capital Hilton",
            bottleneck_step_id="invoice_artifact_generation",
            bottleneck_description="Generating the correct invoice artifact requires math, formatting, proof status, and preview validation.",
            manual_burden="operator must ensure dates, rate, subtotal, recipient, workbook/PDF format, and attachments are correct",
            automation_value="high after facts and proof are confirmed",
            automation_feasibility="LOW_HANGING_FRUIT",
            automation_risk="MEDIUM",
            current_fallback="artifact preview remains future-gated; no invoice is generated now",
            best_near_term_path="artifact preview contract with math/format validation",
            best_future_path="deterministic PDF/Excel generation only after proof and approval bus gates",
            dead_on_arrival_conditions=("operator_approval_cannot_be_made_atomic",),
            required_gates=("math validation", "format validation", "operator approval", "Guardian if protected material"),
            required_receipts=("artifact preview receipt", "math validation receipt", "artifact generation receipt"),
            required_infrastructure=("RECEIPT_WRITER", "APPROVAL_BUS"),
            operator_decision_needed="Confirm whether the preview is correct when a future preview lane exists.",
            next_safe_move="Model artifact preview; do not generate invoice files.",
        ),
        AutomationBottleneckAssessment(
            assessment_id="cassandra_email_send_bottleneck",
            display_name="Cassandra Email Send Bottleneck",
            workflow_ref="cassandra_clara_draft_review_session",
            world="Communications",
            lane="Cassandra / Clara drafts",
            bottleneck_step_id="send_authority_and_attachment_correctness",
            bottleneck_description="Email send is blocked until draft text, attachments, approval, and receipt state are all correct.",
            manual_burden="operator must review draft, check attachment correctness, and provide final signature",
            automation_value="medium to high when draft packets and approval bus are mature",
            automation_feasibility="BLOCKED_PENDING_SECURITY",
            automation_risk="HIGH",
            current_fallback="manual review and no send authority",
            best_near_term_path="draft packet preview plus single approval bus",
            best_future_path="send receipt only after approval bus and dispatch authority exist",
            dead_on_arrival_conditions=("operator_approval_cannot_be_made_atomic", "privacy_leakage_cannot_be_bounded"),
            required_gates=("operator final authority", "Guardian review if protected payload", "approval bus"),
            required_receipts=("draft preview receipt", "approval receipt", "send receipt"),
            required_infrastructure=("APPROVAL_BUS", "WORKFLOW_SESSION_STORE", "RECEIPT_WRITER"),
            operator_decision_needed="Review draft before any future send path.",
            next_safe_move="Keep email dispatch blocked and model draft preview only.",
        ),
        AutomationBottleneckAssessment(
            assessment_id="telegram_approval_split_brain_bottleneck",
            display_name="Telegram / Mission Control Approval Split-Brain Bottleneck",
            workflow_ref="capital_hilton_invoice_workflow_session",
            world="Operations",
            lane="Channel projection / approval bus",
            bottleneck_step_id="duplicate_stale_approval_mirrors",
            bottleneck_description="Duplicate or stale approvals across Telegram and Mission Control can make one human answer appear twice.",
            manual_burden="operator must remember which channel has current state if the bus does not exist",
            automation_value="high because approve-once-close-everywhere removes duplicate approval risk",
            automation_feasibility="LOW_HANGING_FRUIT",
            automation_risk="CRITICAL",
            current_fallback="no live approval controls",
            best_near_term_path="single approval bus with atomic invalidation",
            best_future_path="approval visible in multiple channels only after canonical session store exists",
            dead_on_arrival_conditions=("operator_approval_cannot_be_made_atomic",),
            required_gates=("approval bus validation", "session state receipt policy"),
            required_receipts=("approval receipt", "stale mirror invalidation receipt"),
            required_infrastructure=("APPROVAL_BUS", "WORKFLOW_SESSION_STORE", "RECEIPT_WRITER"),
            operator_decision_needed="None now; keep approvals modeled and non-live.",
            next_safe_move="Build approval bus before any Telegram/Mission Control approval surface goes live.",
        ),
        AutomationBottleneckAssessment(
            assessment_id="work_terrain_consolidation_bottleneck",
            display_name="Work Terrain Consolidation Bottleneck",
            workflow_ref="chief_terrain_reconciliation_session",
            world="Operations / Build",
            lane="Work Terrain reconciliation",
            bottleneck_step_id="old_notes_built_artifacts_gap_reconciliation",
            bottleneck_description="Old notes and built artifacts are hard to reconcile without classifying current/stale/source/built gaps.",
            manual_burden="operator or Chief must inspect many metadata refs and avoid treating old notes as current truth",
            automation_value="medium, because better reconciliation prevents app clutter and stale tasks",
            automation_feasibility="ASSISTED_CAPTURE_FEASIBLE",
            automation_risk="MEDIUM",
            current_fallback="terrain gap detector and metadata-first review",
            best_near_term_path="terrain gap detector with guided consolidation path",
            best_future_path="guided consolidation recommendations, not file movement",
            dead_on_arrival_conditions=("cost_complexity_exceeds_workflow_payoff",),
            required_gates=("metadata-only terrain policy", "operator final reconciliation decision"),
            required_receipts=("classification candidate receipt", "consolidation decision receipt"),
            required_infrastructure=("SOURCE_CARD_REGISTRY", "RECEIPT_WRITER"),
            operator_decision_needed="Pick what should stay current when a guided path exists.",
            next_safe_move="Use terrain gap detector; do not move, delete, archive, or rewrite files.",
        ),
        AutomationBottleneckAssessment(
            assessment_id="check_engine_repair_bottleneck",
            display_name="Check Engine Repair Bottleneck",
            workflow_ref="check_engine_diagnostic_session",
            world="Build",
            lane="Check Engine",
            bottleneck_step_id="unsafe_repair_without_proof_or_rollback",
            bottleneck_description="System repair can be unsafe if evidence, scope, tests, rollback, and receipts are not present.",
            manual_burden="operator or Chief must distinguish real breakage from noise and avoid unsafe repairs",
            automation_value="medium to high when failures are repetitive and rollback is proven",
            automation_feasibility="HIGH_RISK_BUT_POSSIBLE",
            automation_risk="HIGH",
            current_fallback="manual diagnostic check with proof",
            best_near_term_path="diagnostic evidence and next safe check",
            best_future_path="supervised repair trial only after receipts, tests, and rollback proof",
            dead_on_arrival_conditions=("no_receipt_can_prove_no_mutation_occurred", "cost_complexity_exceeds_workflow_payoff"),
            required_gates=("test harness receipt", "rollback receipt", "Guardian/security delta if authority changes"),
            required_receipts=("diagnostic receipt", "test receipt", "rollback receipt", "repair trial receipt"),
            required_infrastructure=("RECEIPT_WRITER", "WORKFLOW_SESSION_STORE"),
            operator_decision_needed="Decide whether the diagnostic evidence is worth a future supervised repair lane.",
            next_safe_move="Check what is actually broken; do not repair in this contract.",
        ),
    )


def default_readiness_evaluations() -> tuple[AutomationReadinessEvaluation, ...]:
    return (
        AutomationReadinessEvaluation(
            evaluation_id="capital_hilton_coupa_po_lookup_readiness",
            target_workflow="capital_hilton_invoice_workflow_session",
            target_step="coupa_po_payment_reference_lookup",
            external_system="Coupa / payment reference portal",
            current_stage="manual fallback with guided capture modeled",
            recommended_next_stage="assisted capture before supervised automation",
            manual_fallback_available=True,
            assisted_path_available=True,
            supervised_path_candidate=True,
            autonomous_path_candidate=False,
            missing_infrastructure=("APPROVED_SITE_REGISTRY", "PROTECTED_CREDENTIAL_BROKER", "SUPERVISED_BROWSER_SESSION", "RECEIPT_WRITER"),
            missing_security_gates=("Guardian review", "terms review if unknown", "security delta before credential/browser authority"),
            missing_operator_approvals=("operator final automation trial approval",),
            missing_receipts=("site approval receipt", "no-mutation receipt", "capture receipt", "automation trial receipt"),
            terms_or_compliance_unknown=True,
            technical_feasibility_unknown=True,
            payoff_if_solved="large reduction in repeated portal lookup and proof-linking burden",
            waste_risk_if_ignored="building pretty invoice rails while the true blocker remains external lookup",
            recommendation="BUILD_ASSISTED_CAPTURE_NEXT",
            next_safe_move="Build assisted capture target first; do not access Coupa now.",
        ),
        AutomationReadinessEvaluation(
            evaluation_id="capital_hilton_invoice_artifact_readiness",
            target_workflow="capital_hilton_invoice_workflow_session",
            target_step="invoice_artifact_generation",
            external_system="local artifact generation only after proof",
            current_stage="blocked; preview contract not live",
            recommended_next_stage="artifact preview after facts and proof refs are confirmed",
            manual_fallback_available=True,
            assisted_path_available=False,
            supervised_path_candidate=False,
            autonomous_path_candidate=False,
            missing_infrastructure=("RECEIPT_WRITER", "APPROVAL_BUS"),
            missing_security_gates=("math validation", "format validation", "operator approval"),
            missing_operator_approvals=("invoice artifact approval",),
            missing_receipts=("artifact preview receipt", "math validation receipt", "generation receipt"),
            terms_or_compliance_unknown=False,
            technical_feasibility_unknown=False,
            payoff_if_solved="clean preview-to-approval path for invoice artifact creation",
            waste_risk_if_ignored="artifact work may be polished before proof facts are ready",
            recommendation="DO_MANUAL_FALLBACK_NOW",
            next_safe_move="Do not generate invoice artifacts; keep facts/proof path first.",
        ),
        AutomationReadinessEvaluation(
            evaluation_id="telegram_approval_bus_readiness",
            target_workflow="capital_hilton_invoice_workflow_session",
            target_step="approval_projection",
            external_system="Telegram plus Mission Control projection",
            current_stage="approval modeled, no live approval controls",
            recommended_next_stage="approval bus and atomic invalidation",
            manual_fallback_available=True,
            assisted_path_available=False,
            supervised_path_candidate=False,
            autonomous_path_candidate=False,
            missing_infrastructure=("APPROVAL_BUS", "WORKFLOW_SESSION_STORE", "RECEIPT_WRITER"),
            missing_security_gates=("approval bus validation",),
            missing_operator_approvals=("operator final approval policy",),
            missing_receipts=("approval receipt", "invalidation receipt"),
            terms_or_compliance_unknown=False,
            technical_feasibility_unknown=False,
            payoff_if_solved="prevents stale or duplicate approval mirrors before any send/submit path exists",
            waste_risk_if_ignored="approval UI could create split-brain state and duplicate action risk",
            recommendation="BUILD_ASSISTED_CAPTURE_NEXT",
            next_safe_move="Finish approval bus infrastructure before live approvals.",
        ),
        AutomationReadinessEvaluation(
            evaluation_id="check_engine_repair_readiness",
            target_workflow="check_engine_diagnostic_session",
            target_step="repair_trial_candidate",
            external_system="local repo/system repair",
            current_stage="diagnostic evidence only",
            recommended_next_stage="supervised repair trial only after receipts and rollback proof",
            manual_fallback_available=True,
            assisted_path_available=True,
            supervised_path_candidate=True,
            autonomous_path_candidate=False,
            missing_infrastructure=("RECEIPT_WRITER", "WORKFLOW_SESSION_STORE"),
            missing_security_gates=("Security delta if repair authority changes", "rollback gate"),
            missing_operator_approvals=("operator repair approval",),
            missing_receipts=("diagnostic receipt", "test receipt", "rollback receipt"),
            terms_or_compliance_unknown=False,
            technical_feasibility_unknown=True,
            payoff_if_solved="faster repair of repetitive system failures without unsafe blind changes",
            waste_risk_if_ignored="automation could repair the wrong thing or hide risk",
            recommendation="REQUIRES_SECURITY_DELTA",
            next_safe_move="Keep repair blocked; gather diagnostic proof only.",
        ),
    )


def relationship_to_prior_lanes(repo_root: str | Path = ROOT) -> list[dict[str, Any]]:
    root = Path(repo_root)
    return [
        {
            "lane_id": lane_id,
            "read_model_ref": ref,
            "observation_status": "OBSERVED" if (root / ref).exists() else "NOT_OBSERVED_OR_PENDING",
            "relationship": "automation feasibility evaluates bottlenecks across prior deterministic rails without duplicating them",
        }
        for lane_id, ref in PRIOR_LANE_REFS.items()
    ]


def build_automation_readiness_feasibility_evaluator_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    bottlenecks = [asdict(item) for item in default_bottleneck_assessments()]
    evaluations = [asdict(item) for item in default_readiness_evaluations()]
    infrastructure = [asdict(item) for item in default_infrastructure_candidates()]
    doa_criteria = [asdict(item) for item in default_dead_on_arrival_criteria()]
    open_source_scouts = [asdict(item) for item in default_open_source_capability_scouts()]
    prior_lanes = relationship_to_prior_lanes(repo_root)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_id": f"{READ_MODEL_ID}_v0",
        "generated_at": _generated_at(generated_at),
        "contract_status": CONTRACT_STATUS,
        "core_doctrine": {
            "manual_is_fallback": True,
            "manual_is_not_target": True,
            "assisted_workflow_is_bridge": True,
            "governed_automation_is_target": True,
            "find_bottleneck_before_polishing_path": True,
            "capital_hilton_is_steel_thread_example_not_boundary": True,
            "app_wide_workflow_agnostic_contract": True,
        },
        "automation_feasibility_values": list(AUTOMATION_FEASIBILITY),
        "automation_risk_values": list(AUTOMATION_RISK),
        "automation_recommendations": list(AUTOMATION_RECOMMENDATIONS),
        "open_source_scout_recommendations": list(OPEN_SOURCE_SCOUT_RECOMMENDATIONS),
        "open_source_scout_license_postures": list(OPEN_SOURCE_SCOUT_LICENSE_POSTURES),
        "infrastructure_types": list(INFRASTRUCTURE_TYPES),
        "automation_bottleneck_assessment_schema": {
            "structure": "AutomationBottleneckAssessment",
            "required_fields": list(REQUIRED_BOTTLENECK_ASSESSMENT_FIELDS),
        },
        "automation_readiness_evaluation_schema": {
            "structure": "AutomationReadinessEvaluation",
            "required_fields": list(REQUIRED_READINESS_EVALUATION_FIELDS),
        },
        "automation_infrastructure_candidate_schema": {
            "structure": "AutomationInfrastructureCandidate",
            "required_fields": list(REQUIRED_INFRASTRUCTURE_CANDIDATE_FIELDS),
        },
        "automation_dead_on_arrival_criterion_schema": {
            "structure": "AutomationDeadOnArrivalCriterion",
            "required_fields": list(REQUIRED_DEAD_ON_ARRIVAL_FIELDS),
        },
        "open_source_capability_scout_schema": {
            "structure": "OpenSourceCapabilityScout",
            "required_fields": list(REQUIRED_OPEN_SOURCE_CAPABILITY_SCOUT_FIELDS),
            "candidate_recommendations": list(OPEN_SOURCE_SCOUT_RECOMMENDATIONS),
            "license_postures": list(OPEN_SOURCE_SCOUT_LICENSE_POSTURES),
        },
        "bottleneck_assessments": bottlenecks,
        "bottleneck_assessments_by_id": {item["assessment_id"]: item for item in bottlenecks},
        "readiness_evaluations": evaluations,
        "readiness_evaluations_by_id": {item["evaluation_id"]: item for item in evaluations},
        "infrastructure_candidates": infrastructure,
        "infrastructure_candidates_by_id": {item["candidate_id"]: item for item in infrastructure},
        "dead_on_arrival_criteria": doa_criteria,
        "dead_on_arrival_criteria_by_id": {item["criterion_id"]: item for item in doa_criteria},
        "open_source_capability_scouts": open_source_scouts,
        "open_source_capability_scouts_by_id": {item["scout_id"]: item for item in open_source_scouts},
        "automation_stage_policy": {
            "manual_fallback_available_when_safe": True,
            "manual_fallback_treated_as_target": False,
            "assisted_path_is_near_term_bridge": True,
            "supervised_path_future_gated": True,
            "autonomous_path_future_gated": True,
            "autonomous_path_candidate_grants_authority": False,
            "dead_on_arrival_stops_build": True,
            "receipt_before_advancement": True,
            "operator_final_authority_required_for_execution": True,
        },
        "relationship_to_prior_lanes": prior_lanes,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "hard_rule": {
            "read_model_only": True,
            "does_not_execute_automation": True,
            "does_not_access_coupa_browser_network_or_accounts": True,
            "does_not_handle_credentials": True,
            "does_not_generate_invoice_or_email": True,
            "does_not_submit_approvals": True,
            "does_not_write_ledger_or_receipts": True,
            "does_not_launch_models_agents_tools_runtime_or_queues": True,
            "does_not_download_install_or_vendor_open_source_code": True,
            "does_not_launder_code_or_evade_licenses": True,
            "current_contract_models_future_candidates_only": True,
            "may_execute_automation_now": False,
            "may_access_external_system_now": False,
            "may_handle_credentials_now": False,
        },
        "machine_proof": {
            "bottleneck_assessment_model_present": True,
            "readiness_evaluation_model_present": True,
            "infrastructure_candidate_model_present": True,
            "dead_on_arrival_criteria_present": True,
            "open_source_capability_scout_model_present": True,
            "bottleneck_assessment_count": len(bottlenecks),
            "readiness_evaluation_count": len(evaluations),
            "infrastructure_candidate_count": len(infrastructure),
            "dead_on_arrival_criteria_count": len(doa_criteria),
            "open_source_capability_scout_count": len(open_source_scouts),
            "open_source_scout_recommendations_supported": True,
            "open_source_scout_grants_dependency_authority": False,
            "open_source_scout_preserves_license_attribution": True,
            "open_source_scout_flags_copyleft": True,
            "default_assessments_present": {
                item["assessment_id"]: True for item in bottlenecks
            },
            "capital_hilton_coupa_po_bottleneck_present": any(
                item["assessment_id"] == "capital_hilton_coupa_po_lookup_bottleneck"
                for item in bottlenecks
            ),
            "telegram_approval_split_brain_bottleneck_present": any(
                item["assessment_id"] == "telegram_approval_split_brain_bottleneck"
                for item in bottlenecks
            ),
            "manual_fallback_is_not_target": True,
            "assisted_supervised_autonomous_paths_future_gated": True,
            "future_automation_candidate_grants_authority": False,
            "all_current_authority_flags_false": _all_authority_flags_false(),
            "credential_handling_allowed": False,
            "network_coupa_browser_authority": False,
            "invoice_email_ledger_approval_authority": False,
            "credentials_or_secrets_included": False,
            "raw_private_bodies_included": False,
            "prior_lane_ref_count": len(prior_lanes),
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_automation_readiness_operator_markdown(payload: dict[str, Any]) -> str:
    proof = payload["machine_proof"]
    coupa = payload["bottleneck_assessments_by_id"]["capital_hilton_coupa_po_lookup_bottleneck"]
    lines = [
        "# Automation Readiness / Feasibility Evaluator Contract v0",
        "",
        "## ELIWINSHIP Summary",
        "",
        "Manual forever is not the goal. Manual is the safe fallback while OpenClaw figures out which parts are actually worth automating and which parts are blocked by security, credentials, terms, proof, or approval risk.",
        "",
        "The point is to find the bottleneck before polishing the path. If the hard part is Coupa/PO lookup, stale approvals, protected evidence, or unsafe repair, OpenClaw should say that plainly instead of making Winship babysit more panels.",
        "",
        "## What The Evaluator Does",
        "",
        "- Names the bottleneck in each workflow.",
        "- Separates low-hanging fruit from high-risk or blocked automation.",
        "- Keeps manual fallback available without treating it as the destination.",
        "- Marks assisted capture as the near-term bridge and governed automation as future-gated.",
        "- Lists the gates, receipts, and infrastructure needed before any live action.",
        "- Scouts existing open-source components before custom builds, while preserving license and attribution boundaries.",
        "",
        "## Capital Hilton Coupa / PO Bottleneck",
        "",
        f"- Current fallback: `{coupa['current_fallback']}`.",
        f"- Near-term path: `{coupa['best_near_term_path']}`.",
        f"- Future path: `{coupa['best_future_path']}`.",
        f"- Feasibility: `{coupa['automation_feasibility']}`.",
        f"- Risk: `{coupa['automation_risk']}`.",
        "- The safe next step is guided manual capture / assisted capture modeling. Coupa, browser, network, credentials, and automation remain blocked now.",
        "",
        "## What Would Make Automation Safe Later",
        "",
        "- Approved site registry.",
        "- Protected credential broker.",
        "- Supervised browser session.",
        "- Protected evidence store.",
        "- Receipt writer.",
        "- Workflow session store and approval bus.",
        "- Guardian/security review and operator final authority.",
        "",
        "## Open Source Capability Scout",
        "",
        "- OpenClaw should first check trusted existing projects, official APIs, libraries, protocols, and adapters.",
        "- Recommendations are explicit: `REUSE`, `WRAP`, `ADAPT`, `MINE_FOR_TESTS`, `BUILD_CUSTOM`, or `AVOID`.",
        "- Copyleft and commercial packaging implications are flagged before use.",
        "- Scout records do not download, install, vendor, import, or execute third-party code.",
        "",
        "## What Remains Blocked",
        "",
        "- No automation execution, browser/Coupa/network access, credential handling, invoice generation, email send, ledger write, approval submission, model/tool/agent/runtime/queue execution, or workflow execution.",
        "",
        "## Why This Makes Life Easier",
        "",
        "Winship should see the few real blockers and the cleanest next safe move. If automation is easy, OpenClaw can propose the next bridge. If it is unsafe or not worth it, OpenClaw should stop early instead of turning one hard step into a complicated cockpit.",
        "",
        "## Machine Proof Summary",
        "",
        f"- Bottleneck assessments: `{proof['bottleneck_assessment_count']}`.",
        f"- Readiness evaluations: `{proof['readiness_evaluation_count']}`.",
        f"- Infrastructure candidates: `{proof['infrastructure_candidate_count']}`.",
        f"- Dead-on-arrival criteria: `{proof['dead_on_arrival_criteria_count']}`.",
        f"- Open-source capability scouts: `{proof['open_source_capability_scout_count']}`.",
        f"- Capital Hilton Coupa/PO bottleneck present: `{str(proof['capital_hilton_coupa_po_bottleneck_present']).lower()}`.",
        f"- All current authority flags false: `{str(proof['all_current_authority_flags_false']).lower()}`.",
        f"- Content hash: `{proof['content_hash']}`.",
    ]
    return "\n".join(lines) + "\n"


def export_automation_readiness_feasibility_evaluator_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> AutomationReadinessExportResult:
    payload = build_automation_readiness_feasibility_evaluator_contract(
        repo_root=repo_root,
        generated_at=generated_at,
    )
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_automation_readiness_operator_markdown(payload), encoding="utf-8")
    return AutomationReadinessExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        bottleneck_assessment_count=len(payload["bottleneck_assessments"]),
        readiness_evaluation_count=len(payload["readiness_evaluations"]),
        infrastructure_candidate_count=len(payload["infrastructure_candidates"]),
        dead_on_arrival_criteria_count=len(payload["dead_on_arrival_criteria"]),
        open_source_scout_count=len(payload["open_source_capability_scouts"]),
        action_authority_granted=False,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Automation Readiness / Feasibility Evaluator Contract."
    )
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_automation_readiness_feasibility_evaluator_contract(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    summary = {
        "schema_version": result.schema_version,
        "json_path": result.json_path,
        "operator_path": result.operator_path,
        "bottleneck_assessment_count": result.bottleneck_assessment_count,
        "readiness_evaluation_count": result.readiness_evaluation_count,
        "infrastructure_candidate_count": result.infrastructure_candidate_count,
        "dead_on_arrival_criteria_count": result.dead_on_arrival_criteria_count,
        "open_source_scout_count": result.open_source_scout_count,
        "action_authority_granted": result.action_authority_granted,
    }
    if args.format in {"summary", "json"}:
        print(stable_json(summary), end="")
    else:
        print("Automation Readiness / Feasibility Evaluator Contract exported")
        print(f"- JSON: `{result.json_path}`")
        print(f"- Operator: `{result.operator_path}`")
    return 0


__all__ = [
    "AUTOMATION_FEASIBILITY",
    "AUTOMATION_RECOMMENDATIONS",
    "AUTOMATION_RISK",
    "AUTHORITY_BOUNDARY",
    "INFRASTRUCTURE_TYPES",
    "JSON_EXPORT_NAME",
    "OPEN_SOURCE_SCOUT_LICENSE_POSTURES",
    "OPEN_SOURCE_SCOUT_RECOMMENDATIONS",
    "OPERATOR_EXPORT_NAME",
    "READ_MODEL_ID",
    "REQUIRED_BOTTLENECK_ASSESSMENT_FIELDS",
    "REQUIRED_DEAD_ON_ARRIVAL_FIELDS",
    "REQUIRED_INFRASTRUCTURE_CANDIDATE_FIELDS",
    "REQUIRED_OPEN_SOURCE_CAPABILITY_SCOUT_FIELDS",
    "REQUIRED_READINESS_EVALUATION_FIELDS",
    "SCHEMA_VERSION",
    "build_automation_readiness_feasibility_evaluator_contract",
    "default_bottleneck_assessments",
    "default_dead_on_arrival_criteria",
    "default_infrastructure_candidates",
    "default_open_source_capability_scouts",
    "default_readiness_evaluations",
    "export_automation_readiness_feasibility_evaluator_contract",
    "format_automation_readiness_operator_markdown",
    "relationship_to_prior_lanes",
    "stable_json",
]

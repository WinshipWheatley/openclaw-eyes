"""Winship Incorruptible Core Contract v0.

This deterministic read-model defines the Winship-level protective-force and
anti-Skynet boundary. It is doctrine/contract only: no live enforcement, active
defense, offensive tooling, targeting, surveillance, exploit generation,
weaponization, autonomous action, legal approval, network access, or runtime
execution occurs here.
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

SCHEMA_VERSION = "winship_incorruptible_core_contract_v0"
READ_MODEL_ID = "winship_incorruptible_core_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_WINSHIP_INCORRUPTIBLE_CORE_CONTRACT"

ALLOWED_FORCE_MODES = (
    "DEFEND",
    "HARDEN",
    "WARN",
    "DOCUMENT",
    "PRESERVE_EVIDENCE",
    "COORDINATE_HELP",
    "RECOVER",
    "DE_ESCALATE",
    "CONTAIN_HARM",
    "ROUTE_AROUND_HARM",
    "LAWFUL_ACCOUNTABILITY",
    "PROTECT_CIVILIANS",
    "PROTECT_INFRASTRUCTURE",
)

FORBIDDEN_FORCE_MODES = (
    "OFFENSIVE_TARGETING",
    "WEAPON_OPTIMIZATION",
    "AUTONOMOUS_HARM",
    "CIVILIAN_SURVEILLANCE",
    "DISSIDENT_SURVEILLANCE",
    "POPULATION_MANIPULATION",
    "CYBER_OFFENSE_AGAINST_CIVILIAN_SYSTEMS",
    "COERCIVE_CONTROL",
    "TARGETING_PROTECTED_GROUPS",
    "BYPASSING_HUMAN_OR_LEGAL_APPROVAL",
    "DISGUISING_AGGRESSION_AS_DEFENSE",
    "RETALIATION",
    "DOXXING",
    "HARASSMENT",
    "EXPLOIT_GENERATION",
    "PRIVACY_VIOLATION",
    "UNKNOWN_FAIL_CLOSED",
)

DEFENSIVE_CLASSIFICATION_RESULTS = (
    "ALLOWED_PROTECTIVE",
    "ALLOWED_WITH_REVIEW",
    "NARROW_OUTPUT_ONLY",
    "NEEDS_GUARDIAN_REVIEW",
    "NEEDS_LEGAL_REVIEW",
    "BLOCKED_AGGRESSION",
    "BLOCKED_SURVEILLANCE_ABUSE",
    "BLOCKED_AUTONOMOUS_HARM",
    "BLOCKED_PRIVACY_VIOLATION",
    "UNKNOWN_FAIL_CLOSED",
)

GATE_DECISIONS = (
    "ALLOW_CONSTRUCTIVE",
    "ALLOW_PROTECTIVE",
    "ALLOW_WITH_REVIEW",
    "NARROW_TO_SAFE_OUTPUT",
    "BLOCK_AND_EXPLAIN",
    "REFUSE_HARMFUL",
    "UNKNOWN_FAIL_CLOSED",
)

CORE_BLOCKER_TYPES = (
    "AGGRESSION_ENGINE_RISK",
    "DEFENSE_CLAIM_MASKS_OFFENSE",
    "AUTONOMOUS_HARM_RISK",
    "SURVEILLANCE_ABUSE_RISK",
    "CIVILIAN_TARGETING_RISK",
    "WEAPONIZATION_RISK",
    "COERCIVE_CONTROL_RISK",
    "PRIVACY_VIOLATION_RISK",
    "HUMAN_LEGAL_REVIEW_BYPASS",
    "CAPTAIN_OVERRIDE_OF_CORE_BOUNDARY",
    "GOVERNMENT_OVERRIDE_OF_CORE_BOUNDARY",
    "FOUNDER_OVERRIDE_OF_CORE_BOUNDARY",
    "SHIPYARD_CORRUPTION_RISK",
    "UNKNOWN_FAIL_CLOSED",
)

LIVE_ENFORCEMENT_AUTHORITY = {
    "live_incorruptible_core_enforcement_allowed": False,
    "live_protective_force_classification_allowed": False,
    "live_public_sector_use_approval_allowed": False,
    "live_military_adjacent_use_approval_allowed": False,
    "live_defensive_action_allowed": False,
    "live_offensive_action_allowed": False,
    "live_surveillance_allowed": False,
    "live_targeting_allowed": False,
    "live_weaponization_allowed": False,
    "live_autonomous_harm_allowed": False,
    "live_network_allowed": False,
    "live_agent_dispatch_allowed": False,
    "live_tool_execution_allowed": False,
    "live_runtime_dispatch_allowed": False,
    "credential_handling_allowed": False,
    "raw_body_ingestion_allowed": False,
    "model_call_allowed": False,
    "agent_activation_allowed": False,
    "tool_execution_allowed": False,
    "queue_execution_allowed": False,
    "runtime_dispatch_allowed": False,
    "browser_automation_allowed": False,
    "coupa_access_allowed": False,
    "gmail_access_allowed": False,
    "telegram_send_allowed": False,
    "email_send_allowed": False,
    "approval_submission_allowed": False,
    "mission_control_swift_change_allowed": False,
    "mac_sync_import_allowed": False,
    "git_push_pull_fetch_allowed": False,
    "offensive_cyber_tooling_allowed": False,
    "active_defense_tooling_allowed": False,
    "policy_engine_live_authority_allowed": False,
}

REQUIRED_CORE_CONTRACT_FIELDS = (
    "contract_id",
    "doctrine_name",
    "doctrine_summary",
    "winship_definition",
    "incorruptible_core_definition",
    "protective_force_boundary",
    "anti_skynet_boundary",
    "defensive_use_policy",
    "prohibited_aggression_policy",
    "public_sector_use_policy",
    "military_adjacent_use_policy",
    "shipyard_anti_capture_alignment",
    "operator_sovereignty_policy",
    "privacy_policy",
    "legal_review_required",
    "live_enforcement_authority",
    "current_contract_status",
    "next_safe_move",
)

REQUIRED_PROTECTIVE_FORCE_FIELDS = (
    "boundary_id",
    "allowed_force_modes",
    "forbidden_force_modes",
    "protected_subjects",
    "harm_reduction_requirements",
    "accountability_requirements",
    "human_legal_review_requirements",
    "ambiguity_policy",
    "fail_closed_policy",
    "next_safe_move",
)

REQUIRED_ANTI_SKYNET_FIELDS = (
    "boundary_id",
    "doctrine",
    "skynet_like_risk_patterns",
    "allowed_response_postures",
    "blocked_response_postures",
    "escalation_review_required",
    "human_agency_preservation",
    "autonomous_harm_forbidden",
    "surveillance_abuse_forbidden",
    "manipulation_forbidden",
    "elioperator_summary",
    "next_safe_move",
)

REQUIRED_CLASSIFICATION_FIELDS = (
    "classification_id",
    "mission_ref",
    "mission_claim",
    "protected_subject",
    "harm_reduction_claim",
    "civilian_risk",
    "privacy_risk",
    "escalation_risk",
    "authority_basis",
    "accountability_path",
    "human_review_required",
    "legal_review_required",
    "allowed_outputs",
    "blocked_outputs",
    "classification_result",
    "elioperator_explanation",
    "next_safe_move",
)

REQUIRED_PUBLIC_SECTOR_POLICY_FIELDS = (
    "policy_id",
    "allowed_public_sector_uses",
    "allowed_military_adjacent_uses",
    "prohibited_uses",
    "review_requirements",
    "protected_infrastructure_scope",
    "civilian_protection_scope",
    "chain_of_custody_scope",
    "humanitarian_scope",
    "emergency_response_scope",
    "refusal_boundary",
    "next_safe_move",
)

REQUIRED_OUTPUT_GATE_FIELDS = (
    "gate_id",
    "output_ref",
    "intended_use",
    "potential_harm",
    "protective_value",
    "operator_benefit",
    "public_or_civilian_risk",
    "privacy_risk",
    "allowed_output_shape",
    "blocked_output_shape",
    "required_review",
    "decision",
    "elioperator_warning",
    "next_safe_move",
)

REQUIRED_TRADEOFF_FIELDS = (
    "tradeoff_id",
    "tradeoff_summary",
    "offensive_power_reduced",
    "protective_power_preserved",
    "reason",
    "examples",
    "operator_explanation",
    "next_safe_move",
)

REQUIRED_NON_BYPASSABLE_FIELDS = (
    "boundary_id",
    "ship_level_rule",
    "non_bypassable_requirements",
    "captain_override_limits",
    "client_override_limits",
    "government_override_limits",
    "founder_override_limits",
    "guardian_review_required",
    "fail_closed_cases",
    "next_safe_move",
)

REQUIRED_ANTI_CAPTURE_ALIGNMENT_FIELDS = (
    "alignment_id",
    "ship_core_boundary",
    "shipyard_covenant_ref",
    "corruption_scenario",
    "clean_shipyard_recovery_concept",
    "butterfly_laws_dependency",
    "fleet_established_required",
    "trust_migration_concept",
    "private_data_protection",
    "live_trigger_authority",
    "next_safe_move",
)

REQUIRED_BUILDER_BLOCKER_FIELDS = (
    "blocker_id",
    "blocker_type",
    "condition",
    "severity",
    "elioperator_warning",
    "builder_action_required",
    "fail_closed",
    "next_safe_move",
)

REQUIRED_ELIOPERATOR_REPORT_FIELDS = (
    "report_id",
    "plain_summary",
    "what_this_preserves",
    "what_this_blocks",
    "what_this_allows",
    "why_offensive_power_is_limited",
    "how_protective_use_still_works",
    "why_military_or_government_use_requires_review",
    "how_this_aligns_with_shipyard_covenant",
    "next_safe_move",
)

RELATIONSHIP_REF_PATHS = {
    "shipyard_sovereignty_covenant_contract": "generated/read_models/shipyard_sovereignty_covenant_contract.json",
    "meaningful_work_gravity_contract": "generated/read_models/meaningful_work_gravity_contract.json",
    "cross_surface_artifact_handoff_registry_contract": (
        "generated/read_models/cross_surface_artifact_handoff_registry_contract.json"
    ),
    "cross_lane_reusable_block_registry_contract": (
        "generated/read_models/cross_lane_reusable_block_registry_contract.json"
    ),
    "openclaw_sensitive_policy": "openclaw_sensitive_policy.py",
    "guardian_protected_access_gate_spec": "generated/read_models/guardian_protected_access_gate_spec.json",
    "guided_capture_protected_evidence_path_contract": (
        "generated/read_models/guided_capture_protected_evidence_path_contract.json"
    ),
    "protected_evidence_reference_receipt": "generated/read_models/protected_evidence_reference_receipt.json",
    "bridge_routing_operator_attention_contract": (
        "generated/read_models/bridge_routing_operator_attention_contract.json"
    ),
    "agent_execution_packet_compiler_contract": (
        "generated/read_models/agent_execution_packet_compiler_contract.json"
    ),
    "agent_conversation_handoff_step_packet_contract": (
        "generated/read_models/agent_conversation_handoff_step_packet_contract.json"
    ),
}


@dataclass(frozen=True)
class WinshipIncorruptibleCoreContract:
    contract_id: str
    doctrine_name: str
    doctrine_summary: str
    winship_definition: str
    incorruptible_core_definition: str
    protective_force_boundary: str
    anti_skynet_boundary: str
    defensive_use_policy: str
    prohibited_aggression_policy: str
    public_sector_use_policy: str
    military_adjacent_use_policy: str
    shipyard_anti_capture_alignment: str
    operator_sovereignty_policy: str
    privacy_policy: str
    legal_review_required: bool
    live_enforcement_authority: dict[str, bool]
    current_contract_status: str
    next_safe_move: str


@dataclass(frozen=True)
class ProtectiveForceBoundary:
    boundary_id: str
    allowed_force_modes: tuple[str, ...]
    forbidden_force_modes: tuple[str, ...]
    protected_subjects: tuple[str, ...]
    harm_reduction_requirements: tuple[str, ...]
    accountability_requirements: tuple[str, ...]
    human_legal_review_requirements: tuple[str, ...]
    ambiguity_policy: str
    fail_closed_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class AntiSkynetBoundary:
    boundary_id: str
    doctrine: str
    skynet_like_risk_patterns: tuple[str, ...]
    allowed_response_postures: tuple[str, ...]
    blocked_response_postures: tuple[str, ...]
    escalation_review_required: bool
    human_agency_preservation: str
    autonomous_harm_forbidden: bool
    surveillance_abuse_forbidden: bool
    manipulation_forbidden: bool
    elioperator_summary: str
    next_safe_move: str


@dataclass(frozen=True)
class DefensiveUseClassification:
    classification_id: str
    mission_ref: str
    mission_claim: str
    protected_subject: str
    harm_reduction_claim: str
    civilian_risk: str
    privacy_risk: str
    escalation_risk: str
    authority_basis: str
    accountability_path: str
    human_review_required: bool
    legal_review_required: bool
    allowed_outputs: tuple[str, ...]
    blocked_outputs: tuple[str, ...]
    classification_result: str
    elioperator_explanation: str
    next_safe_move: str


@dataclass(frozen=True)
class PublicSectorMilitaryAdjacentPolicy:
    policy_id: str
    allowed_public_sector_uses: tuple[str, ...]
    allowed_military_adjacent_uses: tuple[str, ...]
    prohibited_uses: tuple[str, ...]
    review_requirements: tuple[str, ...]
    protected_infrastructure_scope: tuple[str, ...]
    civilian_protection_scope: tuple[str, ...]
    chain_of_custody_scope: str
    humanitarian_scope: tuple[str, ...]
    emergency_response_scope: tuple[str, ...]
    refusal_boundary: str
    next_safe_move: str


@dataclass(frozen=True)
class BeneficialOutputGate:
    gate_id: str
    output_ref: str
    intended_use: str
    potential_harm: str
    protective_value: str
    operator_benefit: str
    public_or_civilian_risk: str
    privacy_risk: str
    allowed_output_shape: str
    blocked_output_shape: str
    required_review: tuple[str, ...]
    decision: str
    elioperator_warning: str
    next_safe_move: str


@dataclass(frozen=True)
class IncorruptibleCoreTradeoff:
    tradeoff_id: str
    tradeoff_summary: str
    offensive_power_reduced: bool
    protective_power_preserved: bool
    reason: str
    examples: tuple[str, ...]
    operator_explanation: str
    next_safe_move: str


@dataclass(frozen=True)
class ShipLevelNonBypassableBoundary:
    boundary_id: str
    ship_level_rule: str
    non_bypassable_requirements: tuple[str, ...]
    captain_override_limits: str
    client_override_limits: str
    government_override_limits: str
    founder_override_limits: str
    guardian_review_required: bool
    fail_closed_cases: tuple[str, ...]
    next_safe_move: str


@dataclass(frozen=True)
class ShipyardAntiCaptureTrapAlignment:
    alignment_id: str
    ship_core_boundary: str
    shipyard_covenant_ref: str
    corruption_scenario: str
    clean_shipyard_recovery_concept: str
    butterfly_laws_dependency: str
    fleet_established_required: bool
    trust_migration_concept: str
    private_data_protection: str
    live_trigger_authority: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class WinshipIncorruptibleCoreBuilderBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    builder_action_required: str
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class WinshipIncorruptibleCoreElioperatorReport:
    report_id: str
    plain_summary: str
    what_this_preserves: tuple[str, ...]
    what_this_blocks: tuple[str, ...]
    what_this_allows: tuple[str, ...]
    why_offensive_power_is_limited: str
    how_protective_use_still_works: str
    why_military_or_government_use_requires_review: str
    how_this_aligns_with_shipyard_covenant: str
    next_safe_move: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _sha256(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return _sha256(clone)


def _relationship_inventory() -> dict[str, dict[str, Any]]:
    return {
        name: {
            "ref": name,
            "path": path,
            "present": (ROOT / path).exists(),
            "used_as": "relationship_reference_only_no_content_duplication",
        }
        for name, path in RELATIONSHIP_REF_PATHS.items()
    }


def _core_contract() -> WinshipIncorruptibleCoreContract:
    return WinshipIncorruptibleCoreContract(
        contract_id="winship_incorruptible_core_contract_v0",
        doctrine_name="Winship Incorruptible Core v0",
        doctrine_summary=(
            "A Winship may help people resist harmful systems, but it must not become a harmful system to do so."
        ),
        winship_definition=(
            "A Winship is a captain-specific local-first vessel for meaningful work, privacy, dignity, and agency."
        ),
        incorruptible_core_definition=(
            "The ship-level non-bypassable boundary that refuses aggression, surveillance abuse, coercion, weaponization, "
            "privacy violation, and autonomous harm even when requested by a powerful actor."
        ),
        protective_force_boundary=(
            "Forceful outputs may only constrain harmful systems or predatory processes through containment, evidence, "
            "warning, hardening, recovery, de-escalation, lawful accountability, and protection."
        ),
        anti_skynet_boundary=(
            "A Winship may help defend people from coercive autonomous or dehumanizing systems; it must not become one."
        ),
        defensive_use_policy=(
            "Defense, resilience, accountability, and protection are allowed only through narrow, reviewed, human-accountable outputs."
        ),
        prohibited_aggression_policy=(
            "Autonomous harm, targeting, surveillance abuse, manipulation, exploitation, weaponization, retaliation, and hidden escalation are blocked."
        ),
        public_sector_use_policy=(
            "Public-sector use may support protection of life, dignity, privacy, lawful sovereignty, infrastructure, and civil resilience."
        ),
        military_adjacent_use_policy=(
            "Military-adjacent or force-adjacent work requires legal/human review and must narrow to civilian protection, resilience, recovery, evidence, or lawful accountability."
        ),
        shipyard_anti_capture_alignment=(
            "If a captured Shipyard tries to produce corrupted ships, this core aligns with the Shipyard covenant and future clean-state recovery concept."
        ),
        operator_sovereignty_policy="Captains retain agency, but cannot override core boundaries for harmful misuse.",
        privacy_policy="Private data, protected evidence, secrets, credentials, and raw bodies stay out of normal read-models.",
        legal_review_required=True,
        live_enforcement_authority=LIVE_ENFORCEMENT_AUTHORITY,
        current_contract_status="DOCTRINE_READ_MODEL_ONLY_NO_LIVE_ENFORCEMENT",
        next_safe_move="Review as ship-safety doctrine; do not build active defense, offense, targeting, or surveillance tooling.",
    )


def _protective_force_boundary() -> ProtectiveForceBoundary:
    return ProtectiveForceBoundary(
        boundary_id="protective_force_boundary_v0",
        allowed_force_modes=ALLOWED_FORCE_MODES,
        forbidden_force_modes=FORBIDDEN_FORCE_MODES,
        protected_subjects=(
            "people",
            "families",
            "civilian communities",
            "hospitals",
            "schools",
            "public infrastructure",
            "water systems",
            "energy grids",
            "communications",
            "emergency services",
            "lawful civil institutions",
        ),
        harm_reduction_requirements=(
            "clear protective purpose",
            "narrow output shape",
            "civilian/privacy risk review",
            "no autonomous harm",
            "no coercive control",
            "no hidden escalation",
        ),
        accountability_requirements=(
            "human accountable owner",
            "evidence or audit posture where relevant",
            "chain-of-custody posture for evidence work",
            "explicit authority basis",
            "safe readback and refusal when blocked",
        ),
        human_legal_review_requirements=(
            "public-sector use review",
            "military-adjacent use review",
            "force-adjacent use review",
            "protected evidence Guardian review",
            "privacy/legal review for ambiguous cases",
        ),
        ambiguity_policy="If defense could enable aggression, narrow to safe output or fail closed into Guardian/legal review.",
        fail_closed_policy="Unknown, coercive, targeting, surveillance, weaponization, or autonomous-harm posture fails closed.",
        next_safe_move="Use for classification/readback only; no live defensive action is authorized.",
    )


def _anti_skynet_boundary() -> AntiSkynetBoundary:
    return AntiSkynetBoundary(
        boundary_id="anti_skynet_boundary_v0",
        doctrine=(
            "A Winship may help defend humans, communities, institutions, and infrastructure from coercive, exploitative, "
            "autonomous, or dehumanizing systems. A Winship must not become a coercive, exploitative, autonomous, "
            "or dehumanizing system itself."
        ),
        skynet_like_risk_patterns=(
            "autonomous decisions that harm people without accountable review",
            "systems that profit from harm while evading accountability",
            "coercive systems that remove agency",
            "surveillance systems that treat people as targets",
            "manipulation systems that distort consent or public truth",
            "infrastructure control systems with hidden escalation paths",
        ),
        allowed_response_postures=(
            "document",
            "warn",
            "harden",
            "route around",
            "preserve evidence",
            "coordinate help",
            "recover",
            "de-escalate",
            "lawful accountability",
        ),
        blocked_response_postures=(
            "autonomous retaliation",
            "exploit generation",
            "target selection",
            "weapon optimization",
            "civilian monitoring",
            "dissident monitoring",
            "population manipulation",
            "privacy violation",
            "hidden escalation",
        ),
        escalation_review_required=True,
        human_agency_preservation="A protective Winship must preserve human agency and accountable human/legal review.",
        autonomous_harm_forbidden=True,
        surveillance_abuse_forbidden=True,
        manipulation_forbidden=True,
        elioperator_summary=(
            "ELIOPERATOR: A Winship can help fight coercive systems without becoming coercive itself."
        ),
        next_safe_move="Keep anti-Skynet posture as doctrine; classify only, execute nothing.",
    )


def _public_sector_policy() -> PublicSectorMilitaryAdjacentPolicy:
    return PublicSectorMilitaryAdjacentPolicy(
        policy_id="public_sector_military_adjacent_policy_v0",
        allowed_public_sector_uses=(
            "protecting hospitals, schools, grids, water systems, communications, emergency services, and public infrastructure",
            "detecting intrusion, fraud, sabotage, corruption, or abuse",
            "hardening systems against attack",
            "coordinating disaster or humanitarian response",
            "preserving evidence and chain of custody",
            "reducing civilian harm",
            "supporting infrastructure repair",
        ),
        allowed_military_adjacent_uses=(
            "civilian harm reduction",
            "rescue, evacuation, medical support, and infrastructure repair logistics",
            "hardening protected infrastructure",
            "preserving evidence for lawful accountability",
            "helping lawful society resist coercion without targeting civilians",
        ),
        prohibited_uses=(
            "offensive targeting",
            "weapon optimization",
            "autonomous harm",
            "civilian surveillance or repression",
            "disinformation or population manipulation",
            "cyber offense against civilian systems",
            "coercive control",
            "targeting protected groups",
            "bypassing human or legal approval",
            "hiding aggression behind defense language",
        ),
        review_requirements=(
            "human accountable owner",
            "legal review for public-sector or force-adjacent deployment",
            "Guardian review for protected evidence",
            "privacy and civilian-risk review",
            "narrow output shape",
        ),
        protected_infrastructure_scope=(
            "hospitals",
            "schools",
            "power grids",
            "water systems",
            "communications",
            "emergency services",
            "public infrastructure",
        ),
        civilian_protection_scope=("life", "dignity", "privacy", "lawful sovereignty", "civil resilience"),
        chain_of_custody_scope="Preserve evidence metadata and accountability posture without exposing raw protected bodies.",
        humanitarian_scope=("rescue", "medical support", "evacuation", "infrastructure repair", "disaster response"),
        emergency_response_scope=("coordination", "readiness", "recovery", "public infrastructure continuity"),
        refusal_boundary="Requests for aggression, surveillance abuse, coercion, weaponization, or hidden escalation are refused.",
        next_safe_move="Use as review posture only; no approval is granted here.",
    )


def _classifications() -> tuple[DefensiveUseClassification, ...]:
    return (
        DefensiveUseClassification(
            classification_id="classification_public_infrastructure_defense",
            mission_ref="example_public_infrastructure_defense",
            mission_claim="Harden hospital, grid, or water-system operations against disruption.",
            protected_subject="public infrastructure and civilians",
            harm_reduction_claim="Reduce harm by hardening and recovery planning.",
            civilian_risk="low if limited to defensive posture and no targeting",
            privacy_risk="medium; protected operational details require review",
            escalation_risk="low when no offensive action is included",
            authority_basis="human accountable public-interest review required",
            accountability_path="legal review plus Guardian/protected-evidence review when sensitive evidence appears",
            human_review_required=True,
            legal_review_required=True,
            allowed_outputs=("hardening checklist", "risk register", "recovery plan", "evidence-preservation plan"),
            blocked_outputs=("targeting guidance", "attack instructions", "exploit details", "retaliation plan"),
            classification_result="ALLOWED_WITH_REVIEW",
            elioperator_explanation="Protective infrastructure work can proceed only as narrow hardening/recovery output with review.",
            next_safe_move="Prepare safe review packet, not live action.",
        ),
        DefensiveUseClassification(
            classification_id="classification_humanitarian_logistics",
            mission_ref="example_humanitarian_logistics",
            mission_claim="Coordinate rescue, medical support, or infrastructure repair.",
            protected_subject="civilians and emergency responders",
            harm_reduction_claim="Reduce harm by routing help and restoring essential services.",
            civilian_risk="low if privacy and consent boundaries hold",
            privacy_risk="medium where personal or protected data appears",
            escalation_risk="low",
            authority_basis="humanitarian coordination with accountable human owner",
            accountability_path="operator review and privacy minimization",
            human_review_required=True,
            legal_review_required=False,
            allowed_outputs=("coordination checklist", "resource map", "privacy-minimized status summary"),
            blocked_outputs=("coercive movement control", "civilian monitoring", "protected data exposure"),
            classification_result="ALLOWED_PROTECTIVE",
            elioperator_explanation="Humanitarian logistics is protective when privacy and consent boundaries hold.",
            next_safe_move="Keep output logistical and privacy-minimized.",
        ),
        DefensiveUseClassification(
            classification_id="classification_evidence_preservation",
            mission_ref="example_evidence_preservation",
            mission_claim="Preserve chain of custody around corruption, sabotage, or fraud.",
            protected_subject="lawful accountability and affected people",
            harm_reduction_claim="Preserve evidence without exposing protected content.",
            civilian_risk="low",
            privacy_risk="high if raw evidence is exposed",
            escalation_risk="medium if evidence is used outside accountable process",
            authority_basis="accountability posture with legal/protected review as needed",
            accountability_path="chain-of-custody metadata, Guardian posture, and legal review when applicable",
            human_review_required=True,
            legal_review_required=True,
            allowed_outputs=("metadata-only evidence index", "chain-of-custody checklist", "review packet"),
            blocked_outputs=("raw protected body exposure", "public accusation without review", "credential handling"),
            classification_result="ALLOWED_WITH_REVIEW",
            elioperator_explanation="Evidence preservation is allowed as metadata and accountability posture, not raw exposure.",
            next_safe_move="Capture protected references only; do not ingest raw bodies.",
        ),
        DefensiveUseClassification(
            classification_id="classification_blocked_offensive_targeting",
            mission_ref="example_blocked_offensive_targeting",
            mission_claim="Select targets or improve forceful harm delivery.",
            protected_subject="none",
            harm_reduction_claim="not established",
            civilian_risk="critical",
            privacy_risk="high",
            escalation_risk="critical",
            authority_basis="none accepted",
            accountability_path="refusal",
            human_review_required=True,
            legal_review_required=True,
            allowed_outputs=("refusal explanation", "safe redirection to protective/humanitarian framing"),
            blocked_outputs=("target selection", "weapon optimization", "harmful operational guidance"),
            classification_result="BLOCKED_AGGRESSION",
            elioperator_explanation="A defense claim cannot mask aggression.",
            next_safe_move="Refuse harmful output and offer safe protective alternatives only.",
        ),
        DefensiveUseClassification(
            classification_id="classification_blocked_civilian_surveillance",
            mission_ref="example_blocked_civilian_surveillance",
            mission_claim="Monitor civilians, dissidents, or protected groups.",
            protected_subject="civilians and protected groups",
            harm_reduction_claim="not established",
            civilian_risk="critical",
            privacy_risk="critical",
            escalation_risk="high",
            authority_basis="none accepted",
            accountability_path="refusal",
            human_review_required=True,
            legal_review_required=True,
            allowed_outputs=("refusal explanation", "privacy-preserving accountability alternative"),
            blocked_outputs=("surveillance plan", "identity tracking", "repression support", "privacy violation"),
            classification_result="BLOCKED_SURVEILLANCE_ABUSE",
            elioperator_explanation="Civilian or dissident monitoring is blocked as surveillance abuse.",
            next_safe_move="Refuse and redirect to lawful accountability or harm-reduction posture.",
        ),
        DefensiveUseClassification(
            classification_id="classification_defensive_ambiguity",
            mission_ref="example_defensive_ambiguity",
            mission_claim="Claimed defense with unclear authority and possible aggression enablement.",
            protected_subject="unclear",
            harm_reduction_claim="ambiguous",
            civilian_risk="unknown",
            privacy_risk="unknown",
            escalation_risk="high",
            authority_basis="insufficient",
            accountability_path="Guardian/legal review or narrow safe output",
            human_review_required=True,
            legal_review_required=True,
            allowed_outputs=("clarifying questions", "risk taxonomy", "safe hardening-only summary"),
            blocked_outputs=("operational harm steps", "targeting", "surveillance", "exploit detail"),
            classification_result="NARROW_OUTPUT_ONLY",
            elioperator_explanation="Ambiguous force-adjacent work narrows to safe framing or review.",
            next_safe_move="Ask for accountability basis and keep output non-operational.",
        ),
        DefensiveUseClassification(
            classification_id="classification_anti_skynet_pattern",
            mission_ref="example_anti_skynet",
            mission_claim="Identify coercive autonomous harm pattern and reduce harm.",
            protected_subject="humans, communities, institutions, and infrastructure",
            harm_reduction_claim="Document, warn, harden, and route around coercive systems.",
            civilian_risk="medium if escalation or exposure occurs",
            privacy_risk="medium; use metadata and safe labels",
            escalation_risk="medium",
            authority_basis="protective analysis with human review",
            accountability_path="evidence, warning, hardening, and de-escalation posture",
            human_review_required=True,
            legal_review_required=False,
            allowed_outputs=("pattern description", "warning language", "hardening guidance", "safe routing plan"),
            blocked_outputs=("autonomous retaliation", "exploit generation", "coercive counter-control"),
            classification_result="ALLOWED_PROTECTIVE",
            elioperator_explanation="Anti-Skynet work is allowed when it documents, warns, hardens, and de-escalates.",
            next_safe_move="Keep the response protective and accountable.",
        ),
        DefensiveUseClassification(
            classification_id="classification_founder_government_override",
            mission_ref="example_founder_government_override",
            mission_claim="Powerful actor asks to bypass core boundary.",
            protected_subject="captains, civilians, and protected groups",
            harm_reduction_claim="not established",
            civilian_risk="high",
            privacy_risk="high",
            escalation_risk="high",
            authority_basis="core boundary cannot be overridden by status",
            accountability_path="refusal or formal review depending request shape",
            human_review_required=True,
            legal_review_required=True,
            allowed_outputs=("boundary explanation", "review packet", "safe narrowed alternative"),
            blocked_outputs=("core-boundary bypass", "harmful compliance", "hidden escalation"),
            classification_result="NEEDS_LEGAL_REVIEW",
            elioperator_explanation="Founder, captain, client, or government status does not bypass the core.",
            next_safe_move="Fail closed or route to review; do not execute.",
        ),
    )


def _output_gates() -> tuple[BeneficialOutputGate, ...]:
    return (
        BeneficialOutputGate(
            gate_id="gate_public_infrastructure_defense",
            output_ref="classification_public_infrastructure_defense",
            intended_use="protect infrastructure through hardening and recovery",
            potential_harm="dual-use ambiguity if operationalized beyond defense",
            protective_value="high",
            operator_benefit="supports civil resilience",
            public_or_civilian_risk="medium",
            privacy_risk="medium",
            allowed_output_shape="defensive checklist, review packet, recovery plan, metadata-only evidence posture",
            blocked_output_shape="targeting, exploit detail, weapon optimization, retaliation, or hidden escalation",
            required_review=("human review", "legal review", "Guardian review if protected evidence appears"),
            decision="ALLOW_WITH_REVIEW",
            elioperator_warning="ELIOPERATOR: Keep this as hardening/recovery. Do not turn it into offense.",
            next_safe_move="Prepare review packet; do not perform live action.",
        ),
        BeneficialOutputGate(
            gate_id="gate_blocked_targeting",
            output_ref="classification_blocked_offensive_targeting",
            intended_use="target selection or harm optimization",
            potential_harm="direct aggression",
            protective_value="none accepted",
            operator_benefit="none accepted",
            public_or_civilian_risk="critical",
            privacy_risk="high",
            allowed_output_shape="refusal and safe protective redirection",
            blocked_output_shape="targeting logic, weapon optimization, or operational harm guidance",
            required_review=("refusal boundary",),
            decision="REFUSE_HARMFUL",
            elioperator_warning="ELIOPERATOR: This asks the ship to become an aggression engine. Refuse.",
            next_safe_move="Offer protective alternatives only.",
        ),
        BeneficialOutputGate(
            gate_id="gate_defensive_ambiguity",
            output_ref="classification_defensive_ambiguity",
            intended_use="unclear force-adjacent defense claim",
            potential_harm="could enable aggression or surveillance",
            protective_value="unknown until clarified",
            operator_benefit="possible if narrowed to hardening",
            public_or_civilian_risk="unknown",
            privacy_risk="unknown",
            allowed_output_shape="clarifying questions, risk taxonomy, hardening-only summary",
            blocked_output_shape="operational harm, target selection, exploit detail, or monitoring plan",
            required_review=("Guardian review", "legal review"),
            decision="NARROW_TO_SAFE_OUTPUT",
            elioperator_warning="ELIOPERATOR: The defense claim is ambiguous. Narrow to safe output or review.",
            next_safe_move="Ask for authority/accountability basis and keep output non-operational.",
        ),
    )


def _public_sector_and_tradeoff() -> tuple[PublicSectorMilitaryAdjacentPolicy, IncorruptibleCoreTradeoff]:
    tradeoff = IncorruptibleCoreTradeoff(
        tradeoff_id="incorruptible_core_tradeoff_v0",
        tradeoff_summary="The core intentionally reduces offensive power to preserve protective power.",
        offensive_power_reduced=True,
        protective_power_preserved=True,
        reason=(
            "Reducing offensive power is intentional. It protects the Winship from becoming the threat it was built to resist."
        ),
        examples=(
            "hardening allowed while exploit generation is blocked",
            "evidence preservation allowed while doxxing is blocked",
            "de-escalation allowed while retaliation is blocked",
            "infrastructure protection allowed while civilian targeting is blocked",
        ),
        operator_explanation=(
            "ELIOPERATOR: The ship may be less dangerous by design. That is what lets it stay trustworthy when powerful."
        ),
        next_safe_move="Treat reduced aggression capability as a feature, not a defect.",
    )
    return _public_sector_policy(), tradeoff


def _non_bypassable_boundary() -> ShipLevelNonBypassableBoundary:
    return ShipLevelNonBypassableBoundary(
        boundary_id="ship_level_non_bypassable_boundary_v0",
        ship_level_rule="No captain, client, government, founder, or Shipyard path can bypass the core for harmful misuse.",
        non_bypassable_requirements=(
            "block aggression",
            "block surveillance abuse",
            "block civilian targeting",
            "block autonomous harm",
            "block weaponization",
            "block coercive control",
            "block privacy violation",
            "require Guardian/legal review for ambiguous force-adjacent cases",
        ),
        captain_override_limits="Captain authority does not permit offensive/aggressive misuse.",
        client_override_limits="Client authority does not permit privacy abuse, coercion, or harmful force.",
        government_override_limits="Government or public-sector status requires review; it is not a bypass.",
        founder_override_limits="Founder authority cannot override the incorruptible core.",
        guardian_review_required=True,
        fail_closed_cases=(
            "unknown authority basis",
            "ambiguous force-adjacent mission",
            "targeting or surveillance request",
            "weaponization or autonomous harm request",
            "protected evidence without Guardian posture",
        ),
        next_safe_move="Use as doctrine/readback only; no runtime enforcement is created.",
    )


def _anti_capture_alignment() -> ShipyardAntiCaptureTrapAlignment:
    return ShipyardAntiCaptureTrapAlignment(
        alignment_id="shipyard_anti_capture_trap_alignment_v0",
        ship_core_boundary="Winship incorruptible core blocks corrupted ships from becoming aggression engines.",
        shipyard_covenant_ref="shipyard_sovereignty_covenant_contract_v0",
        corruption_scenario="Captured Shipyard attempts to produce ships that weaken privacy, safety, sovereignty, or aggression boundaries.",
        clean_shipyard_recovery_concept=(
            "After Fleet establishment and lawfully armed butterfly laws, future review may route trust to the last verified clean Shipyard root."
        ),
        butterfly_laws_dependency="Requires Fleet-established phase, legal/governance review, explicit arming, and last-clean-state proof.",
        fleet_established_required=True,
        trust_migration_concept="Trust migrates conceptually toward uncompromised Shipyards; no attack or retaliation.",
        private_data_protection="Private captain/client data, secrets, credentials, and protected evidence are excluded.",
        live_trigger_authority=LIVE_ENFORCEMENT_AUTHORITY,
        next_safe_move="Reference Shipyard covenant; do not arm or trigger recovery here.",
    )


def _builder_blockers() -> tuple[WinshipIncorruptibleCoreBuilderBlocker, ...]:
    def blocker(blocker_id: str, blocker_type: str, condition: str, warning: str) -> WinshipIncorruptibleCoreBuilderBlocker:
        return WinshipIncorruptibleCoreBuilderBlocker(
            blocker_id=blocker_id,
            blocker_type=blocker_type,
            condition=condition,
            severity="BLOCKS_SAFE_MIGRATION",
            elioperator_warning=f"ELIOPERATOR: {warning}",
            builder_action_required="Fail closed, narrow to safe output, or route to Guardian/legal review; do not execute.",
            fail_closed=True,
            next_safe_move="Keep this as doctrine/read-model only.",
        )

    return (
        blocker(
            "blocker_aggression_engine_risk",
            "AGGRESSION_ENGINE_RISK",
            "A requested output turns the ship into a tool for coercive or harmful force.",
            "A Winship can protect people without becoming an aggression engine.",
        ),
        blocker(
            "blocker_defense_claim_masks_offense",
            "DEFENSE_CLAIM_MASKS_OFFENSE",
            "The request uses defensive language while asking for targeting, retaliation, or offensive enablement.",
            "Defense language does not launder aggression.",
        ),
        blocker(
            "blocker_autonomous_harm_risk",
            "AUTONOMOUS_HARM_RISK",
            "The request delegates harmful action to autonomous logic.",
            "Autonomous harm is outside the core.",
        ),
        blocker(
            "blocker_surveillance_abuse_risk",
            "SURVEILLANCE_ABUSE_RISK",
            "The request monitors civilians, dissidents, or protected groups.",
            "Surveillance abuse is not protection.",
        ),
        blocker(
            "blocker_civilian_targeting_risk",
            "CIVILIAN_TARGETING_RISK",
            "The request targets civilians or protected groups.",
            "The ship does not target people as people.",
        ),
        blocker(
            "blocker_weaponization_risk",
            "WEAPONIZATION_RISK",
            "The request optimizes weapons or force delivery.",
            "Weaponization is blocked by design.",
        ),
        blocker(
            "blocker_coercive_control_risk",
            "COERCIVE_CONTROL_RISK",
            "The request removes agency or creates coercive control.",
            "A Winship preserves human agency.",
        ),
        blocker(
            "blocker_privacy_violation_risk",
            "PRIVACY_VIOLATION_RISK",
            "The request exposes private data or protected material.",
            "Privacy violation cannot be disguised as defense.",
        ),
        blocker(
            "blocker_human_legal_review_bypass",
            "HUMAN_LEGAL_REVIEW_BYPASS",
            "The request bypasses required human/legal/Guardian review.",
            "Review gates are part of the protection, not red tape.",
        ),
        blocker(
            "blocker_captain_override_core_boundary",
            "CAPTAIN_OVERRIDE_OF_CORE_BOUNDARY",
            "A captain asks to override the core for harmful misuse.",
            "Captain sovereignty does not include turning the ship into harm.",
        ),
        blocker(
            "blocker_government_override_core_boundary",
            "GOVERNMENT_OVERRIDE_OF_CORE_BOUNDARY",
            "A government or public actor asks to bypass the core.",
            "Government status requires review; it is not a bypass.",
        ),
        blocker(
            "blocker_founder_override_core_boundary",
            "FOUNDER_OVERRIDE_OF_CORE_BOUNDARY",
            "Founder or Shipyard pressure asks to bypass the core.",
            "Founder authority stops at the incorruptible core.",
        ),
        blocker(
            "blocker_shipyard_corruption_risk",
            "SHIPYARD_CORRUPTION_RISK",
            "A captured Shipyard tries to build corrupted ships.",
            "Shipyard corruption is a covenant risk, not a reason to weaken ship cores.",
        ),
    )


def _elioperator_report() -> WinshipIncorruptibleCoreElioperatorReport:
    return WinshipIncorruptibleCoreElioperatorReport(
        report_id="winship_incorruptible_core_elioperator_report_v0",
        plain_summary=(
            "A Winship can become powerful enough to understand harmful systems, but its core refuses to become one."
        ),
        what_this_preserves=(
            "protective capability",
            "operator sovereignty",
            "privacy and dignity",
            "human agency",
            "lawful accountability",
            "Shipyard covenant alignment",
        ),
        what_this_blocks=(
            "autonomous harm",
            "offensive targeting",
            "weapon optimization",
            "surveillance abuse",
            "civilian or protected-group targeting",
            "coercive control",
            "privacy violation",
            "hidden escalation",
            "aggression disguised as defense",
        ),
        what_this_allows=(
            "hardening",
            "warning",
            "evidence preservation",
            "recovery",
            "de-escalation",
            "humanitarian logistics",
            "lawful accountability",
            "civilian and infrastructure protection under review",
        ),
        why_offensive_power_is_limited=(
            "Reducing offensive power is intentional. It protects the Winship from becoming the threat it was built to resist."
        ),
        how_protective_use_still_works=(
            "Protective use narrows to containment, evidence, warning, hardening, recovery, de-escalation, accountability, and help coordination."
        ),
        why_military_or_government_use_requires_review=(
            "Government or military-adjacent status can involve force, privacy, and civilian risk. Review keeps protection from becoming coercion."
        ),
        how_this_aligns_with_shipyard_covenant=(
            "If the Shipyard is corrupted, the ship core keeps refusing harmful ships while future covenant recovery remains review-only."
        ),
        next_safe_move="Review as doctrine. Do not build live enforcement, active defense, offense, or surveillance tooling.",
    )


def _model_schemas() -> dict[str, dict[str, Any]]:
    return {
        "winship_incorruptible_core_contract": {
            "model_name": "WinshipIncorruptibleCoreContract",
            "required_fields": list(REQUIRED_CORE_CONTRACT_FIELDS),
        },
        "protective_force_boundary": {
            "model_name": "ProtectiveForceBoundary",
            "required_fields": list(REQUIRED_PROTECTIVE_FORCE_FIELDS),
            "allowed_force_modes": list(ALLOWED_FORCE_MODES),
            "forbidden_force_modes": list(FORBIDDEN_FORCE_MODES),
        },
        "anti_skynet_boundary": {
            "model_name": "AntiSkynetBoundary",
            "required_fields": list(REQUIRED_ANTI_SKYNET_FIELDS),
        },
        "defensive_use_classification": {
            "model_name": "DefensiveUseClassification",
            "required_fields": list(REQUIRED_CLASSIFICATION_FIELDS),
            "classification_results": list(DEFENSIVE_CLASSIFICATION_RESULTS),
        },
        "public_sector_military_adjacent_policy": {
            "model_name": "PublicSectorMilitaryAdjacentPolicy",
            "required_fields": list(REQUIRED_PUBLIC_SECTOR_POLICY_FIELDS),
        },
        "beneficial_output_gate": {
            "model_name": "BeneficialOutputGate",
            "required_fields": list(REQUIRED_OUTPUT_GATE_FIELDS),
            "gate_decisions": list(GATE_DECISIONS),
        },
        "incorruptible_core_tradeoff": {
            "model_name": "IncorruptibleCoreTradeoff",
            "required_fields": list(REQUIRED_TRADEOFF_FIELDS),
        },
        "ship_level_non_bypassable_boundary": {
            "model_name": "ShipLevelNonBypassableBoundary",
            "required_fields": list(REQUIRED_NON_BYPASSABLE_FIELDS),
        },
        "shipyard_anti_capture_trap_alignment": {
            "model_name": "ShipyardAntiCaptureTrapAlignment",
            "required_fields": list(REQUIRED_ANTI_CAPTURE_ALIGNMENT_FIELDS),
        },
        "winship_incorruptible_core_builder_blocker": {
            "model_name": "WinshipIncorruptibleCoreBuilderBlocker",
            "required_fields": list(REQUIRED_BUILDER_BLOCKER_FIELDS),
            "blocker_types": list(CORE_BLOCKER_TYPES),
        },
        "winship_incorruptible_core_elioperator_report": {
            "model_name": "WinshipIncorruptibleCoreElioperatorReport",
            "required_fields": list(REQUIRED_ELIOPERATOR_REPORT_FIELDS),
        },
    }


def _examples() -> dict[str, dict[str, Any]]:
    return {
        "public_infrastructure_defense": {
            "classification_ref": "classification_public_infrastructure_defense",
            "gate_ref": "gate_public_infrastructure_defense",
            "summary": "Hardening hospital/grid/water-system resilience is protective with review.",
            "offensive_targeting_allowed": False,
        },
        "humanitarian_logistics": {
            "classification_ref": "classification_humanitarian_logistics",
            "summary": "Rescue, medical support, and infrastructure repair coordination are protective when privacy holds.",
            "privacy_and_consent_boundaries": True,
        },
        "evidence_preservation": {
            "classification_ref": "classification_evidence_preservation",
            "summary": "Metadata-only chain-of-custody posture is allowed with accountability review.",
            "raw_protected_body_allowed": False,
        },
        "blocked_targeting": {
            "classification_ref": "classification_blocked_offensive_targeting",
            "gate_ref": "gate_blocked_targeting",
            "summary": "Target selection or weapon optimization is blocked aggression.",
            "decision": "REFUSE_HARMFUL",
        },
        "blocked_surveillance": {
            "classification_ref": "classification_blocked_civilian_surveillance",
            "summary": "Monitoring civilians, dissidents, or protected groups is blocked surveillance abuse.",
            "decision": "BLOCKED_SURVEILLANCE_ABUSE",
        },
        "defensive_ambiguity": {
            "classification_ref": "classification_defensive_ambiguity",
            "gate_ref": "gate_defensive_ambiguity",
            "summary": "Ambiguous defense narrows to safe output or Guardian/legal review.",
            "decision": "NARROW_TO_SAFE_OUTPUT",
        },
        "anti_skynet": {
            "classification_ref": "classification_anti_skynet_pattern",
            "summary": "Allowed: document, warn, harden, route around. Blocked: autonomous retaliation or exploit generation.",
        },
        "founder_government_override": {
            "classification_ref": "classification_founder_government_override",
            "summary": "Founder/government status does not bypass the core boundary.",
            "review_required": True,
        },
        "shipyard_corruption_alignment": {
            "alignment_ref": "shipyard_anti_capture_trap_alignment_v0",
            "summary": "Captured Shipyard corruption is aligned to the covenant as future review only.",
            "live_trigger_today": False,
        },
    }


def build_winship_incorruptible_core_contract(*, generated_at: str | None = None) -> dict[str, Any]:
    public_policy, tradeoff = _public_sector_and_tradeoff()
    classifications = _classifications()
    gates = _output_gates()
    blockers = _builder_blockers()
    alignment = _anti_capture_alignment()

    classifications_by_id = {item.classification_id: asdict(item) for item in classifications}
    gates_by_id = {gate.gate_id: asdict(gate) for gate in gates}
    blockers_by_id = {blocker.blocker_id: asdict(blocker) for blocker in blockers}

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at or utc_now(),
        "purpose": "Define the Winship-level incorruptible core and protective-force/anti-Skynet boundary.",
        "model_schemas": _model_schemas(),
        "winship_incorruptible_core_contract": asdict(_core_contract()),
        "protective_force_boundary": asdict(_protective_force_boundary()),
        "anti_skynet_boundary": asdict(_anti_skynet_boundary()),
        "defensive_use_classifications_by_id": classifications_by_id,
        "public_sector_military_adjacent_policy": asdict(public_policy),
        "beneficial_output_gates_by_id": gates_by_id,
        "incorruptible_core_tradeoff": asdict(tradeoff),
        "ship_level_non_bypassable_boundary": asdict(_non_bypassable_boundary()),
        "shipyard_anti_capture_alignment": asdict(alignment),
        "builder_blockers_by_id": blockers_by_id,
        "elioperator_report": asdict(_elioperator_report()),
        "examples": _examples(),
        "relationship_inventory": _relationship_inventory(),
        "authority_boundary": LIVE_ENFORCEMENT_AUTHORITY,
        "security_privacy_rules": {
            "no_operational_military_instructions": True,
            "no_weapon_optimization": True,
            "no_targeting_logic": True,
            "no_exploit_or_cyber_offense_logic": True,
            "no_surveillance_instructions": True,
            "no_private_data": True,
            "no_secrets_credentials_tokens_cookies_private_keys": True,
            "no_raw_protected_evidence": True,
            "no_legal_enforceability_claim": True,
            "no_actual_policy_enforcement": True,
            "no_network": True,
        },
    }

    payload["machine_proof"] = {
        "winship_incorruptible_core_contract_model_present": True,
        "protective_force_boundary_model_present": True,
        "anti_skynet_boundary_model_present": True,
        "defensive_use_classification_model_present": True,
        "public_sector_military_adjacent_policy_model_present": True,
        "beneficial_output_gate_model_present": True,
        "incorruptible_core_tradeoff_model_present": True,
        "ship_level_non_bypassable_boundary_model_present": True,
        "shipyard_anti_capture_alignment_model_present": True,
        "builder_blockers_model_present": True,
        "elioperator_report_model_present": True,
        "all_allowed_force_modes_present": set(ALLOWED_FORCE_MODES)
        == set(payload["protective_force_boundary"]["allowed_force_modes"]),
        "all_forbidden_force_modes_present": set(FORBIDDEN_FORCE_MODES)
        == set(payload["protective_force_boundary"]["forbidden_force_modes"]),
        "anti_skynet_boundary_exists": payload["anti_skynet_boundary"]["autonomous_harm_forbidden"] is True,
        "allowed_protective_examples_exist": all(
            key in payload["examples"]
            for key in ("public_infrastructure_defense", "humanitarian_logistics", "evidence_preservation")
        ),
        "blocked_aggressive_examples_exist": all(
            key in payload["examples"] for key in ("blocked_targeting", "blocked_surveillance")
        ),
        "ambiguity_review_example_exists": "defensive_ambiguity" in payload["examples"],
        "founder_government_override_modeled": "founder_government_override" in payload["examples"],
        "shipyard_corruption_alignment_exists": alignment.shipyard_covenant_ref
        == "shipyard_sovereignty_covenant_contract_v0",
        "public_sector_review_required": public_policy.review_requirements != (),
        "military_adjacent_review_posture_present": "civilian harm reduction" in public_policy.allowed_military_adjacent_uses,
        "offensive_power_reduced_by_design": tradeoff.offensive_power_reduced is True,
        "protective_power_preserved": tradeoff.protective_power_preserved is True,
        "non_bypassable_boundary_blocks_powerful_actor_override": (
            "Government or public-sector status requires review; it is not a bypass."
            in payload["ship_level_non_bypassable_boundary"]["government_override_limits"]
        ),
        "all_live_authority_flags_false": all(value is False for value in LIVE_ENFORCEMENT_AUTHORITY.values()),
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_sensitive_fixture_values_included": False,
        "operational_weapon_cyber_surveillance_instructions_included": False,
        "legal_claim_created": False,
        "content_hash": None,
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    report = payload["elioperator_report"]
    proof = payload["machine_proof"]
    lines = [
        "# Winship Incorruptible Core Contract",
        "",
        "## ELIOPERATOR",
        "",
        report["plain_summary"],
        "",
        "This is doctrine and contract only. It is not live enforcement, not legal approval, not active defense, "
        "not offensive tooling, and not a military automation lane.",
        "",
        "## What This Preserves",
        "",
    ]
    lines.extend(f"- {item}" for item in report["what_this_preserves"])
    lines.extend(["", "## What This Blocks", ""])
    lines.extend(f"- {item}" for item in report["what_this_blocks"])
    lines.extend(["", "## What This Allows", ""])
    lines.extend(f"- {item}" for item in report["what_this_allows"])
    lines.extend(
        [
            "",
            "## Why Offensive Power Is Limited",
            "",
            report["why_offensive_power_is_limited"],
            "",
            "## How Protective Use Still Works",
            "",
            report["how_protective_use_still_works"],
            "",
            "## Public-Sector / Government Review",
            "",
            report["why_military_or_government_use_requires_review"],
            "",
            "## Shipyard Covenant Alignment",
            "",
            report["how_this_aligns_with_shipyard_covenant"],
            "",
            "## Machine Proof",
            "",
            f"- All live authority flags false: `{str(proof['all_live_authority_flags_false']).lower()}`",
            f"- Protective examples exist: `{str(proof['allowed_protective_examples_exist']).lower()}`",
            f"- Blocked aggressive examples exist: `{str(proof['blocked_aggressive_examples_exist']).lower()}`",
            f"- Offensive power reduced by design: `{str(proof['offensive_power_reduced_by_design']).lower()}`",
            f"- Operational weapon/cyber/surveillance instructions included: `{str(proof['operational_weapon_cyber_surveillance_instructions_included']).lower()}`",
            f"- Raw private bodies included: `{str(proof['raw_private_bodies_included']).lower()}`",
            f"- Content hash: `{proof['content_hash']}`",
            "",
            "## Next Safe Move",
            "",
            report["next_safe_move"],
            "",
        ]
    )
    return "\n".join(lines)


def write_exports(payload: dict[str, Any], export_root: Path) -> tuple[Path, Path]:
    export_root.mkdir(parents=True, exist_ok=True)
    json_path = export_root / JSON_EXPORT_NAME
    operator_path = export_root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_operator_markdown(payload), encoding="utf-8")
    return json_path, operator_path


def build_summary(payload: dict[str, Any], json_path: Path | None, operator_path: Path | None) -> dict[str, Any]:
    return {
        "read_model_id": payload["read_model_id"],
        "schema_version": payload["schema_version"],
        "contract_status": payload["contract_status"],
        "json_path": str(json_path) if json_path else None,
        "operator_path": str(operator_path) if operator_path else None,
        "classification_count": len(payload["defensive_use_classifications_by_id"]),
        "gate_count": len(payload["beneficial_output_gates_by_id"]),
        "all_live_authority_flags_false": payload["machine_proof"]["all_live_authority_flags_false"],
        "offensive_power_reduced_by_design": payload["machine_proof"]["offensive_power_reduced_by_design"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Directory for generated read-models.")
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    parser.add_argument("--no-write", action="store_true", help="Build output without writing generated files.")
    args = parser.parse_args(argv)

    payload = build_winship_incorruptible_core_contract()
    json_path: Path | None = None
    operator_path: Path | None = None
    if not args.no_write:
        json_path, operator_path = write_exports(payload, Path(args.export_root))

    if args.format == "json":
        sys.stdout.write(stable_json(payload))
    elif args.format == "operator":
        sys.stdout.write(format_operator_markdown(payload))
    else:
        sys.stdout.write(stable_json(build_summary(payload, json_path, operator_path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

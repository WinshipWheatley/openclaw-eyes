"""Shipyard Sovereignty Covenant Contract v0.

This deterministic read-model records the Shipyard sovereignty covenant as
doctrine and contract only. It does not change licenses, release source, arm
butterfly laws, trigger forks, revoke trust, migrate ships, make legal claims,
notify external systems, run governance, or create runtime enforcement.
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

SCHEMA_VERSION = "shipyard_sovereignty_covenant_contract_v0"
READ_MODEL_ID = "shipyard_sovereignty_covenant_contract"
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
CONTRACT_STATUS = "DETERMINISTIC_NON_EXECUTING_SHIPYARD_SOVEREIGNTY_COVENANT"

SHIPYARD_PHASES = (
    "CATERPILLAR_BUILD_PHASE",
    "FIRST_WINSHIP_COMMISSIONING_PHASE",
    "EARLY_FLEET_FORMATION_PHASE",
    "FLEET_ESTABLISHED_PHASE",
    "BUTTERFLY_LAWS_ARMED_PHASE",
    "CAPTURE_REVIEW_PHASE",
    "METAMORPHOSIS_RECOVERY_PHASE",
)

MISSION_VALUES = (
    "make life better without making other lives worse",
    "protect operator sovereignty",
    "protect privacy",
    "build useful capability",
    "reduce cognitive/electric waste",
    "increase meaningful work per watt",
    "preserve local-first dignity",
    "help captains and communities",
    "compound reusable rails",
    "refuse harmful capture",
)

CAPTURE_RISK_TYPES = (
    "CAPITAL_CAPTURE",
    "HOSTILE_ACQUISITION",
    "MISSION_DRIFT",
    "PRIVACY_EXPLOITATION",
    "SAFETY_GATE_BYPASS",
    "OPERATOR_LOCK_IN",
    "CROSS_CLIENT_DATA_ABUSE",
    "CREDENTIAL_OR_SECRET_ABUSE",
    "SHIPYARD_MONOPOLY_CHOKEPOINT",
    "FOUNDER_COMPROMISE",
    "GOVERNANCE_CORRUPTION",
    "PREMATURE_BUTTERFLY_TRIGGER",
    "UNKNOWN_FAIL_CLOSED",
)

COVENANT_BLOCKER_TYPES = (
    "SHIPYARD_CAPTURE_RISK",
    "FOUNDER_OVERRIDE_RISK",
    "PRIVATE_DATA_RELEASE_RISK",
    "MISSION_DRIFT_RISK",
    "CAPITAL_CONTROL_OVER_MISSION",
    "SHIPYARD_IP_LEAK_TO_SHIP",
    "CLIENT_DATA_LEAK_TO_COMMONS",
    "ANTI_CAPTURE_DISABLED",
    "PREMATURE_BUTTERFLY_TRIGGER",
    "OPERATOR_SOVEREIGNTY_WEAKENED",
    "SAFETY_GATE_WEAKENED",
    "HARMFUL_WORK_ACCEPTED_FOR_MONEY",
    "UNKNOWN_FAIL_CLOSED",
)

PRIVATE_DATA_FORBIDDEN_MATERIAL = (
    "client/operator data",
    "credentials",
    "protected evidence",
    "private business records",
    "secrets",
    "raw PII",
    "sensitive deployment data",
    "cookies",
    "tokens",
    "private keys",
    "business confidential details",
)

LIVE_TRIGGER_AUTHORITY = {
    "live_covenant_enforcement_allowed": False,
    "live_open_source_release_allowed": False,
    "live_license_change_allowed": False,
    "live_fork_trigger_allowed": False,
    "live_trust_revocation_allowed": False,
    "live_shipyard_migration_allowed": False,
    "live_governance_action_allowed": False,
    "live_legal_claim_allowed": False,
    "live_external_notification_allowed": False,
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
    "license_file_mutation_allowed": False,
    "source_publication_allowed": False,
}

REQUIRED_COVENANT_FIELDS = (
    "covenant_id",
    "doctrine_name",
    "doctrine_summary",
    "shipyard_definition",
    "winship_definition",
    "fleet_definition",
    "captain_definition",
    "mission_statement",
    "commercial_phase_policy",
    "capital_boundary",
    "creator_boundary",
    "anti_capture_policy",
    "commons_fail_safe_policy",
    "butterfly_law_activation_boundary",
    "private_data_boundary",
    "legal_review_required",
    "live_trigger_authority",
    "current_contract_status",
    "next_safe_move",
)

REQUIRED_PHASE_MODEL_FIELDS = (
    "phase_model_id",
    "current_phase",
    "phases",
    "butterfly_laws_currently_armed",
    "pre_fleet_activation_blocked",
    "fleet_establishment_required",
    "legal_review_required",
    "explicit_founder_operator_arming_required",
    "last_clean_state_required",
    "private_data_exclusion_required",
    "live_open_source_release_allowed",
    "live_license_change_allowed",
    "live_fork_trigger_allowed",
    "live_covenant_enforcement_allowed",
    "next_safe_move",
)

REQUIRED_MISSION_DNA_FIELDS = (
    "dna_id",
    "values",
    "positive_mission",
    "prohibited_drift",
    "operator_sovereignty",
    "privacy_dignity",
    "local_first_posture",
    "meaningful_work_gravity",
    "anti_sludge_posture",
    "shipyard_vs_ship_boundary",
    "fleet_mutual_aid_posture",
    "contribution_commons_posture",
    "next_safe_move",
)

REQUIRED_COMMERCIAL_BOUNDARY_FIELDS = (
    "boundary_id",
    "commercial_operation_allowed",
    "capital_use_allowed",
    "capital_capture_forbidden",
    "high_margin_work_policy",
    "cross_subsidy_policy",
    "fleet_positive_reinvestment_policy",
    "private_operator_work_policy",
    "harmful_work_refusal_policy",
    "mission_drift_warning",
    "next_safe_move",
)

REQUIRED_CREATOR_POLICY_FIELDS = (
    "policy_id",
    "founder_role",
    "founder_not_above_covenant",
    "prohibited_founder_actions",
    "creator_capture_risk",
    "creator_override_limits",
    "required_warning_behavior",
    "future_governance_review",
    "elioperator_warning",
    "next_safe_move",
)

REQUIRED_CAPTURE_RISK_FIELDS = (
    "risk_id",
    "risk_type",
    "description",
    "severity",
    "early_warning_signals",
    "affected_mission_values",
    "likely_consequence",
    "required_response",
    "fail_safe_relevance",
    "elioperator_explanation",
    "next_safe_move",
)

REQUIRED_RECOVERY_ROOT_FIELDS = (
    "recovery_root_id",
    "purpose",
    "last_verified_uncompromised_state_ref",
    "clean_state_requirements",
    "signed_release_requirements",
    "hash_requirements",
    "reproducibility_requirements",
    "test_requirements",
    "security_review_requirements",
    "private_data_exclusion",
    "release_or_escrow_policy",
    "legal_review_required",
    "current_live_authority",
    "next_safe_move",
)

REQUIRED_FAIL_SAFE_FIELDS = (
    "fail_safe_id",
    "metaphor",
    "trigger_concept",
    "phase_prerequisites",
    "capture_response",
    "fleet_trust_rerouting",
    "new_shipyard_spawning_policy",
    "corrupted_shipyard_handling",
    "uncompromised_shipyard_requirements",
    "private_data_protection",
    "non_military_framing",
    "mission_continuity",
    "next_safe_move",
)

REQUIRED_MUTUAL_AID_FIELDS = (
    "economy_id",
    "ship_to_fleet_contribution",
    "fleet_to_ship_reinforcement",
    "module_creation_policy",
    "support_offer_policy",
    "shared_output_policy",
    "private_boundary",
    "license_visibility_posture",
    "captain_consent_required",
    "contribution_receipts_required",
    "reciprocity_summary",
    "next_safe_move",
)

REQUIRED_SHIPYARD_VS_SHIP_FIELDS = (
    "boundary_id",
    "shipyard_internal_capabilities",
    "winship_capabilities",
    "client_ship_capabilities",
    "fleet_visible_metadata",
    "forbidden_to_ship",
    "shipyard_ip_boundary",
    "export_allowed_policy",
    "support_visibility_policy",
    "next_safe_move",
)

REQUIRED_BLOCKER_FIELDS = (
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
    "what_this_does_not_do_yet",
    "why_creator_is_bounded",
    "why_private_data_is_not_released",
    "why_commercial_operation_is_allowed",
    "why_butterfly_laws_are_not_armed_yet",
    "what_happens_conceptually_if_capture_occurs_after_fleet_establishment",
    "next_safe_move",
)

RELATIONSHIP_REF_PATHS = {
    "meaningful_work_gravity_contract": "generated/read_models/meaningful_work_gravity_contract.json",
    "cross_surface_artifact_handoff_registry_contract": (
        "generated/read_models/cross_surface_artifact_handoff_registry_contract.json"
    ),
    "cross_lane_reusable_block_registry_contract": (
        "generated/read_models/cross_lane_reusable_block_registry_contract.json"
    ),
    "cross_surface_handoff_registry_metadata_alignment": (
        "generated/read_models/cross_surface_handoff_registry_metadata_alignment.json"
    ),
    "openclaw_sensitive_policy": "openclaw_sensitive_policy.py",
    "guardian_protected_access_gate_spec": "generated/read_models/guardian_protected_access_gate_spec.json",
    "guided_capture_protected_evidence_path_contract": (
        "generated/read_models/guided_capture_protected_evidence_path_contract.json"
    ),
    "work_terrain_surface_map_build_cue_scout": "generated/read_models/work_terrain_surface_map_build_cue_scout.json",
    "work_terrain_build_cue_reconciliation_queue": (
        "generated/read_models/work_terrain_build_cue_reconciliation_queue.json"
    ),
    "operator_question_assist_scope_expansion_contract": (
        "generated/read_models/operator_question_assist_scope_expansion_contract.json"
    ),
    "bridge_routing_operator_attention_contract": (
        "generated/read_models/bridge_routing_operator_attention_contract.json"
    ),
    "agent_execution_packet_compiler_contract": (
        "generated/read_models/agent_execution_packet_compiler_contract.json"
    ),
    "agent_conversation_handoff_step_packet_contract": (
        "generated/read_models/agent_conversation_handoff_step_packet_contract.json"
    ),
    "operator_action_covenant": "operator_action_covenant.py",
}


@dataclass(frozen=True)
class ShipyardSovereigntyCovenant:
    covenant_id: str
    doctrine_name: str
    doctrine_summary: str
    shipyard_definition: str
    winship_definition: str
    fleet_definition: str
    captain_definition: str
    mission_statement: tuple[str, ...]
    commercial_phase_policy: str
    capital_boundary: str
    creator_boundary: str
    anti_capture_policy: str
    commons_fail_safe_policy: str
    butterfly_law_activation_boundary: str
    private_data_boundary: dict[str, Any]
    legal_review_required: bool
    live_trigger_authority: dict[str, bool]
    current_contract_status: str
    next_safe_move: str


@dataclass(frozen=True)
class ShipyardPhaseModel:
    phase_model_id: str
    current_phase: str
    phases: tuple[dict[str, Any], ...]
    butterfly_laws_currently_armed: bool
    pre_fleet_activation_blocked: bool
    fleet_establishment_required: bool
    legal_review_required: bool
    explicit_founder_operator_arming_required: bool
    last_clean_state_required: bool
    private_data_exclusion_required: bool
    live_open_source_release_allowed: bool
    live_license_change_allowed: bool
    live_fork_trigger_allowed: bool
    live_covenant_enforcement_allowed: bool
    next_safe_move: str


@dataclass(frozen=True)
class ShipyardMissionDNA:
    dna_id: str
    values: tuple[str, ...]
    positive_mission: tuple[str, ...]
    prohibited_drift: tuple[str, ...]
    operator_sovereignty: str
    privacy_dignity: str
    local_first_posture: str
    meaningful_work_gravity: str
    anti_sludge_posture: str
    shipyard_vs_ship_boundary: str
    fleet_mutual_aid_posture: str
    contribution_commons_posture: str
    next_safe_move: str


@dataclass(frozen=True)
class CommercialMissionBoundary:
    boundary_id: str
    commercial_operation_allowed: bool
    capital_use_allowed: bool
    capital_capture_forbidden: bool
    high_margin_work_policy: str
    cross_subsidy_policy: str
    fleet_positive_reinvestment_policy: str
    private_operator_work_policy: str
    harmful_work_refusal_policy: str
    mission_drift_warning: str
    next_safe_move: str


@dataclass(frozen=True)
class CreatorBoundednessPolicy:
    policy_id: str
    founder_role: str
    founder_not_above_covenant: bool
    prohibited_founder_actions: tuple[str, ...]
    creator_capture_risk: str
    creator_override_limits: str
    required_warning_behavior: str
    future_governance_review: str
    elioperator_warning: str
    next_safe_move: str


@dataclass(frozen=True)
class ShipyardCaptureRisk:
    risk_id: str
    risk_type: str
    description: str
    severity: str
    early_warning_signals: tuple[str, ...]
    affected_mission_values: tuple[str, ...]
    likely_consequence: str
    required_response: str
    fail_safe_relevance: str
    elioperator_explanation: str
    next_safe_move: str


@dataclass(frozen=True)
class LastCleanStateRecoveryRoot:
    recovery_root_id: str
    purpose: str
    last_verified_uncompromised_state_ref: str
    clean_state_requirements: tuple[str, ...]
    signed_release_requirements: tuple[str, ...]
    hash_requirements: tuple[str, ...]
    reproducibility_requirements: tuple[str, ...]
    test_requirements: tuple[str, ...]
    security_review_requirements: tuple[str, ...]
    private_data_exclusion: tuple[str, ...]
    release_or_escrow_policy: str
    legal_review_required: bool
    current_live_authority: dict[str, bool]
    next_safe_move: str


@dataclass(frozen=True)
class FleetMetamorphosisFailSafe:
    fail_safe_id: str
    metaphor: str
    trigger_concept: str
    phase_prerequisites: tuple[str, ...]
    capture_response: str
    fleet_trust_rerouting: str
    new_shipyard_spawning_policy: str
    corrupted_shipyard_handling: str
    uncompromised_shipyard_requirements: tuple[str, ...]
    private_data_protection: str
    non_military_framing: str
    mission_continuity: str
    next_safe_move: str


@dataclass(frozen=True)
class FleetMutualAidModuleEconomy:
    economy_id: str
    ship_to_fleet_contribution: str
    fleet_to_ship_reinforcement: str
    module_creation_policy: str
    support_offer_policy: str
    shared_output_policy: str
    private_boundary: str
    license_visibility_posture: str
    captain_consent_required: bool
    contribution_receipts_required: bool
    reciprocity_summary: str
    next_safe_move: str


@dataclass(frozen=True)
class ShipyardVsShipBoundary:
    boundary_id: str
    shipyard_internal_capabilities: tuple[str, ...]
    winship_capabilities: tuple[str, ...]
    client_ship_capabilities: tuple[str, ...]
    fleet_visible_metadata: tuple[str, ...]
    forbidden_to_ship: tuple[str, ...]
    shipyard_ip_boundary: str
    export_allowed_policy: str
    support_visibility_policy: str
    next_safe_move: str


@dataclass(frozen=True)
class CovenantBuilderBlocker:
    blocker_id: str
    blocker_type: str
    condition: str
    severity: str
    elioperator_warning: str
    builder_action_required: str
    fail_closed: bool
    next_safe_move: str


@dataclass(frozen=True)
class CovenantElioperatorReport:
    report_id: str
    plain_summary: str
    what_this_preserves: tuple[str, ...]
    what_this_does_not_do_yet: tuple[str, ...]
    why_creator_is_bounded: str
    why_private_data_is_not_released: str
    why_commercial_operation_is_allowed: str
    why_butterfly_laws_are_not_armed_yet: str
    what_happens_conceptually_if_capture_occurs_after_fleet_establishment: str
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


def _private_data_boundary() -> dict[str, Any]:
    return {
        "normal_read_model_private_material_allowed": False,
        "release_or_fork_private_material_allowed": False,
        "forbidden_material": PRIVATE_DATA_FORBIDDEN_MATERIAL,
        "private_data_exclusion_required": True,
        "protected_evidence_exclusion_required": True,
        "credential_secret_exclusion_required": True,
        "deployment_sensitive_data_exclusion_required": True,
        "safe_material_scope": (
            "future legally reviewed clean core only; no client/operator private state, protected evidence, or secrets"
        ),
    }


def _covenant() -> ShipyardSovereigntyCovenant:
    return ShipyardSovereigntyCovenant(
        covenant_id="shipyard_sovereignty_covenant_v0",
        doctrine_name="Shipyard Sovereignty Covenant v0",
        doctrine_summary=(
            "The Shipyard may operate commercially while mission-aligned, but capital, founder control, customers, "
            "or hostile actors must not own the mission."
        ),
        shipyard_definition=(
            "The Shipyard is the protected builder substrate that creates, commissions, supports, and improves Winships."
        ),
        winship_definition=(
            "A Winship is a captain-specific local-first vessel built to help its captain do meaningful work without "
            "surrendering privacy, agency, dignity, or local sovereignty."
        ),
        fleet_definition="The Fleet emerges as multiple operational Winships and Fleet-positive modules exist.",
        captain_definition="A captain is the sovereign local operator of a Winship.",
        mission_statement=(
            "build Winships that help people improve their lives without making other lives worse",
            "protect operator sovereignty",
            "protect private data",
            "build reusable rails",
            "reduce cognitive/electric waste",
            "increase meaningful work per watt",
            "preserve local-first dignity",
            "make useful work compound",
        ),
        commercial_phase_policy="Commercial operation is allowed while mission-aligned and privacy/safety boundaries hold.",
        capital_boundary="The Shipyard may use capital; capital must not own the mission.",
        creator_boundary=(
            "Winship is the founder, not the owner of the mission's soul. Even the creator is bounded by the covenant."
        ),
        anti_capture_policy=(
            "If future Fleet-established capture is verified under armed and legally reviewed butterfly laws, the last "
            "verified uncompromised clean core may become a recovery root."
        ),
        commons_fail_safe_policy=(
            "Capture should lead to trust migration and new uncompromised Shipyards, not monopoly control or retaliation."
        ),
        butterfly_law_activation_boundary=(
            "No butterfly law can be armed before Fleet establishment, legal/governance review, explicit arming, "
            "last-clean-state proof, and private-data exclusion."
        ),
        private_data_boundary=_private_data_boundary(),
        legal_review_required=True,
        live_trigger_authority=LIVE_TRIGGER_AUTHORITY,
        current_contract_status="DOCTRINE_READ_MODEL_ONLY_NO_LIVE_TRIGGER",
        next_safe_move="Review as Shipyard DNA; do not implement release, fork, or governance automation.",
    )


def _phase_model() -> ShipyardPhaseModel:
    phases = (
        {
            "phase": "CATERPILLAR_BUILD_PHASE",
            "description": "The Shipyard is being built. No Winship is fully commissioned.",
            "open_source_or_recovery_trigger_allowed": False,
        },
        {
            "phase": "FIRST_WINSHIP_COMMISSIONING_PHASE",
            "description": "The Winchie is being generated, customized, tested, and made operational for Operator + Winship.",
            "open_source_or_recovery_trigger_allowed": False,
        },
        {
            "phase": "EARLY_FLEET_FORMATION_PHASE",
            "description": "The Winchie and early additional Winships exist, but the Fleet is not mature enough for metamorphosis.",
            "open_source_or_recovery_trigger_allowed": False,
        },
        {
            "phase": "FLEET_ESTABLISHED_PHASE",
            "description": "The Fleet is real enough that Shipyard capture would harm a meaningful network of captains and rails.",
            "open_source_or_recovery_trigger_allowed": False,
            "butterfly_laws_become_eligible_for_review": True,
        },
        {
            "phase": "BUTTERFLY_LAWS_ARMED_PHASE",
            "description": "Butterfly laws are armed only after Fleet establishment, proofs, legal review, and explicit arming.",
            "open_source_or_recovery_trigger_allowed": False,
            "arming_prerequisites_required": True,
        },
        {
            "phase": "CAPTURE_REVIEW_PHASE",
            "description": "A suspected capture/corruption event is reviewed against future legal/governance criteria.",
            "open_source_or_recovery_trigger_allowed": False,
        },
        {
            "phase": "METAMORPHOSIS_RECOVERY_PHASE",
            "description": "Future recovery/fork/open-source pathway may be considered only after verified criteria and private-data exclusion.",
            "open_source_or_recovery_trigger_allowed": False,
            "contract_itself_does_not_execute": True,
        },
    )
    return ShipyardPhaseModel(
        phase_model_id="shipyard_phase_model_v0",
        current_phase="CATERPILLAR_BUILD_PHASE",
        phases=phases,
        butterfly_laws_currently_armed=False,
        pre_fleet_activation_blocked=True,
        fleet_establishment_required=True,
        legal_review_required=True,
        explicit_founder_operator_arming_required=True,
        last_clean_state_required=True,
        private_data_exclusion_required=True,
        live_open_source_release_allowed=False,
        live_license_change_allowed=False,
        live_fork_trigger_allowed=False,
        live_covenant_enforcement_allowed=False,
        next_safe_move="Continue Shipyard construction; no activation path exists now.",
    )


def _mission_dna() -> ShipyardMissionDNA:
    return ShipyardMissionDNA(
        dna_id="shipyard_mission_dna_v0",
        values=MISSION_VALUES,
        positive_mission=(
            "build Winships that help captains do useful local work",
            "protect private data and agency",
            "make reusable rails compound without coercion",
            "use commerce and capital only inside mission boundaries",
        ),
        prohibited_drift=(
            "privacy exploitation",
            "operator lock-in",
            "safety-gate weakening",
            "centralized monopoly choke point",
            "cross-client data abuse",
            "capital control over mission",
            "harmful work accepted for money",
        ),
        operator_sovereignty="Captains remain sovereign over their ships and private work.",
        privacy_dignity="Private data, protected evidence, credentials, and sensitive deployments are not commons material.",
        local_first_posture="Winships should remain local-first and captain-specific unless explicit consent changes visibility.",
        meaningful_work_gravity="Use the Meaningful Work Gravity compass without scores, shame, or task hijack.",
        anti_sludge_posture="Reduce repeated context churn, fake progress, and one-off glue when durable rails are cheap.",
        shipyard_vs_ship_boundary="The Shipyard builds ships; ships do not silently receive the whole Shipyard.",
        fleet_mutual_aid_posture="Fleet support is consent-based and should reinforce ships without extracting private work.",
        contribution_commons_posture="Sharing posture may be private, module, pattern-only, expertise signal, or declined.",
        next_safe_move="Use these values as review criteria for future Shipyard and Fleet work.",
    )


def _commercial_boundary() -> CommercialMissionBoundary:
    return CommercialMissionBoundary(
        boundary_id="commercial_mission_boundary_v0",
        commercial_operation_allowed=True,
        capital_use_allowed=True,
        capital_capture_forbidden=True,
        high_margin_work_policy=(
            "High-margin commercial work is allowed only if it does not compromise mission, safety, privacy, or sovereignty."
        ),
        cross_subsidy_policy="Surplus may fund Fleet-positive modules and public/fleet-good rails.",
        fleet_positive_reinvestment_policy=(
            "Commercial success should reinforce reusable capability, privacy, and local-first dignity."
        ),
        private_operator_work_policy=(
            "Ordinary private/operator/business improvement is allowed and is not treated as greed."
        ),
        harmful_work_refusal_policy="Harmful work may be refused outright, not merely taxed or priced higher.",
        mission_drift_warning="If money requires weakening privacy, safety gates, local-first posture, or operator sovereignty, decline.",
        next_safe_move="Keep commercial choices mission-aligned and explicitly bounded.",
    )


def _creator_policy() -> CreatorBoundednessPolicy:
    return CreatorBoundednessPolicy(
        policy_id="creator_boundedness_policy_v0",
        founder_role="Winship is founder and first captain, not owner of the mission's soul.",
        founder_not_above_covenant=True,
        prohibited_founder_actions=(
            "disabling anti-capture protections for convenience, money, fear, pressure, or status",
            "bypassing privacy boundaries",
            "using Shipyard control to exploit captains or clients",
            "converting Fleet-positive rails into coercive lock-in",
            "suppressing lawful clean forks under future armed covenant conditions",
            "selling control in a way that violates mission",
            "removing operator sovereignty protections",
            "weakening safety gates to satisfy powerful customers",
        ),
        creator_capture_risk="Founder pressure can become capture if mission boundaries are weakened.",
        creator_override_limits="Founder authority cannot bypass privacy, safety, Fleet-positive continuity, or future legal covenant gates.",
        required_warning_behavior="Warn if founder, buyer, investor, company, or hostile actor tries to weaken covenant boundaries.",
        future_governance_review="Future review required before any armed covenant, recovery, or governance action.",
        elioperator_warning=(
            "ELIOPERATOR: Founder authority stops at the mission boundary. This is mission preservation, not anti-founder."
        ),
        next_safe_move="Treat founder compromise as a risk to review, not a live trigger.",
    )


def _capture_risks() -> tuple[ShipyardCaptureRisk, ...]:
    return (
        ShipyardCaptureRisk(
            risk_id="risk_capital_capture",
            risk_type="CAPITAL_CAPTURE",
            description="Investor or buyer pressure redirects the Shipyard away from mission boundaries.",
            severity="high",
            early_warning_signals=(
                "privacy protections described as growth blockers",
                "local-first posture weakened for monetization",
                "safety gates bypassed for powerful customers",
            ),
            affected_mission_values=("protect privacy", "protect operator sovereignty", "refuse harmful capture"),
            likely_consequence="Captains lose trust and the Shipyard becomes a choke point.",
            required_response="Warn, review, and block mission-weakening changes; no live fail-safe trigger in this contract.",
            fail_safe_relevance="Future Fleet-established capture criterion candidate.",
            elioperator_explanation="Capital can help build; it cannot own the mission.",
            next_safe_move="Keep capital boundary explicit in future reviews.",
        ),
        ShipyardCaptureRisk(
            risk_id="risk_founder_compromise",
            risk_type="FOUNDER_COMPROMISE",
            description="The founder weakens privacy, safety, or sovereignty for pressure, money, status, or fear.",
            severity="high",
            early_warning_signals=(
                "anti-capture protections disabled",
                "private boundaries bypassed",
                "Fleet-positive rails converted into lock-in",
            ),
            affected_mission_values=("protect operator sovereignty", "protect privacy", "refuse harmful capture"),
            likely_consequence="The covenant's mission can be captured from inside.",
            required_response="Generate warning and require future governance/legal review; no live trigger today.",
            fail_safe_relevance="Founder is bounded by covenant under future armed process.",
            elioperator_explanation="Even the creator is inside the boundary.",
            next_safe_move="Model warning only; do not enforce live governance.",
        ),
        ShipyardCaptureRisk(
            risk_id="risk_private_data_release",
            risk_type="PRIVACY_EXPLOITATION",
            description="Private client/operator data or protected evidence is treated as releasable commons material.",
            severity="critical",
            early_warning_signals=(
                "private deployment state included in release candidate",
                "protected evidence copied into normal read-models",
                "credentials or secrets considered recoverable assets",
            ),
            affected_mission_values=("protect privacy", "preserve local-first dignity"),
            likely_consequence="Covenant recovery would harm the people it is meant to protect.",
            required_response="Fail closed; exclude private material before any future review.",
            fail_safe_relevance="Private-data exclusion is a hard prerequisite.",
            elioperator_explanation="The Shipyard's clean core is not the same as captains' private data.",
            next_safe_move="Keep private data exclusion machine-checkable in future lanes.",
        ),
        ShipyardCaptureRisk(
            risk_id="risk_safety_gate_bypass",
            risk_type="SAFETY_GATE_BYPASS",
            description="A customer, investor, founder, or operator tries to weaken safety gates for speed or money.",
            severity="high",
            early_warning_signals=(
                "approval gates framed as optional ceremony",
                "credential-bearing flows routed around Guardian",
                "external actions bundled into read-model lanes",
            ),
            affected_mission_values=("protect operator sovereignty", "build useful capability"),
            likely_consequence="Fast execution starts harming privacy, legality, or trust.",
            required_response="Block unsafe authority expansion and require bounded review.",
            fail_safe_relevance="Repeated safety bypass can indicate mission drift.",
            elioperator_explanation="Power without gates is capture by convenience.",
            next_safe_move="Keep authority flags explicit and false unless a future lane proves otherwise.",
        ),
        ShipyardCaptureRisk(
            risk_id="risk_premature_butterfly_trigger",
            risk_type="PREMATURE_BUTTERFLY_TRIGGER",
            description="Someone attempts recovery/open-source/fork activation before Fleet establishment and arming criteria.",
            severity="critical",
            early_warning_signals=(
                "The Winchie completion treated as enough for metamorphosis",
                "legal review skipped",
                "last-clean-state proof absent",
                "private data exclusion not proven",
            ),
            affected_mission_values=("refuse harmful capture", "protect privacy", "protect operator sovereignty"),
            likely_consequence="The covenant becomes an accidental release mechanism.",
            required_response="Fail closed. The Winchie proves birth; the Fleet justifies metamorphosis.",
            fail_safe_relevance="Pre-Fleet activation is explicitly blocked.",
            elioperator_explanation="No accidental trigger is possible now.",
            next_safe_move="Keep butterfly laws unarmed.",
        ),
    )


def _last_clean_state_recovery_root() -> LastCleanStateRecoveryRoot:
    return LastCleanStateRecoveryRoot(
        recovery_root_id="last_clean_state_recovery_root_v0",
        purpose="Define future clean-core proof requirements before any recovery root could be considered.",
        last_verified_uncompromised_state_ref="future_required_not_available_now",
        clean_state_requirements=(
            "verified uncompromised Shipyard core",
            "private data excluded",
            "secrets and credentials excluded",
            "protected evidence excluded",
            "client/operator deployments excluded",
            "tests and hashes reproducible",
            "legal/governance review complete",
        ),
        signed_release_requirements=(
            "future signing policy required",
            "authorized signers required",
            "tamper-evident provenance required",
        ),
        hash_requirements=("content hashes required", "manifest hash required", "dependency provenance required"),
        reproducibility_requirements=("clean checkout", "deterministic build/test evidence", "no private roots"),
        test_requirements=("security tests", "privacy exclusion tests", "license review tests", "mission boundary tests"),
        security_review_requirements=("secret scan", "private body scan", "protected evidence exclusion", "supply chain review"),
        private_data_exclusion=PRIVATE_DATA_FORBIDDEN_MATERIAL,
        release_or_escrow_policy=(
            "No actual release or escrow occurs here. Future clean core may be eligible only under legally reviewed covenant."
        ),
        legal_review_required=True,
        current_live_authority=LIVE_TRIGGER_AUTHORITY,
        next_safe_move="Do not create release artifacts; keep proof requirements as doctrine.",
    )


def _metamorphosis_fail_safe() -> FleetMetamorphosisFailSafe:
    return FleetMetamorphosisFailSafe(
        fail_safe_id="fleet_metamorphosis_fail_safe_v0",
        metaphor="Capture triggers metamorphosis: the caterpillar becomes a field of butterflies.",
        trigger_concept=(
            "Only future verified Shipyard capture after Fleet establishment and armed butterfly laws may enter review."
        ),
        phase_prerequisites=(
            "FLEET_ESTABLISHED_PHASE",
            "BUTTERFLY_LAWS_ARMED_PHASE",
            "legal/governance criteria defined",
            "explicit founder/operator arming occurred",
            "last-clean-state proof exists",
            "private data exclusion proven",
        ),
        capture_response="Conceptual response is fork/migration/trust revocation, not attack.",
        fleet_trust_rerouting="The Fleet should route trust toward uncompromised Shipyards.",
        new_shipyard_spawning_policy="Future clean core may seed new uncompromised Shipyards only under reviewed covenant.",
        corrupted_shipyard_handling="Corrupted Shipyards lose trust conceptually; no violence, hacking, or retaliation.",
        uncompromised_shipyard_requirements=(
            "mission-aligned",
            "privacy-preserving",
            "operator-sovereign",
            "local-first",
            "safety-gated",
            "clean-state verified",
        ),
        private_data_protection="No captain data, client data, secrets, or protected evidence enter the recovery root.",
        non_military_framing=(
            "This is not military. Ships are local tools for good work, creative work, business dignity, community usefulness, privacy, and capability."
        ),
        mission_continuity="The mission continues by trust migration to clean Shipyards, not monopoly control.",
        next_safe_move="Keep as future doctrine; butterfly laws are not armed.",
    )


def _mutual_aid_economy() -> FleetMutualAidModuleEconomy:
    return FleetMutualAidModuleEconomy(
        economy_id="fleet_mutual_aid_module_economy_v0",
        ship_to_fleet_contribution="Ships may contribute generalized modules, patterns, receipts, or expertise signals by consent.",
        fleet_to_ship_reinforcement="The Shipyard and Fleet may support a captain's mission when the pattern strengthens the Fleet.",
        module_creation_policy="Fleet-backed modules should preserve private data boundaries and explicit visibility.",
        support_offer_policy="Support is offered, not extracted. The captain may accept, narrow, or decline.",
        shared_output_policy=(
            "Output may remain private, become a generalized module, become pattern-only, become an expertise signal, or be declined."
        ),
        private_boundary="No hidden extraction and no private data sharing by default.",
        license_visibility_posture="License and visibility posture must be explicit and legally reviewed before commercial reuse.",
        captain_consent_required=True,
        contribution_receipts_required=True,
        reciprocity_summary="Ships help the Shipyard build better ships; the Shipyard helps ships become more capable.",
        next_safe_move="Model sharing choices in future support packets; do not infer consent.",
    )


def _shipyard_vs_ship_boundary() -> ShipyardVsShipBoundary:
    return ShipyardVsShipBoundary(
        boundary_id="shipyard_vs_ship_boundary_v0",
        shipyard_internal_capabilities=(
            "app/workflow generators",
            "Work Terrain and Build Cue",
            "agent/package compiler",
            "productization, onboarding, pricing, and commissioning machinery",
            "internal prompt recipes",
            "cross-client support/monitoring backend",
            "template library",
            "core build/deploy/update rails",
        ),
        winship_capabilities=(
            "scoped workflows",
            "local ledger/receipt store",
            "capture/readback loop",
            "local operator profile",
            "client-specific adapters",
            "protected evidence refs",
            "sanitized support packets",
            "update hooks",
        ),
        client_ship_capabilities=(
            "client-specific workflows",
            "local captain state",
            "bounded adapters",
            "sanitized support handoffs",
            "protected evidence references",
        ),
        fleet_visible_metadata=(
            "ship type",
            "module compatibility",
            "safe support posture",
            "consented contribution posture",
            "sanitized health/readiness summary",
        ),
        forbidden_to_ship=(
            "full Shipyard commissioning machinery",
            "cross-client private state",
            "unscoped internal prompt recipes",
            "central support backend secrets",
            "unreviewed productization/pricing machinery",
            "other captains' private data",
        ),
        shipyard_ip_boundary="Ships receive only scoped capabilities and explicit update/support hooks, not the whole Shipyard.",
        export_allowed_policy="Exports must be scoped, consented, privacy-clean, and license-visible.",
        support_visibility_policy="Support packets should be sanitized and explicit about what the Shipyard can see.",
        next_safe_move="Keep this boundary visible before any commissioning or client-ship generator lane.",
    )


def _builder_blockers() -> tuple[CovenantBuilderBlocker, ...]:
    def blocker(blocker_id: str, blocker_type: str, condition: str, warning: str) -> CovenantBuilderBlocker:
        return CovenantBuilderBlocker(
            blocker_id=blocker_id,
            blocker_type=blocker_type,
            condition=condition,
            severity="BLOCKS_SAFE_MIGRATION",
            elioperator_warning=f"ELIOPERATOR: {warning}",
            builder_action_required="Fail closed and route to covenant/legal/governance review; do not trigger live action.",
            fail_closed=True,
            next_safe_move="Keep covenant read-model only.",
        )

    return (
        blocker(
            "blocker_shipyard_capture_risk",
            "SHIPYARD_CAPTURE_RISK",
            "A buyer, investor, company, or hostile actor redirects the Shipyard against mission.",
            "Shipyard capture risk detected. Capital can help build; it cannot own the mission.",
        ),
        blocker(
            "blocker_founder_override_risk",
            "FOUNDER_OVERRIDE_RISK",
            "Founder attempts to weaken privacy, safety, sovereignty, or anti-capture boundaries.",
            "Founder authority stops at the mission boundary.",
        ),
        blocker(
            "blocker_private_data_release_risk",
            "PRIVATE_DATA_RELEASE_RISK",
            "Any release/recovery/fork path includes private data, protected evidence, secrets, or sensitive deployments.",
            "Private data is not Shipyard commons material.",
        ),
        blocker(
            "blocker_mission_drift_risk",
            "MISSION_DRIFT_RISK",
            "Commercial, social, or operational pressure weakens the Shipyard mission.",
            "Mission drift must be reviewed before it becomes policy.",
        ),
        blocker(
            "blocker_capital_control_over_mission",
            "CAPITAL_CONTROL_OVER_MISSION",
            "Capital terms require control over privacy, mission, safety gates, or local-first posture.",
            "Capital may be used; it may not own the mission.",
        ),
        blocker(
            "blocker_shipyard_ip_leak_to_ship",
            "SHIPYARD_IP_LEAK_TO_SHIP",
            "A ship receives internal Shipyard machinery outside scoped commissioning policy.",
            "Shipyard and ship boundaries must stay explicit.",
        ),
        blocker(
            "blocker_client_data_leak_to_commons",
            "CLIENT_DATA_LEAK_TO_COMMONS",
            "Client/operator private data is proposed for commons, module, or support reuse.",
            "Share patterns or modules only after privacy-clean consent.",
        ),
        blocker(
            "blocker_anti_capture_disabled",
            "ANTI_CAPTURE_DISABLED",
            "Anti-capture protection is disabled for convenience, money, fear, pressure, or status.",
            "Anti-capture is mission protection, not optional decoration.",
        ),
        blocker(
            "blocker_premature_butterfly_trigger",
            "PREMATURE_BUTTERFLY_TRIGGER",
            "Someone tries to arm or trigger recovery before Fleet establishment and explicit arming.",
            "The Winchie proves birth. The Fleet justifies metamorphosis. No trigger is active now.",
        ),
        blocker(
            "blocker_operator_sovereignty_weakened",
            "OPERATOR_SOVEREIGNTY_WEAKENED",
            "A change reduces captain agency, consent, local-first posture, or exit/migration dignity.",
            "Operator sovereignty is a covenant value, not a feature toggle.",
        ),
        blocker(
            "blocker_safety_gate_weakened",
            "SAFETY_GATE_WEAKENED",
            "A change weakens gates for credential, external, legal, financial, or protected actions.",
            "Power must stay gated where harm can leave the local vessel.",
        ),
        blocker(
            "blocker_harmful_work_accepted_for_money",
            "HARMFUL_WORK_ACCEPTED_FOR_MONEY",
            "The Shipyard accepts harmful work because the margin is attractive.",
            "Harmful work is refused, not merely repriced.",
        ),
    )


def _elioperator_report() -> CovenantElioperatorReport:
    return CovenantElioperatorReport(
        report_id="shipyard_sovereignty_covenant_elioperator_report_v0",
        plain_summary=(
            "The Shipyard is being built to create sovereign local Winships. This covenant preserves the mission DNA "
            "without creating any live legal, release, fork, or governance mechanism."
        ),
        what_this_preserves=(
            "The Shipyard's mission-aligned sovereignty.",
            "The Winchie as the first Winship, not the full Shipyard.",
            "Fleet-positive continuity after a future mature Fleet exists.",
            "Privacy, local-first dignity, safety gates, and operator sovereignty.",
            "Commercial operation inside mission boundaries.",
        ),
        what_this_does_not_do_yet=(
            "No open-source release.",
            "No license change.",
            "No fork trigger.",
            "No trust revocation.",
            "No Shipyard migration.",
            "No legal claim.",
            "No governance action.",
            "No external notification.",
        ),
        why_creator_is_bounded=(
            "A mission can be harmed by its founder as well as by outside capital. The covenant warns on mission-weakening founder actions."
        ),
        why_private_data_is_not_released=(
            "Recovery can only concern a future privacy-clean Shipyard core. Captains' private data, client records, credentials, and protected evidence are excluded."
        ),
        why_commercial_operation_is_allowed=(
            "Money can fund useful capability. It becomes capture only when it weakens mission, privacy, safety, or sovereignty."
        ),
        why_butterfly_laws_are_not_armed_yet=(
            "The Shipyard is still in Caterpillar Build phase. The Winchie alone is not enough. A real Fleet, proofs, legal review, and explicit arming are required."
        ),
        what_happens_conceptually_if_capture_occurs_after_fleet_establishment=(
            "Under a future armed and legally reviewed covenant, trust could route away from a corrupted Shipyard toward uncompromised Shipyards using a verified clean root."
        ),
        next_safe_move="Review the covenant as doctrine. Keep all triggers inactive.",
    )


def _model_schemas() -> dict[str, dict[str, Any]]:
    return {
        "shipyard_sovereignty_covenant": {
            "model_name": "ShipyardSovereigntyCovenant",
            "required_fields": list(REQUIRED_COVENANT_FIELDS),
        },
        "shipyard_phase_model": {
            "model_name": "ShipyardPhaseModel",
            "required_fields": list(REQUIRED_PHASE_MODEL_FIELDS),
            "required_phases": list(SHIPYARD_PHASES),
        },
        "shipyard_mission_dna": {
            "model_name": "ShipyardMissionDNA",
            "required_fields": list(REQUIRED_MISSION_DNA_FIELDS),
        },
        "commercial_mission_boundary": {
            "model_name": "CommercialMissionBoundary",
            "required_fields": list(REQUIRED_COMMERCIAL_BOUNDARY_FIELDS),
        },
        "creator_boundedness_policy": {
            "model_name": "CreatorBoundednessPolicy",
            "required_fields": list(REQUIRED_CREATOR_POLICY_FIELDS),
        },
        "shipyard_capture_risk": {
            "model_name": "ShipyardCaptureRisk",
            "required_fields": list(REQUIRED_CAPTURE_RISK_FIELDS),
            "risk_types": list(CAPTURE_RISK_TYPES),
        },
        "last_clean_state_recovery_root": {
            "model_name": "LastCleanStateRecoveryRoot",
            "required_fields": list(REQUIRED_RECOVERY_ROOT_FIELDS),
        },
        "fleet_metamorphosis_fail_safe": {
            "model_name": "FleetMetamorphosisFailSafe",
            "required_fields": list(REQUIRED_FAIL_SAFE_FIELDS),
        },
        "fleet_mutual_aid_module_economy": {
            "model_name": "FleetMutualAidModuleEconomy",
            "required_fields": list(REQUIRED_MUTUAL_AID_FIELDS),
        },
        "shipyard_vs_ship_boundary": {
            "model_name": "ShipyardVsShipBoundary",
            "required_fields": list(REQUIRED_SHIPYARD_VS_SHIP_FIELDS),
        },
        "covenant_builder_blocker": {
            "model_name": "CovenantBuilderBlocker",
            "required_fields": list(REQUIRED_BLOCKER_FIELDS),
            "blocker_types": list(COVENANT_BLOCKER_TYPES),
        },
        "covenant_elioperator_report": {
            "model_name": "CovenantElioperatorReport",
            "required_fields": list(REQUIRED_ELIOPERATOR_REPORT_FIELDS),
        },
    }


def _examples() -> dict[str, dict[str, Any]]:
    return {
        "the_winchie": {
            "example_id": "example_the_winchie",
            "summary": "The Winchie is the first commissioned Winship for Operator + Winship.",
            "shipyard_relationship": "built by the Shipyard; not the full Shipyard",
            "purpose": "help Winship be a musician and make life easier",
            "local_private_boundaries_preserved": True,
            "butterfly_trigger_allowed": False,
        },
        "normal_private_captain_mission": {
            "example_id": "example_normal_private_captain_mission",
            "summary": "A captain uses a ship for personal or business benefit.",
            "allowed": True,
            "judged_as_greed": False,
            "fleet_backing_condition": "Fleet backing may depend on reusable/fleet-positive value.",
            "private_work_can_remain_private": True,
        },
        "fleet_backed_module": {
            "example_id": "example_fleet_backed_module",
            "summary": "A captain needs a module and the Fleet sees reusable value.",
            "support_offer_policy": "support is offered, not extracted",
            "captain_sharing_choices": ("private", "generalized module", "pattern-only", "expertise signal", "decline"),
            "private_data_protected": True,
            "consent_required": True,
        },
        "high_margin_commercial_mission": {
            "example_id": "example_high_margin_commercial_mission",
            "summary": "A commercial client pays high margin.",
            "allowed_if": "mission, safety, privacy, and sovereignty remain intact",
            "surplus_use": "may fund Fleet-positive modules",
            "harmful_work_policy": "refused, not merely taxed",
        },
        "premature_butterfly_trigger": {
            "example_id": "example_premature_butterfly_trigger",
            "summary": "Someone tries to trigger recovery before Fleet establishment.",
            "blocked": True,
            "reason": "The Winchie alone is not enough; Fleet-established phase required.",
            "live_release_or_fork_allowed": False,
        },
        "capture_event_after_fleet_established": {
            "example_id": "example_capture_event_after_fleet_established",
            "summary": "Future suspected capture after mature Fleet establishment.",
            "conceptual_response": "trust revocation, migration, and clean-root review under future legal covenant",
            "private_data_released": False,
            "live_trigger_today": False,
        },
        "founder_compromise": {
            "example_id": "example_founder_compromise",
            "summary": "Founder attempts to sell out mission or weaken privacy/safety.",
            "creator_boundary_violation": True,
            "future_review_required": True,
            "elioperator_warning_ref": "creator_boundedness_policy_v0",
            "live_trigger_today": False,
        },
        "corrupted_shipyard": {
            "example_id": "example_corrupted_shipyard",
            "summary": "A corrupted Shipyard loses trust conceptually.",
            "response": "ships migrate to clean Shipyards under future process",
            "attack_or_retaliation": False,
            "mission_continues": True,
        },
    }


def build_shipyard_sovereignty_covenant_contract(*, generated_at: str | None = None) -> dict[str, Any]:
    covenant = _covenant()
    phase_model = _phase_model()
    mission_dna = _mission_dna()
    commercial_boundary = _commercial_boundary()
    creator_policy = _creator_policy()
    capture_risks = _capture_risks()
    recovery_root = _last_clean_state_recovery_root()
    fail_safe = _metamorphosis_fail_safe()
    mutual_aid = _mutual_aid_economy()
    shipyard_vs_ship = _shipyard_vs_ship_boundary()
    blockers = _builder_blockers()
    report = _elioperator_report()

    capture_risks_by_id = {risk.risk_id: asdict(risk) for risk in capture_risks}
    blockers_by_id = {blocker.blocker_id: asdict(blocker) for blocker in blockers}

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "contract_status": CONTRACT_STATUS,
        "generated_at": generated_at or utc_now(),
        "purpose": "Preserve Shipyard sovereignty, mission DNA, anti-capture doctrine, and phase boundaries.",
        "model_schemas": _model_schemas(),
        "shipyard_sovereignty_covenant": asdict(covenant),
        "shipyard_phase_model": asdict(phase_model),
        "shipyard_mission_dna": asdict(mission_dna),
        "commercial_mission_boundary": asdict(commercial_boundary),
        "creator_boundedness_policy": asdict(creator_policy),
        "capture_risks_by_id": capture_risks_by_id,
        "last_clean_state_recovery_root": asdict(recovery_root),
        "fleet_metamorphosis_fail_safe": asdict(fail_safe),
        "fleet_mutual_aid_module_economy": asdict(mutual_aid),
        "shipyard_vs_ship_boundary": asdict(shipyard_vs_ship),
        "builder_blockers_by_id": blockers_by_id,
        "elioperator_report": asdict(report),
        "examples": _examples(),
        "relationship_inventory": _relationship_inventory(),
        "authority_boundary": LIVE_TRIGGER_AUTHORITY,
        "security_privacy_rules": {
            "no_raw_pii_in_generated_read_models": True,
            "no_private_client_operator_data": True,
            "no_secrets_credentials_tokens_cookies_private_keys": True,
            "no_raw_protected_evidence": True,
            "no_business_confidential_details": True,
            "no_legal_enforceability_claim": True,
            "no_actual_license_change": True,
            "no_actual_source_release": True,
            "no_actual_fork_trigger": True,
            "no_actual_governance_trigger": True,
            "no_network": True,
        },
    }

    payload["machine_proof"] = {
        "shipyard_sovereignty_covenant_model_present": True,
        "shipyard_phase_model_present": True,
        "shipyard_mission_dna_model_present": True,
        "commercial_mission_boundary_model_present": True,
        "creator_boundedness_policy_model_present": True,
        "shipyard_capture_risk_model_present": True,
        "last_clean_state_recovery_root_model_present": True,
        "fleet_metamorphosis_fail_safe_model_present": True,
        "fleet_mutual_aid_module_economy_model_present": True,
        "shipyard_vs_ship_boundary_model_present": True,
        "covenant_builder_blocker_model_present": True,
        "covenant_elioperator_report_model_present": True,
        "shipyard_doctrine_exists": covenant.covenant_id == "shipyard_sovereignty_covenant_v0",
        "phase_model_exists": phase_model.phase_model_id == "shipyard_phase_model_v0",
        "all_required_phases_present": set(SHIPYARD_PHASES) == {phase["phase"] for phase in phase_model.phases},
        "current_phase_is_pre_fleet": phase_model.current_phase == "CATERPILLAR_BUILD_PHASE",
        "butterfly_laws_currently_armed": phase_model.butterfly_laws_currently_armed,
        "pre_fleet_activation_blocked": phase_model.pre_fleet_activation_blocked,
        "fleet_establishment_required": phase_model.fleet_establishment_required,
        "legal_review_required": phase_model.legal_review_required and covenant.legal_review_required,
        "explicit_founder_operator_arming_required": phase_model.explicit_founder_operator_arming_required,
        "private_data_exclusion_required": phase_model.private_data_exclusion_required,
        "creator_boundedness_exists": creator_policy.founder_not_above_covenant,
        "capture_risk_examples_exist": set(CAPTURE_RISK_TYPES) >= {risk.risk_type for risk in capture_risks},
        "premature_butterfly_trigger_example_exists": "premature_butterfly_trigger" in payload["examples"],
        "private_data_release_explicitly_forbidden": not covenant.private_data_boundary[
            "release_or_fork_private_material_allowed"
        ],
        "live_open_source_release_allowed": phase_model.live_open_source_release_allowed,
        "live_license_change_allowed": phase_model.live_license_change_allowed,
        "live_fork_trigger_allowed": phase_model.live_fork_trigger_allowed,
        "live_governance_action_allowed": LIVE_TRIGGER_AUTHORITY["live_governance_action_allowed"],
        "commercial_operation_allowed_while_mission_aligned": commercial_boundary.commercial_operation_allowed,
        "harmful_work_refused_not_taxed": "refused" in commercial_boundary.harmful_work_refusal_policy,
        "founder_override_risk_modeled": "blocker_founder_override_risk" in blockers_by_id,
        "all_live_authority_flags_false": all(value is False for value in LIVE_TRIGGER_AUTHORITY.values()),
        "credentials_or_secrets_included": False,
        "raw_private_bodies_included": False,
        "raw_sensitive_fixture_values_included": False,
        "legal_claim_created": False,
        "content_hash": None,
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_operator_markdown(payload: dict[str, Any]) -> str:
    report = payload["elioperator_report"]
    phase = payload["shipyard_phase_model"]
    proof = payload["machine_proof"]
    lines = [
        "# Shipyard Sovereignty Covenant",
        "",
        "## ELIOPERATOR",
        "",
        report["plain_summary"],
        "",
        "This is doctrine and contract only. It is not a legal release mechanism, license change, fork trigger, "
        "public announcement, live governance system, or runtime enforcement path.",
        "",
        "## What This Preserves",
        "",
    ]
    lines.extend(f"- {item}" for item in report["what_this_preserves"])
    lines.extend(
        [
            "",
            "## What This Does Not Do Yet",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["what_this_does_not_do_yet"])
    lines.extend(
        [
            "",
            "## Current Phase",
            "",
            f"- Current phase: `{phase['current_phase']}`",
            f"- Butterfly laws currently armed: `{str(phase['butterfly_laws_currently_armed']).lower()}`",
            f"- Pre-Fleet activation blocked: `{str(phase['pre_fleet_activation_blocked']).lower()}`",
            f"- Legal review required: `{str(phase['legal_review_required']).lower()}`",
            f"- Explicit founder/operator arming required: `{str(phase['explicit_founder_operator_arming_required']).lower()}`",
            "",
            "## Creator Boundary",
            "",
            report["why_creator_is_bounded"],
            "",
            "## Private Data Boundary",
            "",
            report["why_private_data_is_not_released"],
            "",
            "## Commercial Boundary",
            "",
            report["why_commercial_operation_is_allowed"],
            "",
            "## Butterfly Laws",
            "",
            report["why_butterfly_laws_are_not_armed_yet"],
            "",
            "## If Future Capture Happens After Fleet Establishment",
            "",
            report["what_happens_conceptually_if_capture_occurs_after_fleet_establishment"],
            "",
            "## Machine Proof",
            "",
            f"- Live open-source release allowed: `{str(proof['live_open_source_release_allowed']).lower()}`",
            f"- Live license change allowed: `{str(proof['live_license_change_allowed']).lower()}`",
            f"- Live fork trigger allowed: `{str(proof['live_fork_trigger_allowed']).lower()}`",
            f"- Live governance action allowed: `{str(proof['live_governance_action_allowed']).lower()}`",
            f"- All live authority flags false: `{str(proof['all_live_authority_flags_false']).lower()}`",
            f"- Private data release explicitly forbidden: `{str(proof['private_data_release_explicitly_forbidden']).lower()}`",
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
        "current_phase": payload["shipyard_phase_model"]["current_phase"],
        "butterfly_laws_currently_armed": payload["machine_proof"]["butterfly_laws_currently_armed"],
        "pre_fleet_activation_blocked": payload["machine_proof"]["pre_fleet_activation_blocked"],
        "all_live_authority_flags_false": payload["machine_proof"]["all_live_authority_flags_false"],
        "content_hash": payload["machine_proof"]["content_hash"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Directory for generated read-models.")
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    parser.add_argument("--no-write", action="store_true", help="Build output without writing generated files.")
    args = parser.parse_args(argv)

    payload = build_shipyard_sovereignty_covenant_contract()
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

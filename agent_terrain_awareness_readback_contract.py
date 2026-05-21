"""Agent Terrain Awareness Readback Contract v0 for OpenClaw.

This read-model inventories what OpenClaw currently knows, partly knows, knows
it does not know, has not discovered, and needs Winship memory comparison for
across major agent/persona and system-loop lanes. It is deterministic metadata
only: no model calls, agent activation, tool execution, browser/OAuth/account
access, Gmail/calendar/Coupa/Telegram access, credentials, Repo B execution,
planner/builder loops, queue/autonomy, broad private scans, Mac sync, or PC
system-drive writes are created.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

SCHEMA_VERSION = "agent_terrain_awareness_readback_contract_v0"
JSON_EXPORT_NAME = "agent_terrain_awareness_readback_contract.json"
OPERATOR_EXPORT_NAME = "agent_terrain_awareness_readback_contract_OPERATOR.md"

NO_AUTHORITY_FLAGS = {
    "runtime_authority": False,
    "model_call_authority": False,
    "model_api_execution_authority": False,
    "actor_agent_activation_authority": False,
    "tool_execution_authority": False,
    "browser_oauth_account_access_enabled": False,
    "gmail_calendar_coupa_telegram_enabled": False,
    "credential_authority": False,
    "send_submit_approval_enabled": False,
    "runtime_daemon_enabled": False,
    "planner_builder_execution_enabled": False,
    "queue_autonomy_execution_enabled": False,
    "hidden_model_routing_enabled": False,
    "hidden_memory_capture_enabled": False,
    "external_retained_memory_enabled": False,
    "raw_private_body_ingestion_enabled": False,
    "vector_memory_expansion_enabled": False,
    "broad_filesystem_indexing_enabled": False,
    "broad_private_file_inspection_enabled": False,
    "repo_b_mutation_enabled": False,
    "repo_b_body_inspection_enabled": False,
    "mission_control_app_authority_added": False,
    "mac_sync_or_import_triggered": False,
    "network_operation_enabled": False,
    "pc_c_drive_artifact_write_allowed": False,
    "authority_escalation_allowed": False,
    "operator_final_authority": True,
}

REQUIRED_LANE_IDS = (
    "chief",
    "chief_test_harness",
    "hermes",
    "cassandra",
    "guardian",
    "niles",
    "struna",
    "agentic_loop",
    "cue_parser_brain_dump_parser",
    "repo_b_leftovers",
    "planner_builder_orchestrator_loop",
    "model_router",
    "tool_plugin_registry",
    "package_compiler",
    "capital_hilton",
    "future_domain_workflow_lanes",
)

READINESS_STATES = (
    "READY_FOR_SECURITY_AUDIT",
    "NEEDS_PROOF",
    "NEEDS_CONTEXT",
    "NEEDS_DISCOVERY_CLASSIFICATION",
    "PARKED_WITH_PROOF",
    "BLOCKED_NOT_AUTHORIZED",
    "UNKNOWN_FAIL_CLOSED",
    "FUTURE_GATED",
)

CONFIDENCE_STATES = (
    "FULL_TRUST_DISPLAY_QUIET",
    "HIGH_TRUST",
    "MEDIUM_TRUST",
    "LOW_TRUST",
    "CONTEXT_ONLY",
    "UNKNOWN_FAIL_CLOSED",
)

LANE_DESTINY_ROUTES = (
    "QUIET_BACKEND_RESOLVED",
    "MOVE_TO_WORLD_ACTION",
    "PARK_WITH_PROOF",
    "HOLDING_CELL",
    "SECURITY_AUDIT_REQUIRED",
    "POST_SECURITY_AUTONOMY_CANDIDATE",
    "REQUEUE_FOR_SYSTEM_BUILD",
)

OPERATOR_QUESTION_TYPES = (
    "memory_only_clarification",
    "proof_needed",
    "repo_discovery_needed",
    "package_contract_needed",
    "security_gate_needed",
    "world_transition_needed",
)

MATRIX_COLUMNS = (
    "current_status",
    "confidence",
    "known",
    "partly_known",
    "known_unknown",
    "not_discovered",
    "operator_memory_needed",
    "machine_proof_needed",
    "safe_next_detour",
    "lane_destiny",
    "quiet_condition",
)


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    path: str
    role: str


@dataclass(frozen=True)
class OperatorQuestion:
    question_id: str
    prompt: str
    classification: str


@dataclass(frozen=True)
class TerrainLane:
    lane_id: str
    display_name: str
    current_status: str
    confidence_state: str
    readiness_state: str
    known: tuple[str, ...]
    partly_known: tuple[str, ...]
    known_unknown: tuple[str, ...]
    not_discovered: tuple[str, ...]
    needs_operator_memory_comparison: tuple[str, ...]
    missing_machine_proof: tuple[str, ...]
    blocked_authorities: tuple[str, ...]
    safe_next_detour: str
    package_preview_available: bool
    current_authority_boundary: str
    future_gated_actions: tuple[str, ...]
    resolution_route: str
    target_world: str | None
    proof_refs: tuple[str, ...]
    memory_candidates_needed: tuple[str, ...]
    what_makes_quiet: str
    recommended_operator_questions: tuple[OperatorQuestion, ...]
    operator_reported_only: bool = False
    machine_proven: bool = True


@dataclass(frozen=True)
class RecommendedLane:
    lane_id: str
    title: str
    priority: str
    why_next: str
    hard_boundary: str


@dataclass(frozen=True)
class TerrainAwarenessExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    lane_count: int
    operator_question_count: int
    runtime_authority_added: bool
    repo_b_mutation_added: bool


EVIDENCE_SOURCES = (
    EvidenceSource(
        "operator_awareness_agent_package_spine",
        "generated/read_models/operator_awareness_agent_package_spine.json",
        "source for known/partly-known/unknown awareness gaps",
    ),
    EvidenceSource(
        "operator_nested_lane_mission_package_spine",
        "generated/read_models/operator_nested_lane_mission_package_spine.json",
        "source for nested lane posture and package/detail boundaries",
    ),
    EvidenceSource(
        "agent_platform_alignment",
        "generated/read_models/agent_platform_alignment.json",
        "agent-platform primitive alignment",
    ),
    EvidenceSource(
        "agent_identity_actor_router_contract",
        "generated/read_models/agent_identity_actor_router_contract.json",
        "actor identity and routing boundaries",
    ),
    EvidenceSource(
        "model_selection_policy_contract",
        "generated/read_models/model_selection_policy_contract.json",
        "model class and sensitivity policy",
    ),
    EvidenceSource(
        "agent_package_preview_contract",
        "generated/read_models/agent_package_preview_contract.json",
        "package preview grammar",
    ),
    EvidenceSource(
        "agent_memory_scope_contract",
        "generated/read_models/agent_memory_scope_contract.json",
        "memory visibility and writeback boundaries",
    ),
    EvidenceSource(
        "tool_protocol_adapter_registry_contract",
        "generated/read_models/tool_protocol_adapter_registry_contract.json",
        "tool/protocol adapter posture",
    ),
    EvidenceSource(
        "memory_candidate_receipt_contract",
        "generated/read_models/memory_candidate_receipt_contract.json",
        "memory candidate receipt grammar",
    ),
    EvidenceSource(
        "model_selection_receipt_contract",
        "generated/read_models/model_selection_receipt_contract.json",
        "model-selection decision receipt grammar",
    ),
    EvidenceSource(
        "package_compiler_contract",
        "generated/read_models/package_compiler_contract.json",
        "deterministic package compiler boundary",
    ),
    EvidenceSource(
        "operator_threshold_map_contract",
        "generated/read_models/operator_threshold_map_contract.json",
        "threshold map and lane destiny",
    ),
    EvidenceSource(
        "operator_map_bundle_contract",
        "generated/read_models/operator_map_bundle_contract.json",
        "stable map bundle contract if present in dirty map lane",
    ),
    EvidenceSource(
        "chief_check_engine_diagnostic_package",
        "generated/read_models/chief_check_engine_diagnostic_package.json",
        "Chief diagnostic package posture",
    ),
    EvidenceSource(
        "chief_check_engine_environment_posture",
        "generated/read_models/chief_check_engine_environment_posture.json",
        "Chief environment posture",
    ),
    EvidenceSource(
        "cassandra_email_calendar_delta_detangle",
        "generated/read_models/cassandra_email_calendar_delta_detangle.json",
        "Cassandra communications/calendar context boundary",
    ),
    EvidenceSource(
        "guardian_protected_access_gate_spec",
        "generated/read_models/guardian_protected_access_gate_spec.json",
        "Guardian protected-access gate",
    ),
    EvidenceSource(
        "niles_album_metadata_intake_packet",
        "generated/read_models/niles_album_metadata_intake_packet.json",
        "Niles music/art metadata intake",
    ),
    EvidenceSource(
        "struna_obscura_project_capsule",
        "generated/read_models/struna_obscura_project_capsule.json",
        "Struna project capsule",
    ),
    EvidenceSource(
        "capital_hilton_actionable_review_packet",
        "generated/read_models/capital_hilton_actionable_review_packet.json",
        "Capital Hilton review packet",
    ),
    EvidenceSource(
        "capital_hilton_external_artifact_proof_capture",
        "generated/read_models/capital_hilton_external_artifact_proof_capture.json",
        "Capital Hilton proof metadata posture",
    ),
)


def _q(question_id: str, prompt: str, classification: str) -> OperatorQuestion:
    if classification not in OPERATOR_QUESTION_TYPES:
        raise ValueError(f"unknown question classification: {classification}")
    return OperatorQuestion(question_id, prompt, classification)


TERRAIN_LANES = (
    TerrainLane(
        "chief",
        "Chief",
        "diagnostic_readback_persona_partly_mapped",
        "MEDIUM_TRUST",
        "NEEDS_DISCOVERY_CLASSIFICATION",
        (
            "Chief is represented as a coordinator/diagnostic/work-board/check-engine character in current contracts.",
            "Chief can be routed in package previews as a character/persona, not as a live backend authority.",
            "Chief-related read-models exist for check-engine diagnostic and environment posture.",
        ),
        (
            "Chief can organize diagnostic posture and work-board metadata.",
            "Chief package shape is implied by package compiler and actor router contracts.",
        ),
        (
            "Whether any remembered Chief system-wide fix/run rail exists outside current read-model visibility.",
            "Which Chief outputs should be test-harness evidence versus operator-facing briefing.",
        ),
        (
            "Complete inventory of Chief-owned artifacts and exact harness inputs/outputs.",
            "Executable Chief runtime authority proof, which is intentionally absent now.",
        ),
        (
            "What Chief actually owns today versus what Chief used to own in older work.",
            "Whether Chief is supposed to send work to a parser or only classify it.",
        ),
        (
            "Named Chief package schema for diagnostic/test harness use.",
            "Receipts proving any Chief harness result, if such a harness exists.",
        ),
        (
            "live Chief activation",
            "service starts",
            "model calls",
            "tool execution",
            "repair/remount/cleanup",
            "Telegram/send actions",
        ),
        "Chief Test Harness Capability Classification",
        True,
        "Chief can be a package character/persona and readback lane only; no live backend/app authority.",
        ("future Chief test harness receipts", "future package routing", "post-security diagnostics"),
        "SECURITY_AUDIT_REQUIRED",
        None,
        (
            "generated/read_models/agent_identity_actor_router_contract.json",
            "generated/read_models/chief_check_engine_diagnostic_package.json",
            "generated/read_models/chief_check_engine_environment_posture.json",
            "generated/read_models/operator_awareness_agent_package_spine.json",
        ),
        (
            "Chief harness purpose",
            "Chief output receipt shape",
            "Chief non-execution boundary note",
        ),
        "Chief is quiet when character, package, harness, and blocked execution boundaries are classified and receipted.",
        (
            _q("chief_001", "What do you remember Chief actually owning: work-board posture, test harness, parser input, or runtime repair?", "memory_only_clarification"),
            _q("chief_002", "Which Chief output should count as proof rather than a briefing?", "proof_needed"),
            _q("chief_003", "Did Chief ever have a safe test harness, and where was it represented?", "repo_discovery_needed"),
            _q("chief_004", "What package fields would Chief need before it can review a lane?", "package_contract_needed"),
        ),
    ),
    TerrainLane(
        "chief_test_harness",
        "Chief Test Harness",
        "remembered_or_partial_harness_needs_classification",
        "LOW_TRUST",
        "NEEDS_DISCOVERY_CLASSIFICATION",
        (
            "Current awareness surfaces explicitly name Chief test harness as a discovery/classification gap.",
            "A harness may be tests, fixtures, status proof, or runtime validation; those are materially different.",
        ),
        (
            "A non-live harness could fit the package/compiler and receipt spine.",
            "Chief could evaluate outputs only after receipts and boundaries exist.",
        ),
        (
            "The system does not know whether the harness lived in Repo A, Repo B, or another workspace.",
            "The system does not know its pass/fail receipt grammar.",
        ),
        (
            "Harness source metadata, fixture names, expected inputs, expected outputs, and safe command class.",
        ),
        (
            "What outcome the remembered harness was meant to prove.",
            "Whether it should be classified as unit tests, synthetic receipts, or blocked runtime behavior.",
        ),
        (
            "Approved metadata pointing to harness source without broad Repo B inspection.",
            "Receipt schema for harness result claims.",
        ),
        (
            "importing Chief runtime modules",
            "running services",
            "calling models",
            "running planner/builder loops",
            "executing Repo B",
        ),
        "Chief Test Harness Capability Classification",
        False,
        "Classification/read-model only until a safe harness contract is created.",
        ("future deterministic harness tests", "future receipt validation", "post-security runtime validation if ever approved"),
        "HOLDING_CELL",
        None,
        (
            "generated/read_models/operator_awareness_agent_package_spine.json",
            "generated/read_models/operator_nested_lane_mission_package_spine.json",
        ),
        ("harness metadata candidate", "harness receipt candidate", "source location memory candidate"),
        "The harness lane is quiet when it is classified as deterministic tests, parked, obsolete, or blocked with proof.",
        (
            _q("chief_harness_001", "What do you remember Chief's test harness actually doing?", "memory_only_clarification"),
            _q("chief_harness_002", "Where did the harness live: Repo A, Repo B, Mac app, or another workspace?", "repo_discovery_needed"),
            _q("chief_harness_003", "What receipt would prove the harness passed?", "proof_needed"),
            _q("chief_harness_004", "Should this be a package contract or only a test fixture?", "package_contract_needed"),
        ),
        operator_reported_only=True,
        machine_proven=False,
    ),
    TerrainLane(
        "hermes",
        "Hermes",
        "architecture_doctrine_advisory_role_needs_memory_proof_review",
        "LOW_TRUST",
        "NEEDS_CONTEXT",
        (
            "Hermes is represented in actor-router and package-preview contracts as architecture/doctrine/system-coherence advisory character.",
            "Hermes has no current live agent or model authority.",
        ),
        (
            "Hermes can be paired with Chief for big-picture doctrine and system coherence.",
            "Hermes package preview exists as a non-executing architecture review example.",
        ),
        (
            "Current Hermes source set and responsibility boundary are not fully proven.",
            "Whether Hermes owns horizon checks, doctrine review, or another concrete workflow needs comparison.",
        ),
        (
            "Hermes-specific status rail, receipts, or source inventory.",
        ),
        (
            "What Hermes actually owns today.",
            "Whether there are prior Hermes notes/source artifacts that should become memory candidates.",
        ),
        (
            "Hermes source/read-model refs if they exist.",
            "Accepted Hermes responsibility contract.",
        ),
        (
            "live advisory agent activation",
            "external research",
            "model/API calls",
            "tool execution",
            "architecture authority without operator review",
        ),
        "Hermes Status Memory/Proof Review",
        True,
        "Hermes can appear in package previews and terrain readback only; no live agent/model/tool authority.",
        ("future advisory package", "future doctrine review receipt", "future horizon-check packet"),
        "PARK_WITH_PROOF",
        None,
        (
            "generated/read_models/agent_identity_actor_router_contract.json",
            "generated/read_models/agent_package_preview_contract.json",
            "generated/read_models/operator_nested_lane_mission_package_spine.json",
        ),
        ("Hermes responsibility memory candidate", "Hermes source-reference candidate"),
        "Hermes is quiet when classified as tracked, parked, obsolete, blocked, or backed by source proof.",
        (
            _q("hermes_001", "What does Hermes actually own today: architecture, doctrine, coherence, horizon checks, or another lane?", "memory_only_clarification"),
            _q("hermes_002", "What source artifact should prove Hermes' current role?", "proof_needed"),
            _q("hermes_003", "Should Hermes be paired with Chief by default for system-coherence review?", "package_contract_needed"),
            _q("hermes_004", "Which remembered Hermes notes should be compared against current read-models?", "memory_only_clarification"),
        ),
    ),
    TerrainLane(
        "cassandra",
        "Cassandra",
        "finance_comms_review_persona_metadata_only_now",
        "MEDIUM_TRUST",
        "NEEDS_PROOF",
        (
            "Cassandra is represented as communications, finance/AP, email/calendar review character.",
            "Capital Hilton relates to Cassandra as protected finance/AP workflow context.",
            "Cassandra can receive package previews but no live account or send authority.",
        ),
        (
            "Cassandra can reason over governed metadata/proof references later.",
            "Email/calendar/draft identity and finance proof rails are partly represented.",
        ),
        (
            "The system does not know live Coupa, Gmail, calendar, or Excel facts.",
            "Which exact source of truth matters for Capital Hilton remains proof-gated.",
        ),
        (
            "Protected proof metadata for Coupa/Excel/invoice source.",
            "Safe source cards for finance/comms context.",
        ),
        (
            "Whether Capital Hilton source truth is Coupa, email, Excel, or protected proof packets.",
            "Which Cassandra workflows should be moved into Finance or Communications worlds after security.",
        ),
        (
            "Coupa/Excel protected metadata receipts.",
            "Cassandra package receipt and protected-access gate result.",
        ),
        (
            "Coupa access",
            "Gmail/calendar access",
            "OAuth/browser/account flows",
            "send/submit/approval",
            "raw private bodies",
            "credential handling",
        ),
        "Capital Hilton Protected Proof Metadata Population",
        True,
        "Cassandra is package-preview/proof-reference only; live finance/comms/account authority is blocked.",
        ("future protected metadata review", "future local/private model review", "future Finance World package"),
        "SECURITY_AUDIT_REQUIRED",
        "Finance",
        (
            "generated/read_models/cassandra_email_calendar_delta_detangle.json",
            "generated/read_models/agent_package_preview_contract.json",
            "generated/read_models/tool_protocol_adapter_registry_contract.json",
            "generated/read_models/operator_threshold_map_contract.json",
        ),
        ("Capital Hilton proof metadata candidate", "Cassandra source-truth context candidate"),
        "Cassandra is quiet when each finance/comms workflow has proof refs, memory gaps, or explicit blockers.",
        (
            _q("cassandra_001", "What is Cassandra's current source of truth for Capital Hilton: Coupa, email, Excel, or protected proof packets?", "memory_only_clarification"),
            _q("cassandra_002", "What metadata could prove the invoice source without exposing raw finance bodies?", "proof_needed"),
            _q("cassandra_003", "Which Cassandra workflow belongs in Finance World versus Communications World?", "world_transition_needed"),
            _q("cassandra_004", "What Guardian gate should be required before any protected context is routed?", "security_gate_needed"),
        ),
    ),
    TerrainLane(
        "guardian",
        "Guardian",
        "boundary_security_gate_persona_known_metadata_only",
        "HIGH_TRUST",
        "READY_FOR_SECURITY_AUDIT",
        (
            "Guardian is represented as safety/security/protected-access boundary character.",
            "Guardian may recommend block/redact/quarantine/revoke in contracts.",
            "Guardian cannot self-authorize or bypass the Operator.",
        ),
        (
            "Exact per-lane future receipt requirements still need refinement.",
        ),
        (
            "No generic approval, credential, account, or protected access authority exists.",
        ),
        (),
        (
            "Whether any remembered Guardian rules are missing from current contracts.",
        ),
        (
            "Future lane-specific Guardian gate receipt shape.",
        ),
        (
            "self-authorization",
            "approval bypass",
            "credential access",
            "protected raw body access",
            "send/submit authority",
        ),
        "Guardian Gate Receipt Definition when a protected lane requests it",
        True,
        "Guardian is a gate/review character only; no execution or self-grant authority.",
        ("future protected access gate receipts", "future revocation/kill-switch receipts"),
        "PARK_WITH_PROOF",
        None,
        (
            "generated/read_models/guardian_protected_access_gate_spec.json",
            "generated/read_models/agent_identity_actor_router_contract.json",
            "generated/read_models/agent_memory_scope_contract.json",
        ),
        ("missing Guardian rule candidate", "protected lane gate candidate"),
        "Guardian is quiet unless a lane tries to cross an authority boundary or needs clearance classification.",
        (
            _q("guardian_001", "Which Guardian rule, if any, is missing from the current contracts?", "memory_only_clarification"),
            _q("guardian_002", "What receipt should prove a protected-access gate was checked?", "proof_needed"),
            _q("guardian_003", "Which lanes should require Guardian before operator approval?", "security_gate_needed"),
        ),
    ),
    TerrainLane(
        "niles",
        "Niles",
        "music_art_creative_persona_partly_mapped",
        "MEDIUM_TRUST",
        "NEEDS_CONTEXT",
        (
            "Niles is represented as music/art/producer/creative operator character.",
            "Niles/Struna context can be package-previewed through scoped project capsules/metadata refs.",
        ),
        (
            "The system can hold creative metadata, but real current album/project metadata is not fully verified.",
            "Operator creative preference can guide work but is context, not proof.",
        ),
        (
            "Canonical current Struna/album/release/personnel/artifact status is not fully proven here.",
        ),
        (
            "Current music/art metadata set and source references.",
            "Rights/release/platform action boundaries for future work.",
        ),
        (
            "What Niles should know about Struna today versus what exists only in Winship memory.",
        ),
        (
            "Niles/Struna source card or project capsule receipt.",
            "Accepted creative metadata candidate receipt.",
        ),
        (
            "broad private archive ingestion",
            "audio automation",
            "public release/platform actions",
            "external account actions",
            "raw unrelated private material",
        ),
        "Niles Real Album Metadata Intake",
        True,
        "Niles can receive scoped creative/package refs only; no broad archive ingestion or release authority.",
        ("future Music/Art World package", "future creative metadata receipt", "future release action gate"),
        "MOVE_TO_WORLD_ACTION",
        "Music / Art",
        (
            "generated/read_models/agent_identity_actor_router_contract.json",
            "generated/read_models/agent_memory_scope_contract.json",
            "generated/read_models/niles_album_metadata_intake_packet.json",
        ),
        ("Niles creative context candidate", "album metadata candidate", "operator preference candidate"),
        "Niles is quiet when current creative metadata is captured, marked stale/private, or explicitly blocked.",
        (
            _q("niles_001", "What does Niles know about Struna now versus what exists only in your memory?", "memory_only_clarification"),
            _q("niles_002", "Which album/project metadata should become source-backed first?", "proof_needed"),
            _q("niles_003", "Which creative context is safe for package preview without broad archive ingestion?", "package_contract_needed"),
            _q("niles_004", "When should this move from helm terrain to Music/Art World action?", "world_transition_needed"),
        ),
    ),
    TerrainLane(
        "struna",
        "Struna",
        "creative_project_lane_context_needed",
        "LOW_TRUST",
        "NEEDS_CONTEXT",
        (
            "Struna appears as a music/art project capsule/source reference in current awareness surfaces.",
            "Struna belongs under Niles/Music-Art world posture, not generic helm clutter.",
        ),
        (
            "Struna can be represented as project metadata, capsule refs, and creative preference candidates.",
        ),
        (
            "Current canonical Struna metadata, artifact state, and next work target are not fully proven.",
        ),
        (
            "Current project capsule completeness.",
            "Which source refs are current versus stale.",
        ),
        (
            "What Struna facts Winship remembers should be candidates, not proof.",
        ),
        (
            "Struna project capsule receipt.",
            "Current artifact/metadata source refs.",
        ),
        (
            "raw creative archive scan",
            "public platform/release action",
            "external account mutation",
            "unrelated private material ingestion",
        ),
        "Struna Project Capsule Memory/Proof Review",
        True,
        "Struna is creative metadata/context only until scoped sources and package boundaries exist.",
        ("future Music/Art World action", "future Niles package", "future release gate"),
        "MOVE_TO_WORLD_ACTION",
        "Music / Art",
        (
            "generated/read_models/struna_obscura_project_capsule.json",
            "generated/read_models/niles_album_metadata_intake_packet.json",
        ),
        ("Struna project fact candidate", "Struna creative preference candidate"),
        "Struna is quiet when current project context is captured as metadata or intentionally parked.",
        (
            _q("struna_001", "What is the current Struna source of truth: project capsule, files, memory, or another artifact?", "memory_only_clarification"),
            _q("struna_002", "Which Struna metadata needs machine proof before Niles can use it?", "proof_needed"),
            _q("struna_003", "What should remain parked until Music/Art World is ready?", "world_transition_needed"),
        ),
    ),
    TerrainLane(
        "agentic_loop",
        "Agentic Loop",
        "operator_reported_architecture_candidate_not_machine_proven",
        "UNKNOWN_FAIL_CLOSED",
        "NEEDS_DISCOVERY_CLASSIFICATION",
        (
            "Operator reports a possible agentic planner/builder/orchestrator loop, parser, queue, holding cell, and Chief harness relationship.",
            "Current contracts classify cue/autonomy/planner-builder as future-gated and post-security.",
        ),
        (
            "The future loop likely relates to package compiler, cue parser, planner, builder, orchestrator, and receipts.",
            "Some parsed work may eventually queue, while other items should go to holding cell.",
        ),
        (
            "Repo A does not currently have machine proof that this loop is safe, current, or executable.",
            "The system does not know which parts live in Repo B, Repo A, or memory.",
        ),
        (
            "Approved metadata proving loop components, boundaries, and current status.",
            "Queue lifecycle receipts and failure routing rules.",
        ),
        (
            "Where the planner/builder loop lived.",
            "Which parts are still relevant versus obsolete.",
            "Whether Chief should feed parser inputs for near-term fixes.",
        ),
        (
            "Non-live loop inventory.",
            "Parser/queue/holding-cell contract refs.",
            "Chief harness receipt refs.",
        ),
        (
            "live loop activation",
            "model calls",
            "tool execution",
            "planner/builder runtime",
            "queue/autonomy execution",
            "Repo B execution",
            "repair loops",
        ),
        "Agentic Loop Workflow Classification",
        False,
        "Operator-reported architecture candidate only; no current execution, queue, parser, or agent authority.",
        ("post-security cue/autonomy spine", "future queue lifecycle receipts", "future planner/builder contracts"),
        "POST_SECURITY_AUTONOMY_CANDIDATE",
        None,
        (
            "generated/read_models/operator_awareness_agent_package_spine.json",
            "generated/read_models/operator_threshold_map_contract.json",
            "generated/read_models/tool_protocol_adapter_registry_contract.json",
        ),
        ("agentic loop memory candidate", "planner-builder source metadata candidate", "holding-cell rule candidate"),
        "The agentic loop is quiet when each component is classified as blocked, parked, obsolete, or future-gated with proof refs.",
        (
            _q("agentic_loop_001", "Where did the planner/builder loop live?", "memory_only_clarification"),
            _q("agentic_loop_002", "Which loop parts should queue now later, and which should go to holding cell?", "memory_only_clarification"),
            _q("agentic_loop_003", "What machine proof would confirm the loop components without executing them?", "proof_needed"),
            _q("agentic_loop_004", "Which failure path should return work to queue, orchestrator, planner, or builder?", "package_contract_needed"),
            _q("agentic_loop_005", "What must wait until post-security autonomy?", "security_gate_needed"),
        ),
        operator_reported_only=True,
        machine_proven=False,
    ),
    TerrainLane(
        "cue_parser_brain_dump_parser",
        "Cue Parser / Brain-Dump Parser",
        "parser_concept_needs_non_live_contract",
        "LOW_TRUST",
        "NEEDS_DISCOVERY_CLASSIFICATION",
        (
            "Operator reports a parser that may turn operator/Chief ideas into queued work or holding-cell candidates.",
            "Awareness surfaces name brain-dump/cue parser as a classification gap.",
        ),
        (
            "The parser likely relates to memory candidate receipts, package previews, holding cell, and queue posture.",
        ),
        (
            "The system does not know allowed cue inputs, output grammar, or where the parser lived.",
            "The system does not know how parser output should become memory candidates without becoming proof.",
        ),
        (
            "Cue parser contract, accepted input classes, output receipt shape, and holding-cell trigger rules.",
        ),
        (
            "Was the cue parser in Repo B, Repo A, or a separate workspace?",
            "What kinds of brain dumps should it accept?",
        ),
        (
            "Parser source metadata.",
            "Cue intake receipt schema.",
            "Holding-cell classification rules.",
        ),
        (
            "raw private note scans",
            "LLM parsing",
            "file moves",
            "automatic truth promotion",
            "queue execution",
            "Repo B execution",
        ),
        "Cue Parser Intake Classification",
        False,
        "Cue parser remains capture/preview contract terrain only; no parsing runtime or queue authority.",
        ("future cue parser receipt", "future holding-cell intake", "future package compiler input"),
        "POST_SECURITY_AUTONOMY_CANDIDATE",
        None,
        (
            "generated/read_models/operator_awareness_agent_package_spine.json",
            "generated/read_models/memory_candidate_receipt_contract.json",
            "generated/read_models/agent_package_preview_contract.json",
        ),
        ("cue parser memory candidate", "brain-dump intake policy candidate", "holding-cell marker candidate"),
        "The cue parser is quiet when accepted inputs, blocked inputs, output receipts, and future-gated status are explicit.",
        (
            _q("cue_parser_001", "Was the cue parser in Repo B, Repo A, or a separate workspace?", "memory_only_clarification"),
            _q("cue_parser_002", "What should Tell System What's Missing capture now without executing?", "package_contract_needed"),
            _q("cue_parser_003", "Which brain-dump inputs are safe metadata and which are raw private bodies?", "security_gate_needed"),
            _q("cue_parser_004", "What proof would confirm parser behavior without running it?", "proof_needed"),
        ),
        operator_reported_only=True,
        machine_proven=False,
    ),
    TerrainLane(
        "repo_b_leftovers",
        "Repo B Leftovers",
        "known_unknown_reference_only_no_broad_inspection",
        "UNKNOWN_FAIL_CLOSED",
        "NEEDS_DISCOVERY_CLASSIFICATION",
        (
            "Repo A awareness surfaces represent Repo B leftovers as references needing tagging, parking, blocking, or promotion.",
            "This lane does not inspect Repo B bodies, mutate Repo B, or execute Repo B.",
        ),
        (
            "Some leftover path or concept metadata may already exist in approved read-models.",
        ),
        (
            "Unclassified leftovers are not current Repo A capabilities.",
            "The system does not know which remembered Repo B items still matter.",
        ),
        (
            "Approved metadata list of named leftovers.",
            "Classification of each leftover as parked, blocked, obsolete, or promotion candidate.",
        ),
        (
            "Which named file, concept, or workflow from Repo B should be classified first.",
        ),
        (
            "Approved Repo B metadata only, not raw bodies.",
            "Classification receipt for each leftover.",
        ),
        (
            "Repo B mutation",
            "broad Repo B body inspection",
            "Repo B execution",
            "runtime imports",
            "migration without package/proof",
        ),
        "Repo B Leftover Classification Packet",
        False,
        "Repo B is reference-only; no broad body inspection, mutation, migration, or execution.",
        ("future narrow metadata discovery", "future classification packet", "future parked/blocked/promoted markers"),
        "PARK_WITH_PROOF",
        None,
        (
            "generated/read_models/operator_awareness_agent_package_spine.json",
            "generated/read_models/operator_nested_lane_mission_package_spine.json",
            "generated/read_models/operator_threshold_map_contract.json",
        ),
        ("repo_b_leftover_metadata_candidate", "repo_b_classification_candidate"),
        "Repo B leftovers are quiet when known items are tagged as blocked, parked, obsolete, or promotion candidates.",
        (
            _q("repo_b_001", "Which Repo B leftover do you remember that Mission Control is not showing?", "memory_only_clarification"),
            _q("repo_b_002", "What metadata would identify that leftover without opening broad private bodies?", "repo_discovery_needed"),
            _q("repo_b_003", "Should the leftover be parked, blocked, promoted, or marked obsolete?", "package_contract_needed"),
            _q("repo_b_004", "What proof is needed before Repo A can reference it as current?", "proof_needed"),
        ),
        operator_reported_only=True,
        machine_proven=False,
    ),
    TerrainLane(
        "planner_builder_orchestrator_loop",
        "Planner / Builder / Orchestrator Loop",
        "future_gated_agentic_loop_component",
        "UNKNOWN_FAIL_CLOSED",
        "NEEDS_DISCOVERY_CLASSIFICATION",
        (
            "Operator reports planner, builder, and orchestrator roles may exist as part of a future agentic loop.",
            "Current tool adapter registry lists planner/builder/orchestrator/queue adapters as candidate/future-gated or blocked.",
        ),
        (
            "Planner/builder may later consume cue parser output and package compiler artifacts.",
            "Failed work may later return to queue/orchestrator/planner/builder, but no route is active.",
        ),
        (
            "No current machine proof establishes the loop as safe, current, or executable.",
            "No lifecycle receipts exist for planner-builder handoff.",
        ),
        (
            "Planner input/output schema.",
            "Builder input/output schema.",
            "Orchestrator failure/return rules.",
            "Queue lifecycle receipts.",
        ),
        (
            "Which component existed and which one owned failure handling.",
            "Whether Chief test harness reviewed planner/builder output.",
        ),
        (
            "Non-live planner-builder contract refs.",
            "Orchestrator receipt grammar.",
            "Queue state receipts.",
        ),
        (
            "planner execution",
            "builder execution",
            "orchestrator runtime",
            "queue/autonomy execution",
            "model/agent launch",
            "Repo B execution",
        ),
        "Planner/Builder/Orchestrator Classification Packet",
        False,
        "Future-gated candidate capability only; no planner/builder/orchestrator runtime.",
        ("post-security autonomy", "future task queue lifecycle", "future tool adapter receipts"),
        "POST_SECURITY_AUTONOMY_CANDIDATE",
        None,
        (
            "generated/read_models/tool_protocol_adapter_registry_contract.json",
            "generated/read_models/operator_threshold_map_contract.json",
        ),
        ("planner role memory candidate", "builder role memory candidate", "orchestrator loop candidate"),
        "This loop is quiet when each component has a non-live contract, is parked, or is explicitly blocked.",
        (
            _q("planner_builder_001", "What did the planner do versus the builder versus the orchestrator?", "memory_only_clarification"),
            _q("planner_builder_002", "Where should failed work return: queue, orchestrator, planner, or builder?", "package_contract_needed"),
            _q("planner_builder_003", "What receipt should prove a future handoff occurred?", "proof_needed"),
            _q("planner_builder_004", "Which parts must wait until after security audit?", "security_gate_needed"),
        ),
        operator_reported_only=True,
        machine_proven=False,
    ),
    TerrainLane(
        "model_router",
        "Model Router",
        "policy_and_receipt_metadata_complete_no_runtime",
        "HIGH_TRUST",
        "SECURITY_AUDIT_REQUIRED",
        (
            "Model Selection Policy and Model Selection Receipt define model classes and decision receipts.",
            "Current live default is blocked_no_model for all actors except Operator as human_operator.",
            "Model choices are recommendations/readiness results, not execution commands.",
        ),
        (
            "Future router implementation plan could use these contracts after security and receipt lanes.",
        ),
        (
            "No runtime router proof exists because no runtime router is allowed here.",
        ),
        (
            "Model router implementation plan, still preview-only.",
            "Model selection execution receipts if ever authorized later.",
        ),
        (
            "Whether any remembered model-routing rule is missing from policy.",
        ),
        (
            "Runtime router proof is intentionally absent.",
            "Future security audit decision for model dispatch authority.",
        ),
        (
            "live model calls",
            "model router runtime",
            "hidden routing",
            "external retained memory",
            "self-selected models",
        ),
        "Model Router Implementation Plan v0, preview-only",
        True,
        "Model router is deterministic policy/receipt metadata only; live dispatch is blocked.",
        ("future model router implementation plan", "future dispatch receipt", "future security audit gate"),
        "SECURITY_AUDIT_REQUIRED",
        None,
        (
            "generated/read_models/model_selection_policy_contract.json",
            "generated/read_models/model_selection_receipt_contract.json",
            "generated/read_models/agent_identity_actor_router_contract.json",
        ),
        ("model-router missing-rule candidate", "model-selection receipt example candidate"),
        "Model router is quiet when packages can show selected/blocked/deferred posture without implying live routing.",
        (
            _q("model_router_001", "Is any actor/model pairing missing from the current policy?", "memory_only_clarification"),
            _q("model_router_002", "What proof should be required before a model route becomes executable later?", "proof_needed"),
            _q("model_router_003", "Which contexts must always return blocked_no_model?", "security_gate_needed"),
        ),
    ),
    TerrainLane(
        "tool_plugin_registry",
        "Tool / Plugin Registry",
        "adapter_contract_complete_runtime_blocked",
        "HIGH_TRUST",
        "SECURITY_AUDIT_REQUIRED",
        (
            "Tool Protocol Adapter Registry defines adapter states, capability classes, package binding, receipts, and quarantine.",
            "Active/read-only and preview-only adapters are distinct from future-gated or blocked adapters.",
            "High-risk adapters such as browser/OAuth/Gmail/calendar/Coupa/Telegram remain blocked/future-gated.",
        ),
        (
            "Some adapter proof and future receipt shapes need deeper per-adapter lanes.",
        ),
        (
            "No live adapter runtime or account integration exists.",
        ),
        (
            "Tool Adapter Receipt v0.",
            "Per-adapter proof and gate decisions.",
        ),
        (
            "Which specific tool adapter should become useful first after read-only surfacing.",
        ),
        (
            "Adapter receipts.",
            "Security audit decisions for future eligible adapters.",
        ),
        (
            "live tool execution",
            "browser/OAuth/account flows",
            "Gmail/calendar/Coupa/Telegram access",
            "credentials/tokens/cookies",
            "send/submit/approval",
            "queue/autonomy execution",
        ),
        "Tool Adapter Receipt v0",
        True,
        "Tool/plugin registry is capability metadata only; adapters cannot self-authorize or run.",
        ("future tool adapter receipts", "future protected access gates", "future read-only adapters"),
        "SECURITY_AUDIT_REQUIRED",
        None,
        (
            "generated/read_models/tool_protocol_adapter_registry_contract.json",
            "generated/read_models/agent_package_preview_contract.json",
        ),
        ("adapter proof candidate", "tool receipt candidate", "blocked adapter review candidate"),
        "Tool registry is quiet when package previews can explain included/excluded adapters and all high-risk adapters stay gated.",
        (
            _q("tool_registry_001", "Which adapter should become useful first, and should it be read-only, preview-only, or receipt-only?", "memory_only_clarification"),
            _q("tool_registry_002", "What receipt should prove a future adapter did nothing unsafe?", "proof_needed"),
            _q("tool_registry_003", "Which blocked adapters should remain blocked even after security audit?", "security_gate_needed"),
        ),
    ),
    TerrainLane(
        "package_compiler",
        "Package Compiler",
        "deterministic_contract_spine_ready_preview_only",
        "HIGH_TRUST",
        "READY_FOR_SECURITY_AUDIT",
        (
            "Package compiler and package preview contracts define package schema, context, authority, gates, stop conditions, and receipts.",
            "Package compiler relates actor, model, tool, memory, sensitivity, and proof contracts.",
            "Packages are preview/contract artifacts only now.",
        ),
        (
            "Package Preview Receipt remains the next missing receipt layer.",
            "Future package export/copy or dispatch is not active.",
        ),
        (
            "No live package dispatch or workbench launch authority exists.",
        ),
        (
            "Package Preview Receipt v0.",
            "Package compilation examples tied to live Mission Control surfaces.",
        ),
        (
            "Which package preview should Mission Control surface first for operator confidence.",
        ),
        (
            "Preview receipt grammar.",
            "Package validation receipts if future dispatch is allowed.",
        ),
        (
            "live package dispatch",
            "model/agent launch",
            "tool execution",
            "send/submit/approval",
            "runtime activation",
        ),
        "Package Preview Receipt v0",
        True,
        "Package compiler is schema/preview/proof only; no send, launch, or execution.",
        ("future package preview receipts", "future workbench launch gate", "future action receipt"),
        "QUIET_BACKEND_RESOLVED",
        None,
        (
            "generated/read_models/package_compiler_contract.json",
            "generated/read_models/agent_package_preview_contract.json",
            "generated/read_models/model_selection_receipt_contract.json",
        ),
        ("package-preview receipt candidate",),
        "Package compiler is quiet when package previews have receipts and blocked execution is visible in proof/detail.",
        (
            _q("package_compiler_001", "Which package preview should Mission Control show first?", "memory_only_clarification"),
            _q("package_compiler_002", "What receipt proves a package was previewed but not dispatched?", "proof_needed"),
            _q("package_compiler_003", "Which package fields are still missing before security audit?", "package_contract_needed"),
        ),
    ),
    TerrainLane(
        "capital_hilton",
        "Capital Hilton Invoice Lane",
        "helm_threshold_lane_finance_world_candidate_not_executable",
        "MEDIUM_TRUST",
        "NEEDS_PROOF",
        (
            "Capital Hilton is the invoice steel-thread candidate and current phase is HELM_THRESHOLD_LANE.",
            "Intended destiny is MOVE_TO_WORLD_ACTION with target world Finance.",
            "It likely requires Coupa/Excel/protected proof context and is intentionally harder than normal invoices.",
        ),
        (
            "Package preview and threshold posture exist, but protected proof metadata is incomplete.",
            "Cassandra and Guardian likely participate in future review.",
        ),
        (
            "The system does not know protected Coupa/Excel/account facts.",
            "Operator memory may clarify workflow shape but cannot become proof.",
        ),
        (
            "Protected proof metadata for invoice source, Coupa/Excel refs, and approved source cards.",
            "Security audit decision for account/protected context handling.",
        ),
        (
            "Whether Coupa, Excel, email, or another packet is the actual source-of-truth path.",
            "Which proof can be safely referenced without raw finance body ingestion.",
        ),
        (
            "Coupa/Excel protected metadata receipt.",
            "Capital Hilton package preview receipt.",
            "Guardian protected-access gate receipt.",
        ),
        (
            "Coupa access",
            "Excel/raw finance file inspection",
            "credential/account handling",
            "browser/OAuth",
            "send/submit/approval",
            "invoice execution",
        ),
        "Capital Hilton Protected Proof Metadata Population",
        True,
        "Not executable; protected finance metadata/package preview only before security audit.",
        ("future Finance World action", "future protected access gate", "future invoice package receipt"),
        "MOVE_TO_WORLD_ACTION",
        "Finance",
        (
            "generated/read_models/operator_threshold_map_contract.json",
            "generated/read_models/capital_hilton_actionable_review_packet.json",
            "generated/read_models/capital_hilton_external_artifact_proof_capture.json",
            "generated/read_models/agent_package_preview_contract.json",
        ),
        ("Capital Hilton finance protected context candidate", "invoice source proof gap candidate"),
        "Capital Hilton is quiet on the helm when workflow proof, package boundaries, protected metadata, and security requirements are mapped; action then moves to Finance World.",
        (
            _q("capital_hilton_001", "What is the Capital Hilton invoice source of truth: Coupa, Excel, email, or protected proof packet?", "memory_only_clarification"),
            _q("capital_hilton_002", "What proof metadata can be captured without exposing raw finance material?", "proof_needed"),
            _q("capital_hilton_003", "What would make this ready for security audit but still not executable?", "security_gate_needed"),
            _q("capital_hilton_004", "When should Capital Hilton move from helm threshold lane to Finance World action?", "world_transition_needed"),
        ),
    ),
    TerrainLane(
        "future_domain_workflow_lanes",
        "Future Domain Workflow Lanes",
        "valid_but_premature_world_work_holding_cell",
        "LOW_TRUST",
        "FUTURE_GATED",
        (
            "Future domain workflow lanes are valid concepts for worlds such as Finance, Music/Art, Operations, Security, Build, Research, Communications, Business Development, and Gardening.",
            "Domains should not clutter the helm unless they affect current readiness, proof, safety, mapping, or blockers.",
        ),
        (
            "Some domain lanes are represented through world registry and threshold destiny.",
        ),
        (
            "Most future domain workflows lack threshold proof, security gates, and package previews.",
        ),
        (
            "Per-world lane contracts, proof requirements, package previews, and security gates.",
        ),
        (
            "Which future world is most urgent after Mission Control is calm.",
        ),
        (
            "World registry refs.",
            "Domain package preview receipts.",
            "Security audit decisions.",
        ),
        (
            "domain workflow execution",
            "account actions",
            "send/submit/approval",
            "raw private body ingestion",
            "runtime automation",
        ),
        "Future Domain Workflow Holding Cell Review",
        False,
        "Future worlds remain holding-cell/preview only until threshold and security gates exist.",
        ("future world package previews", "future security-gated workflow receipts"),
        "HOLDING_CELL",
        "Future worlds",
        (
            "generated/read_models/world_domain_registry.json",
            "generated/read_models/operator_threshold_map_contract.json",
        ),
        ("future world workflow candidate", "holding-cell candidate"),
        "Future domain lanes are quiet when parked with triggers or moved into worlds only after readiness/security gates.",
        (
            _q("future_domains_001", "Which future domain lane matters most after the helm is calm?", "memory_only_clarification"),
            _q("future_domains_002", "What proof would make that domain safe to surface?", "proof_needed"),
            _q("future_domains_003", "Which future domain should stay in holding cell until a trigger changes?", "world_transition_needed"),
        ),
    ),
)


RECOMMENDED_NEXT_LANES = (
    RecommendedLane(
        "package_preview_receipt_v0",
        "Package Preview Receipt v0",
        "P1",
        "Terrain awareness shows package compiler as mostly ready but missing preview receipt grammar.",
        "receipt metadata only; no dispatch",
    ),
    RecommendedLane(
        "tool_adapter_receipt_v0",
        "Tool Adapter Receipt v0",
        "P1",
        "Tool/plugin registry has adapter contracts but no execution receipt grammar.",
        "receipt metadata only; no live tool execution",
    ),
    RecommendedLane(
        "mac_read_only_terrain_surface_v0",
        "Mission Control read-only terrain surfacing",
        "P2",
        "The operator needs a calm terrain surface after this read-model lands and syncs through the stable map.",
        "Mac read-only UI; no backend command authority",
    ),
    RecommendedLane(
        "agentic_loop_classification_packet_v0",
        "Agentic Loop Classification Packet v0",
        "P2",
        "The agentic loop and cue parser need non-live classification before any post-security autonomy planning.",
        "classification only; no Repo B execution",
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _content_hash(payload: dict[str, Any]) -> str:
    clone = json.loads(stable_json(payload))
    clone.get("machine_proof", {}).pop("content_hash", None)
    return "sha256:" + hashlib.sha256(stable_json(clone).encode("utf-8")).hexdigest()


def _source_present(repo_root: str | Path, relative_path: str) -> tuple[bool, str | None]:
    path = Path(repo_root) / relative_path
    if not path.is_file():
        return False, None
    if path.suffix.lower() != ".json":
        return True, None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True, None
    if isinstance(loaded, dict):
        return True, loaded.get("schema_version")
    return True, None


def _source_record(source: EvidenceSource, *, repo_root: str | Path) -> dict[str, Any]:
    present, schema_version = _source_present(repo_root, source.path)
    return {
        "source_id": source.source_id,
        "path": source.path,
        "role": source.role,
        "present": present,
        "schema_version": schema_version,
        "raw_private_body_imported": False,
        "credentials_or_secrets_imported": False,
        "authority_granted_by_source_presence": False,
    }


def _question_record(question: OperatorQuestion) -> dict[str, Any]:
    return {
        "question_id": question.question_id,
        "prompt": question.prompt,
        "classification": question.classification,
        "operator_answer_becomes": "memory_candidate_not_machine_proof",
        "execution_authority_created": False,
    }


def _lane_record(lane: TerrainLane) -> dict[str, Any]:
    return {
        "lane_id": lane.lane_id,
        "display_name": lane.display_name,
        "current_status": lane.current_status,
        "confidence_state": lane.confidence_state,
        "readiness_state": lane.readiness_state,
        "known": list(lane.known),
        "partly_known": list(lane.partly_known),
        "known_unknown": list(lane.known_unknown),
        "not_discovered": list(lane.not_discovered),
        "needs_winship_memory_comparison": list(lane.needs_operator_memory_comparison),
        "needs_operator_memory_comparison": list(lane.needs_operator_memory_comparison),
        "missing_machine_proof": list(lane.missing_machine_proof),
        "blocked_not_authorized": list(lane.blocked_authorities),
        "blocked_authorities": list(lane.blocked_authorities),
        "safe_next_detour": lane.safe_next_detour,
        "package_preview_available": lane.package_preview_available,
        "current_authority_boundary": lane.current_authority_boundary,
        "future_gated_actions": list(lane.future_gated_actions),
        "lane_destiny": {
            "resolution_route": lane.resolution_route,
            "target_world": lane.target_world,
            "helm_after_resolution": _helm_after_resolution(lane),
        },
        "resolution_route": lane.resolution_route,
        "target_world": lane.target_world,
        "proof_refs": list(lane.proof_refs),
        "missing_proof": list(lane.missing_machine_proof),
        "memory_candidates_needed": list(lane.memory_candidates_needed),
        "what_would_make_lane_quiet": lane.what_makes_quiet,
        "what_makes_quiet": lane.what_makes_quiet,
        "recommended_operator_questions": [_question_record(question) for question in lane.recommended_operator_questions],
        "operator_reported_only": lane.operator_reported_only,
        "machine_proven": lane.machine_proven,
        "operator_memory_may_be_used_as_proof": False,
        "live_execution_authority": False,
    }


def _helm_after_resolution(lane: TerrainLane) -> str:
    if lane.resolution_route == "MOVE_TO_WORLD_ACTION":
        return f"Move to {lane.target_world} world for domain work; helm keeps only a quiet global marker if needed."
    if lane.resolution_route == "QUIET_BACKEND_RESOLVED":
        return "Disappear from helm or remain only as quiet proof/detail."
    if lane.resolution_route == "PARK_WITH_PROOF":
        return "Hide from front door unless trigger condition changes or briefing surface asks for it."
    if lane.resolution_route == "POST_SECURITY_AUTONOMY_CANDIDATE":
        return "Hold as future-gated autonomy/cue terrain; no run controls before security."
    if lane.resolution_route == "SECURITY_AUDIT_REQUIRED":
        return "Show as audit-ready or proof/detail, not as executable."
    if lane.resolution_route == "HOLDING_CELL":
        return "Keep in holding cell with dependency/trigger markers."
    return "Return to system build lane until classified."


def _matrix_row(lane: TerrainLane) -> dict[str, Any]:
    return {
        "lane_id": lane.lane_id,
        "display_name": lane.display_name,
        "current_status": lane.current_status,
        "confidence": lane.confidence_state,
        "known": list(lane.known),
        "partly_known": list(lane.partly_known),
        "known_unknown": list(lane.known_unknown),
        "not_discovered": list(lane.not_discovered),
        "operator_memory_needed": list(lane.needs_operator_memory_comparison),
        "machine_proof_needed": list(lane.missing_machine_proof),
        "safe_next_detour": lane.safe_next_detour,
        "lane_destiny": lane.resolution_route,
        "quiet_condition": lane.what_makes_quiet,
    }


def _focus(lane_id: str, lanes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return lanes[lane_id]


def _focused_agentic_loop(lanes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "section_id": "agentic_loop_focus",
        "operator_reported_architecture_candidate": True,
        "machine_proven_current_runtime": False,
        "current_execution_authority": False,
        "components": {
            "agentic_loop": _focus("agentic_loop", lanes),
            "cue_parser_brain_dump_parser": _focus("cue_parser_brain_dump_parser", lanes),
            "planner_builder_orchestrator_loop": _focus("planner_builder_orchestrator_loop", lanes),
            "repo_b_leftovers": _focus("repo_b_leftovers", lanes),
        },
        "known_from_operator_report": [
            "Repo B may contain an agentic planner/builder/orchestrator loop.",
            "A parser may turn operator/Chief ideas into queued work or holding-cell items.",
            "Chief may send work into parser for near-term system fixes/builds.",
            "Operator may use parser for brain dumps with mixed timelines.",
            "Chief may run a test harness on planner/builder outputs.",
            "Failed work may return to queue, orchestrator, planner, or builder.",
        ],
        "not_machine_proven": [
            "loop source location",
            "current code state",
            "safe input/output contracts",
            "queue lifecycle receipts",
            "planner/builder/orchestrator handoff receipts",
        ],
        "blocked": [
            "Repo B body inspection",
            "Repo B execution",
            "planner/builder loop execution",
            "queue/autonomy execution",
            "model/agent/tool activation",
        ],
        "safe_next_detour": "Agentic Loop Classification Packet using approved metadata and operator memory candidates.",
        "what_would_make_quiet": "Each loop component is classified as blocked, parked, obsolete, or future-gated with proof refs and no active run authority.",
    }


def _focused_agent_personas(lanes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "section_id": "agent_persona_focus",
        "chief": _focus("chief", lanes),
        "chief_test_harness": _focus("chief_test_harness", lanes),
        "hermes": _focus("hermes", lanes),
        "cassandra": _focus("cassandra", lanes),
        "guardian": _focus("guardian", lanes),
        "niles": _focus("niles", lanes),
        "struna": _focus("struna", lanes),
        "distinctions": {
            "chief_character": "persona used in package/readback surfaces",
            "chief_package": "deterministic mission/context/proof packet; preview only",
            "chief_test_harness": "unclassified possible deterministic harness; no runtime",
            "chief_live_execution_authority": "absent and blocked",
            "cassandra_now": "finance/comms metadata package preview only",
            "niles_now": "creative metadata/context package preview only",
            "operator_memory": "candidate context, never machine proof by itself",
        },
    }


def _focused_model_tool_package(lanes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "section_id": "model_tool_package_focus",
        "model_router": _focus("model_router", lanes),
        "tool_plugin_registry": _focus("tool_plugin_registry", lanes),
        "package_compiler": _focus("package_compiler", lanes),
        "current_live_default": "blocked_no_model except operator_winship as human_operator; package previews only",
        "proof_backed_contract_refs": [
            "generated/read_models/model_selection_policy_contract.json",
            "generated/read_models/model_selection_receipt_contract.json",
            "generated/read_models/tool_protocol_adapter_registry_contract.json",
            "generated/read_models/package_compiler_contract.json",
            "generated/read_models/agent_package_preview_contract.json",
        ],
        "future_gated": [
            "runtime model router",
            "tool adapter execution",
            "package dispatch",
            "workbench launch",
            "agent activation",
        ],
    }


def _focused_capital_hilton(lanes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    capital = _focus("capital_hilton", lanes)
    return {
        "section_id": "capital_hilton_focus",
        **capital,
        "current_phase": "HELM_THRESHOLD_LANE",
        "intended_destiny": "MOVE_TO_WORLD_ACTION",
        "target_world": "Finance",
        "not_currently_executable": True,
        "no_current_authority": [
            "Coupa access",
            "credential handling",
            "browser/OAuth",
            "send/submit/approval",
            "account flow",
            "raw finance file inspection",
        ],
        "ready_for_security_audit_when": [
            "workflow outline exists",
            "protected proof metadata refs exist",
            "package boundaries and context exclusions exist",
            "Guardian/Operator gates are named",
            "quiet condition is explicit",
        ],
        "ready_for_finance_world_action_when": [
            "security audit grants exact authority",
            "protected proof receipts exist",
            "package preview and pre-action receipt exist",
            "send/submit/approval remains separately gated",
        ],
    }


def _operator_questions(lanes: tuple[TerrainLane, ...]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for lane in lanes:
        for question in lane.recommended_operator_questions:
            record = _question_record(question)
            record["lane_id"] = lane.lane_id
            record["lane_display_name"] = lane.display_name
            questions.append(record)
    return questions


def _recommended_lane_record(lane: RecommendedLane) -> dict[str, Any]:
    return {
        "lane_id": lane.lane_id,
        "title": lane.title,
        "priority": lane.priority,
        "why_next": lane.why_next,
        "hard_boundary": lane.hard_boundary,
    }


def build_agent_terrain_awareness_readback_contract(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    evidence_sources = [_source_record(source, repo_root=repo_root) for source in EVIDENCE_SOURCES]
    lane_records = [_lane_record(lane) for lane in TERRAIN_LANES]
    lanes_by_id = {lane["lane_id"]: lane for lane in lane_records}
    matrix = [_matrix_row(lane) for lane in TERRAIN_LANES]
    questions = _operator_questions(TERRAIN_LANES)
    missing_required_lanes = [lane_id for lane_id in REQUIRED_LANE_IDS if lane_id not in lanes_by_id]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": "agent_terrain_awareness_readback_contract",
        "generated_at": generated_at,
        **NO_AUTHORITY_FLAGS,
        "contract_status": "deterministic_terrain_awareness_readback_metadata_only",
        "operator_summary": (
            "OpenClaw now has a deterministic terrain readback for major agent/persona and system-loop lanes. "
            "It shows what is known, partly known, known unknown, not discovered, and where Winship memory may "
            "clarify context without becoming proof. It adds no execution, runtime, tool, model, Mac, Repo B, or account authority."
        ),
        "core_doctrine": {
            "operator_memory_can_clarify_but_not_prove": True,
            "operator_answers_become_memory_candidates_not_machine_proof": True,
            "operator_reported_architecture_is_labeled": True,
            "repo_b_reference_only_no_broad_body_inspection": True,
            "agentic_loop_post_security_future_gated": True,
            "package_preview_is_not_dispatch": True,
            "mission_control_should_avoid_nested_card_wall": True,
        },
        "evidence_sources": evidence_sources,
        "classification_model": {
            "known": "Represented by current deterministic contracts/read-models or explicit operator-provided context in this lane.",
            "partly_known": "Conceptually represented but missing exact proof, source refs, or receipt grammar.",
            "known_unknown": "The system explicitly knows it lacks source/proof/context.",
            "not_discovered": "No approved source metadata has been found or provided yet.",
            "needs_winship_memory_comparison": "Operator memory may name or clarify context, but answers become memory candidates.",
            "blocked_not_authorized": "Authority is absent and must fail closed.",
            "proof_needed_rule": "Machine proof requires read-model refs, receipts, source cards, hashes, tests, manifests, or protected metadata. Natural-language memory is not proof.",
            "confidence_policy": "No fake percentages. Confidence is quiet when deterministic; visible only when it changes the next safe move.",
            "quiet_condition_model": "A lane quiets when it is proof-backed, intentionally parked, moved to a world, blocked with proof, or returned to system build with a detour.",
        },
        "readiness_states": list(READINESS_STATES),
        "confidence_states": list(CONFIDENCE_STATES),
        "lane_destiny_routes": list(LANE_DESTINY_ROUTES),
        "terrain_inventory": lane_records,
        "readback_matrix": {
            "columns": list(MATRIX_COLUMNS),
            "rows": matrix,
        },
        "agentic_loop_focus": _focused_agentic_loop(lanes_by_id),
        "agent_persona_focus": _focused_agent_personas(lanes_by_id),
        "model_tool_package_focus": _focused_model_tool_package(lanes_by_id),
        "capital_hilton_focus": _focused_capital_hilton(lanes_by_id),
        "operator_memory_comparison_questions": questions,
        "mission_control_surface_guidance": {
            "show": [
                "one System Awareness / Terrain Map surface",
                "agent/persona lanes collapsed by default",
                "known / partly known / known unknown / not discovered matrix",
                "one selected lane's operator questions",
                "operator memory as candidate context, not truth",
                "proof needed separately from memory",
                "package preview if available",
                "future-gated chat/workbench target metadata without launch",
                "Tell System What's Missing as capture/preview only",
            ],
            "hide_or_collapse": [
                "every nested lane as a card wall",
                "raw private content",
                "Repo B body details",
                "live execution controls",
                "queue/autonomy controls",
                "model/tool/browser/account launch controls",
                "fake confidence percentages",
            ],
            "top_layer": "What does the system know, what is missing, and which one thing can Winship clarify next?",
            "middle_layer": "Lane matrix, proof refs, memory questions, package availability, and quiet conditions.",
            "lower_layer": "Read-model evidence refs, missing proof, blocked authorities, future-gated capabilities, and package/receipt details.",
        },
        "stable_map_integration": {
            "registry_generated_as_read_model": True,
            "summary_included_in_stable_map_bundle_now": False,
            "reason_not_included_now": (
                "Stable-map/sync files are separate dirty lane residue in this worktree; this contract does not reopen bridge churn, "
                "run Mac sync, or mutate the stable map bundle."
            ),
            "safe_summary_to_include_next": {
                "contract_id": "agent_terrain_awareness_readback_contract",
                "lanes_inventoried_count": len(lane_records),
                "top_unknown_lanes": [
                    lane["lane_id"]
                    for lane in lane_records
                    if lane["confidence_state"] == "UNKNOWN_FAIL_CLOSED"
                ],
                "operator_memory_questions_count": len(questions),
                "recommended_next_detour": "Pick one terrain gap and answer its guided memory question as a memory candidate.",
            },
            "next_map_bundle_refresh_requirement": "Include this summary in the next stable map bundle refresh after this contract lands.",
        },
        "relationship_to_existing_contracts": {
            "operator_awareness_agent_package_spine": "source for known/unknown agent awareness gaps",
            "operator_nested_lane_mission_package_spine": "source for nested lane posture and package/detail boundaries",
            "agent_platform_alignment": "defines agent-platform primitives and missing platform pieces",
            "agent_identity_actor_router": "defines actor/persona identity and routing posture",
            "model_selection_policy": "defines model class policy",
            "agent_package_preview": "defines non-executing package preview shape",
            "agent_memory_scope": "defines memory/context visibility and blocked memory",
            "tool_protocol_adapter_registry": "defines tool/adapter states and blocked capabilities",
            "memory_candidate_receipt": "defines how operator answers become memory candidates",
            "model_selection_receipt": "defines proof for actor/model decisions",
            "threshold_map_contract": "defines lane readiness and lane destiny",
            "stable_map_bundle": "should carry a small summary later without making raw read-model churn front-door truth",
        },
        "recommended_next_lanes": [_recommended_lane_record(lane) for lane in RECOMMENDED_NEXT_LANES],
        "machine_proof": {
            "source_read_models_present": {source["source_id"]: source["present"] for source in evidence_sources},
            "required_lane_ids": list(REQUIRED_LANE_IDS),
            "missing_required_lane_ids": missing_required_lanes,
            "lane_count": len(lane_records),
            "operator_question_count": len(questions),
            "operator_reported_only_lanes": [
                lane["lane_id"] for lane in lane_records if lane["operator_reported_only"]
            ],
            "unknown_fail_closed_lanes": [
                lane["lane_id"] for lane in lane_records if lane["confidence_state"] == "UNKNOWN_FAIL_CLOSED"
            ],
            "move_to_world_action_lanes": [
                lane["lane_id"] for lane in lane_records if lane["resolution_route"] == "MOVE_TO_WORLD_ACTION"
            ],
            "repo_b_body_inspection_performed": False,
            "repo_b_mutation_performed": False,
            "runtime_execution_added": False,
            "planner_builder_execution_added": False,
            "queue_autonomy_execution_added": False,
            "model_call_performed": False,
            "tool_execution_performed": False,
            "mac_sync_import_triggered": False,
            "pc_c_drive_artifact_write_added": False,
            "content_hash": None,
        },
    }
    payload["machine_proof"]["content_hash"] = _content_hash(payload)
    return payload


def format_agent_terrain_awareness_readback_contract(payload: dict[str, Any]) -> str:
    lines = [
        "# Agent Terrain Awareness Readback Contract v0",
        "",
        "## Operator Summary",
        payload["operator_summary"],
        "",
        "## Terrain Map",
    ]
    for row in payload["readback_matrix"]["rows"]:
        lines.append(
            f"- `{row['lane_id']}`: status `{row['current_status']}`; confidence `{row['confidence']}`; "
            f"destiny `{row['lane_destiny']}`; quiet when {row['quiet_condition']}"
        )
    lines.extend(["", "## Agentic Loop"])
    agentic = payload["agentic_loop_focus"]
    lines.append(f"- Operator-reported architecture candidate: `{str(agentic['operator_reported_architecture_candidate']).lower()}`")
    lines.append(f"- Machine-proven current runtime: `{str(agentic['machine_proven_current_runtime']).lower()}`")
    lines.append(f"- Current execution authority: `{str(agentic['current_execution_authority']).lower()}`")
    lines.append(f"- Safe next detour: {agentic['safe_next_detour']}")
    lines.extend(["", "## Agent Personas"])
    for lane_id in ("chief", "chief_test_harness", "hermes", "cassandra", "guardian", "niles", "struna"):
        lane = payload["agent_persona_focus"][lane_id]
        lines.append(
            f"- `{lane_id}`: readiness `{lane['readiness_state']}`; confidence `{lane['confidence_state']}`; "
            f"next `{lane['safe_next_detour']}`."
        )
    lines.extend(["", "## Model / Tool / Package"])
    for lane_id in ("model_router", "tool_plugin_registry", "package_compiler"):
        lane = payload["model_tool_package_focus"][lane_id]
        lines.append(
            f"- `{lane_id}`: readiness `{lane['readiness_state']}`; boundary {lane['current_authority_boundary']}"
        )
    lines.extend(["", "## Capital Hilton"])
    cap = payload["capital_hilton_focus"]
    lines.append(f"- Current phase: `{cap['current_phase']}`")
    lines.append(f"- Intended destiny: `{cap['intended_destiny']}`")
    lines.append(f"- Target world: `{cap['target_world']}`")
    lines.append(f"- Not currently executable: `{str(cap['not_currently_executable']).lower()}`")
    lines.append(f"- Quiet condition: {cap['what_makes_quiet']}")
    lines.extend(["", "## Operator Questions"])
    for question in payload["operator_memory_comparison_questions"]:
        lines.append(f"- `{question['lane_id']}` / `{question['classification']}`: {question['prompt']}")
    lines.extend(["", "## Mission Control Guidance"])
    for item in payload["mission_control_surface_guidance"]["show"]:
        lines.append(f"- show: {item}")
    for item in payload["mission_control_surface_guidance"]["hide_or_collapse"]:
        lines.append(f"- hide/collapse: {item}")
    lines.extend(["", "## Stable Map Integration"])
    stable = payload["stable_map_integration"]
    lines.append(f"- Summary included in stable map now: `{str(stable['summary_included_in_stable_map_bundle_now']).lower()}`")
    lines.append(f"- Next requirement: {stable['next_map_bundle_refresh_requirement']}")
    lines.extend(["", "## Authority Boundary"])
    for key, value in NO_AUTHORITY_FLAGS.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(["", "## Next Lanes"])
    for lane in payload["recommended_next_lanes"]:
        lines.append(f"- `{lane['lane_id']}` ({lane['priority']}): {lane['title']}")
    return "\n".join(lines).rstrip() + "\n"


def export_agent_terrain_awareness_readback_contract(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> TerrainAwarenessExportResult:
    payload = build_agent_terrain_awareness_readback_contract(repo_root=repo_root, generated_at=generated_at)
    root = Path(export_root)
    if not root.is_absolute():
        root = Path(repo_root) / root
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / JSON_EXPORT_NAME
    operator_path = root / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_agent_terrain_awareness_readback_contract(payload), encoding="utf-8")
    return TerrainAwarenessExportResult(
        schema_version=payload["schema_version"],
        json_path=json_path.as_posix(),
        operator_path=operator_path.as_posix(),
        lane_count=payload["machine_proof"]["lane_count"],
        operator_question_count=payload["machine_proof"]["operator_question_count"],
        runtime_authority_added=bool(payload["runtime_authority"]),
        repo_b_mutation_added=bool(payload["repo_b_mutation_enabled"]),
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Agent Terrain Awareness Readback Contract read-model.")
    parser.add_argument("--repo-root", default=ROOT.as_posix())
    parser.add_argument("--export-root", default=DEFAULT_EXPORT_ROOT.as_posix())
    parser.add_argument("--format", choices=("summary", "json", "operator"), default="summary")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = export_agent_terrain_awareness_readback_contract(repo_root=args.repo_root, export_root=args.export_root)
    if args.format == "json":
        print(stable_json(build_agent_terrain_awareness_readback_contract(repo_root=args.repo_root)), end="")
    elif args.format == "operator":
        payload = build_agent_terrain_awareness_readback_contract(repo_root=args.repo_root)
        print(format_agent_terrain_awareness_readback_contract(payload), end="")
    else:
        print(
            stable_json(
                {
                    "schema_version": result.schema_version,
                    "json_path": result.json_path,
                    "operator_path": result.operator_path,
                    "lane_count": result.lane_count,
                    "operator_question_count": result.operator_question_count,
                    "runtime_authority_added": result.runtime_authority_added,
                    "repo_b_mutation_added": result.repo_b_mutation_added,
                }
            ),
            end="",
        )
    return 0


__all__ = [
    "CONFIDENCE_STATES",
    "JSON_EXPORT_NAME",
    "LANE_DESTINY_ROUTES",
    "MATRIX_COLUMNS",
    "NO_AUTHORITY_FLAGS",
    "OPERATOR_EXPORT_NAME",
    "OPERATOR_QUESTION_TYPES",
    "READINESS_STATES",
    "REQUIRED_LANE_IDS",
    "SCHEMA_VERSION",
    "TERRAIN_LANES",
    "build_agent_terrain_awareness_readback_contract",
    "export_agent_terrain_awareness_readback_contract",
    "format_agent_terrain_awareness_readback_contract",
    "main",
    "stable_json",
]

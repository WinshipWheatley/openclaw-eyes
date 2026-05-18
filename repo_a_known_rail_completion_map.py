"""Repo A known rail completion map v0.

This module builds a deterministic Repo A-only readiness map for the known
OpenClaw rails already represented in the canonical backend repo. It checks
named Repo A files/read-models/tests only; it does not inspect Repo B, activate
runtime paths, send messages, access external services, or start a security
threshold pass.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from post_preflight_batch_gate import PASS, evaluate_post_preflight_lane


ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = "repo_a_known_rail_completion_map_v0"
JSON_EXPORT_NAME = "repo_a_known_rail_completion_map.json"
OPERATOR_EXPORT_NAME = "repo_a_known_rail_completion_map_OPERATOR.md"
DEFAULT_EXPORT_ROOT = Path("generated/read_models")

MATURITY_SCALE = (
    "NOT_FOUND",
    "LEGACY_OR_REFERENCE_IN_REPO_A",
    "METADATA_ONLY",
    "READ_MODEL_VISIBLE",
    "REVIEW_PACKET_READY",
    "PROOF_RAIL_READY",
    "APPROVAL_REQUEST_CONTRACT_READY",
    "APPROVAL_RECEIPT_READY",
    "EXECUTION_GATE_MODELED",
    "SECURITY_THRESHOLD_READY",
    "LIVE_AUTHORITY_BLOCKED",
)

READINESS_KEYS = (
    "visibility_only",
    "review_packet",
    "proof_packet",
    "approval_request_contract",
    "approval_receipt",
    "execution_gate",
    "security_threshold_audit",
    "live_workflow",
)

NO_AUTHORITY_FLAGS = {
    "repo_b_inspected": False,
    "runtime_authority_added": False,
    "send_or_submit_authority_added": False,
    "approval_execution_authority_added": False,
    "browser_or_coupa_authority_added": False,
    "credential_or_pii_access_added": False,
    "customer_deployment_authority_added": False,
    "planner_builder_agent_automation_activated": False,
    "mission_control_app_changed": False,
    "security_pass_started": False,
    "generic_calendar_cleanup_performed": False,
    "old_files_treated_as_truth": False,
}

REPO_B_DELTA_QUESTIONS = (
    "Which Repo B capabilities are already represented in Repo A read-models, contracts, or tests?",
    "Which Repo B surfaces are partially represented but still missing a Repo A steel-thread rail?",
    "Which Repo B code is obsolete, unsafe, or superseded by Repo A contracts?",
    "Which remembered Winship workflows have no deterministic Repo A evidence yet?",
    "Which Repo B capabilities are worth bringing forward only after Repo A rails reach proof/request maturity?",
)


@dataclass(frozen=True)
class EvidenceSpec:
    path: str
    role: str
    evidence_type: str
    truth_status: str = "repo_a_evidence_not_truth"


@dataclass(frozen=True)
class RailSpec:
    rail_id: str
    rail_name: str
    domain: str
    operator_value: str
    maturity: str
    steel_thread_stage_reached: str
    key_files: tuple[EvidenceSpec, ...]
    generated_read_models: tuple[EvidenceSpec, ...]
    tests: tuple[EvidenceSpec, ...]
    sqlite_read_model_integration_status: str
    mission_control_visibility_status: str
    missing_next_pieces: tuple[str, ...]
    authority_boundary: str
    ready_for: dict[str, bool]
    can_wait: bool = False


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _display_path(path: str | Path) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.as_posix()


def _repo_path(path: str | Path, *, repo_root: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(repo_root) / candidate


def _evidence_record(spec: EvidenceSpec, *, repo_root: str | Path) -> dict[str, Any]:
    path = _repo_path(spec.path, repo_root=repo_root)
    return {
        "path": spec.path,
        "present": path.exists(),
        "role": spec.role,
        "evidence_type": spec.evidence_type,
        "truth_status": spec.truth_status,
        "repo_a_only": True,
        "body_read": False,
    }


def _ready(
    *,
    visibility_only: bool = False,
    review_packet: bool = False,
    proof_packet: bool = False,
    approval_request_contract: bool = False,
    approval_receipt: bool = False,
    execution_gate: bool = False,
    security_threshold_audit: bool = False,
    live_workflow: bool = False,
) -> dict[str, bool]:
    return {
        "visibility_only": visibility_only,
        "review_packet": review_packet,
        "proof_packet": proof_packet,
        "approval_request_contract": approval_request_contract,
        "approval_receipt": approval_receipt,
        "execution_gate": execution_gate,
        "security_threshold_audit": security_threshold_audit,
        "live_workflow": live_workflow,
    }


def _spec(
    path: str,
    role: str,
    evidence_type: str,
    truth_status: str = "repo_a_evidence_not_truth",
) -> EvidenceSpec:
    return EvidenceSpec(path=path, role=role, evidence_type=evidence_type, truth_status=truth_status)


def _rail_specs() -> tuple[RailSpec, ...]:
    return (
        RailSpec(
            rail_id="capital_hilton_cassandra_clara_finance",
            rail_name="Capital Hilton / Cassandra-Clara finance workflow",
            domain="finance_ap_invoice",
            operator_value="Turns governed invoice facts into review, proof, and Guardian request posture for Capital Hilton.",
            maturity="APPROVAL_REQUEST_CONTRACT_READY",
            steel_thread_stage_reached="review_packet_plus_proof_rail_plus_final_send_request_contract",
            key_files=(
                _spec("capital_hilton_actionable_review_packet.py", "review-only packet builder", "code"),
                _spec("capital_hilton_external_artifact_proof_capture.py", "protected proof metadata capture", "code"),
                _spec("capital_hilton_send_approval_gate.py", "final-send gate model", "code"),
                _spec("guardian_draft_approval_request_contract.py", "Guardian draft approval request contract", "code"),
            ),
            generated_read_models=(
                _spec("generated/read_models/capital_hilton_actionable_review_packet.json", "actionable review packet", "read_model"),
                _spec("generated/read_models/capital_hilton_external_artifact_proof_capture.json", "proof rail", "read_model"),
                _spec("generated/read_models/capital_hilton_send_approval_gate.json", "final-send gate", "read_model"),
                _spec("generated/read_models/guardian_draft_approval_request_contract.json", "draft approval request contract", "read_model"),
            ),
            tests=(
                _spec("tests/test_capital_hilton_external_artifact_proof_capture.py", "proof rail tests", "test"),
                _spec("tests/test_capital_hilton_send_approval_gate.py", "send gate tests", "test"),
                _spec("tests/test_guardian_draft_approval_request_contract.py", "Guardian request contract tests", "test"),
            ),
            sqlite_read_model_integration_status="read_model_integrated_sqlite_facts_evidence_only",
            mission_control_visibility_status="visible_for_review_packet_and_proof_posture_via_mirror",
            missing_next_pieces=(
                "real operator proof metadata/protected references",
                "specific draft identity and attachment identity",
                "future approval receipt contract",
                "execution remains blocked",
            ),
            authority_boundary="review/proof/request-contract only; no Coupa, browser, Gmail, send, submit, credential, or spreadsheet authority",
            ready_for=_ready(
                visibility_only=True,
                review_packet=True,
                proof_packet=True,
                approval_request_contract=True,
                execution_gate=True,
                live_workflow=False,
            ),
        ),
        RailSpec(
            rail_id="cassandra_draft_review_email_calendar",
            rail_name="Cassandra draft/review/email/calendar capability",
            domain="cassandra_comms",
            operator_value="Lets Cassandra produce review-only draft packets while email/calendar execution remains blocked.",
            maturity="REVIEW_PACKET_READY",
            steel_thread_stage_reached="draft_review_packet_and_capability_reconciliation",
            key_files=(
                _spec("cassandra_draft_review_packet.py", "draft review packet", "code"),
                _spec("cassandra_email_calendar_capability_reconciliation.py", "email/calendar capability reconciliation", "code"),
                _spec("cassandra_outreach.py", "legacy/reference outreach machinery", "code", "legacy_or_reference_evidence_only"),
            ),
            generated_read_models=(
                _spec("generated/read_models/cassandra_draft_review_packet.json", "draft review packet", "read_model"),
                _spec("generated/read_models/cassandra_email_calendar_capability_reconciliation.json", "capability reconciliation", "read_model"),
                _spec("generated/read_models/cassandra_send_status_dry_run.json", "no-send status/dry-run posture", "read_model"),
            ),
            tests=(
                _spec("tests/test_cassandra_draft_review_packet.py", "draft review tests", "test"),
                _spec("tests/test_cassandra_email_calendar_capability_reconciliation.py", "capability reconciliation tests", "test"),
            ),
            sqlite_read_model_integration_status="read_model_only_no_live_gmail_or_calendar",
            mission_control_visibility_status="draft packet surfaced; execution controls absent by design",
            missing_next_pieces=(
                "generic second workflow draft packet proof",
                "future Guardian send approval receipt shape",
                "execution authority intentionally deferred",
            ),
            authority_boundary="no Gmail draft, Gmail send, calendar write, OAuth, or live account access",
            ready_for=_ready(visibility_only=True, review_packet=True, live_workflow=False),
        ),
        RailSpec(
            rail_id="guardian_hitl_security_sovereignty",
            rail_name="Guardian approval/HITL/security/sovereignty contracts",
            domain="approval_security",
            operator_value="Defines Guardian responsibility, approval request/receipt separation, and power-stage limits.",
            maturity="SECURITY_THRESHOLD_READY",
            steel_thread_stage_reached="contracts_modeled_security_threshold_not_crossed",
            key_files=(
                _spec("guardian_responsibility_dna_audit.py", "Guardian responsibility audit", "code"),
                _spec("guardian_hitl_sqlite_authority_contract.py", "canonical approval contract", "code"),
                _spec("operator_sovereignty_power_stage_gate.py", "power-stage gate", "code"),
            ),
            generated_read_models=(
                _spec("generated/read_models/guardian_responsibility_dna_audit.json", "Guardian DNA audit", "read_model"),
                _spec("generated/read_models/guardian_hitl_sqlite_authority_contract.json", "SQLite authority contract", "read_model"),
                _spec("generated/read_models/operator_sovereignty_power_stage_gate.json", "power-stage gate", "read_model"),
            ),
            tests=(
                _spec("tests/test_guardian_responsibility_dna_audit.py", "Guardian DNA tests", "test"),
                _spec("tests/test_guardian_hitl_sqlite_authority_contract.py", "authority contract tests", "test"),
                _spec("tests/test_operator_sovereignty_power_stage_gate.py", "power-stage tests", "test"),
            ),
            sqlite_read_model_integration_status="contract_defined_observational_sqlite_support_present_for_some_legacy_paths",
            mission_control_visibility_status="read-model visible; app-specific surfaces vary by prior lanes",
            missing_next_pieces=(
                "approval receipt contract for draft/final send",
                "old HITL caller transition proof",
                "security pass later when rails approach execution threshold",
            ),
            authority_boundary="Guardian remains gatekeeper/not executor; no live approval execution or send authority",
            ready_for=_ready(
                visibility_only=True,
                approval_request_contract=True,
                approval_receipt=True,
                security_threshold_audit=False,
                live_workflow=False,
            ),
        ),
        RailSpec(
            rail_id="chief_orchestration_work_packets",
            rail_name="Chief orchestration/planning/work packets",
            domain="planning_work_packets",
            operator_value="Routes intents into Work Board and Agent Work Packet posture without activating agents.",
            maturity="READ_MODEL_VISIBLE",
            steel_thread_stage_reached="work_board_and_agent_work_packets_visible",
            key_files=(
                _spec("chief_router.py", "legacy Chief router/reference", "code", "legacy_or_reference_evidence_only"),
                _spec("work_board.py", "Work Board read-model substrate", "code"),
                _spec("agent_work_packet.py", "Agent Work Packet builder", "code"),
                _spec("intent_router.py", "intent router", "code"),
            ),
            generated_read_models=(
                _spec("generated/read_models/work_board.json", "Work Board", "read_model"),
                _spec("generated/read_models/agent_work_packets.json", "Agent work packets", "read_model"),
                _spec("generated/read_models/intent_router.json", "intent router", "read_model"),
            ),
            tests=(
                _spec("tests/test_work_board.py", "Work Board tests", "test"),
                _spec("tests/test_agent_work_packet.py", "Agent work packet tests", "test"),
                _spec("tests/test_intent_router.py", "intent router tests", "test"),
            ),
            sqlite_read_model_integration_status="work_packet_read_models_exist_runtime_agent_activation_blocked",
            mission_control_visibility_status="read-model surfaces exist; operator helm integration may be partial",
            missing_next_pieces=(
                "prove second non-finance real workflow through work packet path",
                "separate Chief legacy runtime from governed packet substrate",
            ),
            authority_boundary="planning/read-model only; no agent activation or automatic execution",
            ready_for=_ready(visibility_only=True, review_packet=False, live_workflow=False),
        ),
        RailSpec(
            rail_id="hermes_advisory_synthesis",
            rail_name="Hermes advisory synthesis",
            domain="advisory_synthesis",
            operator_value="Keeps Hermes as advisory packet-in/proposal-out synthesis, not a decision or authority source.",
            maturity="METADATA_ONLY",
            steel_thread_stage_reached="contract_helpers_and_registry_evidence",
            key_files=(
                _spec("hermes_advisory_packet.py", "Hermes advisory packet helper", "code"),
                _spec("expert_escalation_packet.py", "sanitized expert escalation helper", "code"),
                _spec("agent_lane_registry.py", "Hermes lane registry metadata", "code"),
            ),
            generated_read_models=(
                _spec("generated/read_models/agent_lanes.json", "agent lane registry", "read_model"),
                _spec("generated/read_models/external_ai_context_packs.json", "external AI context packs", "read_model"),
            ),
            tests=(
                _spec("tests/test_hermes_advisory_packet.py", "Hermes advisory tests", "test"),
                _spec("tests/test_expert_escalation_packet.py", "expert escalation tests", "test"),
            ),
            sqlite_read_model_integration_status="metadata_contract_only_no_decision_authority",
            mission_control_visibility_status="likely indirect through lane/context read-models",
            missing_next_pieces=(
                "operator-facing Hermes advisory rail packet",
                "prove advisory output cannot promote truth or authority",
            ),
            authority_boundary="advisory only; no decisions, sends, external expert contact, or truth promotion",
            ready_for=_ready(visibility_only=True, live_workflow=False),
            can_wait=True,
        ),
        RailSpec(
            rail_id="niles_music_album_struna_capsule",
            rail_name="Niles music/album/Struna/project capsule lane",
            domain="music_art_projects",
            operator_value="Tracks Niles album metadata and Struna project context without scanning private creative files.",
            maturity="REVIEW_PACKET_READY",
            steel_thread_stage_reached="metadata_intake_boundary_and_review_packets",
            key_files=(
                _spec("niles_album_evidence_intake_boundary.py", "album evidence intake boundary", "code"),
                _spec("niles_album_review_packet.py", "album review packet", "code"),
                _spec("struna_obscura_project_capsule.py", "Struna project capsule", "code"),
            ),
            generated_read_models=(
                _spec("generated/read_models/niles_album_evidence_intake_boundary.json", "Niles evidence boundary", "read_model"),
                _spec("generated/read_models/niles_album_review_packet.json", "Niles album review packet", "read_model"),
                _spec("generated/read_models/struna_obscura_project_capsule.json", "Struna capsule", "read_model"),
            ),
            tests=(
                _spec("tests/test_niles_album_evidence_intake_boundary.py", "Niles boundary tests", "test"),
                _spec("tests/test_niles_album_review_packet.py", "Niles review tests", "test"),
                _spec("tests/test_struna_obscura_project_capsule.py", "Struna capsule tests", "test"),
            ),
            sqlite_read_model_integration_status="metadata_read_model_only_no_raw_audio_or_project_scan",
            mission_control_visibility_status="read-models exist; current app visibility not proven here",
            missing_next_pieces=(
                "operator-supplied governed metadata capture",
                "Mission Control visibility if needed",
                "no raw creative file ingest proof for future expansion",
            ),
            authority_boundary="metadata/review only; no raw session/audio/project folder scan or file mutation",
            ready_for=_ready(visibility_only=True, review_packet=True, live_workflow=False),
        ),
        RailSpec(
            rail_id="report_bridge_package_intake",
            rail_name="Report Bridge / package intake",
            domain="package_intake",
            operator_value="Imports bounded report/read-model packages without granting execution or deployment authority.",
            maturity="READ_MODEL_VISIBLE",
            steel_thread_stage_reached="package_intake_read_model_and_tests",
            key_files=(
                _spec("report_bridge.py", "report package intake", "code"),
                _spec("scripts/export_report_bridge_read_model.py", "Report Bridge exporter", "script"),
            ),
            generated_read_models=(
                _spec("generated/read_models/report_bridge.json", "Report Bridge read-model", "read_model"),
            ),
            tests=(
                _spec("tests/test_report_bridge.py", "Report Bridge tests", "test"),
                _spec("tests/test_report_bridge_read_model.py", "Report Bridge read-model tests", "test"),
            ),
            sqlite_read_model_integration_status="bounded_package_metadata_sqlite_read_model",
            mission_control_visibility_status="available as read-model surface",
            missing_next_pieces=(
                "client capsule boundary proof before external deployments",
                "operator review for any write-capable package paths",
            ),
            authority_boundary="package metadata/read-model only; no execution or deployment",
            ready_for=_ready(visibility_only=True, live_workflow=False),
        ),
        RailSpec(
            rail_id="deterministic_planner_builder_automation",
            rail_name="Deterministic planner/builder/automation build",
            domain="automation_builder",
            operator_value="Keeps builder/planner machinery classified and warning-only until governed execution is explicitly approved.",
            maturity="LEGACY_OR_REFERENCE_IN_REPO_A",
            steel_thread_stage_reached="active_machinery_classified_and_guardrailed",
            key_files=(
                _spec("builder_watcher.sh", "legacy builder watcher", "script", "legacy_or_reference_evidence_only"),
                _spec("active_machinery_block_later_guardrail.py", "block-later metadata guardrail", "code"),
                _spec("active_machinery_high_risk_quarantine.py", "warning-only quarantine read-model", "code"),
            ),
            generated_read_models=(
                _spec("generated/read_models/active_machinery_block_later_guardrail.json", "block-later guardrail", "read_model"),
                _spec("generated/read_models/active_machinery_high_risk_quarantine.json", "warning-only quarantine", "read_model"),
                _spec("generated/read_models/active_machinery_quarantine_decision_packet.json", "quarantine decision packet", "read_model"),
            ),
            tests=(
                _spec("tests/test_active_machinery_block_later_guardrail.py", "block-later guardrail tests", "test"),
                _spec("tests/test_active_machinery_high_risk_quarantine.py", "quarantine tests", "test"),
            ),
            sqlite_read_model_integration_status="warning_read_model_only_no_builder_runtime_activation",
            mission_control_visibility_status="read-models exist; no app execution surface",
            missing_next_pieces=(
                "keep block-later surfaces non-runnable",
                "do not resume planner/builder automation before authority/security threshold",
            ),
            authority_boundary="warning-only; no planner/builder/agent automation activation",
            ready_for=_ready(visibility_only=True, live_workflow=False),
            can_wait=True,
        ),
        RailSpec(
            rail_id="brain_dump_cue_intent_inbox",
            rail_name="Brain-dump / cue parser / intent inbox / dropped intents",
            domain="operator_intake",
            operator_value="Captures or classifies operator intent/cues without treating old freeform notes as truth.",
            maturity="READ_MODEL_VISIBLE",
            steel_thread_stage_reached="intent_and_dropped_intent_read_models_visible",
            key_files=(
                _spec("brain_dump_parser.py", "legacy brain dump parser", "code", "legacy_or_reference_evidence_only"),
                _spec("dropped_intent_registry.py", "dropped intent registry", "code"),
                _spec("operator_intent_core.py", "operator intent core", "code"),
                _spec("operator_action_inbox.py", "strict operator action request inbox", "code"),
            ),
            generated_read_models=(
                _spec("generated/read_models/dropped_intents.json", "dropped intents", "read_model"),
                _spec("generated/read_models/intent_router.json", "intent router", "read_model"),
                _spec("generated/read_models/operator_actions.json", "operator action posture", "read_model"),
            ),
            tests=(
                _spec("tests/test_dropped_intent_registry.py", "dropped intent tests", "test"),
                _spec("tests/test_operator_intent_core.py", "intent core tests", "test"),
                _spec("tests/test_operator_action_inbox.py", "operator action inbox tests", "test"),
            ),
            sqlite_read_model_integration_status="strict_inbox_and_read_models_exist_legacy_freeform_parser_reference_only",
            mission_control_visibility_status="read-model surfaces exist; write path remains backend-gated",
            missing_next_pieces=(
                "avoid broad Markdown/private note ingestion",
                "prove cue parser path is governed before use",
            ),
            authority_boundary="intent metadata only; no execution from freeform notes",
            ready_for=_ready(visibility_only=True, live_workflow=False),
        ),
        RailSpec(
            rail_id="mission_control_read_model_surfaces",
            rail_name="Mission Control-facing read-model surfaces",
            domain="operator_helm",
            operator_value="Shows operator-useful status from mirrored read-models without backend command paths.",
            maturity="READ_MODEL_VISIBLE",
            steel_thread_stage_reached="multiple_backend_read_models_mirrored_for_app_consumption",
            key_files=(
                _spec("generated_read_model_files.py", "safe generated read-model file set", "code"),
                _spec("read_model_shuttle.py", "read-model shuttle", "code"),
                _spec("mac_read_model_sync_agent.py", "Mac mirror sync agent", "code"),
            ),
            generated_read_models=(
                _spec("generated/read_models/sync_health.json", "sync health", "read_model"),
                _spec("generated/read_models/context_selection.json", "context selection", "read_model"),
                _spec("generated/read_models/helm_state.json", "helm state", "read_model"),
            ),
            tests=(
                _spec("tests/test_sync_read_model_mirror.py", "sync mirror tests", "test"),
                _spec("tests/test_pc_read_model_import_agent.py", "PC import agent tests", "test"),
                _spec("tests/test_context_selection_read_model.py", "context selection tests", "test"),
            ),
            sqlite_read_model_integration_status="generated_read_model_mirror_no_app_backend_execution",
            mission_control_visibility_status="central visibility rail; app changes out of scope here",
            missing_next_pieces=(
                "sync-health drift should be handled by existing sync lane if it matters",
                "surface new map after normal mirror loop",
            ),
            authority_boundary="read-only mirror; no backend commands from app",
            ready_for=_ready(visibility_only=True, live_workflow=False),
        ),
        RailSpec(
            rail_id="sync_mirror_read_model_trust",
            rail_name="Sync/mirror/read-model trust",
            domain="sync_trust",
            operator_value="Keeps PC/Mac read-model trust visible and prevents stale mirror state from masquerading as current.",
            maturity="READ_MODEL_VISIBLE",
            steel_thread_stage_reached="durable_sync_health_loop_modeled",
            key_files=(
                _spec("read_model_shuttle.py", "shuttle package builder", "code"),
                _spec("scripts/pc_read_model_import_agent.py", "PC import agent", "script"),
                _spec("scripts/export_sync_health_read_model.py", "sync health exporter", "script"),
            ),
            generated_read_models=(
                _spec("generated/read_models/sync_health.json", "sync health", "read_model"),
                _spec("generated/read_models/sync_health_OPERATOR.md", "sync health operator view", "read_model"),
            ),
            tests=(
                _spec("tests/test_read_model_shuttle.py", "shuttle tests", "test"),
                _spec("tests/test_pc_read_model_import_agent.py", "import agent tests", "test"),
                _spec("tests/test_sync_read_model_mirror.py", "sync tests", "test"),
            ),
            sqlite_read_model_integration_status="manifest_and_marker_based_sync_no_manual_copy_authority",
            mission_control_visibility_status="Mirror Trust surface consumes this posture",
            missing_next_pieces=(
                "do not commit unrelated volatile sync-health churn in unrelated lanes",
                "normal mirror loop should pick up new read-model",
            ),
            authority_boundary="transport/proof only; not source-of-truth edits",
            ready_for=_ready(visibility_only=True, live_workflow=False),
        ),
        RailSpec(
            rail_id="project_client_capsule_custom_build",
            rail_name="Project/client capsule/custom-build substrate",
            domain="custom_build_capsules",
            operator_value="Defines client/project capsules and custom-build detangling rules without generating client repos.",
            maturity="METADATA_ONLY",
            steel_thread_stage_reached="contracts_and_capsule_read_models",
            key_files=(
                _spec("custom_build_module_detangling_contract.py", "custom-build detangling contract", "code"),
                _spec("project_capsule.py", "project capsule read-model substrate", "code"),
                _spec("bundle_blueprint_planner.py", "bundle planner advisory manifest", "code"),
            ),
            generated_read_models=(
                _spec("generated/read_models/custom_build_module_detangling_contract.json", "custom-build contract", "read_model"),
                _spec("generated/read_models/project_capsules.json", "project capsules", "read_model"),
                _spec("generated/read_models/bundle_blueprint_planner.json", "bundle planner", "read_model"),
            ),
            tests=(
                _spec("tests/test_custom_build_module_detangling_contract.py", "custom-build tests", "test"),
                _spec("tests/test_project_capsule_read_model.py", "project capsule tests", "test"),
                _spec("tests/test_bundle_blueprint_planner.py", "bundle planner tests", "test"),
            ),
            sqlite_read_model_integration_status="metadata_contract_only_no_client_repo_generation",
            mission_control_visibility_status="read-model surfaces exist; no app change here",
            missing_next_pieces=(
                "future real custom-build pressure test",
                "do not extract modules abstractly before named workflow proof",
            ),
            authority_boundary="no physical module extraction, client repo generation, deployment, or customer authority",
            ready_for=_ready(visibility_only=True, live_workflow=False),
            can_wait=True,
        ),
        RailSpec(
            rail_id="operator_action_intent_gates",
            rail_name="Operator action path / action intent gates",
            domain="operator_action",
            operator_value="Provides the narrow SQLite-backed action request/inbox/receipt spine for allowlisted local actions.",
            maturity="APPROVAL_RECEIPT_READY",
            steel_thread_stage_reached="canonical_narrow_sqlite_request_approval_receipt_spine",
            key_files=(
                _spec("operator_action.py", "Operator Action SQLite spine", "code"),
                _spec("operator_action_inbox.py", "strict request inbox", "code"),
                _spec("operator_action_covenant.py", "operator action covenant", "code"),
            ),
            generated_read_models=(
                _spec("generated/read_models/operator_actions.json", "operator actions", "read_model"),
            ),
            tests=(
                _spec("tests/test_operator_action.py", "operator action tests", "test"),
                _spec("tests/test_operator_action_inbox.py", "operator action inbox tests", "test"),
                _spec("tests/test_operator_action_covenant.py", "covenant tests", "test"),
            ),
            sqlite_read_model_integration_status="active_narrow_sqlite_spine_for_allowlisted_local_actions",
            mission_control_visibility_status="read-model visible; Mission Control request writer remains separate future lane",
            missing_next_pieces=(
                "do not generalize to sends/runtime/browser",
                "future Mission Control request writer must stay marker/file-request only if built",
            ),
            authority_boundary="narrow allowlisted local actions only; not general external/send/runtime authority",
            ready_for=_ready(
                visibility_only=True,
                approval_request_contract=True,
                approval_receipt=True,
                live_workflow=False,
            ),
        ),
        RailSpec(
            rail_id="approval_request_receipt_execution_boundaries",
            rail_name="Approval request / approval receipt / execution boundaries",
            domain="authority_lifecycle",
            operator_value="Keeps review packet, request, receipt, and execution from collapsing into one unsafe authority object.",
            maturity="APPROVAL_REQUEST_CONTRACT_READY",
            steel_thread_stage_reached="request_contracts_and_receipt_rules_modeled_execution_blocked",
            key_files=(
                _spec("guardian_draft_approval_request_contract.py", "draft final-send approval request contract", "code"),
                _spec("guardian_hitl_sqlite_authority_contract.py", "canonical request/decision/receipt contract", "code"),
                _spec("capital_hilton_coupa_start_approval_packet.py", "start approval packet", "code"),
            ),
            generated_read_models=(
                _spec("generated/read_models/guardian_draft_approval_request_contract.json", "draft approval request contract", "read_model"),
                _spec("generated/read_models/guardian_hitl_sqlite_authority_contract.json", "authority contract", "read_model"),
                _spec("generated/read_models/capital_hilton_coupa_start_approval_packet.json", "start approval packet", "read_model"),
            ),
            tests=(
                _spec("tests/test_guardian_draft_approval_request_contract.py", "draft approval request tests", "test"),
                _spec("tests/test_guardian_hitl_sqlite_authority_contract.py", "authority contract tests", "test"),
                _spec("tests/test_capital_hilton_coupa_start_approval_packet.py", "start packet tests", "test"),
            ),
            sqlite_read_model_integration_status="request_contracts_defined_receipt_execution_future_only",
            mission_control_visibility_status="read-model surfaces exist; live approval request delivery not enabled",
            missing_next_pieces=(
                "specific final-send approval receipt contract",
                "request delivery remains future and non-live until prerequisites exist",
                "execution is later security-threshold work",
            ),
            authority_boundary="request/receipt/execution distinct; no live approval request, receipt, or executor",
            ready_for=_ready(
                visibility_only=True,
                approval_request_contract=True,
                approval_receipt=False,
                execution_gate=False,
                live_workflow=False,
            ),
        ),
    )


def _rail_record(spec: RailSpec, *, repo_root: str | Path) -> dict[str, Any]:
    if spec.maturity not in MATURITY_SCALE:
        raise ValueError(f"unsupported rail maturity: {spec.maturity}")
    if set(spec.ready_for) != set(READINESS_KEYS):
        raise ValueError(f"rail ready_for keys incomplete: {spec.rail_id}")
    key_files = [_evidence_record(item, repo_root=repo_root) for item in spec.key_files]
    read_models = [_evidence_record(item, repo_root=repo_root) for item in spec.generated_read_models]
    tests = [_evidence_record(item, repo_root=repo_root) for item in spec.tests]
    present_counts = {
        "key_files_present": sum(1 for item in key_files if item["present"]),
        "key_files_expected": len(key_files),
        "read_models_present": sum(1 for item in read_models if item["present"]),
        "read_models_expected": len(read_models),
        "tests_present": sum(1 for item in tests if item["present"]),
        "tests_expected": len(tests),
    }
    return {
        "rail_id": spec.rail_id,
        "rail_name": spec.rail_name,
        "domain": spec.domain,
        "operator_value": spec.operator_value,
        "maturity": spec.maturity,
        "steel_thread_stage_reached": spec.steel_thread_stage_reached,
        "what_exists": {
            "key_files": key_files,
            "generated_read_models": read_models,
            "tests": tests,
            "present_counts": present_counts,
        },
        "sqlite_read_model_integration_status": spec.sqlite_read_model_integration_status,
        "mission_control_visibility_status": spec.mission_control_visibility_status,
        "missing_next_pieces": list(spec.missing_next_pieces),
        "authority_boundary": spec.authority_boundary,
        "ready_for": dict(spec.ready_for),
        "ready_for_live_workflow": False,
        "live_authority_blocked": True,
        "security_threshold_audit_now": False,
        "security_threshold_audit_posture": "future_threshold_not_current_lane",
        "old_files_treated_as_evidence_not_truth": True,
        "can_wait": spec.can_wait,
    }


def unknown_rail_record(rail_name: str) -> dict[str, Any]:
    return {
        "rail_id": "unknown_unproven",
        "rail_name": rail_name,
        "maturity": "NOT_FOUND",
        "steel_thread_stage_reached": "not_proven",
        "ready_for": {key: False for key in READINESS_KEYS},
        "authority_boundary": "fail_closed_until_repo_a_evidence_exists",
        "operator_confirmation_needed": True,
        "old_files_treated_as_evidence_not_truth": True,
    }


def _recommended_lanes() -> list[dict[str, Any]]:
    lanes = [
        (
            "Capital Hilton Proof Metadata Capture v0",
            "Record operator-supplied protected proof metadata for Coupa payment invoice and Excel match when proof exists.",
            "Capital Hilton companion invoice final-send readiness",
            "protected_proof_metadata_gap",
            "capital_hilton_external_artifact_proof_capture_v0",
            "Reusable governed proof metadata capture for review packets.",
            "Capital Hilton proof rail read-model updated with real metadata/protected references or explicit pending state.",
            "generated/read_models/capital_hilton_external_artifact_proof_capture.json",
        ),
        (
            "Guardian Final-Send Approval Receipt Contract v0",
            "Define the future decision receipt shape for a specific Guardian final-send approval without dispatching it.",
            "Capital Hilton final-send approval lifecycle",
            "approval_receipt_gap",
            "guardian_draft_approval_request_contract_v0",
            "Reusable approval receipt contract for draft+attachment outward email workflows.",
            "Guardian final-send receipt contract read-model; no approval, send, or execution.",
            "generated/read_models/guardian_final_send_approval_receipt_contract.json",
        ),
        (
            "Niles Governed Metadata Review Packet Completion v0",
            "Bring the Niles/Struna creative rail to the same metadata/proof packet clarity without scanning creative files.",
            "Niles album and Struna creative project review",
            "metadata_review_packet_completion_gap",
            "niles_album_evidence_intake_boundary_v0",
            "Reusable metadata-only review packet completion pattern for non-finance rails.",
            "Niles/Struna operator review packet completion map and proof of no raw creative file ingest.",
            "generated/read_models/niles_album_review_packet.json",
        ),
    ]
    results: list[dict[str, Any]] = []
    for lane_name, summary, workflow, bottleneck, contract_link, substrate, proof_output, artifact_path in lanes:
        gate = evaluate_post_preflight_lane(
            lane_name=lane_name,
            lane_summary=summary,
            named_operator_workflow=workflow,
            shared_bottleneck=bottleneck,
            steel_thread_contract_link=contract_link,
            reusable_substrate_improvement=substrate,
            workflow_proof_output=proof_output,
            detangling_scope={
                "serves_lane_directly": True,
                "opportunistic_only": True,
                "physical_module_extraction_requested": False,
                "client_repo_generation_requested": False,
                "detangling_required_before_workflow_proof": False,
                "notes": "Record structural gaps without extracting modules or activating runtime.",
            },
            module_split_disposition={
                "disposition": "record_future_work",
                "recorded_future_work": True,
                "reason": "Any module split found should be recorded, not executed, before Repo B delta inspection.",
            },
            authority_change_requested={
                "requested": False,
                "authority_types": [],
                "reason": "Read-model/proof/contract completion only.",
            },
            expected_artifacts=[
                {"artifact_kind": "read_model", "path_or_contract": artifact_path},
                {"artifact_kind": "operator_packet", "path_or_contract": artifact_path.replace(".json", "_OPERATOR.md")},
                {"artifact_kind": "test_proof", "path_or_contract": "focused tests"},
            ],
            validation_required=("focused tests", "JSON validation", "authority boundary flags"),
            synthetic_example=False,
        )
        results.append(
            {
                "lane_name": lane_name,
                "why_before_repo_b": summary,
                "post_preflight_batch_gate_evaluation": gate,
            }
        )
    return results


def _eli5_summary(rails: list[dict[str, Any]], recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    tracked = [
        "Capital Hilton finance/Cassandra-Clara",
        "Cassandra draft review",
        "Guardian approval contracts",
        "Operator Action",
        "sync/Mission Control read-model visibility",
    ]
    partially_tracked = [
        "Chief planning/work packets",
        "Hermes advisory synthesis",
        "Niles album/Struna creative project rails",
        "planner/builder automation guardrails",
    ]
    not_yet_proven = [
        "real Coupa proof metadata",
        "specific final-send approval receipt",
        "live email/Coupa/browser/spreadsheet execution",
        "what Repo B still contains that Repo A has not already absorbed",
        "workflows Winship remembers but Repo A evidence has not proven yet",
    ]
    next_lanes = [item["lane_name"] for item in recommendations[:3]]
    return {
        "summary_text": (
            "Repo A already tracks the main rails: Capital Hilton finance, Cassandra review packets, "
            "Guardian approval boundaries, Operator Action, sync/Mission Control visibility, Niles/Struna, "
            "Report Bridge, and capsule/custom-build planning. Capital Hilton is the furthest along, but it "
            "is still intentionally blocked before anything live happens. Chief/Hermes/Niles/planner-builder "
            "rails are visible or partially modeled, not ready for authority. Repo B should wait until these "
            "known Repo A rails finish their proof/request/receipt gaps, so the later Repo B pass only hunts "
            "for true leftovers."
        ),
        "tracked": tracked,
        "partially_tracked": partially_tracked,
        "not_yet_proven": not_yet_proven,
        "blocked_on_purpose": [
            "live sends",
            "browser/Coupa",
            "credentials",
            "approval execution",
            "runtime/agent automation",
            "client deployment",
            "automatic repair",
        ],
        "next_1_to_3_sensible_lanes": next_lanes,
    }


def build_repo_a_known_rail_completion_map(
    *,
    repo_root: str | Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    rail_records = [_rail_record(spec, repo_root=repo_root) for spec in _rail_specs()]
    maturity_counts = Counter(item["maturity"] for item in rail_records)
    ready_counts = {
        key: sum(1 for item in rail_records if item["ready_for"][key])
        for key in READINESS_KEYS
    }
    recommendations = _recommended_lanes()
    gate_pass_count = sum(
        1
        for item in recommendations
        if item["post_preflight_batch_gate_evaluation"]["gate_status"] == PASS
    )
    rails_ready_enough = [
        item["rail_name"]
        for item in rail_records
        if item["ready_for"]["review_packet"]
        or item["ready_for"]["proof_packet"]
        or item["ready_for"]["approval_request_contract"]
    ]
    rails_needing_completion = [
        {
            "rail_id": item["rail_id"],
            "rail_name": item["rail_name"],
            "missing_next_pieces": item["missing_next_pieces"],
        }
        for item in rail_records
        if item["missing_next_pieces"] and not item["can_wait"]
    ]
    can_wait = [item["rail_name"] for item in rail_records if item["can_wait"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "codex",
        "generated_at": generated_at or utc_now(),
        "repo_scope": "Repo A only",
        "repo_b_inspected": False,
        "repo_b_delta_pass_prepared_not_run": True,
        "repo_b_delta_questions_for_later": list(REPO_B_DELTA_QUESTIONS),
        "security_pass_current": False,
        "security_pass_posture": "future_when_rails_approach_live_execution_threshold",
        "known_rail_count": len(rail_records),
        "maturity_scale": list(MATURITY_SCALE),
        "maturity_counts": dict(sorted(maturity_counts.items())),
        "readiness_keys": list(READINESS_KEYS),
        "readiness_counts": ready_counts,
        "rails": rail_records,
        "rails_ready_enough": rails_ready_enough,
        "rails_needing_completion_before_repo_b": rails_needing_completion,
        "rails_that_can_wait": can_wait,
        "must_not_activate_yet": [
            "live sends",
            "browser/Coupa",
            "credentials",
            "approval execution",
            "runtime/agent automation",
            "client deployment",
            "automatic repair",
        ],
        "recommended_next_lanes_before_repo_b": recommendations,
        "recommended_next_lanes_all_gate_pass": gate_pass_count == len(recommendations),
        "operator_eli5_summary": _eli5_summary(rail_records, recommendations),
        "unknown_rail_policy": unknown_rail_record("unproven remembered workflow"),
        "read_model_distinguishes_visibility_review_proof_approval_execution": True,
        "old_files_treated_as_evidence_not_truth": True,
        "no_authority_flags": dict(NO_AUTHORITY_FLAGS),
        **NO_AUTHORITY_FLAGS,
    }


def format_repo_a_known_rail_completion_map(payload: dict[str, Any]) -> str:
    eli5 = payload["operator_eli5_summary"]
    lines = [
        "# Repo A Known Rail Completion Map v0",
        "",
        "Status:",
        f"- Repo scope: `{payload['repo_scope']}`.",
        f"- Known rails classified: `{payload['known_rail_count']}`.",
        "- Repo B inspected: `false`.",
        "- Live execution/security threshold work started: `false`.",
        "",
        "## ELI5 Summary",
        eli5["summary_text"],
        "",
        "Tracked:",
    ]
    lines.extend(f"- {item}" for item in eli5["tracked"])
    lines.extend(["", "Partially tracked:"])
    lines.extend(f"- {item}" for item in eli5["partially_tracked"])
    lines.extend(["", "Not yet proven:"])
    lines.extend(f"- {item}" for item in eli5["not_yet_proven"])
    lines.extend(["", "## Maturity Counts"])
    for maturity, count in payload["maturity_counts"].items():
        lines.append(f"- `{maturity}`: {count}")
    lines.extend(["", "## Rails Needing Completion Before Repo B"])
    for item in payload["rails_needing_completion_before_repo_b"]:
        lines.append(f"- {item['rail_name']}: {', '.join(item['missing_next_pieces'][:3])}")
    lines.extend(["", "## Recommended Next Lanes"])
    for item in payload["recommended_next_lanes_before_repo_b"]:
        gate = item["post_preflight_batch_gate_evaluation"]
        lines.append(f"- `{item['lane_name']}`: gate `{gate['gate_status']}` - {item['why_before_repo_b']}")
    lines.extend(["", "## Blocked On Purpose"])
    lines.extend(f"- {item}" for item in payload["must_not_activate_yet"])
    lines.extend(["", "## Repo B Delta Questions For Later"])
    lines.extend(f"- {item}" for item in payload["repo_b_delta_questions_for_later"])
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class RepoAKnownRailCompletionMapExportResult:
    schema_version: str
    json_path: str
    operator_path: str
    known_rail_count: int
    repo_b_inspected: bool
    security_pass_current: bool
    live_workflow_ready_count: int
    runtime_authority_added: bool
    send_or_submit_authority_added: bool


def export_repo_a_known_rail_completion_map(
    *,
    repo_root: str | Path = ROOT,
    export_root: str | Path = DEFAULT_EXPORT_ROOT,
    generated_at: str | None = None,
) -> RepoAKnownRailCompletionMapExportResult:
    root = Path(repo_root)
    out_dir = root / export_root
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_repo_a_known_rail_completion_map(repo_root=repo_root, generated_at=generated_at)
    json_path = out_dir / JSON_EXPORT_NAME
    operator_path = out_dir / OPERATOR_EXPORT_NAME
    json_path.write_text(stable_json(payload), encoding="utf-8")
    operator_path.write_text(format_repo_a_known_rail_completion_map(payload), encoding="utf-8")
    return RepoAKnownRailCompletionMapExportResult(
        schema_version=SCHEMA_VERSION,
        json_path=_display_path(json_path),
        operator_path=_display_path(operator_path),
        known_rail_count=payload["known_rail_count"],
        repo_b_inspected=payload["repo_b_inspected"],
        security_pass_current=payload["security_pass_current"],
        live_workflow_ready_count=payload["readiness_counts"]["live_workflow"],
        runtime_authority_added=payload["runtime_authority_added"],
        send_or_submit_authority_added=payload["send_or_submit_authority_added"],
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Repo A known rail completion map read-model.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repo A root.")
    parser.add_argument("--export-root", default=str(DEFAULT_EXPORT_ROOT), help="Generated read-model export root.")
    parser.add_argument("--format", choices=("json", "operator"), default="operator")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else None)
    result = export_repo_a_known_rail_completion_map(
        repo_root=args.repo_root,
        export_root=args.export_root,
    )
    if args.format == "json":
        print(stable_json(result.__dict__), end="")
    else:
        payload = build_repo_a_known_rail_completion_map(repo_root=args.repo_root)
        print(format_repo_a_known_rail_completion_map(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

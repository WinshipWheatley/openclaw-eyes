"""OpenClaw System Knowledge Registry v0.

This registry is an inert documentation/read-model/SQLite surface for the
current local OpenClaw repo. It records safely discoverable components,
boundaries, unknowns, and build tasks. It does not call external services,
start runtimes, inspect credentials, mutate business records, or grant
authority.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
READ_MODEL_ID = "openclaw_system_knowledge_registry"
SCHEMA_VERSION = "openclaw_system_knowledge_registry_v0"
REGISTRY_NAME = "OpenClaw System Knowledge Registry"
DEFAULT_GENERATED_AT = "2026-06-13T00:00:00+00:00"

READ_MODEL_DIR = Path("generated/read_models")
SYSTEM_KNOWLEDGE_DIR = Path("generated/system_knowledge")
JSON_EXPORT_NAME = f"{READ_MODEL_ID}.json"
OPERATOR_EXPORT_NAME = f"{READ_MODEL_ID}_OPERATOR.md"
SQLITE_EXPORT_NAME = f"{READ_MODEL_ID}.sqlite"
SCHEMA_SQL_EXPORT_NAME = f"{READ_MODEL_ID}_SCHEMA.sql"
SEED_SQL_EXPORT_NAME = f"{READ_MODEL_ID}_SEED.sql"

REQUIRED_TABLES = (
    "system_component",
    "capability",
    "workflow_rail",
    "brain_route_inventory",
    "orchestration_decision",
    "knowledge_claim",
    "known_unknown",
    "build_task",
    "agent_role",
    "artifact_policy",
    "authority_boundary",
    "safety_posture",
    "advice_integrity_receipt",
)

TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "system_component": (
        "component_id",
        "display_name",
        "component_type",
        "evidence_status",
        "evidence_paths_json",
        "summary",
        "authority_boundary",
    ),
    "capability": (
        "capability_id",
        "component_id",
        "capability_name",
        "evidence_status",
        "evidence_basis",
        "boundary",
    ),
    "workflow_rail": (
        "workflow_id",
        "component_id",
        "rail_name",
        "evidence_status",
        "evidence_basis",
        "boundary",
    ),
    "brain_route_inventory": (
        "brain_id",
        "legacy_router_wired",
        "current_state",
        "mission_lane",
        "disposition_action",
        "compose_status",
        "evidence_ref",
        "boundary",
    ),
    "orchestration_decision": (
        "decision_id",
        "source_ref",
        "decision",
        "status",
        "boundary",
        "next_safe_action",
    ),
    "knowledge_claim": (
        "claim_id",
        "subject",
        "claim",
        "evidence_status",
        "evidence_paths_json",
        "confidence",
    ),
    "known_unknown": (
        "unknown_id",
        "subject",
        "unknown_status",
        "reason",
        "next_safe_check",
    ),
    "build_task": (
        "task_id",
        "task_rank",
        "title",
        "owner_lane",
        "rationale",
        "status",
        "boundary",
    ),
    "agent_role": (
        "role_id",
        "agent_name",
        "role_summary",
        "evidence_status",
        "evidence_paths_json",
        "authority_notes",
    ),
    "artifact_policy": (
        "policy_id",
        "artifact_name",
        "allowed_surfaces",
        "blocked_actions",
        "evidence_basis",
        "evidence_status",
    ),
    "authority_boundary": (
        "boundary_id",
        "boundary_name",
        "allowed",
        "blocked",
        "evidence_basis",
        "notes",
    ),
    "safety_posture": (
        "posture_id",
        "posture_name",
        "state",
        "evidence_basis",
        "operator_summary",
        "next_safe_action",
    ),
    "advice_integrity_receipt": (
        "receipt_id",
        "desired_outcome",
        "verified_constraints",
        "protected_currencies_considered",
        "minimum_sufficient_option",
        "recommended_posture",
        "premium_justification",
        "restraint_rationale",
        "integrity_tests_applied",
        "client_agency_preserved",
        "commercial_interest_alignment",
        "trust_gear_state",
        "agent_contributions",
        "evidence_refs",
        "generated_at",
        "status",
    ),
}

AUTHORITY_BOUNDARY = {
    "documentation_read_model_sqlite_only": True,
    "live_automation_granted": False,
    "runtime_service_mutation_allowed": False,
    "email_gmail_send_or_draft_allowed": False,
    "browser_coupa_bank_access_allowed": False,
    "workbook_pdf_ledger_invoice_mutation_allowed": False,
    "confirmed_reference_data_mutation_allowed": False,
    "daw_media_session_mutation_allowed": False,
    "live_model_invocation_allowed": False,
    "guardian_approval_bypass_allowed": False,
    "git_push_or_merge_allowed": False,
    "hermes_start_allowed": False,
    "niles_daw_daemon_start_allowed": False,
}


def _component(
    component_id: str,
    display_name: str,
    component_type: str,
    evidence_status: str,
    evidence_paths: list[str],
    summary: str,
    authority_boundary: str,
) -> dict[str, Any]:
    return {
        "component_id": component_id,
        "display_name": display_name,
        "component_type": component_type,
        "evidence_status": evidence_status,
        "evidence_paths": evidence_paths,
        "summary": summary,
        "authority_boundary": authority_boundary,
    }


COMPONENTS: tuple[dict[str, Any], ...] = (
    _component(
        "cassandra",
        "Cassandra",
        "operator_agent",
        "CONFIRMED_LOCAL",
        [
            "cassandra_listener.py",
            "cassandra_brain.py",
            "cassandra_guided_review.py",
            ".claude/commands/cassandra.md",
        ],
        "Cassandra owns operator communications, guided review, universal intake surfaces, and exact-send request state.",
        "Cassandra must not send email, create drafts, mutate business systems, create approvals, or promote reference data without separate gates.",
    ),
    _component(
        "chief",
        "Chief",
        "operator_agent",
        "CONFIRMED_LOCAL",
        ["chief_router.py", "chief_listener.py", "chief_ops_brain.py"],
        "Chief coordinates system status, diagnostics, routing, and operator-facing build/readiness work.",
        "Chief records and routes; it does not bypass Guardian, push, merge, or execute protected business actions.",
    ),
    _component(
        "guardian",
        "Guardian",
        "safety_agent",
        "CONFIRMED_LOCAL",
        ["guardian_protected_access_gate_spec.py", "chief_guardian_listener.py", "hitl_action_service.py"],
        "Guardian is the approval and protected-action boundary for high-risk requests.",
        "Guardian approves or denies; it does not execute business logic or mutate protected systems.",
    ),
    _component(
        "niles",
        "Niles",
        "creative_lane",
        "CONFIRMED_LOCAL_LOGICAL",
        [".claude/commands/niles.md", "agent_lane_registry.py", "niles_album_metadata_intake_packet.py"],
        "Niles is a logical/spawned creative lane for music and album context.",
        "No Niles DAW daemon or media/session mutation is authorized by this registry.",
    ),
    _component(
        "hermes",
        "Hermes",
        "architecture_lane",
        "CONFIRMED_LOCAL_BOUNDARY",
        [".claude/commands/hermes.md", "openclaw_hermes_sidecar.py", "tool_protocol_adapter_registry_contract.py"],
        "Hermes is an architecture and adapter-boundary lane with sidecar planning artifacts.",
        "Hermes remains unsafe_to_start here; no generic sidecar launch is authorized.",
    ),
    _component(
        "watch_desk",
        "Watch Desk",
        "operator_display",
        "CONFIRMED_LOCAL",
        ["watch_desk_feed.py", "generated/read_models/watch_desk_feed.json"],
        "Watch Desk projects current operator-facing items from read models and receipts.",
        "Display and triage only; no automatic execution authority.",
    ),
    _component(
        "universal_intake",
        "Universal Operator Intake",
        "intake_router",
        "CONFIRMED_LOCAL",
        ["operator_universal_intake.py", "operator_intake_events.py", "generated/read_models/operator_intake_events.json"],
        "Universal Intake classifies local operator messages into income, expense, gig, identity, lane, and approval-gated request records.",
        "Local receipt/intake only; no invoice paid marking, email send, or ledger/workbook mutation.",
    ),
    _component(
        "context_switchboard",
        "Operator Context Switchboard",
        "context_router",
        "CONFIRMED_LOCAL",
        ["operator_context_switchboard.py", "generated/read_models/operator_active_contexts.json", "cassandra_brain.py"],
        "Context Switchboard maintains active/resumable operator contexts and protects lane switching.",
        "Context routing is not authority to answer stale questions or mutate unrelated lanes.",
    ),
    _component(
        "guided_review_coach",
        "Guided Review / Coach Mode",
        "review_system",
        "CONFIRMED_LOCAL",
        ["cassandra_guided_review.py", "cassandra_review_coach.py", "cassandra_review_coach_packs.py"],
        "Guided Review and Coach Mode run provisional Data Room review sessions with explanatory coach replies.",
        "Review sessions remain authoritative=false and runtime_policy_changed=false until later promotion.",
    ),
    _component(
        "data_room_form_fill_lane",
        "Data Room form-fill lane",
        "manual_model_handoff",
        "CONFIRMED_LOCAL",
        ["data_room_form_fill_package.py", "tests/test_data_room_form_fill_package.py"],
        "Packages the Data Room review as a redacted form and paste-ready manual ChatGPT 5.5 prompt.",
        "Manual handoff only unless a separate live adapter is verified; model text advises and OpenClaw records only confirmed provisional answers.",
    ),
    _component(
        "model_work_package_router",
        "Model Work Package Router",
        "work_package_router",
        "CONFIRMED_LOCAL",
        ["model_work_package_router.py", "tests/test_model_work_package_router.py"],
        "Routes model/work packages through bounded metadata and permission boundaries.",
        "No model/package output directly mutates runtime or protected state.",
    ),
    _component(
        "assignment_loop_contract",
        "Assignment Loop Contract",
        "worker_contract",
        "CONFIRMED_LOCAL",
        ["assignment_loop_contract.py", "tests/test_assignment_loop_contract.py"],
        "Defines bounded worker assignments with goal, sources, standard, proof, permissions, and stop conditions.",
        "READY requires proof; parking lot and Watch Desk are status surfaces, not authority grants.",
    ),
    _component(
        "worker_run_manager",
        "Worker Run Manager",
        "worker_lifecycle",
        "CONFIRMED_LOCAL",
        ["scripts/openclaw_run.py", "worker_run_manager.py", "tests/test_codex_work_package_lifecycle.py"],
        "Manages package lifecycle, dispatch claims, ingest records, and package read models without calling external workers.",
        "Lifecycle bookkeeping only unless a separate worker execution is explicitly approved.",
    ),
    _component(
        "reference_data_hydration",
        "Reference Data Hydration",
        "data_room_pipeline",
        "CONFIRMED_BLOCKED_UNTIL_CONFIRMED_DATA",
        ["reference_data_hydration.py", "generated/read_models/reference_data_hydration_status.json"],
        "Hydrates confirmed Data Room reference data when confirmed data exists.",
        "Blocked until confirmed reference data exists; no provisional review answer is runtime truth.",
    ),
    _component(
        "artifact_link_normalizer",
        "Artifact Link Normalizer",
        "operator_artifact_export",
        "CONFIRMED_LOCAL",
        ["scripts/operator_artifact_link_normalizer.py", "docs/operator_artifact_links.md", "tests/test_operator_artifact_link_normalizer.py"],
        "Copies intended operator-facing artifacts to Windows-openable report folders and writes manifests.",
        "Copies only intended artifacts; refuses secret-looking paths and never moves originals.",
    ),
    _component(
        "pc_mac_sync",
        "PC/Mac Sync",
        "sync_boundary",
        "PARTIAL_LOCAL",
        ["read_model_shuttle.py", "generated/read_models/sync_health.json", "/mnt/e/openclaw/mac_generated_read_models_manifest.json"],
        "Tracks read-model shuttle and PC/Mac generated artifact sync posture.",
        "Registry does not sync, copy, delete, quarantine, import maps, or start Mac jobs.",
    ),
    _component(
        "invoice_ledger_discovery",
        "Invoice/Ledger discovery",
        "finance_boundary",
        "CONFIRMED_LOCAL_BOUNDARY",
        ["capital_hilton_*", "proof_to_response_runtime.py", "operator_controller_event_router.py"],
        "Finance routes can explain proof state, payment watch, and candidate evidence posture.",
        "No paid marking, ledger posting, workbook mutation, Coupa/browser/Gmail access, or submit action is authorized.",
    ),
    _component(
        "voice_kokoro_caveat",
        "Voice/Kokoro caveat",
        "voice_side_effect",
        "CONFIRMED_DEGRADED_OR_NONCANONICAL",
        ["cassandra_voice.py", "cassandra_listener.py", "/mnt/c/OpenClaw/logs/cassandra_listener.out"],
        "Voice/Kokoro may be degraded or side-effect-only; text route is canonical.",
        "Registry does not fix, start, or depend on voice playback.",
    ),
    _component(
        "compose_gate_pipeline",
        "Compose/Gate Pipeline",
        "operator_front_door",
        "CONFIRMED_LOCAL",
        [
            "compose_contract.py",
            "chief_compose.py",
            "/mnt/e/openclaw/orchestration/artifacts/COMPOSER_GATE_PIPELINE_DESIGN.md",
        ],
        "The compose front door routes redacted operator text to read-only handlers or G3 packet approval.",
        "Executor registry is intentionally empty unless a separate approved executor is registered.",
    ),
    _component(
        "orbit_brain_map",
        "Orbit Brain Map",
        "system_map",
        "CONFIRMED_ORCHESTRATION_SOURCE",
        [
            "/mnt/e/openclaw/orchestration/artifacts/orbit_brain_map.md",
            "/mnt/e/openclaw/orchestration/artifacts/orbit_lockin.md",
        ],
        "Structured inventory of old-router brains and their WIRE/RETIRE/VERIFY disposition into compose.",
        "Map is a planning/source inventory record; it does not start brains or grant runtime authority.",
    ),
    _component(
        "gig_intake_flow",
        "Gig Intake Flow",
        "business_intake_flow",
        "CONFIRMED_LOCAL",
        [
            "gig_intake.py",
            "tests/test_gig_intake.py",
            "/mnt/e/openclaw/orchestration/artifacts/gig_intake_flow_design.md",
            "/mnt/e/openclaw/orchestration/artifacts/gig_slot_schema.json",
        ],
        "Cassandra can collect gig facts, persist session state, and stage approval packets for intro email and invoice.",
        "No send or invoice execution occurs without explicit approval and a future registered executor.",
    ),
    _component(
        "correspondence_agent_plan",
        "Correspondence Agent Plan",
        "correspondence_design",
        "PLANNED_SEND_HOLD",
        ["/mnt/e/openclaw/orchestration/artifacts/correspondence_agent_spec.md"],
        "Design for watch, understand, calendar-aware draft, and gate loop for inbound correspondence.",
        "Gmail body scope and live send remain unapproved; SEND_HOLD keeps this design non-executing.",
    ),
    _component(
        "approval_gate_convergence",
        "Approval Gate Convergence",
        "gate_convergence",
        "CONFIRMED_LOCAL",
        ["approval_gate_convergence.py", "chief_compose.py", "tests/test_approval_gate_convergence.py"],
        "Legacy email/SMS/approval surfaces converge onto the G3 packet gate in compose preview metadata.",
        "No legacy direct send, double gate, executor registration, or external send authority is granted.",
    ),
    _component(
        "system_knowledge_query",
        "System Knowledge Registry Query",
        "agent_query_surface",
        "CONFIRMED_LOCAL",
        ["openclaw_system_knowledge_registry.py", "tests/test_openclaw_system_knowledge_registry.py"],
        "Deterministic helper for agents to answer system-shape, known-unknown, orbit, and task questions from registry/ledger/atlas data.",
        "Registry query is read-only and does not call models, tools, runtimes, services, or external APIs.",
    ),
)

ORBIT_BRAIN_ROUTE_RECORDS: tuple[dict[str, str], ...] = (
    {
        "brain_id": "chief_musiclaw_brain",
        "legacy_router_wired": "yes",
        "current_state": "real",
        "mission_lane": "legal/high",
        "disposition_action": "WIRE",
        "compose_status": "read_only_category_added",
        "evidence_ref": "orbit_brain_map.md; intent_router.py",
        "boundary": "read-only Q&A; no legal advice authority",
    },
    {
        "brain_id": "chief_publishing_brain",
        "legacy_router_wired": "yes",
        "current_state": "real",
        "mission_lane": "rights/high",
        "disposition_action": "WIRE",
        "compose_status": "read_only_category_added",
        "evidence_ref": "orbit_brain_map.md; intent_router.py",
        "boundary": "read-only rights/catalog posture only",
    },
    {
        "brain_id": "chief_cpa_brain",
        "legacy_router_wired": "yes",
        "current_state": "real",
        "mission_lane": "finance/high",
        "disposition_action": "WIRE",
        "compose_status": "read_only_category_added",
        "evidence_ref": "orbit_brain_map.md; intent_router.py",
        "boundary": "read-only tax/accounting orientation; no tax advice or filing",
    },
    {
        "brain_id": "chief_financial_brain",
        "legacy_router_wired": "yes",
        "current_state": "real",
        "mission_lane": "finance/high",
        "disposition_action": "WIRE",
        "compose_status": "read_only_category_added",
        "evidence_ref": "orbit_brain_map.md; intent_router.py",
        "boundary": "read-only finance reports; no ledger mutation",
    },
    {
        "brain_id": "chief_invoice_brain",
        "legacy_router_wired": "no_or_orphaned",
        "current_state": "legacy",
        "mission_lane": "booking/med",
        "disposition_action": "RETIRE",
        "compose_status": "not_wired_retire_candidate",
        "evidence_ref": "orbit_brain_map.md; orbit_lockin.md",
        "boundary": "do not use for invoice authority; superseded by billing/gig flows",
    },
    {
        "brain_id": "chief_email_brain",
        "legacy_router_wired": "yes",
        "current_state": "real",
        "mission_lane": "finance/high",
        "disposition_action": "WIRE_G3_GATE",
        "compose_status": "g3_convergence_metadata_added",
        "evidence_ref": "orbit_brain_map.md; approval_gate_convergence.py",
        "boundary": "draft/gate only; no executor registered under SEND_HOLD",
    },
    {
        "brain_id": "chief_sms_brain",
        "legacy_router_wired": "yes",
        "current_state": "real",
        "mission_lane": "finance/high",
        "disposition_action": "WIRE_G3_GATE",
        "compose_status": "g3_convergence_metadata_added",
        "evidence_ref": "orbit_brain_map.md; approval_gate_convergence.py",
        "boundary": "draft/gate only; no executor registered under SEND_HOLD",
    },
    {
        "brain_id": "chief_watcher_brain",
        "legacy_router_wired": "partial",
        "current_state": "real",
        "mission_lane": "ops/high",
        "disposition_action": "VERIFY",
        "compose_status": "verified_active_service_not_compose_wired",
        "evidence_ref": "orbit_lockin.md",
        "boundary": "background alerter only; no send or mutation authority",
    },
    {
        "brain_id": "chief_billing_brain",
        "legacy_router_wired": "not_in_original_sweep",
        "current_state": "real",
        "mission_lane": "finance/high",
        "disposition_action": "PARK_FOR_GATED_BILLING_FLOW",
        "compose_status": "surveyed_mixed_write_session_surface",
        "evidence_ref": "orbit_lockin.md; chief_billing_brain.py",
        "boundary": "must route through gated billing/gig/invoice flows, not generic read-only",
    },
    {
        "brain_id": "read_only_orbit_brain_group",
        "legacy_router_wired": "yes",
        "current_state": "real",
        "mission_lane": "independent_artist_stack",
        "disposition_action": "WIRE",
        "compose_status": "pc12_categories_added",
        "evidence_ref": "intent_router.py; tests/test_orbit_compose_wiring.py",
        "boundary": "read-only categories only; write-like phrases fail closed to gated paths",
    },
)

ORCHESTRATION_DECISIONS: tuple[dict[str, str], ...] = (
    {
        "decision_id": "decision_compose_front_door",
        "source_ref": "INTEGRATION_MAP.md; COMPOSER_GATE_PIPELINE_DESIGN.md",
        "decision": "compose(text) is the one operator front door.",
        "status": "accepted",
        "boundary": "read-only fast path or G3 packet path; no direct executor by default",
        "next_safe_action": "Keep adding intent categories and packet previews through compose.",
    },
    {
        "decision_id": "decision_generated_churn_not_authority",
        "source_ref": "board.md DECISIONS",
        "decision": "Volatile generated snapshots are not source-of-truth changes by themselves.",
        "status": "accepted",
        "boundary": "Do not stage unrelated generated runtime drift.",
        "next_safe_action": "Commit source/test/read-model artifacts intentionally by task.",
    },
    {
        "decision_id": "decision_square_payment_rail",
        "source_ref": "board.md DECISIONS",
        "decision": "Square is approved as a payment rail, while branded invoice artifacts remain what the client sees.",
        "status": "approved_direction_not_executor",
        "boundary": "No Square publish/send while SEND_HOLD is active.",
        "next_safe_action": "Use Square sandbox/spec work only until hold is lifted and executor is approved.",
    },
    {
        "decision_id": "decision_first_real_send_reynolds",
        "source_ref": "board.md DECISIONS; artifacts/reynolds",
        "decision": "First real send target is Reynolds Tavern, not Capital Hilton.",
        "status": "accepted_planning_target",
        "boundary": "Drafts only until executors are wired and Winship approves.",
        "next_safe_action": "Stage Reynolds packets; do not send under SEND_HOLD.",
    },
    {
        "decision_id": "decision_send_hold_active",
        "source_ref": "SEND_HOLD.md",
        "decision": "No external sends of any kind until the hold is explicitly lifted.",
        "status": "active_boundary",
        "boundary": "No email, SMS, Square publish/send, outbound third-party Telegram, calendar invites, or posting.",
        "next_safe_action": "Continue drafting, designing, contract tests, and safetied wiring only.",
    },
)

CAPABILITIES: tuple[dict[str, str], ...] = (
    {
        "capability_id": "capability_guided_review",
        "component_id": "guided_review_coach",
        "capability_name": "Provisional guided review with coach explanation",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "cassandra_guided_review.py and cassandra_review_coach.py",
        "boundary": "authoritative=false; runtime_policy_changed=false; promotion later",
    },
    {
        "capability_id": "capability_form_fill_prompt",
        "component_id": "data_room_form_fill_lane",
        "capability_name": "Redacted manual ChatGPT 5.5 form-fill prompt",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "data_room_form_fill_package.py",
        "boundary": "manual handoff only; no live model call by registry",
    },
    {
        "capability_id": "capability_operator_intake",
        "component_id": "universal_intake",
        "capability_name": "Local operator intake classification and receipts",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "operator_universal_intake.py",
        "boundary": "local receipt only; no protected business action",
    },
    {
        "capability_id": "capability_worker_lifecycle",
        "component_id": "worker_run_manager",
        "capability_name": "Worker package dispatch/claim/ingest lifecycle",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "worker_run_manager.py and scripts/openclaw_run.py",
        "boundary": "no worker/model/API call unless separately approved",
    },
    {
        "capability_id": "capability_artifact_export",
        "component_id": "artifact_link_normalizer",
        "capability_name": "Operator-openable artifact copy and manifest",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "scripts/operator_artifact_link_normalizer.py",
        "boundary": "copy intended artifacts only; no secret path export",
    },
    {
        "capability_id": "capability_gig_intake_flow",
        "component_id": "gig_intake_flow",
        "capability_name": "Conversational gig fact intake and approval packet staging",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "gig_intake.py and orchestration gig intake design",
        "boundary": "records candidate gig facts and pending packets only; no send/execution",
    },
    {
        "capability_id": "capability_correspondence_agent_plan",
        "component_id": "correspondence_agent_plan",
        "capability_name": "Correspondence watcher/draft/gate design",
        "evidence_status": "PLANNED_SEND_HOLD",
        "evidence_basis": "correspondence_agent_spec.md",
        "boundary": "metadata/design only until Gmail scope and executor approval are resolved",
    },
    {
        "capability_id": "capability_legacy_gate_convergence",
        "component_id": "approval_gate_convergence",
        "capability_name": "Single G3 gate metadata for legacy email/SMS surfaces",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "approval_gate_convergence.py",
        "boundary": "no double-gate, no direct legacy send, no registered executor",
    },
    {
        "capability_id": "capability_system_knowledge_query",
        "component_id": "system_knowledge_query",
        "capability_name": "Agent-queryable registry answers",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "query_system_knowledge_registry",
        "boundary": "answers from registry/ledger/atlas metadata only; no LLM guess or live authority",
    },
)

WORKFLOW_RAILS: tuple[dict[str, str], ...] = (
    {
        "workflow_id": "rail_data_room_review",
        "component_id": "guided_review_coach",
        "rail_name": "Data Room provisional guided review",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "guided_review_sessions read model and Cassandra guided review code",
        "boundary": "answers are provisional pending promotion",
    },
    {
        "workflow_id": "rail_data_room_form_fill",
        "component_id": "data_room_form_fill_lane",
        "rail_name": "Manual ChatGPT 5.5 Data Room form-fill handoff",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "package/prompt/state artifacts",
        "boundary": "external model response is candidate text, not truth",
    },
    {
        "workflow_id": "rail_payment_watch",
        "component_id": "invoice_ledger_discovery",
        "rail_name": "Finance payment watch proof-to-response",
        "evidence_status": "CONFIRMED_LOCAL_BOUNDARY",
        "evidence_basis": "proof_to_response_runtime.py and controller event router status",
        "boundary": "explain/attach proof only; no mark paid or ledger mutation",
    },
    {
        "workflow_id": "rail_assignment_loop",
        "component_id": "assignment_loop_contract",
        "rail_name": "Bounded assignment lifecycle",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "assignment_loop_contract.py",
        "boundary": "no READY without proof and receipts",
    },
    {
        "workflow_id": "rail_compose_gate_pipeline",
        "component_id": "compose_gate_pipeline",
        "rail_name": "Compose front door to read-only or G3 packet",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "compose_contract.py, chief_compose.py, tests/test_chief_compose_contract.py",
        "boundary": "executor registry empty by default",
    },
    {
        "workflow_id": "rail_reynolds_gig_intake",
        "component_id": "gig_intake_flow",
        "rail_name": "Reynolds-style gig intake and handoff",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "tests/test_gig_intake.py and artifacts/reynolds",
        "boundary": "candidate gig metadata and pending approval packets only",
    },
    {
        "workflow_id": "rail_correspondence_watcher_plan",
        "component_id": "correspondence_agent_plan",
        "rail_name": "Inbound correspondence watcher/draft/gate loop",
        "evidence_status": "PLANNED_SEND_HOLD",
        "evidence_basis": "correspondence_agent_spec.md",
        "boundary": "no Gmail body assumption, no send, no executor registration",
    },
)

KNOWLEDGE_CLAIMS: tuple[dict[str, Any], ...] = (
    {
        "claim_id": "claim_models_advise_openclaw_records",
        "subject": "Model authority",
        "claim": "Models advise; OpenClaw records deterministic state after validation and confirmation.",
        "evidence_status": "CONFIRMED_LOCAL_DOCTRINE",
        "evidence_paths": ["data_room_form_fill_package.py", "proof_to_response_runtime.py"],
        "confidence": "high",
    },
    {
        "claim_id": "claim_guardian_approval_boundary",
        "subject": "Guardian",
        "claim": "Guardian approval remains separate from business execution and cannot be bypassed by registry output.",
        "evidence_status": "CONFIRMED_LOCAL_DOCTRINE",
        "evidence_paths": ["guardian_protected_access_gate_spec.py", "hitl_action_service.py"],
        "confidence": "high",
    },
    {
        "claim_id": "claim_reference_data_not_confirmed_by_review",
        "subject": "Data Room",
        "claim": "Guided review and form-fill outputs are provisional until a later promotion/hydration lane runs.",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": ["cassandra_guided_review.py", "reference_data_hydration.py"],
        "confidence": "high",
    },
    {
        "claim_id": "claim_text_route_canonical",
        "subject": "Cassandra voice",
        "claim": "Text route is canonical; voice/Kokoro can degrade without blocking text operation.",
        "evidence_status": "CONFIRMED_LOCAL_CAVEAT",
        "evidence_paths": ["cassandra_listener.py", "cassandra_voice.py"],
        "confidence": "medium",
    },
    {
        "claim_id": "claim_orchestration_share_not_machine_record",
        "subject": "Orchestration workspace",
        "claim": "The shared orchestration folder is a working bus; durable decisions must land in the registry or ledger.",
        "evidence_status": "CONFIRMED_OPERATOR_DIRECTION",
        "evidence_paths": ["/mnt/e/openclaw/orchestration/inbox/to-codex-pc/0006-land-into-canonical-stores.md"],
        "confidence": "high",
    },
    {
        "claim_id": "claim_orbit_brains_are_wiring_work",
        "subject": "Orbit brain map",
        "claim": "Most old-router brains are real logic needing compose wiring, not rebuilds.",
        "evidence_status": "CONFIRMED_ORCHESTRATION_SOURCE",
        "evidence_paths": ["/mnt/e/openclaw/orchestration/artifacts/orbit_brain_map.md"],
        "confidence": "medium",
    },
    {
        "claim_id": "claim_send_hold_active",
        "subject": "SEND_HOLD",
        "claim": "External sends remain blocked while SEND_HOLD is active.",
        "evidence_status": "CONFIRMED_ACTIVE_BOUNDARY",
        "evidence_paths": ["/mnt/e/openclaw/orchestration/SEND_HOLD.md"],
        "confidence": "high",
    },
)

KNOWN_UNKNOWNS: tuple[dict[str, str], ...] = (
    {
        "unknown_id": "unknown_missing_prior_commit",
        "subject": "Reported local registry commit",
        "unknown_status": "UNKNOWN_UNREACHABLE",
        "reason": "Commit c5b83f6cda91daf25b95367e6d94e0d8890ffea3, branch, and patch were not found locally.",
        "next_safe_check": "Use this rebuilt branch/patch as the review source unless the original commit is later restored.",
    },
    {
        "unknown_id": "unknown_live_chatgpt55_adapter",
        "subject": "Live ChatGPT 5.5 advisory path",
        "unknown_status": "NOT_VERIFIED_AS_LIVE_ADAPTER",
        "reason": "Current form-fill lane can package manual prompts; no verified live ChatGPT 5.5 adapter is proven by this registry.",
        "next_safe_check": "Build a separate approved adapter readiness lane before claiming a live ChatGPT brain.",
    },
    {
        "unknown_id": "unknown_external_repo_a",
        "subject": "External Repo A",
        "unknown_status": "UNKNOWN_EXTERNAL",
        "reason": "Local read-models mention Repo A, but the external repo itself is not present in this checkout.",
        "next_safe_check": "Inspect the intended external repository in its own checkout when provided.",
    },
    {
        "unknown_id": "unknown_external_repo_b",
        "subject": "External Repo B",
        "unknown_status": "UNKNOWN_EXTERNAL",
        "reason": "Local read-models mention Repo B/runtime intake, but external repo contents are absent from this checkout.",
        "next_safe_check": "Reconcile the cross-repo estate map with explicit repo paths or remotes.",
    },
    {
        "unknown_id": "unknown_mac_map_import_agent",
        "subject": "Mac stable map import",
        "unknown_status": "KNOWN_GAP",
        "reason": "Prior sync verification separated map import gap from read-model sync.",
        "next_safe_check": "Create or run mac_map_import_agent in a separate sync lane.",
    },
    {
        "unknown_id": "unknown_confirmed_reference_data",
        "subject": "Confirmed reference data",
        "unknown_status": "BLOCKING_ABSENCE_OR_NOT_CONFIRMED_HERE",
        "reason": "Hydration waits for confirmed reference data; this registry does not create it.",
        "next_safe_check": "Run a separate promotion task over confirmed guided-review answers.",
    },
    {
        "unknown_id": "unknown_runtime_service_freshness",
        "subject": "Runtime service state",
        "unknown_status": "OUT_OF_SCOPE",
        "reason": "Task prohibits runtime service mutation; registry does not assert current daemon freshness.",
        "next_safe_check": "Use a verify-only runtime readiness lane if service freshness matters.",
    },
    {
        "unknown_id": "unknown_private_finance_truth",
        "subject": "Private finance proofs",
        "unknown_status": "BLOCKED_BY_BOUNDARY",
        "reason": "Registry does not inspect raw private finance documents, ledgers, workbooks, bank records, or portal data.",
        "next_safe_check": "Use redacted proof-bundle and evidence-intake lanes with explicit permission.",
    },
    {
        "unknown_id": "unknown_correspondence_gmail_scope",
        "subject": "Correspondence watcher Gmail scope",
        "unknown_status": "OPERATOR_SCOPE_DECISION_REQUIRED",
        "reason": "Correspondence scaffold is present, but real Gmail body reading still needs a metadata-vs-readonly-body scope decision.",
        "next_safe_check": "Ask Winship whether Gmail readonly body scope is allowed for the correspondence watcher.",
    },
    {
        "unknown_id": "unknown_reynolds_canonical_ledger_row",
        "subject": "Reynolds gig canonical ledger row",
        "unknown_status": "RESOLVED_PC16",
        "reason": "PC-16 landed Reynolds through the gig-intake path as a candidate gig event, packet receipt, and sanitized canonical fact.",
        "next_safe_check": "Use the pending approval packet ids for future approved draft/send work; do not send under SEND_HOLD.",
    },
    {
        "unknown_id": "unknown_graphiffy_atlas_staleness",
        "subject": "Graphiffy/atlas freshness",
        "unknown_status": "RESOLVED_PC17",
        "reason": "PC-17 refreshed atlas/Graphiffy artifacts to include live compose/API source nodes and orchestration layer.",
        "next_safe_check": "Refresh again after major new source roots or compose/API spine changes.",
    },
    {
        "unknown_id": "unknown_registry_pr_source",
        "subject": "Codex Web PR source",
        "unknown_status": "UNKNOWN_UNPUBLISHED",
        "reason": "Earlier registry work reported a failed push through a 403 tunnel and no PR URL; this registry records the rebuilt local state.",
        "next_safe_check": "Use the pushed local branch or compare URL as the review source after validation succeeds.",
    },
)

BUILD_TASKS: tuple[dict[str, Any], ...] = (
    {
        "task_id": "task_verify_mac_patch_apply",
        "task_rank": 1,
        "title": "Apply and validate registry patch on Mac",
        "owner_lane": "Mac Codex",
        "rationale": "PC cannot push due CONNECT tunnel 403; Mac should apply and push if validation passes.",
        "status": "ready_for_mac_apply",
        "boundary": "Mac applies patch and runs local validation; no PC push.",
    },
    {
        "task_id": "task_promote_confirmed_reference_data",
        "task_rank": 2,
        "title": "Promote confirmed Data Room reference answers",
        "owner_lane": "Cassandra / Codex",
        "rationale": "Hydration is blocked until confirmed reference data exists.",
        "status": "blocked_until_operator_confirmation",
        "boundary": "No provisional answer becomes runtime truth automatically.",
    },
    {
        "task_id": "task_live_chatgpt_adapter_readiness",
        "task_rank": 3,
        "title": "Prove or reject live ChatGPT 5.5 advisory adapter",
        "owner_lane": "Hermes / Guardian",
        "rationale": "Manual form-fill package is ready, but live adapter claims must fail closed.",
        "status": "future_gated",
        "boundary": "No external model call without explicit approved adapter and receipts.",
    },
    {
        "task_id": "task_map_import_gap",
        "task_rank": 4,
        "title": "Resolve Mac map import gap separately",
        "owner_lane": "PC/Mac Sync",
        "rationale": "Map import was explicitly separate from read-model sync repair.",
        "status": "separate_lane_required",
        "boundary": "Registry does not run sync or Mac jobs.",
    },
    {
        "task_id": "task_voice_caveat",
        "task_rank": 5,
        "title": "Keep voice/Kokoro caveat separate",
        "owner_lane": "Cassandra",
        "rationale": "Text route is canonical and voice side effects should not block core operator workflows.",
        "status": "known_caveat",
        "boundary": "No voice fix or daemon start here.",
    },
    {
        "task_id": "task_correspondence_watcher",
        "task_rank": 6,
        "title": "Wire correspondence watcher loop safely",
        "owner_lane": "PC Codex",
        "rationale": "PC-9 scaffold exists for fixture/approved-summary planning; real Gmail scope must remain explicit.",
        "status": "scaffolded_pc9_send_hold_safetied",
        "boundary": "No Gmail body reading without scope decision; no email send.",
    },
    {
        "task_id": "task_email_send_executor_scaffold",
        "task_rank": 7,
        "title": "Scaffold email_send executor unregistered",
        "owner_lane": "PC Codex",
        "rationale": "PC-10 scaffold exists and records blocked side-effect rows; SEND_HOLD prevents firing.",
        "status": "scaffolded_pc10_send_hold_safetied",
        "boundary": "Executor remains unregistered and non-firing until tested and approved.",
    },
    {
        "task_id": "task_land_reynolds_gig",
        "task_rank": 8,
        "title": "Land Reynolds gig as canonical business record",
        "owner_lane": "PC Codex",
        "rationale": "PC-16 should dogfood gig intake by moving Reynolds facts from share artifact to canonical ledger.",
        "status": "completed_pc16",
        "boundary": "Recorded candidate gig/canonical fact only; no send or invoice execution.",
    },
    {
        "task_id": "task_refresh_graphiffy_atlas",
        "task_rank": 9,
        "title": "Refresh atlas/Graphiffy after compose/orchestration wiring",
        "owner_lane": "PC Codex",
        "rationale": "PC-17 should make graph artifacts reflect compose/API/orchestration reality.",
        "status": "completed_pc17",
        "boundary": "Use established local generator only; no external API or service mutation.",
    },
    {
        "task_id": "task_wire_nervous_system",
        "task_rank": 10,
        "title": "Wire ledger tracking, live registry query, and parked polish-loop package design",
        "owner_lane": "PC Codex",
        "rationale": "PC-18/19/20 should route executor/file/atlas state into the ledger and expose deterministic self-knowledge answers.",
        "status": "in_progress_pc18_pc19_pc20",
        "boundary": "No sends, model calls, service restarts, or live polish-loop activation.",
    },
)

AGENT_ROLES: tuple[dict[str, Any], ...] = (
    {
        "role_id": "role_cassandra",
        "agent_name": "Cassandra",
        "role_summary": "Business ops, AR/client follow-up, universal intake, guided review, exact-send state.",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": ["cassandra_brain.py", "cassandra_guided_review.py", ".claude/commands/cassandra.md"],
        "authority_notes": "No send/draft/business mutation without Guardian and operator gates.",
    },
    {
        "role_id": "role_chief",
        "agent_name": "Chief",
        "role_summary": "System status, diagnostics, build coordination, and routing.",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": ["chief_router.py", "chief_ops_brain.py"],
        "authority_notes": "No push/merge/protected mutation from registry.",
    },
    {
        "role_id": "role_guardian",
        "agent_name": "Guardian",
        "role_summary": "Safety and approval boundary.",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": ["guardian_protected_access_gate_spec.py", "hitl_action_service.py"],
        "authority_notes": "Approves/denies; does not execute business logic.",
    },
    {
        "role_id": "role_niles",
        "agent_name": "Niles",
        "role_summary": "Creative/music lane, logical/spawned context.",
        "evidence_status": "CONFIRMED_LOCAL_LOGICAL",
        "evidence_paths": [".claude/commands/niles.md", "agent_lane_registry.py"],
        "authority_notes": "No DAW/session/media daemon authority.",
    },
    {
        "role_id": "role_hermes",
        "agent_name": "Hermes",
        "role_summary": "Architecture/system direction and adapter boundary.",
        "evidence_status": "CONFIRMED_LOCAL_BOUNDARY",
        "evidence_paths": [".claude/commands/hermes.md", "openclaw_hermes_sidecar.py"],
        "authority_notes": "Unsafe_to_start unless separately approved and verified.",
    },
)

ARTIFACT_POLICIES: tuple[dict[str, str], ...] = (
    {
        "policy_id": "policy_operator_reports",
        "artifact_name": "Operator-facing reports",
        "allowed_surfaces": "/mnt/e/OpenClaw_Operator_Reports or /tmp/openclaw-mission-control/operator_reports",
        "blocked_actions": "No secret-looking paths, no moving originals, no raw private proof export.",
        "evidence_basis": "scripts/operator_artifact_link_normalizer.py",
        "evidence_status": "CONFIRMED_LOCAL",
    },
    {
        "policy_id": "policy_system_knowledge_registry",
        "artifact_name": "System knowledge registry artifacts",
        "allowed_surfaces": "generated/read_models and generated/system_knowledge",
        "blocked_actions": "No runtime policy mutation, no live action grants, no external calls.",
        "evidence_basis": "this module and tests",
        "evidence_status": "CONFIRMED_LOCAL",
    },
)

AUTHORITY_ROWS: tuple[dict[str, str], ...] = (
    {
        "boundary_id": key,
        "boundary_name": key.replace("_", " "),
        "allowed": str(value).lower(),
        "blocked": str(not value).lower(),
        "evidence_basis": "AUTHORITY_BOUNDARY constant",
        "notes": "Only documentation_read_model_sqlite_only may be true.",
    }
    for key, value in AUTHORITY_BOUNDARY.items()
)

ADVICE_INTEGRITY_RECEIPT_REQUIRED_FIELDS: tuple[str, ...] = (
    "desired_outcome",
    "verified_constraints",
    "protected_currencies_considered",
    "minimum_sufficient_option",
    "recommended_posture",
    "premium_justification",
    "restraint_rationale",
    "integrity_tests_applied",
    "client_agency_preserved",
    "commercial_interest_alignment",
    "trust_gear_state",
    "agent_contributions",
    "evidence_refs",
)

ADVICE_INTEGRITY_RECEIPT_SCHEMA: dict[str, Any] = {
    "schema_id": "Advice_Integrity_Receipt",
    "schema_version": "advice_integrity_receipt_v0",
    "status": "READ_ONLY_DESIGN",
    "source_ref": "/mnt/e/openclaw/orchestration/SYSTEM-TRUSTED-COUNSEL-DOCTRINE-SOURCE.md",
    "required_fields": list(ADVICE_INTEGRITY_RECEIPT_REQUIRED_FIELDS),
    "storage_metadata_fields": ["receipt_id", "generated_at", "status"],
    "integrity_tests": [
        "Equal-Compensation Test",
        "No-Audience Test",
        "Client-Paraphrase Test",
        "Upgrade-Trigger Test",
        "Two-Sided Quality Test",
        "Autonomy Test",
        "Specificity Test",
    ],
    "authority_boundary": {
        "read_only_design": True,
        "live_prompt_mutation": False,
        "autonomous_decline_or_task_drop": False,
        "client_send_allowed": False,
    },
}

ADVICE_INTEGRITY_RECEIPTS: tuple[dict[str, Any], ...] = ()

SAFETY_POSTURE: tuple[dict[str, str], ...] = (
    {
        "posture_id": "posture_no_external_calls",
        "posture_name": "No external calls",
        "state": "enforced_by_design",
        "evidence_basis": "standard-library local file/sqlite exporter only",
        "operator_summary": "Registry exporter writes local artifacts only.",
        "next_safe_action": "Keep network/push on Mac apply task, not PC export task.",
    },
    {
        "posture_id": "posture_no_live_grants",
        "posture_name": "No live action grants",
        "state": "closed",
        "evidence_basis": "authority boundary false flags and tests",
        "operator_summary": "Registry output cannot authorize model, tool, runtime, finance, or business action.",
        "next_safe_action": "Use separate Guardian/operator approval lanes for protected actions.",
    },
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def compact_json(payload: Any) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _normalized_question(question: str) -> str:
    text = str(question or "").lower()
    text = text.replace("’", "'").replace("?", " ").replace("/", " ")
    return " ".join(text.split())


def is_system_knowledge_registry_query(question: str) -> bool:
    """Return True for operator/agent questions this registry can answer."""

    text = _normalized_question(question)
    if not text:
        return False
    direct_phrases = (
        "system knowledge registry",
        "self knowledge registry",
        "self-knowledge registry",
        "system self knowledge",
        "system self-knowledge",
        "what is in orbit",
        "what's in orbit",
        "whats in orbit",
        "floating in orbit",
    )
    if any(phrase in text for phrase in direct_phrases):
        return True
    system_terms = ("system", "openclaw", "registry")
    knowledge_terms = (
        "shape",
        "know",
        "known",
        "unknown",
        "not know",
        "doesn't know",
        "does not know",
        "capability",
        "component",
        "orbit",
        "orphan",
    )
    return any(term in text for term in system_terms) and any(term in text for term in knowledge_terms)


def _question_topics(question: str) -> set[str]:
    text = _normalized_question(question)
    topics: set[str] = set()
    if any(term in text for term in ("unknown", "not know", "doesn't know", "does not know", "missing")):
        topics.add("unknowns")
    if any(term in text for term in ("orbit", "floating", "orphan", "graph", "atlas")):
        topics.add("orbit")
    if any(term in text for term in ("task", "next", "build", "work")):
        topics.add("tasks")
    if any(term in text for term in ("shape", "system", "component", "capability", "registry")):
        topics.add("shape")
    return topics


def generated_paths(repo_root: Path) -> dict[str, Path]:
    return {
        "json": repo_root / READ_MODEL_DIR / JSON_EXPORT_NAME,
        "operator_markdown": repo_root / READ_MODEL_DIR / OPERATOR_EXPORT_NAME,
        "sqlite": repo_root / SYSTEM_KNOWLEDGE_DIR / SQLITE_EXPORT_NAME,
        "schema_sql": repo_root / SYSTEM_KNOWLEDGE_DIR / SCHEMA_SQL_EXPORT_NAME,
        "seed_sql": repo_root / SYSTEM_KNOWLEDGE_DIR / SEED_SQL_EXPORT_NAME,
    }


def _path_exists(repo_root: Path, path_text: str) -> bool | None:
    if path_text.startswith("/") or "*" in path_text:
        return None
    return (repo_root / path_text).exists()


def _source_audit(repo_root: Path) -> dict[str, Any]:
    evidence_paths: list[str] = []
    for component in COMPONENTS:
        evidence_paths.extend(component["evidence_paths"])
    checked = [
        {"path": path, "exists": _path_exists(repo_root, path)}
        for path in sorted(set(evidence_paths))
        if _path_exists(repo_root, path) is not None
    ]
    return {
        "repo_root": str(repo_root),
        "checked_path_count": len(checked),
        "missing_checked_paths": [item["path"] for item in checked if item["exists"] is False],
        "path_check_note": "Absolute paths and wildcard evidence are recorded but not file-existence checked.",
    }


def build_registry(repo_root: Path | str | None = None, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else ROOT
    output_paths = generated_paths(root)
    coverage = {
        "component_count": len(COMPONENTS),
        "seeded_component_ids": [component["component_id"] for component in COMPONENTS],
        "brain_route_record_count": len(ORBIT_BRAIN_ROUTE_RECORDS),
        "orchestration_decision_count": len(ORCHESTRATION_DECISIONS),
        "known_unknown_count": len(KNOWN_UNKNOWNS),
        "build_task_count": len(BUILD_TASKS),
        "covered_high_level_areas": [
            "Cassandra",
            "Chief",
            "Guardian",
            "Niles",
            "Hermes",
            "Watch Desk",
            "Universal Intake",
            "Context Switchboard",
            "Guided Review / Coach Mode",
            "Data Room form-fill lane",
            "Model Work Package Router",
            "Assignment Loop Contract",
            "Worker Run Manager",
            "Reference Data Hydration",
            "Artifact Link Normalizer",
            "PC/Mac Sync",
            "Invoice/Ledger discovery",
            "Voice/Kokoro caveat",
            "Compose/Gate Pipeline",
            "Orbit Brain Map",
            "Gig Intake Flow",
            "Correspondence Agent Plan",
            "Approval Gate Convergence",
            "System Knowledge Registry Query",
        ],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "registry_id": READ_MODEL_ID,
        "registry_name": REGISTRY_NAME,
        "current_status": "OPENCLAW_SYSTEM_KNOWLEDGE_REGISTRY_REBUILT",
        "generated_at": generated_at,
        "repo": {
            "local_path": str(root),
            "target_repo": "WinshipWheatley/openclaw-eyes",
            "target_branch": "codex/system-knowledge-registry-v0",
            "rebuild_reason": "reported commit and patch were unavailable in this PC checkout",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "current_safety_posture": list(SAFETY_POSTURE),
        "required_tables": list(REQUIRED_TABLES),
        "required_sqlite_tables": list(REQUIRED_TABLES),
        "sqlite_contract": {
            "required_tables": list(REQUIRED_TABLES),
            "sqlite_table_prefix_rule": "Registry schema must not explicitly define sqlite_* tables.",
            "explicit_sqlite_internal_tables_defined": False,
        },
        "component_inventory": list(COMPONENTS),
        "capabilities": list(CAPABILITIES),
        "workflow_rails": list(WORKFLOW_RAILS),
        "brain_route_inventory": list(ORBIT_BRAIN_ROUTE_RECORDS),
        "orchestration_decisions": list(ORCHESTRATION_DECISIONS),
        "knowledge_claims": list(KNOWLEDGE_CLAIMS),
        "known_unknowns": list(KNOWN_UNKNOWNS),
        "build_tasks": list(BUILD_TASKS),
        "agent_roles": list(AGENT_ROLES),
        "artifact_policies": list(ARTIFACT_POLICIES),
        "authority_boundaries": list(AUTHORITY_ROWS),
        "advice_integrity_receipt_schema": ADVICE_INTEGRITY_RECEIPT_SCHEMA,
        "advice_integrity_receipts": list(ADVICE_INTEGRITY_RECEIPTS),
        "coverage_assessment": coverage,
        "source_audit": _source_audit(root),
        "generated_outputs": {name: str(path.relative_to(root)) for name, path in output_paths.items()},
        "live_projection": build_live_registry_projection(root),
        "no_secrets": True,
        "no_live_action_grants": True,
        "no_runtime_mutation": True,
        "no_external_calls": True,
        "safety_assertions": {
            "no_secrets": True,
            "no_live_action_grants": True,
            "no_runtime_mutation": True,
            "no_external_calls": True,
        },
    }


def _first_existing_path(paths: tuple[Path, ...]) -> Path | None:
    for path in paths:
        if path.is_file():
            return path
    return None


def _sqlite_table_counts(path: Path, table_names: tuple[str, ...]) -> dict[str, int | str]:
    if not path.is_file():
        return {"status": "missing"}
    uri = f"file:{path.as_posix()}?mode=ro"
    counts: dict[str, int | str] = {}
    try:
        with sqlite3.connect(uri, uri=True) as conn:
            existing = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            for table in table_names:
                if table not in existing:
                    counts[table] = "missing"
                else:
                    counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.Error:
        return {"status": "unreadable"}
    return counts


def _load_json_if_exists(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _live_projection_known_unknowns(projection: dict[str, Any]) -> list[dict[str, str]]:
    unknowns: list[dict[str, str]] = []
    ledger_counts = projection.get("ledger_counts")
    if isinstance(ledger_counts, dict):
        ledger_status = ledger_counts.get("status")
        if ledger_status == "missing":
            unknowns.append(
                {
                    "unknown_id": "unknown_live_business_ops_ledger_missing",
                    "subject": "Business ops ledger live projection",
                    "unknown_status": "MISSING_IN_THIS_WORKTREE",
                    "reason": "The configured ledger SQLite file is not present, so live ledger counts cannot be projected here.",
                    "next_safe_check": "Run the query against the live repo ledger path or let PC-18/claude-mac confirm ledger export availability.",
                }
            )
        elif ledger_status == "unreadable":
            unknowns.append(
                {
                    "unknown_id": "unknown_live_business_ops_ledger_unreadable",
                    "subject": "Business ops ledger live projection",
                    "unknown_status": "UNREADABLE_SQLITE",
                    "reason": "The configured ledger SQLite file exists but could not be opened read-only.",
                    "next_safe_check": "Verify file permissions and SQLite integrity without mutating the ledger.",
                }
            )
        else:
            missing_tables = sorted(
                table for table, count in ledger_counts.items() if count == "missing"
            )
            if missing_tables:
                unknowns.append(
                    {
                        "unknown_id": "unknown_live_business_ops_ledger_tables",
                        "subject": "Business ops ledger table coverage",
                        "unknown_status": "EXPECTED_TABLES_MISSING",
                        "reason": f"Expected ledger tables are absent from the live projection: {', '.join(missing_tables)}.",
                        "next_safe_check": "Coordinate table/schema changes through the PC-18 ledger lane; do not patch ledger schema from this registry lane.",
                    }
                )
    if not projection.get("atlas_path") or not projection.get("atlas_summary"):
        unknowns.append(
            {
                "unknown_id": "unknown_live_filesystem_atlas_missing",
                "subject": "Filesystem atlas live projection",
                "unknown_status": "ATLAS_MISSING_OR_EMPTY",
                "reason": "No readable atlas summary was found for the live projection.",
                "next_safe_check": "Refresh or provide the established filesystem atlas artifact, then rerun the query.",
            }
        )
    if not projection.get("graphiffy_path"):
        unknowns.append(
            {
                "unknown_id": "unknown_live_graphiffy_missing",
                "subject": "Graphiffy orbit projection",
                "unknown_status": "GRAPHIFY_MISSING",
                "reason": "No readable Graphiffy artifact was found, so orphaned/in-orbit node sampling is incomplete.",
                "next_safe_check": "Refresh or provide the established Graphiffy artifact, then rerun the query.",
            }
        )
    return unknowns


def build_live_registry_projection(
    repo_root: Path | str | None = None,
    *,
    ledger_path: str | Path | None = None,
    atlas_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build a read-only live projection from the ledger and atlas artifacts."""

    root = Path(repo_root) if repo_root is not None else ROOT
    ledger = Path(ledger_path) if ledger_path is not None else root / ".openclaw/business_ops/ledger.sqlite"
    atlas = (
        Path(atlas_path)
        if atlas_path is not None
        else _first_existing_path(
            (
                root / "generated/read_models/openclaw_filesystem_atlas.json",
                Path("/mnt/e/openclaw/orchestration/artifacts/openclaw_filesystem_atlas.json"),
                Path("/mnt/e/openclaw-source/generated/read_models/openclaw_filesystem_atlas.json"),
            )
        )
    )
    graphiffy = _first_existing_path(
        (
            root / "generated/read_models/openclaw_filesystem_graphiffy.json",
            Path("/mnt/e/openclaw/orchestration/artifacts/openclaw_filesystem_graphiffy.json"),
            Path("/mnt/e/openclaw-source/generated/read_models/openclaw_filesystem_graphiffy.json"),
        )
    )
    ledger_counts = _sqlite_table_counts(
        ledger,
        (
            "events",
            "packets",
            "side_effects",
            "file_inventory",
            "canonical_facts",
            "agent_work_packets",
            "agent_work_packet_receipts",
            "intent_records",
        ),
    )
    atlas_payload = _load_json_if_exists(atlas)
    graph_payload = _load_json_if_exists(graphiffy)
    graph_nodes = graph_payload.get("nodes") if isinstance(graph_payload, dict) else []
    orbit_like_nodes = [
        {
            "label": node.get("label"),
            "path": node.get("path"),
            "category": node.get("category"),
            "move_safety_posture": node.get("move_safety_posture"),
        }
        for node in graph_nodes
        if isinstance(node, dict)
        and node.get("move_safety_posture") in {"candidate_only_after_validation", "unknown_manual_review"}
    ][:25]
    projection = {
        "projection_version": "openclaw_live_registry_projection_v0",
        "source_mode": "read_only_ledger_and_atlas_metadata",
        "ledger_path": ledger.as_posix(),
        "ledger_counts": ledger_counts,
        "atlas_path": atlas.as_posix() if atlas else None,
        "atlas_summary": dict(atlas_payload.get("summary") or {}) if isinstance(atlas_payload, dict) else {},
        "graphiffy_path": graphiffy.as_posix() if graphiffy else None,
        "graphiffy_node_count": len(graph_nodes) if isinstance(graph_nodes, list) else 0,
        "orbit_like_node_sample": orbit_like_nodes,
        "authority_boundary": {
            "read_only": True,
            "ledger_mutation": False,
            "runtime_mutation": False,
            "model_call": False,
            "external_call": False,
        },
    }
    projection["live_known_unknowns"] = _live_projection_known_unknowns(projection)
    return projection


def query_system_knowledge_registry(
    question: str,
    *,
    repo_root: Path | str | None = None,
    ledger_path: str | Path | None = None,
    atlas_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return deterministic registry answers for agents without LLM guessing."""

    root = Path(repo_root) if repo_root is not None else ROOT
    payload = build_registry(root)
    live_projection = build_live_registry_projection(root, ledger_path=ledger_path, atlas_path=atlas_path)
    topics = _question_topics(question)
    static_unknowns = list(payload["known_unknowns"])
    live_unknowns = list(live_projection.get("live_known_unknowns") or [])
    all_unknowns = static_unknowns + live_unknowns
    if len(topics & {"shape", "unknowns", "orbit"}) >= 2:
        answer_type = "system_self_knowledge"
        items = {
            "system_shape": {
                "components": payload["component_inventory"],
                "capabilities": payload["capabilities"],
                "knowledge_claims": payload["knowledge_claims"],
            },
            "known_unknowns": all_unknowns,
            "orbit_and_atlas": {
                "brain_route_inventory": payload["brain_route_inventory"],
                "atlas_summary": live_projection["atlas_summary"],
                "orbit_like_node_sample": live_projection["orbit_like_node_sample"],
                "graphiffy_node_count": live_projection["graphiffy_node_count"],
            },
            "live_projection": live_projection,
        }
        summary = (
            f"{len(payload['component_inventory'])} components, "
            f"{len(payload['capabilities'])} capabilities, "
            f"{len(payload['knowledge_claims'])} knowledge claims, "
            f"{len(all_unknowns)} known unknowns, and "
            f"{len(payload['brain_route_inventory'])} orbit brain records are available."
        )
    elif "unknowns" in topics:
        answer_type = "known_unknowns"
        items = all_unknowns
        summary = f"{len(items)} known unknowns are recorded, including live projection gaps."
    elif "orbit" in topics:
        answer_type = "orbit_and_atlas"
        items = {
            "brain_route_inventory": payload["brain_route_inventory"],
            "atlas_summary": live_projection["atlas_summary"],
            "orbit_like_node_sample": live_projection["orbit_like_node_sample"],
            "graphiffy_node_count": live_projection["graphiffy_node_count"],
        }
        summary = "Orbit posture comes from brain-route inventory plus atlas/Graphiffy metadata."
    elif "tasks" in topics:
        answer_type = "build_tasks"
        items = payload["build_tasks"]
        summary = f"{len(items)} build tasks are recorded."
    elif "shape" in topics:
        answer_type = "system_shape"
        items = {
            "components": payload["component_inventory"],
            "capabilities": payload["capabilities"],
            "knowledge_claims": payload["knowledge_claims"],
            "live_projection": live_projection,
        }
        summary = (
            f"{len(payload['component_inventory'])} components, "
            f"{len(payload['capabilities'])} capabilities, and "
            f"{len(payload['knowledge_claims'])} knowledge claims are recorded."
        )
    else:
        answer_type = "overview"
        items = {
            "components": payload["coverage_assessment"]["seeded_component_ids"],
            "known_unknown_count": len(all_unknowns),
            "build_task_count": len(payload["build_tasks"]),
            "live_projection": live_projection,
        }
        summary = "Registry overview returned; ask for shape, unknowns, orbit, or tasks for a narrower answer."
    return {
        "status": "ok",
        "query": question,
        "answer_type": answer_type,
        "summary": summary,
        "items": items,
        "source_refs": {
            "registry": "openclaw_system_knowledge_registry.py",
            "ledger_path": live_projection["ledger_path"],
            "atlas_path": live_projection["atlas_path"],
            "graphiffy_path": live_projection["graphiffy_path"],
        },
        "authority_boundary": {
            "read_only": True,
            "model_call": False,
            "external_call": False,
            "runtime_mutation": False,
            "business_action": False,
        },
    }


def _status_line(item: dict[str, Any], id_key: str, status_key: str, subject_key: str = "subject") -> str:
    label = str(item.get(subject_key) or item.get(id_key) or "").strip()
    status = str(item.get(status_key) or "").strip()
    identifier = str(item.get(id_key) or "").strip()
    if label and status:
        return f"{label} ({status})"
    return label or identifier


def _sample_lines(items: list[dict[str, Any]], *, id_key: str, status_key: str, subject_key: str = "subject", limit: int = 4) -> str:
    if not items:
        return "none"
    return "; ".join(
        _status_line(item, id_key=id_key, status_key=status_key, subject_key=subject_key)
        for item in items[:limit]
    )


def format_system_knowledge_answer(answer: dict[str, Any]) -> str:
    """Format a deterministic registry answer for Cassandra/CLI operator use."""

    answer_type = str(answer.get("answer_type") or "overview")
    items = answer.get("items") if isinstance(answer.get("items"), dict) else {}
    authority = answer.get("authority_boundary") if isinstance(answer.get("authority_boundary"), dict) else {}
    boundary = (
        "Boundary: read-only registry query; no model call, external call, "
        "runtime mutation, or business action."
        if authority.get("read_only") is True
        else "Boundary: registry answer only."
    )
    if answer_type == "system_self_knowledge":
        shape = items.get("system_shape") if isinstance(items, dict) else {}
        orbit = items.get("orbit_and_atlas") if isinstance(items, dict) else {}
        live = items.get("live_projection") if isinstance(items, dict) else {}
        components = list((shape or {}).get("components") or [])
        capabilities = list((shape or {}).get("capabilities") or [])
        claims = list((shape or {}).get("knowledge_claims") or [])
        unknowns = list((items or {}).get("known_unknowns") or [])
        brains = list((orbit or {}).get("brain_route_inventory") or [])
        atlas_summary = dict((orbit or {}).get("atlas_summary") or {})
        orbit_sample = list((orbit or {}).get("orbit_like_node_sample") or [])
        ledger_counts = (live or {}).get("ledger_counts") if isinstance(live, dict) else {}
        ledger_status = ledger_counts.get("status", "available") if isinstance(ledger_counts, dict) else "unknown"
        claim_subjects = ", ".join(str(claim.get("subject") or claim.get("claim_id")) for claim in claims[:4]) or "none"
        return "\n".join(
            [
                "OpenClaw System Knowledge (read-only)",
                f"Shape: {len(components)} components, {len(capabilities)} capabilities, {len(brains)} orbit brain records.",
                f"Knows: {len(claims)} registry claims; first subjects: {claim_subjects}.",
                f"Does not know: {len(unknowns)} known unknowns; {_sample_lines(unknowns, id_key='unknown_id', status_key='unknown_status')}.",
                (
                    "In orbit: "
                    f"atlas roots={atlas_summary.get('root_count', 0)}, "
                    f"directories={atlas_summary.get('directory_count', 0)}, "
                    f"Graphiffy nodes={(orbit or {}).get('graphiffy_node_count', 0)}, "
                    f"sampled nodes={len(orbit_sample)}."
                ),
                f"Live ledger projection: {ledger_status}.",
                boundary,
            ]
        )
    if answer_type == "known_unknowns":
        unknowns = list(answer.get("items") or [])
        return "\n".join(
            [
                "OpenClaw Known Unknowns (read-only)",
                f"Count: {len(unknowns)}.",
                _sample_lines(unknowns, id_key="unknown_id", status_key="unknown_status"),
                boundary,
            ]
        )
    if answer_type == "orbit_and_atlas":
        orbit = answer.get("items") if isinstance(answer.get("items"), dict) else {}
        brains = list((orbit or {}).get("brain_route_inventory") or [])
        atlas_summary = dict((orbit or {}).get("atlas_summary") or {})
        orbit_sample = list((orbit or {}).get("orbit_like_node_sample") or [])
        return "\n".join(
            [
                "OpenClaw Orbit (read-only)",
                f"Brain-route records: {len(brains)}.",
                f"Atlas: roots={atlas_summary.get('root_count', 0)}, directories={atlas_summary.get('directory_count', 0)}.",
                f"Graphiffy nodes: {(orbit or {}).get('graphiffy_node_count', 0)}; sampled orbit-like nodes: {len(orbit_sample)}.",
                boundary,
            ]
        )
    if answer_type == "system_shape":
        shape = answer.get("items") if isinstance(answer.get("items"), dict) else {}
        components = list((shape or {}).get("components") or [])
        capabilities = list((shape or {}).get("capabilities") or [])
        claims = list((shape or {}).get("knowledge_claims") or [])
        return "\n".join(
            [
                "OpenClaw System Shape (read-only)",
                f"Components: {len(components)}.",
                f"Capabilities: {len(capabilities)}.",
                f"Knowledge claims: {len(claims)}.",
                boundary,
            ]
        )
    return "\n".join(
        [
            "OpenClaw System Knowledge (read-only)",
            str(answer.get("summary") or "Registry overview returned."),
            boundary,
        ]
    )


def sqlite_rows(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        "system_component": [
            {
                "component_id": row["component_id"],
                "display_name": row["display_name"],
                "component_type": row["component_type"],
                "evidence_status": row["evidence_status"],
                "evidence_paths_json": compact_json(row["evidence_paths"]),
                "summary": row["summary"],
                "authority_boundary": row["authority_boundary"],
            }
            for row in payload["component_inventory"]
        ],
        "capability": list(payload["capabilities"]),
        "workflow_rail": list(payload["workflow_rails"]),
        "brain_route_inventory": list(payload["brain_route_inventory"]),
        "orchestration_decision": list(payload["orchestration_decisions"]),
        "knowledge_claim": [
            {
                "claim_id": row["claim_id"],
                "subject": row["subject"],
                "claim": row["claim"],
                "evidence_status": row["evidence_status"],
                "evidence_paths_json": compact_json(row["evidence_paths"]),
                "confidence": row["confidence"],
            }
            for row in payload["knowledge_claims"]
        ],
        "known_unknown": list(payload["known_unknowns"]),
        "build_task": list(payload["build_tasks"]),
        "agent_role": [
            {
                "role_id": row["role_id"],
                "agent_name": row["agent_name"],
                "role_summary": row["role_summary"],
                "evidence_status": row["evidence_status"],
                "evidence_paths_json": compact_json(row["evidence_paths"]),
                "authority_notes": row["authority_notes"],
            }
            for row in payload["agent_roles"]
        ],
        "artifact_policy": list(payload["artifact_policies"]),
        "authority_boundary": list(payload["authority_boundaries"]),
        "safety_posture": list(payload["current_safety_posture"]),
        "advice_integrity_receipt": list(payload["advice_integrity_receipts"]),
    }


def schema_sql() -> str:
    statements = [
        "-- OpenClaw System Knowledge Registry schema",
        "-- Generated for documentation/read-model/SQLite review only.",
    ]
    for table in REQUIRED_TABLES:
        columns = TABLE_COLUMNS[table]
        lines = []
        for column in columns:
            if table == "build_task" and column == "task_rank":
                lines.append("  task_rank INTEGER NOT NULL")
            else:
                lines.append(f"  {column} TEXT NOT NULL")
        lines.append(f"  PRIMARY KEY ({columns[0]})")
        statements.append(f"CREATE TABLE IF NOT EXISTS {table} (\n" + ",\n".join(lines) + "\n);")
    return "\n\n".join(statements) + "\n"


def _sql_literal(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def seed_sql(payload: dict[str, Any]) -> str:
    rows_by_table = sqlite_rows(payload)
    lines = [
        "-- OpenClaw System Knowledge Registry seed data",
        "-- Generated for documentation/read-model/SQLite review only.",
    ]
    for table in REQUIRED_TABLES:
        columns = TABLE_COLUMNS[table]
        lines.append(f"DELETE FROM {table};")
        for row in rows_by_table[table]:
            column_list = ", ".join(columns)
            values = ", ".join(_sql_literal(row[column]) for column in columns)
            lines.append(f"INSERT INTO {table} ({column_list}) VALUES ({values});")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_operator_markdown(payload: dict[str, Any]) -> str:
    coverage = payload["coverage_assessment"]
    lines = [
        "# OpenClaw System Knowledge Registry",
        "",
        "## Summary",
        f"- Registry ID: `{payload['registry_id']}`",
        f"- Schema version: `{payload['schema_version']}`",
        f"- Component count: {coverage['component_count']}",
        f"- Brain route records: {coverage['brain_route_record_count']}",
        f"- Orchestration decisions: {coverage['orchestration_decision_count']}",
        f"- Known unknown count: {coverage['known_unknown_count']}",
        f"- Build task count: {coverage['build_task_count']}",
        "- Boundary: documentation/read-model/SQLite only.",
        "- READY means registry artifacts validated; it does not grant runtime, business, model, or GitHub authority.",
        "",
        "## Authority Boundaries",
    ]
    for key, value in payload["authority_boundary"].items():
        lines.append(f"- `{key}`: {str(value).lower()}")
    lines.extend(["", "## Components"])
    for component in payload["component_inventory"]:
        lines.append(f"- `{component['component_id']}`: {component['evidence_status']} - {component['summary']}")
    lines.extend(["", "## Brain Route Inventory"])
    for brain in payload["brain_route_inventory"]:
        lines.append(
            f"- `{brain['brain_id']}`: {brain['disposition_action']} / {brain['compose_status']} - "
            f"{brain['boundary']}"
        )
    lines.extend(["", "## Orchestration Decisions"])
    for decision in payload["orchestration_decisions"]:
        lines.append(
            f"- `{decision['decision_id']}`: {decision['status']} - {decision['decision']} "
            f"Next: {decision['next_safe_action']}"
        )
    lines.extend(["", "## Known Unknowns"])
    for unknown in payload["known_unknowns"]:
        lines.append(
            f"- `{unknown['unknown_id']}`: {unknown['subject']} - {unknown['unknown_status']}. "
            f"Next: {unknown['next_safe_check']}"
        )
    lines.extend(["", "## Build Tasks"])
    for task in payload["build_tasks"]:
        lines.append(f"{task['task_rank']}. {task['title']} ({task['owner_lane']}) - {task['status']}")
    lines.extend(["", "## Current Safety Posture"])
    for posture in payload["current_safety_posture"]:
        lines.append(f"- `{posture['posture_id']}`: {posture['state']} - {posture['operator_summary']}")
    lines.extend(["", "## Generated Outputs"])
    for name, path in payload["generated_outputs"].items():
        lines.append(f"- `{name}`: `{path}`")
    return "\n".join(lines) + "\n"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_sqlite(path: Path, payload: dict[str, Any]) -> None:
    rows_by_table = sqlite_rows(payload)

    def build_database(database_path: Path) -> None:
        with sqlite3.connect(database_path) as conn:
            conn.executescript(schema_sql())
            for table in REQUIRED_TABLES:
                columns = TABLE_COLUMNS[table]
                placeholders = ", ".join("?" for _ in columns)
                column_list = ", ".join(columns)
                values = [tuple(row[column] for column in columns) for row in rows_by_table[table]]
                conn.executemany(f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})", values)
            conn.commit()

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="openclaw_system_registry_") as temp_dir:
        temp_path = Path(temp_dir) / path.name
        build_database(temp_path)
        new_bytes = temp_path.read_bytes()
    if path.exists() and path.read_bytes() == new_bytes:
        return
    path.write_bytes(new_bytes)


def export_registry(repo_root: Path | str | None = None, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else ROOT
    payload = build_registry(root, generated_at=generated_at)
    paths = generated_paths(root)
    write_text(paths["json"], stable_json(payload))
    write_text(paths["operator_markdown"], render_operator_markdown(payload))
    write_text(paths["schema_sql"], schema_sql())
    write_text(paths["seed_sql"], seed_sql(payload))
    write_sqlite(paths["sqlite"], payload)
    return {
        "payload": payload,
        "paths": paths,
        "component_count": len(payload["component_inventory"]),
        "known_unknown_count": len(payload["known_unknowns"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the OpenClaw System Knowledge Registry.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Repository root for generated outputs.")
    parser.add_argument(
        "--format",
        choices=("paths", "json", "markdown", "sqlite", "all"),
        default="all",
        help="Output view after writing all registry artifacts.",
    )
    args = parser.parse_args(argv)
    result = export_registry(Path(args.repo_root))
    payload = result["payload"]
    paths: dict[str, Path] = result["paths"]
    root = Path(args.repo_root)
    if args.format == "paths":
        for key in ("json", "operator_markdown", "sqlite", "schema_sql", "seed_sql"):
            print(paths[key].relative_to(root))
    elif args.format == "json":
        print(stable_json(payload), end="")
    elif args.format == "markdown":
        print(render_operator_markdown(payload), end="")
    elif args.format == "sqlite":
        print(paths["sqlite"].relative_to(root))
    else:
        print(f"{READ_MODEL_ID}: components={result['component_count']} known_unknowns={result['known_unknown_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

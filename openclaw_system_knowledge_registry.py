"""OpenClaw Eyes System Knowledge Registry v0.

This module exports an inert documentation/read-model/SQLite registry for the
local ``openclaw-eyes`` checkout. It records local evidence and known unknowns;
it does not start services, contact accounts, call models, browse, send, export
PDFs, read workbooks, or mutate ledgers.
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
REGISTRY_NAME = "OpenClaw Eyes System Knowledge Registry"
DEFAULT_GENERATED_AT = "2026-05-30T00:00:00+00:00"

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
    "knowledge_claim",
    "known_unknown",
    "build_task",
    "agent_role",
    "artifact_policy",
    "registry_sqlite_display_surface",
    "repo_relationship_analysis",
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
        "model_class_recommendation",
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
    "registry_sqlite_display_surface": (
        "surface_id",
        "surface_name",
        "table_name",
        "display_purpose",
        "operator_notes",
    ),
    "repo_relationship_analysis": (
        "analysis_id",
        "relationship_name",
        "local_evidence_status",
        "conclusion",
        "known_unknown_refs_json",
        "next_step",
    ),
}

AUTHORITY_BOUNDARY = {
    "documentation_read_model_sqlite_only": True,
    "live_automation_allowed": False,
    "service_start_allowed": False,
    "email_or_gmail_access_allowed": False,
    "browser_or_coupa_access_allowed": False,
    "workbook_cell_read_allowed": False,
    "pdf_export_allowed": False,
    "ledger_mutation_allowed": False,
    "production_mutation_allowed": False,
    "live_model_or_tool_action_allowed": False,
    "merge_to_main_allowed": False,
}

COMPONENTS: tuple[dict[str, Any], ...] = (
    {
        "component_id": "openclaw_eyes_repo_identity",
        "display_name": "openclaw-eyes repo identity",
        "component_type": "repo",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": [".gitignore", "AGENTS.md", "docs/INDEX.md"],
        "summary": "Local checkout for WinshipWheatley/openclaw-eyes with an allowlist tracked-file model.",
        "authority_boundary": "Registry records local repo shape only; no branch merge or runtime authority.",
    },
    {
        "component_id": "generated_read_model_system",
        "display_name": "Generated read-model system",
        "component_type": "read_model_substrate",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": [
            "generated/read_models/artifact_registry.json",
            "generated/read_models/context_selection.json",
            "generated/read_models/operator_actions.json",
            "scripts/export_read_models.py",
        ],
        "summary": "Repo contains deterministic JSON, markdown, and text read-model outputs.",
        "authority_boundary": "Generated outputs are evidence/display surfaces, not execution grants.",
    },
    {
        "component_id": "evidence_grounded_context_registry_concept",
        "display_name": "Evidence-Grounded Context Registry concept",
        "component_type": "context_substrate",
        "evidence_status": "PARTIAL_LOCAL",
        "evidence_paths": [
            "compiled_knowledge_substrate.py",
            "context_selection.py",
            "corpus_atlas.py",
            "evidence_kettle.py",
            "docs/planning/command_atlas/04_CONTEXT_DEVELOPMENT_LIFECYCLE_AND_CONTEXT_FILTER_DOCTRINE.md",
            "docs/planning/operator_harness/COMPILED_KNOWLEDGE_SUBSTRATE_NORTH_STAR.md",
        ],
        "summary": "Local files support evidence-grounded context, freshness, and compiled substrate ideas.",
        "authority_boundary": "Concept is recorded as local substrate evidence; it is not a vector RAG mandate.",
    },
    {
        "component_id": "work_terrain_operator_map_surfaces",
        "display_name": "Work terrain and operator map surfaces",
        "component_type": "operator_navigation",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": [
            "openclaw_work_terrain_query_contract.py",
            "openclaw_work_terrain_relationship_index.py",
            "openclaw_work_terrain_gap_detector.py",
            "operator_map_bundle_contract.py",
            "generated/read_models/openclaw_work_terrain_relationship_index.json",
            "generated/read_models/operator_map_bundle_contract.json",
        ],
        "summary": "Repo has work-terrain query, relationship, classification, and operator map records.",
        "authority_boundary": "Navigation and reconciliation only; no cleanup, archive, or private-root action.",
    },
    {
        "component_id": "operator_action_workflow_surfaces",
        "display_name": "Operator action and workflow atlas surfaces",
        "component_type": "workflow_control",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": [
            "operator_action.py",
            "operator_action_inbox.py",
            "workflow_session_channel_projection_approval_bus_contract.py",
            "generated/read_models/operator_workflow_atlas.json",
            "generated/read_models/operator_actions.json",
        ],
        "summary": "Repo records operator action requests, inboxes, workflow rails, and approval-bus contracts.",
        "authority_boundary": "Registry does not approve or execute operator actions.",
    },
    {
        "component_id": "bridge_shuttle_sync_surfaces",
        "display_name": "Bridge, shuttle, and read-model sync surfaces",
        "component_type": "transport_boundary",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": [
            "read_model_shuttle.py",
            "mac_mirror_atlas.py",
            "bridge_manual_mount_recovery_packet.py",
            "bridge_trust_sync_truth.py",
            "scripts/prepare_mac_read_model_shuttle.py",
            "scripts/import_mac_read_model_shuttle.py",
        ],
        "summary": "Repo contains Mac/PC read-model shuttle, bridge truth, and manual recovery packet surfaces.",
        "authority_boundary": "Transport policy only; this registry does not import, mount, or sync.",
    },
    {
        "component_id": "cassandra_chief_guardian_references",
        "display_name": "Cassandra, Chief, and Guardian references",
        "component_type": "agent_role_family",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": [
            "cassandra_brain.py",
            "cassandra_listener.py",
            "cassandra_contact_policy.py",
            "chief_router.py",
            "chief_approval_brain.py",
            "guardian_protected_access_gate_spec.py",
            "templates/agent/guardian_approval_request_packet_template.json",
        ],
        "summary": "Agent-role code and packet templates exist for Cassandra, Chief, and Guardian rails.",
        "authority_boundary": "Reference mapping only; no agent activation, send, approval, or live dispatch.",
    },
    {
        "component_id": "mac_eyes_surfaces",
        "display_name": "mac_eyes surfaces",
        "component_type": "mac_reflection",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": [
            "mac_eyes/Winship/AGENTS.md",
            "mac_eyes/Launchers/sync_to_mac.sh",
            "mac_eyes/Launchers/refresh_operator_harness_ingest.sh",
        ],
        "summary": "Mac reflection and launcher surfaces are present as local files.",
        "authority_boundary": "Registry records paths only; it does not run launchers or sync jobs.",
    },
    {
        "component_id": "polish_loop_runtime_task_area",
        "display_name": "polish_loop runtime task area",
        "component_type": "review_loop",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": [
            "polish_loop/orchestrator.py",
            "polish_loop/builder_output_validator.py",
            "polish_loop/pc_review_fallback.py",
            "polish_loop/status.json",
        ],
        "summary": "Repo contains a builder/review loop area and status files.",
        "authority_boundary": "No loop is started or advanced by this registry.",
    },
    {
        "component_id": "legal_module_surfaces",
        "display_name": "Legal module surfaces",
        "component_type": "legal_planning",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": [
            "legal/support_packet.py",
            "legal/path_guard.py",
            "legal/local_capability_policy.py",
            "apps/legal-console-spike/README.md",
            "docs/planning/openclaw_legal/law_program/",
        ],
        "summary": "Legal support, path guard, local policy, and console spike surfaces are present.",
        "authority_boundary": "Registry records planning surfaces only; no legal-private file inspection.",
    },
    {
        "component_id": "context_evidence_read_model_substrate",
        "display_name": "Context, evidence, and read-model substrate",
        "component_type": "evidence_layer",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": [
            "context_selection.py",
            "evidence_kettle.py",
            "generated/context_packets/context_packet_latest.json",
            "generated/context_packs/mission_control_current/MANIFEST.json",
            "generated/read_models/evidence_freshness.json",
        ],
        "summary": "Repo contains context packet, evidence freshness, and read-model selection machinery.",
        "authority_boundary": "Evidence visibility is not authority to use private or live sources.",
    },
    {
        "component_id": "business_ops_artifact_policy_surfaces",
        "display_name": "Business ops and artifact policy surfaces",
        "component_type": "finance_artifact_boundary",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": [
            "business_ops_ledger.py",
            "protected_access_broker_concept.py",
            "capital_hilton_invoice_delivery_steel_thread.py",
            "generated/read_models/capital_hilton_invoice_delivery_steel_thread.json",
            "generated/read_models/protected_evidence_reference_receipt.json",
        ],
        "summary": "Repo has finance/artifact policy surfaces and protected evidence references.",
        "authority_boundary": "This registry does not read workbooks, export PDFs, access portals, or mutate ledgers.",
    },
    {
        "component_id": "external_repo_a_b_runtime_relationship",
        "display_name": "External Repo A, Repo B, and runtime relationship",
        "component_type": "external_relationship",
        "evidence_status": "UNKNOWN_EXTERNAL",
        "evidence_paths": [
            "generated/read_models/repo_a_known_rail_completion_map.json",
            "generated/read_models/repo_b_remaining_capability_delta_map.json",
            "docs/operations/OPENCLAW_REPO_B_RUNTIME_INTAKE_V0.md",
        ],
        "summary": "Local repo mentions Repo A, Repo B, and runtime intake, but external repos are not present.",
        "authority_boundary": "External repo/runtime facts stay UNKNOWN until inspected in their own repos.",
    },
    {
        "component_id": "prior_codex_web_registry_commit",
        "display_name": "Prior Codex Web registry commit",
        "component_type": "unreachable_work",
        "evidence_status": "UNKNOWN_UNREACHABLE",
        "evidence_paths": [
            "Codex Web report: c5b83f6cda91daf25b95367e6d94e0d8890ffea3",
            "local search before recreation: no openclaw_system_knowledge_registry files",
        ],
        "summary": "Reported Codex Web commit could not be fetched or pushed; this branch recreates locally.",
        "authority_boundary": "Do not chase unreachable commits; validate the local recreation instead.",
    },
)

CAPABILITIES: tuple[dict[str, str], ...] = (
    {
        "capability_id": "cap_deterministic_registry_export",
        "component_id": "generated_read_model_system",
        "capability_name": "Deterministic registry export",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "New exporter writes JSON, operator markdown, SQLite, schema SQL, and seed SQL.",
        "boundary": "No network, model, browser, account, service, PDF, workbook, or ledger action.",
    },
    {
        "capability_id": "cap_sqlite_operator_display",
        "component_id": "generated_read_model_system",
        "capability_name": "SQLite-backed operator display contract",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "Required SQLite tables are defined as local registry tables.",
        "boundary": "SQLite is generated artifact storage only.",
    },
    {
        "capability_id": "cap_context_selection",
        "component_id": "context_evidence_read_model_substrate",
        "capability_name": "Context selection and evidence freshness",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "context_selection.py and generated evidence freshness read-models exist locally.",
        "boundary": "No body ingestion or private-root expansion.",
    },
    {
        "capability_id": "cap_operator_action_receipts",
        "component_id": "operator_action_workflow_surfaces",
        "capability_name": "Operator action request and receipt surfaces",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "operator_action.py, operator_action_inbox.py, and generated operator actions exist.",
        "boundary": "No action approval or execution by registry.",
    },
    {
        "capability_id": "cap_bridge_shuttle_transport",
        "component_id": "bridge_shuttle_sync_surfaces",
        "capability_name": "Bridge and shuttle transport mapping",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "read_model_shuttle.py and Mac shuttle scripts exist.",
        "boundary": "No import, export, mount, or sync executed.",
    },
    {
        "capability_id": "cap_role_authority_mapping",
        "component_id": "cassandra_chief_guardian_references",
        "capability_name": "Agent role authority mapping",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "Cassandra, Chief, and Guardian role files and templates are present.",
        "boundary": "Role mapping does not activate agents or grant sends.",
    },
    {
        "capability_id": "cap_legal_boundary_mapping",
        "component_id": "legal_module_surfaces",
        "capability_name": "Legal surface boundary mapping",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "legal path guard, support packet, and legal planning files are present.",
        "boundary": "No legal-private content read or exported.",
    },
    {
        "capability_id": "cap_artifact_policy_mapping",
        "component_id": "business_ops_artifact_policy_surfaces",
        "capability_name": "Protected artifact policy mapping",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "protected_access_broker_concept.py and protected evidence read-models exist.",
        "boundary": "No portal, PDF, workbook, or ledger action.",
    },
)

WORKFLOW_RAILS: tuple[dict[str, str], ...] = (
    {
        "workflow_id": "rail_registry_export",
        "component_id": "generated_read_model_system",
        "rail_name": "Registry export",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "scripts/export_openclaw_system_knowledge_registry.py",
        "boundary": "Writes deterministic generated artifacts only.",
    },
    {
        "workflow_id": "rail_context_to_read_model",
        "component_id": "context_evidence_read_model_substrate",
        "rail_name": "Context to read-model",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "context_selection.py and generated/context_packets paths.",
        "boundary": "Context visibility does not imply authority.",
    },
    {
        "workflow_id": "rail_operator_action",
        "component_id": "operator_action_workflow_surfaces",
        "rail_name": "Operator action request and approval separation",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "operator_action.py and workflow approval-bus contract.",
        "boundary": "Registry does not approve, send, submit, or execute.",
    },
    {
        "workflow_id": "rail_bridge_shuttle",
        "component_id": "bridge_shuttle_sync_surfaces",
        "rail_name": "Mac/PC read-model shuttle",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "read_model_shuttle.py and scripts/prepare_mac_read_model_shuttle.py.",
        "boundary": "No shuttle command is run by registry export.",
    },
    {
        "workflow_id": "rail_protected_access",
        "component_id": "business_ops_artifact_policy_surfaces",
        "rail_name": "Protected access review",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "protected_access_broker_concept.py and guardian gate surfaces.",
        "boundary": "No live account, portal, workbook, PDF, or ledger use.",
    },
    {
        "workflow_id": "rail_polish_loop_review",
        "component_id": "polish_loop_runtime_task_area",
        "rail_name": "Polish loop review",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_basis": "polish_loop/orchestrator.py and builder_output_validator.py.",
        "boundary": "Registry does not start the loop.",
    },
)

KNOWLEDGE_CLAIMS: tuple[dict[str, Any], ...] = (
    {
        "claim_id": "claim_repo_is_openclaw_eyes",
        "subject": "repo identity",
        "claim": "This checkout is the local openclaw-eyes repository intended for WinshipWheatley/openclaw-eyes.",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": [".git/config", ".gitignore", "AGENTS.md"],
        "confidence": "high",
    },
    {
        "claim_id": "claim_required_tables_present",
        "subject": "registry SQLite",
        "claim": "The registry defines the ten required SQLite tables and no registry table begins with sqlite_.",
        "evidence_status": "CONFIRMED_LOCAL_AFTER_EXPORT",
        "evidence_paths": ["generated/system_knowledge/openclaw_system_knowledge_registry.sqlite"],
        "confidence": "high",
    },
    {
        "claim_id": "claim_documentation_only",
        "subject": "authority boundary",
        "claim": "The registry is documentation/read-model/SQLite only and grants no live-action authority.",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": ["openclaw_system_knowledge_registry.py"],
        "confidence": "high",
    },
    {
        "claim_id": "claim_hermes_reference_only",
        "subject": "Hermes",
        "claim": "Hermes is locally visible as planning/template/service-reference material, not activated by this registry.",
        "evidence_status": "PARTIAL_LOCAL_REFERENCE",
        "evidence_paths": [
            "docs/operations/HERMES_MACHINE_CONTRACT.md",
            "templates/agent/hermes_advisory_packet_template.json",
            "systemd/user/hermes-gateway.service.in",
        ],
        "confidence": "medium",
    },
    {
        "claim_id": "claim_external_repos_unknown",
        "subject": "external repos",
        "claim": "External Repo A, Repo B, and runtime state are not confirmed from this local checkout.",
        "evidence_status": "UNKNOWN_EXTERNAL",
        "evidence_paths": [
            "generated/read_models/repo_a_known_rail_completion_map.json",
            "generated/read_models/repo_b_remaining_capability_delta_map.json",
        ],
        "confidence": "medium",
    },
)

KNOWN_UNKNOWNS: tuple[dict[str, str], ...] = (
    {
        "unknown_id": "unknown_external_repo_a",
        "subject": "External Repo A",
        "unknown_status": "UNKNOWN_EXTERNAL",
        "reason": "Local read-models mention Repo A, but the external repo itself is not present here.",
        "next_safe_check": "Inspect the intended external repository in its own checkout when provided.",
    },
    {
        "unknown_id": "unknown_external_repo_b",
        "subject": "External Repo B",
        "unknown_status": "UNKNOWN_EXTERNAL",
        "reason": "Local read-models mention Repo B/runtime intake, but external repo contents are absent.",
        "next_safe_check": "Reconcile the cross-repo estate map with explicit repo paths or remotes.",
    },
    {
        "unknown_id": "unknown_runtime_state",
        "subject": "Runtime state",
        "unknown_status": "UNKNOWN_BY_BOUNDARY",
        "reason": "No services or runtime probes were started for this registry.",
        "next_safe_check": "Use a separate runtime validation prompt if service inspection is authorized.",
    },
    {
        "unknown_id": "unknown_prior_codex_web_commit",
        "subject": "Prior Codex Web registry commit",
        "unknown_status": "UNKNOWN_UNREACHABLE",
        "reason": "Reported commit c5b83f6cda91daf25b95367e6d94e0d8890ffea3 was not available locally.",
        "next_safe_check": "Stop chasing the SHA; validate this local branch and pushed branch instead.",
    },
    {
        "unknown_id": "unknown_clara_runtime",
        "subject": "Clara runtime identity",
        "unknown_status": "REFERENCE_ONLY_UNKNOWN",
        "reason": "A Cassandra/Clara generated read-model reference exists, but no Clara runtime is confirmed.",
        "next_safe_check": "Treat Clara as reference-only until a source component is visible.",
    },
    {
        "unknown_id": "unknown_live_arts_pdf_helper",
        "subject": "Live Arts PDF export/helper implementation",
        "unknown_status": "UNKNOWN_OR_OUT_OF_SCOPE",
        "reason": "The registry task names the architecture as future work; this repo evidence does not authorize PDF export.",
        "next_safe_check": "Design helper architecture separately without generating PDFs in this validation.",
    },
    {
        "unknown_id": "unknown_registry_pr_source",
        "subject": "Codex Web PR source",
        "unknown_status": "UNKNOWN_UNPUBLISHED",
        "reason": "Codex Web reported a failed push through a 403 tunnel and no PR URL.",
        "next_safe_check": "Use this local branch as the review source after successful SSH push.",
    },
)

BUILD_TASKS: tuple[dict[str, Any], ...] = (
    {
        "task_id": "task_01_repo_topology",
        "task_rank": 1,
        "title": "Reconcile repo topology / cross-repo estate map",
        "model_class_recommendation": "high-context reasoning model",
        "rationale": "Resolve local Repo A, Repo B, runtime, Mission Control, and openclaw-eyes boundaries before implementation.",
        "status": "NEXT_BOUNDED_TASK",
        "boundary": "Read-only repo/path analysis; no merge or runtime action.",
    },
    {
        "task_id": "task_02_adopt_registry_later",
        "task_rank": 2,
        "title": "Adopt registry into Hermes/Chief later",
        "model_class_recommendation": "systems architecture model",
        "rationale": "Wire this deterministic registry into existing agent surfaces only after review.",
        "status": "FUTURE_INTEGRATION",
        "boundary": "No Hermes or Chief activation in this branch.",
    },
    {
        "task_id": "task_03_preserve_source_of_truth",
        "task_rank": 3,
        "title": "Preserve Evidence-Grounded Context Registry as source of truth",
        "model_class_recommendation": "deterministic code model",
        "rationale": "Keep registry facts tied to evidence paths, freshness, and known unknowns.",
        "status": "ARCHITECTURE_GUARD",
        "boundary": "No invented external evidence.",
    },
    {
        "task_id": "task_04_avoid_vector_duplication",
        "task_rank": 4,
        "title": "Avoid duplicating deterministic registry with generic vector RAG",
        "model_class_recommendation": "retrieval-design model",
        "rationale": "Use the registry for exact system facts and reserve embeddings for separate exploratory retrieval.",
        "status": "DESIGN_GUARD",
        "boundary": "No indexing or embedding in this branch.",
    },
    {
        "task_id": "task_05_mac_pc_transport",
        "task_rank": 5,
        "title": "Mac/PC artifact transport policy",
        "model_class_recommendation": "cross-platform systems model",
        "rationale": "Clarify shuttle/import/export policy and what may cross Mac/PC boundaries.",
        "status": "POLICY_NEXT",
        "boundary": "No mount, import, sync, or launcher execution.",
    },
    {
        "task_id": "task_06_live_arts_pdf_helper",
        "task_rank": 6,
        "title": "Live Arts PDF export/helper architecture",
        "model_class_recommendation": "macOS/Python helper architecture model",
        "rationale": "Design helper responsibilities and failure modes before any actual PDF export.",
        "status": "ARCHITECTURE_ONLY",
        "boundary": "No PDF generation in this registry branch.",
    },
    {
        "task_id": "task_07_access_broker_permissions",
        "task_rank": 7,
        "title": "Access Broker permissions",
        "model_class_recommendation": "security/policy model",
        "rationale": "Keep protected access gates explicit before portal, account, or artifact handling.",
        "status": "POLICY_NEXT",
        "boundary": "No browser, Coupa, Gmail, workbook, or credential access.",
    },
    {
        "task_id": "task_08_request_response_stability",
        "task_rank": 8,
        "title": "Request/response stability",
        "model_class_recommendation": "test/stability model",
        "rationale": "Stabilize request, receipt, and display contracts before broader UI integration.",
        "status": "TEST_NEXT",
        "boundary": "No production mutation.",
    },
    {
        "task_id": "task_09_payment_watch_ledger",
        "task_rank": 9,
        "title": "Payment watch / ledger readiness",
        "model_class_recommendation": "finance-control/guardrail model",
        "rationale": "Separate evidence references, payment-watch status, and ledger readiness before any money workflow.",
        "status": "GUARDED_FUTURE_WORK",
        "boundary": "No ledger mutation and no workbook cell reads.",
    },
    {
        "task_id": "task_10_stale_ui_chat_card_drift",
        "task_rank": 10,
        "title": "Stale UI/chat-card drift checks",
        "model_class_recommendation": "UI regression/review model",
        "rationale": "Detect stale cards and chat display drift against deterministic read-model outputs.",
        "status": "REVIEW_NEXT",
        "boundary": "No UX feature work in this branch.",
    },
)

AGENT_ROLES: tuple[dict[str, Any], ...] = (
    {
        "role_id": "role_operator",
        "agent_name": "Operator",
        "role_summary": "Human authority holder represented by operator-facing contracts and read-models.",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": ["Operator/00_READ_ME_FIRST.md", "OPERATOR_EXTENSION_MANIFESTO.md"],
        "authority_notes": "Registry does not replace operator approval.",
    },
    {
        "role_id": "role_chief",
        "agent_name": "Chief",
        "role_summary": "Local orchestration, routing, approval, reporting, and specialist brain surfaces.",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": ["chief_router.py", "chief_approval_brain.py", "docs/operations/CHIEF_MACHINE_CONTRACT.md"],
        "authority_notes": "Reference only; no Chief service is started.",
    },
    {
        "role_id": "role_cassandra",
        "agent_name": "Cassandra",
        "role_summary": "Correspondence, contact policy, outreach, listener, and briefing surfaces.",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": ["cassandra_brain.py", "cassandra_listener.py", "cassandra_contact_policy.py"],
        "authority_notes": "Reference only; no email or calendar access.",
    },
    {
        "role_id": "role_guardian",
        "agent_name": "Guardian",
        "role_summary": "Protected access gate, approval packet, and sensitive-action review surfaces.",
        "evidence_status": "CONFIRMED_LOCAL",
        "evidence_paths": [
            "guardian_protected_access_gate_spec.py",
            "templates/agent/guardian_approval_request_packet_template.json",
            "docs/operations/GUARDIAN_MACHINE_CONTRACT.md",
        ],
        "authority_notes": "Reference only; no approval or execution.",
    },
    {
        "role_id": "role_hermes",
        "agent_name": "Hermes",
        "role_summary": "Advisory/gateway reference visible in docs, templates, and service template.",
        "evidence_status": "PARTIAL_LOCAL_REFERENCE",
        "evidence_paths": [
            "docs/operations/HERMES_MACHINE_CONTRACT.md",
            "templates/agent/hermes_advisory_packet_template.json",
            "systemd/user/hermes-gateway.service.in",
        ],
        "authority_notes": "Planning/reference only; no gateway service is installed or started.",
    },
    {
        "role_id": "role_clara",
        "agent_name": "Clara",
        "role_summary": "Reference-only name in generated read-model evidence; runtime identity is unknown.",
        "evidence_status": "REFERENCE_ONLY_UNKNOWN",
        "evidence_paths": ["generated/read_models/cassandra_clara_fact_packet.json"],
        "authority_notes": "Do not treat Clara as confirmed runtime without additional repo evidence.",
    },
)

ARTIFACT_POLICIES: tuple[dict[str, str], ...] = (
    {
        "policy_id": "policy_json_read_model",
        "artifact_name": "Registry JSON read-model",
        "allowed_surfaces": "generated/read_models/openclaw_system_knowledge_registry.json",
        "blocked_actions": "No external source fetch, no private-root scan, no live account action.",
        "evidence_basis": "Generated by local exporter from static local evidence inventory.",
        "evidence_status": "CONFIRMED_LOCAL",
    },
    {
        "policy_id": "policy_operator_markdown",
        "artifact_name": "Operator markdown summary",
        "allowed_surfaces": "generated/read_models/openclaw_system_knowledge_registry_OPERATOR.md",
        "blocked_actions": "No authority promotion beyond summary/display.",
        "evidence_basis": "Derived from registry payload.",
        "evidence_status": "CONFIRMED_LOCAL",
    },
    {
        "policy_id": "policy_sqlite_registry",
        "artifact_name": "SQLite registry",
        "allowed_surfaces": "generated/system_knowledge/openclaw_system_knowledge_registry.sqlite",
        "blocked_actions": "No runtime DB, no service DB, no ledger DB, no production DB.",
        "evidence_basis": "Generated SQLite file with required tables only.",
        "evidence_status": "CONFIRMED_LOCAL",
    },
    {
        "policy_id": "policy_schema_seed_sql",
        "artifact_name": "Schema and seed SQL",
        "allowed_surfaces": "generated/system_knowledge/*_SCHEMA.sql and *_SEED.sql",
        "blocked_actions": "No migration authority and no external database execution.",
        "evidence_basis": "Static SQL mirrors generated local SQLite registry.",
        "evidence_status": "CONFIRMED_LOCAL",
    },
    {
        "policy_id": "policy_protected_artifacts",
        "artifact_name": "Protected PDF/workbook/Coupa/ledger artifacts",
        "allowed_surfaces": "Metadata and policy references only.",
        "blocked_actions": "No PDF export, workbook cell read, Coupa/browser access, or ledger mutation.",
        "evidence_basis": "Protected access broker and finance artifact policy surfaces.",
        "evidence_status": "CONFIRMED_LOCAL_BOUNDARY",
    },
    {
        "policy_id": "policy_mac_pc_transport",
        "artifact_name": "Mac/PC transport artifacts",
        "allowed_surfaces": "Read-model shuttle manifests and context packs only after separate authorization.",
        "blocked_actions": "No shuttle command, mount recovery, import, export, or sync from this registry.",
        "evidence_basis": "read_model_shuttle.py and bridge manual recovery surfaces.",
        "evidence_status": "CONFIRMED_LOCAL_BOUNDARY",
    },
)

DISPLAY_SURFACES: tuple[dict[str, str], ...] = tuple(
    {
        "surface_id": f"display_{table}",
        "surface_name": table.replace("_", " ").title(),
        "table_name": table,
        "display_purpose": "Operator review and exact registry inspection.",
        "operator_notes": "Display-only table; no row grants action authority.",
    }
    for table in REQUIRED_TABLES
)

REPO_RELATIONSHIP_ANALYSIS: tuple[dict[str, Any], ...] = (
    {
        "analysis_id": "rel_local_main_origin",
        "relationship_name": "Local main and origin/main",
        "local_evidence_status": "CONFIRMED_BY_GIT_STATUS",
        "conclusion": "Work started from clean local main at origin/main before creating the local registry branch.",
        "known_unknown_refs": [],
        "next_step": "Review and merge only after validation and explicit instruction.",
    },
    {
        "analysis_id": "rel_cassandra_wip",
        "relationship_name": "Cassandra correspondence WIP branch",
        "local_evidence_status": "CONFIRMED_BY_GIT_BRANCH",
        "conclusion": "wip/cassandra-correspondence-contract exists and remains untouched by this branch.",
        "known_unknown_refs": [],
        "next_step": "Do not merge or modify the WIP branch during registry review.",
    },
    {
        "analysis_id": "rel_repo_a_repo_b",
        "relationship_name": "Repo A and Repo B references",
        "local_evidence_status": "UNKNOWN_EXTERNAL",
        "conclusion": "Local read-models mention Repo A and Repo B, but external repos are not confirmed here.",
        "known_unknown_refs": ["unknown_external_repo_a", "unknown_external_repo_b"],
        "next_step": "Create a cross-repo estate map when the external repositories are available.",
    },
    {
        "analysis_id": "rel_runtime",
        "relationship_name": "Runtime state",
        "local_evidence_status": "UNKNOWN_BY_BOUNDARY",
        "conclusion": "Runtime docs and service templates exist, but no service state was inspected.",
        "known_unknown_refs": ["unknown_runtime_state"],
        "next_step": "Use a separate runtime-safe validation plan if needed.",
    },
    {
        "analysis_id": "rel_codex_web_registry",
        "relationship_name": "Codex Web registry work",
        "local_evidence_status": "UNKNOWN_UNREACHABLE",
        "conclusion": "Codex Web reported a local-only commit and failed push; this branch is the local recreation.",
        "known_unknown_refs": ["unknown_prior_codex_web_commit", "unknown_registry_pr_source"],
        "next_step": "Use the pushed local branch or compare URL as the review source.",
    },
)


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def compact_json(payload: Any) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def generated_paths(repo_root: Path) -> dict[str, Path]:
    return {
        "json": repo_root / READ_MODEL_DIR / JSON_EXPORT_NAME,
        "operator_markdown": repo_root / READ_MODEL_DIR / OPERATOR_EXPORT_NAME,
        "sqlite": repo_root / SYSTEM_KNOWLEDGE_DIR / SQLITE_EXPORT_NAME,
        "schema_sql": repo_root / SYSTEM_KNOWLEDGE_DIR / SCHEMA_SQL_EXPORT_NAME,
        "seed_sql": repo_root / SYSTEM_KNOWLEDGE_DIR / SEED_SQL_EXPORT_NAME,
    }


def _path_exists(repo_root: Path, path_text: str) -> bool | None:
    if path_text.startswith("Codex Web report:") or path_text.startswith("local search"):
        return None
    if "*" in path_text:
        return None
    return (repo_root / path_text).exists()


def _source_audit(repo_root: Path) -> dict[str, Any]:
    evidence_paths: list[str] = []
    for component in COMPONENTS:
        evidence_paths.extend(component["evidence_paths"])
    unique_paths = sorted(set(evidence_paths))
    checked = [
        {"path": path, "exists": _path_exists(repo_root, path)}
        for path in unique_paths
        if _path_exists(repo_root, path) is not None
    ]
    return {
        "repo_root_name": repo_root.name,
        "checked_path_count": len(checked),
        "missing_checked_paths": [item["path"] for item in checked if item["exists"] is False],
        "path_check_note": "Directories and pattern-like evidence paths are recorded but not file-existence checked.",
    }


def build_registry(repo_root: Path | str | None = None, generated_at: str = DEFAULT_GENERATED_AT) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else ROOT
    output_paths = generated_paths(root)
    component_count = len(COMPONENTS)
    unknown_count = len(KNOWN_UNKNOWNS)
    coverage = {
        "component_count": component_count,
        "known_unknown_count": unknown_count,
        "eight_seeded_components_is_appropriate": False,
        "assessment": (
            "Eight components would be too shallow for this checkout. Local evidence covers repo identity, "
            "read-models, context/evidence substrate, terrain/operator maps, workflow rails, bridge/shuttle, "
            "agent-role references, mac_eyes, polish_loop, legal, artifact policy, and external unknowns."
        ),
        "covered_high_level_areas": [
            "generated read-model system",
            "work terrain surfaces",
            "operator action / workflow surfaces",
            "Cassandra / Chief / Guardian references",
            "mac_eyes / bridge / shuttle surfaces",
            "polish_loop runtime task area",
            "legal module",
            "context / evidence / read-model substrate",
            "external Repo A / Repo B / runtime UNKNOWN",
        ],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "registry_id": READ_MODEL_ID,
        "registry_name": REGISTRY_NAME,
        "generated_at": generated_at,
        "repo": {
            "name": "openclaw-eyes",
            "intended_remote": "git@github.com:WinshipWheatley/openclaw-eyes.git",
            "local_path": str(root),
            "branch_created_for_local_recreation": "codex/system-knowledge-registry-v0-local",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "required_sqlite_tables": list(REQUIRED_TABLES),
        "sqlite_table_prefix_rule": "No registry table name may begin with sqlite_.",
        "component_inventory": list(COMPONENTS),
        "capabilities": list(CAPABILITIES),
        "workflow_rails": list(WORKFLOW_RAILS),
        "knowledge_claims": list(KNOWLEDGE_CLAIMS),
        "known_unknowns": list(KNOWN_UNKNOWNS),
        "top_build_tasks": list(BUILD_TASKS),
        "agent_roles": list(AGENT_ROLES),
        "artifact_policies": list(ARTIFACT_POLICIES),
        "registry_sqlite_display_surfaces": list(DISPLAY_SURFACES),
        "repo_relationship_analysis": list(REPO_RELATIONSHIP_ANALYSIS),
        "coverage_assessment": coverage,
        "source_audit": _source_audit(root),
        "generated_outputs": {name: str(path.relative_to(root)) for name, path in output_paths.items()},
    }


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
        "build_task": list(payload["top_build_tasks"]),
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
        "registry_sqlite_display_surface": list(payload["registry_sqlite_display_surfaces"]),
        "repo_relationship_analysis": [
            {
                "analysis_id": row["analysis_id"],
                "relationship_name": row["relationship_name"],
                "local_evidence_status": row["local_evidence_status"],
                "conclusion": row["conclusion"],
                "known_unknown_refs_json": compact_json(row["known_unknown_refs"]),
                "next_step": row["next_step"],
            }
            for row in payload["repo_relationship_analysis"]
        ],
    }


def schema_sql() -> str:
    statements: list[str] = [
        "-- OpenClaw Eyes System Knowledge Registry schema",
        "-- Generated for documentation/read-model/SQLite review only.",
    ]
    for table in REQUIRED_TABLES:
        columns = TABLE_COLUMNS[table]
        column_lines = ["  " + column + " TEXT NOT NULL" for column in columns]
        if table == "build_task":
            column_lines = [
                "  " + ("task_rank INTEGER NOT NULL" if column == "task_rank" else column + " TEXT NOT NULL")
                for column in columns
            ]
        pk_column = columns[0]
        column_lines.append(f"  PRIMARY KEY ({pk_column})")
        statements.append(f"CREATE TABLE IF NOT EXISTS {table} (\n" + ",\n".join(column_lines) + "\n);")
    return "\n\n".join(statements) + "\n"


def _sql_literal(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    text = str(value).replace("'", "''")
    return f"'{text}'"


def seed_sql(payload: dict[str, Any]) -> str:
    rows_by_table = sqlite_rows(payload)
    lines = [
        "-- OpenClaw Eyes System Knowledge Registry seed data",
        "-- Generated for documentation/read-model/SQLite review only.",
    ]
    for table in REQUIRED_TABLES:
        columns = TABLE_COLUMNS[table]
        lines.append(f"DELETE FROM {table};")
        for row in rows_by_table[table]:
            values = ", ".join(_sql_literal(row[column]) for column in columns)
            column_list = ", ".join(columns)
            lines.append(f"INSERT INTO {table} ({column_list}) VALUES ({values});")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_operator_markdown(payload: dict[str, Any]) -> str:
    coverage = payload["coverage_assessment"]
    lines = [
        "# OpenClaw Eyes System Knowledge Registry",
        "",
        "## Summary",
        f"- Registry ID: `{payload['registry_id']}`",
        f"- Schema version: `{payload['schema_version']}`",
        f"- Component count: {coverage['component_count']}",
        f"- Known unknown count: {coverage['known_unknown_count']}",
        "- Boundary: documentation/read-model/SQLite only.",
        "- READY means local registry artifacts validated, not merged to main.",
        "",
        "## Authority Boundary",
    ]
    for key, value in payload["authority_boundary"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Required SQLite Tables"])
    for table in payload["required_sqlite_tables"]:
        lines.append(f"- `{table}`")
    lines.extend(["", "## Coverage Assessment", coverage["assessment"], "", "## Components"])
    for component in payload["component_inventory"]:
        lines.append(
            f"- `{component['component_id']}`: {component['evidence_status']} - {component['summary']}"
        )
    lines.extend(["", "## Known Unknowns"])
    for unknown in payload["known_unknowns"]:
        lines.append(
            f"- `{unknown['unknown_id']}`: {unknown['subject']} - {unknown['unknown_status']}. "
            f"Next: {unknown['next_safe_check']}"
        )
    lines.extend(["", "## Top 10 Build Tasks"])
    for task in payload["top_build_tasks"]:
        lines.append(
            f"{task['task_rank']}. {task['title']} "
            f"({task['model_class_recommendation']}) - {task['status']}"
        )
    lines.extend(["", "## Generated Outputs"])
    for name, path in payload["generated_outputs"].items():
        lines.append(f"- `{name}`: `{path}`")
    return "\n".join(lines) + "\n"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_sqlite(path: Path, payload: dict[str, Any]) -> None:
    def write_database(database_path: Path) -> None:
        rows_by_table = sqlite_rows(payload)
        with sqlite3.connect(database_path) as conn:
            conn.executescript(schema_sql())
            for table in REQUIRED_TABLES:
                columns = TABLE_COLUMNS[table]
                placeholders = ", ".join("?" for _ in columns)
                column_list = ", ".join(columns)
                values = [tuple(row[column] for column in columns) for row in rows_by_table[table]]
                conn.executemany(
                    f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})",
                    values,
                )
            conn.commit()

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="openclaw_registry_") as temp_dir:
        temp_path = Path(temp_dir) / path.name
        write_database(temp_path)
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
    parser = argparse.ArgumentParser(description="Export the OpenClaw Eyes System Knowledge Registry.")
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

    if args.format == "paths":
        for key in ("json", "operator_markdown", "sqlite", "schema_sql", "seed_sql"):
            print(paths[key].relative_to(Path(args.repo_root)))
    elif args.format == "json":
        print(stable_json(payload), end="")
    elif args.format == "markdown":
        print(render_operator_markdown(payload), end="")
    elif args.format == "sqlite":
        print(paths["sqlite"].relative_to(Path(args.repo_root)))
    else:
        print(
            f"{READ_MODEL_ID}: components={result['component_count']} "
            f"known_unknowns={result['known_unknown_count']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

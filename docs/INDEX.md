# OpenClaw Documentation Index

Central entry point for OpenClaw knowledge, repository structure, and operational guides.

## Repository Law & Identity

- [**Runtime Law**](../OPENCLAW_RUNTIME.md) — Canonical execution rules and safety mandates.
- [**User Identity**](../USER.md) — Operator preferences and communication style.
- [**Agent Roles**](../AGENTS.md) — Mapping of autonomous personalities to responsibilities.

## Operational Surfaces

- [**Runbook**](../RUNBOOK.md) — Exact bash commands for stack management and smoke tests.
- [**Unified Restart**](../scripts/start_all.sh) — authoritative one-liner to restart the full OpenClaw environment.
- [**Current State**](../CURRENT_STATE.md) — Latest technical snapshot and active constraints.
- [**Next Actions**](../NEXT_ACTIONS.md) — High-level roadmap and pending tasks.

## Knowledge Lanes

### 0. Core Doctrine

- [Truth and Reality](./doctrine/TRUTH_AND_REALITY.md) — Evidence hierarchy and sourcing rules.
- [Operator Communication](./doctrine/OPERATOR_COMMUNICATION.md) — Standardized escalation and 4-line assist blocks.
- [Surface Authority](./doctrine/SURFACE_AUTHORITY.md) — Canonical paths vs. mirrors.

### 1. Operations & Governance

- [Doc Governance](./operations/DOC_GOVERNANCE.md) — Lifecycle and authority for this `docs/` folder.
- [Doc Lifecycle](./operations/DOC_LIFECYCLE.md) — Rules for identifying and archiving stale material.
- [Dependency Hygiene](./operations/DEPENDENCY_HYGIENE.md) — Architectural boundaries and import rules.
- [Intent and Control Map](./operations/OPENCLAW_INTENT_AND_CONTROL_MAP.md) — Cross-lane authority map, progressive discovery contract, and integration-readiness notes.
- [MCP Progressive Discovery Profiles](./operations/MCP_PROGRESSIVE_DISCOVERY_PROFILES.md) — Hardened default filesystem profile and explicit unlock contracts.
- [OpenRouter Key Storage](./operations/OPENROUTER_KEY_STORAGE.md) — Non-printing key metadata, optional-provider boundaries, and approval rules for guarded OpenRouter use.
- [Known Gaps](../KNOWN_GAPS.md) — Systemic issues and un-implemented features.

### 2. Testing & Verification

- [Testing System](./testing/TESTING_SYSTEM.md) — Strategy and hierarchy overview.
- [Validation Map](./testing/VALIDATION_MAP.md) — Mandatory test lookup table for modified files.
- [Validation Policy](./testing/VALIDATION_POLICY.md) — Definition of Done and required validation levels.
- [Harness Index](./testing/HARNESS_INDEX.md) — Guide to specialized Python harnesses.

### 3. Engineering & Specs

- [Inner-Circle Specs](./specs/spec-inner-circle-correspondence.md) — Detailed workflow for identity-gated replies.
- [Google Drive MCP Contract](./specs/google_drive_mcp_contract.md) — Candidate, non-canonical Drive MCP setup note pending live verification.
- [AI Working Context](./_ai/AI_WORKING_CONTEXT.md) — High-density context for agentic loading.

### Planning Packages

- [Command Atlas / OpenClaw System Program Map](./planning/command_atlas/00_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md) — Top-level system-of-systems planning layer; Operator Harness is a lane/view/cockpit beneath it, not the whole system.
- [Operator North Star Machine Contract](./planning/launch_ladder/source_set_bridges/operator_north_star_machine_contract_20260505.md) — Top-layer operator-intent contract for preserving the receivables/chase-money steel thread, active-stoicism daily-life burden reduction, creative garden bounded surprise, knowledge compiler loop, operator-native interaction contract, creative/business leverage, modular product-transfer goals, and future idea bounce rule; intent authority only, not backend/API/schema/SQLite/ingestion/runtime/app, provider/model, Hermes, MCP, private-root, source-set generation, or implementation authority.
- [Hermes Systems Engineering Run Mode Spec](./planning/command_atlas/01_HERMES_SYSTEMS_ENGINEERING_RUN_MODE_SPEC.md) — Non-authoritative coherence-tuning lane with Level 1 docs-only, Level 2 metadata topology, and Level 3 approved external scout packet boundaries; not runtime, provider, MCP, messaging, private-data, source-set, or migration authority.
- [External Communications / Relationship Judgment Lane](./planning/command_atlas/02_EXTERNAL_COMMUNICATIONS_RELATIONSHIP_JUDGMENT_LANE.md) — External-facing communication judgment doctrine for customer, client, venue, contractor, friend-of-system, outside-circle, and relationship-risk interactions; supports drafts, risk notes, posture recommendations, and escalation recommendations, not sending, legal/financial advice, private-data disclosure, authority transfer, or relationship automation.
- [Agentic Build-Loop / GitHub Action Pattern Without Claude](./planning/command_atlas/03_AGENTIC_BUILD_LOOP_GITHUB_ACTION_PATTERN_WITHOUT_CLAUDE.md) — Architectural planning lane for borrowing headless job packets, explicit tool/path allowlists, structured receipts, resumable state handles, and CI/PR feedback loops while keeping execution local-first, approval-gated, non-Claude, sensitive-data-safe, and explicit-authority-only; not Claude tooling, workflow creation, cloud-agent commits, private-data access, provider/model prompt leakage, or hidden CI authority.
- [Context Development Lifecycle And Context Filter Doctrine](./planning/command_atlas/04_CONTEXT_DEVELOPMENT_LIFECYCLE_AND_CONTEXT_FILTER_DOCTRINE.md) — Command Atlas doctrine for treating source sets, manifests, prompts, skills, handoffs, job packets, receipts, eval notes, and planning docs as engineered context packages with provenance, linting/evals, observability, regeneration, and pre-execution filtering; not provider/model, MCP, Hermes, ingestion, indexing, SQLite, source-set generation, runtime, implementation, or private-root authority.
- [04 Backend Data Contract Readiness Context-Filter Freshness Bridge](./planning/launch_ladder/source_set_bridges/04_backend_data_contract_readiness_context_filter_freshness_bridge_20260505.md) — Freshness bridge requiring the post-`38294f9` Context Development Lifecycle / Context Filter doctrine before `04_BACKEND_DATA_CONTRACT_READINESS` is used for backend implementation readiness, source-set use, agent/build-loop packets, or context-package generation; preserves the source set as useful planning input while blocking standalone implementation, ingestion, SQLite, indexing, embeddings, extraction, chunking, provider/model, Hermes, MCP, private-root, source-set regeneration, and runtime authority.
- [Windows Root Triage / Dependency Map Plan](./planning/launch_ladder/27_WINDOWS_ROOT_TRIAGE_AND_DEPENDENCY_MAP_PLAN.md) — Metadata-only sequencing for Windows root dependency mapping; read with the [PC Windows roots boundary](./planning/launch_ladder/26_PC_WINDOWS_ROOTS_PRIVATE_DATA_BOUNDARY_BREADCRUMB.md), [dependency-map template](./planning/launch_ladder/28_WINDOWS_ROOT_DEPENDENCY_MAP_TEMPLATE.md), and [current dependency map](./planning/launch_ladder/29_WINDOWS_ROOT_DEPENDENCY_MAP.md); classification/exclusion guidance only before backend source-set planning, not cleanup, migration, source-set inclusion, backend build-prep, bridge, ingestion, provider/model, MCP, SQLite, FTS, embedding, chunking, extraction, or private-root browsing authority.
- [Backend Source-Set Bridge And Exclusion Plan](./planning/launch_ladder/30_BACKEND_SOURCE_SET_BRIDGE_AND_EXCLUSION_PLAN.md) — Compact bridge for using Windows dependency-map docs in `04_BACKEND_DATA_CONTRACT_READINESS` planning as exclusion/classification guidance only; not private-root content, backend input authority, ingestion, indexing, SQLite, provider/model, MCP, runtime, cleanup, migration, or source-set generation authority.
- [Backend Data Contract First Planning Slice Decision](./planning/launch_ladder/source_set_bridges/backend_data_contract_first_planning_slice_decision_20260505.md) — Docs-only decision selecting a Markdown semantic contract matrix as the first safe backend/data-contract planning slice after the source-set 04 context-filter bridge; not backend/API/schema/SQLite/ingestion/runtime, source-set generation, private-root, provider/model, Hermes, MCP, or implementation-readiness authority.
- [Backend Data Contract Semantic Matrix Plan](./planning/launch_ladder/source_set_bridges/backend_data_contract_semantic_matrix_plan_20260505.md) — Docs-only semantic contract matrix for backend/data-contract readiness planning, defining future record meanings, evidence/freshness/provenance, authority/sensitivity boundaries, source categories, relationships, and validation gates; not database schema, API, SQLite, ingestion, fixtures, runtime, app implementation, source-set generation, private-root, provider/model, Hermes, MCP, or implementation-readiness authority.
- [Backend Data Contract Semantic Contract Matrix](./planning/launch_ladder/source_set_bridges/backend_data_contract_semantic_contract_matrix_20260505.md) — Durable docs-only semantic contract matrix defining backend/data-contract entities, allowed states, evidence/freshness/provenance fields, authority/sensitivity boundaries, relationships, knowledge compiler loop preservation, excluded/unknown classifications, validation gates, and future handoff requirements; not backend/API/schema/SQLite/ingestion/fixtures/runtime/app code, private-root, provider/model, Hermes, MCP, source-set generation, or implementation authority.
- [Backend Data Contract Implementation-Readiness Checklist](./planning/launch_ladder/source_set_bridges/backend_data_contract_implementation_readiness_checklist_20260505.md) — Docs-only readiness checklist defining gates that must pass before any separate future backend/data-contract implementation prompt; not backend/API/schema/SQLite/ingestion/fixtures/runtime/app code, private-root, provider/model, Hermes, MCP, source-set generation, or implementation authority.
- [Backend Data Contract First Implementation Slice Readiness](./planning/launch_ladder/source_set_bridges/backend_data_contract_first_implementation_slice_readiness_20260505.md) — Docs-only decision selecting static semantic-contract enforcement in the existing Launch Ladder checker/test harness as the first safe future implementation slice, with exact allowed future edit paths, forbidden paths/actions, preserved matrix meanings, checklist gates, validation receipts, and next-step authority; not backend/API/schema/SQLite/ingestion/fixtures/runtime/app code, private-root, provider/model, Hermes, MCP, source-set generation, or runtime authority.
- [Backend Data Contract Storage Schema Plan](./planning/launch_ladder/source_set_bridges/backend_data_contract_storage_schema_plan_20260505.md) — Docs-only storage/schema planning bridge for eventually mapping the pure-Python backend contract spine to SQLite/storage concepts while preserving raw/compiled/wiki/relationship/synthesis/write-back separation, labels, provenance, freshness, sensitivity, authority, review status, operator promotion, and receivables/accountability boundaries; not SQLite, schema migrations, persistence, API, ingestion, indexing, embeddings, runtime, provider/model, private-root, or fixture implementation authority.
- [Lane A OpenRouter Scout Backlog](./planning/OPENCLAW_LANE_A_OPENROUTER_SCOUT_BACKLOG.md) — Future-only cloud scout/overflow note for public/synthetic work; not runtime doctrine.
- [OpenClaw Legal Planning Package](./planning/openclaw_legal/law_program/LEGAL_V1_CONTRACT_INDEX.md) — Imported planning-only material; not canonical implementation doctrine.

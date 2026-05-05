# Operator Harness Planning Index

Status: docs-only navigation index from the completed Gemini read-only navigation audit. This file helps future agents and human operators choose the right Launch Ladder / Operator Harness planning sources. It is not runtime truth, implementation authority, or permission to mutate services, bridges, storage, app code, secrets, or existing planning docs.

Generated/reviewed: 2026-05-05

Source basis:

- Completed Gemini read-only navigation audit as summarized for this task.
- Current PC WSL canonical workspace at `/home/openclaw`.
- Current Launch Ladder planning file inventory.

## 1. Purpose & North Star

Prevent the Launch Ladder / Operator Harness planning stack from becoming a context trap.

This index tells future agents what to read, in what order, what each planning lane is for, and which documents are canonical baseline, bridge/addendum, source-set input, prior art, deployment doctrine, hardening doctrine, or non-canonical mirror reference.

North star:

- Command Atlas / OpenClaw System Program is the top-level system-of-systems planning layer.
- Operator Harness is a lane/view/cockpit under Command Atlas, not the whole system.
- PC WSL `/home/openclaw` remains canonical unless a later canonical doc says otherwise.
- Documents `00` through `18` are baseline planning docs.
- Later changes should usually use addenda, breadcrumbs, and bridge documents rather than heavy rewrites of the baseline package.
- Mac mirror packets are useful planning/reference surfaces, not runtime truth.
- Stale dashboard/status files are prior art only unless refreshed and promoted.
- Visual packets are taste/source-set planning inputs, not implementation authority.

## 2. Current State & Warning Boundaries

Current canonical posture:

- PC WSL Ubuntu-E at `/home/openclaw` is the canonical Launch Ladder / Operator Harness planning workspace.
- Mac mirror surfaces may contain valuable imported planning packets, but they do not override PC WSL repo state.
- Deployment/bridge docs constrain future implementation but do not authorize runtime changes.
- Agentic hardening docs constrain process but do not authorize implementation.
- Command Atlas docs frame the system program layer and Hermes systems-engineering prep, but do not authorize implementation, runtime activation, provider/model calls, MCP invocation, messaging, private-data inspection, source-set mutation, root migration, or commits.
- `19_OPERATOR_WORLD_MODEL_BUILD_READINESS_ADDENDUM.md` updates earlier generic dashboard/card assumptions toward Bridge/Captain's View, Helm, Chart Room, Engine Room, and authority-scope/place language.
- If another local planning artifact shares a numeric prefix, do not renumber files from this index. Use filenames and categories, not numeric prefix alone, as authority.

Warning boundary:

This index should reduce context load. It should not become a place to restate every planning document.

## 3. Task-Specific Read Orders

### Command Atlas / Systems Engineering Prep

1. `docs/planning/command_atlas/00_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md`
2. `docs/planning/command_atlas/01_HERMES_SYSTEMS_ENGINEERING_RUN_MODE_SPEC.md`
3. `docs/planning/launch_ladder/26_PC_WINDOWS_ROOTS_PRIVATE_DATA_BOUNDARY_BREADCRUMB.md`
4. `docs/planning/launch_ladder/20_DEPLOYMENT_TOPOLOGY_NODE_PORTABILITY_AND_OS_AGNOSTICISM.md`
5. `docs/planning/launch_ladder/22_CROSS_PLATFORM_BRIDGE_CONTRACT_BREADCRUMB.md`
6. `docs/planning/launch_ladder/24_OPERATOR_HARNESS_PLANNING_INDEX.md`

This read order is for Command Atlas / systems-engineering preparation only. It does not authorize implementation, runtime activation, provider/model calls, MCP invocation, messaging, private-data inspection, source-set mutation, root migration, bridge behavior changes, or commits.

### Windows Root Dependency-Map Prep

1. `docs/planning/command_atlas/00_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md`
2. `docs/planning/launch_ladder/26_PC_WINDOWS_ROOTS_PRIVATE_DATA_BOUNDARY_BREADCRUMB.md`
3. `docs/planning/launch_ladder/27_WINDOWS_ROOT_TRIAGE_AND_DEPENDENCY_MAP_PLAN.md`
4. `docs/planning/launch_ladder/28_WINDOWS_ROOT_DEPENDENCY_MAP_TEMPLATE.md`
5. `docs/planning/launch_ladder/24_OPERATOR_HARNESS_PLANNING_INDEX.md`

This read order is for metadata-only dependency-map preparation. `27_WINDOWS_ROOT_TRIAGE_AND_DEPENDENCY_MAP_PLAN.md` defines the future triage/dependency-map plan, and `28_WINDOWS_ROOT_DEPENDENCY_MAP_TEMPLATE.md` is a template only, not the actual audit and not cleanup, migration, source-set, backend, bridge, or Operator Harness ingestion authority. Windows cleanup, migration, source-set inclusion, Operator Harness ingestion, bridge changes, and backend build-prep remain blocked until dependency mapping, private-root exclusions, owner review, and an approved move manifest exist; private roots must not enter source sets, agent browsing, provider/model context, or Operator Harness ingestion unless explicitly approved.

### Visual/UI Continuation

1. `docs/planning/launch_ladder/19_OPERATOR_WORLD_MODEL_BUILD_READINESS_ADDENDUM.md`
2. `docs/planning/launch_ladder/visual/operator_harness_north_star_v1/01_NORTH_STAR_AND_TASTE.md`
3. `docs/planning/launch_ladder/13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md`
4. `docs/planning/launch_ladder/12_MAC_DESKTOP_MISSION_CONTROL_FIXTURE_CONTRACT.md`

### Backend/Data-Contract Continuation

1. `docs/planning/launch_ladder/17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md`
2. `docs/planning/launch_ladder/18_BACKEND_DATA_CONTRACT_SHAPE_PLAN.md`
3. `docs/planning/launch_ladder/19_OPERATOR_WORLD_MODEL_BUILD_READINESS_ADDENDUM.md`
4. `docs/planning/launch_ladder/knowledge_substrate/02_SQLITE_LAYER_MODEL.md` if present, or the imported equivalent if differently named.

### Deployment/Portability Continuation

1. `docs/planning/launch_ladder/20_DEPLOYMENT_TOPOLOGY_NODE_PORTABILITY_AND_OS_AGNOSTICISM.md`
2. `docs/planning/launch_ladder/20_PC_STORAGE_RELIEF_LAUNCH_PACKET_PLAN.md` if present.
3. `docs/planning/launch_ladder/21_WSL_RELOCATION_AND_C_DRIVE_RELIEF_BREADCRUMB.md` if present.

### Bridge Replacement/Design Continuation

1. `docs/planning/launch_ladder/22_CROSS_PLATFORM_BRIDGE_CONTRACT_BREADCRUMB.md`
2. `docs/planning/launch_ladder/source_set_bridges/operator_harness_visual_import_freshness_bridge_20260505.md`

### Agentic Workflow Hardening Continuation

1. `docs/planning/launch_ladder/23_AGENTIC_WORKFLOW_HARDENING_BREADCRUMB.md`

### Local Model Benchmark / PI Local Experiment Continuation

1. `docs/planning/launch_ladder/20_DEPLOYMENT_TOPOLOGY_NODE_PORTABILITY_AND_OS_AGNOSTICISM.md`
2. `docs/planning/launch_ladder/25_LOCAL_MODEL_BENCHMARK_PLAN_QWEN3_6_35B_A3B.md`
3. `docs/planning/launch_ladder/23_AGENTIC_WORKFLOW_HARDENING_BREADCRUMB.md`

This read order is for an experimental local-model benchmark / Hardware Fit Analyzer input only. It does not authorize model install, runtime changes, Chief/Cassandra/PI production routing, service changes, or sensitive-data processing.

### Mac Mirror Cleanup/Reintegration Continuation

1. `docs/planning/launch_ladder/mac_import_planning/00_README_MAC_IMPORT_PLANNING.md` if present.
2. `docs/planning/launch_ladder/mac_import_planning/07_IMPORT_EXECUTION_PLAN.md` if present.

### New ChatGPT Project Visual Brainstorm Continuation

1. `docs/planning/launch_ladder/visual/operator_harness_north_star_v1/08_HIT_THE_GROUND_RUNNING_PROMPT.md`
2. `docs/planning/launch_ladder/visual/operator_harness_north_star_v1/07_FINAL_HANDOFF_PROMPT.md`

## 4. Document Inventory & Categorization

### Command Atlas / System Program Planning

Use these before resuming Operator Harness implementation or broader systems-engineering run-throughs. They establish the top-level OpenClaw System Program frame, keep Operator Harness as a lane/view/cockpit under Command Atlas, and define Hermes as a non-authoritative systems-engineering / coherence-tuning lane.

- `docs/planning/command_atlas/00_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md` - top-level Command Atlas / OpenClaw System Program map, root/data-boundary sequencing gate, lane inventory, and final calibration gate.
- `docs/planning/command_atlas/01_HERMES_SYSTEMS_ENGINEERING_RUN_MODE_SPEC.md` - Hermes run-mode boundary with Level 1 docs-only, Level 2 metadata topology, and Level 3 approved external scout packet modes; not provider/model, MCP, messaging, runtime, queue, source-set, private-data, or migration authority.

### Windows Root Boundary / Dependency Mapping

Use these before preparing any Windows metadata-only audit prompt, cleanup plan, migration plan, source-set inclusion, Operator Harness ingestion, bridge change, or backend build-prep. `/home/openclaw` remains the canonical code/docs/planning repo, and Command Atlas remains the top-layer system map.

- `docs/planning/launch_ladder/26_PC_WINDOWS_ROOTS_PRIVATE_DATA_BOUNDARY_BREADCRUMB.md` - PC/Windows private-data boundary breadcrumb.
- `docs/planning/launch_ladder/27_WINDOWS_ROOT_TRIAGE_AND_DEPENDENCY_MAP_PLAN.md` - future metadata-only Windows root triage/dependency-map plan.
- `docs/planning/launch_ladder/28_WINDOWS_ROOT_DEPENDENCY_MAP_TEMPLATE.md` - dependency-map template only; not actual audit, cleanup, migration, source-set, backend, bridge, or Operator Harness ingestion authority.

### Canonical Baseline

Use these as the baseline planning package. Do not heavily rewrite them unless a future task explicitly authorizes baseline refresh work.

- `docs/planning/launch_ladder/00_NORTH_STAR.md` through `docs/planning/launch_ladder/11_NEXT_IMPLEMENTATION_SEQUENCE.md` if present.
- `docs/planning/launch_ladder/12_MAC_DESKTOP_MISSION_CONTROL_FIXTURE_CONTRACT.md`
- `docs/planning/launch_ladder/13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md`
- `docs/planning/launch_ladder/14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md`
- `docs/planning/launch_ladder/15_MAC_DESKTOP_SOUND_HAPTICS_QUIET_FEEDBACK_ADDENDUM.md`
- `docs/planning/launch_ladder/16_MAC_APP_KNOWLEDGE_SUBSTRATE_SOURCE_SET_BRIEF.md`
- `docs/planning/launch_ladder/17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md`
- `docs/planning/launch_ladder/18_BACKEND_DATA_CONTRACT_SHAPE_PLAN.md`
- `docs/planning/launch_ladder/LAUNCH_LADDER_INDEX.md` if present.

### Bridge/Addendum

Use these when baseline docs are too generic, stale, or missing the bridge/source-set nuance.

- `docs/planning/launch_ladder/19_OPERATOR_WORLD_MODEL_BUILD_READINESS_ADDENDUM.md`
- `docs/planning/launch_ladder/22_CROSS_PLATFORM_BRIDGE_CONTRACT_BREADCRUMB.md`
- `docs/planning/launch_ladder/source_set_bridges/operator_harness_visual_import_freshness_bridge_20260505.md`

### Deployment Doctrine

Use these for portability, node, OS, storage-relief, and bridge-readiness implications. They constrain future implementation but do not authorize runtime changes.

- `docs/planning/launch_ladder/20_DEPLOYMENT_TOPOLOGY_NODE_PORTABILITY_AND_OS_AGNOSTICISM.md`
- `docs/planning/launch_ladder/20_PC_STORAGE_RELIEF_LAUNCH_PACKET_PLAN.md` if present.
- `docs/planning/launch_ladder/21_WSL_RELOCATION_AND_C_DRIVE_RELIEF_BREADCRUMB.md` if present.

### Agentic Hardening Doctrine

Use this for future process hardening, tool-surface boundaries, release artifact gates, context budgets, and clean-room research boundaries. It constrains process but does not authorize implementation.

- `docs/planning/launch_ladder/23_AGENTIC_WORKFLOW_HARDENING_BREADCRUMB.md`

### Local Model / Hardware Fit / Experimental Benchmark Planning

Use this for local-model fit questions, bounded benchmark design, PI Local experiment planning, and future Hardware Fit Analyzer evidence. It is not production routing authority.

- `docs/planning/launch_ladder/25_LOCAL_MODEL_BENCHMARK_PLAN_QWEN3_6_35B_A3B.md` - experiment-lane plan for Qwen3.6-35B-A3B on the PC GTX 1660 Ti 6 GB environment, with llama.cpp-first testing, MoE-aware flags such as `--n-cpu-moe`, `--no-mmap`, `--mlock`, KV-cache quantization, success criteria, and rollback planning.

### Visual/Taste Input

Use these as taste, vocabulary, and ChatGPT Project source-set planning inputs. They are not app-code authority.

- `docs/planning/launch_ladder/visual/operator_harness_north_star_v1/`
- `docs/planning/launch_ladder/visual/operator_harness_north_star_v1/image_drops/README_IMAGE_DROPS.md`

### Knowledge Substrate Input

Use these for knowledge-substrate planning context before backend/data-contract continuation.

- `docs/planning/launch_ladder/knowledge_substrate/` if present.
- `docs/planning/launch_ladder/knowledge_substrate/INDEX.md` or `KNOWLEDGE_SUBSTRATE_INDEX.md` imported equivalent if present.
- `docs/planning/launch_ladder/knowledge_substrate/01_NORTH_STAR.md` through `docs/planning/launch_ladder/knowledge_substrate/06_STATIC_VALIDATION_EXPECTATIONS.md` if present.

### Mac Import Planning

Use this lane for cleanup and reintegration of imported Mac mirror planning material.

- `docs/planning/launch_ladder/mac_import_planning/` if present.

### Prior Art / Research / Stale

Use these for research memory and prior-art comparison only. Refresh and promote before treating them as current implementation guidance.

- `docs/planning/launch_ladder/operator_harness_research/`
- `docs/planning/launch_ladder/WATCH_PRIOR_ART_CANONICALIZATION.md` if present.
- `docs/planning/launch_ladder/CHAT_STAY_UP_TO_DATE.md` if present.

## 5. Non-Canonical Mac Mirror References

These Mac paths are non-canonical references. They may help explain imported planning packets, visual brainstorm source sets, or consolidation history, but PC WSL `/home/openclaw` remains canonical unless a later canonical doc says otherwise.

- `~/OpenClaw_Watch`
- `~/OpenClaw_Watch/operator_harness_readiness`
- `~/OpenClaw_Watch/operator_harness_readiness/visual_brainstorm_packets/operator_harness_north_star_v1/`
- `~/OpenClaw_Watch/operator_harness_readiness/visual_brainstorm_packets/operator_harness_north_star_v1/image_drops/`
- `~/OpenClaw_Watch/consolidation_packets/openclaw_watch_loose_files_v1/`
- `~/OpenClaw_Watch/consolidation_packets/home_openclaw_surfaces_v1/`

Do not treat mirror paths as runtime truth, live bridge state, source of authority, or permission to inspect private Mac content.

## 6. Current / Stale / Prior-Art Warnings

- Current docs are docs that are present in the PC WSL repo and not superseded by a later canonical addendum or breadcrumb.
- Stale dashboard/status files are prior art only unless refreshed and promoted.
- Prior-art research files can inform questions and comparison, but they do not override current authority docs.
- Visual packets can guide taste, metaphor, and source-set planning, but they do not authorize SwiftUI/AppKit, backend, schema, ingestion, bridge, or runtime changes.
- Deployment docs can define constraints and future specs, but they do not authorize moving nodes, starting services, editing launchers, changing storage, or modifying bridge behavior.
- Agentic hardening docs can constrain process, but they do not authorize package/build configuration work or tool implementation.
- Command Atlas and Hermes systems-engineering docs can guide calibration, critique, and sequencing, but they do not authorize implementation, runtime activation, provider/model calls, MCP invocation, messaging, private-data inspection, source-set mutation, root migration, or commits.
- Local-model benchmark docs can inform Hardware Fit Analyzer and PI Local experiment planning only; they do not authorize model install, llama.cpp/Ollama/LM Studio runtime changes, Chief/Cassandra/PI production routing, service changes, or sensitive-data processing.

When in doubt, read the narrow task-specific stack first, then stop and ask what implementation authority is actually present.

## 7. Sensitive / Do-Not-Touch Boundaries

Do not inspect:

- secrets;
- `.gemini`;
- `.claude`;
- PII vaults;
- legal, private, client, tax, ledger, or live private vault data;
- provider credentials.

Do not run ingestion, create SQL DDL, create app code, start backend services, call real LLM providers, or mutate bridge/runtime behavior from this index.

Do not use this index as authorization to move, delete, rewrite, reclassify, or import files.

## 8. What This Index Does Not Authorize

This index is a navigation aid, not implementation authority.

It does not authorize:

- runtime code changes;
- service changes;
- bridge script changes;
- package, build, storage, database, schema, or app-code changes;
- secret inspection or credential handling;
- provider/model calls;
- ingestion runs;
- broad scans;
- file moves or deletes;
- rewrites of existing planning docs;
- commits.

Future implementation requires separate authority, current source inspection, a narrow plan, and task-appropriate validation.

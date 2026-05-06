# SQLite Schema Definition Project Source-Set Guide (2026-05-06)

Status: docs-only ChatGPT Project source-set guide for the inert SQLite schema-definition orchestration phase. This file is not implementation authority, not a source-set folder, not a mirror sync instruction, and not permission to create SQLite databases or runtime behavior.

## Purpose

Define the exact 24-file ChatGPT Project packet for the next `05_BACKEND_SQLITE_SCHEMA_ORCHESTRATION` Project folder.

The packet is intentionally bird's-eye orchestration context. It should let a fresh Project chat understand the North Star, repo truth, current backend/data-contract decisions, SQLite schema-definition readiness, source authority, and prompt boundaries without preloading tactical code and test files that Codex/Gemini can read directly from `/home/openclaw`.

## Source Authority

Authority order for this packet:

1. current terminal truth from `/home/openclaw`
2. `docs/planning/launch_ladder/source_set_bridges/sqlite_schema_definition_repo_truth_20260506.md`
3. `docs/planning/project_orchestration/24_PROJECT_SOURCE_SET_TRANSITION_PROTOCOL.md`
4. `docs/planning/project_orchestration/01_PROJECT_CHAT_OPERATOR_EXPERIENCE_CONTRACT.md`
5. current backend/data-contract and SQLite planning bridge docs
6. Command Atlas / runtime / validation docs
7. older Launch Ladder indexes and historical source-set recommendations
8. chat memory

Terminal truth wins if any guide, handoff, or Project memory disagrees.

`docs/planning/OPENCLAW_MODULAR_READINESS_LEDGER.md` exists and was last updated before the current SQLite schema-definition source-set turn. It remains useful modular/product-readiness background, but it is too broad and not current enough for this 24-file packet, so it is excluded from the recommended Project upload set.

## Exactly 24 Recommended Files

| # | Path | Role | Classification | Why it belongs |
| --- | --- | --- | --- | --- |
| 1 | `docs/planning/project_orchestration/01_PROJECT_CHAT_OPERATOR_EXPERIENCE_CONTRACT.md` | Operator-facing Project chat behavior contract. | Required | Keeps new chats low-stress, concise, prompt-hygienic, and North-Star aligned while supervising Codex/Gemini. |
| 2 | `docs/planning/project_orchestration/24_PROJECT_SOURCE_SET_TRANSITION_PROTOCOL.md` | Phase transition and 24-file packet doctrine. | Required | Explains why this packet is orchestration context, how to retire stale files, and how to prepare the next Project source-set. |
| 3 | `docs/planning/launch_ladder/source_set_bridges/sqlite_schema_definition_repo_truth_20260506.md` | Current repo-truth snapshot for the SQLite schema-definition lane. | Required | Carries git status, latest commits, validation receipt, cleared verdict, allowed next implementation, and hard forbids. |
| 4 | `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_first_sqlite_implementation_plan_20260505.md` | Immediate first SQLite schema-definition implementation plan. | Current | Defines the separately authorized future inert schema constants slice and keeps sqlite3, DB connections, persistence, SQL execution, runtime, provider/model, and private-root work forbidden. |
| 5 | `docs/planning/launch_ladder/source_set_bridges/operator_north_star_machine_contract_20260505.md` | Top-layer operator intent contract. | Required | Keeps the SQLite lane tied to receivables/accountability, burden reduction, creative support, operator-native interaction, modularity, and truth/evidence. |
| 6 | `docs/planning/command_atlas/00_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md` | System-of-systems map. | Required | Frames Operator Harness as one lane under Command Atlas and prevents backend/SQLite work from becoming the whole system. |
| 7 | `docs/planning/command_atlas/04_CONTEXT_DEVELOPMENT_LIFECYCLE_AND_CONTEXT_FILTER_DOCTRINE.md` | Context package doctrine. | Required | Makes source sets, manifests, prompts, handoffs, receipts, and planning docs engineered inputs with provenance and filter obligations. |
| 8 | `CORE_ARCHITECTURE_PRINCIPLES.md` | Core architecture boundary doctrine. | Required | Keeps future schema work aligned with local-first, explicit-authority, lean-governance, and no-shadow-system principles. |
| 9 | `OPENCLAW_RUNTIME.md` | Canonical runtime law for agents. | Required | Establishes inspect-plan-act-verify, approval boundaries, validation discipline, and canonical repo authority. |
| 10 | `docs/testing/VALIDATION_MAP.md` | Validation lookup. | Required | Tells future agents which tests/checks apply when source-set, checker, or backend contract surfaces are touched. |
| 11 | `docs/planning/launch_ladder/17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md` | Backend/data-contract readiness baseline. | Reference | Gives the pre-bridge baseline for why backend/data-contract work exists and what conceptual readiness must preserve. |
| 12 | `docs/planning/launch_ladder/18_BACKEND_DATA_CONTRACT_SHAPE_PLAN.md` | Backend/data-contract shape baseline. | Reference | Provides the broader shape vocabulary that later semantic matrix and SQLite planning narrow. |
| 13 | `docs/planning/launch_ladder/19_OPERATOR_WORLD_MODEL_BUILD_READINESS_ADDENDUM.md` | Operator world-model addendum. | Reference | Preserves operator-facing map/cockpit framing so schema work supports the experience instead of becoming backend-only machinery. |
| 14 | `docs/planning/launch_ladder/24_OPERATOR_HARNESS_PLANNING_INDEX.md` | Navigation/read-order index. | Reference | Helps new chats find current Launch Ladder lanes, stale warnings, and read orders without loading every file. |
| 15 | `docs/planning/launch_ladder/30_BACKEND_SOURCE_SET_BRIDGE_AND_EXCLUSION_PLAN.md` | Backend source-set exclusion bridge. | Current | Keeps Windows/private-root dependency-map material as classification/exclusion guidance only, not backend input authority. |
| 16 | `docs/planning/launch_ladder/source_set_bridges/04_backend_data_contract_readiness_context_filter_freshness_bridge_20260505.md` | Freshness bridge for the older backend readiness source-set. | Required | Blocks standalone use of the older 04 source set without Context Development Lifecycle / Context Filter doctrine. |
| 17 | `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_first_planning_slice_decision_20260505.md` | First safe backend/data-contract planning-slice decision. | Historical | Shows why the lane began with a Markdown semantic matrix before any implementation or SQLite work. |
| 18 | `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_semantic_matrix_plan_20260505.md` | Semantic matrix planning bridge. | Historical | Records early semantic entity/field/authority decisions that still explain the current contract spine. |
| 19 | `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_semantic_contract_matrix_20260505.md` | Durable semantic contract matrix. | Current | Defines meanings, evidence/freshness/provenance, authority/sensitivity boundaries, and relationship concepts SQLite must preserve. |
| 20 | `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_implementation_readiness_checklist_20260505.md` | Implementation-readiness checklist. | Current | Names the gates that must pass before backend/data-contract implementation, keeping readiness separate from execution. |
| 21 | `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_first_implementation_slice_readiness_20260505.md` | First static implementation slice readiness decision. | Historical | Explains how static checker/test gates were introduced before any backend SQLite schema-definition work. |
| 22 | `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_storage_schema_plan_20260505.md` | Storage/schema planning bridge. | Current | Maps the pure-Python contract spine toward future storage concepts while forbidding DB creation, migrations, persistence, ingestion, indexing, runtime, provider/model, and private-root inspection. |
| 23 | `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_sqlite_plan_20260505.md` | SQLite planning bridge. | Current | Names the seven first table concepts and the smallest future SQLite schema-contract path without authorizing implementation. |
| 24 | `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_sqlite_implementation_readiness_20260505.md` | SQLite implementation-readiness bridge. | Current | Provides the exact readiness boundary immediately before the first inert schema-definition implementation plan. |

Count: exactly 24 files.

## Tactical Codex/Gemini Files Not Preloaded

These files are intentionally not in the 24-file ChatGPT Project packet. Codex/Gemini can read them directly from `/home/openclaw` when a prompt explicitly names them.

| Path | Why not preloaded |
| --- | --- |
| `backend_data_contract.py` | Tactical code contract file for Codex implementation/reference, not repeated Project orchestration context. |
| `tests/test_backend_data_contract.py` | Tactical test file for Codex validation/reference, not bird's-eye Project context. |
| `launch_ladder_contract_check.py` | Tactical static checker file for exact-path Codex work, not a Project packet member. |
| `tests/test_launch_ladder_static_contract.py` | Tactical static-check test file for Codex validation/reference, not orchestration context. |

## Files Removed From Gemini Recommendation And Why

The Gemini recommendation is treated as useful curation input, not final authority. The final packet removes or excludes these categories:

| File or category | Disposition | Why |
| --- | --- | --- |
| `backend_data_contract.py` | Moved to tactical Codex/Gemini files. | Needed for exact implementation prompts, but too granular for Project preload. |
| `tests/test_backend_data_contract.py` | Moved to tactical Codex/Gemini files. | Useful for Codex validation, not repeated orchestration decisions. |
| `launch_ladder_contract_check.py` | Moved to tactical Codex/Gemini files. | Static checker implementation detail; prompts can name it directly. |
| `tests/test_launch_ladder_static_contract.py` | Moved to tactical Codex/Gemini files. | Test implementation detail; prompts can name it directly. |
| `docs/planning/OPENCLAW_MODULAR_READINESS_LEDGER.md` | Excluded. | Exists, but is broad modular readiness background and appears stale relative to this current SQLite source-set turn. |
| Older visual, Mac, deployment, local-model, and Windows cleanup docs | Excluded. | Useful for other lanes, but not central to inert SQLite schema-definition orchestration. |
| Runtime logs, private data, secrets, scratch notes, mirror-only files | Excluded. | Forbidden or unsuitable for Project source-set context. |

## Mac Mirror Destination

Mirror/reference destination:

```text
~/OpenClaw_Watch/operator_harness_readiness/CHATGPT_PROJECT_INGEST_OPERATOR_HARNESS/05_BACKEND_SQLITE_SCHEMA_ORCHESTRATION
```

This destination is mirror/reference only. PC WSL `/home/openclaw` remains canonical build truth. Do not infer repo status from the mirror, and do not silently promote Mac-side edits back into the repo without an explicit PC-side promotion task, destination paths, validation plan, and commit plan.

## First New Chat Prompt

```text
You are in a new ChatGPT Project folder for OpenClaw.

Project scope: inert SQLite schema-definition orchestration for the backend/data-contract lane.

Source authority:
1. current terminal truth from /home/openclaw
2. docs/planning/launch_ladder/source_set_bridges/sqlite_schema_definition_repo_truth_20260506.md
3. docs/planning/project_orchestration/24_PROJECT_SOURCE_SET_TRANSITION_PROTOCOL.md
4. docs/planning/project_orchestration/01_PROJECT_CHAT_OPERATOR_EXPERIENCE_CONTRACT.md
5. current backend/data-contract and SQLite planning docs in the uploaded 24-file packet

First action:
Ask for or verify current /home/openclaw terminal truth before preparing any Codex prompt:

cd /home/openclaw
pwd
git status -sb --untracked-files=all
git log --oneline -12
git diff --check
git diff --cached --check
python3 launch_ladder_contract_check.py
pytest tests/test_launch_ladder_static_contract.py
pytest tests/test_backend_data_contract.py
python3 -m py_compile backend_data_contract.py launch_ladder_contract_check.py

Current likely next lane:
Prepare a Codex prompt for the first separately authorized inert SQLite schema-definition implementation slice.

Hard boundaries:
Do not authorize sqlite3, DB connections, SQL execution, migrations, persistence, DB files, runtime file I/O behavior, API routes, ingestion, extraction, indexing, embeddings, fixtures, runtime services, frontend/app behavior, provider/model calls, Hermes, MCPs, sync, source-set generation, private-root/private-data inspection, app behavior, Chief/Cassandra/Legal/polish-loop runtime edits, broad scans, broad staging, or commits unless separately and explicitly authorized.

Use the Project Chat Operator Experience Contract:
Keep the current slice clear, translate machine-contract complexity into concise ELI5 checkpoints, protect against context overload, produce full paste-ready Codex/Gemini prompts when needed, and keep progress tied to the North Star.

Report first:
- confirmed repo truth
- inferred next move
- unknowns/blockers
- recommended next action
```

## Validation Receipt

Baseline receipt before this guide was created:

- `pwd`: `/home/openclaw`
- `git status -sb --untracked-files=all`: clean tracked tree; preexisting untracked `docs/planning/launch_ladder/source_set_bridges/sqlite_schema_definition_repo_truth_20260506.md`
- `git log --oneline -12`: latest commit `67d2540 docs(planning): add first sqlite implementation plan`
- `git diff --check`: OK
- `git diff --cached --check`: OK
- `python3 launch_ladder_contract_check.py`: OK with existing freshness normalization warning
- `pytest tests/test_launch_ladder_static_contract.py`: 28 passed
- `pytest tests/test_backend_data_contract.py`: 41 passed
- `python3 -m py_compile backend_data_contract.py launch_ladder_contract_check.py`: OK

Required validation after editing this docs-only guide:

```bash
cd /home/openclaw
git status -sb --untracked-files=all
git diff --check
git diff --cached --check
python3 launch_ladder_contract_check.py
pytest tests/test_launch_ladder_static_contract.py
pytest tests/test_backend_data_contract.py
python3 -m py_compile backend_data_contract.py launch_ladder_contract_check.py
git diff --no-index --check -- /dev/null docs/planning/project_orchestration/01_PROJECT_CHAT_OPERATOR_EXPERIENCE_CONTRACT.md
git diff --no-index --check -- /dev/null docs/planning/project_orchestration/24_PROJECT_SOURCE_SET_TRANSITION_PROTOCOL.md
git diff --no-index --check -- /dev/null docs/planning/launch_ladder/source_set_bridges/sqlite_schema_definition_project_source_set_20260506.md
tail -c 1 docs/planning/project_orchestration/01_PROJECT_CHAT_OPERATOR_EXPERIENCE_CONTRACT.md | od -An -t x1
tail -c 1 docs/planning/project_orchestration/24_PROJECT_SOURCE_SET_TRANSITION_PROTOCOL.md | od -An -t x1
tail -c 1 docs/planning/launch_ladder/source_set_bridges/sqlite_schema_definition_project_source_set_20260506.md | od -An -t x1
```

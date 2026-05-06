# Backend SQLite Schema Orchestration Active Handoff

## 1. Repo Verification Receipt

- **Current Branch:** main
- **Latest Pushed State:** `e381214 docs(project): add audit-to-execution rule`
- **Backend Capability Checkpoint:** `d09fc50 feat(backend): add semantic record sqlite repository`
- **Current Terminal Status Before This Docs Slice:** `main...origin/main`
- **Latest Commits:**
```
e381214 docs(project): add audit-to-execution rule
d09fc50 feat(backend): add semantic record sqlite repository
359deef docs(project): add right stride length rule
1b025ac feat(backend): add file-backed sqlite persistence
5a1793c docs(planning): add sqlite file persistence readiness plan
02f0b61 docs(project): add faster workflow checkpoint rule
f6a4030 feat(backend): add in-memory schema version checks
4e7617d feat(backend): add sqlite schema version metadata
0c90662 docs(planning): add sqlite schema versioning policy
5ebb706 test(backend): harden in-memory sqlite runtime proof
5ee3de0 feat(backend): add in-memory sqlite runtime proof
705bdfc docs(planning): add sqlite runtime in-memory readiness plan
```

## 2. Validation Receipt

- `launch_ladder_contract_check.py`: OK, known freshness warning only
- `tests/test_launch_ladder_static_contract.py`: 28 passed
- `tests/test_backend_data_contract.py`: 41 passed
- `tests/test_backend_sqlite_schema.py`: 15 passed
- `tests/test_backend_sqlite_runtime.py`: 33 passed
- `tests/test_backend_sqlite_repository.py`: 12 passed
- `py_compile` includes:
  - `backend_data_contract.py`
  - `backend_sqlite_schema.py`
  - `backend_sqlite_runtime.py`
  - `backend_sqlite_repository.py`
  - `launch_ladder_contract_check.py`

## 3. Current Built-State Ledger

This lane is past docs-only planning.
This lane is past static schema only.
This lane is past in-memory-only runtime.
File-backed SQLite persistence exists.
Semantic record repository write/read exists.
The current baseline is backend SQLite repository substrate, not merely schema planning.

### Built Surfaces:
- `backend_data_contract.py`
- `backend_sqlite_schema.py`
- `backend_sqlite_runtime.py`
- `backend_sqlite_repository.py`
- `tests/test_backend_data_contract.py`
- `tests/test_backend_sqlite_schema.py`
- `tests/test_backend_sqlite_runtime.py`
- `tests/test_backend_sqlite_repository.py`

## 4. What Is Now Built

- static semantic schema tables
- schema_versions physical metadata table
- physical schema APIs
- in-memory SQLite runtime
- file-backed SQLite persistence with explicit Path policy
- schema version record/check helpers
- fail-closed behavior for invalid/mismatched/ambiguous DB versions
- semantic record repository with write/read by record_id
- repository helpers use caller-supplied connections only
- repository does not create paths or connections
- repository does not automatically promote accepted truth
- duplicate record_id fails closed
- missing read returns None

## 5. Current Forbidden Surfaces

Still forbidden:
- migrations and migration runners
- ingestion/extraction
- indexing, FTS, embeddings, vectors, RAG, PageIndex
- LLM/provider/model calls
- Hermes/MCP/sync
- private-root/private-data inspection
- API routes
- frontend/app behavior
- automatic accepted-truth promotion
- app/agent/runtime integration outside this backend substrate
- broad staging
- `git add .`
- editing `24_files` during active lane
- new broad/unbounded persistence beyond the existing explicit-path backend runtime.

## 6. Current Next Lane

The next visible-road lane should be:
- extend repository coverage from `semantic_records` to:
  A. `semantic_labels` and `provenance_refs`
  B. `semantic_relationships`, `validation_receipts`, `operator_promotions`
  C. deterministic read/query helpers
  D. first knowledge packet assembler
  E. deterministic context selection
  F. synthesis-ready read-model output without model calls
  G. deterministic write-back/capture/promotion boundary helpers if safely in scope
  H. richer retrieval only as deterministic metadata/relationship traversal or planning; no FTS/vector/RAG/PageIndex yet

Future coder prompts should include the visible A-H road and let the coder proceed through the visible road until a real review point.

## 7. Canonical Read List For Next Chat

- `docs/planning/project_packets/05_BACKEND_SQLITE_SCHEMA_ORCHESTRATION/00_ACTIVE_HANDOFF.md` (this handoff)
- `backend_sqlite_repository.py`
- `tests/test_backend_sqlite_repository.py`
- `backend_sqlite_runtime.py`
- `tests/test_backend_sqlite_runtime.py`
- `backend_sqlite_schema.py`
- `tests/test_backend_sqlite_schema.py`
- `backend_data_contract.py`
- `tests/test_backend_data_contract.py`
- `docs/planning/project_orchestration/01_PROJECT_CHAT_OPERATOR_EXPERIENCE_CONTRACT.md`
- `docs/planning/project_orchestration/24_PROJECT_SOURCE_SET_TRANSITION_PROTOCOL.md`
- `docs/planning/project_packets/05_BACKEND_SQLITE_SCHEMA_ORCHESTRATION/README.md`

## 8. Workflow Rules

- **Right Stride Length Rule**
- **Faster Workflow / Batch Checkpoint Rule**
- **Audit-to-Execution Rule**
- **Visible-Road Rule:** When the road is visible, prompt the agent with the road, not a crumb. If A-E are clear, include A-E in one prompt. If F branches, the agent should evaluate the branch, choose the better path using stated criteria, and continue if clear. Stop only at real review points.

## 9. 24_files Rule

- `24_files` are stable historical/source packet context.
- Do not edit `24_files` during the active lane.
- Current truth lives in this handoff plus canonical repo commits/docs.
- Regenerate/archive packet only when the lane is complete or future chats would be materially misled.

## 10. Required Validation

```bash
git status -sb --untracked-files=all
git diff --check
git diff --cached --check
python3 launch_ladder_contract_check.py
pytest tests/test_launch_ladder_static_contract.py
pytest tests/test_backend_data_contract.py
pytest tests/test_backend_sqlite_schema.py
pytest tests/test_backend_sqlite_runtime.py
pytest tests/test_backend_sqlite_repository.py
python3 -m py_compile backend_data_contract.py backend_sqlite_schema.py backend_sqlite_runtime.py backend_sqlite_repository.py launch_ladder_contract_check.py
git status -sb --untracked-files=all
```
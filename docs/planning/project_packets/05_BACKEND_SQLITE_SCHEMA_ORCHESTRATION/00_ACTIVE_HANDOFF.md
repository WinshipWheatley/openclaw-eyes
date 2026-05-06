# SQLite Schema Definition Repo Truth (2026-05-06)

## 1. Repo Verification Receipt

- **Current Branch:** main
- **Current Status:** Clean (no untracked or uncommitted changes)
- **Latest 12 Commits:**
```
67d2540 docs(planning): add first sqlite implementation plan
a4ecd66 fix(backend): harden sqlite table concept boundaries
30f2e59 feat(backend): add sqlite table concept contract
88fb058 docs(planning): add sqlite implementation readiness gate
e0b539f test(planning): enforce backend sqlite plan gate
7928786 docs(planning): add backend sqlite schema contract plan
759e925 fix(backend): harden schema contract boundaries
51a92c5 feat(backend): add schema contract surfaces
a54e875 test(planning): enforce backend storage schema plan gate
6f62b62 docs(planning): add backend storage schema plan
f1fe5c5 fix(backend): harden write-back promotion gate
f63cd72 feat(backend): add semantic entity family validator
```
- **Validation Command Results:**
  - `python3 launch_ladder_contract_check.py`: OK
  - `pytest tests/test_launch_ladder_static_contract.py`: 28 passed
  - `pytest tests/test_backend_data_contract.py`: 41 passed
  - `python3 -m py_compile backend_data_contract.py launch_ladder_contract_check.py`: OK

## 2. Current Cleared Verdict

Cleared for separate actual inert SQLite schema-definition implementation prompt.

## 3. Canonical Files For Next Lane

Exact files the next ChatGPT/Codex lane should read:
- `backend_data_contract.py`
- `tests/test_backend_data_contract.py`
- `docs/planning/launch_ladder/source_set_bridges/backend_data_contract_first_sqlite_implementation_plan_20260505.md`
- `docs/planning/launch_ladder/source_set_bridges/sqlite_schema_definition_repo_truth_20260506.md`

## 4. Allowed Next Implementation

- `backend_sqlite_schema.py`
- `tests/test_backend_sqlite_schema.py`
- Optional static checker/validation-map paths only if explicitly needed to enforce the new contract.

## 5. Hard Forbids

- No sqlite3
- No DB connections
- No SQL execution
- No migrations
- No persistence
- No DB files
- No runtime file I/O
- No API
- No ingestion
- No extraction
- No indexing
- No embeddings
- No fixtures
- No runtime services
- No frontend/app behavior
- No provider/model calls
- No Hermes
- No MCPs
- No sync
- No source-set generation
- No private-root/private-data inspection
- No app behavior
- No Chief/Cassandra/Legal/polish-loop runtime edits
- No broad scans
- No broad staging
- No `git add .`

## 6. Doctrine Summary

- OpenClaw is a knowledge compiler/operator substrate, not generic RAG.
- raw reality -> compiled/wiki -> relationship graph -> synthesis -> write-back/capture -> recompile.
- Synthesis is not automatically truth.
- Accepted knowledge requires write-back/capture, labels, receipt/provenance boundaries, and operator promotion.

## 7. Existing Backend Contract Capabilities

- Semantic data contract foundation
- Field-bundle validator
- Entity-family validator
- Schema-contract surfaces
- SQLite table-concept contract
- Static checker gates

## 8. Seven Table Concepts

- `semantic_records`
- `semantic_labels`
- `semantic_relationships`
- `provenance_refs`
- `validation_receipts`
- `operator_promotions`
- `context_filter_receipts`

## 9. Required Validation For Next Implementation

```bash
cd /home/openclaw
git status -sb --untracked-files=all
git diff --check
git diff --cached --check
python3 launch_ladder_contract_check.py
pytest tests/test_launch_ladder_static_contract.py
pytest tests/test_backend_data_contract.py
pytest tests/test_backend_sqlite_schema.py
python3 -m py_compile backend_data_contract.py backend_sqlite_schema.py launch_ladder_contract_check.py
git status -sb --untracked-files=all
git diff --check
git diff --cached --check
```

## 10. Notes / Warnings

- `sglite_handoff.md` is Mac-side handoff/reference only.
- This repo-truth file is generated from PC canonical repo state.
- If terminal truth differs later, trust terminal truth.
- The old 24-file source packet is historical and should not be used alone for the next lane.

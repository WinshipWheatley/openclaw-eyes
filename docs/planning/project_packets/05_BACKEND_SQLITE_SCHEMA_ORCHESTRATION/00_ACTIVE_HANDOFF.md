# Backend SQLite Schema Orchestration Active Handoff

## 1. Repo Verification Receipt

- **Current Branch:** main
- **Latest Pushed State (Origin):** `bdb127d feat(backend): add runtime presence health substrate`
- **Latest Local Backend Capability Checkpoint:** `565d05a feat(backend): add performance show map substrate`
- **Current Terminal Status:** `main...origin/main [ahead 1]`
- **Latest Local Commits:**
```
565d05a feat(backend): add performance show map substrate
bdb127d feat(backend): add runtime presence health substrate
d43f869 feat(backend): add network node authorization substrate
5561e92 feat(backend): add storage intelligence substrate
d99c0f5 feat(backend): add exact seed context wrappers
73b9036 feat(backend): add exact candidate seed helpers
47804b3 feat(backend): add deterministic multi-seed context
79c4bc4 feat(backend): harden traversal context boundaries
c30b023 feat(backend): add deterministic knowledge traversal
```

## 2. Validation Receipt

- `launch_ladder_contract_check.py`: OK, known freshness warning only
- `tests/test_launch_ladder_static_contract.py`: 28 passed
- `tests/test_backend_data_contract.py`: 44 passed
- `tests/test_backend_sqlite_schema.py`: 18 passed
- `tests/test_backend_sqlite_runtime.py`: 33 passed
- `tests/test_backend_sqlite_repository.py`: 41 passed
- `tests/test_backend_knowledge_packet.py`: 27 passed
- `tests/test_backend_storage_intelligence.py`: 17 passed
- `tests/test_backend_performance_repository.py`: 7 passed
- `tests/test_backend_performance_intelligence.py`: 8 passed
- `py_compile` includes:
  - `backend_data_contract.py`
  - `backend_sqlite_schema.py`
  - `backend_sqlite_runtime.py`
  - `backend_sqlite_repository.py`
  - `backend_knowledge_packet.py`
  - `backend_storage_intelligence.py`
  - `launch_ladder_contract_check.py`

## 3. Current Built-State Ledger

This lane is past docs-only planning.
This lane is past static schema only.
This lane is past in-memory-only runtime.
File-backed SQLite persistence exists.
Semantic record repository write/read exists.
Storage intelligence substrate exists (Authorizations, Runtime Presence).
Knowledge packet substrate exists (Seeds, Traversal, Context).
Performance Director / Show Map substrate exists.

### Built Surfaces:
- `backend_data_contract.py`
- `backend_sqlite_schema.py`
- `backend_sqlite_runtime.py`
- `backend_sqlite_repository.py`
- `backend_knowledge_packet.py`
- `backend_storage_intelligence.py`
- `tests/test_backend_data_contract.py`
- `tests/test_backend_sqlite_schema.py`
- `tests/test_backend_sqlite_runtime.py`
- `tests/test_backend_sqlite_repository.py`
- `tests/test_backend_knowledge_packet.py`
- `tests/test_backend_storage_intelligence.py`
- `tests/test_backend_performance_repository.py`
- `tests/test_backend_performance_intelligence.py`

## 4. What Is Now Built

- **Performance Director / Show Map static schema/data-contract substrate**
- **Physical SQLite schema definitions** for `performance_sessions`, `setlists`, `setlist_items`, `song_cues`, `section_cues`, `performance_action_receipts`, `manual_override_events`, and `highlight_markers`
- **Repository helpers** for performance tables using caller-owned SQLite connections only
- **Performance semantics**: cues are inert map markers, receipts are evidence/logs, manual override is first-class state, and highlight markers are metadata only
- **Pure performance readiness/action-risk models** in `backend_storage_intelligence.py`
- **Risk finding support** for:
  - low-confidence safe-baseline holds
  - unapproved creative moves
  - action tiers requiring confirmation
  - high-risk blocked actions
  - manual override active state
  - stale/degraded runtime component
  - tenant mismatch
  - missing performance session
  - missing setlist
  - cue/action not approved for current session
  - unavailable live adapters
- static semantic schema tables
- schema_versions physical metadata table
- file-backed SQLite persistence with explicit Path policy
- semantic record repository with write/read by record_id
- Exact candidate seed selection and bounded deterministic traversal
- Multi-seed context packets and exact-seed-to-context wrappers
- OpenClaw nodes, node-source links, and source authorization scopes
- Runtime components, capabilities, heartbeats, and health snapshots

## 5. Current Forbidden Surfaces

STRICTLY FORBIDDEN (No live performance or control architecture):
- **live MIDI listeners**
- **audio/chord/lyric analysis**
- **camera switching**
- **OBS WebSocket control**
- **X32 OSC control**
- **Dante routing**
- **DAW/looper integration**
- **Home Assistant/Hue/Matter/MQTT actions**
- **TTS headphone cue engines**
- **live performance runners**
- **adaptive inference engines**
- **live file operations / network polling**
- **process/service scanning**
- **model/provider calls**
- migrations and migration runners
- ingestion/extraction
- indexing, FTS, embeddings, vectors, RAG, PageIndex

## 6. Current Next Lane

The next visible-road lane should be:
- **Adaptive Playbook Schema**
- **Control Device / Operator Deck Schema**
- **Studio Session / Production Routing Schema**
- **Architecture review before live adapters**

## 7. Review Boundary

- Latest checkpoint `565d05a` must be pushed to origin/main or remains local-only.

## 8. Canonical Read List For Next Chat

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
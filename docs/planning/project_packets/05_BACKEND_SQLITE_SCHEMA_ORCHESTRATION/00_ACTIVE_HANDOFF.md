# Backend SQLite Schema Orchestration Active Handoff

## 1. Repo Verification Receipt

- **Current Branch:** main
- **Latest Pushed State (Origin):** `6e7117d docs(project): refresh backend sqlite active handoff`
- **Latest Local Backend Capability Checkpoint:** `627326a feat(backend): add agent context export substrate`
- **Current Terminal Status:** `main...origin/main [ahead 2]`
- **Latest Local Commits:**
```
6845e62 fix(chief): repair telegram listener lifecycle
627326a feat(backend): add agent context export substrate
6e7117d docs(project): refresh backend sqlite active handoff
565d05a feat(backend): add performance show map substrate
bdb127d feat(backend): add runtime presence health substrate
d43f869 feat(backend): add network node authorization substrate
```

## 2. Validation Receipt

- `launch_ladder_contract_check.py`: OK, known freshness warning only
- `tests/test_launch_ladder_static_contract.py`: 28 passed
- `tests/test_backend_data_contract.py`: 44 passed
- `tests/test_backend_sqlite_schema.py`: 24 passed
- `tests/test_backend_sqlite_runtime.py`: 33 passed
- `tests/test_backend_sqlite_repository.py`: 41 passed
- `tests/test_backend_knowledge_packet.py`: 27 passed
- `tests/test_backend_storage_intelligence.py`: 17 passed
- `tests/test_backend_performance_repository.py`: 7 passed
- `tests/test_backend_performance_intelligence.py`: 8 passed
- `tests/test_backend_agent_context.py`: 7 passed
- **Full Backend Validation:** 230 tests passed
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
Agent Context Export / Access Policy substrate exists.

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
- `tests/test_backend_agent_context.py`

## 4. What Is Now Built

- **Agent Context Export / Access Policy static schema/data-contract substrate**
- **Physical SQLite schema definitions** for `agent_context_profiles` and `context_export_receipts`
- **Repository helpers** for agent context profiles and context export receipts using caller-owned SQLite connections only
- **Deterministic agent context request/access/export read models** in `backend_knowledge_packet.py`
- **Context export semantics**: context is not truth, export is not action, profile access is not runtime authority, denied/omitted context is explicit and non-leaking
- **Agnostic actor/agent role and task-class semantics**: current agents are examples, future agents can be represented as data
- **Fail-closed behavior** for missing profiles, tenant mismatch, invalid bounds, and denied context
- **Performance Director / Show Map static schema/data-contract substrate**
- **Physical SQLite schema definitions** for `performance_sessions`, `setlists`, `setlist_items`, `song_cues`, `section_cues`, `performance_action_receipts`, `manual_override_events`, and `highlight_markers`
- **Repository helpers** for performance tables using caller-owned SQLite connections only
- **Performance semantics**: cues are inert map markers, receipts are evidence/logs, manual override is first-class state, and highlight markers are metadata only
- **Pure performance readiness/action-risk models** in `backend_storage_intelligence.py`
- static semantic schema tables
- schema_versions physical metadata table
- file-backed SQLite persistence with explicit Path policy
- semantic record repository with write/read by record_id
- Exact candidate seed selection and bounded deterministic traversal
- Multi-seed context packets and exact-seed-to-context wrappers
- OpenClaw nodes, node-source links, and source authorization scopes
- Runtime components, capabilities, heartbeats, and health snapshots

## 5. Runtime Recovery Notes

- **6845e62 fix(chief): repair telegram listener lifecycle**
- Repaired Chief Telegram listener async lifecycle using explicit PTB lifecycle and import-safety/lifecycle tests.
- Verified by `tests/test_chief_listener_lifecycle.py` (2 passed).
- This is runtime recovery, not SQLite substrate expansion.

## 6. Current Forbidden Surfaces

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
- **retrieval/search/RAG/vector/PageIndex**
- **private-root inspection**
- migrations and migration runners
- ingestion/extraction

## 7. Current Next Lane

The next visible-road lane should be:
- **Agent Context Export hardening**
- **Actor Registry / sidecar profile schema** if not already built
- **Operator Harness read-model assembly**
- **Legal context export policy**
- **Runtime integration architecture review**
- **MCP/shared memory architecture review inspired by Open Brain / OB1**

## 8. Review Boundary

- Latest checkpoint `627326a` and fix `6845e62` remain local-only (`ahead 2`).

## 9. Canonical Read List For Next Chat

- `docs/planning/project_packets/05_BACKEND_SQLITE_SCHEMA_ORCHESTRATION/00_ACTIVE_HANDOFF.md` (this handoff)
- `backend_sqlite_repository.py`
- `tests/test_backend_sqlite_repository.py`
- `backend_sqlite_runtime.py`
- `tests/test_backend_sqlite_runtime.py`
- `backend_sqlite_schema.py`
- `tests/test_backend_sqlite_schema.py`
- `backend_data_contract.py`
- `tests/test_backend_data_contract.py`
- `backend_knowledge_packet.py`
- `tests/test_backend_agent_context.py`
- `docs/planning/project_orchestration/01_PROJECT_CHAT_OPERATOR_EXPERIENCE_CONTRACT.md`
- `docs/planning/project_orchestration/24_PROJECT_SOURCE_SET_TRANSITION_PROTOCOL.md`
- `docs/planning/project_packets/05_BACKEND_SQLITE_SCHEMA_ORCHESTRATION/README.md`

## 10. Workflow Rules

- **Right Stride Length Rule**
- **Faster Workflow / Batch Checkpoint Rule**
- **Audit-to-Execution Rule**
- **Visible-Road Rule:** When the road is visible, prompt the agent with the road, not a crumb. If A-E are clear, include A-E in one prompt. If F branches, the agent should evaluate the branch, choose the better path using stated criteria, and continue if clear. Stop only at real review points.

## 11. 24_files Rule

- `24_files` are stable historical/source packet context.
- Do not edit `24_files` during the active lane.
- Current truth lives in this handoff plus canonical repo commits/docs.
- Regenerate/archive packet only when the lane is complete or future chats would be materially misled.

## 12. Required Validation

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
pytest tests/test_backend_agent_context.py
python3 -m py_compile backend_data_contract.py backend_sqlite_schema.py backend_sqlite_runtime.py backend_sqlite_repository.py launch_ladder_contract_check.py
git status -sb --untracked-files=all
```
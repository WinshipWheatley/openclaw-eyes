# Backend SQLite Schema Orchestration Active Handoff

## 1. Repo Verification Receipt

- **Current Branch:** main
- **Latest Pushed State (Origin):** `bd723ce docs(project): refresh backend sqlite active handoff`
- **Latest Local Backend Capability Checkpoint:** `e306c4d feat(backend): add actor registry context trust bridge`
- **Current Terminal Status:** `main...origin/main [ahead 1]`
- **Latest Local Commits:**
```text
e306c4d feat(backend): add actor registry context trust bridge
bd723ce docs(project): refresh backend sqlite active handoff
6845e62 fix(chief): repair telegram listener lifecycle
627326a feat(backend): add agent context export substrate
6e7117d docs(project): refresh backend sqlite active handoff
565d05a feat(backend): add performance show map substrate
```

## 2. Validation Receipt

- `launch_ladder_contract_check.py`: OK, known freshness warning only
- `tests/test_launch_ladder_static_contract.py`: 28 passed
- `tests/test_backend_data_contract.py`: 45 passed
- `tests/test_backend_sqlite_schema.py`: 19 passed
- `tests/test_backend_sqlite_runtime.py`: 33 passed
- `tests/test_backend_sqlite_repository.py`: 43 passed
- `tests/test_backend_knowledge_packet.py`: 27 passed
- `tests/test_backend_storage_intelligence.py`: 17 passed
- `tests/test_backend_performance_repository.py`: 7 passed
- `tests/test_backend_performance_intelligence.py`: 8 passed
- `tests/test_backend_agent_context.py`: 15 passed
- **Full Backend Validation:** 242 tests passed
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
Actor Registry / Context Export Trust Bridge exists.

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

- **Actor Registry / Context Export Trust Bridge**
  - `actor_profiles` physical and semantic models
  - Actor lanes and actor classes
  - Trust tiers and sensitivity ceilings
  - Capability scopes and inert authority flags
  - Receipt requirements for sensitive context
  - Cloud-sidecar deny-by-default context trust behavior
  - No fake sanitization logic allowed
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
- **cloud sidecars deny by default unless context is already public/sanitized and approval/receipt-backed**
- **no fake `sanitize_packet()` placeholder**
- **no sidecar/Jules runtime use**
- **no invoice hardening in this same backend lane**
- **no live runtime integration, API/MCP, retrieval/RAG/vector/PageIndex, model/provider calls, private-root inspection, filesystem/network/MIDI/web/control behavior**
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
- migrations and migration runners
- ingestion/extraction

## 7. Candidate Next Lanes from Current Checkpoint

This handoff records the train position. The 24_files and canonical source-set docs define the tracks. The following are candidate continuations from the current checkpoint, not independently authoritative roadmap decisions.

- **Agent Context Export hardening**
- **Actor Registry / sidecar profile schema** if not already built
- **Operator Harness read-model assembly**
- **Legal context export policy**
- **Runtime integration architecture review**
- **MCP/shared memory architecture review inspired by Open Brain / OB1**

## 8. Process Lessons & Known State

- **Docs-Only Drift:** Gemini previously drifted into implementation (`backend_data_contract.py`) after a docs-only handoff update. Future docs-only workers must strictly stop after the requested documentation update and report.
- **Invoice Tools Reality:** Existing invoice tools are not safe for unattended real invoice generation. `reportlab` and `requests` are missing from the active `.venv`, and `chief_invoice_brain.py` misparsed “Tomorrow” as `deposit_amount`. Real invoices should be manual/semi-manual until an "Invoice Artifact v0 / Billing Bridge" lane is explicitly selected.
- **24_files Archive Rule:** When the current `24_files` are exhausted, they must be archived *together* with the final active handoff as a paired snapshot before generating the next batch.

## 9. Review Boundary

- Latest checkpoint `e306c4d` remains local-only (`ahead 1`).

## 10. Canonical Read List For Next Chat

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

## 11. Workflow Rules

- **Right Stride Length Rule**
- **Faster Workflow / Batch Checkpoint Rule**
- **Audit-to-Execution Rule**
- **Visible-Road Rule:** When the road is visible, prompt the agent with the road, not a crumb. If A-E are clear, include A-E in one prompt. If F branches, the agent should evaluate the branch, choose the better path using stated criteria, and continue if clear. Stop only at real review points.

### North Star Rails Doctrine (Motherland / Big-Strides)
- **The Choo Choo Train:** The active handoff is the train. It records where the train is now: what was done, what mile markers were passed, current detours, validation receipts, and what a new chat must verify before moving.
- **Not the Roadmap:** The handoff must not become the roadmap by itself. It should keep new chats oriented back to the `24_files` and current canonical docs.
- **Big-Strides over Timid Crumbs:** Prompts should not shrink the operator’s ambition into timid crumbs. When the visible road is clear, prompts should carry the whole relevant picture and ask for the right-sized stride.
- **Safe Big Strides:** “Big stride” does not mean unsafe scope expansion. It means the largest correct bounded chunk that preserves rollback/review points. Future chats should translate the big vision into concrete bounded lanes with strong examples, clear boundaries, validation, and a review stop.

## 12. 24_files Rule

- **The Railroad Tracks:** `24_files` are the durable rails. They define the roadmap, source-set authority, North Star continuity, and bird’s-eye future-work direction.
- **Bird's-Eye View:** The point of a `24_files` batch is to enable substantial future work from a bird’s-eye view, so the train can gain as much distance as possible in the right direction toward the North Star.
- `24_files` are stable historical/source packet context until exhausted.
- **Do not edit `24_files` during the active lane.**
- Current truth lives in this handoff plus canonical repo commits/docs.
- **The current active handoff should orient new chats back to `24_files`.**
- **Renewal Protocol:** The next `24_files` renewal should allow the current handoff to flow into the new chat’s handoff, then switch authority to the newly built handoff, then archive the old handoff together with the old `24_files` as the paired snapshot of where that batch ended.

## 13. Required Validation

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
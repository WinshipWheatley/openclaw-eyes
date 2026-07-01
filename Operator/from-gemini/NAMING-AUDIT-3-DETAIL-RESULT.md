# GEMINI AUDIT RESULT — Canonical Naming, Pass 3 of 3: DETAIL LEVEL

**Audit ID:** NAMING-AUDIT-3-DETAIL
**Date:** 2026-06-30

## 1. Detailed Inconsistency List (The Drift)

| Name / Concept | Where | The Drift | Confuses Who |
|---|---|---|---|
| **Watch Desk Agent ID** | `operator_universal_intake.py` vs `agent_lane_registry.py` | Intake uses `"watch desk"` (with a space) as the `agent_id` key. Registry defines `agent_id="watch_desk"` (with an underscore). | **Agent / CLI** (Lookups will fail because of the space/underscore mismatch). |
| **Agent Lane IDs** | `operator_universal_intake.py` vs `agent_lane_registry.py` | Intake sets `lane: "cassandra_ar"` and `lane: "chief_runtime"`. Registry defines these exact same lanes as `lane_id="operator_comms"` and `lane_id="system_orchestration"`. | **Agent / Operator** (Intake stages work into lanes that the authoritative registry does not formally declare). |
| **Niles / Producer** | `agent_lane_registry.py` | The agent is named `niles`, but the alias `producer` is widely used. | **Operator / CLI** (Users type "producer", but internal routing needs "niles"). |
| **Front Door vs Mission Control** | `openclaw-request-response.service` | The systemd unit is called `openclaw-request-response.service`, the description says "Mission Control bridge", but the environment variables control the "Frontdoor" (`OPENCLAW_FRONTDOOR_MODEL_PROFILE`). | **CLI / Operator** (3 completely different names for the same entrypoint). |
| **Knowledge vs Corpus Tables** | `ledger.sqlite` Schema | Operator prompted about `knowledge_*` tables, but the ledger exclusively uses `corpus_roots`, `corpus_paths`, `evidence_items`, and `tool_candidates`. | **Operator** (Stale mental model of the schema). |

## 2. PRIORITIZED Rename Recommendations

**1. Align Agent Lane IDs (CRITICAL)**
- **Recommendation:** Change `operator_universal_intake.py` lanes (`cassandra_ar`, `chief_runtime`, `niles_creative`) to match `agent_lane_registry.py` (`operator_comms`, `system_orchestration`, `music_art_production`).
- **Risk:** `BREAKS-INGEST-OR-PACKETS` (High risk). Packets depend on lane strings for routing. DO NOT RENAME WITHOUT RUNNING INGEST/TESTS.

**2. Standardize "Watch Desk" ID (HIGH)**
- **Recommendation:** Standardize strictly on `watch_desk` (underscore) across both files. Remove `"watch desk"` as a primary key in `operator_universal_intake.py`.
- **Risk:** `BREAKS-INGEST-OR-PACKETS` (High risk).

**3. Rename Service Unit to match Env Vars (MED)**
- **Recommendation:** Rename `openclaw-request-response.service` to `openclaw-frontdoor-bridge.service` to match `OPENCLAW_FRONTDOOR_*` env vars and operator vocabulary.
- **Risk:** `cosmetic-safe` (Safe, but requires `systemctl daemon-reload`).

**4. Deprecate "Mission Control" terminology (LOW)**
- **Recommendation:** Standardize all descriptions on "Operator Frontdoor".
- **Risk:** `cosmetic-safe`.

## 3. Proposed Canonical Naming Standard (To Halt Future Drift)

To stop adding drift, enforce these rules on all future builds:
- **Agent IDs & Lanes:** MUST be `snake_case` (e.g., `watch_desk`, never `watch desk` or `watchdesk`).
- **Lane IDs:** MUST describe the function, not the agent (e.g., `system_orchestration`, not `chief_runtime`), because agents can theoretically swap lanes.
- **Service Units:** `openclaw-[canonical-subsystem].service`.
- **Env Vars:** `OPENCLAW_[SUBSYSTEM]_[VAR_NAME]`.

## 4. Side-Benefit Capture (Ledger Gaps & Component Map)

- **Ledger Gaps:** The ledger robustly tracks `corpus_paths`, `tool_candidates`, and `project_capsules`. However, it does **not** track systemd unit statuses, active system environment variables, or CLI tool routes. These runtime operational configs are floating outside the ledger's knowledge graph.
- **Component Map (Finalized):**
  - `/home/openclaw/operator_universal_intake.py` → Intake Route → Purpose: Initial receipt creation → Proposed Canonical Name: `FrontdoorUniversalIntake`
  - `/home/openclaw/agent_lane_registry.py` → Registry → Purpose: Defining agent boundaries → Proposed Canonical Name: `AgentLaneRegistry`
  - `/home/openclaw/.openclaw/business_ops/ledger.sqlite` → Ledger → Purpose: System Knowledge/Evidence → Proposed Canonical Name: `BusinessOpsLedger`
  - `/home/openclaw/scripts/run_openclaw_request_response_service.py` → Service Script → Purpose: Frontdoor Bridge → Proposed Canonical Name: `FrontdoorBridgeService`

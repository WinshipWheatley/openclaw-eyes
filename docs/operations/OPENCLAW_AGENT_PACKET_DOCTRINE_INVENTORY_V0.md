# OpenClaw Agent Packet Doctrine Inventory v0

## Status
- Source basis: repo evidence only
- Generated/edited by: manual planning pass
- Do not treat UNKNOWN as absent
- Do not treat FUTURE as built

## Doctrine Summary
- **Compiled context, not fuzzy memory**: Packets must be minimized for context efficiency and grounded in deterministic evidence.
- **Contract governs packet construction**: Each agent lane must have a schema authority (contract) defining inputs, outputs, and boundaries.
- **Packet is a runtime object**: A structured instance of data emitted under a contract.
- **Raw files/chats are evidence, not truth**: Prior history is a source for extraction, not an overriding authority.
- **LLM synthesis is not authority**: Agentic judgment is secondary to deterministic extraction and receipt-backed truth.
- **Ingestion Discipline**: Follows strict packet/source/promotion rules to prevent context bloat and "hallucinated" state claims.

---

## Agent Inventory

### Producer / Niles
- **Status**: CURRENT / ACTIVE
- **Role**: Creative review, technical production advice, and tool-intent proposals.
- **Authority Boundary**: Judgment only; `no_side_effects: true`. Restricted to suggestions; no direct mutation of DAW or hardware.
- **Current Packet Surfaces**: 
  - `ProducerInput`: Structured representation of creative artifacts.
  - `ProducerReview`: Deterministic evaluation output.
  - `Explain Packet (v0)`: Intake packet emitted by `producer_intake.py --explain`.
  - `ToolIntentPacket`: Suggests specific technical interventions (embedded in review).
- **Proposed/Future Packet Surfaces**: Hardware receipts, Audio Analysis receipts.
- **Context/Evidence**: Compiled context (`producer_compiled_context.json`), raw text input, artifact summaries.
- **Blocked Actions**: Live audio analysis claims (without receipt), direct DAW mutation.
- **Known Files**: `docs/producer/PRODUCER_MACHINE_CONTRACT.md`, `scripts/producer_intake.py`, `generated/producer/producer_compiled_context.json`.
- **Gaps**: Direct wiring to hardware/DAW state receptors.

### Chief
- **Status**: CURRENT
- **Role**: Runtime orchestration, routing, approval policy enforcement, and final acceptance of loop results.
- **Authority Boundary**: Top-level coordinator. Owns approval routing and acceptance verdicts.
- **Current Packet Surfaces**: 
  - Approval Decision Packets: Deterministic records of operator decisions.
  - Acceptance Verdicts: Review of loop/harness outputs.
- **Proposed/Future Packet Surfaces**: Universal `ActionIntentPacket` implementation.
- **Context/Evidence**: Loop status records, harness manifests, operator promotions.
- **Blocked Actions**: Execution of Tier 2 (high-risk) actions without Guardian approval.
- **Known Files**: `chief_router.py`, `chief_approval_policy.py`, `chief_approval_brain.py`, `chief_acceptance_gate.py`.
- **Gaps**: Explicit "Packet" documentation for routing decisions.

### Cassandra / Clara Reed
- **Status**: MIXED (Core built / Packets implicit)
- **Role**: Executive assistant for email triage, outreach drafts, and PII-aware correspondence.
- **Authority Boundary**: Draft creation and triage only. No direct sends without approval. Broker-gated Google access.
- **Current Packet Surfaces**: 
  - Triage/Correspondence summaries (implicit in brain/outreach logic).
- **Proposed/Future Packet Surfaces**: `Briefing Packet`, `Known-Contact Notification Packet`.
- **Context/Evidence**: Gmail thread metadata, PII tokenization vault, contact records.
- **Blocked Actions**: Direct Gmail sends, roaming into unauthorized threads.
- **Known Files**: `cassandra_brain.py`, `cassandra_outreach.py`, `cassandra_pii_hooks.py`, `scripts/demo_cassandra_email_triage.py`.
- **Gaps**: Explicit machine contract and formal packet schemas.

### Guardian
- **Status**: CURRENT
- **Role**: Dedicated human-in-the-loop approval interface via Telegram.
- **Authority Boundary**: Final authority for high-risk (Tier 2) actions.
- **Current Packet Surfaces**: 
  - Approval Request Prompts (button-bearing or text-coded).
  - Approval/Denial Receipts.
- **Context/Evidence**: Pending job manifests, risk classifications.
- **Blocked Actions**: Cannot be bypassed by other agents for Tier 2 moves.
- **Known Files**: `chief_guardian_listener.py`, `chief_guardian_sender.py`.
- **Gaps**: Formal schema doc for the "Approval Packet".

### Hermes
- **Status**: FUTURE / DOCTRINE
- **Role**: Advisory sidecar for systems-engineering and technical evaluations.
- **Authority Boundary**: Advisory only; non-canonical. No mutation authority.
- **Current Packet Surfaces**: Doctrine/contract surface exists, but active runtime implementation is not verified.
- **Proposed/Future Packet Surfaces**: `Advisory Packet`.
- **Context/Evidence**: Technical specs, dry-run logs, eval handoffs.
- **Blocked Actions**: Governance, mutation, or approval authority.
- **Known Files**: `docs/operations/HERMES_ADVISORY_PACKET_CONTRACT.md`, `docs/planning/HERMES_FIRST_ADVISORY_TRIAL_PLAN.md`.
- **Gaps**: Implementation scripts and active runtime lane.

### Operator Next Sane Thing (Deferred PI Concept)
- **Status**: DEFERRED / NOT ACTIVE / NOT STANDALONE
- **Role**: Deterministic next-action advisory pattern.
- **Authority Boundary**: Advisory only; behavior absorbed into existing agents.
- **Proposed/Future Packet Surfaces**: `operator_next_sane_thing` packet.
- **Known Files**: `docs/operations/OPENCLAW_AGENT_INTAKE_AND_ACTION_INTENT_CONTRACT_V0.md`.

---

## Packet Families Inventory

| Packet Family | Owner | Status | Purpose | Source/Files |
|---|---|---|---|---|
| **ProducerInput** | Producer | CURRENT | Normalizes creative artifact for review. | `PRODUCER_MACHINE_CONTRACT.md` |
| **ProducerReview** | Producer | CURRENT | Deterministic creative evaluation. | `PRODUCER_MACHINE_CONTRACT.md` |
| **Explain Packet** | Producer | CURRENT | Intake intent extraction (Niles). | `producer_intake.py` |
| **ToolIntentPacket** | Producer | CURRENT | Suggests specific technical intervention. | `PRODUCER_MACHINE_CONTRACT.md` |
| **Advisory Packet** | Hermes | FUTURE | Systems engineering technical advice. | `HERMES_ADVISORY_PACKET_CONTRACT.md` |
| **Intake Packet** | Universal | FUTURE | Normalizes any initial human/trigger request. | `AGENT_INTAKE...CONTRACT_V0.md` |
| **ActionIntentPacket** | Universal | FUTURE | Proposes side-effect for approval. | `AGENT_INTAKE...CONTRACT_V0.md` |
| **Approval Receipt** | Guardian | CURRENT | Evidence of human decision. | `chief_approval_brain.py` |

---

## SQLite / Receipt / Read-model Alignment
- **Built Capability**: `backend_sqlite_schema.py` and `repository.py` support `semantic_records`, `validation_receipts`, and `operator_promotions`.
- **Evidence Mapping**: Schema support appears present, but packet-specific lifecycle wiring is not verified in this inventory.
- **Drift Protection**: `audit_proof_coverage.py` ensures proofs match Git HEAD, preventing stale state ingestion.
- **Read-Models**: Generated operator status/read-model surfaces and generated status breadcrumbs are the primary consumers of these receipts.
- **Ingestion Guard**: Broad RAG or SQLite ingestion is blocked until packet/source promotion rules are enforced.

---

## Maps / Index Follow-up
- `docs/INDEX.md`: Needs update for Cassandra/Chief status.
- `docs/operations/OPENCLAW_INTENT_AND_CONTROL_MAP.md`: Needs specific packet surface links.
- `docs/navigation_maps/COMPILED_KNOWLEDGE_SUBSTRATE_FRONTIER_MAP.md`: Needs alignment with active packet lanes.

---

## Do Not Build Yet (Blocked)
1. **Broad RAG**: No fuzzy context ingestion before packet boundaries are firm.
2. **DAW/Hardware Mutation**: Direct execution is strictly forbidden (no execution lanes built).
3. **Live State Claims**: No claiming "I am listening to the audio" without a deterministic receipt.
4. **LLM Authority**: Agents must not use LLM "memory" to override deterministic contracts.

---

## Recommended Next Slice
Review and index Agent Packet Doctrine Inventory v0, then choose the first per-agent contract; Cassandra/Clara is the leading candidate because packet schemas are currently implicit.

FINAL MARKER: READY_FOR_INVENTORY_REVIEW

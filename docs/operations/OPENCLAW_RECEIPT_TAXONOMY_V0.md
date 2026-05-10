# Business Ops Receipt Taxonomy v0

This document defines the narrow Receipt Taxonomy v0 for OpenClaw. Receipts in this context are durable evidence records stored in the SQLite Business Ops Ledger, used to compile read models and audit system behavior.

## 1. Receipt Purpose
- **Durable Evidence**: Receipts are immutable records of events, decisions, or side effects. They are not "truth" by themselves but provide the evidence from which truth is derived.
- **Read Model Input**: Read models (e.g., `OPERATOR_STATUS.md`) compile information from receipts, committed source code, tests, and operator promotions.
- **Auditability**: Receipts allow for retroactive auditing of system actions without relying on volatile log files.

## 2. Event Type Conventions
- **Preferred Format**: Canonical receipts should follow the `[domain]_[action]_receipt` or `[noun_phrase]_receipt` pattern.
- **Current Canonical Example**:
  - `orientation_snapshot_receipt`
- **Legacy/Early Artifacts**:
  - `orientation_snapshot` (Do not use this pattern for new receipts).

## 3. Receipt Classes
- **Orientation/Status Receipts**: Signals about the current state or focus of the operator (e.g., `orientation_snapshot_receipt`).
- **Packet/Intent Receipts**: Evidence of intent creation or packet lifecycle transitions.
- **Retrieval Receipts**: Proof of data retrieval from external sources or internal databases.
- **Side-Effect Receipts**: Records of actions taken that modify external state (e.g., file writes, API calls).
- **Approval/Gate Receipts**: Evidence of human-in-the-loop approvals or automated gate transitions.
- **Operator Promotion Receipts**: Signals that a specific state or version has been promoted to a higher stability tier.
- **Test/Proof Receipts**: Evidence of test execution or formal proofs of correctness.

## 4. Minimum Safe Fields
All receipts should aim to include the following fields at minimum:
- **Timestamp**: ISO 8601 UTC.
- **Event Type**: Slugified canonical name.
- **Actor/Source**: The agent, script, or user responsible for the event.
- **Safe Summary**: A human-readable, non-sensitive description of the event.
- **Source Pointer**: Path, Git commit, or URI when applicable.
- **Hash**: SHA-256 of the related artifact when useful for integrity.
- **Redaction Marker**: Explicit indication if sensitive data was removed.
- **No Raw Private Data**: Raw private data must be excluded by default.

## 5. Sensitive-Data Boundaries
The ledger MUST NOT contain:
- Raw Gmail/Email bodies.
- Legal, client-sensitive, or private content.
- Credentials, tokens, or secrets.
- Payment or billing details.
- Live runtime-health claims (unless produced by a deterministic readiness probe).

## 6. Promotion Doctrine
- **Receipt != Truth**: A receipt records an event, not its ultimate validity.
- **Retrieval != Truth**: Data fetched might be stale or incorrect.
- **Synthesis != Truth**: AI-generated summaries are probabilistic.
- **Read Model != Authority**: A read model is only as authoritative as the evidence (receipts + source + tests) it is generated from.
- **Authority**: Durable working state is decided by operator promotion, committed tests, and source code.

## 7. Future Event-Type Examples (Non-Implemented)
These are planned but not yet implemented:
- `generated_status_check_receipt`
- `operator_promotion_receipt`
- `cassandra_status_answer_receipt`
- `retrieval_query_receipt`
- `side_effect_request_receipt`
- `approval_decision_receipt`

## 8. Explicit Non-Goals
- No schema changes in this phase.
- No automated ingestion or RAG implementation.
- No broad data extraction or document QA.
- No live runtime activation based solely on ledger state.

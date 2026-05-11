# OpenClaw Packet-to-Receipt Mapping v0

## Status
- **Source basis**: repo evidence only
- **Purpose**: mapping doc, not runtime wiring
- **This document does not prove receipts are written**
- **This document does not authorize ingestion**
- **This document separates terrain from Map Room**

## Terrain vs Declaration
- **Packet template declaration**: The JSON files in `templates/` that define the expected fields and receipt requirements for a given agent action.
- **Receipt expectation**: The logical name of a receipt (e.g., `approval_log_entry`) that an agent claims it will produce or requires.
- **Runtime receipt writer**: The actual Python function (e.g., `append_packet_receipt` in `business_ops_ledger.py`) that executes a write to storage.
- **SQLite/ledger terrain**: The actual database schema and file (typically `.openclaw/business_ops/ledger.sqlite`) that holds durable records.
- **Generated read-model consumer**: Scripts like `generate_operator_status.py` that read the ledger to produce documentation.
- **Map Room/index docs**: Navigational documents that describe the intended architecture without necessarily reflecting the current built state.

## Mapping Table

| Template Path | packet_type | Owner/Lane | required_receipts / expected_receipts | provenance_refs | Receipt Status | Known Writer / Evidence | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `templates/agent/action_intent_packet_template.json` | `agent.action_intent_packet` | Universal | `action_intent_gate_receipt` | [] | SQLITE_VERIFIED | `business_ops_ledger.py` | Records intent evaluation only. |
| `templates/agent/agent_intake_packet_template.json` | `agent.intake_packet` | Universal | [] | [] | DECLARED_ONLY | - | - |
| `templates/agent/cassandra_email_triage_packet_template.json` | `cassandra.email_triage_packet` | Cassandra | `email_triage_classification` | `gmail_thread_id` | WRITER_VERIFIED | `cassandra_email_triage.py` | Writes to JSONL, not SQLite. |
| `templates/agent/cassandra_outreach_draft_packet_template.json` | `cassandra.outreach_draft_packet` | Cassandra | `outreach_email_draft_receipt` | `draft_id`, `thread_id` | DECLARED_ONLY | - | - |
| `templates/agent/cassandra_pii_handling_packet_template.json` | `cassandra.pii_handling_packet` | Cassandra | `pii_vault_record` | `token_mapping_id` | DECLARED_ONLY | - | - |
| `templates/agent/chief_acceptance_verdict_packet_template.json` | `chief.acceptance_verdict_packet` | Chief | [] | [] | DECLARED_ONLY | - | - |
| `templates/agent/chief_action_intent_evaluation_packet_template.json` | `chief.action_intent_evaluation_packet` | Chief | [] | [] | DECLARED_ONLY | - | - |
| `templates/agent/chief_approval_decision_packet_template.json` | `chief.approval_decision_packet` | Chief | `approval_log_entry` | [] | SQLITE_VERIFIED | `business_ops_ledger.py` | Records approval decision only; does not prove execution. |
| `templates/agent/chief_routing_decision_packet_template.json` | `chief.routing_decision_packet` | Chief | [] | [] | DECLARED_ONLY | - | - |
| `templates/agent/guardian_approval_decision_packet_template.json` | `guardian.approval_decision_packet` | Guardian | `approval_log_entry` | [] | SQLITE_VERIFIED | `business_ops_ledger.py` | Records approval decision only; does not prove execution. |
| `templates/agent/guardian_approval_request_packet_template.json` | `guardian.approval_request_packet` | Guardian | `approval_request_record` | [] | DECLARED_ONLY | - | - |
| `templates/agent/hermes_advisory_output_memo_template.json` | `hermes.advisory_output_memo` | Hermes | [] | [] | DECLARED_ONLY | - | - |
| `templates/agent/hermes_advisory_packet_template.json` | `hermes.advisory_packet` | Hermes | [] | [] | DECLARED_ONLY | - | - |
| `templates/producer/producer_review_template.json` | `producer.review_packet` | Producer | [] | [] | DECLARED_ONLY | - | - |

### Non-Template Receipts (Terrain Only)

| Receipt Name | Owner/Lane | Receipt Status | Known Writer / Evidence | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `orientation_snapshot_receipt` | Operator | SQLITE_VERIFIED | `scripts/orientation_snapshot.py` | Written to `events` table in SQLite. |
| `test_proof_receipt` | Operator | SQLITE_VERIFIED | `scripts/generate_operator_status.py` | Evidence used for read-model generation. |

## Agent Summary

### Producer/Niles
- **Packet templates**: `producer_review_template.json`.
- **Receipt expectations**: None declared in template.
- **Writer terrain**: Not verified for specific producer reviews.
- **SQLite terrain**: Not verified.
- **Current status**: DECLARED_ONLY.

### Cassandra
- **Packet templates**: `email_triage`, `outreach_draft`, `pii_handling`.
- **Receipt expectations**: `email_triage_classification`, `outreach_email_draft_receipt`, `pii_vault_record`.
- **Writer terrain**: `record_email_triage_classification` verified (JSONL).
- **SQLite terrain**: Not verified.
- **Current status**: WRITER_VERIFIED (partially, non-SQLite).

### Chief
- **Packet templates**: `acceptance_verdict`, `action_intent_evaluation`, `approval_decision`, `routing_decision`.
- **Receipt expectations**: `approval_log_entry`.
- **Writer terrain**: `record_approval_log_entry` verified.
- **SQLite terrain**: Verified in `events` and `packets` tables.
- **Current status**: SQLITE_VERIFIED (partial).

### Guardian
- **Packet templates**: `approval_decision`, `approval_request`.
- **Receipt expectations**: `approval_log_entry`, `approval_request_record`.
- **Writer terrain**: `record_approval_log_entry` verified.
- **SQLite terrain**: Verified in `events` and `packets` tables.
- **Current status**: SQLITE_VERIFIED (partial).

### Hermes
- **Packet templates**: `advisory_output_memo`, `advisory_packet`.
- **Receipt expectations**: None declared.
- **Writer terrain**: Not verified.
- **SQLite terrain**: Not verified.
- **Current status**: DECLARED_ONLY.

### Universal agent intake/action
- **Packet templates**: `agent_intake`, `action_intent`.
- **Receipt expectations**: `action_intent_gate_receipt`.
- **Writer terrain**: `record_action_intent_gate_receipt` verified.
- **SQLite terrain**: Verified in `events` and `packets` tables.
- **Current status**: SQLITE_VERIFIED.

## Known Receipt Names

### Action/Approval
- `approval_log_entry`
- `approval_request_record`

### Cassandra/Email/PII
- `email_triage_classification`
- `outreach_email_draft_receipt`
- `pii_vault_record`

### Hermes/Advisory
- (None currently declared)

### Producer/Review
- (None currently declared)

### Universal/Intake
- `action_intent_gate_receipt` (In `action_intent_packet_template.json`)

## Risks
- **Template declaration mistaken for durable truth**: Agents may claim a receipt is "required" without any runtime code actually enforcing or writing it.
- **Non-deterministic receipt names**: If agents or scripts invent receipt names that are not in the mapping table, the deterministic spine is weakened.
- **Duplicate receipt names across ledgers**: Lack of a central registry could lead to name collisions.
- **Generated read-models consuming partial terrain**: Read-models might only look for `test_proof_receipt` and miss other valid evidence.
- **Sensitive-data receipt leakage**: Receipts might inadvertently store PII if not properly gated (see `pii_vault_record` intent).
- **Map Room overclaiming terrain**: Navigational maps might claim the system is "RECEIPTED" when only templates exist.

## Recommended Next Slice
**Read-only receipt writer audit for declared receipt names.**

**Rationale**: The mapping now distinguishes declared receipt expectations from verified terrain. The next safe move is to inspect actual writer paths for `approval_log_entry`, `approval_request_record`, `outreach_email_draft_receipt`, and `pii_vault_record` before adding runtime wiring or claiming SQLite-backed receipt status.

## Completed Gates
- **Placeholder Rejection**: `tests/test_packet_template_receipt_provenance_fields.py` now rejects all placeholder/stub/todo/tbd receipt names.
- **Doctrine Alignment**: `action_receipt_placeholder` replaced with `action_intent_gate_receipt`.

## Do Not Build Yet
- Broad RAG ingestion
- Gmail body ingestion
- Live runtime mutation
- SQLite schema changes
- New receipt writers
- Automatic promotion
- Map Room automation

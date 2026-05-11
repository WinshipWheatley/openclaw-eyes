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
| `templates/agent/action_intent_packet_template.json` | `agent.action_intent_packet` | Universal | `action_receipt_placeholder` | [] | DECLARED_ONLY | - | Uses placeholder. |
| `templates/agent/agent_intake_packet_template.json` | `agent.intake_packet` | Universal | [] | [] | DECLARED_ONLY | - | - |
| `templates/agent/cassandra_email_triage_packet_template.json` | `cassandra.email_triage_packet` | Cassandra | `email_triage_classification` | `gmail_thread_id` | WRITER_VERIFIED | `cassandra_email_triage.py` | Writes to JSONL, not SQLite. |
| `templates/agent/cassandra_outreach_draft_packet_template.json` | `cassandra.outreach_draft_packet` | Cassandra | `outreach_email_draft_receipt` | `draft_id`, `thread_id` | DECLARED_ONLY | - | - |
| `templates/agent/cassandra_pii_handling_packet_template.json` | `cassandra.pii_handling_packet` | Cassandra | `pii_vault_record` | `token_mapping_id` | DECLARED_ONLY | - | - |
| `templates/agent/chief_acceptance_verdict_packet_template.json` | `chief.acceptance_verdict_packet` | Chief | [] | [] | DECLARED_ONLY | - | - |
| `templates/agent/chief_action_intent_evaluation_packet_template.json` | `chief.action_intent_evaluation_packet` | Chief | [] | [] | DECLARED_ONLY | - | - |
| `templates/agent/chief_approval_decision_packet_template.json` | `chief.approval_decision_packet` | Chief | `approval_log_entry` | [] | DECLARED_ONLY | - | - |
| `templates/agent/chief_routing_decision_packet_template.json` | `chief.routing_decision_packet` | Chief | [] | [] | DECLARED_ONLY | - | - |
| `templates/agent/guardian_approval_decision_packet_template.json` | `guardian.approval_decision_packet` | Guardian | `approval_log_entry` | [] | DECLARED_ONLY | - | - |
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
- **Writer terrain**: Not verified.
- **SQLite terrain**: Not verified.
- **Current status**: DECLARED_ONLY.

### Guardian
- **Packet templates**: `approval_decision`, `approval_request`.
- **Receipt expectations**: `approval_log_entry`, `approval_request_record`.
- **Writer terrain**: Not verified.
- **SQLite terrain**: Not verified.
- **Current status**: DECLARED_ONLY.

### Hermes
- **Packet templates**: `advisory_output_memo`, `advisory_packet`.
- **Receipt expectations**: None declared.
- **Writer terrain**: Not verified.
- **SQLite terrain**: Not verified.
- **Current status**: DECLARED_ONLY.

### Universal agent intake/action
- **Packet templates**: `agent_intake`, `action_intent`.
- **Receipt expectations**: `action_receipt_placeholder`.
- **Writer terrain**: Not verified.
- **SQLite terrain**: Not verified.
- **Current status**: DECLARED_ONLY (with placeholders).

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
- (None currently declared)

### Placeholders Needing Replacement
- `action_receipt_placeholder` (In `action_intent_packet_template.json`)

## Risks
- **Template declaration mistaken for durable truth**: Agents may claim a receipt is "required" without any runtime code actually enforcing or writing it.
- **Placeholder receipt names fossilizing**: Using `action_receipt_placeholder` in templates may lead to it being used in actual packets if not caught by tests.
- **Duplicate receipt names across ledgers**: Lack of a central registry could lead to name collisions.
- **Generated read-models consuming partial terrain**: Read-models might only look for `test_proof_receipt` and miss other valid evidence.
- **Sensitive-data receipt leakage**: Receipts might inadvertently store PII if not properly gated (see `pii_vault_record` intent).
- **Map Room overclaiming terrain**: Navigational maps might claim the system is "RECEIPTED" when only templates exist.

## Recommended Next Slice
**B. Add tests that reject placeholder receipt names except in explicitly legacy/deferred templates.**

**Rationale**: Preventing the "fossilization" of placeholders like `action_receipt_placeholder` is the highest priority for maintaining a clean deterministic spine. Wiring (D) or replacement (A) is premature until the validation gates (B) are in place to prevent regression.

## Do Not Build Yet
- Broad RAG ingestion
- Gmail body ingestion
- Live runtime mutation
- SQLite schema changes
- New receipt writers
- Automatic promotion
- Map Room automation

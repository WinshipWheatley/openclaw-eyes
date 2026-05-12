# OPENCLAW TRUTH PACKET DECISION RECEIPTS V0

- **Date:** 2026-05-12
- **Status:** Contract Defined — Not yet implemented in runtime writer
- **Receipt Type:** `truth_packet_decision_receipt`

## 1. Purpose
The `truth_packet_decision_receipt` provides a durable, append-only record in the SQLite ledger of every decision made by the Truth Reconciliation Gateway. This ensures that the boundary between verified truth, uncertain evidence, and blocked corruption is fully auditable without leaking unsafe or sensitive fact content into the receipt layer.

## 2. Required Fields
Every `truth_packet_decision_receipt` MUST include the following fields:

- **receipt_type**: `truth_packet_decision_receipt`
- **packet_status**: One of `MODEL_ALLOWED_VERIFIED`, `MODEL_ALLOWED_UNCERTAIN`, or `MODEL_BLOCKED`.
- **fact_text_crossed_model_boundary**: `true` if `packet_status` is `MODEL_ALLOWED_VERIFIED` or `MODEL_ALLOWED_UNCERTAIN`; `false` if `MODEL_BLOCKED`.
- **fact_text_redacted_in_receipt**: `true` (receipts must NEVER store the actual `fact_text`).
- **runtime_authority**: `false` (Truth packets are descriptive, not authoritative for execution).
- **execution_authority**: `0`
- **external_model_access_granted**: `false` (Unless explicitly true in a future gated path).
- **recorded_at**: RFC 3339 UTC timestamp.

### 2.1 Contextual Fields (Optional/If Available)
- **question** / **query_text**: The natural language question or query that triggered the retrieval.
- **fact_id**: The unique ID of the canonical fact being evaluated.
- **truth_source_id**: The ID of the source document in the registry.
- **source_file**: The observed path of the source document.
- **source_commit**: The commit hash associated with the fact.
- **content_hash**: The recorded hash of the fact content.
- **source_content_hash_status**: The status of the source (e.g., `current`, `stale`, `changed`).
- **truth_status**: The classification of the truth (e.g., `doctrine_reference`).
- **verification_required**: Boolean/Integer indicating if verification is needed.
- **verification_evidence_id**: ID of the evidence supporting the fact.
- **uncertainty_status**: Reason for uncertainty (e.g., `verification_required_no_evidence`).
- **confidence_band**: Numerical or categorical confidence (e.g., `medium_provisional`).
- **block_reason**: Why the packet was blocked (e.g., `source_hash_mismatch`).
- **transitions**: The state machine history of the gateway decision.

## 3. Safety Boundaries and Invariants

- **Fact Content Redaction**: `fact_text` must NEVER be stored in the receipt. The receipt only proves that a decision was made and whether content was allowed to pass to the model.
- **Blocked Path Secrecy**: If `packet_status` is `MODEL_BLOCKED`, `fact_text_crossed_model_boundary` MUST be `false`.
- **Integrity Precedence**: Source hash mismatches MUST result in `MODEL_BLOCKED` and `fact_text_crossed_model_boundary=false`.
- **No Truth Upgrades**: Receipt logging is a passive recording of gateway outcomes; it must not be used to upgrade the `truth_status` or `verification_required` state of a fact.
- **No Mechanical Changes**: Logging a receipt must not trigger a source hash rebaseline or modify `fact_text`.
- **Audit Only**: Receipts are for auditability and operator visibility; they do not grant runtime authority to the agent.

## 4. Contract Guarantees
- **Verified packets** are the only ones allowed to be treated as "hard truth".
- **Uncertain packets** must trigger qualified language (provisional).
- **Blocked packets** are terminal failures for that specific fact.
- **Source hash mismatch** remains a hard block.
- **Runtime authority** remains `false`.

## 5. Next Move
- **Chunk B**: Implement the `append_truth_packet_decision_receipt` function in `business_ops_ledger.py` and wire it into `scripts/truth_reconciliation_gateway.py`.

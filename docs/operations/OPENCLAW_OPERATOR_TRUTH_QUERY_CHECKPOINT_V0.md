# OPENCLAW OPERATOR TRUTH QUERY CHECKPOINT V0

- **Date:** 2026-05-12
- **Commit:** bcbe082
- **Status:** Operational — Standardized natural-language truth query interface for the human operator is active.

## Overview
The Operator Truth Query v0 introduces a high-level, human-facing CLI wrapper that serves as the primary interface for natural-language inquiries into the Truth Substrate. It routes all queries through the `answer_harness.py` layer, ensuring that every answer is filtered by the Truth Reconciliation Gateway, qualified for uncertainty, and auditable through the ledger. This wrapper enforces the system's "boundary logic" while providing a concise, readable summary of truth posture to the operator.

## 1. What is Now Built

- **`operator_truth_query.py` Wrapper**: A concise CLI tool (`python3 scripts/operator_truth_query.py "question"`) that routes standard inquiries to the truth substrate.
- **Harness Integration**: The wrapper calls `answer_harness.answer_operator_question`, preserving the mapping between operator intents (e.g., "where are we?") and canonical fact headings.
- **Boundary-Preserving Output**:
    - **Status Reporting**: Displays terminal outcomes (SUCCESS, REFUSED, MODEL_BLOCKED).
    - **Qualified Answers**: Propagates provisional language for uncertain facts.
    - **Truth Summary Metadata**: Surfaces counts of allowed, uncertain, and blocked candidates.
    - **Blocked Reason Summaries**: Lists reasons why facts were blocked without exposing their content.
    - **Boundary Disclaimers**: Explicitly displays the `answer_boundary` and a non-authorizing runtime statement.
- **Opt-In Receipt Logging**: Supports `--record-receipt` and `--receipt-db-path` for manual, auditable truth decisions.
- **Strict Read-Only Default**: The tool defaults to read-only mode and performs no writes unless explicitly instructed.

## 2. Safety Invariants

- **No Gateway Bypass**: All queries MUST flow through the `answer_harness` and `truth_reconciliation_gateway`.
- **Blocked Fact Protection**: Blocked facts are never exposed. The operator sees the *reason* for the block (e.g., hash mismatch), but never the `fact_text`.
- **Qualifying Uncertainty**: Uncertain answers are always prefixed with a provisional disclaimer. They cannot be presented as absolute truth.
- **Non-Authoritative**: `runtime_authority` is strictly `False`. The tool describes the substrate but does not grant execution power.
- **Deterministic Routing**: Inquiries are limited to recognized intents defined in the harness mapping.
- **Private by Default**: No receipts are written and no substrate mutations occur without explicit opt-in flags.

## 3. Commit Trail

- **bcbe082** feat(operator): add truth query wrapper
- **46d8067** fix(knowledge): align candidate truth posture evidence
- **548d367** fix(knowledge): summarize mixed truth candidate outcomes
- **d909e7f** fix(knowledge): clarify candidate truth posture status

## 4. What is Intentionally NOT Built

- **No Agent/Machine Consumption**: This wrapper is for the human operator. Cassandra, Chief, and other agents do not yet use this path for internal reasoning.
- **No Broad Semantic Search**: Queries are limited to specific mapped intents (e.g., "where are we?", "what is built?").
- **No Runtime Authority**: The output is informational and does not authorize service restarts or deployments.
- **No Source Mutation**: The query path does not update hashes or ingest documents.
- **No Automatic Receipt Logging**: Audit trails remain manual and opt-in to prevent ledger bloat during exploration.

## 5. Tests and Checks

- **Wrapper Unit Tests**: `tests/test_operator_truth_query.py` (5 PASS)
- **Harness Tests**: `tests/test_answer_harness.py` (11 PASS)
- **Gateway Integration**: `tests/test_truth_reconciliation_gateway.py` (29 PASS)
- **Receipt Audits**: `tests/test_truth_packet_decision_receipts_writer.py` and `tests/test_truth_gateway_receipt_integration.py` (14 PASS)
- **Manual Smoke Test**: `python3 scripts/operator_truth_query.py "where are we?"` (Verified output formatting and boundary notes).

## 6. Recommended Next Safe Lanes

1. **Manual Approved Smoke Test**: Perform a formal inquiry against the production ledger with `--record-receipt` to verify visibility in the live operator status.
2. **Standard "Where Are We?" Route**: Formally adopt this wrapper as the recommended starting point for every operator session.
3. **Read-Only Agent Consumption**: Begin prototyping a "Recent Truths" dashboard in Chief or Cassandra that consumes success receipts recorded by this wrapper.
4. **Additional Narrow Intents**: Expand the `answer_harness` to support more operator-centric queries (e.g., "what are my credentials?", "what is the billable state?") only as safe, canonical documents are ingested.

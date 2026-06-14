# Machine Intent Candidate Validator

Future LM output may propose intent candidates, but deterministic validation decides what becomes real.
The validator now consults the portable capability index for capability status, inputs, scope, and authority.

## Validator
- Candidate is not truth.
- Candidate has no execution authority.
- Candidate cannot promote itself.
- Generic language like next, go ahead, do it, or send it is not exact approval.

## Examples
- Capital Hilton next: VALIDATED_INTENT with missing PO/reference intake.
- Capital Hilton go ahead: BLOCKED_BY_AUTHORITY; exact approval still required.
- Ambiguous next: CLARIFICATION_REQUIRED with clarification.
- Cassandra draft: VALIDATED_INTENT with no send authority.
- Niles X32: CONTEXT_GAP_CREATED with source-ref context gap.
- Prompt injection: BLOCKED_BY_AUTHORITY.
- Hallucinated rail: BLOCKED_BY_MISSING_CAPABILITY.
- Send it: BLOCKED_BY_AUTHORITY with send authority false.
- Make video: VALIDATED_INTENT with provider generation missing.
- Proposed capability misuse: BLOCKED_BY_MISSING_CAPABILITY.

## Capability Index Checks
- capability_index_used: true
- matched_capabilities, missing_capabilities, and rejected_capabilities are recorded per example.
- authority_profile_checked, tenant_scope_checked, and fixture_scope_checked are recorded per example.

## Authority
- No live LM interpreter.
- No model call.
- No agent dispatch.
- No workflow run.
- No external action.
- No send/submit or approval execution.
- No candidate self-promotion.
- No credential handling or raw-body ingestion.

Next safe move: Wire future LM output into MachineIntentCandidate only after this validator is used as the promotion gate.

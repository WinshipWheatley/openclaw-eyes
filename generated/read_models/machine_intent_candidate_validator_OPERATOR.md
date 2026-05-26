# Machine Intent Candidate Validator

Future LM output may propose intent candidates, but deterministic validation decides what becomes real.

## Validator
- Candidate is not truth.
- Candidate has no execution authority.
- Candidate cannot promote itself.
- Generic language like next, go ahead, do it, or send it is not exact approval.

## Examples
- Capital Hilton next: VALIDATED_INTENT with missing PO/reference intake.
- Capital Hilton go ahead: BLOCKED_BY_AUTHORITY; exact approval still required.
- Ambiguous next: CLARIFICATION_REQUIRED with clarification.
- Cassandra draft: BUILD_CUE_CREATED with no send authority.
- Niles X32: CONTEXT_GAP_CREATED with source-ref context gap.
- Prompt injection: BLOCKED_BY_AUTHORITY.
- Hallucinated rail: BLOCKED_BY_MISSING_CAPABILITY.

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

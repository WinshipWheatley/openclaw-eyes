# Local LM Proof Response Pilot Postmortem

Status: LOCAL_LM_PROOF_RESPONSE_PILOT_POSTMORTEM_READY

This postmortem analyzes saved pilot artifacts only. It does not invoke a model, connect runtimes, send prompts, or send proof bundles.

## What Failed

- Model output did not parse as the required JSON response, so the verifier received an empty candidate.
- Verifier status: `BLOCKED_BY_DETERMINISTIC_VERIFIER`
- Verification errors: `response_not_concise, required_phrase_missing:payment evidence, required_phrase_missing:ledger, next_step_not_allowed:`

## Classification

- Non-JSON: `true`
- Structurally invalid: `true`
- Empty candidate after parse failure: `true`
- Factually unsafe: `false`
- Unsupported completion claims: `false`
- Protected action promises: `false`
- Machine-contract jargon: `false`

## Fallback

- Correctly published: `true`
- Latest headline: Needs verification

## Recommendations

- Require JSON-only output with no prose outside the JSON object.
- Include one valid example JSON response in the prompt.
- Repeat the allowed keys: headline, body, next_step, missing_input, can_do_now, cannot_do_yet, requested_controls, claimed_facts.
- Add a short local schema-adapter test before another model invocation.
- Keep verifier mandatory.
- Keep fallback mandatory.
- Do not loosen truth or authority checks to make the model pass.
- Do not loosen protected gates.
- Recommended next test: `schema_adapter_test`
- Do not rerun a model until the operator approves the next invocation.

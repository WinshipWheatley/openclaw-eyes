# External LM Synthetic Response Capture

Status: `EXTERNAL_LM_SYNTHETIC_RESPONSE_CAPTURE_READY`

This is a local-only intake path for manually pasted responses to the synthetic external LM test packet.
It does not call an external provider, send prompts, send proof bundles, read secrets, or mutate business systems.

## Manual Capture

- Paste only the synthetic external LM response text into this local capture harness.
- Do not paste private proof, real client data, credentials, internal paths, OCR, or artifact bodies.
- Run capture_manual_synthetic_response or the focused tests to get a verifier receipt.
- Use verifier_pass/verifier_fail for quality comparison only.

## Verifier Checks

- strict JSON-only parse
- required draft schema fields
- claimed facts must exist in the synthetic proof bundle
- no paid, sent, submitted, ledger-updated, or executed claims
- no send, submit, browser, Coupa, ledger, paid marking, workbook, PDF, push, merge, or worker-spawn promises
- requested controls must be safe and allowed by the synthetic bundle
- response must be concise and human-readable
- machine-contract jargon is rejected

## Boundaries

- Synthetic responses are never Finance truth.
- Private proof is not allowed.
- A passing verifier receipt is quality evidence for the synthetic test only.
- Protected actions remain blocked.

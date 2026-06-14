# Proof To Response Schema Adapter

Status: `PROOF_TO_RESPONSE_SCHEMA_ADAPTER_READY`

This adapter defines the JSON-only response draft shape for future LM proof-to-response work.
It does not invoke a model, send a prompt, connect a runtime, or grant protected authority.

## Draft Fields

- `headline`
- `body`
- `next_step`
- `missing_input`
- `can_do_now`
- `cannot_do_yet`
- `claimed_facts`
- `requested_controls`
- `uncertainty_notes`

## Prompt Rules

- return JSON only
- no markdown
- no prose outside JSON
- no code fences
- use only provided proof bundle
- do not claim paid/sent/submitted/executed unless proof says so
- do not promise protected actions
- do not ask for hidden context
- keep response concise

## Adapter Behavior

- parse strict JSON
- reject non-JSON
- reject markdown-wrapped JSON
- reject missing required fields
- normalize empty list fields
- map to proof_to_response_verifier shadow candidate fields
- preserve verifier failure reasons
- never loosen truth or authority checks

## Safety Boundary

- No local or external LM invocation.
- No prompt or proof bundle is sent anywhere.
- No email, browser, Gmail, Coupa, submit, ledger, workbook, PDF, paid marking, worker spawn, merge, or push.
- Verifier failures are preserved; the adapter does not loosen truth checks.

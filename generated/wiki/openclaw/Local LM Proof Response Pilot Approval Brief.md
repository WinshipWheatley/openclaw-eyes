# Local LM Proof Response Pilot Approval Brief

Status: review_only_pending_operator_decision

This brief does not approve or run a model. It summarizes what the operator would be reviewing.

## What Would Be Approved

One future, one-time local shadow-mode proof-to-response pilot for Finance / Capital Hilton. The pilot would ask a local approved harness to draft a short answer to: "What should I do here?"

Expected answer: "Payment evidence needed" — Coupa is processing. I can't mark this paid until payment evidence is attached. The ledger stays untouched. Next step: Attach payment evidence.

## What The Model Would See

- Lane: `finance/capital_hilton`
- Safe summary: Payment evidence is missing; Coupa is processing; ledger and paid state remain untouched.
- Missing input: payment evidence
- Allowed fields: world_ref, thread_ref, objective_ref, redacted_known_facts, proof_meter_labels, receipt_refs, gate_labels, missing_input, allowed_controls, blocked_action_summaries, human_safe_summaries, agent_voice_mode

## What The Model Would Not See

No raw bank details, credentials, device/session verification material, raw prompts, raw OCR or artifact text, workbook/email/ledger bodies, hidden implementation detail, or authority grant fields.

## What The Model Can Do

It can draft concise wording, name the missing proof, and point to the safe next control already present in the proof bundle.

## What The Model Cannot Do

It cannot send email, use Gmail/browser/Coupa, submit anything, mutate ledger or workbooks, mark paid, export PDFs, spawn workers, use tools, grant authority, or call an external provider.

## Verifier And Fallback

Verifier: `proof_to_response_verifier.py#proof_to_response_verifier_v0`

If the draft claims paid/sent/submitted, promises protected action, grants authority, or asks for hidden context, the verifier blocks it. The runtime publishes a safe fallback and records the failure reason.

## Receipts Required

- `operator_approval_receipt`
- `model_harness_selected_receipt`
- `no_external_provider_receipt`
- `redacted_proof_bundle_receipt`
- `no_tool_authority_receipt`
- `verifier_pass_fail_receipt`
- `published_response_hash_receipt`

## Operator Decision Options

- `approve_one_time_local_lm_proof_response_pilot`: allow one future local shadow-mode pilot attempt after required receipts are present.
- `request_more_detail`: ask for more detail before deciding.
- `reject_for_now`: keep live/local LM invocation blocked.

## Boundary

This brief is review-only. It creates no execution path and grants no authority.

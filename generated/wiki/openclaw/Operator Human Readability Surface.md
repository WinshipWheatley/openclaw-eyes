# Operator Human Readability Surface

Status: `OPERATOR_HUMAN_READABILITY_SURFACE_READY`

This surface gives Mission Control compact primary card copy while keeping machine refs and proof behind collapsed details.

## Display Rules

- `primary_card_max_visible_facts`: `3`
- `plain_summary_max_sentences`: `1`
- `next_safe_action_max_sentences`: `1`
- `proof_collapsed_by_default`: `True`
- `machine_refs_primary_visible`: `False`

## Compact Cards

- St. Anne’s invoice sent: May invoice was sent manually and recorded. Next: Watch for payment.
- Capital Hilton invoice submitted: Coupa is processing, and Annette was emailed. Next: Watch Coupa and payment.
- Capital Hilton proposal sent: Proposal is with Lawrence for review. Next: Wait for response.
- St. Anne’s work log captured: Saved as a draft event until you confirm it. Next: Confirm or discard.
- Capital Hilton needs operator assist: Coupa cannot run unattended. Next: Stage an operator-assist packet.

## Stale Surface Overrides

- `legacy.capital_hilton.excel_invoice_candidate_not_confirmed` -> `secondary_or_hidden` because Capital Hilton invoice was submitted through operator assist; legacy invoice candidate panels must not remain primary.
- `business_development.capital_hilton.proposal_draft_unsent` -> `secondary_or_hidden` because The proposal has been sent for client review; draft-only cards must not look unsent.
- `finance.st_annes.invoice_draft_or_send_needed` -> `secondary_or_hidden` because St. Anne's May invoice was manually sent and recorded; do not show it as draft or send-needed.

## Boundary

- No email, browser, Gmail, Coupa, portal submit, workbook, PDF, ledger, paid, or sent authority is granted.
- This is a display/read-model contract only.

# Dynamic Card Lifecycle Policy

Status: `DYNAMIC_CARD_LIFECYCLE_POLICY_READY`

This policy keeps Mission Control focused on current controls instead of stale dashboard accumulation.

## Required Fields

`lifecycle_state`, `freshness_state`, `operator_attention_required`, `visible_by_default`, `collapse_when_resolved`, `expires_at`, `replacement_card_ref`, `resolved_by_receipt_ref`, `stale_reason`, `primary_control_ref`

## Visibility Rules

- Show active/needs_operator cards by default.
- Hide resolved cards by default after receipt is recorded.
- Collapse historical cards under Completed / History.
- Stale cards must say Needs verification.
- Proof-only cards are hidden unless requested.
- Workroom cards show only if operator attention is needed.
- Finance payment-watch card stays visible only while payment evidence is missing.
- Payment-processing evidence does not mark paid.
- No card can remain primary if a newer receipt supersedes it.
- No machine-contract card is visible in operator mode.

## Lifecycle States

`active`, `waiting`, `needs_operator`, `resolved`, `archived`, `stale`, `unknown`

## Safety

This policy does not send, submit, mark paid, mutate ledgers/workbooks, invoke models, spawn workers, export PDFs, or grant authority.

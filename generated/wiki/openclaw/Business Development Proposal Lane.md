# Business Development Proposal Lane

Status: `BUSINESS_DEVELOPMENT_PROPOSAL_LANE_READY`

This lane captures reusable Business Development proposal flow before Finance. A sent proposal is still only a client-review state. It is not acceptance, invoice authorization, ledger truth, payment truth, or finance handoff.

## Lifecycle

1. `DRAFT_CREATED`
2. `DRAFT_READY_FOR_OPERATOR_REVIEW`
3. `SENT_FOR_CLIENT_REVIEW`
4. `CLIENT_ACCEPTED`
5. `FINANCE_HANDOFF_ELIGIBLE`
6. `FINANCE_HANDOFF_CREATED`

## Rules

- `proposal_sent` does not imply accepted.
- Accepted requires a separate receipt.
- Finance handoff is disabled until accepted.
- Proposal lane belongs to Business Development, not Finance.
- Email send requires explicit operator approval.
- Raw prompt dumps should not be stored in client-facing drafts.
- Style references may be stored as refs, not uncontrolled prompt blobs.

## Capital Hilton Fixture

- Client: `capital_hilton`
- Proposal type: `fight_weekend_entertainment`
- Sent to: `lawrencevalcovic@hilton.com`
- Status: `SENT_FOR_CLIENT_REVIEW`
- Proposal accepted: no
- Finance handoff allowed: no
- Invoice created: no
- Ledger mutation: no
- Paid: no
- Source read model: `/mnt/e/openclaw/generated/read_models/capital_hilton_business_development_proposal.json`

## Authority Boundary

- Email send allowed: no
- Finance handoff allowed: no
- Invoice creation allowed: no
- Ledger posting allowed: no
- Paid marking allowed: no
- Proposal acceptance marking allowed: no
- Browser/Gmail/Coupa allowed: no

## Next Safe Action

Await client response. If the client accepts, capture a separate acceptance receipt before any finance handoff, invoice creation, ledger action, or payment tracking state changes.

# First Class Capability Authority Loop

Status: `OPENCLAW_FIRST_CLASS_CAPABILITY_AUTHORITY_LOOP_READY`

Defines the reusable path from missing capability to scoped authority request, deterministic grant, build request, and activation receipt.

## Contracts

- `CAPABILITY_GAP_V0`
- `OPERATOR_AUTHORITY_REQUEST_V0`
- `OPERATOR_AUTHORITY_GRANT_V0`
- `CAPABILITY_BUILD_REQUEST_V0`
- `CAPABILITY_ACTIVATION_RECEIPT_V0`

## Read-Only Email Lookup Slice

- Missing email evidence emits `CAPABILITY_GAP_V0`.
- The gap emits `OPERATOR_AUTHORITY_REQUEST_V0` for scoped read-only email lookup.
- Natural-language confirmation compiles `OPERATOR_AUTHORITY_GRANT_V0` only when an active request exists.
- Build permission remains separate from data-access permission.
- Denied actions preserve send/delete/archive/mark-read/browser/Gmail UI/Coupa/ledger/paid/workbook/PDF/push/merge blocks.

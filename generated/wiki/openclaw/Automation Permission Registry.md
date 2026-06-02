# Automation Permission Registry

Status: `AUTOMATION_PERMISSION_REGISTRY_READY`

This registry records which automation paths are warmed, blocked, unstable, or not required. It is a capability and permission map only. It does not grant live business authority.

## Permission Statuses

- Mac bridge mount: `confirmed`
- PC bridge read/write: `confirmed`
- PC package gate: `confirmed`
- Mac Excel helper permissions: `partially_warmed`
- Live Arts helper working copy: `opened_and_closed`
- Capital Hilton helper working copy: `opened_and_closed`
- St. Anne's Excel permission persistence: `blocked_or_unstable`
- Capital Hilton operator-assist provider: `available_operator_present_required`
- Gmail send: `blocked_until_explicit_send_gate`
- Coupa submit: `blocked_until_explicit_submit_gate`
- Ledger post: `blocked`
- Paid marking: `blocked`

## Workflow Requirements

### `st_annes_work_log_event`

Required:

- `pc_package_queue`
- `privacy_gate`
- `operator_review`

Not required:

- Excel
- PDF export
- Gmail
- Coupa
- Ledger

Result: this workflow can stage local work-log events without Excel. Operator confirmation is still required before monthly rollup or invoice inclusion.

### `st_annes_monthly_invoice_rollup`

Required:

- Confirmed work-log events
- Staged workbook patch
- Excel/PDF permission resolution
- PDF artifact review
- Send gate

Result: month-end invoice generation remains blocked until St. Anne's Excel/PDF permissions are stable and the operator approves the staged artifacts.

### `capital_hilton_invoice_operator_assist`

Required:

- Operator present
- Coupa login/MFA
- Final `Submit` gate
- Final `Send` gate

Blocked:

- Unattended submit

Result: Capital Hilton invoice submission is an operator-assisted provider path, not an unattended OpenClaw action.

### `capital_hilton_proposal_followup`

Required:

- Proposal read model
- Operator approval before email

Blocked:

- Finance handoff until accepted

Result: proposal follow-up stays in Business Development until a separate acceptance receipt makes finance handoff eligible.

## Authority Boundary

- Email/Gmail send authority: no
- Browser/Coupa submit authority: no
- Workbook mutation authority: no
- PDF export authority: no
- Ledger authority: no
- Paid marking authority: no
- Autonomous OpenClaw action authority: no

## Source Proof

- PC package gate persistence: `/mnt/e/openclaw/artifacts/permission_warmup/pc/pc_package_gate_recheck_20260601T194049Z.json`
- PC full package permission warmup: `/mnt/e/openclaw/artifacts/permission_warmup/pc/pc_full_package_permission_warmup_20260601T193318Z.json`
- Mac full permission warmup: `/mnt/e/openclaw/artifacts/permission_warmup/mac/mac_full_permission_warmup_20260601T193753Z.json`
- Mac Excel permission persistence recheck: `/mnt/e/openclaw/artifacts/permission_warmup/mac/mac_excel_permission_persistence_hardened_20260601T200431Z.json`
- Operator-assist provider registry: `/mnt/e/openclaw/generated/read_models/operator_assist_provider_registry.json`
- Workflow package queue contract: `/mnt/e/openclaw/generated/read_models/workflow_package_queue_contract.json`

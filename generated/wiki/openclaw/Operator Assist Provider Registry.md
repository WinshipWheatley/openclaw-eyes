# Operator Assist Provider Registry

Status: `OPERATOR_ASSIST_PROVIDER_REGISTRY_READY`

This registry defines operator-assist providers as real execution providers while keeping them separate from autonomous OpenClaw actions. The Capital Hilton invoice run on June 1, 2026 is the fixture: Mac Codex Desktop helped with Excel, print-to-PDF, Coupa, and Gmail, while the PC side later ingested receipts.

## Providers

### `mac_codex_desktop_operator_assist`

- Capabilities: GUI navigation, Excel UI work, print-to-PDF, browser portal assist, Gmail draft/send assist
- Authority class: `operator_present_required`
- Autonomous: no
- Unattended use: blocked

### `excel_gui_print_to_pdf`

- Capabilities: high-fidelity PDF export
- Authority class: `operator_assisted`
- Known failure modes:
  - AppleScript success but no PDF
  - `OPEN_WORKBOOK` permission fragility
- Required checks: PDF exists, nonzero size, page count, hash, and text facts where available

### `coupa_browser_operator_assist`

- Capabilities: PO invoice creation, submission with final human gate
- Authority class: `explicit_submit_gate_required`
- Final gate: `Submit`
- Autonomous: no

### `gmail_operator_assist`

- Capabilities: draft, attach artifact, send after explicit approval
- Authority class: `explicit_send_gate_required`
- Final gate: `Send`
- Autonomous: no

## Rules

- Operator-assist actions are not autonomous OpenClaw actions.
- Receipts must record `operator_assisted=true`.
- Coupa or portal submission must record a final human `Submit` gate.
- Email sending must record a final human `Send` gate.
- Receipts and source artifacts must be preserved for PC/OpenClaw ingest.
- Provider activity must not mark ledger or paid state.
- Unattended use is blocked unless a future explicit provider gate is created.

## Authority Boundary

- Autonomous OpenClaw action allowed: no
- Unattended use allowed: no
- Browser/Coupa/Gmail access allowed by this registry: no
- Email send allowed by this registry: no
- Coupa submit allowed by this registry: no
- Ledger posting allowed: no
- Paid marking allowed: no

## Fixture Evidence

- Operator run status: `/mnt/e/openclaw/generated/read_models/capital_hilton_invoice_operator_run_status.json`
- Coupa workflow harvest: `/mnt/e/openclaw/generated/read_models/capital_hilton_coupa_workflow_harvest.json`
- Receipt: `/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_receipt_20260601T221600Z.json`
- Full automation report: `/mnt/e/openclaw/artifacts/invoice_workbooks/capital_hilton/capital_hilton_invoice_operator_run_full_automation_report_20260601T222036Z.md`

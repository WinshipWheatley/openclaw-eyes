# Operator Next Decision

Status: READY

## Chosen Move
- Headline: Watch Capital Hilton payment
- Summary: Coupa is processing. Ledger stays untouched until payment proof arrives.
- Action: Open Capital Hilton
- Lane: finance / capital_hilton

## Excluded Or Resolved Items
- `safe_next_st_annes_review`
- `st_annes_smoke_work_log_event`

## Proof
- Proof stays collapsed by default.
- `generated/read_models/helm_actionability_surface.json`
- `generated/read_models/helm_action_lifecycle_status.json`
- `generated/read_models/capital_hilton_invoice_operator_run_status.json`
- `generated/read_models/package_event_index.json`

## Boundary
This decision surface only reads local read models and writes generated status artifacts. It does not send email, open Gmail, open browser or Coupa, submit portal actions, mutate ledgers, mutate workbooks, export PDFs, mark paid, or create business truth.

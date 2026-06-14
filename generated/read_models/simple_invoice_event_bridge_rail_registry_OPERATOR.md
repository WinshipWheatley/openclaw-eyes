# Simple Invoice Event Bridge Rail Registry

- Rail: simple_invoice_event_bridge_pdf_artifact_rail_v0
- Status: generated deterministic read-model; no live action authority.
- Pattern: simple invoice clients use one Event Bridge prepare-PDF action, one candidate-result shape, and approve/reject operator decision contracts.
- Decision contracts: preview is not approval; approval/rejection records the operator decision only.
- Boundary: no email, Gmail, browser, Coupa, ledger, workbook cell read, PDF export, service start, or handler execution.

## Clients
- Live Arts MD (live_arts_md): simple_invoice_event_bridge_pdf_artifact_rail_v0; descriptor READY_FOR_EVENT_BRIDGE_ACTION.
- St. Anne's (st_annes): simple_invoice_event_bridge_pdf_artifact_rail_v0; descriptor PLANNED_OR_UNKNOWN_SCOPE.

## Separation

- Capital Hilton remains complex: supplier portal=True, purchase order=True; these blockers are not inherited by simple clients.

## Next Safe Move

- Emit client-specific Event Bridge envelopes from fixture/config scope; keep manual attach/link as fallback only.
- Add real client invoice facts only when a source fixture or receipt exists.

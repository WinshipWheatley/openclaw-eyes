# Workflow Block Intent / Live Draft Contract v0

## ELIWINSHIP Summary

A live draft workspace is a place to try workflow answers before they become permanent. Winship can step through blocks, change values, explore branches, and see previews update without committing canonical state.

Stepping through blocks is not permanent. Editing a value changes the active draft and downstream preview only. Current OpenClaw state, active draft state, and future captured state stay visibly separate.

A future Use this draft moment is the capture boundary. That boundary would require deterministic validation, an explicit operator action, a receipt type, and a governed state writer. This contract defines the boundary but does not write anything.

Agents can help conversationally. Cassandra, Chief, Hermes, Niles, Guardian, Clara, and future workflow agents may translate a request into candidate blocks, fill what is known from deterministic evidence, and ask only the missing questions. Their proposals are not truth.

Mission Control, Telegram, and agent conversations all use the same draft-intent shape. No surface owns workflow state. The workflow session owns state; surfaces render and propose.

Deterministic validation and receipts are required because a helpful phrase is not a durable fact. Agents translate. Determinism validates. Receipts commit. Gates execute.

This is the backend shape that can eventually make the app feel like: that was easy.

## Examples

- Capital Hilton Mission Control: adding May 22 and May 29 updates the draft performance dates, marks invoice subtotal and attachment previews stale, and stays preview-only.
- Telegram/Cassandra invoice request: Cassandra can compile the request, fill known client/rate/route fields, ask missing date questions, and keep draft review/send approval gated.
- New workflow request: an agent proposes a block chain and asks whether Winship wants to review and fill it together.
- Chief/check-engine: Chief can brief what is blocking the build from current proof refs and keep engineering detail below deck unless needed.

## Starship Operating Model

- Captain: operator/final authority.
- Bridge/Helm: command and attention surface that routes work.
- Worlds: domain work surfaces where workflows are inspected and solved.
- Away Missions: workflow sessions with one canonical state.
- Crew: agents that brief, translate, and propose without owning truth.
- Engineering: proof, sync, tests, receipts, read-models, and diagnostics below deck.
- Ship Logs: receipts and proof that make durable state auditable.
- Shipyard Mode: developer/build noise that should not dominate operator surfaces.

Helm routes; worlds do work. Engineering details stay below deck unless blocking or summoned. Agents brief, not spam. Captain sees decisions, not raw telemetry.

## Still Blocked

- No canonical state write, receipt write, capture write, execution, invoice generation, email draft/send, browser/Coupa/Gmail/Calendar/Telegram access, credential handling, model/tool/agent/runtime/queue execution, ledger write, file write, raw body ingestion, Mac UI work, Mac sync/import, network, or push.

## Machine Proof Summary

- Draft intents: `4`.
- Live workspaces: `2`.
- Agent proposals: `3`.
- Validation results: `4`.
- Capture boundaries: `4`.
- Conversational flows: `4`.
- All authority flags false: `true`.
- Content hash: `sha256:7ad5279c1bc18bbbf08d60ebed855bb547fec05b640b3d46317f79414abf82c5`.

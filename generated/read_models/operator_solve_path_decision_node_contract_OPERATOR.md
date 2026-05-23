# Operator Solve Path / Decision Node Contract v0

## ELIWINSHIP Summary

A solve path is the plain-language route through a piece of work. It does not ask Winship to manage the database, file paths, state propagation, or cleanup. It asks for the next true choice.

A decision node is one step in that route. It says what OpenClaw thinks, why it matters, what Winship can choose, and what would happen after each choice. The doctrine is simple: pick what is true; OpenClaw handles the consequences.

This prompt still does not build UI, persist answers, write receipts, or enable actions. It only models the deterministic packets a later app surface and writer lane can use.

## Why This Makes The App Easier

- Winship sees one human move instead of proof slots and machine-contract walls.
- Each choice has a known consequence before anything is written.
- I don't know is not a dead end; it creates a discovery substep target and keeps the workflow alive.
- Correction opens a follow-up node instead of making Winship solve state routing manually.
- Receipt targets are modeled now, but no receipt is written yet.

## Solve Paths

- `capital_hilton_invoice_solve_path`: Pick what is true about the invoice.
- `check_engine_diagnostic_solve_path`: Check what is actually broken.
- `chief_terrain_reconciliation_solve_path`: Pick what should stay current.
- `security_delta_solve_path`: Decide if this needs security review.
- `coupa_po_automation_candidate_solve_path`: Choose manual capture now or build the automation path.

## Capital Hilton Date Node

- Prompt: OpenClaw thinks these were the Capital Hilton performance dates. What is true?
- System thinks: May 8, 2026, May 15, 2026.
- Choices:
  - `both_dates_are_right`: Both are right -> moves workflow to confirm_rate
  - `one_date_is_wrong`: One is wrong -> opens follow-up node correct_performance_date with no dead end
  - `add_another_date`: Add another date -> opens add_performance_date; recalculation may be needed later
  - `i_dont_know_dates`: I don't know -> keeps workflow alive and may move focus to next answerable step
  - `needs_discovery_dates`: Needs discovery -> routes to Cassandra/Chief later when active; no action authority
  - `date_set_is_wrong`: This date set is wrong -> opens correction/rejection path and requires reason before quieting

Both dates are right would create an operator confirmation receipt target and move the workflow toward rate confirmation. It does not prove external truth, and final send proof may still be needed.

One date is wrong and add another date open follow-up nodes. I don't know and needs discovery create discovery substep targets. This date set is wrong opens a correction/rejection path and requires a reason before quieting.

## LM Boundary

- LM may rephrase and generate plain language from deterministic packets.
- LM may not create choices, decide authority, mark proof complete, approve action, or hide blockers.
- Choices must come from deterministic contract state.

## Still Blocked

- No answer persistence, SQLite answer writes, receipt writes, workflow execution, automation execution, approval submission, invoice generation, email/Telegram send, browser/account/Coupa/Gmail/calendar access, credential handling, model/tool/agent/runtime/queue execution, ledger writes, file cleanup, stable-map refresh, Mac UI implementation, or authority grant.

## Machine Proof Summary

- Solve paths: `5`.
- Decision nodes: `8`.
- Decision choices: `21`.
- Receipt targets: `9`.
- Receipt targets modeled, not written: `true`.
- All authority flags false: `true`.
- Content hash: `sha256:ebd1140cc3efd4776c90fcafe541a06347296b1927682baa4b30c4f19871d10b`.

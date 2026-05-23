# Workflow Session / Channel Projection / Approval Bus Contract v0

## ELIWINSHIP Summary

A workflow session is the one canonical state for a piece of work. Finance World, Telegram, Cassandra/Clara, Guardian, Chief, and the Helm may show that same state, but they do not each get their own separate version of the workflow.

This prevents split-brain. Winship answers once. A future receipt updates the canonical session. Every surface reads that state instead of keeping a private copy.

## Why Approve Once Matters

Stale approval mirrors are dangerous because one channel might show an old approval after another channel already approved, rejected, expired, cancelled, quarantined, or superseded it. The approval bus says approval exists once, approving from one channel closes every mirror, and duplicate approval is blocked.

## Capital Hilton Session

- Session: `capital_hilton_invoice_workflow_session`.
- Current state: `DECISION_NODE_ACTIVE`.
- Active solve path: `capital_hilton_invoice_solve_path`.
- Finance World and Telegram attach to the same canonical session.
- Invoice/send authority remains false.

## Channel Roles

- Finance World may later be an entry/control surface, but it reads the session.
- Telegram may later mirror or control the same session, but it cannot keep split local state.
- Cassandra/Clara may render draft or communication state later, but does not own workflow truth.
- Guardian may render review/approval state later, but does not own the invoice workflow.
- Chief may verify completion or reconciliation later, but does not execute the workflow.

## Modeled, Not Live

- No live Telegram, approval buttons, email send, invoice generation, workflow-state writes, ledger writes, browser/account access, model/tool/agent/runtime/queue execution, or stable-map refresh.

## Prompt 5

- Prompt 5 should add automation readiness / feasibility and the integrated stable-map refresh plan for this batch.

## Machine Proof Summary

- Workflow sessions: `5`.
- Channel projections: `19`.
- Approval buses: `5`.
- Finance World and Telegram same session: `true`.
- Approval more than once blocked: `true`.
- All authority flags false: `true`.
- Content hash: `sha256:84c2d96868ce9392b862f29542ad332b79b933b62a3180fdbdcfdc69bd8afb35`.

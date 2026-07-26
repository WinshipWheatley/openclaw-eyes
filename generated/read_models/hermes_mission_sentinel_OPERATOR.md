# Hermes Mission Sentinel

Goal: Send the Live Arts MD invoice today before the 4:00 PM cutoff, or manually send it.
Cutoff: 2026-05-28T16:00:00-04:00
Time bucket: CUTOFF_PASSED (0 minutes remaining)

Current blocker: invoice candidate/artifact/recipient/send readiness.

Recommended human action:
Manually send the invoice and capture proof now if OpenClaw has not produced a safe send-ready package.

Manual send proof to capture:
- recipient list
- subject
- attachment/file name
- send timestamp
- invoice id
- amount
- payment watch target
- manual send receipt

Codex PC should stop spending time on:
- Telegram integration
- Coupa/PO rails
- ledger automation
- payment matching
- new dashboards
- large refactors
- invoice generator architecture unless it directly produces today's safe artifact path

Boundary: Hermes observes only. No email, Gmail, Coupa/browser, workbook cell read, invoice generation, ledger mutation, production mutation, live model/tool action, or Repo B start.

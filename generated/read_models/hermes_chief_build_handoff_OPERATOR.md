# Hermes -> Chief Build Handoff

Goal: Send the Live Arts MD invoice today before the 4:00 PM cutoff, or manually send it.
Cutoff: 2026-05-28T16:00:00-04:00

Chief critical-path tasks:
- Build/verify Live Arts invoice candidate selection path (BOTH, CRITICAL)
- Build/verify manual artifact attach/link rail (BOTH, CRITICAL)
- Build/verify recipient confirmation rail (BOTH, CRITICAL)
- Build/verify Clara send-ready draft transition (PC, HIGH)
- Build/verify manual-send proof capture fallback (BOTH, CRITICAL)
- Build/verify payment watch readiness after send proof (PC, MEDIUM)

Mac Codex should handle:
- Build/verify Live Arts invoice candidate selection path
- Build/verify manual artifact attach/link rail
- Build/verify recipient confirmation rail
- Build/verify manual-send proof capture fallback

PC Codex should handle:
- Build/verify Live Arts invoice candidate selection path
- Build/verify manual artifact attach/link rail
- Build/verify recipient confirmation rail
- Build/verify Clara send-ready draft transition
- Build/verify manual-send proof capture fallback
- Build/verify payment watch readiness after send proof

Manual fallback:
- Winship manually sends the invoice if OpenClaw is not safely send-ready.

Do not touch: email send, Gmail drafts/polling, Coupa/browser, workbook cells, invoice generation/export, ledger mutation, production business state, Repo B runtime, live model/tool action, or push.

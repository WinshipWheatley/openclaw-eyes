# Gate Decision Ledger

Status: GATE_DECISION_LEDGER_READY

This is a non-financial governance ledger. It records why OpenClaw allows, blocks, or requires approval for package gates without touching the business ledger.

## Gates
- send_email: approval_required (guardian) - authority granted: false
- coupa_submit: approval_required (guardian) - authority granted: false
- ledger_post: blocked (guardian) - authority granted: false
- mark_paid: blocked (guardian) - authority granted: false
- workbook_mutation: approval_required (guardian) - authority granted: false
- pdf_export: approval_required (guardian) - authority granted: false
- git_push: blocked (chief) - authority granted: false
- worker_spawn: blocked (chief) - authority granted: false
- external_provider: blocked (guardian) - authority granted: false
- local_only_read: allowed (openclaw) - authority granted: false

## Boundary

No email, Coupa submit, ledger post, workbook mutation, PDF export, paid marking, worker spawn, external provider call, or git push authority is granted here.

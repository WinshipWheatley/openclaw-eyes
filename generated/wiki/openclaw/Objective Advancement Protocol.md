# Objective Advancement Protocol

Status: `OBJECTIVE_ADVANCEMENT_PROTOCOL_READY`
Generated: `2026-06-06T04:14:10+00:00`

Objective advancement is the backend meaning behind Continue, Advance, Prepare it, Stage it, Handle what you can, What's missing?, and Next safe move.

It does not mean execute the final protected action. It means advance to the next safe internal state, or explain the missing input/proof/approval.

## Class A Approval

Class A approval may allow safe internal steps:
- readback
- plan
- draft
- stage package
- inspect local/status refs
- prepare evidence request
- prepare approval package
- prepare review packet

Class A approval must not allow:
- email send
- Gmail/browser/Coupa access
- portal submit
- ledger mutation
- mark paid
- workbook source mutation
- PDF export/send
- git push/merge
- worker spawn
- external provider call

## Examples

### objective:finance:capital_hilton:payment_watch
- Next safe state: `REQUEST_PAYMENT_EVIDENCE`
- Response: I can't complete payment yet. I need payment evidence first.
- Next safe action: Attach proof
- Protected final action: `ledger_post_or_mark_paid`

### objective:finance:live_arts_md:payment_evidence
- Next safe state: `EVIDENCE_RECORDED_WAITING_FOR_CONFIRMATION`
- Response: I recorded this as payment-processing evidence. Ledger remains untouched.
- Next safe action: Review confirmation when payment proof is complete.
- Protected final action: `ledger_post_or_mark_paid`

### objective:business_development:capital_hilton:followup
- Next safe state: `FOLLOWUP_DRAFT_STAGED`
- Response: I can stage a Capital Hilton follow-up draft. I will not send it.
- Next safe action: Review the staged follow-up draft.
- Protected final action: `email_send`

### objective:build:review_packet
- Next safe state: `REVIEW_DECISION_READY_TO_RECORD`
- Response: I can record the review decision receipt. No merge or push will run.
- Next safe action: Record review decision
- Protected final action: `merge_or_git_push`

### objective:finance:st_annes:work_log_review
- Next safe state: `SURFACE_WORK_LOG_REVIEW_CHOICES`
- Response: I can surface the St. Anne's work-log review choices. I will not create an invoice, PDF, or email.
- Next safe action: Choose confirm, discard, edit, or mark test.
- Protected final action: `invoice_pdf_or_email_send`

### objective:unknown
- Next safe state: `NEEDS_VERIFICATION`
- Response: I need the lane or objective before I can safely advance it.
- Next safe action: Tell me the lane or objective.
- Protected final action: `unknown`

## Authority Boundary

Email, Gmail/browser/Coupa, portal submit, ledger mutation, paid marking, workbook mutation, PDF export/send, git push/merge, worker spawn, external provider calls, external LLM calls, and local model runtime connections remain blocked.

Status: `OBJECTIVE_ADVANCEMENT_PROTOCOL_READY`

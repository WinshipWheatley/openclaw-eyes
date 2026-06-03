# Operator Action Payloads

Status: `OPERATOR_ACTION_PAYLOADS_READY`

This read-model gives Mac cards safe backend button payloads. It is a render/stage contract only.

## Counts

- Payloads: `29`
- `explain_gate`: `5`
- `navigate`: `8`
- `record_payment_proof_intake`: `1`
- `review_decision`: `3`
- `stage_package_request`: `6`
- `system_question`: `5`
- `workbook_registration`: `1`

## Payloads

- `capital_hilton.payment.open_finance` - Open Finance / Capital Hilton (navigate, finance/capital_hilton)
- `capital_hilton.payment.record_proof` - Record payment proof (record_payment_proof_intake, finance/capital_hilton)
- `capital_hilton.proposal.stage_followup` - Stage proposal follow-up (stage_package_request, business_development/capital_hilton)
- `chief_diagnostic.open` - Open Chief diagnostic (navigate, system/chief_diagnostic)
- `client_invoice_workbook.register` - Register workbook (workbook_registration, finance/capital_hilton)
- `guardian_gate.coupa_submit.explain` - Explain this gate (explain_gate, system/guardian)
- `guardian_gate.coupa_submit.open` - Open relevant lane (navigate, finance/capital_hilton)
- `guardian_gate.coupa_submit.stage_approval_request` - Stage approval request (stage_package_request, finance/capital_hilton)
- `guardian_gate.ledger_post.explain` - Explain this gate (explain_gate, system/guardian)
- `guardian_gate.ledger_post.open` - Open relevant lane (navigate, finance/capital_hilton)
- `guardian_gate.ledger_post.stage_approval_request` - Stage approval request (stage_package_request, finance/capital_hilton)
- `guardian_gate.pdf_export.explain` - Explain this gate (explain_gate, system/guardian)
- `guardian_gate.pdf_export.open` - Open relevant lane (navigate, finance/st_annes)
- `guardian_gate.pdf_export.stage_approval_request` - Stage approval request (stage_package_request, finance/st_annes)
- `guardian_gate.send_email.explain` - Explain this gate (explain_gate, system/guardian)
- `guardian_gate.send_email.open` - Open relevant lane (navigate, finance/capital_hilton)
- `guardian_gate.send_email.stage_approval_request` - Stage approval request (stage_package_request, finance/capital_hilton)
- `guardian_gate.workbook_mutation.explain` - Explain this gate (explain_gate, system/guardian)
- `guardian_gate.workbook_mutation.open` - Open relevant lane (navigate, finance/st_annes)
- `guardian_gate.workbook_mutation.stage_approval_request` - Stage approval request (stage_package_request, finance/st_annes)
- `helm_question.capital_hilton_invoice_block.ask` - Why did Submit Capital Hilton invoice block? (system_question, finance/capital_hilton)
- `helm_question.email_authority.ask` - Can this send email? (system_question, system/guardian)
- `helm_question.hardwired_vs_spawned.ask` - What is the difference between Chief and a spawned worker? (system_question, system/architecture)
- `helm_question.safe_next.ask` - What is safe next? (system_question, finance/capital_hilton)
- `helm_question.st_annes_church_sound.ask` - Mark that I'm at church running sound. (system_question, finance/st_annes)
- `review_packet.review_packet_c4ec166103f9aa35.approve_review_packet_for_record` - Approve for record (review_decision, build/build_openclaw_backend)
- `review_packet.review_packet_c4ec166103f9aa35.mark_review_packet_informational` - Mark informational (review_decision, build/build_openclaw_backend)
- `review_packet.review_packet_c4ec166103f9aa35.open` - Open review packet (navigate, build/build_openclaw_backend)
- `review_packet.review_packet_c4ec166103f9aa35.request_review_packet_rework` - Request rework (review_decision, build/build_openclaw_backend)

## Boundary

No payload grants email send, Gmail, browser, Coupa, portal submit, ledger posting, workbook mutation, PDF export, paid/sent truth, merge, push, repair authority, worker spawn, child agents, or agent loops.

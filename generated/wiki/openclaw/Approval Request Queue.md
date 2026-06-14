# Approval Request Queue

Status: APPROVAL_REQUEST_QUEUE_READY

This queue centralizes approval requests and does not execute approvals.

## Pending Requests
- approve_review_packet_for_record (chief): Approve a review packet for record only, with no merge or push.
- request_review_packet_rework (chief): Ask for review packet rework without spawning a worker automatically.
- approve_email_draft_send (guardian): Approve an already prepared email draft for manual or gated send.
- approve_coupa_submit (guardian): Approve Coupa submit only through a separate operator-assisted provider gate.
- approve_workbook_mutation (guardian): Approve source workbook edits only after operator review.
- approve_pdf_export (guardian): Approve PDF export only through a later artifact-producing workflow.
- approve_ledger_post (guardian): Approve ledger posting only after separate payment or posting evidence exists.

Business actions require a separate executor/gate. Protected send, Coupa, ledger, workbook, PDF, submit, and paid actions remain blocked here.

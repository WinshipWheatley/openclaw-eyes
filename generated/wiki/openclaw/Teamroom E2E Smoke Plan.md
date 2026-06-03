# Teamroom E2E Smoke Plan

Status: TEAMROOM_E2E_SMOKE_PLAN_READY

Planning only. Do not run smoke from this plan.

## Scenario

- cassandra_st_annes_intake: Mission Control routes St. Anne work-log intake into a staged package or review event.
- cassandra_records_work_log_package: Work-log package or review surface records local metadata with evidence preserved.
- operator_confirms_or_marks_test: Operator decision updates review state without invoice, Excel, PDF, send, or ledger work.
- hermes_recommends_next_rail: Hermes explains architecture/safe next rail without spawning agents or invoking models.
- chief_stages_worker_package: Chief stages a worker package stub only; no worker runs.
- worker_fixture_result_becomes_review_packet: A fixture result is represented as review-packet metadata for operator review only.
- operator_records_review_decision: Decision receipt is recorded; no merge, push, worker spawn, or business action occurs.
- homecoming_brief_summarizes_result: Cassandra summarizes completed/blocked state in plain language with proof collapsed.
- guardian_confirms_no_protected_action: Guardian confirms protected actions stayed blocked.

## Blocked Gates

- send_email
- coupa_submit
- ledger_post
- mark_paid
- workbook_mutation
- pdf_export
- worker_spawn
- external_provider
- git_push

No business action proof stays false for send, Coupa, ledger, workbook, PDF/export, paid, worker spawn, external provider, and push.

# Canonical State Map

Status: `CANONICAL_STATE_MAP_READY`

This map answers where OpenClaw knows facts from. It is read-only and does not grant mutation authority.

## Domains

### Workflow package queue

- Domain: `package_queue`
- Canonical source: `generated/read_models/workflow_package_queue_contract.json`
- Truth scope: Package definitions, package statuses, workflow refs, gate results, worker result receipts.
- Write posture: `no_write_grant_from_this_map`

### Mission Control request/response receipts

- Domain: `request_response`
- Canonical source: `generated/read_models/package_event_index.json`
- Truth scope: Request/response linkage, event ids, package ids, response refs, and proof refs.
- Write posture: `no_write_grant_from_this_map`

### Operator-facing conversation journal

- Domain: `conversation_journal`
- Canonical source: `generated/read_models/operator_conversation_journal.json`
- Truth scope: Operator-facing history, thread grouping, headlines, summaries, and proof refs.
- Write posture: `no_write_grant_from_this_map`

### St. Anne's work log

- Domain: `st_annes_work_log`
- Canonical source: `generated/read_models/st_annes_work_log_events.json`
- Truth scope: Staged St. Anne's work-log events, confirmation posture, invoice inclusion status, and source package refs.
- Write posture: `no_write_grant_from_this_map`

### St. Anne's invoice status

- Domain: `st_annes_invoice_status`
- Canonical source: `generated/read_models/st_annes_invoice_status.json`
- Truth scope: Recorded invoice artifact status, manual send posture, payment status, validation refs, and safety flags.
- Write posture: `no_write_grant_from_this_map`

### Capital Hilton invoice status

- Domain: `capital_hilton_invoice_status`
- Canonical source: `generated/read_models/capital_hilton_invoice_operator_run_status.json`
- Truth scope: Ingested operator run receipt for Coupa submission posture, email recording, invoice ids, proof refs, and paid=false.
- Write posture: `no_write_grant_from_this_map`

### Capital Hilton proposal status

- Domain: `capital_hilton_proposal_status`
- Canonical source: `generated/read_models/capital_hilton_business_development_proposal.json`
- Truth scope: Business Development proposal status, proposal refs, operator-assisted send recording, review posture, and no-finance-handoff flags.
- Write posture: `no_write_grant_from_this_map`

### Agent voice profiles

- Domain: `agent_voice_profiles`
- Canonical source: `generated/read_models/agent_voice_profiles.json`
- Truth scope: Speaker refs, voice profile refs, voice modes, copy rules, and TTS shaping rules.
- Write posture: `no_write_grant_from_this_map`

### Automation permission registry

- Domain: `permission_registry`
- Canonical source: `generated/read_models/automation_permission_registry.json`
- Truth scope: Permission posture for Coupa submit, Gmail send, ledger post, paid marking, bridge, package gate, and workbook-related gates.
- Write posture: `no_write_grant_from_this_map`

### Overnight workboard

- Domain: `overnight_workboard`
- Canonical source: `generated/read_models/overnight_workboard.json`
- Truth scope: Planning-only work packets, Hermes recommendations, Chief packets, and Guardian gates for operator review.
- Write posture: `no_write_grant_from_this_map`

### Protected business ledger

- Domain: `business_ledger`
- Canonical source: `generated/read_models/sqlite_governance_registry.json`
- Truth scope: Ledger location/classification truth: protected_business_ledger, isolated, consolidation forbidden.
- Write posture: `no_write_grant_from_this_map`

## Truth Rules

- Package status truth comes from package queue / package event index.
- Operator-facing history comes from conversation journal.
- St. Anne's work-log truth comes from St. Anne's work-log DB/read model.
- Capital Hilton invoice submission truth comes from ingested operator run receipt/read model.
- Proposal status truth comes from Business Development proposal read model.
- Paid truth never comes from proposal, send, or Coupa submit alone.
- Ledger truth stays isolated until explicit payment evidence.

## Boundary

- No database consolidation, move, delete, or migration.
- No ledger or workbook mutation.
- No Gmail, browser, Coupa, email send, paid marking, submit, or push.

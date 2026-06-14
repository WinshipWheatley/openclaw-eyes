# SQLite Governance Registry

Status: `SQLITE_GOVERNANCE_REGISTRY_READY`

This registry classifies OpenClaw SQLite databases by truth ownership. It does not consolidate, migrate, delete, or grant write authority.

Registry SQLite: `/home/openclaw/generated/system_knowledge/sqlite_governance_registry.sqlite`
Databases classified: `654`
Protected ledger entries: `438`
Consolidation candidates: `17`
Unknown review count: `10`

## Classification Counts

- `canonical_workflow_state`: 3
- `generated_evidence`: 15
- `generated_status`: 2
- `test_harness`: 186
- `legacy_archive`: 0
- `protected_business_ledger`: 438
- `unknown_needs_review`: 10

## Boundary

- Business ledgers are `protected_business_ledger` and `consolidation_risk=forbidden`.
- Test harness databases are never canonical truth.
- Generated status and proof databases remain evidence unless explicitly named canonical.
- Unknown databases are non-writable and require review.
- `safe_to_delete` is false for every database.

## Protected Ledger Samples

- `/home/openclaw/.openclaw/business_ops/backups/ledger_before_controlled_ingest_20260512_114446.sqlite` (forbidden)
- `/home/openclaw/.openclaw/business_ops/ledger.sqlite` (forbidden)
- `/home/openclaw/.openclaw/tmp/debug-shuttle/ledger.sqlite` (forbidden)
- `/home/openclaw/.openclaw/tmp/debug-shuttle2/ledger.sqlite` (forbidden)
- `/home/openclaw/.openclaw/tmp/debug_read_model_shuttle/1779389592/ledger.sqlite` (forbidden)
- `/home/openclaw/.openclaw/tmp/pytest-agent-platform-adjacent-final/test_build_script_accepts_fixt0/ledger.sqlite` (forbidden)
- `/home/openclaw/.openclaw/tmp/pytest-agent-platform-adjacent-final/test_degraded_if_proof_files_m0/ledger.sqlite` (forbidden)
- `/home/openclaw/.openclaw/tmp/pytest-agent-platform-adjacent-final/test_extra_files_require_manua0/ledger.sqlite` (forbidden)
- `/home/openclaw/.openclaw/tmp/pytest-agent-platform-adjacent-final/test_hash_mismatch_produces_st0/ledger.sqlite` (forbidden)
- `/home/openclaw/.openclaw/tmp/pytest-agent-platform-adjacent-final/test_mac_completion_newer_than0/ledger.sqlite` (forbidden)

## Unknown Review Samples

- `/home/openclaw/.openclaw/activation/activation_receipts.sqlite`
- `/home/openclaw/.openclaw/flows/registry.sqlite`
- `/home/openclaw/.openclaw/invoice_review/invoice_review_state.sqlite`
- `/home/openclaw/.openclaw/memory/chief.sqlite`
- `/home/openclaw/.openclaw/memory/health-sentinel.sqlite`
- `/home/openclaw/.openclaw/memory/main.sqlite`
- `/home/openclaw/.openclaw/memory/strategy-sentinel.sqlite`
- `/home/openclaw/.openclaw/memory/timeline-sentinel.sqlite`
- `/home/openclaw/.openclaw/operator_events/operator_action_events.sqlite`
- `/home/openclaw/.openclaw/tasks/runs.sqlite`

# Agentic Chain Inspector

Status: `AGENTIC_CHAIN_INSPECTOR_READY`

This is a read-only map of OpenClaw's message -> gate -> package -> worker -> receipt chain plus a SQLite inventory. It does not consolidate databases.

SQLite DBs inventoried: `651`
Inspector SQLite: `/home/openclaw/generated/system_knowledge/agentic_chain_inspector.sqlite`

## Gate Chain

1. `human_message` - live, exists=True, sqlite_tracked=True, tests=True
2. `privacy_pii_gate` - dry-run, exists=True, sqlite_tracked=True, tests=True
3. `intent_lm_gate` - dry-run, exists=True, sqlite_tracked=True, tests=True
4. `sqlite_package_gate` - dry-run, exists=True, sqlite_tracked=True, tests=True
5. `workflow_package_compiler` - dry-run, exists=True, sqlite_tracked=True, tests=True
6. `capability_provider_gate` - dry-run, exists=True, sqlite_tracked=True, tests=True
7. `lm2_child_cage` - contract-only, exists=True, sqlite_tracked=False, tests=True
8. `worker` - dry-run, exists=True, sqlite_tracked=True, tests=True
9. `result_receipt` - dry-run, exists=True, sqlite_tracked=True, tests=True
10. `operator_review_gate` - live, exists=True, sqlite_tracked=True, tests=True
11. `business_action_gate` - dry-run, exists=True, sqlite_tracked=True, tests=True
12. `final_read_model_ui_response` - live, exists=True, sqlite_tracked=True, tests=True

## Top Fragmentation Risks

- `duplicate_package_concepts` (high): Package, gate, and delegated/LM package concepts exist in multiple SQLite stores and generated contracts. Affected paths: 103.
- `duplicate_event_journals` (medium): Operator events, conversation history, sentinels, and service status stores can drift if treated as separate truth stores. Affected paths: 10.
- `request_response_status_stores` (medium): Request/response and review status appears across bridge files, package queue state, and invoice-review state. Affected paths: 26.
- `generated_status_dbs` (medium): Generated system-knowledge databases should remain read-model/evidence stores until canonical ownership is declared. Affected paths: 16.
- `test_harness_dbs` (low): Test harness and pytest databases are numerous and should be excluded from production consolidation. Affected paths: 622.
- `business_ledger_exclusion` (critical): Business ledger databases must not be mixed with package, test, or agent-state consolidation. Affected paths: 438.

## Recommendations

- `consolidate_first`: Create a single package-event index that references workflow_package_queue, request/response receipts, and operator_conversation_journal without moving business ledger data.
- `leave_isolated`: Keep .openclaw/business_ops/ledger.sqlite and all ledger backups out of package/agent consolidation.
- `leave_isolated`: Keep token_vault and privacy stores isolated; reference only protected hashes or token refs.
- `read_only_evidence`: Treat .openclaw/test_harness and .openclaw/tmp pytest databases as read-only evidence or disposable fixtures, not production truth.
- `defer`: Do not merge generated status databases until each has a declared canonical owner and migration target.
- `never_mix`: Never mix business ledger truth with agent memory, package queues, test harnesses, or generated read-model status stores.

## Boundary

- No SQLite consolidation.
- No business ledger mutation.
- No email, browser, Gmail, Coupa, workbook, PDF, submit, paid, agent spawn, or loop execution.
- The business ledger must remain excluded from agent/package/test consolidation.

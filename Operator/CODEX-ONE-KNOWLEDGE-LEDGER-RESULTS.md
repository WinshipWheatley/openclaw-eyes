# CODEX ONE KNOWLEDGE LEDGER RESULTS

status: partial_operator_pending
repo: /home/openclaw
branch: codex/stress-fixes
no_push: true
generated_at: 2026-06-30T03:45:00Z

## Commits

- 786ddc69 fix(context): enforce ledger provenance for packet builders
- bb063d73 feat(ledger): add gated knowledge consolidation tools

## Read-Models Determination

answer: mixed

- generated/read_models JSON files are not uniformly ledger projections.
- Probe result: 494 JSON read models found.
- Ledger-backed or ledger-recorded projections: 58.
- Independent or unmarked generated read models: 436.
- Decision: context_source reads the business-ops ledger directly as source of truth. Existing read-model facts are preserved for lane compatibility, but every emitted packet fact now carries explicit ledger_provenance metadata.

samples:

- ledger_backed_or_recorded: active_machinery_gemini_verification.json, agent_lanes.json, agent_runtime_readiness.json, agent_work_packets.json, agentic_chain_inspector.json, artifact_registry.json, bridge_manual_mount_recovery_packet.json, bridge_trust_sync_truth.json, capital_hilton_actionable_review_packet.json, capital_hilton_coupa_start_approval_packet.json, capital_hilton_send_approval_gate.json, cassandra_chief_memory_authority.json
- independent_or_unmarked: OPENCLAW_CRITICAL_PATH_EXECUTION_PACKET_READY.json, OPENCLAW_REMAINING_WORK_STRATIFIER_READY_PACKET.json, active_machinery_block_later_guardrail.json, active_machinery_classification_orchestrator.json, active_machinery_high_risk_quarantine.json, active_machinery_operator_disposition.json, active_machinery_quarantine_decision_packet.json, active_machinery_quarantine_operator_review.json, active_next_step_policy.json, agent_capability_migration_map.json, agent_conversation_handoff_step_packet_contract.json, agent_execution_packet_compiler_contract.json

## Files Changed

commit 786ddc69:

- context_source.py
- context_packet_builder_registry.py
- maestro_context_packet.py
- cassandra_context_packet.py
- hermes_context_packet.py
- guardian_context_packet.py
- backend_knowledge_packet.py
- cassandra_clara_fact_packet.py
- tests/test_context_source.py
- tests/test_context_packet_ledger_contract.py
- tests/test_maestro_brain_packet.py

commit bb063d73:

- scripts/ingest_system_catalog_to_ledger.py
- scripts/reconcile_knowledge_satellites.py
- scripts/export_hermes_inventory_from_ledger.py
- sqlite_governance_registry.py
- tests/test_one_knowledge_ledger_tools.py
- sidecars/hermes_home/OPENCLAW_INVENTORY.md

## Per-Item Status

### 1. Determine read_models source

status: completed

result:

- Mixed source model. Some generated read models are ledger projections/recorded packet items; most are independent or unmarked.
- The shared context source therefore reads ledger.sqlite directly and annotates legacy lane facts with ledger provenance.

### 2. Guarantee first: context_source + contract test

status: completed

implementation:

- Added ledger-backed context_source with capped facts from canonical_facts, agent_lanes, repo roots, and corpus paths.
- Added sensitivity/path filtering for secret, credential, vault, private raw, legal-private, finance-private, no-go, MAX-like labels, and secret paths.
- Added context_packet_builder_registry and tests/test_context_packet_ledger_contract.py.
- Contract discovers top-level *_context_packet.py and *_fact_packet.py builders and asserts the registered set is complete. It also includes backend_knowledge_packet.py as the explicit non-pattern builder from the work order.

builders registered:

- maestro_context_packet.py
- cassandra_context_packet.py
- hermes_context_packet.py
- guardian_context_packet.py
- cassandra_clara_fact_packet.py
- backend_knowledge_packet.py

### 3. Repoint packet builders

status: completed_with_compatibility_adapter

details:

- Maestro, Cassandra, Hermes, Guardian, Cassandra/Clara, and backend packet paths now call context_source.
- Existing lane source_ref values were preserved to avoid breaking existing grounded tests and prompt behavior.
- Every emitted fact now carries ledger_provenance and ledger_source_ref.
- backend_knowledge_packet.py now exposes build_backend_ledger_context_packet().
- Cassandra/Clara now supports write_artifacts=False and allow_schema_init=False for read-only live probes.
- Maestro DEFAULT_SYSTEM_CATALOG_PATH now points to /home/openclaw/.openclaw/business_ops/ledger.sqlite instead of /home/openclaw/system_catalog.sqlite3.
- Mixed stale relative-date operator truth is now stripped clause-by-clause, so useful facts survive while stale "next Friday is 2026-06-26" claims are excluded.

### 4. Write multi-repo knowledge into ledger

status: operator_pending

implementation:

- Added scripts/ingest_system_catalog_to_ledger.py.
- It dedupes worktrees by remote/name/path and writes to knowledge_repo_roots only when --confirm is supplied.
- Live dry-run did not write.

live dry-run:

```json
{
  "catalog_path": "/home/openclaw/system_catalog.sqlite3",
  "deduped_repo_count": 10,
  "ledger_path": "/home/openclaw/.openclaw/business_ops/ledger.sqlite",
  "operator_command": "python3 scripts/ingest_system_catalog_to_ledger.py --catalog /home/openclaw/system_catalog.sqlite3 --ledger /home/openclaw/.openclaw/business_ops/ledger.sqlite --confirm",
  "source_repo_count": 134,
  "status": "operator_confirmation_required",
  "target_table": "knowledge_repo_roots"
}
```

operator command:

```bash
mkdir -p /home/openclaw/.openclaw/business_ops/backups
cp -a /home/openclaw/.openclaw/business_ops/ledger.sqlite /home/openclaw/.openclaw/business_ops/backups/ledger.sqlite.$(date -u +%Y%m%dT%H%M%SZ).before-one-knowledge-ledger
python3 scripts/ingest_system_catalog_to_ledger.py --catalog /home/openclaw/system_catalog.sqlite3 --ledger /home/openclaw/.openclaw/business_ops/ledger.sqlite --confirm
```

### 5. Reconcile + retire satellites non-destructively

status: read_only_diff_completed_fold_archive_operator_pending

implementation:

- Added scripts/reconcile_knowledge_satellites.py.
- It is read-only and classifies tables as already_present, unique_fold_in, or separate_concern.
- No satellite was moved/deleted.

reconciliation summary:

| satellite | size_bytes | tables | already_present | unique_fold_in | separate_concern |
|---|---:|---:|---:|---:|---:|
| /home/openclaw/system_catalog.sqlite3 | 94208 | 3 | 0 | 3 | 0 |
| /home/openclaw/generated/system_knowledge/openclaw_system_knowledge_registry.sqlite | 122880 | 12 | 0 | 11 | 1 |
| /home/openclaw/generated/system_knowledge/operator_controller_event_router.sqlite | 1466368 | 5 | 0 | 5 | 0 |
| /home/openclaw/generated/system_knowledge/proof_to_response_runtime.sqlite | 995328 | 6 | 0 | 6 | 0 |
| /home/openclaw/generated/system_knowledge/sqlite_governance_registry.sqlite | 983040 | 3 | 0 | 3 | 0 |
| /home/openclaw/generated/system_knowledge/agentic_chain_inspector.sqlite | 888832 | 4 | 0 | 4 | 0 |
| /mnt/e/openclaw/generated/read_models/openclaw_filesystem_atlas.sqlite | 2699264 | 9 | 0 | 9 | 0 |

notable table classifications:

- system_catalog.sqlite3: repos/scans/skills are unique_fold_in.
- openclaw_system_knowledge_registry.sqlite: build_task is separate_concern; semantic/system tables are unique_fold_in.
- filesystem_atlas.sqlite: atlas_runs, directory_inventory, graph_edges, graph_nodes, inventory_roots, map_room_territories, move_candidates, repo_inventory are unique_fold_in.

operator archive command after fold+verify:

```bash
mkdir -p /home/openclaw/.openclaw/archive/knowledge_satellites/$(date -u +%Y%m%dT%H%M%SZ)
mv /home/openclaw/system_catalog.sqlite3 /home/openclaw/.openclaw/archive/knowledge_satellites/$(date -u +%Y%m%dT%H%M%SZ)/
mv /home/openclaw/generated/system_knowledge/openclaw_system_knowledge_registry.sqlite /home/openclaw/.openclaw/archive/knowledge_satellites/$(date -u +%Y%m%dT%H%M%SZ)/
mv /home/openclaw/generated/system_knowledge/operator_controller_event_router.sqlite /home/openclaw/.openclaw/archive/knowledge_satellites/$(date -u +%Y%m%dT%H%M%SZ)/
mv /home/openclaw/generated/system_knowledge/proof_to_response_runtime.sqlite /home/openclaw/.openclaw/archive/knowledge_satellites/$(date -u +%Y%m%dT%H%M%SZ)/
mv /home/openclaw/generated/system_knowledge/sqlite_governance_registry.sqlite /home/openclaw/.openclaw/archive/knowledge_satellites/$(date -u +%Y%m%dT%H%M%SZ)/
mv /home/openclaw/generated/system_knowledge/agentic_chain_inspector.sqlite /home/openclaw/.openclaw/archive/knowledge_satellites/$(date -u +%Y%m%dT%H%M%SZ)/
mv /mnt/e/openclaw/generated/read_models/openclaw_filesystem_atlas.sqlite /home/openclaw/.openclaw/archive/knowledge_satellites/$(date -u +%Y%m%dT%H%M%SZ)/
```

Note: run only after unique data is folded into ledger and verified queryable.

### 6. Hermes inventory from ledger

status: completed

implementation:

- Added scripts/export_hermes_inventory_from_ledger.py.
- Regenerated sidecars/hermes_home/OPENCLAW_INVENTORY.md from /home/openclaw/.openclaw/business_ops/ledger.sqlite.
- The generated inventory names the ledger and does not direct Hermes to system_catalog.sqlite3.

live exporter output:

```text
wrote sidecars/hermes_home/OPENCLAW_INVENTORY.md from /home/openclaw/.openclaw/business_ops/ledger.sqlite (6502 bytes)
```

inventory ledger counts:

- corpus_paths: 59073
- file_inventory: 3326
- canonical_facts: 104
- agent_runtime_components: 48
- agent_lanes: 7
- module_registry_modules: 17
- context_packet_items: 90

### 7. Governance + cleanup

status: helper_completed_live_write_operator_pending

implementation:

- Extended sqlite_governance_registry.py with knowledge_sqlite_policies and record_one_knowledge_ledger_policy().
- Helper is gated: confirm=False returns an operator command and writes nothing.

operator governance command:

```bash
python3 - <<'PY'
from pathlib import Path
from sqlite_governance_registry import record_one_knowledge_ledger_policy
print(record_one_knowledge_ledger_policy(
    registry_sqlite_path=Path('/home/openclaw/generated/system_knowledge/sqlite_governance_registry.sqlite'),
    ledger_path=Path('/home/openclaw/.openclaw/business_ops/ledger.sqlite'),
    confirm=True,
))
PY
```

cleanup audit:

- /home/openclaw/.openclaw/business_ops/ledger.sqlite.bak.fin exists, 666136576 bytes.
- .openclaw/tmp/pytest-*/ledger.sqlite copies found: 0.

operator cleanup command:

```bash
mkdir -p /home/openclaw/.openclaw/business_ops/backups/manual_archive_$(date -u +%Y%m%dT%H%M%SZ)
mv /home/openclaw/.openclaw/business_ops/ledger.sqlite.bak.fin /home/openclaw/.openclaw/business_ops/backups/manual_archive_$(date -u +%Y%m%dT%H%M%SZ)/
find /home/openclaw/.openclaw/tmp -path '*/pytest-*/ledger.sqlite' -type f -print -delete
```

## Tests

failing tests written first:

- tests/test_context_source.py
- tests/test_context_packet_ledger_contract.py
- tests/test_one_knowledge_ledger_tools.py

red run:

```text
6 failed: missing context_source, context_packet_builder_registry, ingest/reconcile scripts.
1 failed: missing export_hermes_inventory_from_ledger.
1 failed: missing record_one_knowledge_ledger_policy.
```

green runs:

```text
OPENCLAW_TEST_MODE=1 python3 -m pytest -q tests/test_context_source.py tests/test_context_packet_ledger_contract.py tests/test_one_knowledge_ledger_tools.py
8 passed in 1.61s
```

```text
OPENCLAW_TEST_MODE=1 python3 -m pytest -q tests/test_maestro_brain_packet.py tests/test_packet_sqlite_flip.py tests/test_cassandra_grounding.py tests/test_hermes_context_packet_grounding.py tests/test_guardian_approval_posture_grounding.py tests/test_backend_knowledge_packet.py tests/test_cassandra_clara_fact_packet.py
132 passed in 14.83s
```

```text
OPENCLAW_TEST_MODE=1 python3 -m pytest -q tests/test_context_source.py tests/test_context_packet_ledger_contract.py tests/test_one_knowledge_ledger_tools.py tests/test_maestro_brain_packet.py tests/test_packet_sqlite_flip.py tests/test_cassandra_grounding.py tests/test_hermes_context_packet_grounding.py tests/test_guardian_approval_posture_grounding.py tests/test_backend_knowledge_packet.py tests/test_cassandra_clara_fact_packet.py
140 passed in 21.96s
```

syntax:

```text
python3 -m py_compile context_source.py context_packet_builder_registry.py maestro_context_packet.py cassandra_context_packet.py hermes_context_packet.py guardian_context_packet.py backend_knowledge_packet.py cassandra_clara_fact_packet.py sqlite_governance_registry.py scripts/ingest_system_catalog_to_ledger.py scripts/reconcile_knowledge_satellites.py scripts/export_hermes_inventory_from_ledger.py
pass
```

## Live Verification

packet-builder live probe:

```text
maestro: status=READY fact_count=16 ledger_provenance=True
  packet_id=maestro_context_packet:d748921af3a272ae
  ledger_path=/home/openclaw/.openclaw/business_ops/ledger.sqlite
  source_refs_sample=['/mnt/e/openclaw/orchestration/OPERATOR-TRUTH-20260619-evening.md', 'generated/read_models/agent_presence.json', 'generated/read_models/openclaw_capability_index.json']
cassandra: status=READY fact_count=20 ledger_provenance=True
  packet_id=cassandra_context_packet:ecddcd64b2f69e47
  ledger_path=/home/openclaw/.openclaw/business_ops/ledger.sqlite
  source_refs_sample=['generated/read_models/cassandra_email_calendar_delta_detangle.json', 'generated/read_models/cassandra_runtime_wiring_audit.json', 'generated/read_models/agent_presence.json']
hermes: status=READY fact_count=19 ledger_provenance=True
  packet_id=hermes_context_packet:2716647175d1b1ee
  ledger_path=/home/openclaw/.openclaw/business_ops/ledger.sqlite
  source_refs_sample=['agent_lane_registry.DEFAULT_AGENT_LANE_SEEDS', 'openclaw_hermes_gateway_policy', 'hermes_advisory_packet']
guardian: status=READY fact_count=10 ledger_provenance=True
  packet_id=guardian_context_packet:5245b943fde26854
  ledger_path=/home/openclaw/.openclaw/business_ops/ledger.sqlite
  source_refs_sample=['generated/read_models/guardian_approval_posture.json', 'generated/read_models/guardian_hitl_authority_reconciliation.json', 'generated/read_models/guardian_hitl_sqlite_authority_contract.json']
backend: status=READY fact_count=12 ledger_provenance=True
  packet_id=backend_knowledge_packet:5a6135e0bd72969c
  ledger_path=/home/openclaw/.openclaw/business_ops/ledger.sqlite
  source_refs_sample=['ledger:/home/openclaw/.openclaw/business_ops/ledger.sqlite#agent_lanes:cassandra', 'ledger:/home/openclaw/.openclaw/business_ops/ledger.sqlite', 'ledger:/home/openclaw/.openclaw/business_ops/ledger.sqlite#agent_lanes:chief']
cassandra_clara: status=READY fact_count=46 ledger_provenance=True
  packet_id=finance_capital_hilton_invoice_packet_v0
  ledger_path=/home/openclaw/.openclaw/business_ops/ledger.sqlite
  source_refs_sample=[]
```

direct ledger query:

```text
repo roots: 7 corpus_roots + 1 repo_b_roots sampled
components: agent_runtime_components sampled, count 48
capabilities/modules: module_registry_modules sampled, count 17
files: corpus_paths count 59073; file_inventory count 3326
canonical_facts count 104
agent_lanes count 7
```

freshness note:

- The ledger has deep corpus/file counts, but a query for newly added packet files only found older indexed packet material. A corpus refresh is therefore still operator-pending with the ingest/write commands above.

## Before/After Sizes

No self-approved prod-state write was run. The live ledger is actively written by existing OpenClaw services, so size may drift independently of this Codex run.

| path | size_bytes_after |
|---|---:|
| /home/openclaw/.openclaw/business_ops/ledger.sqlite | 678604800 |
| /home/openclaw/system_catalog.sqlite3 | 94208 |
| /home/openclaw/generated/system_knowledge/openclaw_system_knowledge_registry.sqlite | 122880 |
| /home/openclaw/generated/system_knowledge/operator_controller_event_router.sqlite | 1466368 |
| /home/openclaw/generated/system_knowledge/proof_to_response_runtime.sqlite | 995328 |
| /home/openclaw/generated/system_knowledge/sqlite_governance_registry.sqlite | 983040 |
| /home/openclaw/generated/system_knowledge/agentic_chain_inspector.sqlite | 888832 |
| /mnt/e/openclaw/generated/read_models/openclaw_filesystem_atlas.sqlite | 2699264 |

## Blocked / Operator Pending

- Backup live ledger before any write.
- Run system_catalog ingest with --confirm.
- Fold unique satellite data into ledger tables, verify queryability, then archive satellites.
- Record one-knowledge-ledger policy in the live sqlite_governance_registry.sqlite with confirm=True.
- Archive ledger.sqlite.bak.fin.
- No pytest ledger copies were found to delete.

No push performed.

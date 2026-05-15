# OpenClaw Repo B Runtime Intake v0

Repo B Runtime Intake maps the legacy `openclaw-runtime` repository into OpenClaw Core as a metadata-only, non-canonical source.

It exists to reduce operator burden. Older runtime code should not have to live in the operator's memory as "maybe useful, maybe dangerous." This intake makes it queryable, classifies likely value, and preserves the boundaries needed before anything is ported, wrapped, promoted, or blocked.

## Source

- Canonical core repo: `/home/openclaw`
- Quarantined Repo B path: `/home/openclaw_external/openclaw-runtime`
- Expected remote: `WinshipWheatley/openclaw-runtime`
- Current posture: `non_canonical_until_promoted`
- Import posture: `metadata_scanned_only`

Repo B code is not run by this lane.

## What It Records

The intake records file metadata, safe hashes for small safe files, bounded classification snippets only where safe, startup script references, agent/runtime surfaces, safety findings, module candidates, future-home candidates, and burden-reduction categories.

Every row preserves:

- `source_repo=openclaw-runtime`
- source remote, branch, and commit
- `canonical_status=non_canonical_until_promoted`
- `import_status=metadata_scanned_only`
- `execution_allowed=false`
- `promotion_required=true`
- a burden-reduction category where determinable
- a future-home candidate such as core, module, client, personal, reference, blocked, or unknown

## Boundaries

- No Repo B Python or shell script execution.
- No env sourcing.
- No secret, token, credential, key, private, legal, tax, finance, client, SQLite, or database raw content reads.
- No service starts or restarts.
- No Telegram, Gmail, API, model, Docker, Ollama, SSH, SCP, or rsync behavior.
- No file moves, deletes, renames, merges, module copying, promotions, client repo generation, or Mission Control changes.

Startup scripts such as `start_chief.sh`, `start_openclaw_brains.sh`, and `loop_supervisor.sh` are classified as legacy runtime risks until reviewed and wrapped in current Operator Action / Agent Presence recovery policy.

## Classification Axes

Agent hints:

- `chief`
- `cassandra`
- `guardian`
- `niles`
- `hermes`
- `report_bridge`
- `producer`
- `unknown`

Surface kinds include runtime listeners, Telegram listeners, watchers, workers, schedulers, approval bridges, approval policy, session managers, file I/O, notification senders, memory/state workers, dashboards, orchestrators, polish-loop surfaces, skill loaders, budget/finance helpers, music/album helpers, website/marketing surfaces, HITL approval, PII vault, Google access, and unknown.

Reconciliation classifications include:

- `current_equivalent_exists`
- `candidate_to_port`
- `candidate_to_wrap`
- `legacy_runtime_risk`
- `docs_only`
- `task_backlog_candidate`
- `superseded_candidate`
- `client_product_candidate`
- `module_registry_candidate`
- `needs_operator_review`
- `blocked_no_go`
- `local_only_sensitive`
- `unknown_review`

Future architectural roles include:

- `core_module_candidate`
- `reusable_module_candidate`
- `client_template_candidate`
- `runtime_service_candidate`
- `report_bridge_component_candidate`
- `context_pack_component_candidate`
- `security_guardrail_candidate`
- `personal_only_candidate`
- `no_go_candidate`
- `unknown_review`

Burden-reduction categories:

- `reduces_build_burden`
- `reduces_finance_burden`
- `reduces_music_burden`
- `reduces_client_delivery_burden`
- `reduces_system_maintenance_burden`
- `mainly_reference`
- `unknown`

## Commands

Build intake:

```bash
python3 scripts/build_repo_b_runtime_intake.py --format operator
```

Query:

```bash
python3 scripts/query_repo_b_runtime_intake.py --report summary --format operator
python3 scripts/query_repo_b_runtime_intake.py --report agents --format operator
python3 scripts/query_repo_b_runtime_intake.py --report startup --format operator
python3 scripts/query_repo_b_runtime_intake.py --report risks --format operator
python3 scripts/query_repo_b_runtime_intake.py --report module-candidates --format operator
python3 scripts/query_repo_b_runtime_intake.py --report client-candidates --format operator
python3 scripts/query_repo_b_runtime_intake.py --report burden-reduction --format operator
python3 scripts/query_repo_b_runtime_intake.py --report finance-candidates --format operator
python3 scripts/query_repo_b_runtime_intake.py --report music-candidates --format operator
python3 scripts/query_repo_b_runtime_intake.py --agent cassandra --format operator
python3 scripts/query_repo_b_runtime_intake.py --agent chief --format operator
```

Export read-model:

```bash
python3 scripts/export_repo_b_runtime_intake_read_model.py --format operator
```

Generated read-models:

- `generated/read_models/repo_b_runtime_intake.json`
- `generated/read_models/repo_b_runtime_intake_OPERATOR.md`

## How This Makes the Operator Freer

This lane turns a mentally tracked legacy runtime repo into structured evidence. Instead of remembering whether Cassandra, Chief startup scripts, finance helpers, album helpers, approval bridges, or PII/HITL code exist somewhere in Repo B, the operator can query the map and decide what matters.

The first useful follow-up lanes should be:

1. `Finance Invoice Helper Reconciliation v0`
2. `Niles Music Runtime Candidate Review v0`
3. `Agent Runtime Reconciliation v0`
4. `Guardian HITL Security Reconciliation v0`
5. `Client Template Candidate Review v0`

No follow-up lane should port or execute Repo B code without explicit operator approval and current OpenClaw receipts.

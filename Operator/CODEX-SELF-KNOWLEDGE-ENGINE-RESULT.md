# CODEX Self-Knowledge Engine Result

Date: 2026-07-01
Branch/worktree: `codex/fail-closed-sweep-20260701` in `/tmp/openclaw-failclosed-20260701`

## Status

PARTIAL: safe seed crawler implemented. This is not the full perpetual daemon.

Implemented:

- Read-only filesystem crumb crawler (`self_knowledge_crawler.py`)
- Deterministic file metadata: absolute path, relative path, size, sha256
- Default exclusions for secrets, `.openclaw`, generated state, worktrees, sidecars, private corpora, venvs, node_modules, and tool temp files
- Bounded crawl budget via `max_files`
- Read-only SQLite ledger path inventory lookup from known inventory tables
- Ground-truth vs ledger diff that reports unknown files
- Missing ledger returns `ledger_unavailable` instead of a false green

Not enabled:

- No production ledger writes.
- No daemon/cron/systemd watcher.
- No local model enrichment.
- No Gemini frontier handoff.
- No self-governance scheduler.

## Files Changed

- `self_knowledge_crawler.py`
- `tests/test_self_knowledge_crawler.py`
- `Operator/CODEX-SELF-KNOWLEDGE-ENGINE-RESULT.md`

## Tests

Red-first proof:

- `tests/test_self_knowledge_crawler.py` failed before `self_knowledge_crawler.py` existed.
- The vault-wall expansion failed until `.chief.env*`, `.claude*`, `.openclaw`, and private-corpus exclusions were added.

Passing verification:

```text
python3 -m pytest tests/test_self_knowledge_crawler.py -q
5 passed in 0.11s
```

Bounded real read-only probe:

```text
python3 - <<'PY'
from self_knowledge_crawler import diff_filesystem_against_ledger
from pathlib import Path
result = diff_filesystem_against_ledger(Path('/home/openclaw'), Path('/home/openclaw/.openclaw/business_ops/ledger.sqlite'), max_files=200)
print('status', result['status'])
print('counts', result['counts'])
print('first_unknown', [c['relative_path'] for c in result['unknown_files'][:10]])
PY
```

Output:

```text
status gaps_found
counts {'filesystem_files': 200, 'ledger_known_paths': 5296, 'unknown_files': 118}
first_unknown ['.hitl_pending.lock', 'CASSANDRA_MIGRATION_MAP.md', 'CHIEF_DELETION_NOTEBOOK.md', 'THREE-COMPONENT-SPEC.md', 'action_runtime.py', 'activation_gate_register.py', 'active_machinery_classification_orchestrator.py', 'active_machinery_gemini_verification.py', 'active_machinery_high_risk_quarantine.py', 'active_machinery_operator_disposition.py']
```

The initial full-root unbounded probe was stopped because it attempted to enumerate/sort too much state. The crawler was then corrected to stream with `os.walk`, prune excluded directories before descent, and support `max_files`.

## Next Required P6 Work

1. Add a ledger write adapter that records crawler metadata into the business-ops ledger, gated by `--confirm` and preceded by a backup.
2. Add a scheduler that uses the GPU arbiter/router so crawling yields to interactive agents.
3. Add incremental state so repeated crawls avoid rehashing unchanged files.
4. Add process/cron/systemd/port/database enumerators.
5. Add Gemini frontier handoff and local verification of Gemini-discovered edges.

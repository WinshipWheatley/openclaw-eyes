# CODEX Resource-Aware Model Orchestration Result

Date: 2026-07-01
Branch/worktree: `codex/fail-closed-sweep-20260701` in `/tmp/openclaw-failclosed-20260701`

## Status

PARTIAL: Component 1 from the build order is implemented.

Implemented:

- GPU arbiter lease primitive (`polish_loop/gpu_arbiter.py`)
- Durable SQLite table `gpu_resource_leases`
- Build lease acquisition
- Interactive preemption of build lease
- Recommended preemption plan (`recommended_keep_alive=0`) without executing live unloads
- Build denial while interactive lease is active
- TTL/expired lease reclaim
- Heartbeat lease extension
- Nonce-checked release

Not enabled:

- Continuous polish-loop building remains off.
- No live model unloads are executed by the arbiter.
- No service restart was performed for this component.
- Capability/availability router, self-repair wiring, harness-first diagnosis integration, and build lifecycle registry are still pending.

## Files Changed

- `polish_loop/gpu_arbiter.py`
- `tests/test_gpu_arbiter.py`
- `Operator/CODEX-RESOURCE-ORCHESTRATION-RESULT.md`

## Tests

Red-first proof:

- `tests/test_gpu_arbiter.py` failed before `polish_loop.gpu_arbiter` existed.

Passing verification:

```text
python3 -m pytest tests/test_gpu_arbiter.py -q
6 passed in 0.36s
```

```text
python3 -m pytest tests/test_polish_loop_file_ledger_reconciliation.py tests/test_polish_loop_closure_bridge.py tests/test_polish_loop_task_package_materialization.py tests/test_gpu_arbiter.py -q
32 passed in 3.52s
```

## Next Required P5 Work

1. Wire polish-loop builder admission to request a build lease before starting local model work.
2. Wire interactive front-door/listener paths to acquire/heartbeat/release interactive leases.
3. Add a non-destructive unload adapter that can send `keep_alive=0` only between build units.
4. Build the capability/availability router on top of this lease state and existing quota/model fit signals.

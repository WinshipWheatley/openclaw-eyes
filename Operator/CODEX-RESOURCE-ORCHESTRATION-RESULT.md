# CODEX Resource-Aware Model Orchestration Result

Date: 2026-07-01
Branch/worktree: `codex/fail-closed-sweep-20260701` in `/tmp/openclaw-failclosed-20260701`

## Status

PARTIAL: Components 1 and 2 from the build order now have bounded primitives.

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
- Same-holder reacquire renews the existing lease
- Capability/availability router primitive (`polish_loop/capability_availability_router.py`)
- Local-first build routing when the GPU is idle
- Honest build deferral while an interactive agent holds the GPU lease
- Cloud blocked unless the task is explicitly safe and headroom is known available
- Quota/rate-limit builder output falls back to local when possible
- No-capability state defers honestly instead of silently stalling

Not enabled:

- Continuous polish-loop building remains off.
- No live model unloads are executed by the arbiter.
- No service restart was performed for this component.
- The capability router is not wired into the live builder launcher yet.
- Self-repair wiring, harness-first diagnosis integration, and build lifecycle registry are still pending.

## Files Changed

- `polish_loop/gpu_arbiter.py`
- `polish_loop/capability_availability_router.py`
- `tests/test_gpu_arbiter.py`
- `tests/test_capability_availability_router.py`
- `Operator/CODEX-RESOURCE-ORCHESTRATION-RESULT.md`

## Tests

Red-first proof:

- `tests/test_gpu_arbiter.py` failed before `polish_loop.gpu_arbiter` existed.

Passing verification:

```text
python3 -m pytest tests/test_gpu_arbiter.py -q
7 passed
```

```text
python3 -m pytest tests/test_capability_availability_router.py -q
5 passed in 0.23s
```

```text
python3 -m pytest tests/test_polish_loop_file_ledger_reconciliation.py tests/test_polish_loop_closure_bridge.py tests/test_polish_loop_task_package_materialization.py tests/test_gpu_arbiter.py -q
32 passed in 3.52s
```

```text
python3 -m pytest tests/test_gpu_arbiter.py tests/test_capability_availability_router.py tests/test_runner_cloud_policy.py tests/test_runner_headroom_fail_closed.py tests/test_builder_fallback.py tests/test_chief_llm_router.py tests/test_frontdoor_model_profile.py -q
168 passed in 2.47s
```

## Next Required P5 Work

1. Wire polish-loop builder admission to request a build lease before starting local model work.
2. Wire interactive front-door/listener paths to acquire/heartbeat/release interactive leases.
3. Add a non-destructive unload adapter that can send `keep_alive=0` only between build units.
4. Wire the capability/availability router into the builder launcher and deferred-reprocess queue.
5. Add the self-repair / harness-first diagnosis integration and ledger build-lifecycle registry.

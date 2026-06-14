# Test Engine Substrate Audit

## Phase 1: Target Discovery & Audit
Discovered tests are tracked in `test_engine_substrate_audit.json`.

## Phase 2: Architectural Substrate Design
Recommendation:
Use structured pytest as the core, with a small Python manifest/router layer around it.
This prioritizes low latency, strict isolation, no accidental model/provider invocation, PC/Mac separation, clear bridge validation, deterministic smoke routes, future distributed node routing, and receipt/read-model verification.

## Phase 3: Autonomous Routing & Execution Engine

### What to test:
- changed files
- changed generated read models
- changed bridge artifacts
- changed package/compiler/router/model-boundary code
- stale receipts
- failed previous validation

### Where to test:
- PC node for backend, SQLite, package compiler, proof-to-response, local model runtime boundaries
- Mac cockpit for SwiftUI, controller shell, composer, proof-to-response promotion, release build
- bridge for read-model equality and response handoff

### When to test:
- smoke on service/node boot
- unit on file save or local commit
- integration before model/worker approval
- regression before release or after harness changes

## Phase 4: Output Contract
Proposed directory tree:
```
tests/
  substrate/
    manifest/
      test_manifest.schema.json
      test_manifest.json
    discovery/
    routing/
    runners/
      pc_node_runner.py
      mac_cockpit_runner.py
      bridge_runner.py
      local_model_boundary_runner.py
    reports/
    fixtures/
    policies/
    README.md
```

Manifest schema must include:
- test_id
- path
- type
- environment
- owner_subsystem
- dependencies
- command
- safe_to_run_by_default
- requires_model_runtime
- invokes_model
- invokes_external_provider
- mutates_business_state
- mutates_files
- uses_bridge
- expected_artifacts
- timeout_seconds
- last_status
- last_run_at
- receipt_refs
- failure_class
- rerun_policy

Rules:
- No test may invoke models unless explicitly marked and approved.
- No test may touch external providers.
- No test may mutate business systems.
- Mac tests must be separable from PC tests.
- Bridge tests must verify local/bridge equality.
- Future Test Engine must be manifest-driven and receipt-backed.

Notes:
- Model-runtime tests are not safe by default.
- Protected/external actions are false by default.

# CODEX Fail-Closed Sweep Result

Date: 2026-07-01
Branch/worktree: `codex/fail-closed-sweep-20260701` in `/tmp/openclaw-failclosed-20260701`
Base: `origin/codex/stress-fixes`

## Status

PASS for Priority 2 scoped sweep. I found and fixed four concrete fail-open controls, all with red-first regression tests:

1. Front-door Stage-1 validation unavailable delivered unchecked model text.
2. Chief approval HMAC allowed partial hash states to pass.
3. Autonomous runner headroom/registry/budget failures selected cloud runners.
4. Runner command construction defaulted unknown runners to Codex.

## Files Changed

- `protected_generate.py`
- `chief_approval_brain.py`
- `runner_profiles.py`
- `tests/test_frontdoor_model_profile.py`
- `tests/test_chief_approval_hash_fail_closed.py`
- `tests/test_runner_headroom_fail_closed.py`
- `tests/test_runner_cloud_policy.py`
- `Operator/CODEX-FAIL-OPEN-SWEEP-RESULT.md`

## Fixes

### 1. Front-door Stage-1 validator

Before: `_stage1_validate()` returned `(True, False, ())` when the machine-contract leak validator could not import or crashed. For `done_reason=stop`, that was treated as `model_ok`, so a live model answer could be delivered without the safety validator.

After: when front-door profile is active and validation is unavailable, the model output is discarded and the receipt records `model_fallback_reason=validation_unavailable` plus `validation_unavailable=true`. Existing `done_reason=length` behavior remains fail-closed as `truncated`.

### 2. Chief approval HMAC

Before: `_verify_hash()` returned true when the stored hash was missing or when the stored hash existed but the secret was unavailable. The caller also skipped verification entirely when the stored hash field was removed.

After: fully disabled legacy mode is still allowed only when no secret and no stored hash exist. Partial states now deny:

- secret configured + stored hash missing -> deny
- stored hash present + secret missing -> deny
- stored hash mismatch -> deny

The approval polling path now always calls `_verify_hash()`.

### 3. Runner headroom / budget / registry

Before: missing headroom policy, missing provider, headroom probe error, unavailable provider headroom, registry failure/empty, or missing budget tracker could pass through to cloud runners (`codex`, `gemini`, `aider`).

After: those unknown/error states fail closed to local `ollama`/`chief-fast:latest` or skip the cloud candidate so normal selection lands on local. Explicit local policies remain allowed. Explicit `passthrough_to_budget_zone` remains unchanged because it is an explicit configured policy, not missing/error telemetry.

### 4. Runner command construction

Before: `_build_invoke_cmd()` defaulted unknown/unpatterned runners to `codex exec`.

After: unknown/unpatterned runners and registry-missing `ollama` command construction fail closed to the local builder (`polish_loop/local_builder.py`).

## Tests

Red-first proof:

- `tests/test_frontdoor_model_profile.py::test_pgwr_frontdoor_validator_unavailable_fails_closed_for_stop` failed before the patch with `model_ok`.
- `tests/test_chief_approval_hash_fail_closed.py` first two tests failed before the patch.
- `tests/test_runner_headroom_fail_closed.py` failed all five tests before the patch.
- New runner fallback tests failed before the patch on Codex fallback.

Passing verification:

```text
python3 -m pytest tests/test_pytest_sandbox_dir_fd_failclosed.py tests/test_frontdoor_model_profile.py tests/test_protected_generate.py tests/test_chief_approval_hash_fail_closed.py tests/test_runner_cloud_policy.py tests/test_runner_headroom_fail_closed.py -q
94 passed in 1.38s
```

```text
python3 -m pytest tests/test_runner_cloud_policy.py tests/test_runner_headroom_fail_closed.py tests/test_builder_fallback.py tests/test_chief_llm_router.py tests/test_frontdoor_model_profile.py -q
153 passed in 1.62s
```

## Sweep Classifications

- `openclaw_pytest_sandbox.py` dir_fd sandbox bypass: already fixed on `codex/stress-fixes` before this branch; regression tests still pass.
- `chief_llm.py` “fail open” comments: inspected. Active lane candidates already resolve to fitting qwen/mistral/nemotron lanes in tests; no unsafe change made in this sweep.
- `headroom_routing_policy.json` `passthrough_to_budget_zone`: left unchanged as an explicit policy choice, not a missing/error control. Missing/error headroom now fails closed.
- Observational `except Exception: pass` paths in UI/status/reporting modules: classified as non-dangerous in this sweep unless they gate send/money/approval/cloud/sandbox/model-output delivery.
- `polish_loop/orchestrator.py` “assume running” process status fallback: deferred. It is operational-status semantics, not a send/money/cloud/sandbox control. Should be revisited under resource/GPU arbiter work.

## Remaining Recommendation

Add a static fail-open detector as a future enforcement layer, as described in `Operator/FAIL-CLOSED-INVARIANT-SPEC.md`, so new protective controls cannot reintroduce passthrough-on-error behavior.

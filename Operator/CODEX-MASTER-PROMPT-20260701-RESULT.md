# CODEX Master Prompt 20260701 Result

Date: 2026-07-01
Worktree: `/tmp/openclaw-failclosed-20260701`
Branch: `codex/fail-closed-sweep-20260701`
Base: `origin/codex/stress-fixes`

## Executive Status

Priority 1 is complete and promoted. The remaining priorities are implemented as bounded,
reviewable branch work. They are **not merged into `codex/stress-fixes` or live services yet**.

Branch commits:

```text
aa05e74d fix: fail closed on safety control uncertainty
836fff40 feat: make frontdoor answers freshness aware
94555b9a docs: record wsl popup task fix
0a31ac1e feat: add gpu lease arbiter primitive
e5d60c39 feat: add capability availability router primitive
bc92a918 feat: add self-knowledge crawler seed
```

## Priority 1 — Green-Gate + Promotion

Status: **PASS / COMPLETE**

Green-gate command:

```text
OPENCLAW_TRUSTED_TEST_REF=origin/codex/pc4-self-healing bash scripts/green_gate.sh codex/stress-fixes
```

Result:

```text
9411 passed, 14 skipped, 3 subtests passed in 1587.68s (0:26:27)
```

Promotion method:

```text
git checkout main
git merge --ff-only codex/stress-fixes
git push origin main
```

Push hook reran the clean-room gate on `9e2d09cd`:

```text
9411 passed, 14 skipped, 3 subtests passed in 1595.69s (0:26:35)
```

Final release state:

```text
main = origin/main = codex/stress-fixes = origin/codex/stress-fixes = 9e2d09cd9a61d7854490c4ac69d48953d44d3c64
```

No triage report was written because the trusted-ref clean-room gate was already green.

## Priority 2 — Fail-Closed Invariant Sweep

Status: **PASS for scoped sweep**
Report: `Operator/CODEX-FAIL-OPEN-SWEEP-RESULT.md`
Commit: `aa05e74d`

Fixed:

- Front-door Stage-1 validator unavailable now fails closed.
- Chief approval HMAC partial states now deny.
- Cloud/headroom/registry uncertainty now falls back to local.
- Unknown runner invocation now falls back to local builder, not Codex.

Tests:

```text
python3 -m pytest tests/test_pytest_sandbox_dir_fd_failclosed.py tests/test_frontdoor_model_profile.py tests/test_protected_generate.py tests/test_chief_approval_hash_fail_closed.py tests/test_runner_cloud_policy.py tests/test_runner_headroom_fail_closed.py -q
94 passed in 1.38s
```

```text
python3 -m pytest tests/test_runner_cloud_policy.py tests/test_runner_headroom_fail_closed.py tests/test_builder_fallback.py tests/test_chief_llm_router.py tests/test_frontdoor_model_profile.py -q
153 passed in 1.62s
```

## Priority 3 — Agent Freshness-Awareness

Status: **PARTIAL PASS / safe hardening landed**
Report: `Operator/CODEX-FRESHNESS-AWARENESS-RESULT.md`
Commit: `836fff40`

Fixed:

- Front-door prompt includes freshness tags from `freshness.as_of`.
- Stale facts are marked `stale-needs-refresh`.
- Receipts include `stale_fact_ids`.
- Read-only packet read-model freshness audit utility added.

Real audit:

```text
25 packet read-model sources
19 problems: 18 stale, 1 missing (reynolds_gig_setup_status.json)
```

Tests:

```text
python3 -m pytest tests/test_frontdoor_model_profile.py tests/test_protected_generate.py tests/test_read_model_freshness_audit.py -q
55 passed in 1.09s
```

Remaining: refreshing stale sources is not auto-mutated in this branch.

## Priority 4 — WSL Popup Fix

Status: **PASS for visible popup candidates**
Report: `Operator/CODEX-WSL-POPUP-FIX-RESULT.md`
Commit: `94555b9a`

Applied machine config:

- Corrected `OpenClaw-Sonnet-G2C005-20260625` from `Ubuntu` to `Ubuntu-E`.
- Set that task Hidden=true.
- Corrected disabled OpenClaw startup tasks to `Ubuntu-E` and Hidden=true.
- `Start-WSL-OpenClaw` already targeted `Ubuntu-E`; Hidden=true could not be applied due stored Windows password mismatch (`0x8007052e`).

## Priority 5 — Resource-Aware Model Orchestration

Status: **PARTIAL / components 1-2 primitives**
Report: `Operator/CODEX-RESOURCE-ORCHESTRATION-RESULT.md`
Commits: `0a31ac1e`, `e5d60c39`

Built:

- SQLite-backed GPU lease arbiter.
- Interactive preemption plan (`recommended_keep_alive=0`) without executing live unloads.
- TTL, heartbeat, nonce-checked release.
- Capability router primitive: local-first, defer while interactive GPU lease active, cloud only when explicit and available, quota output falls back local.

Tests:

```text
python3 -m pytest tests/test_gpu_arbiter.py tests/test_capability_availability_router.py tests/test_runner_cloud_policy.py tests/test_runner_headroom_fail_closed.py tests/test_builder_fallback.py tests/test_chief_llm_router.py tests/test_frontdoor_model_profile.py -q
168 passed in 2.47s
```

Remaining:

- Wire builder launcher to acquire GPU leases.
- Wire listeners/front-door to heartbeat/release interactive leases.
- Add live unload adapter between build units.
- Wire router into deferred-reprocess.
- Build lifecycle registry and harness-first self-repair integration.

## Priority 6 — Perpetual Self-Knowledge Engine

Status: **PARTIAL / safe seed crawler**
Report: `Operator/CODEX-SELF-KNOWLEDGE-ENGINE-RESULT.md`
Commit: `bc92a918`

Built:

- Read-only filesystem crumb crawler.
- Secret/private/generated exclusions.
- Bounded `max_files` crawl budget.
- Read-only ledger path diff against known inventory tables.
- Missing ledger fails honest (`ledger_unavailable`).

Tests:

```text
python3 -m pytest tests/test_self_knowledge_crawler.py -q
5 passed in 0.11s
```

Bounded real read-only probe:

```text
status gaps_found
counts {'filesystem_files': 200, 'ledger_known_paths': 5296, 'unknown_files': 118}
```

Remaining:

- Gated ledger writer (`--confirm`, backup first).
- Incremental crawl state.
- Process/cron/systemd/port/database enumerators.
- Scheduler integration with the GPU arbiter.
- Gemini frontier handoff and local verification.

## Final Verification

Combined relevant suite:

```text
python3 -m pytest tests/test_self_knowledge_crawler.py tests/test_gpu_arbiter.py tests/test_capability_availability_router.py tests/test_frontdoor_model_profile.py tests/test_protected_generate.py tests/test_chief_approval_hash_fail_closed.py tests/test_runner_cloud_policy.py tests/test_runner_headroom_fail_closed.py tests/test_builder_fallback.py tests/test_chief_llm_router.py tests/test_read_model_freshness_audit.py -q
181 passed in 2.88s
```

## What Is Still Needed

1. Review and merge `codex/fail-closed-sweep-20260701` into `codex/stress-fixes`.
2. Run the full clean-room green-gate again after merge.
3. Restart relevant services only after the merged code is accepted.
4. Continue Priority 5 wiring and Priority 6 daemon/ledger-write work as separate gated builds.

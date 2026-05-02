# Next Implementation Sequence

Status: docs-only sequence. This file does not authorize implementation beyond future prompts.

Freshness:

- Generated/reviewed: 2026-05-02
- Source commit at creation: `e06b7ae`
- Package commit: `TBD_AFTER_COMMIT`
- Source basis: Launch Ladder package, validation map, source-set scripts, modular readiness ledger, service freeze, Hermes advisory contract.
- Stale when: this package is committed under a new hash, validation map changes, or any proposed next slice is completed.
- Refresh trigger: update after each accepted slice and before recommending compact route buttons.

## Smallest Safe Sequence

1. Commit this docs-only Launch Ladder package.
2. Add `.gitignore` allowlist entries for `docs/planning/launch_ladder/**/*.md` only if the operator wants normal tracked adds instead of `git add -f`.
3. Add static Launch Ladder data-contract docs or schemas for records named in the app brief.
4. Add static tests/checker for Launch Ladder docs and future source-set counts.
5. Add generator spec before generator code.
6. Add generator code only after the spec and tests exist.
7. Generate source sets only after the generator is validated.
8. Create read-only app mock fixtures.
9. Route a Codex Desktop Mac app build from the app-specific source set.

The Multi-OpenClaw Command Atlas should stay a long-range horizon until the v1 Launch Ladder proof is committed and statically checked. Do not skip from this package to a multi-deployment app or registry without first defining data contracts, freshness rules, authority boundaries, and fixtures.

## Recommended Direct Route

Use when the operator wants the smallest safe next move after this package.

| Field | Value |
| --- | --- |
| `steps_to_launch` | 3 |
| `estimated_true_steps` | 7 |
| `includes` | commit docs package, define data-contract/schema slice, add static checker/tests. |
| `defers` | app fixtures, generator, backend schema. |
| `risk` | low |
| `confidence` | high |
| `freshness` | stale when package commit changes or validation map changes. |

## Recommended Balanced Route

Use when the operator wants source-set discipline and app/backend prep before UI build.

| Field | Value |
| --- | --- |
| `steps_to_launch` | 5 |
| `estimated_true_steps` | 10 |
| `includes` | docs package, data contracts, source-set generator spec, static checker/tests, mock fixture plan. |
| `defers` | actual generated ingest folders, Mac app build, live/runtime routes. |
| `risk` | medium |
| `confidence` | medium |
| `freshness` | stale when source-set files or route fields change. |

## Recommended System Route

Use when the operator wants a robust productization foundation before app work.

| Field | Value |
| --- | --- |
| `steps_to_launch` | 8 |
| `estimated_true_steps` | 14 |
| `includes` | docs package, data contracts, source-set generator spec/tests, app fixture plan, backend data-model plan, validation map entry, operator-trail spec, productization checklist. |
| `defers` | live service verification, provider/model execution, private-data workflows, app runtime integration, full Multi-OpenClaw Command Atlas registry/app. |
| `risk` | medium |
| `confidence` | medium |
| `freshness` | stale when any upstream control source changes. |

## Parallel Bundle Candidate

Potential future operator-approved bundle:

- Lane A: Launch Ladder data contracts.
- Lane B: source-set generator spec.
- Lane C: Mac/iOS mock fixture plan.
- Lane D: Multi-OpenClaw Command Atlas record-shape note for deployments, departments, launch goals, and evidence zoom levels.

This bundle is not ready until collisions, outputs, validation commands, commit boundaries, and stop conditions are explicit.

## Next Prompt Candidate

After this package is committed, the smallest safe implementation prompt is:

```text
Create a docs/test-only Launch Ladder static contract slice.

Read docs/planning/launch_ladder/*.md, docs/planning/OPENCLAW_MODULAR_READINESS_LEDGER.md, docs/testing/VALIDATION_MAP.md, and .gitignore.

Add a lightweight static checker/test that verifies Launch Ladder docs define the seven ladder stages, route compression fields, compact button fields, parallel bundle requirements, view modes, freshness fields, source-set 23+MANIFEST=24 rule, and non-authority warnings.

Also verify that the docs name the Multi-OpenClaw Command Atlas as a long-range horizon, define atlas zoom levels, state that Launch Ladders replace vague lanes as the operator-facing unit of work, and keep the v1 package docs/spec-only.

Do not edit runtime code, services, installers, launchers, schedulers, provider/model wiring, Gmail/Telegram behavior, Hermes runtime, .mcp.json, secrets, vaults, logs, private data, or Legal lane files.

Do not create generated ingest folders or generator scripts yet.

Validate with the new focused static test plus git diff --check and git status.
```

## Unresolved Ambiguity To Carry Forward

- Whether to update `.gitignore` for normal tracking or continue force-adding planning docs.
- Exact Mac/Codex project workspace path.
- Exact backend schema output path.
- Exact future app validation command.
- Whether operator-trail artifacts belong under `docs/operator_trail/` or a generated/artifact path outside canonical docs.
- Exact Multi-OpenClaw Command Atlas registry/data model and whether it starts as Markdown, JSON fixtures, or a static schema.

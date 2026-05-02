# Evidence And Freshness

Status: docs-only evidence/freshness model. This file does not create artifacts.

Freshness:

- Generated/reviewed: 2026-05-02
- Source commit at creation: `e06b7ae`
- Package commit: `TBD_AFTER_COMMIT`
- Source basis: validation map, service freeze, modular readiness ledger, intent/control map, existing ingest refresh scripts.
- Stale when: validation commands, source-set contents, module status, route outputs, or commit hash changes.
- Refresh trigger: update before any generated source set, app fixture, backend schema, or launch-ready claim.

## Evidence Rule

Every major Launch Ladder claim must cite at least one of:

- Canonical docs.
- Static tests.
- Commit hashes.
- Generated artifacts.
- Explicit checks.
- Approval/broker receipts.

If no evidence exists, the claim must be marked `planned`, `concept`, `unknown`, or `needs proof`.

## Freshness Record

Every map, source set, status card, route, compact button, parallel bundle, and evidence artifact should include:

| Field | Required meaning |
| --- | --- |
| `generated_at` | Timestamp when generated. |
| `reviewed_at` | Timestamp when human/agent reviewed. |
| `source_commit` | Commit hash used as source basis. |
| `package_commit` | Commit hash that contains the generated package, or `TBD_AFTER_COMMIT`. |
| `source_basis` | Explicit docs/tests/source files used. |
| `stale_conditions` | Conditions that invalidate the record. |
| `refresh_trigger` | What action should refresh it. |
| `withheld_surfaces` | Surfaces intentionally not read. |

## Evidence Reference Shape

Use this lightweight shape in future JSON/Markdown artifacts:

```text
evidence_ref:
  kind: doc | test | commit | artifact | check | approval
  path_or_id: string
  claim_supported: string
  freshness: current | stale | unknown
  limits: string
```

## Repo-Side Operator Trail

Suggested future path:

```text
docs/operator_trail/<launch_id>/
```

One human-readable artifact should be written per completed step in a future implementation. This package does not create that path.

Suggested files per launch trail:

- `00_RECOMMENDATION.md`
- `01_PLANNED_SLICE.md`
- `02_SOURCE_SET_READY.md`
- `03_BUILD_READY.md`
- `04_VALIDATION_READY.md`
- `05_LAUNCH_READY.md`
- `06_LAUNCH_AUTHORIZED.md`, only if authorization actually occurs.

Each artifact should include source commit, timestamp, route, stage, operator-visible summary, evidence refs, withheld surfaces, validation result, deferred work, and stop condition.

## Freshness Status Values

| Status | Meaning |
| --- | --- |
| `fresh` | Source commit matches current route/source-set basis and stale conditions are false. |
| `review_needed` | Source changed or enough time has passed that a human/agent review is needed. |
| `stale` | A stale condition is true; route cannot claim launch-ready. |
| `unknown` | The record lacks enough metadata to judge freshness. |

## Stale Conditions

A Launch Ladder record is stale if:

- Any source-basis file changes.
- The validation map changes for touched surfaces.
- The modular readiness ledger changes for a referenced module.
- A generated source set is older than its source commit.
- A route uses an approval/broker policy that has changed.
- A route references a workspace, machine, or client that has changed location or authority.
- A compact route hides deferred work or loses the North Star link.

## Do Not Do Yet

- Do not write operator trail artifacts until a later implementation slice defines the generator/checker.
- Do not treat copied ChatGPT Project files as evidence freshness by themselves.
- Do not claim live service or model freshness from static docs.

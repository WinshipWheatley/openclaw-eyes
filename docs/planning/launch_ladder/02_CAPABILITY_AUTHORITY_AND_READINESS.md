# Capability, Authority, And Readiness

Status: docs-only derived view. The modular readiness ledger is the upstream source of module readiness.

Freshness:

- Generated/reviewed: 2026-05-02
- Source commit at creation: `e06b7ae`
- Package commit: `TBD_AFTER_COMMIT`
- Source basis: `docs/planning/OPENCLAW_MODULAR_READINESS_LEDGER.md`, intent/control map, Google policy, model fallback policy, validation map.
- Stale when: any module's purpose, status, authority, data boundary, proof, dependency, or productization posture changes.
- Refresh trigger: update after modular ledger changes and before any app/backend route consumes readiness data.

## Rule

Capability is not authority. A module may technically be able to do something and still be forbidden, frozen, advisory-only, unproven, or pending approval.

## Status Vocabulary

Use the modular readiness ledger vocabulary:

- `concept`
- `static contract`
- `read-only proof`
- `dry-run proof`
- `bounded action`
- `production candidate`
- `frozen / do not expand`

## Authority Vocabulary

Use the modular readiness ledger vocabulary:

- `no authority / advisory only`
- `read-only`
- `proposal only`
- `approval gate`
- `broker-gated action`
- `bounded executor`
- `forbidden`

## Console Record Shape

Every capability card should expose:

| Field | Required meaning |
| --- | --- |
| `module_id` | Stable module key. |
| `module_name` | Human-readable name. |
| `purpose` | One-sentence job. |
| `current_status` | Ledger status value. |
| `authority_level` | Ledger authority value. |
| `data_allowed` | Explicit allowed data classes. |
| `data_withheld` | Explicit withheld surfaces. |
| `proof_refs` | Docs, tests, commits, artifacts, or checks. |
| `dependencies` | Required upstream modules or policies. |
| `next_safe_slice` | Smallest safe next step. |
| `do_not_do_yet` | Forbidden or premature actions. |
| `freshness` | generated/reviewed time, source commit, stale conditions, refresh trigger. |

## Derived Readiness Bands

| Band | Meaning | Example evidence |
| --- | --- | --- |
| `visible` | Module is named and bounded enough to show. | Ledger row or control-map row. |
| `selectable_for_planning` | Module can be included in route planning. | Purpose, authority, withheld surfaces, and next safe slice exist. |
| `selectable_for_build` | Module can support docs/test/backend/app implementation. | Validation map entry or explicit static contract exists. |
| `selectable_for_launch_ready` | Module has evidence/freshness/route/authority fields and validation plan. | Static tests, dry-run proof, or bounded action proof. |
| `selectable_for_launch_authorized` | Applicable approval/broker/operator path has granted authority for a specific action. | Approval receipt, broker gate, human decision, or Chief/Guardian path. |

## Initial Module Readiness Notes

- Core runtime law/canonical docs are production-candidate governance docs, not product runtime.
- Service-control SE kernel is static/read-only proof and explicitly not live service health.
- MCP progressive discovery has a hardened docs-read default and gated unlock profiles.
- Model routing has policy hardening, but model quality remains unproven until benchmarks.
- Cassandra has mixed bounded, dry-run, and planned behavior; broad autonomy is not ready.
- Hermes has static advisory packet contracts and remains non-canonical/advisory-only.
- Guardian is an approval gate, but routine chat confirmation must not replace required Tier 2 approval.
- Google broker is actor/capability/class gated; Gmail body and draft creation remain sensitive Class B paths.
- Legal/local discovery is deterministic/local-first; no external model path for real matters.
- Memory/retrieval substrate is still concept-level.
- Dashboard/operator reporting is planned/read-only and must not control services in the first version.
- Source-set/ChatGPT ingest workflow is derived and non-canonical.

## Open Ambiguities

- SMS/Telegram notification authority remains a decision area in the intent/control map.
- Planner-builder cloud runner rules remain approval/policy sensitive.
- Future live Cassandra/Gmail behavior requires separate design and approval.
- Live service state requires a later read-only verification plan before any command is run.

## Do Not Do Yet

- Do not infer authority from capability registry entries alone.
- Do not promote planned or concept modules to launch-ready without proof.
- Do not make an app button capable of hidden mutation because a module has a launcher or service path somewhere in source.

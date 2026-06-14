# OpenClaw LM Child Package Gate

- Readiness: `READY_FOR_CONTRACT_NOT_RUNTIME_SPAWNING`
- Contract status: `DETERMINISTIC_LM_CHILD_PACKAGE_GATE_CONTRACT_NO_RUNTIME_SWARMS`
- Runtime child spawning: `false`
- Swarm mode: `false`
- Live action authority default: `false`

## Package Gate Shape

- `lm_package` defines parent/child package scope, budget, authority, tests, outputs, and stop conditions.
- `child_spawn_policy` defines whether any child can be requested, plus max children, depth, and budget.
- `child_package_request` is the only visible request path for a child package.
- `package_receipt` is required before parent closure can rely on child work.
- `package_gate_decision` records allow/block/Guardian/operator/budget/authority outcomes.

## Child Spawn Policy

- Packages seeded: `5`
- Policies seeded: `5`
- Default policy: `max_children=0`, `max_depth=0`, `spawn_allowed=false`.
- Audit child: read-only inspection only.
- Test-writer child: test files only.
- Implementation child: Guardian required.
- Live-action child: forbidden.

## Guardian Requirements

- Guardian is required for implementation children and scope/authority escalation.
- Guardian approval does not grant live business action authority.
- Operator approval is separate and required only when a policy explicitly says so.

## Decisions

- `ALLOW`: `2`
- `AUTHORITY_DENIED`: `1`
- `BLOCK`: `2`
- `REQUIRE_GUARDIAN`: `1`

## Boundary

- No LM call, child spawn, Chief launch, service start, email/Gmail/browser/Coupa access, workbook cell read, PDF export, ledger mutation, production mutation, or push.
- This is readiness/contract work only.

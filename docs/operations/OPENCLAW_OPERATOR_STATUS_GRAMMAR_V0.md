# OpenClaw Operator Status Grammar v0

## 1. Purpose

This document captures a reusable generated-status grammar for operator-facing
read models:

```text
Evidence / Boundary / Blocked / Next safe move
```

The grammar is for deterministic status surfaces that summarize receipts,
committed artifacts, tests, or source-backed posture. It is not runtime
authority, deployment authority, or permission to act.

## 2. When To Use This Grammar

Use this grammar when a generated or operator-facing status section needs to
show:

- what evidence exists
- what the evidence proves
- what the evidence does not authorize
- what remains blocked
- what the Operator can safely do next

Good fits include:

- receipt-backed artifact checkpoints
- validation result summaries
- generated status read-models
- launch/readiness posture sections
- truth or source posture summaries
- approval or gate visibility surfaces

Do not use it to decorate raw logs. If a status section cannot answer evidence,
boundary, blocked surface, and next safe move, the section is not ready to be
operator-facing.

## 3. Section Semantics

### Evidence

Evidence states what is actually proven by committed source, tests, receipts,
or deterministic checks.

Good shape:

- `**Evidence:** committed docs/code artifacts have metadata-only SQLite checkpoint receipts.`
- `**Evidence:** validation command passed against three synthetic manifest examples.`

Evidence must not imply more than the source can prove.

### Boundary

Boundary states the authority limit of the evidence.

Good shape:

- `**Boundary:** recorded checkpoint only; not runtime authority.`
- `**Boundary:** read-model visibility only; no live service health is claimed.`

Boundary is where fake confidence gets cut off before it turns into implied
permission.

### Blocked

Blocked states what remains unavailable, denied, or out of scope.

Good shape:

- `**Blocked:** no module, agent, broker, customer deployment, or runtime behavior is activated or authorized by these receipts.`
- `**Blocked:** no private data body, external model export, or generated-status mutation is authorized.`

Blocked should sound calm and protective, not alarming. It is a protected
boundary, not a failure tone.

### Next Safe Move

Next safe move gives the Operator a short, bounded action that follows from the
evidence and boundary.

Good shape:

- `**Next safe move:** review docs/tests/receipts; runtime activation still requires a separate approved lane.`
- `**Next safe move:** add a synthetic test fixture before considering runtime wiring.`

The next move should be specific enough to guide work and narrow enough to avoid
scope expansion.

## 4. UX Rules

Generated status should feel like a calm operator console:

- lead with evidence, not vibes
- separate proof from authority
- show blocked surfaces before the Operator has to infer them
- keep tables compact and stable
- prefer one high-signal line over several caveats
- use exact machine-readable boundary fields when they prevent ambiguity
- avoid raw JSON, raw ledger rows, stack traces, and debug labels
- avoid status words that imply activation unless activation was separately
  proven and approved

For receipt-backed artifact status, compact table rows should preserve fields
like:

- `authority=no-runtime-authority`
- `runtime_activation=false`
- `sqlite=receipt-record-only`
- `body=not-ingested`

These fields are useful because they are short, exact, and hard to misread.

## 5. Fake-Confidence Prevention

This grammar prevents fake confidence by forcing every status surface to answer
four different questions:

| Question | Required answer |
| --- | --- |
| What is proven? | Evidence |
| What does that proof mean? | Boundary |
| What is still unavailable? | Blocked |
| What can happen next without overreach? | Next safe move |

If a section only says something is `ready`, `healthy`, `connected`, `active`,
or `done`, it is incomplete unless it also names evidence, boundary, blocked
surfaces, and a safe next move.

## 6. Evidence Is Not Authority

Receipts, generated status, read-model visibility, and committed docs are
evidence surfaces. They do not grant runtime authority.

Explicit rule:

**Receipts/status visibility never equals runtime authority.**

This means:

- a receipt can prove a checkpoint was recorded
- a receipt can prove a validation command ran
- a receipt can prove an approval request or decision was logged
- a generated status page can display those facts
- none of those facts activates modules, agents, brokers, customer deployment,
  runtime behavior, sensitive-data processing, or SQLite meaning beyond the
  recorded evidence

## 7. Good Wording Examples

### Artifact Checkpoint

```md
**Evidence:** committed docs/code artifacts have metadata-only SQLite checkpoint receipts.
**Boundary:** recorded checkpoint only; not runtime authority. No full Markdown/code body is ingested.
**Blocked:** no module, agent, broker, customer deployment, or runtime behavior is activated or authorized by these receipts.
**Next safe move:** review docs/tests/receipts; runtime activation still requires a separate approved lane.

| Artifact | Receipt Time | Checkpoint | Authority Boundary |
| --- | --- | --- | --- |
| `docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md` | 2026-05-13 10:00 | recorded `docs-only` | `authority=no-runtime-authority`; `runtime_activation=false`; `sqlite=receipt-record-only`; `body=not-ingested` |
```

### Validation Result

```md
**Evidence:** focused validator tests passed against synthetic fixtures.
**Boundary:** validation proves schema/example behavior only; it does not prove runtime readiness.
**Blocked:** no module activation, broker connection, customer deployment, or private-data processing is authorized.
**Next safe move:** add the next synthetic fixture or approval-gate test before any runtime lane.
```

### Approval Visibility

```md
**Evidence:** approval request receipt is visible in SQLite.
**Boundary:** request recorded only; no decision or execution is recorded.
**Blocked:** no side effect may run until a separate approval decision receipt exists.
**Next safe move:** wait for or request an explicit approval decision.
```

## 8. Bad Wording To Avoid

Avoid raw-log wording:

```text
2026-05-13 [ARTIFACT_CHECKPOINT] [SQLITE_VERIFIED] docs/module_atlas/... status=docs_only
```

Avoid activation ambiguity:

```text
Module Atlas receipts are ready.
```

Avoid authority inflation:

```text
Receipt exists, so the module can be used.
```

Avoid buried caveats:

```text
The checkpoint is verified, with some limitations around authority, runtime, data, brokers, and deployment.
```

Avoid vague confidence:

```text
Looks good.
```

Preferred replacement:

```md
**Evidence:** checkpoint receipt exists for the committed artifact.
**Boundary:** recorded checkpoint only; not runtime authority.
**Blocked:** no module, broker, agent, customer deployment, or runtime behavior is activated.
**Next safe move:** review the receipt-backed artifact and keep runtime work in a separate approved lane.
```

## 9. Non-Authority Boundary

This doctrine is documentation only. It does not change runtime behavior,
SQLite schema, receipt recording, generated files, module activation, broker
connections, agent wiring, customer deployment, or approval policy.

Future generated-status sections should adopt this grammar when it improves
operator clarity without creating verbosity or fake confidence.

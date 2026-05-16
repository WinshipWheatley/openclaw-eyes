# OpenClaw Codex Arc and Handoff Doctrine v0

## Purpose

This doctrine formalizes the OpenClaw working pattern for Codex lanes:

ChatGPT and the operator maintain strategy. Codex inspects the actual repo and environment. The operator approves implementation when scope or authority is uncertain. Codex performs bounded implementation only after the battlefield is understood, then leaves a portable handoff back to ChatGPT/operator.

This file complements `OPENCLAW_RUNTIME.md`, `USER.md`, `CORE_ARCHITECTURE_PRINCIPLES.md`, and the Project Chat orchestration docs. It does not authorize runtime changes, external sends, data import, Repo B execution, or approval bypass.

## 1. The Arc

Every meaningful OpenClaw lane should preserve this arc:

1. **Strategy surface**
   - ChatGPT/operator planning defines the goal, product direction, safety boundaries, and likely next lane.
   - Strategic prompts should be exact enough to prevent scope drift, but they are not a substitute for repo inspection.

2. **Battlefield inspection**
   - Codex inspects the real repo/environment before editing.
   - Codex checks branch, HEAD, dirty state, existing primitives, generated-file ownership, sensitive boundaries, and likely source of truth.
   - Codex reports what it found when the next move is uncertain or authority-sensitive.

3. **Approval point**
   - The operator decides whether implementation proceeds when ambiguity would change scope, authority, data handling, runtime behavior, or module boundaries.
   - Codex should ask direct questions when proceeding would cause drift.

4. **Implementation**
   - Codex implements only the bounded lane that is safe and approved.
   - It uses existing repo primitives where possible and avoids new parallel authority systems.
   - It validates with the narrowest meaningful tests/checks.

5. **Handoff**
   - After meaningful work, Codex should create or update a portable Markdown handoff when context continuity matters.
   - The handoff is memory for ChatGPT/operator, not hidden runtime authority.

## 2. When Codex Must Not Edit Yet

Codex should inspect and report before editing when any of these are true:

- scope is uncertain or the lane could branch materially;
- the repo is dirty beyond known/approved residue;
- generated-file ownership is unknown;
- the source of truth is unclear;
- authority boundaries are unclear;
- Repo A / Repo B split or module boundary is unclear;
- private, no-go, client, financial, bank, spreadsheet, raw log, Telegram, credential, or env data risk exists;
- live runtime/service behavior could change;
- Guardian/HITL approval authority is ambiguous;
- implementation would require operator choice;
- external send/API/deploy/runtime/remote-builder behavior could be enabled;
- a cleanup urge appears before the lane's real goal is proven.

Default response in these cases:

1. inspect;
2. summarize findings;
3. identify uncertainties;
4. propose a bounded plan;
5. ask the operator only for decisions that cannot be resolved from repo evidence.

## 3. Required Inspection Report

When a lane requires inspection before implementation, Codex should report:

- repo path and project state: empty, partially initialized, established, dirty, generated-heavy, sensitive, or unknown;
- branch and HEAD;
- dirty/untracked state;
- relevant existing files/surfaces;
- likely source of truth;
- generated-file handling;
- sensitive/no-go boundaries discovered from safe docs;
- uncertainties and questions;
- proposed implementation plan;
- exact stop conditions;
- whether implementation is ready now.

This report can be concise. It should be concrete enough that ChatGPT/operator can decide the next prompt without guessing.

## 4. Required Handoff Format

Use this template for portable handoffs when a lane crosses a meaningful checkpoint, starts a new phase, or leaves context that the next ChatGPT/Codex turn will need.

```markdown
# Codex Handoff: <lane name>

## Branch / Commit

## Completed Work

## Changed Files

## Commands Run

## Tests Passed

## Tests Failed

## Known Issues

## Risks / Boundaries

## Deliberately Not Touched

## Current Dirty State

## Next Recommended Prompt

## Ready / Not Ready Marker
```

Handoffs must preserve repo truth, not vibes. Include exact paths, commit hashes, validation receipts, known residue, and the next prompt target. Do not let handoffs become motivational summaries.

## 5. Sensitive OpenClaw Lane Handling

Use the inspect-report-approve-handoff arc especially for:

- HITL/Guardian authority lanes;
- Repo A / Repo B reconciliation;
- Cassandra/Chief memory import and classification;
- remote-builder bridge planning;
- Mission Control app lanes;
- client/friend/company module or bundle lanes;
- external-action, send, deploy, runtime, or approval lanes;
- generated read-model and SQLite authority changes.

These lanes often look small in code but large in authority. Codex should not jump straight into implementation unless the prompt, repo evidence, and existing contracts make the next move unambiguous.

## 6. Current Next-Lane Guardrail

The current next implementation candidate is:

`Guardian HITL SQLite Chief Approval Request Dual-Write v0`

That lane touches approval authority. It must start with inspection and plan confirmation before code changes.

Minimum first move:

1. confirm repo state and known residue;
2. read the dual-write spec and ready packet;
3. inspect `chief_approval_brain.py`, Operator Action, Guardian contract, and current tests;
4. confirm old JSON remains authoritative and no callers switch;
5. propose the exact implementation slice and tests;
6. proceed only if the lane remains bounded to observational request mirrors.

It must not implement decision/callback dual-write, sender receipts, Cassandra HITL dual-write, memory import, remote-builder, send-path expansion, old JSON deletion, or caller switch unless a later approved prompt explicitly authorizes that work.

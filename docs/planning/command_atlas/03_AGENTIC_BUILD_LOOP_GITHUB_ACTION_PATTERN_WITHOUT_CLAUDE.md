# Agentic Build-Loop / GitHub Action Pattern Without Claude

Generated/reviewed: 2026-05-05

Status: docs-only Command Atlas planning artifact. Freshness is current as of the generated/reviewed date and should be rechecked before any implementation, runner, CI workflow, GitHub integration, or agent-facing automation is proposed.

Source basis: recent operator review of the Claude Code SDK / GitHub Action pattern as architecture only, `docs/planning/command_atlas/00_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md`, `docs/planning/command_atlas/01_HERMES_SYSTEMS_ENGINEERING_RUN_MODE_SPEC.md`, `docs/planning/command_atlas/02_EXTERNAL_COMMUNICATIONS_RELATIONSHIP_JUDGMENT_LANE.md`, `docs/planning/launch_ladder/24_OPERATOR_HARNESS_PLANNING_INDEX.md`, and `docs/INDEX.md`. No Claude Code, Claude GitHub Action, SDK, runner, provider/model, Hermes run, MCP, service, sync, runtime work, indexing, embeddings, SQLite, extraction, chunking, source-set generation, private root, private data, GitHub Actions workflow, dependency install, or automation was run, installed, inspected, created, or modified for this artifact.

## 1. Status / Non-Authority

This document captures a pattern OpenClaw may borrow: headless agent jobs, scoped prompt packets, allowed tools, structured receipts, resumable state handles, issue/PR/check feedback loops, and explicit approval gates.

It does not adopt Claude Code as an execution substrate. It does not authorize installing Claude Code, Claude GitHub Actions, SDKs, CI runners, dependencies, providers, model routes, MCP servers, background services, workflow files, or automation.

OpenClaw policy remains local-first, approval-gated, non-Claude for agent execution, sensitive-data-safe, and explicit-authority-only.

## 2. Scope

In scope:

- planning the architectural pattern for a future agentic build-loop lane under Command Atlas;
- separating GitHub issue/PR/check coordination from actual agent execution;
- defining scoped job packets, explicit tool/path allowlists, receipts, and approval checkpoints;
- preserving local approved runner execution for code/docs mutation;
- describing deterministic CI verification after a commit or PR exists;
- naming authority boundaries among Cassandra, Chief, Guardian, Hermes, GitHub Actions, and the operator.

## 3. Non-Scope

Out of scope:

- installing or configuring Claude Code, Claude GitHub Actions, SDKs, packages, runners, or dependencies;
- creating GitHub Actions workflows;
- running cloud agents, providers, models, Hermes, MCPs, services, sync, runtime work, indexing, embeddings, SQLite, extraction, chunking, source-set generation, or implementation;
- inspecting private roots or private data;
- mutating branches, PRs, issues, runtime, services, credentials, repo settings, or code without explicit approval;
- making GitHub Actions a hidden approver, router, builder, or canonical authority.

## 4. Pattern Being Borrowed

OpenClaw may borrow these architectural ingredients without inheriting Claude execution:

- Headless agent invocation: a job can be described and dispatched without a conversational UI becoming the execution authority.
- Scoped job packets: each job declares purpose, exact inputs, allowed paths, forbidden paths, allowed tools, expected outputs, validation, and stale conditions.
- Explicit allowed tools: the runner receives a narrow tool list and cannot infer broader shell, network, provider/model, MCP, runtime, private-root, or repo mutation authority.
- Structured output and receipts: every run produces a machine-readable and human-readable record of inputs, exclusions, actions proposed, checks run, files touched, errors, and approval state.
- Resumable session IDs or equivalent state handles: a job may pause, resume, or be audited through an explicit handle without relying on hidden chat memory.
- CI/PR/comment feedback loops: GitHub issues, comments, PRs, and checks can show job status, review notes, validation results, and follow-up questions.
- Permission prompts or approval gates: sensitive, destructive, external, private-data, runtime, service, credential, branch, PR, or commit actions stop for explicit approval.

These ingredients are coordination and control patterns. They are not endorsement of Claude Code, cloud-agent commits, provider fallback, ambient credentials, or autonomous mutation.

## 5. OpenClaw Translation

OpenClaw translation:

- GitHub may serve as a coordination, issue, PR, comment, and deterministic check surface only.
- Actual agent execution remains on a local approved runner with explicit operator/Guardian/Chief boundaries.
- No Claude Code autonomous execution is authorized.
- No cloud model fallback is authorized for sensitive, private-root, system, runtime, credential-bearing, or authority-sensitive work.
- No private-root traversal is authorized.
- No unapproved repo mutation is authorized.
- GitHub Actions may verify deterministic checks after a commit or PR, but checks do not approve the underlying action.
- Prompt packets must not leak private data, secrets, provider keys, internal sensitive context, or broad repo state.
- The runner must default to proposal-first output: patch proposal, tests/diagnostics, receipt, and escalation route before application.

The useful pattern is not `let a cloud agent commit`. The useful pattern is `turn work into bounded packets with receipts, approvals, and deterministic verification`.

## 6. Proposed Steel-Thread Flow

1. An issue, comment, or task creates a bounded job request with purpose, repo scope, expected output, and forbidden surfaces.
2. A deterministic parser creates a job packet with exact input paths, allowed tools, validation plan, approval requirements, receipt fields, and state handle.
3. A local approved runner reads approved paths only and refuses private roots, secrets, runtime state, broad scans, providers/models, MCPs, Hermes runs, and unapproved mutation.
4. The runner proposes a patch plus tests, diagnostics, and a receipt. It does not apply sensitive, destructive, external-risk, or broad changes by itself.
5. Guardian or another human-in-the-loop gate approves, rejects, or narrows sensitive, destructive, external-risk, credential-bearing, private-data, branch, PR, or runtime actions.
6. Chief or the operator applies and commits explicit paths only when the work has the right authority and receipts.
7. GitHub Actions verifies deterministic checks after commit or PR and reports status back to the issue, PR, or check surface.

The steel thread starts with docs-only and deterministic checks. It should not begin with live code mutation, workflow creation, provider calls, or private-data tasks.

## 7. Authority Boundaries

- Cassandra may summarize job requests, draft clarifying questions, and help turn ambiguous comments into bounded packets. Cassandra does not approve execution.
- Chief may route approved work, sequence jobs, and execute approved repo workflows with explicit paths and receipts.
- Guardian gates sensitive, destructive, external-risk, credential-bearing, private-data, runtime, service, permission, branch, PR, and broad-mutation actions.
- Hermes may critique coherence, phase, authority, scope, tone, and signal alignment only. Hermes does not execute, approve, route, invoke MCP, or call providers/models.
- GitHub Actions may run deterministic checks and report pass/fail evidence. GitHub Actions must not become hidden authority, hidden execution policy, hidden provider/model route, or hidden approver.
- The operator remains the final authority for commits, branch/PR mutation, external effects, and scope expansion unless a later explicit policy grants a narrower authority path.

## 8. Allowed Outputs

Allowed outputs from this lane:

- job packet;
- patch proposal;
- test report;
- validation receipt;
- PR/check summary;
- issue/comment summary;
- clarification request;
- escalation recommendation;
- risk note;
- approval checkpoint request.

Allowed outputs are advisory or deterministic evidence until a separate approved workflow applies them.

## 9. Forbidden Actions

Forbidden actions:

- installing Claude Code, Claude GitHub Actions, SDKs, runners, dependencies, or provider packages;
- creating GitHub Actions workflow files in this planning lane;
- autonomous cloud-agent commits;
- provider/model prompt leakage;
- private-data access or private-root traversal;
- unapproved branch, PR, issue, label, check, or repo-setting mutation;
- hidden runtime, service, queue, bridge, sync, credential, permission, or user activation;
- broad repo mutation;
- `git add .` or implicit all-path staging;
- ambient fallback to cloud models for sensitive/system work;
- treating CI success as approval for the underlying change;
- treating an issue comment as execution authority without a parsed job packet and approval state.

## 10. Minimal Future Implementation Shape

A future implementation plan, if explicitly authorized later, should start with these pieces:

- deterministic job-packet schema: purpose, request source, exact input paths, allowed tools, forbidden paths, expected outputs, validation, receipt fields, approval gates, and state handle;
- local runner queue: local-first storage for pending, running, blocked, proposed, approved, applied, validated, failed, and archived job states;
- path/tool allowlist: exact repo paths and exact tools per job, with private roots, secrets, providers/models, MCPs, runtime, sync, and broad scans denied by default;
- receipt format: source request, parsed packet, inputs read, outputs proposed, files touched, checks run, diagnostics, approval decisions, state handle, commit or PR reference when present;
- CI verification workflow: deterministic checks after commit or PR only, not a hidden builder or approver;
- approval checkpoints: Guardian/HITL for sensitive, destructive, external-risk, credential-bearing, runtime, private-data, branch/PR, or broad-mutation actions.

The first implementation slice should be a schema and fixture plan, not a live GitHub Action or cloud-agent runner.

## 11. Checklist Before Any Implementation

Before any implementation begins, confirm:

- The work is still under Command Atlas, not an ad hoc automation shortcut.
- GitHub is coordination/check surface only.
- The execution substrate is a local approved runner, not Claude Code or a cloud autonomous agent.
- No Claude Code, Claude GitHub Action, SDK, runner, workflow, dependency, provider/model route, MCP, or service installation is authorized by this doc.
- Private roots, private data, secrets, credentials, runtime state, logs, queues, sync payloads, and broad repo scans are excluded.
- Job packets have exact input paths, allowed tools, forbidden paths, expected outputs, validation, receipt fields, and approval gates.
- Runner outputs are proposal-first unless a later policy grants a narrow apply authority.
- Guardian gates sensitive, destructive, external-risk, credential-bearing, runtime, service, private-data, branch/PR, or broad-mutation actions.
- Chief or the operator applies and commits explicit paths only.
- GitHub Actions checks are deterministic and post-commit or PR verification only.
- Receipts can prove what was requested, parsed, read, proposed, approved, applied, validated, and withheld.

If any checklist item is missing, the next allowed output is a planning note, job-packet draft, risk note, or escalation recommendation only.

## 12. Final Boundary

This lane borrows architecture, not execution authority. The OpenClaw build loop should become more packetized, receipt-producing, resumable, reviewable, and CI-verifiable without making Claude Code, cloud agents, GitHub Actions, issues, comments, checks, or PRs into hidden authority.

# Context Development Lifecycle And Context Filter Doctrine

Generated/reviewed: 2026-05-05

Source basis: `docs/planning/command_atlas/00_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md`, `docs/planning/command_atlas/01_HERMES_SYSTEMS_ENGINEERING_RUN_MODE_SPEC.md`, `docs/planning/command_atlas/03_AGENTIC_BUILD_LOOP_GITHUB_ACTION_PATTERN_WITHOUT_CLAUDE.md`, `docs/planning/launch_ladder/24_OPERATOR_HARNESS_PLANNING_INDEX.md`, `docs/INDEX.md`, `docs/planning/launch_ladder/knowledge_substrate/README.md`, `docs/planning/launch_ladder/knowledge_substrate/01_NORTH_STAR.md`, and `docs/planning/launch_ladder/knowledge_substrate/06_STATIC_VALIDATION_EXPECTATIONS.md`. No providers, models, Claude, Claude Code, Hermes runs, MCPs, services, sync, runtime work, indexing, embeddings, SQLite, extraction, chunking, source-set generation, private roots, private data, runtime/code edits, or source-set edits were run, inspected, created, or modified for this artifact.

## 1. Status / Non-Authority

This is a docs-only Command Atlas planning doctrine for Context Development Lifecycle and Context Filter work.

It records how OpenClaw should treat context as an engineered artifact before prompts, job packets, skills, handoffs, source sets, manifests, receipts, and planning docs are handed to agents or humans.

This document does not authorize provider/model calls, Claude, Claude Code, Hermes runs, MCP use, source-set generation, ingestion, indexing, embeddings, SQLite, FTS, extraction, chunking, runtime automation, GitHub workflow creation, private-root browsing, implementation, commits, or edits to `04_BACKEND_DATA_CONTRACT_READINESS`.

## 2. Purpose

The purpose is to put `context is the new code` in the correct layer: Command Atlas.

Context is now a first-class engineered artifact, not casual prompt prose. It should be generated, reviewed, tested, packaged, distributed, observed, and regenerated with the same seriousness OpenClaw applies to code, data boundaries, source-set manifests, and validation receipts.

This doctrine strengthens the non-Claude agentic build-loop pattern by adding lifecycle discipline around job packets, prompts, receipts, skills, and handoffs before any local runner or future automation receives them.

## 3. Core Thesis

Context changes system behavior.

Therefore, context packages need engineering discipline. Source sets, manifests, prompts, skills, handoffs, job packets, receipts, eval notes, planning docs, and reusable context registries are not neutral notes. They define what an agent sees, what it believes is relevant, what it thinks is allowed, and what it may accidentally treat as authority.

OpenClaw should treat context like code:

1. Generate context from approved sources.
2. Validate and test context before use.
3. Distribute and package context with provenance.
4. Observe context performance through receipts and failures.
5. Adapt or regenerate context when it becomes stale, unsafe, vague, or misleading.

Context changes need linting, evals, and checks, not vibes.

## 4. Context Development Lifecycle

The lifecycle is:

| Stage | Meaning | OpenClaw boundary |
| --- | --- | --- |
| Generate | Create a context package from named, approved inputs. | Use explicit source paths, source commits, freshness notes, and withheld surfaces. |
| Validate / test | Check the context package before an agent or workflow consumes it. | Run context linting, provenance checks, authority checks, private-leakage checks, and scope checks. |
| Distribute / package | Hand context to a runner, agent, human, source set, skill, or prompt surface. | Include manifest, purpose, allowed use, forbidden use, stale conditions, and receipt expectations. |
| Observe | Watch what the context caused or failed to support. | Use validation receipts, PR feedback, agent logs, failed runs, blocked runs, and critique notes only within approved non-sensitive surfaces. |
| Adapt / regenerate | Update the context package when evidence shows it is stale, risky, missing, overbroad, or misleading. | Regenerate from approved inputs and rerun checks; do not silently patch authority into prompts. |

The lifecycle is not an implementation pipeline. It is a planning and governance frame for safe context packages.

## 5. OpenClaw Context Artifacts

OpenClaw context artifacts include:

- source sets;
- manifests;
- freshness docs;
- prompts;
- skills;
- handoffs;
- job packets;
- validation receipts;
- approval receipts;
- eval notes;
- Sentinel or Hermes critique packets;
- planning docs;
- reusable context registries;
- future context-filter reports.

Source-set manifests and freshness docs are context provenance. They say what the package is, where it came from, when it becomes stale, what was withheld, and what it must not authorize.

No artifact becomes authority merely because it is packaged, named, visible, synced, mirrored, indexed, or included in a prompt. Context-visible does not mean authorized.

## 6. Context Testing / Evals

Context testing should ask whether the package is safe, current, bounded, and truthful about its own authority.

Static validators are context linting. They can check required terms, forbidden claims, source counts, manifest shape, freshness language, source-path allowlists, withheld-surface statements, and no-implementation boundaries.

Sentinel or Hermes critique may act as context eval, but only non-authoritatively. Critique can identify phase errors, authority inflation, private-data leakage, source-set laundering, stale assumptions, overbroad tool permissions, and missing receipts. Critique does not approve execution, generate authority, or mutate the package.

Context eval outputs should be advisory receipts: what was checked, what inputs were considered, what risks were found, what remains unknown, and what next bounded action is recommended.

## 7. Context Distribution / Packaging

Context should be distributed as an explicit package, not loose ambient instruction.

Every future context package should declare:

- purpose;
- source basis;
- source commit or timestamp when relevant;
- included inputs;
- excluded and withheld surfaces;
- allowed uses;
- forbidden uses;
- stale conditions;
- reviewer or approval path;
- expected receipts;
- tool and path boundaries when a runner or agent will consume it.

Context registries and reusable skills create dependencies. They need versioning, security review, provenance, prompt-injection controls, and deprecation rules. Reuse is useful only when the imported context remains current, scoped, and safe for the receiving task.

## 8. Context Observability

Context observability means noticing when a context package worked, failed, misled, or left gaps.

Approved observability signals may include:

- validation receipts;
- PR feedback;
- deterministic check results;
- failed runs;
- blocked runs;
- agent or runner receipts;
- reviewer notes;
- missing-evidence notes;
- context-filter findings;
- approved, non-sensitive issue or comment summaries.

These signals can reveal missing context, bad context, stale context, unsafe authority wording, bad tool boundaries, hidden execution instructions, private-data risk, or unclear next-action routing.

Observability does not authorize reading private logs, private roots, secrets, runtime state, provider prompts, MCP context, Hermes state, or hidden session material.

## 9. Context Regeneration

Context should be regenerated when:

- source inputs change;
- manifests or freshness docs become stale;
- validation receipts expose missing or misleading context;
- agent output repeatedly fails for the same context reason;
- PR or review feedback shows the packet is ambiguous;
- a doctrine doc changes authority boundaries;
- a tool/path allowlist changes;
- private-data, source-set, or root-boundary policy changes;
- a prompt or skill becomes too broad, stale, or authority-inflating.

Regeneration should return to approved inputs and rerun context checks. Do not patch over context drift by adding louder prompts, hidden commands, broader tools, or vague authority language.

## 10. Context Filter Doctrine

A context filter is required before agent execution because sandboxing runtime alone does not stop bad context from being loaded.

The filter should screen context packages for:

- private-root leakage;
- credential, token, key, or secret exposure;
- stale assumptions;
- authority inflation;
- prompt injection;
- source-set laundering;
- overbroad tool permissions;
- hidden execution instructions;
- private-data summaries smuggled into prompts;
- provider/model prompt leakage;
- MCP, Hermes, sync, runtime, or service activation by implication;
- GitHub issue/PR/comment/check surfaces becoming hidden authority;
- claims that retrieved, discovered, mirrored, or indexed content is accepted working context.

The filter should run before a local runner, agent, scout packet, skill, prompt, or reusable context package is allowed to influence execution. It may produce pass, warn, block, or needs-review outcomes. Sensitive, destructive, external-risk, private-data, credential-bearing, runtime, or broad-mutation concerns route to Guardian or operator review.

## 11. Relationship To Knowledge Substrate

This doctrine complements Knowledge Substrate planning.

Knowledge Substrate doctrine says retrieval finds candidates, compilation creates durable inspectable knowledge, and operator promotion or approval decides what becomes accepted working context. Raw files are evidence, not truth. Extracted text is parsed evidence, not truth. Compiled notes are interpretation, not truth. Unknown remains unknown.

Context Development Lifecycle governs how those concepts are packaged and handed to agents, humans, source sets, skills, prompts, and job packets. It does not authorize ingestion, indexing, embeddings, SQLite, extraction, chunking, provider/model calls, or private-data inspection.

## 12. Relationship To Agentic Build Loop

This doctrine strengthens `03_AGENTIC_BUILD_LOOP_GITHUB_ACTION_PATTERN_WITHOUT_CLAUDE.md`.

The build-loop pattern depends on scoped job packets, allowed tools, structured receipts, resumable state handles, PR/check feedback, and approval gates. Context Development Lifecycle says those job packets, prompts, receipts, and reusable skills must be generated, filtered, tested, packaged, observed, and regenerated like engineered artifacts.

Before a local runner reads approved paths or proposes a patch, the context filter should confirm the packet is bounded, current, non-leaking, non-injecting, and explicit about authority. GitHub issues, PRs, comments, checks, and queues remain coordination surfaces, not context authority, execution authority, or new attention sinks.

## 13. Risks / Anti-Patterns

Risks and anti-patterns:

- treating prompt prose as harmless because no runtime tool has started;
- loading broad docs or source sets without provenance;
- treating manifests as boilerplate rather than context provenance;
- treating static validators as optional when context changes behavior;
- letting reusable skills become stale hidden dependencies;
- allowing context registries to bypass source review;
- source-set laundering, where excluded/private/runtime facts become accepted because they appear in a package;
- authority inflation, where a prompt implies permission not granted by policy;
- prompt injection embedded in docs, comments, receipts, logs, or handoffs;
- overbroad allowed tools or path scopes;
- hidden execution instructions inside context packages;
- fake freshness, where old context is treated as current because it is packaged;
- treating Sentinel or Hermes critique as approval;
- treating GitHub checks as authority;
- using failed runs as permission to broaden scope without review.

## 14. Required Future Checks

Future context-filter and lifecycle checks should verify:

- context package purpose is explicit;
- source basis and source commit or timestamp are present where needed;
- manifests and freshness docs are current;
- direct inputs and withheld surfaces are named;
- private roots, private data, secrets, credentials, runtime state, logs, provider/model prompts, MCP context, Hermes output, sync output, and generated runtime artifacts are excluded unless a separate approval path exists;
- prompt-injection patterns are flagged for review;
- hidden execution instructions are absent;
- allowed tools and paths are exact and minimal;
- source-set bridges do not launder excluded/private content into authority;
- context does not claim retrieved, discovered, indexed, mirrored, or compiled material is accepted working context without operator promotion or approval;
- context eval output is advisory and receipt-backed;
- stale conditions and regeneration triggers are present;
- the next action remains bounded and reviewable.

## 15. What This Does Not Authorize

This doctrine does not authorize:

- provider/model calls;
- Claude or Claude Code;
- Hermes runs;
- MCP use;
- source-set generation;
- ingestion;
- indexing;
- embeddings;
- SQLite or FTS work;
- extraction or chunking;
- runtime automation;
- GitHub workflow creation;
- implementation;
- runtime/code edits;
- private-root browsing;
- secret inspection;
- edits to `04_BACKEND_DATA_CONTRACT_READINESS`;
- commits.

It only defines context lifecycle and filtering doctrine under Command Atlas.

## 16. Next Safe Action

Exact next safe action: create a docs-only context-filter checker plan for future job packets, prompts, source-set manifests, and reusable skills. That plan should define required fields, lint rules, eval receipts, block conditions, and examples of safe pass/warn/block outcomes without implementing a runner or invoking any provider, model, MCP, Hermes, runtime, or source-set generation.

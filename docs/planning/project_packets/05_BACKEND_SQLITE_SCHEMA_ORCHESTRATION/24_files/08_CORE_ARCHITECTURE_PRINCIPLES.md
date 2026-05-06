# Core Architecture Principles

This document is the permanent architectural guardrail for this project.

## How This Is Used

Before proposing any new tool, architecture, dependency, service, plugin, or major refactor, perform a silent pre-check against these principles.

If a proposal fails any principle, do not recommend it unless there is a documented and explicit exception approved by project authority.

## 1) Single Source of Truth

Design and operations must converge on one canonical location per concern.

- Do not duplicate state across parallel stores when one canonical store is sufficient.
- Do not create shadow memory systems, side ledgers, or mirrored docs that can drift.
- Prefer native project files and unified data stores over external synchronization layers.
- If redundancy is unavoidable for reliability, define one canonical writer and deterministic reconciliation rules.

## 2) Minimalist Infrastructure (Code Over Bloat)

Prefer simple, inspectable code paths over heavyweight orchestration frameworks.

- Start with standard functions, small queues, native schedulers, and direct scripts.
- Avoid adding visual orchestration stacks or complex abstraction layers unless strictly necessary.
- Optimize for low operational overhead and fast incident diagnosis.
- Every new moving part must have a clear failure model and maintenance owner.

## 3) Audit Before Adding

No new dependency or system layer is introduced without proving existing capabilities are insufficient.

- First audit what the current stack can already do.
- Use existing native features when they satisfy the requirement.
- Add new tools only when there is a verified capability gap.
- Record the gap, alternatives considered, and decision rationale in the relevant project log.

## 4) Categorical Clarity

Keep infrastructure, tooling, and application logic separated by role.

- Use each system for its foundational purpose.
- Do not repurpose application frameworks for local operator workflows.
- Do not mix runtime concerns with build, deployment, or governance concerns.
- Keep boundaries explicit so ownership and troubleshooting remain clear.

## 5) Future-Proof Simplicity

Architecture should be understandable quickly by a new engineer.

- Favor topologies that can be explained in a short diagram and verified from code.
- If a design requires a second system whose main job is managing the first, simplify.
- Prefer fewer layers, fewer transforms, fewer coordination loops.
- Make the correct path obvious and the unsafe path difficult.

## Proposal Gate Checklist

Before recommending changes, ensure all answers are "yes":

1. Is there a single canonical source for new state introduced?
2. Can this be solved with existing stack features and native project mechanisms?
3. Is the solution the lightest option that meets reliability and security needs?
4. Are infrastructure, tooling, and app logic boundaries still clean?
5. Can a new engineer explain and operate this design quickly without extra control planes?

If any answer is "no", revise the proposal or document an explicit exception before proceeding.

## Exception Standard

Exceptions are rare and must include all of the following:

- Why current stack-native options are insufficient.
- Why the added complexity is justified by measurable risk reduction or capability gain.
- Rollback plan and decommission criteria.
- Owner responsible for long-term maintenance.

Without this record, the default decision is to reject the addition.
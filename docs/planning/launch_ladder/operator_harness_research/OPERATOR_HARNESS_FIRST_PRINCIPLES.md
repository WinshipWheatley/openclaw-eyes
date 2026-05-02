# Operator Harness First Principles

## Purpose

This document defines first principles for an OpenClaw Operator Harness: the umbrella control layer that helps an operator plan, approve, route, launch, and verify work across one or more OpenClaw-style builds. It treats the harness as an operator-support surface, not as an autonomous authority.

## Source Basis

- Human-automation research: Parasuraman, Sheridan, and Wickens' automation-level taxonomy; Bainbridge's "Ironies of Automation"; Onnasch et al.'s meta-analysis on automation level effects; Microsoft Human-AI Interaction Guidelines; Google PAIR explainability and trust guidance.
- Risk and governance sources: [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework), [NIST Four Principles of Explainable AI](https://www.nist.gov/publications/four-principles-explainable-artificial-intelligence), [NIST AI 600-1 Generative AI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf), and [OpenAI practices for governing agentic AI systems](https://openai.com/index/practices-for-governing-agentic-ai-systems).
- Operational sources: [Google SRE postmortem culture](https://sre.google/sre-book/postmortem-culture/), [Google SRE eliminating toil](https://sre.google/sre-book/eliminating-toil/), [OpenGitOps principles](https://opengitops.dev/), and [Kubernetes controller pattern](https://kubernetes.io/docs/concepts/architecture/controller/).
- Local-first source: Kleppmann et al., [Local-first software](https://martin.kleppmann.com/2019/10/23/local-first-at-onward.html).

## Confirmed Best Practices

Human authority must remain explicit when systems affect real resources. Human-automation research consistently warns that automation can improve routine throughput while degrading situation awareness and failure recovery when operators are pushed out of the loop. The harness should therefore keep the operator in the decision loop for destructive, credential-bearing, external, irreversible, billing, or scope-expanding actions.

Automation should support different stages differently. The Parasuraman/Sheridan/Wickens model separates information acquisition, information analysis, decision selection, and action implementation. For OpenClaw, v1 should automate acquisition and analysis where safe, assist decision selection, and require explicit approval for action implementation.

Explanations must be sufficient, contextual, and calibrated. NIST's explainability work and Google PAIR guidance both emphasize that confidence and explanations are useful only when they help the human decide what to trust, verify, or reject. Numeric confidence alone is not enough.

Operations should produce durable evidence. SRE practice treats postmortems, logs, and operational records as learning artifacts. OpenClaw's Evidence Trail should be a first-class output of work, not a side effect hidden in terminal scrollback.

State needs one canonical owner. OpenGitOps and Kubernetes both separate desired state from observed state and rely on reconciliation loops. OpenClaw should borrow the conceptual clarity without adopting a heavy controller system in v1.

## First Principles For OpenClaw

1. The operator is the authority.

The Operator Harness routes, visualizes, validates, and records. It does not become the principal that decides what is allowed. Approval must bind to a specific launch packet, not to a vague class of future actions.

2. The console is a window, not a crown.

The console may show maps, ladders, packets, evidence, freshness, and pending approvals. It must not become the sole source of truth for project state, secrets, permissions, or runtime identity.

3. The repo is the proof surface.

Planning state, launch packets, evidence trails, and drift reports should live as human-readable repo artifacts where possible. A database may index them for speed, but it should not be the only place where proof exists.

4. Assist before acting.

The safe v1 ladder is: read local public project context, synthesize routes, draft launch packets, validate constraints, produce evidence, and wait for operator approval before execution that touches real systems.

5. Every action has a boundary.

A launch packet must name machine, workspace, tool, source set, files or systems in scope, explicit exclusions, stop conditions, validation, rollback or undo notes, and commit boundaries.

6. Freshness is a design primitive.

The harness should never present stale context as current. Every map node, ladder rung, source-set bundle, and evidence artifact should carry freshness metadata: observed time, source, hash or commit, and stale reason when known.

7. Compression must remain reversible.

Route Compression can shorten the visible route into Direct, Balanced, or System paths, but deferred work must remain attached as visible debt, assumptions, and skipped checks.

8. Parallelism is a privilege earned by explicit non-collision.

A Parallel Step Bundle is valid only when independent write sets, validations, commit boundaries, collision handling, stop conditions, and operator approval are explicit.

9. Secrets stay outside the harness.

Guardian or other approval helpers may approve or deny exact action packets. They must never store, transmit, paste, unlock, or ask to reveal passwords, SSH passphrases, tokens, private keys, vault contents, or credential material.

10. V1 must be boring on purpose.

The first usable harness should prefer repo-native Markdown, schemas, local validation, and a thin UI over a distributed control plane. Future clients can be preserved by stable packet/evidence schemas, not by adding service infrastructure early.

## OpenClaw Recommendations

- Build the v1 harness around three durable artifacts: `LaunchPacket`, `EvidenceTrail`, and `DeploymentRegistry`.
- Make the UI a browser over those artifacts plus a launcher for approved local commands.
- Treat the Multi-OpenClaw Command Atlas as an inventory and navigation surface in v1, not as a live remote control plane.
- Encode authority in packet approval records: who approved, what exact packet hash, when, from what local workspace, and what was excluded.
- Require every automated suggestion to show its source set and freshness state.
- Keep model/provider invocation out of v1 unless a later scoped decision introduces it with a separate approval and privacy design.

## Risks And Anti-Patterns

- Hidden autonomy: "approve this workflow" becomes blanket permission for future mutations.
- Confidence theater: polished UI implies certainty without source, freshness, or validation.
- Control-plane overreach: the Atlas starts modifying runtimes before the local evidence and approval model is proven.
- Secret capture: a helper stores or forwards credentials for convenience.
- Dashboard sprawl: many views exist, but none bind to exact launch packets or evidence.
- Task-board collapse: the ladder becomes generic work tracking instead of staged progress toward a North Star task.

## V1 Non-Goals

- No service/runtime mutation.
- No private/legal/vault/log inspection.
- No provider/model calls unless explicitly scoped later.
- No autonomous cross-machine execution.
- No remote client sync layer.
- No credential storage beyond OS/keychain/SSH-agent/passkey/manual operator mechanisms.


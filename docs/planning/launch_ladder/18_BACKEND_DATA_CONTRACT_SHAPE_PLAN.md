# Backend Data Contract Shape Plan

Status: docs/test-only planning.

## 1. Purpose

Define conceptual backend/data-contract shapes needed before backend/schema/SQLite/ingestion/fixture work.

## 2. Non-goals

This slice does not authorize implementation. Explicitly, do not authorize implementation, backend/API/schema files, SQL DDL, SQLite DB creation, ingestion, fixture generation, provider/model calls, private-data inspection, runtime mutation, app implementation, app naming, audio/haptic/notification work, or source-set 05 generation.

## 3. March/April 2026 OpenClaw Prior-Art / Upstream Alignment

Important researched context to include as planning input:

- March 2026 OpenClaw introduced/expanded gateway-daemon architecture, Control UI v2 / gateway dashboard views, command palette/search/export/pinned-message-style surfaces, ACP / Agent Communication Protocol, inter-agent messaging, task delegation/context sharing, thread-bound persistent sessions, sub-agent spawning, session_status-style tracking, health checks, backup CLI, recovery/session persistence, provider/plugin architecture, and security hardening around gateway auth, WebSocket origin validation, SSRF/tar traversal, device-pairing credentials, workspace/plugin trust gates, and approval-prompt hardening.
- April 2026 OpenClaw introduced/expanded /tasks, SQLite-backed background task/task-flow ledger concepts, durable task-flow orchestration, Memory Wiki claim/evidence/freshness semantics, freshness-weighted search, Active Memory as an optional pre-reply memory sub-agent, bundled Codex provider support, provider-backed inference surfaces such as openclaw infer, exec-policy / owner-only command safety surfaces, and other SQL/SQLite-backed task/memory primitives.

Treat these as upstream prior art / alignment constraints, not as implementation authority.
Do not bind to upstream schemas in this slice.
Do not claim our local installed OpenClaw definitely has every feature unless verified later.
Before implementation we must inspect the actual installed/local OpenClaw version and repo surfaces.

Operator Harness / Mission Control should define operator-facing semantic contracts over upstream primitives, not blindly duplicate upstream task ledgers, task flows, memory wiki, active memory, provider inference, exec-policy, gateway dashboard, or Control UI concepts. Future implementation must first inspect actual local installed OpenClaw version/surfaces before binding to any upstream schema or CLI.

## 4. Contract Shape Principles

- Treat readiness layer as a directed typed evidence graph.
- Edges represent dependency only; they do not imply truth, safety, freshness, visibility, or authority.
- Preserve: visibility != truth != safety != freshness != authority.
- Discovered does not mean read.
- Extracted does not mean true.
- Classified does not mean safe.
- Compiled does not mean accepted.
- Promoted does not mean general authority.
- Unknown remains restricted.
- Sensitive/local-only must be representable without exposing content.
- App-visible state must have evidence/freshness basis.

## 5. First Conceptual Record Shapes

- **source file record**: Represents the discovered file entity. Minimum conceptual fields: id, path, discovery timestamp, hash. Must not imply read or safe. App-facing use: discovery card.
- **extracted text record**: Represents parsed text. Minimum conceptual fields: id, text blob, source ref, extracted timestamp. Must not imply true or semantic meaning. App-facing use: detail view.
- **rendered fragment record**: Represents visual or rich rendering. Minimum conceptual fields: id, visual blob, source/extracted ref. Must not imply authority. App-facing use: rich preview.
- **artifact classification record**: Represents sensitivity label. Minimum conceptual fields: id, source ref, label, reviewer. Must not imply safe. App-facing use: security badge.
- **claim record**: Represents confidence-bounded proposition. Minimum conceptual fields: id, proposition, evidence refs, confidence. Must not imply truth. App-facing use: claim detail.
- **contradiction record**: Represents detected conflict. Minimum conceptual fields: id, claim refs, desc. Must not imply resolution. App-facing use: operator alert.
- **compiled note record**: Represents synthesized interpretation. Minimum conceptual fields: id, summary, claim/evidence refs. Must not imply accepted truth. App-facing use: note card.
- **freshness record**: Represents recency of a specific target. Minimum conceptual fields: id, target ref, reviewed at, source basis. Must not imply global system freshness. App-facing use: staleness indicator.
- **operator promotion record**: Represents explicit operator acceptance. Minimum conceptual fields: id, target ref, action (accept/reject), timestamp. Must not imply general authority. App-facing use: approval state.
- **conversation packet record**: Represents sanitized conversation summary. Minimum conceptual fields: id, sanitized text, source refs. Must not imply full context or external-model safety. App-facing use: chat history card.
- **blocked sensitive source record**: Represents withheld content. Minimum conceptual fields: id, source ref, block reason. Can prove blocked existence without exposing content. App-facing use: block notice.
- **unknown/unclassified artifact record**: Represents unsorted item. Minimum conceptual fields: id, item ref. Must not soften into confidence. App-facing use: unknown boundary warning.

## 6. Relationship Rules

- extracted text references source file
- rendered fragment references source file or extracted text
- claim references evidence
- compiled note references claims/evidence
- freshness references the target it scopes
- promotion references explicit target/scope
- conversation packet references sanitized records only
- blocked sensitive source can prove blocked existence without exposing content
- BlockedSensitiveSource may only be referenced through opaque or sanitized references; blocked content must not be exposed
- UnknownArtifact must not flow directly into claims, promotions, or conversation packets

## 7. App-Facing State Mapping

Map records to future Mission Control/app states. This is state semantics only, not UI implementation.
- ready: Preconditions met for review.
- blocked: Action or data withheld.
- stale: Freshness constraint failed.
- unknown: Lacks classification or evidence.
- sensitive/local-only: Constrained visibility.
- evidence available: References present.
- approval/promotion available: Action pending operator.
- contradiction present: Requires resolution.
- packet prepared: Ready for transmission.

## 8. Upstream Update Monitor / OpenClaw Update Review Card

Operator Harness should monitor OpenClaw releases, changelogs, security advisories, and relevant ecosystem updates.
New updates should appear as evidence-backed update cards.
Each card should include: what changed, why it matters, how it maps to our system, risk/security impact, overlap with current Operator Harness plans, recommended action, and operator-approved next step.
Recommended card actions: Ignore, Monitor, Research, Create sandbox test packet, Prepare implementation plan, Apply after approval.
“OpenClaw upstream updates should be represented as evidence-backed update cards with impact analysis and operator-approved Launch Packets, not silent background changes.”
The card can recommend, the operator approves, the system prepares a Launch Packet, and execution remains separate.

## 9. Failure Modes / Laundering Risks

- classification laundering
- compilation laundering
- promotion leakage
- freshness overreach
- sanitization ambiguity
- unknown downgrade
- contradiction-resolution-by-presentation
- source-existence bias
- local-only leakage
- packet authority illusion

## 10. Future Fixture Topics

Synthetic fixture topics for the future (this artifact does not create fixtures):
- valid synthetic source
- contradiction scenario
- stale freshness record

## 11. Future Static Validation Expectations

Future static validation should prove:
- 18 plan exists
- required record shapes are named
- forbidden implementation authorizations are absent
- state-separation phrases are preserved
- upstream prior-art alignment is present
- update monitor/review card concept is present
- unknown restricted and sensitive local-only are preserved
- app-facing states require evidence/freshness basis
- no source-set 05 generation occurs in this slice

## 12. Recommended Next Move

Recommend either:
- one more docs/test planning slice for synthetic fixture design, or
- source-set generation for future 05 only after the 18 plan is committed and audited
Do not recommend implementation yet.

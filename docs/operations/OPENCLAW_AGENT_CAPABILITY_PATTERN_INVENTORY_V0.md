# OpenClaw Agent Capability Pattern Inventory v0

## Status
- Source basis: repo evidence and current contract formalization work
- Current owner: manual planning/docs pass
- Future advisory owner: Hermes advisory lane
- Not runtime authority
- Not a promotion engine
- Not an automation system
- Do not treat candidate_shared as already promoted

## Purpose
- This tracks useful patterns discovered while formalizing agents.
- It helps decide whether patterns stay agent-specific or become shared doctrine.
- It prevents duplication, accidental rewrites, and bad redundancy.
- It supports future Hermes consultant/systems-engineer review.
- It does not itself authorize runtime changes.

## Pattern Promotion Vocabulary
- **agent_specific**: Pattern is tightly coupled to one agent's domain/logic.
- **candidate_shared**: Pattern is identified as potentially useful across multiple agents.
- **shared_doctrine_candidate**: Pattern is being drafted into a cross-agent contract or template.
- **promoted_shared**: Pattern is now part of the formal shared doctrine (e.g., universal intake contract).
- **blocked_from_generalization**: Pattern must remain isolated due to security, complexity, or domain mismatch.
- **needs_more_evidence**: Potential pattern identified but requires more real-world usage data.
- **future_hermes_review**: Target for Hermes advisory review in the next phase.

## Pattern Entries

### 1. Niles Explain Packet Pattern
- **source_agent**: Producer/Niles
- **what is useful**: deterministic intake → human response / explain packet; specific suggested_move identifiers.
- **current status**: built/current for Niles.
- **reuse decision**: candidate_shared for explainability shape; music taste remains Niles-specific.
- **promotion target**: shared explainability packet doctrine.
- **risk if generalized too early**: generic explain packets with no useful domain specificity.
- **next safe slice**: compare against Cassandra templates and universal intake/action contract.

### 2. Niles Deterministic Suggested Move Pattern
- **source_agent**: Producer/Niles
- **useful because**: converts vague creative text into compact machine-action language.
- **reuse decision**: candidate_shared pattern for domain-specific suggested_move identifiers.
- **keep agent-specific**: actual music/production suggested_move vocabulary.

### 3. Cassandra PII / Sensitive Context Handling Pattern
- **source_agent**: Cassandra/Clara
- **useful because**: supports safe external model usage through redaction/tokenization, safe_prompt, opaque context, local rehydration.
- **current status**: built behavior / implied packet / initial template exists.
- **reuse decision**: high-value candidate_shared for any agent touching sensitive text.
- **promotion target**: shared_sensitive_context_packet or external_model_safety_gate.
- **hard boundary**: no raw sensitive data to external models.
- **risk if generalized too early**: false confidence from weak redaction; sensitive leakage.
- **next safe slice**: define shared sensitivity-class policy after more agent contracts.

### 4. Cassandra Draft-Only Outreach Pattern
- **source_agent**: Cassandra/Clara
- **useful because**: allows useful outward-facing work without send authority.
- **reuse decision**: candidate_shared for “draft/prep only until approval” workflows.
- **promotion target**: shared draft/action-intent gating pattern.
- **hard boundary**: send-class actions require Chief/Guardian approval.

### 5. Chief Action/Approval Routing Pattern
- **source_agent**: Chief
- **useful because**: centralizes routing, approval policy, acceptance verdicts.
- **reuse decision**: should remain centralized/shared authority, not copied into agents.
- **promotion target**: shared action-intent/approval routing doctrine.
- **risk if generalized too early**: agents gain local approval authority.

### 6. Guardian HITL Approval Receipt Pattern
- **source_agent**: Guardian
- **useful because**: human approval creates inspectable gate/receipt.
- **reuse decision**: shared gate pattern, Guardian remains final approval lane.
- **promotion target**: approval receipt schema / HITL doctrine.
- **risk if generalized too early**: approval bypass or duplicate approval systems.

### 7. Hermes Advisory-Only Pattern
- **source_agent**: Hermes
- **useful because**: systems-engineering review without mutation authority.
- **reuse decision**: Hermes should own future pattern review as advisory packets.
- **promotion target**: Hermes pattern-review advisory packet.
- **hard boundary**: Hermes cannot mutate, approve, or become hidden authority.

### 8. PI / Operator Next Sane Thing Pattern
- **source_agent**: PI / Operator Clarity
- **useful because**: prevents operator overload and choice bloat.
- **current status**: future/proposed unless repo evidence proves more.
- **reuse decision**: candidate for operator-facing advisory surfaces only.
- **hard boundary**: advisory only, not runtime authority.

## Generalization Rules
- Do not promote a pattern just because it is useful once.
- Promote only when source agent keeps its specialization.
- Shared patterns need clear owner, tests, boundaries, and receipt/provenance expectations.
- If a pattern touches sensitive data, approval, external models, or runtime mutation, require explicit gates.
- Agent-specific taste/context should not be flattened into generic shared doctrine.

## Future Hermes Role
- Hermes may later review this inventory and emit advisory packets.
- Hermes may recommend promote/defer/block for each pattern.
- Hermes must not auto-promote, auto-edit runtime, or override Chief/Guardian.
- This document is the seed surface for that future review.

## Do Not Build Yet
- Hermes runtime updater for this inventory.
- SQLite-backed pattern promotion system.
- automatic cross-agent pattern promotion.
- shared PII gate implementation.
- external model router changes.
- runtime mutation or approval changes.

## Recommended Next Slice
- Index this inventory in docs/maps.
- Continue agent contracts while appending pattern entries manually.

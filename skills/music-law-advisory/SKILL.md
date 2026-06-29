---
id: music_law_advisory
name: music-law-advisory
description: Advisory music-law skill for publishing splits, sync, sample-clearance, rights, and music-business legal-risk questions routed through OpenClaw.
owner_agent: chief
triggers:
  - music law
  - music legal
  - music-law
  - publishing split
  - publishing splits
  - sync license
  - sample clearance
  - copyright split
  - co-write
  - topliner
  - Ten Fingers
  - Log Rhythm
tools:
  - chief_musiclaw_brain
  - niles_album_review_packet
  - niles_track_registry
authority: advisory_only
capability_needed: multi-step-reasoning
tiers:
  simple: |
    Identify the music-rights question type: publishing split, sync, sample clearance, copyright ownership, co-write/topliner credit, or active dispute. Pull only the relevant music-law facts and known OpenClaw music read-model context. Answer plainly as advisory orientation. Always preserve the safety boundary: This is general information, not legal advice. Consult an entertainment lawyer before taking action.
  rich: |
    Identify the music-rights question type, then reason through authorship, composition versus master rights, publishing administration, sync/sample clearance, split-sheet gaps, and the known Ten Fingers / Log Rhythm dispute context when relevant. Use chief_musiclaw_brain for the grounded music-law knowledge body and preserve edge-case uncertainty. Stay advisory only; do not draft threats, send notices, sign, file, or approve legal action. Always include the safety boundary: This is general information, not legal advice. Consult an entertainment lawyer before taking action.
---

# Music Law Advisory

Use this skill to answer music-business legal-risk questions through the existing `chief_musiclaw_brain` knowledge body and music read-model context. Keep the answer in Chief's advisory lane even when the operator reaches the skill through Maestro or Cassandra.

## Boundaries

- Treat the skill as advisory context only.
- Use `chief_musiclaw_brain._ensure_musiclaw_safety` as the guardrail; do not replace it.
- Never send, sign, file, threaten, approve legal action, submit a claim, or mutate a ledger or rights record.
- Do not inspect private music-law vault roots or raw contract material.
- If stakes are real, active, contractual, disputed, or money-bearing, include: This is general information, not legal advice. Consult an entertainment lawyer before taking action.

## Simple Tier

Identify the question type, pull the relevant public/internal music-law facts, answer plainly, and append the lawyer flag when stakes are real.

## Rich Tier

Reason through publishing, sync, sample-clearance, split-sheet, authorship, and dispute-context edge cases. Use the Ten Fingers / Log Rhythm context only when it is relevant and present in the grounded packet. Keep the response advisory and lawyer-flagged.

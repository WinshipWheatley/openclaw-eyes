# Model And Tool Specific Prompt Doctrine

Status type: OPERATING_DOCTRINE / BOUNDARY_GUARD

## Purpose

Make prompt discipline a first-class Packet 07 rail. Prompts must be shaped to the worker's strengths, failure modes, and authority boundaries, not written as generic safety boilerplate.

## Source Inputs

- Packet 06 final `00_ACTIVE_HANDOFF.md`
- Packet 06 `06_PROJECT_CHAT_OPERATOR_EXPERIENCE_CONTRACT.md`
- Packet 06 `24_VISIBLE_ROAD_AND_BIG_STRIDES_DOCTRINE.md`
- Packet 06 final consolidation prompt-doctrine carry-forward
- `USER.md`

## What It Governs

- Gemini planning/audit prompt shape.
- Codex implementation prompt shape.
- Review prompt split by tool.
- Boundaries that prevent real drift without disabling useful execution.
- Prompt granularity and right-stride length.

## Doctrine

- Prompts must be tailored to the worker's actual strengths and failure modes.
- Gemini planning/audit prompts are for rail interpretation, architecture/design judgment, tradeoffs, risk, scope, campaign shaping, and READY/NOT_READY recommendations.
- Gemini plans are not automatic execution authority.
- Codex implementation prompts are for bounded repo mutation: inspect conventions, edit files, add focused tests, run checks, fix failures, and produce reviewable diffs.
- Codex prompts should guard against Codex's real drift risks: invented architecture, adjacent-file mutation, broad cleanup/refactors, unnecessary code for policy rails, dirty-worktree mistakes, broad staging, and overclaiming completion.
- Do not castrate Codex with generic forbiddance spam. Guard the real risks.
- Review prompts split by tool:
  - Gemini review: architecture, scope, risk, rail alignment, overreach/underreach.
  - Codex review: dirty diff, line behavior, tests, failure modes, exact changed files, boundary leaks, commit readiness.

## Repo Implementation Pointers

- `docs/planning/project_packets/07_OPERATOR_HARNESS_PROMPT_DOCTRINE_AND_GATED_ACTIVATION/00_ACTIVE_HANDOFF.md`
- `scripts/openclaw_receipts.py`
- `tests/test_openclaw_receipts.py`

## Valid Future Lane Moves

- Produce reusable prompt patterns for Packet 07 lanes.
- Review existing prompts for over-guarding, under-guarding, and tool mismatch.
- Convert rough operator requests into exact Gemini, Codex, or review prompts.
- Add handoff notes only when prompt behavior materially changes the train state.

## Forbidden Drift

- Do not use generic forbiddance lists as a substitute for scoped authority.
- Do not ask Gemini to mutate the repo.
- Do not ask Codex to make architecture decisions without source rails and review boundaries.
- Do not treat model output as execution approval.
- Do not hide failures or overclaim completion.

## Review Boundary

Review before launching a multi-mile-marker campaign, assigning model roles, or writing prompts for runtime, billing, legal, sensitive, MCP, or Packet renewal work.

## Why It Should Last 10-20 Moves

Prompt discipline is the main Packet 07 authority. It should reduce operator tax and model drift across many substantial moves.

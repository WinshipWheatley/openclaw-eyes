# Backend SQLite Schema Orchestration Project Packet

Status: ChatGPT Project upload packet export for the inert SQLite schema-definition orchestration phase.

This folder is an export package. `/home/openclaw` remains the canonical repo and build truth.

## Contents

- `24_files/` contains the stable phase source-set for ChatGPT Project upload.
- `00_ACTIVE_HANDOFF.md` sits outside `24_files/` because it is active/current and may change more often than the stable source-set.
- `README.md` explains the packet structure and mirror boundary.

## Mac Mirror Destination

```text
~/OpenClaw_Watch/project_packets/05_BACKEND_SQLITE_SCHEMA_ORCHESTRATION/
```

The Mac mirror is for operator review and ChatGPT Project upload convenience. It is not canonical authority.

Future ChatGPT Project packets should use this same structure:

```text
<PROJECT_PACKET_NAME>/
  24_files/
  00_ACTIVE_HANDOFF.md
  README.md
```

## Faster Workflow / Batch Checkpoint Rule

- If a bounded lane is clear, complete implementation + hardening + polish/taste in one batch.
- ChatGPT should not ask for diff review after every micro-step.
- One combined diff/status review is enough unless there is risk.
- Commit/push at meaningful checkpoints, not after every small edit.
- Deep diff review is reserved for authority boundary changes, runtime/persistence/private-data behavior, failed tests, unexpected files, or ambiguity.
- `00_ACTIVE_HANDOFF.md` is milestone-based, not micro-step-based.
- `24_files/` is stable/archive-like during an active lane.

## Right Stride Length Rule

- The project should move at safe speed, not maximum caution.
- Baby steps are for unclear/high-risk/high-authority work.
- Solid strides are the default once tests, boundaries, and rollback points exist.
- Running is allowed for repetitive, low-risk, well-tested work.
- Future prompts should choose the stride length intentionally.
- Constraints are guardrails, not a substitute for completing the lane.
- Agents should finish the bounded lane when appropriate: build, harden, polish, taste-pass up to 3, validate, and report.
- Handoffs/commits should happen at meaningful checkpoints, not every micro-step.

## Audit-to-Execution Rule

When a coder/agent is asked to audit a lane and determine the next move, do not stop at recommendation when the next move is clear and authorized. It must execute the chosen move in the same pass if:
- the next move is clear,
- it is inside the established authority boundary,
- tests/rollback points exist,
- and it does not require operator governance.

Stop at recommendation only for real blockers or governance decisions:
- the next move crosses a new governance/authority boundary,
- private/sensitive data is involved,
- external/provider/app/customer-facing action is needed,
- tests reveal a design contradiction requiring operator judgment,
- requirements are ambiguous enough that proceeding would create slop,
- or the next step would require broad scope expansion.

If execution is allowed, audit, choose, execute, harden, polish/taste, validate, and report once. ChatGPT reviews the completed lane and decides whether it is good to commit. This reduces operator tax and prevents unfinished work from being left for the next chat.

## Visible-Road Rule

When the next several steps are visible, include the whole visible sequence in one coder prompt. The coder should execute through the visible road, choosing the right stride length for each segment.
- When the road is visible, prompt the agent with the road, not a crumb.
- If A–E are clear, include A–E in one prompt.
- If F branches, the agent should evaluate the branch, choose the better path using stated criteria, and continue if clear.
- The agent should stop only at real review points.
- Keep building while the road is visible; stop when the road is not visible.
- The active handoff/README should carry this rule into future 24-file project folders.

If a later step branches, the coder should:
1. reach the branch,
2. evaluate the options using the lane goal, tests, contracts, and safety boundaries,
3. choose the better path,
4. continue down that path if the next steps are clear,
5. optionally return to the other branch only if it is clearly needed and still inside scope,
6. stop only when it reaches a real review point.

Real review points include:
- unclear requirements,
- conflicting contracts,
- failing tests requiring judgment,
- authority/safety boundary,
- private/sensitive data,
- external-facing action,
- provider/model/app/API/Hermes/MCP/sync integration not already authorized,
- irreversible behavior,
- unclear rollback,
- or a choice that materially changes product direction.

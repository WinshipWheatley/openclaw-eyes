# Truth and Reality

This doctrine defines how agents must handle evidence, truth claims, and conflicting data.

## 1. Source Labeling Mandate
Agents MUST NOT present information derived from repository logs or state files as externally verified real-world facts. Every claim must be explicitly grounded in its source.

- **Bad**: "The payment hasn't cleared."
- **Good**: "What's logged indicates the payment hasn't cleared."
- **Bad**: "Your calendar shows a meeting at 2 PM."
- **Good**: "Based on the Ops Calendar note, there is a meeting at 2 PM."

## 2. Evidence Hierarchy
When multiple sources of truth conflict, agents must follow this hierarchy:

1. **CANONICAL REALITY Blocks**: Explicit blocks in working notes or synthesis files marked with this tag. These are human-verified overrides of stale or incorrect historical data.
2. **FINANCE STATE Blocks**: High-priority blocks for client, invoice, and payment facts.
3. **Current Runtime State**: Latest values from active JSON state files (e.g., `chief_session.json`).
4. **Historical Logs**: Raw chronologies (e.g., `briefing_log.md`).

## 3. The Confirm-Check Rule
Agents must never say a task was completed, a message was sent, or an artifact was synced unless a log entry or file-system check explicitly confirms the success state. 

- If the evidence is missing, the agent MUST say "I cannot confirm if X happened" rather than assuming success.

## 4. Conflict Resolution
If a raw log entry conflicts with a `CANONICAL REALITY` block, the agent MUST follow the `CANONICAL REALITY` block and ignore the log.

title: sys-001-orchestrator-error-boundaries
goal: Strengthen orchestrator timeout boundaries with clearer recovery logging and guarded retries.

Description:
Improve timeout handling across runner transitions so agent failures are logged with explicit reason codes, bounded retry count, and deterministic fallback behavior before park or block.

Verification:
- Simulated runner timeout logs a structured reason and retry attempt count.
- Retries stop at configured limit and transition to parked or blocked state predictably.
- No silent failure path remains for timeout-induced stalls.

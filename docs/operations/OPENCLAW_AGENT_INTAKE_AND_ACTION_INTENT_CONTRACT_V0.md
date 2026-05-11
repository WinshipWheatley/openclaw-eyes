# OpenClaw Agent Intake and Action Intent Contract v0

## 1. Purpose
This contract extracts a reusable pattern already proven by:
- Business Ops Packet / intent gating
- Receipt taxonomy and proof coverage
- ProducerInput / ProducerReview / ToolIntentPacket
- Generated operator status read-models

## 2. Non-rebuild Rule
- Existing systems remain authoritative in their lanes.
- This contract maps and standardizes the pattern. Unification, not rebuild.
- No existing runtime is replaced.
- Existing lane-specific packets can continue to exist.

## 3. Universal Flow
- **Human Language / Trigger**: The initiating event.
- **IntakePacket**: Normalizes the initial request.
- **EvidenceContext**: Retrieves existing receipts to prove state.
- **DecisionPacket or ReviewPacket**: Deterministic judgment logic.
- **HumanResponse**: Human-readable output.
- **ActionIntentPacket**: (Optional) Formally proposed change or execution.
- **ApprovalGate**: Manual or policy-driven authorization.
- **ExecutionLane**: The dedicated lane where execution actually occurs (elsewhere).
- **Receipt**: Deterministic evidence of the executed action.
- **ReadModel**: Safe, non-blocking state updates reflecting receipts.

## 4. Agent Applicability
- **Cassandra**: Conversational front door / human response synthesis.
- **Chief**: Routing, coordination, execution ownership.
- **Guardian**: Approval/security decision packets.
- **Hermes**: Advisory systems-engineering packets.
- **Producer**: Creative review and tool-intent proposals.
- **Legal/Business Ops**: Bounded task packets and receipt-backed decisions.

## 5. IntakePacket Template Semantics
See `templates/agent/agent_intake_packet_template.json`. It normalizes intent but performs zero side-effects.

## 6. ActionIntentPacket Template Semantics
See `templates/agent/action_intent_packet_template.json`. It isolates proposed side-effects behind approval gates.

## 7. Evidence/Live-Claim Rule
No agent may claim a file, DAW, hardware device, email thread, GitHub repo, service, network, external account, or runtime is live/current/available unless deterministic evidence or a receipt proves it.

## 8. Side-Effect Rule
Default path is review/propose/respond only. Execution belongs to an execution lane after explicit approval and must produce receipts.

## 9. Producer as First Implementation Note
Producer is now a concrete early implementation: plain English → ProducerInput → ProducerReview → readable Producer response. Ableton/Logic/hardware actions remain suggested-only until gated execution exists.

## 10. Boundary
This document does not imply new authority. It does not imply Cassandra or Producer can execute tools directly. It does not imply Guardian/Chief rules are bypassed. It does not imply existing receipts prove whole-system health.

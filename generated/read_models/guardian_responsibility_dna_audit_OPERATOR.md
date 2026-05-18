# Guardian Responsibility + Deterministic DNA Audit v0

Status: `ready_for_specific_approval_request_contract_not_execution`
Guardian role: Guardian is the deterministic safety/HITL/security approval gatekeeper; Guardian is not an executor.

## Responsibility Map
- Specific action scope gatekeeper: `CANONICAL_DETERMINISTIC`
  - Role: Bind approval semantics to exact workflow/action scope, payload identity, TTL, idempotency, and receipts.
  - Not responsible for: generic authority, freeform shell approval, executor role
  - Safe next use: Use as the shape for future specific approval-request packets only.
- Start approval distinct from final send approval: `CANONICAL_DETERMINISTIC`
  - Role: Keep workflow start/preparation approval separate from any later final-send approval.
  - Not responsible for: treating start approval as send approval, opening Coupa/email/browser authority
  - Safe next use: Require final-send packets to cite distinct proof, draft, attachment, and Guardian approval conditions.
- Review, approval request, approval receipt, and execution separation: `CANONICAL_DETERMINISTIC`
  - Role: Preserve distinct lifecycle objects so review packets do not imply approval or execution.
  - Not responsible for: executing a reviewed action, creating receipts before a decision, approving generic future work
  - Safe next use: Add request packets before any receipt or execution wiring.
- Operator sovereignty and power-stage boundary: `CANONICAL_DETERMINISTIC`
  - Role: Fail closed at higher-power boundaries and keep current Stage 1 visibility/review-only posture explicit.
  - Not responsible for: operator behavior surveillance, hidden raw capture, crossing stages without controls
  - Safe next use: Keep Guardian approval-request generation read-model-only until higher-stage controls exist.
- Sensitive/no-go policy preservation: `TESTED_SUPPORTING_CONTRACT`
  - Role: Respect sensitive/no-go boundaries and avoid raw private content in normal read-models.
  - Not responsible for: raw private content ingestion, credential/OAuth access, legal/payment/contact raw storage
  - Safe next use: Reference no-go policy in future approval packets as boundary evidence.
- Operator Action SQLite spine: `TESTED_SUPPORTING_CONTRACT`
  - Role: Existing narrow SQLite request/approval/receipt pattern for allowlisted local actions.
  - Not responsible for: general remote builder, send authority, unbounded runtime execution
  - Safe next use: Borrow receipt/request discipline, not execution behavior, for Guardian approval rails.
- Legacy HITL/Telegram/JSON approval compatibility paths: `LEGACY_OR_REFERENCE`
  - Role: Current compatibility evidence and transport/reference surfaces that must be reconciled before expansion.
  - Not responsible for: new generic sends, new Telegram authority, declaring old JSON obsolete without migration proof
  - Safe next use: Keep as reference/compatibility until SQLite authority adapters exist.
- Cassandra and Capital Hilton review integration: `TESTED_SUPPORTING_CONTRACT`
  - Role: Guard later email approval by requiring governed draft, proof, attachment identity, and final-send gate conditions.
  - Not responsible for: Gmail draft creation, email send, Coupa/browser access, PDF attachment, spreadsheet mutation
  - Safe next use: Build approval-request rail that remains unavailable until exact prerequisites are modeled.
- Fixed-scope Cassandra recovery clearance: `IMPLIED_NOT_YET_CANONICAL`
  - Role: Special-case fixed-scope recovery approval/clearance evidence, not a general runtime model.
  - Not responsible for: general agent start/stop authority, recovery command expansion, unbounded service control
  - Safe next use: Leave out of draft approval rails except as no-general-runtime evidence.
- Future live external actions: `UNSAFE_OR_BLOCKED`
  - Role: Block until exact scope, proof, identity, receipt, and higher-stage execution controls exist.
  - Not responsible for: live Gmail, calendar mutation, Coupa/browser automation, credential/OAuth access, Telegram sends, runtime execution
  - Safe next use: Keep approval request generation separate from execution/connectors.
- Unknown future Guardian capability: `UNKNOWN_NEEDS_REVIEW`
  - Role: Fail closed when identity, scope, proof, authority, or source contract is unclear.
  - Not responsible for: implicit approval, silent authority expansion, private-life monitoring
  - Safe next use: Require a deterministic read-model/contract before implementation.

## Taxonomy
- Review packet: visibility/review only; not approval or execution.
- Approval request: specific immutable action scope with TTL/idempotency/payload hash.
- Approval receipt: exact decision/result evidence; not generic authority.
- Execution: future separately gated path; not enabled here.

## Start vs Final Send
- Start approval remains preparation-only and does not authorize send.
- Final-send approval remains future, specific to one draft and one attachment, and unavailable until governed proof exists.

## Blocked Authority
- generic approval authority
- runtime execution
- send/submit authority
- browser/Coupa automation
- credential/OAuth/token access
- Gmail draft or email send
- Telegram send
- calendar read/write
- spreadsheet mutation
- raw private content surveillance
- Repo B execution

## Cassandra / Capital Hilton
- Cassandra role: review-only draft packet producer, not executor
- Capital Hilton state: blocked_until_coupa_excel_draft_attachment_and_specific_guardian_gate_conditions_are_satisfied

## Next Safe Lane
`Guardian Draft Approval Request Contract v0`

## Authority Boundary
- Guardian is not modeled as executor: `false`
- Generic approval authority added: `false`
- Runtime/send/submit/browser/credential authority added: `false`

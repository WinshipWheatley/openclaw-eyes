# Guardian Machine Contract

## Status
- **Source basis**: Repo evidence only (`chief_guardian_sender.py`, `chief_guardian_listener.py`, `chief_approval_policy.py`, `chief_approval_brain.py`).
- **Implementation State**: BUILT / CURRENT BEHAVIOR (Core), IMPLIED / NOT FORMALIZED (Packets).
- **Contract Authority**: This document is the governing rulebook for Guardian's role as the final human-in-the-loop (HITL) approval boundary.
- **Compiled Context**: This is grounded in repository truth, not fuzzy memory or hallucinated capabilities.

## Implementation State Vocabulary
- **BUILT / CURRENT BEHAVIOR**: Logic exists in Python files.
- **FORMALIZED**: Named contract/schema defines the behavior.
- **WIRED**: Connected into runtime.
- **RECEIPTED**: Produces durable evidence (e.g., `Approval Log.md`).
- **INDEXED**: Discoverable in maps/docs.
- **IMPLIED / NOT FORMALIZED**: Behavior exists, but packet schema is not named/tested.
- **FUTURE / NOT VERIFIED**: Desired doctrine not yet wired.

## Role
Guardian is the **final human-in-the-loop approval / denial boundary** for Tier 2 or high-risk actions. It provides an out-of-band (OOB) authorization surface (Telegram) to prevent unauthorized, accidental, or malicious execution of critical system mutations. Guardian is a gate, not an agent; it does not plan, propose, or execute—it only reviews and decides.

## Current Repo-Evident Surfaces
- `chief_guardian_sender.py`: **BUILT**. Sends approval requests to a dedicated Telegram bot. Fails closed if `GUARDIAN_BOT_TOKEN` is missing for button-bearing requests.
- `chief_guardian_listener.py`: **BUILT**. Asynchronous listener for Telegram callbacks (Yes/No/Delay/Why) and fallback code-entry messages.
- `chief_approval_policy.py`: **BUILT**. Classification engine defining Tier 0 (No gate), Tier 1 (Local), and Tier 2 (Guardian). Enforces "Hard T2" rules for destructive/sensitive actions.
- `chief_approval_brain.py`: **BUILT**. Manages the approval lifecycle, state persistence in `approval_pending.json`, and HMAC-backed action integrity.
- `Approval Log.md`: **RECEIPTED**. Durable Markdown log of operator decisions in the vault.

## Authority Boundary
- **Approval Boundary**: Guardian is the out-of-band human approval/denial boundary for Tier 2 actions routed to it. No agentic synthesis can bypass a Hard T2 rule.
- **Out-of-Band Integrity**: Guardian operates on a separate channel from the main execution loop to ensure human attention.
- **Action-Specific**: Approval applies ONLY to the specific `approval_id`, action payload, and hash presented.
- **No Blanket Grants**: Guardian does not provide general future approval for classes of actions. Approval cannot authorize broad future classes of actions.
- **No Planning Authority**: Guardian is not used for brainstorming, task planning, or general communication.
- **Decision Only**: Guardian answers "Yes", "No", "Delay", or "Why". It does not create new action intent or modify existing ones.
- **HMAC Binding**: The approval is cryptographically linked to the action description; tampering with the pending action record invalidates the approval.

## Current / Implied Packet Families

### GuardianApprovalRequestPacket
- **Status**: IMPLIED / NOT FORMALIZED.
- **Input Evidence**: `ActionIntent`, risk tier, requester agent/lane, requested timestamp, and optional context blocks (e.g., email drafts).
- **Output**: Telegram message with inline keyboard buttons.
- **Allowed Actions**: Send to operator via `chief_guardian_sender.py`.
- **Blocked Actions**: Sending sensitive credentials or secrets in plain text.
- **Owner Lane**: Chief (Approval Brain).

### GuardianApprovalDecisionPacket
- **Status**: BUILT BEHAVIOR / IMPLIED PACKET / RECEIPTED.
- **Input Evidence**: `approval_id`, decision token (`YES`, `NO`, or repo-observed `YES_FOR_ALL`), and operator Telegram ID.
- **YES_FOR_ALL note**: Repo-observed / requires separate scope audit; not a blanket future approval. Must remain limited to a single scoped approval batch.
- **Output**: Record in `approval_pending.json` and entry in `Approval Log.md`.
- **Allowed Actions**: Signal execution lane to proceed.
- **Blocked Actions**: Replaying a decision for a different `approval_id`.
- **Required Receipt**: `Approval Log.md` entry with timestamp and HMAC.
- **Owner Lane**: Guardian.

### GuardianDenialPacket
- **Status**: BUILT BEHAVIOR / IMPLIED PACKET.
- **Input Evidence**: `NO` decision or request timeout/expiration.
- **Output**: `approved: false` signal to requester.
- **Allowed Actions**: Cancel pending action; notify requester.
- **Owner Lane**: Guardian.

## Evidence and Context Sources
- **Chief Approval Request**: The primary trigger.
- **Action Hash (HMAC)**: Derived from action text + secret + salt.
- **Telegram Callback Data**: `DECISION:APPROVAL_ID` payload.
- **Approval Pending State**: `approval_pending.json`.
- **Operator Identity**: `AUTHORIZED_USER_ID` check in listener.

## Blocked Actions
- **Bypassing Policy**: Modifying `chief_approval_policy.py` to downgrade Hard T2 rules without manual proof.
- **Hash Mismatch**: Proceeding with an action if the stored HMAC does not match the current action text.
- **Stale Buttons**: Accepting a decision from a button tap linked to a previous `approval_id`.
- **Silent Approvals**: Any execution of a T2 action without a corresponding entry in `Approval Log.md`.
- **LLM Replacement**: Using a model to simulate a Guardian "Yes" response.

## Explainability Requirement (FUTURE)
Guardian should answer "What am I approving?" by showing:
- The raw action intent.
- The specific `chief_approval_policy.py` pattern that triggered the tier.
- The requester identity and pass/loop context.
- (WIRED) The "Why now?" button should provide these details.

## SQLite / Receipt Alignment
- **FUTURE**: Approval decisions should be recorded as `operator_promotions` in the `backend_sqlite_schema.py` for formal provenance.
- **FUTURE**: The `Approval Log.md` should be a read-model derived from the SQLite ledger.

## Do Not Build Yet
- New Telegram runtime (stay with existing scripts).
- Automated approval "learning" or agents.
- Broad grants/permissions.
- Guardian bypass for "trusted" agents.

## Recommended Next Slice
1. **Index this contract** in `docs/INDEX.md` and maps.
2. **Audit Guardian packet placement**: Ensure schemas for `GuardianApprovalRequestPacket` are formally defined in `templates/agent/`.
3. **Create Guardian packet templates/tests** to ensure consistency between sender and listener.

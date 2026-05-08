# 07 Authority and Covenant Rules

## The Sacred Pause
Natural language intent is not execution authority. The Action Covenant is the system's sacred pause before power.

## Restricted Lanes (Blocked)
The following lanes remain blocked and require explicit future authority:
- **Runtime Launch**: No live service launch, process scans, or runtime mutation.
- **MCP/Shared Memory**: No hidden canonical memory writes or external MCP calls.
- **Provider/API Calls**: No live provider connections or external API calls.
- **Money/Legal/Private**: No invoice generation, bank access, legal content access, or private-root inspection.
- **External Sends**: No emails, SMS, or Telegram messages.
- **Destructive Actions**: No broad filesystem deletion or Packet 08 creation.

## Covenant Mechanics
- **Evidence grounds response**: Action must be based on repo receipts and tests.
- **Covenant governs power**: An Action Covenant defines the action, risk, authority, evidence, and rollback.
- **Exact Approval**: Commands like "go ahead" or "do it" require a valid pending Action Covenant and may require an exact confirmation phrase (e.g., `APPROVE cov_ID`).

## Forbidden Drift
- **Receipts != Approval**: A passing receipt proves readiness/state; it does not grant execution permission.
- **Vague Authorization**: Do not accept "just handle it" as authority for restricted domains.

---
**Authority Backpointers:**
- `operator_action_covenant.py` (Implementation Authority)
- Packet 07 File 19: `GATED_ACTIVATION_READINESS_MAP.md`
- Packet 07 File 22: `MCP_SHARED_MEMORY_AND_HIDDEN_AUTHORITY_GATES.md`

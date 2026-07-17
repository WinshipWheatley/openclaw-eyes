# Activation Record: Subscription External-Brain Router

- Capability: `external_brain_router`
- Owner driving proof and review: Fable
- Builder: PC Codex Desktop
- Default state during build: OFF
- Target off-window: hours; shadow proof in this or the next session
- Operator activation: one explicit operator tap after all proof criteria pass
- Live activation authority in this build: none

## Proof Required Before The Tap

1. Shadow receipts prove subscription usage below 80% admits only ChatGPT-subscription transport.
2. At or above 80%, no external thread or turn starts without a verified, scoped, unexpired
   Guardian operator approval. While approval is absent or ambiguous, the live path remains local.
3. Legal/MAX data remains local unless fully tokenized and minimized; raw values, unresolved
   sensitive values, and secrets always remain local.
4. The raw operator prompt reaches the advisory model verbatim, with minimized context attached as a
   separately labeled aid.
5. Local fallback output and authority behavior remain at parity with the existing Ollama path.
6. External turns are ephemeral, read-only, approval-never, network-disabled, and return text only.
7. Receipts contain only safe metadata: lane, effort and reason, privacy verdict, usage/window,
   binding id, fallback reason, and hashed request/thread ids.

## 80% Guardian Boundary

Crossing the 80% included-usage threshold creates an approval request, not an external call and not
automatic paid-credit use. Any approval must bind the request hash, lane, effort, usage window,
expiry, and bounded use count. It grants no purchase, top-up, payment, send, tool, write, delete, or
other authority. Delivery and activation of that approval remain subject to the fleet's verified
operator-present gate.

## Activation And Rollback

- Activation: the operator explicitly enables `OPENCLAW_EXTERNAL_BRAIN_ROUTER` after reviewing the
  proof receipt set; Fable records the tap and live canary receipt.
- Immediate rollback: unset `OPENCLAW_EXTERNAL_BRAIN_ROUTER`; keep the existing local Ollama route.
- Rollback trigger: any privacy leak, raw-prompt mutation, unreadable headroom, approval mismatch,
  unexpected authority, protocol failure, model absence, or local-parity regression.
- Binding swaps do not constitute activation and are not part of rollback.

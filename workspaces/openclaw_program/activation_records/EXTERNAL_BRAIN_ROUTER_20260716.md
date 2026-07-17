# Activation Record: Subscription External-Brain Router

- Capability: `external_brain_router`
- Owner driving proof and review: Fable
- Builder: PC Codex Desktop
- Default state during build: OFF; live state after proof: ON behind the guarded runtime flag
- Operator activation: binding activation directive applied after the real-process canary passed
- Live transport: dedicated `/home/openclaw/.nvm/versions/node/v24.14.0/bin/codex app-server`
- Required app-server version: exactly `0.144.5`

## Verified Evidence — 2026-07-16

- Real model catalog: ChatGPT auth asserted; Luna, Terra, and Sol bindings all present.
- Live headroom preflight: Pro subscription, 14% used in the 10080-minute window; no thread or turn
  started during preflight.
- Money boundary: a real child handshake with a synthetic 80% rate response returned
  `guardian_approval_required` after `account/rateLimits/read`; no `model/list`, `thread/start`, or
  `turn/start` occurred.
- PUBLIC canary: `PUBLIC-CANARY-OK` returned through `protected_generate`; route was
  `external_brain_router`, app-server `0.144.5`, Terra at medium effort, external invoked true,
  local invoked false, fallback reason empty.
- Focused regression: 84 router, adapter, protected-generate, and activation-register tests passed.
- Safe canary receipt:
  `/home/openclaw/Operator/from-codex/EXTERNAL-BRAIN-PUBLIC-CANARY-20260716-PC-Codex-Desktop.jsonl`.

## Router v2 Evidence — 2026-07-17

- The existing guarded runtime now makes the WORK call one capability tier above
  the nominal task grade: easy to mid, mid to hard, with hard capped at hard.
  Binding-default effort follows the promoted work lane; explicit effort remains
  an independent override.
- The same read-only subscription turn must return both `answer` and a structured,
  turn-grounded `packet_critique`. Missing or malformed critique output fails to
  the existing local route.
- Packet delivery records the original packet hash/id, build time, builder name,
  delivery builder version, and builder config hash. Raw operator prompts and
  answer text are not written to packet-quality telemetry.
- Packet-quality reports are active in
  `/home/openclaw/.openclaw/business_ops/ledger.sqlite`, with validated work
  evidence required before a task class can become eligible for lower-lane trials.
  Model self-score alone cannot graduate a class.
- Real PUBLIC v2 canary: nominal easy promoted to Terra/mid at medium effort,
  exact marker observed, packet critique score 85, Pro window 18% used, and report
  `sha256:b6ad523249fa2aebbcd54a905696545a` was durably recorded and validated by
  `external_brain_canary:exact_public_marker`.
- Updated money boundary: real dedicated 0.144.5 child handshake plus synthetic
  80% usage refused the promoted mid-lane call with
  `guardian_approval_required`. Observed methods stopped at `initialize`,
  `account/read`, and `account/rateLimits/read`; no `model/list`, `thread/start`,
  or `turn/start` occurred.
- Focused v2 regression: 113 router, app-server, runtime, telemetry,
  protected-generate, work-package-router, and model-policy tests passed.

## Proof Gate — Passed

1. Shadow receipts prove subscription usage below 80% admits only ChatGPT-subscription transport.
2. At or above 80%, no external thread or turn starts without a verified, scoped, unexpired
   Guardian operator approval. While approval is absent or ambiguous, the live path remains local.
3. Legal/MAX data remains local unless fully tokenized and minimized; raw values, unresolved
   sensitive values, and secrets always remain local.
4. The raw operator prompt reaches the advisory model verbatim, with minimized context attached as a
   separately labeled aid.
5. Local fallback output and authority behavior remain at parity with the existing Ollama path.
6. External turns are ephemeral, read-only, approval-never, network-disabled, and
   return answer plus packet critique only; the application publishes only the answer.
7. Receipts contain only safe metadata: nominal/work lane, effort and reason, privacy verdict, usage/window,
   binding id, fallback reason, and hashed request/thread ids.
8. Packet-quality telemetry stores critique summaries/items and build provenance,
   never raw prompts, packet bodies, or answer text. Regression comparisons name
   the last known-good builder/config version for a controlled code/config revert.

## 80% Guardian Boundary

Crossing the 80% included-usage threshold creates an approval request, not an external call and not
automatic paid-credit use. Any approval must bind the request hash, lane, effort, usage window,
expiry, and bounded use count. It grants no purchase, top-up, payment, send, tool, write, delete, or
other authority. Delivery and activation of that approval remain subject to the fleet's verified
operator-present gate.

## Activation And Rollback

- Activation: `OPENCLAW_EXTERNAL_BRAIN_ROUTER=1` is installed on the owning request/response
  service after the proof receipt set passes.
- Immediate rollback: unset `OPENCLAW_EXTERNAL_BRAIN_ROUTER`; keep the existing local Ollama route.
- Rollback trigger: any privacy leak, raw-prompt mutation, unreadable headroom, approval mismatch,
  unexpected authority, protocol failure, model absence, or local-parity regression.
- Binding swaps do not constitute activation and are not part of rollback.

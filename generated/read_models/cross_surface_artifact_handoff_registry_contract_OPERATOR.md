# Cross-Surface Artifact Handoff Registry v0

## ELIOPERATOR

This is the OpenClaw post office contract. It does not move files by itself, watch folders, import Mac packages, run Telegram, launch agents, or send anything externally.

The problem it solves: Mission Control can emit a capture request, Repo A can consume it, Repo A can publish readback, and Mission Control can render the result. That loop works, but each lane has been using one-off shuttle language. The post office gives those artifacts a common envelope.

A handoff records what the artifact is, which schema validates it, which world/lane/block/session it belongs to, who originated it, which handler should process it, what authority boundary applies, what privacy boundary applies, and what readback the operator should see.

Lifecycle is status, not permission. WRITTEN means OpenClaw saved local state. RENDERED means a surface showed the result. Neither means approved, sent, submitted, or externally executed.

Mission Control, Telegram, Cassandra, Chief, Guardian, Hermes, Niles, and future client apps are surfaces or fronting actors. They do not own workflow truth. The backend receipt/state/readback substrate owns canonical local truth.

Protected values stay protected. Normal handoffs can carry safe labels, tokenized_value_ref, protected_store_ref, privacy_class, and sensitivity_class. They cannot carry raw contact routes, raw payment references, raw proof bodies, credentials, cookies, tokens, or private documents.

Builder warnings are fail-closed. UI-coupled packets, raw protected payloads, missing schema, missing idempotency, fake artifact hashes, send-ready claims without approval, copied calculated state, and cross-tenant leaks are blocked before routing.

## What It Does Not Do Yet

- No live bus.
- No file watcher.
- No automatic Mac import.
- No automatic PC consume.
- No live Telegram integration.
- No model, agent, or tool dispatch.
- No external email, Coupa, browser, or approval action.

## Capital Hilton Examples

- Performance dates capture maps to `mission_control_capture_request_intake`.
- PO/Coupa delivery facts capture maps to `capital_hilton_delivery_facts_capture_writer`.
- Reusable fact handoff references the tokenization contract and forbids raw values.
- Telegram/Cassandra can front the same backend handler without owning truth.
- Approval/send remains blocked unless an approval receipt and gated adapter exist.

## Machine Proof

- All live authority flags false: True
- External authority false in modeled boundaries: True
- Raw private bodies included: False
- Raw sensitive fixture values included: False
- Content hash: `sha256:ff11cc56d8e788987359b14e9a009c9248b6a88e3c1a8eb53899f4dc38a8dc44`

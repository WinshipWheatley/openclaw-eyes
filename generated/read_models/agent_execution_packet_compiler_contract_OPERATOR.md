# Agent Execution Packet Compiler Contract v0

## ELIWINSHIP Summary

An execution packet is a focused assignment for an agent. It says: here is the current block, here is the exact objective, here is the allowed context, here is what is excluded, here are the allowed and blocked capabilities, here is the expected return shape, and here is when to stop.

This does not build a new runtime. The existing Context Selection / Knowledge Packet layer already handles substrate evidence packet selection. This contract sits above it and defines how workflow blocks compile into agent assignment packets without giving the agent the whole system.

Agents receive focused packets because one huge context dump makes them less reliable. Multi-step work should become multiple small packets: classify intent, fill the active block, ask the missing question, prepare a preview shape, prepare approval if prerequisites exist, and stop when send/execution would be required.

Tools, MCPs, scripts, and hooks are capabilities, not authority. A packet can list what would be allowed or blocked, but this contract does not run any capability. Browser, Coupa, Gmail, Telegram send, credentials, file write, invoice generation, email send, and approval submission stay blocked.

Telegram/Cassandra and Mission Control can share workflow state because both compile from the same block/draft/session refs. The surface can differ; the packet shape stays consistent.

Compact operator context hints help an agent explain unfamiliar domains without being patronizing. The hint can say to use a studio signal-flow or ship/bridge analogy when useful, but it should not become a personal dossier or passive advice.

No live execution exists yet. Deterministic validation decides what happens next. Receipts and gates handle durable state or action later.

## Existing-Build Boundary

- Existing substrate inspected: `context_selection_knowledge_packet_v0`.
- Boundary: Context Selection already compiles deterministic evidence/knowledge packets from the substrate.
- This contract gap: Defines workflow-block to agent assignment packet selection, capability filtering, return shapes, and packet chains.

## Examples

- Capital Hilton dates: normalize added dates from the active draft and return structured field updates or ambiguity flags.
- Capital Hilton PO proof: identify likely proof/reference targets from source cards and proof refs; no Coupa/browser/credential access.
- Invoice preview: model preview-prep shape only; invoice preview render remains future-gated and not executed.
- Telegram/Cassandra request chain: intent classification, block fill, missing-question handoff, draft preview prep, approval prep, send blocked.
- Chief/check-engine: current read-model/test refs only; return concise blocker briefing or Engineering Contained; no shell/repair/broad scan.
- Out-of-depth support: use compact operator context hints to explain PO/Coupa with familiar analogies and workflow choices, without patronizing.

## Starship Alignment

- Bridge: compiles focused orders.
- Crew: receives packets, not the whole ship.
- Engineering: supplies proof/context below deck.
- Captain: gets handoff only when needed.
- Guardian: handles sensitive gates.
- Ship logs: future receipts/proofs prove later commits.
- Shipyard: Shipyard packets are separate from normal world work.

## Still Blocked

- No packet execution, live agent execution, model call, tool/MCP/script/hook execution, receipt/state write, invoice generation, invoice preview render, email draft/send, browser/Coupa/Gmail/Telegram access, credential handling, approval submission, queue/runtime dispatch, file write/cleanup, raw body ingestion, network, Mac sync/import, Mission Control Swift change, or push.

## Machine Proof Summary

- Execution packets: `6`.
- Compilers: `4`.
- Context policies: `4`.
- Capability policies: `5`.
- Return shapes: `6`.
- Packet chains: `2`.
- Operator context hints: `1`.
- Does not duplicate existing context selection: `true`.
- Packets narrow/focused: `true`.
- All authority flags false: `true`.
- Content hash: `sha256:ec3dd238a1565a27fe67ce249e51838682c3c77b912b8b35b0b8d93b271bf228`.

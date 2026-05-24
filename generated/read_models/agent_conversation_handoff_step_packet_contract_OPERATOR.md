# Agent Conversation Handoff / Step Packet Contract v0

## ELIWINSHIP Summary

Winship can talk to an agent in Telegram, Mission Control, or a future surface. The agent does not get the whole ship. The system gives the agent a focused step packet with only the workflow refs, draft refs, proof refs, stop conditions, and return shape needed for that step.

The agent talks to the system below deck. Packet requests, proof lookup requests, validation requests, and draft returns do not spam Winship. They are summarized only when they become a crew briefing, decision request, draft review, or useful status update.

When operator judgment is needed, the agent hands back cleanly: here is the concise summary, here is why you are needed, here are the choices, and here is what will stay blocked. Proof stays one level down unless summoned.

Liveness matters because typing is not enough. Complex workflow help needs to distinguish thinking, making packet, waiting on the system, waiting on Winship, validating, returning briefing, stalled, offline, and timed out. The operator should never wonder whether something is working or silently dead.

Telegram and Mission Control can render the same handoff state. Telegram may show compact text like Cassandra is preparing packet. Mission Control may show a calm status chip. Bridge shows only captain-relevant waiting, blocked, stalled, or handoff states.

No live authority exists here. No agent runs, no model is called, no message is sent, no receipt/state write happens, no invoice/email/browser/Coupa/Gmail/Telegram action occurs, and no workflow state is mutated.

## Examples

- Telegram/Cassandra invoice: Send Capital Hilton an invoice for this week's and last week's job. Cassandra receives focused packets, returns draft intents or missing questions, and keeps invoice draft/send approval gated.
- Mission Control draft: a block edit can create the same draft-review packet shape an agent would receive from Telegram.
- Chief/check-engine: What is blocking the build? Chief gets current read-model/test refs only and returns a concise blocker briefing.
- Guardian approval: Guardian prepares an approval question only when prerequisites exist; no send authority is created.
- Offline/stalled: Cassandra appears stalled while preparing the invoice packet. No action was taken. Resume, retry, or park?
- Operator/system update: system tells the agent `Performance dates draft changed; prior packet stale.` and shows Winship `Cassandra is updating from your latest draft.`.

## Starship Alignment

- Captain: operator.
- Bridge: captain-level attention.
- Worlds: domain work.
- Crew: agents that translate, propose, and brief.
- Engineering: packet compilation, proof, validation, liveness, and status below deck.
- Ship Logs: future receipts/proofs.
- Crew briefings: operator handoff packets.
- Status/liveness: calm crew visibility so the captain knows thinking, making packet, waiting, offline, or stalled.
- Red Alert: Red Alert only when captain decision is required before safe continuation.

## Still Blocked

- No live agent execution, model call, Telegram/message send, tool/MCP/script/hook execution, receipt/state write, invoice generation, email draft/send, browser/Coupa/Gmail/Calendar/account access, credential handling, approval submission, queue/runtime dispatch, file write/cleanup, raw body ingestion, network, Mac sync/import, Mission Control Swift change, or push.

## Machine Proof Summary

- Handoff sessions: `6`.
- Step packets: `6`.
- Agent/system exchanges: `7`.
- Operator handoff packets: `6`.
- Liveness statuses: `8`.
- Timeout policies: `3`.
- Visibility policies: `2`.
- Packets focused/narrow: `true`.
- Required status states present: `true`.
- All authority flags false: `true`.
- Content hash: `sha256:94dd6c4443a88e210ccc2ec3711f3a1075dd18d638e87e34a766134a0333ee27`.

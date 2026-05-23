# Bridge Routing / Operator Attention Contract v0

## ELIWINSHIP Summary

Bridge routes. Worlds do work. Engineering stays below deck.

The Helm should feel calm because it only shows captain-level attention: a real decision, a real route into a World, or a true safety block. It should not become a wall of proof, sync status, debug cards, or completed machine details.

Normal flight should be quiet. If the ship is working, Winship should not have to stare at engine-room telemetry. Proof, receipts, sync health, tests, generated read-model detail, and debug state remain inspectable one level down.

Worlds are where domain work happens. Capital Hilton belongs in Finance World, with Helm showing only a short marker like Finance needs attention. Security review belongs in Security World unless safe continuation requires a Red Alert decision.

Shipyard Mode is for building or repairing the ship. Chief/check-engine, dirty state, validation, sync repair, and developer noise live there unless they block an active mission.

Crew briefings are concise decision or update packets. Cassandra, Clara, Chief, Guardian, Hermes, Niles, and future agents brief; they do not spam Helm, own truth, approve actions, or execute work.

This is systems engineering, not Star Trek theming. The metaphor is just the routing model: captain, bridge, worlds, crew, engineering, logs, and shipyard each have a job.

## Routing Examples

- Capital Hilton: Helm shows Finance needs attention, Finance World shows invoice blocks and local draft, Below Deck holds proof/Coupa refs/receipts/source detail.
- Capital Hilton approval locked: Helm does not show a raw proof wall; Finance World shows locked prerequisites; Guardian briefs only when approval is actually ready or needed.
- Chief/check-engine: Shipyard handles build troubleshooting. Helm is interrupted only when an active mission cannot proceed without a captain decision.
- Sync health mismatch: repaired or contained mismatch stays Engineering Contained or Quiet Log Only; mission-blocking read-model staleness can promote to Yellow or Red.
- Telegram/Cassandra request: a conversation proposal becomes a workflow block draft; Helm may show a draft-ready marker only if a captain review choice exists.

## Alert Policy

- Normal Flight: quiet by default.
- Yellow Alert: visible, nonblocking attention that routes to a World.
- Red Alert: safe continuation requires a captain decision.
- Engineering Contained: crew handled or logged it below deck.
- Shipyard Mode: explicit build/troubleshooting surface.
- Quiet Log Only: traceable and inspectable, never interrupting.

## Still Blocked

- No Helm/World/Crew action execution, receipt write, state write, approval submission, invoice generation, email/Telegram send, browser/Coupa/Gmail/Calendar/account access, credential handling, model/tool/agent/runtime/queue execution, file write/cleanup, raw body ingestion, network, Mac sync/import, Mission Control Swift change, or push.

## Machine Proof Summary

- Doctrine: Bridge routes; Worlds do work; Engineering stays below deck.
- Attention records: `7`.
- Routing decisions: `7`.
- World surfaces: `4`.
- Below deck details: `7`.
- Crew briefings: `6`.
- Shipyard records: `2`.
- Alert policies: `6`.
- Capital Hilton routes to Finance World: `true`.
- Proof/debug below deck by default: `true`.
- All authority flags false: `true`.
- Content hash: `sha256:c9f97759efee20e9bdb77382515263067697f7c74b8340abb2b97121666b8673`.

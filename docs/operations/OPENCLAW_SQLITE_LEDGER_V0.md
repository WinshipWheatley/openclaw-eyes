# OpenClaw SQLite Ledger v0

## Purpose
The SQLite Ledger v0 serves as an append-only receipt layer for the Business Ops Spine. It records operator events, context packets, capability decisions, retrieval attempts, and side effects to provide a deterministic and auditable trail of system behavior.

See the [Business Ops Receipt Taxonomy v0](./OPENCLAW_RECEIPT_TAXONOMY_V0.md) for the definitive list of event types and safety boundaries.

## Non-Goals
- **State Management**: This is NOT a replacement for live runtime state (e.g., HITL pending stores, active email thread state).
- **Migration**: Existing JSON/JSONL logs are not being migrated to this ledger in v0.
- **Sensitive Data Storage**: Raw private content (Gmail bodies, PII, etc.) MUST NOT be stored in this ledger.

## Map Room vs SQLite Ledger
- **Map Room**: A high-level architectural view of components and their relationships.
- **SQLite Ledger**: A low-level execution trace of specific operator requests and decisions.

## Sensitive Data Rule
No raw sensitive data should enter the ledger. Use summaries, hashes, or boolean flags (`raw_sensitive_data_stored=False`) to indicate that sensitive data was handled elsewhere.

## Table Overview
1.  **events**: Root table for every operator interaction. Includes `orientation_snapshot_receipt` events.
2.  **packets**: Captures the `BusinessOpsPacket` snapshot (intent, actor, permitted capabilities).
3.  **capability_decisions**: Explicit logs of which capabilities were allowed or forbidden.
4.  **retrieval_receipts**: Logs data retrieval attempts (e.g., "Tried to fetch Gmail metadata").
5.  **side_effects**: Logs external actions taken or proposed (e.g., "Drafted an email").
6.  **operator_explanations**: Natural language summaries of what happened, safe for display to users.

## Recording Receipts
The Orientation Snapshot tool (`scripts/orientation_snapshot.py`) can record receipts to this ledger using the `--record` flag. This creates an `orientation_snapshot_receipt` event with a compact summary of the system state.

## Inspection CLI
A read-only CLI tool is available for auditing the ledger: `scripts/inspect_business_ops_ledger.py`.

### Usage
- `python scripts/inspect_business_ops_ledger.py --summary`: Shows table row counts and event type distribution.
- `python scripts/inspect_business_ops_ledger.py --latest 10`: Shows the 10 most recent events.
- `python scripts/inspect_business_ops_ledger.py --latest 5 --event-type orientation_snapshot_receipt`: Filters by event type.
- `python scripts/inspect_business_ops_ledger.py --summary --json`: Outputs the summary in machine-readable JSON format.

The tool is strictly read-only and truncates long fields for safer terminal display.

## Why Append-Only First?
Append-only receipts ensure that we don't accidentally corrupt or overwrite historical audits. It simplifies the implementation and minimizes the risk of side effects on the core system.

## Future Migration Path
Eventually, HITL stores and email thread state will be moved into this SQLite environment, allowing for complex queries like "Show me all pending actions across all actors."

## Example Debug Questions
- "Show me the packet for your last answer."
- "Did Gmail get touched?"
- "What evidence did you use?"
- "What approval gate blocked this?"

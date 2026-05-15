# OpenClaw Agent Work Packet v0

Status: implemented backend substrate.

Agent Work Packet v0 turns a routed intent into a bounded planning packet that can be handed to a future Codex/local worker. It is a draft/proposal artifact only.

## Source

- Reads `intent_records` and `intent_context_links`.
- Links to generated read-models and safe SQLite report surfaces.
- Writes `agent_work_packet_*` tables in the Business Ops ledger.

## Tables

- `agent_work_packet_runs`
- `agent_work_packets`
- `agent_work_packet_context_links`
- `agent_work_packet_allowed_surfaces`
- `agent_work_packet_blocked_surfaces`
- `agent_work_packet_command_candidates`
- `agent_work_packet_receipts`

## Generated Surfaces

- `generated/read_models/agent_work_packets.json`
- `generated/read_models/agent_work_packets_OPERATOR.md`

## Commands

Build from latest or explicit intent:

```bash
python3 scripts/build_agent_work_packet.py --intent-id <intent_id> --format operator
```

Build the sample Chief Markdown reorg packet:

```bash
python3 scripts/build_agent_work_packet.py --sample-markdown-reorg --format operator
```

Query:

```bash
python3 scripts/query_agent_work_packets.py --report summary --format operator
python3 scripts/query_agent_work_packets.py --report latest --format operator
```

Export:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/export_agent_work_packets_read_model.py --format operator
```

## Boundary

- Planning packets only.
- No execution.
- No action request creation.
- No approval bypass.
- No agent activation.
- No model calls.
- No tool or network authority.
- No file moves/deletes/renames.
- No private/no-go raw content.

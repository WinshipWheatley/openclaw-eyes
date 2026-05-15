# OpenClaw Overnight Usefulness Stack v0 Report

Status: completed with one mirror-sync attention item.

This lane advanced the backend toward: "Agent X, do Y with that new file." It did not start agent runtime readiness, activate agents, execute actions, call models, modify Mission Control, or grant runtime/tool authority.

## Phases Completed

1. Recent File Context Resolver v0
   - Commit: `a86ab37 feat(files): add recent file context resolver`
   - Adds metadata-only resolution for phrases like `that new file`, `the new Logic file`, and `that Markdown doc`.
   - Live read-model: `recent_file_context.json`, `recent_file_context_OPERATOR.md`
   - Live counts: 100 candidates, 0 resolution queries.

2. Approved Markdown Evidence Ingestion v0
   - Commit: `fb917d0 feat(markdown): ingest approved markdown evidence`
   - Adds bounded heading/excerpt ingestion for approved Markdown only.
   - Live read-model: `markdown_evidence.json`, `markdown_evidence_OPERATOR.md`
   - Live counts: 6 sources, 103 evidence items.

3. Intent Router + Recent File Context Integration v0.1
   - Commit: `b498d63 feat(intent): link router to recent file context`
   - Routes file-context intents through `recent_file_candidates` metadata.
   - Live read-model updated: `intent_router.json`, `intent_router_OPERATOR.md`
   - Live counts: 5 intents, 4 routed, 1 needs review.

4. Agent Work Packet v0
   - Commit: `ae6897f feat(agents): add bounded agent work packets`
   - Adds draft planning packets from routed intents.
   - Live read-model: `agent_work_packets.json`, `agent_work_packets_OPERATOR.md`
   - Live counts: 1 packet.

5. Mirror runner hardening during hygiene
   - Commit: `951e577 fix(sync): handle stale mirror mismatches in runner`
   - Fixes operator output when missing expected files and hash mismatches coexist.
   - Writes Mac sync request marker when backend has newer generated read-models.

## Tables Added

Recent File Context:
- `recent_file_context_runs`
- `recent_file_candidates`
- `recent_file_aliases`
- `recent_file_resolution_queries`
- `recent_file_context_links`
- `recent_file_rejections`

Approved Markdown Evidence:
- `markdown_evidence_runs`
- `markdown_evidence_sources`
- `markdown_evidence_items`
- `markdown_evidence_query_receipts`

Agent Work Packets:
- `agent_work_packet_runs`
- `agent_work_packets`
- `agent_work_packet_context_links`
- `agent_work_packet_allowed_surfaces`
- `agent_work_packet_blocked_surfaces`
- `agent_work_packet_command_candidates`
- `agent_work_packet_receipts`

Intent Router schema was not replaced; it now links to Recent File Context rows.

## New Generated Read-Models

- `generated/read_models/recent_file_context.json`
- `generated/read_models/recent_file_context_OPERATOR.md`
- `generated/read_models/markdown_evidence.json`
- `generated/read_models/markdown_evidence_OPERATOR.md`
- `generated/read_models/agent_work_packets.json`
- `generated/read_models/agent_work_packets_OPERATOR.md`

Updated:
- `generated/read_models/intent_router.json`
- `generated/read_models/intent_router_OPERATOR.md`

## Tests

Phase 1:
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_recent_file_context.py tests/test_file_event_queue.py tests/test_markdown_knowledge_atlas.py -q`
- Result: 26 passed.

Phase 2:
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_markdown_evidence_ingestion.py tests/test_markdown_knowledge_atlas.py tests/test_evidence_kettle.py tests/test_context_selection.py -q`
- Result: 29 passed.

Phase 3:
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_intent_router.py tests/test_recent_file_context.py tests/test_agent_lane_registry.py tests/test_operator_action_inbox.py -q`
- Result: 42 passed.

Phase 4:
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_agent_work_packet.py tests/test_intent_router.py tests/test_agent_lane_registry.py tests/test_context_selection.py -q`
- Result: 36 passed.

Sync runner fix:
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_sync_read_model_mirror.py tests/test_read_model_mirror_automation.py tests/test_mac_mirror_atlas.py -q`
- Result: 32 passed.

## Current Mirror Health

The PC/WSL backend canonical generated read-model set has advanced to 40 files. The latest imported Mac manifest is stale:

- canonical_expected=40
- observed=34
- missing_expected=6
- extra=0
- hash_mismatch=2
- matched_hash=32

Missing on Mac mirror:
- `agent_work_packets.json`
- `agent_work_packets_OPERATOR.md`
- `markdown_evidence.json`
- `markdown_evidence_OPERATOR.md`
- `recent_file_context.json`
- `recent_file_context_OPERATOR.md`

Stale hash on Mac mirror:
- `intent_router.json`
- `intent_router_OPERATOR.md`

Request marker written:
- `/mnt/e/openclaw/shuttle/to_mac/read_model_sync_required.json`

Next Mac command:

```bash
cd ~/Developer/OpenClawBackend/openclaw
PYTHONDONTWRITEBYTECODE=1 python3 scripts/sync_read_model_mirror.py --pull --format operator
```

The bounded wait loop checked 10 times over about 10 minutes and the mirror did not clear. Do not mark the mirror healthy until the Mac sync agent runs and PC/WSL imports the refreshed manifest.

## What OpenClaw Can Now Do

- Record recent file candidates from File Event Queue metadata.
- Resolve simple recent-file phrases conservatively.
- Recognize Logic project metadata as `music_art` / Niles-safe context, metadata-only.
- Link routed intents to Recent File Context without raw file reads.
- Ingest approved Markdown headings/excerpts as parsed evidence, not truth.
- Build bounded draft Agent Work Packets from routed intents.
- Export all new posture as generated read-model files.

## Still Blocked

- No agent runtime activation.
- No model calls.
- No arbitrary shell.
- No auto-approval or auto-execution.
- No Telegram API wiring.
- No Mission Control write path in this lane.
- No file moves/deletes/renames/reorg.
- No private/no-go raw reads.
- No client deployment.
- Mac read-model mirror is stale until the Mac sync agent processes the request marker.

## Next Lane Inspect List

The next queued lane, Agent Runtime Readiness + Start Sequence v0, should inspect:

- `agent_lane_registry.py`
- `intent_router.py`
- `recent_file_context.py`
- `markdown_evidence_ingestion.py`
- `agent_work_packet.py`
- `operator_action.py`
- `operator_action_inbox.py`
- `file_event_queue.py`
- `context_selection.py`
- `generated/read_models/agent_lanes.json`
- `generated/read_models/intent_router.json`
- `generated/read_models/recent_file_context.json`
- `generated/read_models/markdown_evidence.json`
- `generated/read_models/agent_work_packets.json`
- `generated/read_models/operator_actions.json`
- `docs/operations/OPENCLAW_AGENT_LANE_REGISTRY_V0.md`
- `docs/operations/OPENCLAW_INTENT_ROUTER_V0.md`
- `docs/operations/OPENCLAW_RECENT_FILE_CONTEXT_V0.md`
- `docs/operations/OPENCLAW_APPROVED_MARKDOWN_EVIDENCE_V0.md`
- `docs/operations/OPENCLAW_AGENT_WORK_PACKET_V0.md`

## Recommended Next Lane

Proceed with the queued Agent Runtime Readiness + Start Sequence v0, but treat runtime as readiness/start-sequence design only until explicit operator approval exists. First reconcile the stale Mac mirror so Mission Control can see the new read-models.

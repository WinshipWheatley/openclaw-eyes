# Active Machinery Classification Orchestrator v0

Status:
- Shards ready for Gemini: `true`.
- LLM calls made: `false`.
- Raw private content read: `false`.
- Repo B executed: `false`.
- Classification claims final: `false`.

## Counts
- Candidates: `800`.
- Header-readable shard items: `766`.
- Blocked/no-go candidates: `18`.
- Shards generated: `31`.

## Groups
### daemon/listener
- Count: `0`
- No mocked worker rows yet.

### scheduler/watchdog
- Count: `0`
- No mocked worker rows yet.

### sync bridge
- Count: `0`
- No mocked worker rows yet.

### importer/exporter
- Count: `0`
- No mocked worker rows yet.

### approval/HITL
- Count: `0`
- No mocked worker rows yet.

### send/external API
- Count: `0`
- No mocked worker rows yet.

### MCP/tool/plugin surface
- Count: `0`
- No mocked worker rows yet.

### state mutator
- Count: `0`
- No mocked worker rows yet.

### generated/read-model artifact
- Count: `100`
- `generated/read_models/OPENCLAW_CRITICAL_PATH_EXECUTION_PACKET_READY.json` -> worker_review_required (Path is a generated read-model artifact; worker must verify posture.)
- `generated/read_models/OPENCLAW_REMAINING_WORK_STRATIFIER_READY_PACKET.json` -> worker_review_required (Path is a generated read-model artifact; worker must verify posture.)
- `generated/read_models/active_machinery_classification_orchestrator.json` -> worker_review_required (Path is a generated read-model artifact; worker must verify posture.)
- `generated/read_models/active_machinery_classification_orchestrator_OPERATOR.md` -> worker_review_required (Path is a generated read-model artifact; worker must verify posture.)
- `generated/read_models/agent_capability_migration_map.json` -> worker_review_required (Path is a generated read-model artifact; worker must verify posture.)
- `generated/read_models/agent_lanes.json` -> worker_review_required (Path is a generated read-model artifact; worker must verify posture.)
- `generated/read_models/agent_lanes_OPERATOR.md` -> worker_review_required (Path is a generated read-model artifact; worker must verify posture.)
- `generated/read_models/agent_presence.json` -> worker_review_required (Path is a generated read-model artifact; worker must verify posture.)
- `generated/read_models/agent_presence_OPERATOR.md` -> worker_review_required (Path is a generated read-model artifact; worker must verify posture.)
- `generated/read_models/agent_runtime_readiness.json` -> worker_review_required (Path is a generated read-model artifact; worker must verify posture.)

### canonical doctrine/docs
- Count: `138`
- `docs/operations/ACTIVE_MACHINERY_CLASSIFICATION_WORKER_PROMPT_V0.md` -> worker_review_required (Path is an operations doctrine/spec document; worker must verify content.)
- `docs/operations/AGENT_CAPABILITY_MIGRATION_MAP_V0.md` -> worker_review_required (Path is an operations doctrine/spec document; worker must verify content.)
- `docs/operations/CASSANDRA_CHIEF_MEMORY_AUTHORITY_SQLITE_MIGRATION_SPEC_V0.md` -> worker_review_required (Path is an operations doctrine/spec document; worker must verify content.)
- `docs/operations/CASSANDRA_CHIEF_MEMORY_AUTHORITY_SQLITE_SCHEMA_V0.md` -> worker_review_required (Path is an operations doctrine/spec document; worker must verify content.)
- `docs/operations/CASSANDRA_MACHINE_CONTRACT.md` -> worker_review_required (Path is an operations doctrine/spec document; worker must verify content.)
- `docs/operations/CHIEF_MACHINE_CONTRACT.md` -> worker_review_required (Path is an operations doctrine/spec document; worker must verify content.)
- `docs/operations/CROSS_REPO_SPLIT_HITL_AND_MODULE_BOUNDARY_RECONCILIATION_V0.md` -> worker_review_required (Path is an operations doctrine/spec document; worker must verify content.)
- `docs/operations/DEPENDENCY_HYGIENE.md` -> worker_review_required (Path is an operations doctrine/spec document; worker must verify content.)
- `docs/operations/DOC_GOVERNANCE.md` -> worker_review_required (Path is an operations doctrine/spec document; worker must verify content.)
- `docs/operations/DOC_LIFECYCLE.md` -> worker_review_required (Path is an operations doctrine/spec document; worker must verify content.)

### legacy reference-only
- Count: `1`
- `.` -> keep_reference_only (Repo role is pre-split reference-only and was not header-read.)

### unknown/operator review
- Count: `528`
- `AGENTS.md` -> worker_review_required (Mock placeholder; Gemini worker has not classified this item.)
- `CURRENT_STATE.md` -> worker_review_required (Mock placeholder; Gemini worker has not classified this item.)
- `DEEPPOCKET.md` -> worker_review_required (Mock placeholder; Gemini worker has not classified this item.)
- `KNOWN_GAPS.md` -> worker_review_required (Mock placeholder; Gemini worker has not classified this item.)
- `NEXT_ACTIONS.md` -> worker_review_required (Mock placeholder; Gemini worker has not classified this item.)
- `OPENCLAW_RUNTIME.md` -> worker_review_required (Mock placeholder; Gemini worker has not classified this item.)
- `OPERATOR_EXTENSION_MANIFESTO.md` -> worker_review_required (Mock placeholder; Gemini worker has not classified this item.)
- `Operator/GENERATED_CURRENT_STATE.md` -> worker_review_required (Mock placeholder; Gemini worker has not classified this item.)
- `Operator/GENERATED_NEXT_ACTIONS.md` -> worker_review_required (Mock placeholder; Gemini worker has not classified this item.)
- `RUNBOOK.md` -> worker_review_required (Mock placeholder; Gemini worker has not classified this item.)

## Worker Prompt
- `docs/operations/ACTIVE_MACHINERY_CLASSIFICATION_WORKER_PROMPT_V0.md`

## Next Safe Move
- Send shard packets and worker prompt to Gemini 3.1 Pro for JSON-only classification.

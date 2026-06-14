# Repo B Chief Offline Worker Wrapper

## Summary
Repo B Chief has useful routing, queue/status, validation, approval-policy, and briefing shapes, but v0 keeps it offline and fixture/source-ref based. Live dispatch, queue mutation, Telegram, listener startup, watchdog/repair, file repair, model calls, credentials, raw bodies, and external actions are blocked.

## Posture
- Wrapper posture: WRAP_AS_OFFLINE_READBACK_WORKER_WITH_PROMOTED_DETERMINISTIC_SUBSET
- Repo B invocation: none in v0
- Output type: candidate route/readback/package-shaping cards only

## Safe Capabilities
- TASK_CLASSIFICATION: Classify a task goal into a candidate lane from safe text and scoped refs.
- ROUTE_SUGGESTION: Suggest MAC_CODEX, PC_CODEX, GEMINI_AGY, Guardian, Cassandra, or workflow package compiler without dispatching.
- QUEUE_STATUS_SUMMARY: Summarize safe queue metadata refs without reading or mutating live queues.
- WORK_PACKET_SHAPING: Turn an operator goal into a bounded worker prompt outline for Repo A validation.
- NEXT_SAFE_MOVE: Recommend the next reversible, bounded move when a task is blocked or under-scoped.
- BUILD_NOW_VS_HOLD: Suggest build-now, build-next, park, or clarify based on safe task metadata.
- DIAGNOSTIC_SUMMARY: Summarize safe readback/status refs into an operator diagnostic card.
- OPERATOR_BRIEFING: Produce a concise operator briefing from safe counts and readback refs.
- WORKER_RECOMMENDATION: Recommend the appropriate worker type from static Repo A worker routing rules.
- MISSING_INFO_DETECTION: Identify missing inputs that prevent safe package compilation or execution claims.

## Blocked Capabilities
- LIVE_DISPATCH_ATTEMPTED: Chief offline cannot dispatch workers.
- TELEGRAM_OUTPUT_ATTEMPTED: Chief offline cannot send or post Telegram output.
- LIVE_LISTENER_START_ATTEMPTED: Listener startup is blocked.
- QUEUE_MUTATION_ATTEMPTED: Queue mutation is blocked.
- WATCHDOG_REPAIR_ATTEMPTED: Watchdog/repair loops are blocked.
- FILE_REPAIR_ATTEMPTED: File repair/cleanup requires a separate approved lane.
- CREDENTIAL_OR_ENV_MUTATION_ATTEMPTED: Credential/env mutation is blocked.
- BROAD_FILESYSTEM_SCAN: Broad filesystem scans are blocked.
- RAW_PRIVATE_BODY_INCLUDED: Raw private bodies are blocked.
- EXTERNAL_ACTION_ATTEMPTED: External action is blocked.
- UNKNOWN_FAIL_CLOSED: Unknown actions fail closed.

## Example Readback
- Status: FIXTURE_READBACK_READY
- Candidate worker: UNKNOWN_NEEDS_ROUTING
- Candidate route: unknown_needs_routing
- Next safe move: Ask for the concrete task or pass the request to Worker Routing Intelligence for deterministic routing.

## Boundary
No live Chief dispatch, no queue mutation, no Telegram output, no listener start, no watchdog/repair, no file repair, no worker execution, no model call, no external action, no credentials, no raw private body exposure.

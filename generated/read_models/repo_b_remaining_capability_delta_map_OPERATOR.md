# Repo B Remaining Capability Delta Map v0

Status:
- Repo A baseline rails: `14`.
- Repo B paths inspected as metadata: `118`.
- Repo B code executed: `false`.
- Live/security-threshold work started: `false`.

## ELI5 Summary
Repo B still contains a lot of the older OpenClaw machinery, but much of it is already represented in Repo A as safer read-models, proof rails, or blocked contracts. The useful remaining delta looks less like code to copy and more like concepts to harvest: Chief status, queue timing, protected-access ideas, and some music/reporting semantics. The risky old pieces are still the live loops, send/OAuth/tool bridges, and automatic repair machinery. Nothing here is ready for live execution.

Already handled or represented:
- `cassandra_core_listener_review`

Partly tracked:
- `cassandra_calendar_email_draft`
- `chief_orchestrator_planner_status`
- `brain_dump_inbox_parser`
- `niles_music_producer_album`
- `report_bridge_client_company_reporting`
- `budget_tracker_finance_legacy`

May need bringing forward:
- `dropped_intent_task_queue_timing`
- `pii_vault_protected_broker_concept`
- `capability_skill_registry`

Unsafe, old, or blocked:
- `planner_builder_automation_loops`
- `automatic_fix_repair_loops`
- `oauth_tool_browser_credential_bridges`

Needs Winship memory review:
- Hermes status

## Classification Counts
- `ALREADY_REPRESENTED_IN_REPO_A`: 1
- `MISSING_FROM_REPO_A`: 1
- `OBSOLETE_OR_STALE`: 1
- `PARTIALLY_REPRESENTED_IN_REPO_A`: 6
- `SUPERSEDED_BY_REPO_A`: 1
- `UNKNOWN_NEEDS_OPERATOR_MEMORY_REVIEW`: 1
- `UNSAFE_OR_BLOCKED`: 3
- `WORTH_BRINGING_FORWARD`: 3

## Recommended Next Lanes
- `Chief Status Rail Completion v0`: gate `pass` - Bring forward Chief status/readiness semantics as read-model proof, not runtime brains.
- `Build Now Vs Hold Queue Posture v0`: gate `pass` - Model the hold-vs-build timing workflow from queue/dropped-intent evidence without executing queues.
- `Protected Access Broker Concept Delta v0`: gate `pass` - Review Repo B protected PII/OAuth/tool concepts as metadata only before any security-threshold lane.

## Boundaries
- Repo B remains reference-only.
- No Repo B code was imported, executed, migrated, or activated.
- No live send, browser, credential, approval execution, planner/builder automation, or security pass was enabled.

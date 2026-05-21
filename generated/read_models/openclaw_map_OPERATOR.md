# OpenClaw Stable Map Bundle

## What Mission Control Should Read

- Map generation: `map_911cd302343946ad6369`
- Bundle hash: `sha256:dfa1e6c95bc6b74cb64a5c4652a19005bbfb63033352b43e5fd109f6f344d061`
- Stable files: `openclaw_map_snapshot.json`, `openclaw_map_manifest.json`, `openclaw_map_OPERATOR.md`
- Raw generated read-models remain proof/detail, not the front-door app dependency.

## Current Sync Truth

- Raw canonical expected: `241`
- Raw observed: `218`
- Raw missing expected: `23`
- Raw hash mismatch: `4`
- Raw lifecycle: `actionable_sync_failure`
- Check Transmission source: `sync_health controls Check Transmission freshness; taxonomy must not override fresher proof`

## Threshold Map Included

- Capital Hilton route: `MOVE_TO_WORLD_ACTION` -> `Finance`
- System Awareness lane: `READY_FOR_SECURITY_AUDIT`
- Cue/autonomy remains future-gated and is not active authority.

## Agent Council / Dossier Summary

- Cards available: `12`
- Featured agents: `cassandra, chief, guardian, hermes, niles, struna`
- System-loop cards: `agentic_loop, cue_parser_brain_dump_parser, repo_b_planner_builder_orchestrator, package_compiler, model_router, tool_plugin_registry`
- Future-gated cards: `12`
- Cassandra, Chief, Guardian, Hermes, Niles, and Struna are available as read-only dossier cards.
- Agentic Loop, Cue Parser / Brain Dump Parser, Repo B Planner / Builder / Orchestrator, Package Compiler, Model Router, and Tool / Plugin Registry are available as system-loop cards.
- Cards are preview/readback only; live chat, agent activation, model launch, tool execution, credentials, browser/OAuth, Gmail/calendar/Coupa/Telegram, send/submit/approval, and raw private context remain blocked.
- Mission Control should render a selected dossier card, roster rail, permission chips, strengths, missing proof, operator questions, and package preview route without adding a new per-contract file dependency.

## What This Fixes

- Adding a new backend read-model may update the map content or raw proof count, but it should not require a new Mission Control entitlement or app-facing file path.
- Mission Control can fail closed on the stable map if the map receipt is stale without treating the whole raw terrain as absent.

## Boundary

- Metadata/read-model contract only.
- No model calls, agent activation, browser/OAuth/account access, send/submit/approval, remount, repair, delete, file move, network operation, or C-drive artifact write.

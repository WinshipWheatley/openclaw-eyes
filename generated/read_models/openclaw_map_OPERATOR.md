# OpenClaw Stable Map Bundle

## What Mission Control Should Read

- Map generation: `map_d49f3a6dd4a0eedc1777`
- Bundle hash: `sha256:127b49cd02832950dceb9c9ff8943a1a790507a6c360806bbbf944cce3108211`
- Stable files: `openclaw_map_snapshot.json`, `openclaw_map_manifest.json`, `openclaw_map_OPERATOR.md`
- Raw generated read-models remain proof/detail, not the front-door app dependency.

## Current Sync Truth

- Raw canonical expected: `245`
- Raw observed: `218`
- Raw missing expected: `27`
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

## Package Preview Receipt Summary

- Summary present: `true`
- Contract: `package_preview_receipt_contract` / `package_preview_receipt_contract_v0`
- Receipt types: `14`
- Preview states: `19`
- Example preview cards: `8`
- Mission Control can render package preview cards for Cassandra Capital Hilton, Chief Check Engine, Guardian Protected Evidence, Niles / Struna, Hermes, Codex, Gemini / Antigravity, and Agentic Loop Classification.
- Package preview remains display-only: dispatch, model calls, tool execution, agent activation, queue execution, account access, send/submit/approval, raw body inclusion, and canonical memory writes are blocked.

## Tool Adapter Receipt Summary

- Summary present: `true`
- Contract: `tool_adapter_receipt_contract` / `tool_adapter_receipt_contract_v0`
- Receipt types: `15`
- Receipt states: `20`
- Capability classes: `20`
- Adapter receipt cards: `12`
- Allowed read-only: `1`
- Preview/receipt-only: `3`
- Blocked or future-gated: `8`
- Mission Control can render adapter receipt cards for the stable map reader, package preview exporter, Codex verifier, Cassandra/Capital Hilton proof adapter, Guardian gate, Chief harness, browser/OAuth, Gmail/calendar, Coupa, Telegram, Repo B planner/builder, and memory candidate writer.
- Live tool execution, network/account/browser access, send/submit/approval, command execution, model calls, agent activation, and queue execution remain false.

## What Mission Control Can Render Next

- Package Preview surface: preview cards, included/excluded context summaries, missing proof, gates, receipts, stop conditions, and future dispatch blockers.
- Tool Adapter Receipt surface: requested adapter, package, actor, capability requested/granted/blocked, gates, blocked reasons, and output receipt shape.
- Agent Council can link dossier cards to package/tool summaries through this stable map snapshot without new per-file app dependencies.

## What Remains Blocked / Future-Gated

- No live dispatch, model launch, tool execution, browser/OAuth/account access, Gmail/calendar/Coupa/Telegram controls, credentials, send/submit/approval, planner/builder/queue/autonomy, arbitrary commands, or raw private context.
- Package and adapter records are proof/display surfaces only; they do not create authority.

## What This Fixes

- Adding a new backend read-model may update the map content or raw proof count, but it should not require a new Mission Control entitlement or app-facing file path.
- Mission Control can fail closed on the stable map if the map receipt is stale without treating the whole raw terrain as absent.

## Boundary

- Metadata/read-model contract only.
- No model calls, agent activation, browser/OAuth/account access, send/submit/approval, remount, repair, delete, file move, network operation, or C-drive artifact write.

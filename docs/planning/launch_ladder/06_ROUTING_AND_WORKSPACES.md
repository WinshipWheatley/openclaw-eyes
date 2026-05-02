# Routing And Workspaces

Status: docs-only routing map. This file does not authorize commands or live integrations.

Freshness:

- Generated/reviewed: 2026-05-02
- Source commit at creation: `e06b7ae`
- Package commit: `TBD_AFTER_COMMIT`
- Source basis: runtime law, MCP profiles, model fallback policy, Hermes advisory contract, source-set scripts, service freeze, validation map.
- Stale when: workspace paths, tool policy, MCP profiles, source-set workflow, validation commands, or authority boundaries change.
- Refresh trigger: update before routing a build to Mac/Codex/ChatGPT/Gemini/Hermes or future clients.

## Routing Entry Required Fields

Every routing entry must include:

- `route_id`
- `tool`
- `machine`
- `workspace_path`
- `allowed_source_set`
- `output_path`
- `authority_level`
- `validation_command`
- `do_not_touch_surfaces`
- `freshness`
- `stop_condition`

## Initial Routing Map

| Route ID | Tool | Machine | Workspace/path | Allowed source set | Output path | Authority level | Validation command | Do-not-touch surfaces |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `pc_wsl_docs_spec` | VS Code / local agent | PC/WSL | `/home/openclaw` | Exact repo docs listed in task. | `docs/planning/launch_ladder/` | docs-only write when explicitly requested. | `git diff --check`; ignored-file no-index checks for new docs. | Runtime code, services, installers, launchers, timers, schedulers, providers, models, Gmail/Telegram, Hermes runtime, `.mcp.json`, secrets, vaults, logs, Legal/private data. |
| `pc_wsl_backend_schema_future` | local agent or builder | PC/WSL | `/home/openclaw` | Future Launch Ladder docs plus explicit source fixtures. | `TBD_BACKEND_SCHEMA_PATH` | planned slice only. | TBD static tests. | Live services, private data, provider/model calls, runtime mutation. |
| `mac_review_mirror_future` | curated sync script design | Mac | `~/OpenClaw_Watch/...` | Explicit manifest copied from PC/WSL. | Mac mirror folders. | read-only copy/review. | Future dry-run/list and count checks. | No delete, no broad repo, no secrets/logs/vaults/private data. |
| `codex_desktop_mac_app_future` | Codex Desktop | Mac | `TBD_MAC_APP_WORKSPACE` | Future `2_MAC_IOS_APP_BUILD` source set. | `TBD_MAC_IOS_PROJECT_PATH` | build proposal/read-only first app until approved. | Xcode/Swift checks TBD in later slice. | Service control, provider/model calls, private data, generated source-set mutation. |
| `chatgpt_project_spec_review_future` | ChatGPT Project | Cloud UI | Numbered upload folder | 23 content files + `MANIFEST.md`, 24 upload files total. | ChatGPT project conversation/output only. | advisory/proposal only. | Manifest count/freshness check before upload. | Secrets, private logs, Legal/private matter data, Gmail bodies, vaults, runtime state. |
| `gemini_architecture_advisory_future` | Gemini or other external advisor | External/cloud | Explicit sanitized packet | Non-sensitive repo/docs packet only. | Non-canonical memo. | advisory only, approval required before use. | Sanitizer/export gate TBD. | Protected/private packets, provider fallback by default, decisions, canonical writes. |
| `hermes_advisory_future` | Hermes advisory packet checker | PC/WSL or Hermes gateway-advisory profile | OpenClaw bounded packet | Explicit allowed source references only. | Non-canonical advisory memo. | advisory only. | `tests/test_hermes_advisory_packet_contract.py` in future approved validation. | Hermes runtime, provider fallback, logs, sessions, state DB, private data, canonical writes. |
| `future_macos_ios_client` | native app | macOS/iOS | User device app sandbox | Read-only generated artifacts/API payloads. | App UI/cache TBD. | read-only display. | App tests TBD. | Service control, credential storage beyond approved auth, direct mutation, hidden sync. |
| `future_other_client` | TBD client | TBD | TBD | Read-only artifacts/API payloads. | TBD | read-only first. | TBD | Same withheld surfaces as default unless explicitly narrowed. |

## Delta Bridge Routing Rule

`CHAT_STAY_UP_TO_DATE.md` may be uploaded alongside the active ChatGPT Project source-set folder as an adjacent delta bridge. It must stay outside `CHATGPT_PROJECT_INGEST_OPERATOR_HARNESS/*`, must not be counted in the 24-file folder total, and must not replace `MANIFEST.md` as source-set authority.

Use the bridge for small repo deltas and current chat focus. Use a full 24-file refresh when folder purpose, file membership, source commit basis, withheld surfaces, authority rules, or source-set ladder position changes.

## Route Compression Fields

Every route comparison should include `steps_to_launch`, `estimated_true_steps`, `includes`, `defers`, `risk`, `confidence`, and freshness.

Example:

| Route | steps_to_launch | estimated_true_steps | includes | defers | risk | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| Direct Route | 3 | 7 | docs package, validation, force-add/commit | app fixtures, generator, backend schema | low | high |
| Balanced Route | 5 | 10 | docs, schemas, source-set spec, validation, manifest rules | native app build | medium | medium |
| System Route | 8 | 14 | docs, schemas, generator spec, app brief, backend plan, validation map update plan | live routes and runtime mutation | medium | medium |

## Stop Conditions

Stop immediately if a route requires:

- Secrets, credentials, vaults, private logs, LegalPrivate, Gmail bodies, private matter data, or installed units.
- Live service/model/provider/Hermes runtime commands.
- `.mcp.json` edits outside an explicit MCP lane.
- Runtime code changes outside a docs-only task.
- Ambiguous output ownership or collision with another lane.

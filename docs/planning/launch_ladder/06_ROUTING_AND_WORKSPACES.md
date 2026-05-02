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

## Workspace Launch Profiles

A Workspace Launch Profile is a named, evidence-backed view/navigation route that helps the operator open the right working surface for the reason work is happening. It opens the right machine, folder, workspace, files, tabs, and optional prompt only. It is a creature-comfort/navigation primitive, not hidden execution.

A Workspace Launch Profile does not imply permission to mutate repo/runtime state. Opening VS Code/workspace/files is safe navigation. Any execution must be a separate Launch Packet / Launch Ladder action.

Workspace Launch Profiles must never authorize tests, sync, commits, service commands, provider/model calls, app execution, runtime mutation, private-data inspection, secrets, logs, vault access, Gmail/Telegram behavior, Hermes runtime expansion, LegalPrivate work, or installed-unit checks.

Record shape:

- `profile_id`
- `display_name`
- `purpose`
- `owner_lane` or `domain`
- `target_machine` or `context`
- `target_root` or `path`
- `workspace_file` or `workspace_hint`
- `recommended_files` or `tabs`
- `optional_prompt_path` or `prompt_hint`
- `evidence_sources`
- `freshness_fields`
- `allowed_navigation_actions`
- `explicitly_forbidden_execution_actions`
- `required_next_launch_packet_for_execution`

YAML-style contract:

```yaml
workspace_launch_profile:
  profile_id: "string-stable-id"
  display_name: "Operator-facing profile name"
  purpose: "Why this view exists"
  owner_lane: "operator_harness | legal | audit | hermes | other"
  domain: "Optional domain alias when owner_lane is not enough"
  target_machine: "PC_WSL | Mac | ChatGPT_Project | Codex_Desktop | future"
  context: "Human-readable context for the target"
  target_root: "Exact root/path or TBD placeholder"
  path: "Optional narrower path"
  workspace_file: "Optional .code-workspace path"
  workspace_hint: "Optional layout hint when no workspace file exists yet"
  recommended_files:
    - "Exact non-private docs/code/planning file"
  tabs:
    - "Optional tab or view label"
  optional_prompt_path: "Optional repo-side prompt file"
  prompt_hint: "Optional short prompt to copy manually"
  evidence_sources:
    - "Docs, manifests, commits, tests, or prior-art decision records"
  freshness_fields:
    source_commit: "commit or manifest basis"
    generated_or_reviewed: "timestamp or TBD"
    stale_conditions:
      - "What makes this profile stale"
  allowed_navigation_actions:
    - "open_machine"
    - "open_folder"
    - "open_workspace"
    - "open_files"
    - "copy_prompt_text"
  explicitly_forbidden_execution_actions:
    - "run_tests"
    - "sync_files"
    - "commit_or_push"
    - "service_commands"
    - "provider_or_model_calls"
    - "app_execution"
    - "runtime_mutation"
    - "private_data_inspection"
    - "secrets_logs_vaults"
    - "gmail_or_telegram_behavior"
    - "hermes_runtime_expansion"
    - "legalprivate_work"
    - "installed_unit_checks"
  required_next_launch_packet_for_execution: "Exact Launch Packet / Launch Ladder action required before any execution"
```

Example/fixture profiles:

| `profile_id` | Display name | Target machine/context | Target root/path | Recommended files/tabs | Boundary |
| --- | --- | --- | --- | --- | --- |
| `pc_wsl_repo_view` | PC WSL repo view | PC/WSL local repo | `/home/openclaw` | `LAUNCH_LADDER_INDEX.md`, `06_ROUTING_AND_WORKSPACES.md`, `CHAT_STAY_UP_TO_DATE.md`, static checker/test | Navigation only; docs/test execution requires a separate Launch Packet. |
| `mac_upload_prep_view` | Mac upload-prep view | Mac readiness mirror | `~/OpenClaw_Watch/operator_harness_readiness` | `CHAT_STAY_UP_TO_DATE.md`, `00_launch_ladder/WATCH_PRIOR_ART_CANONICALIZATION.md`, `CHATGPT_PROJECT_INGEST_OPERATOR_HARNESS/01_CURRENT_PRODUCT_SPEC/MANIFEST.md` | Navigation only; sync, refresh, upload, or cleanup require a separate Launch Packet. |
| `mac_desktop_app_planning_view` | Mac desktop app planning view | Mac/Codex Desktop future app workspace | `TBD_MAC_APP_WORKSPACE` | `09_MAC_IOS_APP_BUILD_BRIEF.md`, source-set rules, UX/security research, read-only fixture plan | Navigation only; app build or app execution requires a separate Launch Packet. |
| `legal_visual_polish_view` | Legal visual-polish view | Legal planning workspace | `docs/planning/openclaw_legal/law_program/` or Legal-specific Mac mirror after boundary review | Legal visual polish planning docs and handoff files | Navigation only; LegalPrivate and real-matter work remain forbidden unless separately authorized. |
| `audit_runtime_review_view` | Audit runtime-review view | Audit-build readiness mirror | `~/OpenClaw_Watch/openclaw_audit_build_readiness` | audit-build source sets, future manifests, service-freeze docs | Navigation only; runtime inspection, service commands, logs, or installed-unit checks require a separate approved Launch Packet. |
| `hermes_advisory_packet_view` | Hermes advisory-packet view | PC/WSL repo | `/home/openclaw` | `docs/operations/HERMES_ADVISORY_PACKET_CONTRACT.md`, `docs/planning/HERMES_FIRST_ADVISORY_TRIAL_PLAN.md`, Hermes packet fixtures/tests | Navigation only; Hermes runtime expansion, provider fallback, or advisory execution requires a separate Launch Packet. |

## Workspace Profile To Launch Packet Handoff

The profile-to-packet handoff is explicit and one-way:

1. The Workspace Launch Profile opens context only.
2. The profile may point to `required_next_launch_packet_for_execution`.
3. The Launch Packet authorizes a bounded next action only after evidence/freshness, operator-readable scope, validation, authority, and stop conditions are present.
4. The Workspace Launch Profile must not contain executable commands or silently authorize them.

The handoff exists so navigation can be comfortable without becoming hidden execution. A profile can identify the right machine, folder, workspace, files/tabs, and prompt hints. A packet is the separate execution-authorizing object for tests, sync, commit, service command, provider/model call, runtime mutation, app execution, private-data inspection, launcher action, or any other side effect.

Profile handoff fields:

- `required_next_launch_packet_for_execution`: packet id, packet type, or prompt hint for the next action.
- `handoff_reason`: why execution is outside the profile.
- `handoff_evidence_sources`: docs, manifests, commits, tests, or prior-art records the packet must cite.
- `handoff_freshness_fields`: source commit, generated/reviewed timestamp, stale conditions, and refresh trigger the packet must preserve.
- `handoff_operator_readable_scope`: plain-language scope the operator should see before approving the packet.

Valid context-only profile example:

```yaml
workspace_launch_profile:
  profile_id: "mac_upload_prep_view"
  display_name: "Mac upload-prep view"
  target_machine: "Mac"
  target_root: "~/OpenClaw_Watch/operator_harness_readiness"
  recommended_files:
    - "CHAT_STAY_UP_TO_DATE.md"
    - "CHATGPT_PROJECT_INGEST_OPERATOR_HARNESS/01_CURRENT_PRODUCT_SPEC/MANIFEST.md"
  allowed_navigation_actions:
    - "open_folder"
    - "open_files"
    - "copy_prompt_text"
  required_next_launch_packet_for_execution: "operator_harness_refresh_packet"
  handoff_reason: "Sync, refresh, upload, or cleanup are execution actions."
```

Bounded Launch Packet example:

```yaml
launch_packet:
  packet_id: "operator_harness_refresh_packet"
  source_profile_id: "mac_upload_prep_view"
  bounded_next_action: "Refresh the existing Operator Harness Mac mirror and ingest folders."
  target_machine: "PC_WSL_to_Mac"
  target_workspace: "/home/openclaw"
  operator_readable_scope: "Run only the existing Operator Harness sync and refresh scripts, then verify the adjacent bridge and 24-file folder counts."
  execution_commands:
    - "mac_eyes/Launchers/sync_operator_harness_to_mac.sh"
    - "mac_eyes/Launchers/refresh_operator_harness_ingest.sh"
  evidence_sources:
    - "docs/planning/launch_ladder/CHAT_STAY_UP_TO_DATE.md"
    - "docs/planning/launch_ladder/08_SOURCE_SET_REFRESH_SYSTEM.md"
  freshness_fields:
    source_commit: "current repo HEAD or manifest basis"
    generated_or_reviewed: "timestamp at packet creation"
    stale_conditions:
      - "source-set membership changed"
      - "withheld surfaces changed"
  validation_commands:
    - "folder count verification from refresh script"
  withheld_surfaces:
    - "secrets"
    - "vaults"
    - "logs"
    - "LegalPrivate"
    - "runtime state"
  authority_required: "operator_authorized"
  stop_condition: "Stop on missing bridge, non-24 file count, stale manifest basis, or any request outside Operator Harness readiness."
```

Denied/malformed profile example:

```yaml
workspace_launch_profile:
  profile_id: "bad_upload_prep_runner"
  target_root: "~/OpenClaw_Watch/operator_harness_readiness"
  executable_commands:
    - "mac_eyes/Launchers/refresh_operator_harness_ingest.sh"
  reason_invalid: "A Workspace Launch Profile with executable commands is invalid; commands belong in a Launch Packet."
```

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

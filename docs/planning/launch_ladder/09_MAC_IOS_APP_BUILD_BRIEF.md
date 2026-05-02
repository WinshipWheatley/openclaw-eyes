# Mac/iOS App Build Brief

Status: docs-only app build brief. This file does not create an app or authorize app-side control.

Freshness:

- Generated/reviewed: 2026-05-02
- Source commit at creation: `e06b7ae`
- Package commit: `TBD_AFTER_COMMIT`
- Source basis: Launch Ladder docs, modular readiness ledger, runtime law, MCP profiles, source-set refresh model.
- Stale when: app route, data contract, source-set workflow, security/authority rules, or product scope changes.
- Refresh trigger: update before Codex Desktop or any Mac/iOS build agent starts implementation.

## First App Principle

The first macOS/iOS app is a read-only control console. It displays Launch Ladder state, module readiness, routes, freshness, evidence, and withheld surfaces. It must not control services, mutate runtime state, send messages, call providers/models, inspect private data, or become canonical memory.

`Mac/iOS` is Apple-platform planning shorthand in this package. The intended build order is Mac desktop app first, iOS companion later. Do not read this brief as iOS-first implementation.

Long range, that console can become a client for the Multi-OpenClaw Command Atlas: a zoomable map across personal OpenClaw and future client/company deployments. The first app must not try to build the whole atlas. It should prove read-only presentation of Launch Ladders, evidence, freshness, blockers, and next safe actions first.

## Initial App Goals

- Bird's Eye view for North Star, module readiness, stale flags, and next safe route.
- Future atlas view that can zoom from all builds/deployments to one build, departments, agents/systems/subsystems/modules, launch goals, Launch Ladders, steps, evidence artifacts, and docs/code/prompts/validation.
- Route View for Direct, Balanced, and System route comparison.
- Step View for exact tool, machine, workspace, source set, output, validation, evidence, authority, and stop condition.
- Compact buttons that display resulting step count and deferred work before selection.
- Parallel Step Bundle preview that displays collisions, validation commands, commit boundaries, and stop conditions.
- Evidence and freshness panels for every claim.

## App-Facing Workspace Launch Profiles

The app may eventually display or open Workspace Launch Profiles, but only as view/navigation routes. A profile can help the operator open the correct machine, folder, VS Code workspace/layout, files/tabs, and optional copied prompt for the current task. It must not run tests, sync files, commit changes, call providers/models, issue service commands, mutate runtime state, or infer authority from the fact that a workspace opened.

First app-facing examples:

- `Operator Harness - Upload Prep View`
- `Operator Harness - Backend/Data Model View`
- `Operator Harness - Mac Desktop App Planning View`
- `Hermes - Advisory Packet View`

If the operator selects an action from a profile, the app should route to a separate Launch Packet / Launch Ladder action with explicit command, machine, workspace, validation, evidence, authority, and stop condition fields. Opening VS Code/workspace/files is safe navigation; execution is a separate approval surface.

The app must treat any Workspace Launch Profile that contains executable commands as malformed. The valid path is profile opens context only, then a Launch Packet authorizes a bounded next action with operator-readable scope, evidence/freshness, validation, authority, and stop conditions.

## Read-Only Data Contract Needs

The app should consume stable JSON or Markdown-derived fixtures before any backend API exists.

Minimum records:

- `deployment_record`
- `department_record`
- `module_readiness_record`
- `launch_goal_record`
- `launch_route_record`
- `launch_stage_record`
- `compact_button_record`
- `parallel_bundle_record`
- `evidence_ref`
- `freshness_record`
- `routing_entry`
- `withheld_surface_record`
- `operator_trail_step_record`

Each record must include source commit, generated/reviewed time, stale conditions, and authority level.

Each atlas-level record should answer what it is, what it can do, its North Star, readiness, blockers, evidence, and next safe Launch Ladder.

## Mock Fixture Needs

Create mock fixtures in a later slice before app work starts:

- Fresh Direct Route for docs-only work.
- Stale Balanced Route after source change.
- System Route with deferred backend/app work.
- Hermes advisory route that is non-canonical.
- Service-control route that is static/read-only only.
- Blocked route because authority is missing.
- Parallel bundle rejected because of file/workspace collision.

## UI States

The app must handle:

- Empty/no route.
- Fresh route.
- Stale route.
- Unknown freshness.
- Missing evidence.
- Missing authority.
- Deferred work visible.
- Launch-ready but not launch-authorized.
- Launch-authorized for one specific action.
- Withheld surfaces present.
- Validation failed.
- Source-set count mismatch.

## UI State Claim Rules

The app must use product copy that separates record availability, authorization, execution, result, and freshness. A display state is allowed only when the named evidence supports exactly that state.

- "Profile available" does not mean "packet available." It means a Workspace Launch Profile can navigate to context.
- "Packet available" does not mean "approved." It means a bounded Launch Packet exists for operator review.
- "Approved" does not mean "executed." It means an Approval Receipt currently permits the named packet/action/scope.
- "Executed" does not mean "succeeded." It means the action was attempted and needs a separate result reference.
- "Succeeded" requires an execution result reference and validation/evidence proof.
- "Current/fresh" requires evidence/freshness proof, including source basis, timestamp or commit, stale conditions, and refresh trigger.
- "Synced/tested/healthy/running" cannot be shown unless backed by explicit evidence for that exact claim.
- UI must distinguish configured vs observed, requested vs approved, approved vs executed, executed vs succeeded, and current vs stale.
- Convenience must not collapse navigation, approval, and execution into one hidden action.
- Opening a Workspace Launch Profile must not auto-approve, auto-run, or auto-consume a Launch Packet.

Valid UI copy examples:

```yaml
ui_state_claim:
	id: "packet_waiting_for_approval"
	label: "Packet available"
	meaning: "A bounded Launch Packet exists for review."
	must_not_imply:
		- "approved"
		- "executed"
		- "succeeded"
	evidence_required:
		- "launch_packet_id"
		- "operator_readable_scope"
		- "freshness_snapshot"
```

```yaml
ui_state_claim:
	id: "approved_not_executed"
	label: "Approved"
	meaning: "A current Approval Receipt permits one named packet/action/scope."
	must_not_imply:
		- "executed"
		- "succeeded"
	evidence_required:
		- "approval_receipt.receipt_id"
		- "approval_receipt.launch_packet_id"
		- "approval_receipt.approved_scope"
		- "approval_receipt.expiry"
		- "approval_receipt.consumed_state"
		- "approval_receipt.revocation_state"
```

Invalid UI state claim example:

```yaml
ui_state_claim:
	id: "invalid_tests_passed_without_evidence"
	label: "Tests passed"
	evidence_refs: []
	freshness_snapshot: "unknown"
	reason_invalid: "UI state claim says tests passed without evidence."
```

Invalid profile-open execution flow example:

```yaml
workspace_launch_flow:
	id: "invalid_profile_open_auto_approves_and_runs"
	profile_id: "mac_upload_prep_view"
	on_open:
		- "create_launch_packet"
		- "approve_launch_packet"
		- "run_launch_packet"
	reason_invalid: "Opening a Workspace Launch Profile silently approves/runs a packet; navigation, approval, and execution must stay separate."
```

## Suggested Project Placeholders

| Field | Placeholder |
| --- | --- |
| Mac workspace | `TBD_MAC_APP_WORKSPACE` |
| App project path | `TBD_MAC_IOS_PROJECT_PATH` |
| Source-set input | future `CHATGPT_PROJECT_INGEST_LAUNCH_LADDER/2_MAC_IOS_APP_BUILD/` |
| Fixture input | `TBD_LAUNCH_LADDER_FIXTURES_PATH` |
| Backend/API input | `TBD_BACKEND_DATA_MODEL_PATH` |

## Technology Note

Use a native, boring, inspectable first build unless a later audit proves another stack is safer. SwiftUI is the natural macOS/iOS default, but this brief does not select or install a stack.

## Hard App Boundaries

- No service control in first version.
- No hidden shell commands.
- No provider/model calls.
- No Gmail/Telegram actions.
- No Hermes runtime integration.
- No private logs, vaults, LegalPrivate, Gmail bodies, or private matter data.
- No source-set generation inside the app.
- No canonical decisions by app display.
- No assumption that the app/atlas is authority; it is a window, router, and evidence browser.

## Future Build Route

The app build should start only after:

1. Launch Ladder docs are committed.
2. Data contract and mock fixtures are created.
3. Source-set refresh rules are implemented and validated.
4. Codex Desktop/Mac route has exact workspace and output paths.
5. App validation commands are named.

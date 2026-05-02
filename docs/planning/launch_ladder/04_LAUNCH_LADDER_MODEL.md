# Launch Ladder Model

Status: docs-only ladder/spec model. This file does not authorize launch execution.

Freshness:

- Generated/reviewed: 2026-05-02
- Source commit at creation: `e06b7ae`
- Package commit: `TBD_AFTER_COMMIT`
- Source basis: runtime law, modular readiness ledger, MCP progressive discovery, Hermes advisory contract, service freeze, validation map.
- Stale when: stage definitions, route compression semantics, view modes, or approval/authority rules change.
- Refresh trigger: update before generating backend route schemas or app UI fixtures.

## Ladder Stages

The Launch Ladder has seven distinct stages:

| Stage | Meaning | Required evidence | Authority |
| --- | --- | --- | --- |
| `recommendation` | A suggested direction exists. | Source refs and uncertainty. | Advisory only. |
| `planned_slice` | A bounded task is scoped. | Files, constraints, validation plan, do-not-touch list. | Planning only. |
| `source_set_ready` | The exact context packet/source set is assembled or specified. | Included files, withheld surfaces, stale conditions. | Read/proposal only. |
| `build_ready` | The route has a build plan and collision/validation/stop conditions. | Workspace, tool, output path, expected files, validation commands. | Build only if separately authorized by operator. |
| `validation_ready` | Tests/checks are named and safe to run for the slice. | Validation map entry or explicit static/no-index checks. | Test/check authority only. |
| `launch_ready` | Artifacts and checks indicate readiness for a specific launch path. | Passing validation, evidence refs, freshness, route, authority field. | Not launch authorization. |
| `launch_authorized` | The applicable operator/Chief/Guardian/broker approval has authorized a specific action. | Approval receipt, operator decision, broker class approval, or human promotion. | Specific authorized action only. |

Launch-ready is not launch-authorized. The console must display those as separate states.

## Launch Ladder Vs Source-Set Ladder

Launch Ladder is the operator-facing work progression toward a North Star. Source-Set Ladder is the slower ChatGPT Project context progression across folders such as `01_CURRENT_PRODUCT_SPEC`, `02_MAC_IOS_APP_BUILD`, `03_BACKEND_AND_DATA_MODEL`, and future `04/05/etc.` folders.

Source-set folders are not Launch Ladder steps. A Launch Ladder may include a `source_set_ready` stage, but that stage means the exact context packet is assembled or specified. It does not mean the chat has advanced from source-set folder 01 to 02 or 03.

The console should preserve both views without merging them: Launch Ladders track work readiness and authority; Source-Set Ladders track which source packet a ChatGPT Project session is currently using and what packet should come next.

## Ladders Replace Vague Lanes

For operator-facing work, Launch Ladders replace vague lanes. A lane can still be a planning or ownership category in source docs, but the atlas/console should route the operator through a Launch Ladder when work needs to get done.

Each Launch Ladder must name its launch goal, stage, route, steps, evidence artifacts, docs/code/prompts/validation references, blockers, freshness, authority requirement, and next safe action. This keeps the future Multi-OpenClaw Command Atlas progressive and quiet instead of presenting a noisy list of loose workstreams.

## Route Compression

Route compression offers different ways to get from recommendation to launch-ready while preserving deferred work.

| Route | Meaning | Use when |
| --- | --- | --- |
| Direct Route | The fewest safe serial steps to reach launch-ready for one bounded target. | Scope is narrow, no collisions, validation is obvious. |
| Balanced Route | A moderate route that includes the most important safety and source-set steps while deferring non-blocking polish. | The operator needs progress without losing proof discipline. |
| System Route | A fuller route that also closes architecture, source-set, validation, app/backend, and productization implications. | The work touches shared contracts, future clients, or broad authority surfaces. |

Every compressed route must expose:

- `steps_to_launch`: count of visible operator steps.
- `estimated_true_steps`: fuller count including deferred/subordinate work.
- `includes`: work included in this route.
- `defers`: work preserved for later.
- `risk`: low, medium, or high.
- `confidence`: low, medium, or high.
- `freshness`: generated/reviewed time, source commit, stale conditions, refresh trigger.

## Ladder Compact Buttons

A compact button is a proposed operator action, not silent execution authority.

Button shape:

| Field | Meaning |
| --- | --- |
| `label` | Human text, such as `Direct Route: Docs Package`. |
| `resulting_step_count` | Visible step count after compression. |
| `estimated_true_steps` | Full work count including deferred tasks. |
| `deferred_work_summary` | What is preserved for later. |
| `authority_required` | None, operator approval, Chief, Guardian, broker, or future lane. |
| `stop_condition` | When the button must stop. |
| `evidence_output` | Where the human-readable step artifact will be written if later implemented. |

The button must show the resulting step count and what work is deferred before the operator chooses it.

## Launch Packets

A Launch Packet is the separate execution-authorizing object for one bounded next action. It can be attached to a Launch Ladder step after the applicable operator, Chief, Guardian, broker, or lane approval path is explicit.

Opening a Workspace Launch Profile never creates, approves, or executes a Launch Packet. Any tests, sync, commit, service command, provider/model call, runtime mutation, app execution, private-data inspection, launcher action, or other side effect requires a Launch Packet or higher Launch Ladder action.

Minimum Launch Packet fields:

- `packet_id`
- `source_profile_id`, if the action was proposed from a Workspace Launch Profile.
- `bounded_next_action`
- `target_machine`
- `target_workspace`
- `operator_readable_scope`
- `execution_commands` or `execution_plan`, only in the Launch Packet, never in the Workspace Launch Profile.
- `evidence_sources`
- `freshness_fields`
- `constraints`
- `validation_commands`
- `withheld_surfaces`
- `authority_required`
- `approval_receipt_or_operator_decision`
- `stop_condition`

The packet authorizes only the named bounded next action. If operator-readable scope, evidence/freshness, validation, authority, or stop condition is missing, the state remains a proposal or planned slice, not launch-authorized.

## Action Authorization / Approval Receipt

Launch Packet exists does not equal approved. A Launch Packet is a scoped proposal for one bounded action; an Approval Receipt is the separate operator-readable record that explicit authorization was granted for that packet, action, and scope.

Approval Receipt rules:

- Approval Receipt records explicit operator authorization and must name whether `approved_by_operator` is true.
- Approval Receipt binds to one Launch Packet/action/scope through `launch_packet_id` and `approved_scope`.
- Approval Receipt records visible evidence/freshness state at approval time through `evidence_snapshot` and `freshness_snapshot`.
- Approval Receipt has expiry/replay rules through `expiry` and `replay_policy`; expired receipts cannot authorize new execution.
- Approval Receipt records whether approval was consumed through `consumed_state`; single-use receipts cannot be replayed after consumption.
- Approval Receipt distinguishes `permitted`, `executed`, `succeeded`, `failed`, `expired`, and `revoked` instead of collapsing them into one approved-looking state.
- Approval Receipt must be operator-readable: the human must be able to see who approved, what was approved, which evidence was visible, whether it is fresh, whether it is expired/revoked, and whether it was consumed.
- Approval Receipt must not broaden the Launch Packet scope. `forbidden_scope_expansion` records the explicit rule that a receipt cannot add commands, files, machines, withheld surfaces, or target systems beyond the packet.

Minimum Approval Receipt fields:

- `receipt_id`
- `launch_packet_id`
- `approved_by_operator`
- `approved_at`
- `approved_scope`
- `evidence_snapshot`
- `freshness_snapshot`
- `expiry`
- `replay_policy`
- `consumed_state`
- `execution_result_reference`
- `revocation_state`
- `forbidden_scope_expansion`

Valid narrow Approval Receipt example:

```yaml
approval_receipt:
	receipt_id: "receipt_docs_test_2026_05_02_001"
	launch_packet_id: "operator_harness_docs_test_packet"
	approved_by_operator: true
	approved_at: "2026-05-02T00:00:00-07:00"
	approved_scope: "Edit only Launch Ladder docs/static checker/tests, then run the named static validations."
	evidence_snapshot:
		source_commit: "ae0eb56"
		visible_files:
			- "docs/planning/launch_ladder/04_LAUNCH_LADDER_MODEL.md"
			- "docs/planning/launch_ladder/09_MAC_IOS_APP_BUILD_BRIEF.md"
			- "launch_ladder_contract_check.py"
			- "tests/test_launch_ladder_static_contract.py"
	freshness_snapshot:
		state: "current"
		proof: "git status and git log checked at slice start"
		stale_if:
			- "repo HEAD changes before execution"
			- "requested scope changes"
	expiry:
		expires_at: "end_of_current_operator_session"
		expired_state: false
	replay_policy: "single_use"
	consumed_state: "not_consumed"
	lifecycle_state: "permitted"
	execution_result_reference: null
	revocation_state: "not_revoked"
	forbidden_scope_expansion: "Receipt cannot add runtime code, app code, provider/model calls, launchers, services, private data, or commits beyond the Launch Packet."
```

Expired Approval Receipt example:

```yaml
approval_receipt:
	receipt_id: "receipt_docs_test_expired"
	launch_packet_id: "operator_harness_docs_test_packet"
	approved_by_operator: true
	approved_scope: "Run the named static validations once."
	evidence_snapshot: "visible at approval time"
	freshness_snapshot: "current at approval time, stale after HEAD changed"
	expiry:
		expires_at: "2026-05-02T10:00:00-07:00"
		expired_state: true
	replay_policy: "single_use"
	consumed_state: "not_consumed"
	lifecycle_state: "expired"
	execution_result_reference: null
	revocation_state: "not_revoked"
	forbidden_scope_expansion: "Expired receipt cannot authorize a later broader run."
```

Consumed Approval Receipt example:

```yaml
approval_receipt:
	receipt_id: "receipt_docs_test_consumed"
	launch_packet_id: "operator_harness_docs_test_packet"
	approved_by_operator: true
	approved_scope: "Run the named static validations once."
	evidence_snapshot: "visible at approval time"
	freshness_snapshot: "current at approval time"
	expiry:
		expires_at: "end_of_current_operator_session"
		expired_state: false
	replay_policy: "single_use"
	consumed_state: "consumed"
	lifecycle_state: "executed"
	execution_result_reference: "validation output or operator trail artifact for succeeded or failed result"
	revocation_state: "not_revoked"
	forbidden_scope_expansion: "Consumed single-use receipt cannot be replayed."
```

Revoked Approval Receipt example:

```yaml
approval_receipt:
	receipt_id: "receipt_docs_test_revoked"
	launch_packet_id: "operator_harness_docs_test_packet"
	approved_by_operator: true
	approved_scope: "Run the named static validations once."
	evidence_snapshot: "visible at approval time"
	freshness_snapshot: "current at approval time"
	expiry:
		expires_at: "end_of_current_operator_session"
		expired_state: false
	replay_policy: "single_use"
	consumed_state: "not_consumed"
	lifecycle_state: "revoked"
	execution_result_reference: null
	revocation_state: "revoked_by_operator"
	forbidden_scope_expansion: "Revoked receipt grants no remaining permission."
```

Invalid scope-broadening receipt example:

```yaml
approval_receipt:
	receipt_id: "invalid_broadened_receipt"
	launch_packet_id: "operator_harness_docs_test_packet"
	approved_by_operator: true
	approved_scope: "Run static docs/tests validation only."
	requested_execution_scope: "Run tests, sync the Mac mirror, commit changes, and start app planning."
	lifecycle_state: "invalid"
	reason_invalid: "Approval Receipt cannot broaden the Launch Packet scope."
	forbidden_scope_expansion: "Sync, commit, launcher, service, provider/model, runtime, app execution, private-data inspection, and source-set movement require a separate Launch Packet or higher Launch Ladder action."
```

## Parallel Step Bundles

One operator-approved button may fire multiple independent lanes only when all of these are explicit:

- File/workspace collision matrix.
- Independent output paths.
- Validation commands per lane.
- Commit boundaries per lane.
- Stop conditions per lane.
- Shared dependency order.
- Authority boundaries and approval class.
- Failure handling and partial-completion reporting.

No parallel bundle may include live service changes, provider/model calls, Gmail/Telegram actions, Hermes runtime, private data, logs, vaults, LegalPrivate, or installed-unit checks unless a future approved lane specifically allows that surface.

## View Modes

| View | Purpose | Must show |
| --- | --- | --- |
| Bird's Eye | One-screen map of North Star, modules, routes, freshness, and blockers. | Current horizon, module readiness, route choices, stale flags, do-not-do-yet. |
| Route View | Compare Direct, Balanced, and System routes. | Steps, true steps, includes, defers, risk, confidence, freshness, authority needed. |
| Step View | Inspect one step deeply. | Tool, machine, workspace, source set, output path, validation, evidence refs, stop condition. |

## Atlas Fit

In the long-range Multi-OpenClaw Command Atlas, Launch Ladders are the work layer between high-level capability maps and street-level repo evidence. The operator should be able to zoom from all builds/deployments down to one step, then back to evidence and readiness without losing North Star, blockers, or authority state.

The v1 model only proves this work layer for one repo planning package. It does not create the full atlas, app backend, generated source sets, runtime integration, service control, private-data access, or provider/model execution.

## State Transition Rules

- A recommendation can become a planned slice only when scope and do-not-touch surfaces are explicit.
- A planned slice can become source-set ready only when included and withheld files/surfaces are named.
- A source-set ready route can become build-ready only when workspace, outputs, collisions, validation, and stop conditions are explicit.
- Build-ready can become validation-ready only when checks are safe and named.
- Validation-ready can become launch-ready only when checks pass or residual risk is documented.
- Launch-ready can become launch-authorized only through the applicable approval path.

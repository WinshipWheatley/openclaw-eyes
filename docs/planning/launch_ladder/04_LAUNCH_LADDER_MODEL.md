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

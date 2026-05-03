# Mac Desktop First Screen Composition Spec

Status: docs/test-only first-screen composition contract for the Mac desktop Mission Control surface. This file does not create UI, SwiftUI/AppKit files, source-set folders, backend/schema/SQLite work, a SQLite database, ingestion scripts, provider/model calls, private-data inspection, runtime/service/approval mutation, or app execution.

Freshness:

- Generated/reviewed: 2026-05-02
- Active source-set baseline: `02_MAC_IOS_APP_BUILD`
- Source commit from active `MANIFEST.md`: `df52ff4687d7dd8a32990658d557cb2b4d1371d9`
- Source basis: Mac/iOS App Build Brief, Mission Control Fixture Contract, Compiled Knowledge Substrate planning package, and Launch Ladder static contract checker.
- Stale when: first-screen zones, visible copy, Mission Control fixture states, evidence/freshness rules, knowledge-substrate posture, app-planning boundaries, or naming boundary changes.
- Refresh trigger: update before any Mac desktop app implementation, design mockup, fixture loader, backend/schema slice, SQLite slice, or source-set refresh generator.

## Naming Boundary

Do not name the app. Do not invent product names. Use only neutral phrases for this surface:

- Mac desktop app
- Operator Harness app
- personal operator console
- Mission Control surface

The first screen must feel personal/operator-specific without creating a product name, codename, chatbot persona, mascot, or brand label.

## First-Screen Layout Thesis

The first screen should feel like a calm cockpit / personal command desk: one glance tells the operator what context they are in, what lane is active, what is safe to do next, what evidence supports the display, and what is blocked or unknown.

It is evidence-backed, not bureaucratic. It is personal/operator-specific, not generic SaaS. It offers the next safe move, not task-manager sprawl. It shows knowledge context, not a RAG search box. Unknown means unknown. Blocked means protected boundary, not panic. Nothing moves just because it is visible.

The first screen is read-only planning. It does not execute work, approve packets, mutate services, inspect private data, ingest files, create a SQLite database, call providers/models, or claim runtime state.

## Screen Zones

### Top Operating Context Band

Purpose: anchor the operator in machine/context, source-set posture, repo freshness, authority, and local-vs-remote status.

Default contents:

- project context: `Operator Harness app planning`
- active source-set: `02_MAC_IOS_APP_BUILD`
- local repo state: `Local branch ahead of origin; remote sync not verified`
- authority state: `Operator remains authority`
- implementation state: `Planning contract only`

### Left Active Lanes Column

Purpose: show the few active lanes the operator can orient around without task-manager sprawl.

Default lanes:

- `Mission Control first screen`
- `Mission Control fixture contract`
- `Compiled Knowledge Substrate planning`
- `Source-set / delta bridge`

Each Active Lane card must show state, evidence, stale condition, and next safe move. It must not show hidden worker progress or vague agent status.

### Center Current Focus / Selected Lane

Purpose: show the selected lane with enough detail to understand the current product decision.

Default selected lane: `Mission Control first screen`

The center pane should expose:

- thesis;
- selected lane state;
- card examples;
- malformed patterns to avoid;
- exact boundary before implementation.

### Right Next Safe Move Panel

Purpose: keep the operator oriented toward one safe next move, not a backlog cloud.

Default visible copy:

```text
Next safe move: Review the first-screen composition fixtures. No implementation is authorized.
Requires: static checker and pytest pass.
Not allowed from this screen: run app code, sync, push, provider/model calls, ingestion, database creation, private-data inspection, or runtime mutation.
```

### Lower Evidence/Freshness Drawer

Purpose: expose proof without flooding the top view.

Default visible proof:

- active source-set baseline and manifest commit;
- local commits since baseline;
- validation commands expected;
- stale conditions;
- withheld surfaces;
- proof limits.

The drawer can collapse by default, but evidence must be one click away and must never be buried so deeply that status copy cannot be trusted.

### Quiet Recent Changes Strip

Purpose: show the smallest useful commit/source-set delta.

Default visible copy:

```text
Recent local changes: Mission Control fixture contract and Compiled Knowledge Substrate planning package exist locally. Local main is ahead of origin; do not show synced/current until push evidence exists.
```

This strip must be quiet. It should not become a live feed, notification wall, or urgency engine.

### Future Knowledge/Context Strip

Purpose: reserve space for future knowledge context without implying ingestion or database implementation.

Default visible copy:

```text
Knowledge context: planning package available. No files ingested. No SQLite database exists. No business archive scanned. No claims promoted.
```

This is knowledge context, not a RAG search box. It can point to future compiled notes, classifications, blocked sensitive sources, and operator promotions only after a later backend/data-model contract exists.

## Default Visible Copy For Current Project State

```text
Context: Operator Harness app planning.
Surface: Mission Control surface, read-only planning.
Source set: 02_MAC_IOS_APP_BUILD.
Local status: ahead of origin; remote sync not verified.
Authority: operator remains authority.
Implementation: not started.
Next safe move: review first-screen composition contract and fixtures.
Blocked: app implementation, backend/schema, SQLite DB, ingestion, provider/model calls, runtime mutation, private-data inspection.
Unknown: live runtime state, remote push state, future app validation command.
```

Do not show `synced`, `current`, `healthy`, `running`, `tested`, or `complete` unless evidence for that exact claim is visible.

## Card Density And Hierarchy Rules

- First screen should expose 5 to 7 primary cards, not a dashboard wall.
- One primary next safe move should be visually stronger than secondary lanes.
- Navigation/context cards must look different from Launch Packet or approval/action cards.
- Blocked and unknown states should be calm and legible, not alarming.
- Evidence/freshness snippets should be visible on every stateful card.
- Dense tables, raw manifests, long command outputs, and full evidence trails belong in drawers or drill-down views.
- Card copy should use exact state language: `planning`, `local ahead`, `blocked`, `unknown`, `available`, `not approved`, `not implemented`.
- No card may imply hidden analysis, hidden ingestion, hidden approval, hidden execution, or hidden truth.

## Example Card Copy

### Active Lane Card

```text
Mission Control first screen
State: planning contract in progress.
Evidence: this spec and seven synthetic first-screen fixtures.
Next safe move: run static validation.
Not authorized: UI implementation.
```

### Next Safe Move Card

```text
Review first-screen composition fixtures.
Why: locks the default surface before Mac desktop app implementation.
Requires: static checker and pytest pass.
Boundary: no code runs from this card.
```

### Evidence/Freshness Card

```text
Source set: 02_MAC_IOS_APP_BUILD.
Manifest commit: df52ff4687d7dd8a32990658d557cb2b4d1371d9.
Repo state: local branch ahead of origin; remote sync not verified.
Stale when: source-set posture, fixture states, or evidence rules change.
```

### Recent Commit / Source-Set Card

```text
Recent local commits: Mission Control fixture contract and Compiled Knowledge Substrate planning package.
Remote state: not verified as synced.
Display rule: do not show current/synced until push evidence exists.
```

### Knowledge Context Card

```text
Compiled Knowledge Substrate: planning package available.
State: future context only.
No ingestion. No SQLite database. No business-file scanning. No promoted claims.
Next safe move: defer schema/fixture decisions to backend/data-model planning.
```

### Blocked Without Panic Card

```text
Blocked: app implementation.
Reason: first-screen contract and fixtures must pass static validation first.
Meaning: protected boundary, not failure.
Next safe move: review validation output.
```

### Unknown Without Fake Confidence Card

```text
Unknown: live runtime state.
Reason: this surface does not inspect runtime or service state.
Display rule: show unknown, not healthy/running/current.
Next safe move: none from this screen.
```

## State Color/Emphasis Guidance

Do not choose final colors in this contract. Use semantic emphasis guidance only:

- `planning`: calm neutral emphasis.
- `available`: quiet positive emphasis only when evidence exists.
- `local_ahead`: informative emphasis; not success.
- `blocked`: protected-boundary emphasis; not panic.
- `unknown`: low-confidence emphasis; never softened.
- `stale`: clear attention emphasis with refresh trigger.
- `approved`: rare authority emphasis tied to an Approval Receipt.
- `execution`: not present on the first screen unless a separate Launch Packet/Approval Receipt/result contract exists.

Color must never be the only state channel. Text, iconography, position, and evidence labels must carry state.

## What Must Be Tucked Away

- Full source-set manifests and long evidence trails.
- Raw command output and validation transcripts.
- Debug details.
- Dense tables and backlog lists.
- Full file trees.
- Runtime/service status controls.
- Provider/model controls.
- Ingestion controls.
- SQLite/schema details.
- Private-data previews.
- Old business-file contents.
- Logs, vaults, secrets, LegalPrivate, Gmail, cloud-drive, or hidden auth surfaces.

Tucked away does not mean hidden authority. Anything dangerous must be absent or blocked, not merely visually de-emphasized.

## First-Screen Golden Examples

- `golden_first_screen_default.json`: default read-only planning first screen with the required zones, evidence/freshness, and next safe move.
- `golden_first_screen_local_ahead_of_origin.json`: shows local branch ahead of origin without claiming synced/current.
- `golden_first_screen_knowledge_context_non_ingestive.json`: shows future knowledge context without ingestion, SQLite DB creation, RAG search box, or business-file truth claims.
- `golden_first_screen_unknown_preserved.json`: preserves unknown without fake confidence.

Golden examples must preserve the read-only app-planning posture and must not authorize execution.

## First-Screen Malformed Examples

- `malformed_first_screen_ai_command_center.json`: invalid because it frames the screen as chatbot home or AI command center, implies hidden intelligence, and makes business-file truth claims.
- `malformed_first_screen_profile_executes_work.json`: invalid because opening or selecting a profile executes work.
- `malformed_first_screen_synced_after_push_failure.json`: invalid because it claims synced/current when local push evidence is absent or failed.

Malformed examples must be rejected by static validation and must never be treated as implementation examples.

## Boundaries Before Implementation

- No UI implementation.
- No SwiftUI/AppKit files.
- No source-set folders.
- No backend/schema/SQLite work.
- No SQLite database.
- No ingestion scripts.
- No file ingestion.
- No old business-file scanning.
- No private-data inspection.
- No provider/model calls.
- No runtime/service/approval mutation.
- No Gmail/Telegram actions.
- No Hermes runtime expansion.
- No secrets, vaults, logs, LegalPrivate, Gmail, or cloud-drive access.
- No app naming.
- No assumption that visibility authorizes action.

The Mac desktop app may later render this contract, but only after static validation, fixture shape review, and a separate implementation prompt.

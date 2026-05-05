# Operator World Model Build Readiness Addendum

Status: docs-only build-readiness addendum. This file does not create source-set folders, UI code, app implementation, backend/API/schema files, SQL DDL, a SQLite database, ingestion, fixtures, provider/model calls, Mac imports, sync, cleanup, file moves, private-data inspection, runtime mutation, approval mutation, app naming, audio assets, haptics, notification behavior, or sound settings UI.

Generated/reviewed: 2026-05-05

Source basis:

- `source_set_bridges/operator_harness_visual_import_freshness_bridge_20260505.md`
- `visual/operator_harness_north_star_v1/`
- `operator_harness_research/DOMAIN_AGNOSTIC_OPERATOR_SYSTEMS.md`
- `operator_harness_research/STUDIO_BORN_OPERATOR_INTELLIGENCE.md`
- `12_MAC_DESKTOP_MISSION_CONTROL_FIXTURE_CONTRACT.md`
- `13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md`
- `17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md`
- `18_BACKEND_DATA_CONTRACT_SHAPE_PLAN.md`

Freshness:

- Canonical repo: PC WSL `/home/openclaw`.
- Latest bridge commit in repo at review time: `175672c docs(planning): add operator harness source-set freshness bridge`.
- Visual/spatial import commit: `bb635e6 docs(app): import mac operator harness visual packet`.
- Prior 24-file Project source set remains useful but stale relative to the visual/spatial import for any planning that depends on this addendum.
- Stale when: the visual/spatial packet changes, Operator Harness research docs change, first-screen zones change, fixture state meanings change, 17/18 are edited to absorb this addendum, source-set membership changes, or implementation starts.
- Refresh trigger: update before generating `04_BACKEND_DATA_CONTRACT_READINESS`, before editing 17/18 for source-set generation, or before any Mac desktop app implementation prompt.

## Purpose

Translate the newly canonical Operator Harness visual/spatial packet and doctrine/research docs into build-readiness implications for the first shippable read-only Mission Control / Operator Harness app.

This addendum is a bridge between the imported visual/world-model doctrine and the existing backend/data-contract readiness lane. It preserves the existing read-only, evidence-backed, no-implementation posture while adding the missing product-world constraint: modes are future places, and places carry authority, evidence, freshness, and context boundaries.

## What The Import Changes

### First-Screen Hierarchy

The first screen should no longer be understood mainly as a grid of cards. It should be understood as the `Bridge / Captain's View`: an ambient, read-only window into the current operator world, route, port, or context.

The strongest first-screen hierarchy becomes:

1. Operating context and authority breadcrumb.
2. Bridge / Captain's View ambient watch surface.
3. Helm decision instrument for the one current next safe move.
4. Chart Room evidence/freshness access close to every claim.
5. Quiet context strips for recent changes, blocked/unknown states, and future knowledge context.

The existing first-screen zones in `13_MAC_DESKTOP_FIRST_SCREEN_COMPOSITION_SPEC.md` remain useful, but their product meaning shifts:

- Top Operating Context Band becomes the authority/context breadcrumb.
- Center Current Focus becomes the Bridge / Captain's View when idle and the focused mode surface when a lane is selected.
- Right Next Safe Move Panel becomes Helm-adjacent decision instrumentation.
- Lower Evidence/Freshness Drawer becomes Chart Room access, not generic hidden details.
- Active Lanes become mode/place entries only when they preserve authority scope and evidence expectations.

### Decision-Instrument Behavior

The import makes the primary decision instrument more precise. A decision surface should feel like the Helm: current command, next safe action, proposed action, evidence basis, risk reason codes, confirm/defer/block state, and explicit operator authority.

The decision instrument must not become:

- a chatbot suggestion panel;
- a vague `AI recommends` card;
- a dramatic alert surface;
- a one-click hidden approval path;
- an execution control disguised as navigation.

The v1 read-only app may display the decision instrument, but it must not execute from it. Approval, execution, and success remain separate states with separate evidence.

### Evidence/Freshness Display

Evidence and freshness should now have a place model. Evidence belongs in the Chart Room / source registry, even when surfaced as compact snippets on the Bridge or Helm.

Implications:

- Every stateful card still needs visible evidence/freshness snippets.
- Full manifests, source trails, stale conditions, unknowns, and contradiction notes should route to Chart Room-style drill-downs.
- Runtime/system health evidence belongs to Engine Room-style surfaces and must not imply service-control authority.
- Storage, staging, and blocked sensitive source evidence belongs to Cargo Hold-style surfaces and must not imply cleanup, sync, deletion, or ingestion.
- Communications evidence belongs to Radio Room-style surfaces and must not imply auto-send or private-message inspection.
- Finance evidence belongs to Treasury / Purser's Office-style surfaces and must not imply bank access, posting, payment, or final financial truth.

This does not require literal rooms in v1. It requires mode labels, breadcrumbs, visual separation, state copy, and validation expectations that preserve where evidence is allowed to appear and what it can imply.

### Operator-World Model

The imported model changes the app from `dashboard about work` to `window into an operator world`.

The core rule to preserve is:

```text
Spatial movement equals authority and context transition.
```

In a 2D Mac desktop v1, this should be represented through:

- mode names and mode-specific surfaces;
- strong breadcrumbs showing active context and authority scope;
- explicit transitions between personal ship, ports, projects, clients, companies, and life-domain contexts;
- visually distinct sensitive/local-only areas;
- controls that separate navigation, review, approval, execution, and evidence-backed result;
- a clear rule that navigation does not equal approval, approval does not equal execution, and execution does not equal success.

The model should train real-world operating discipline: evidence goes to Chart Room, runtime to Engine Room, money to Treasury, communications to Radio Room, creative production to Studio Bay, private planning to Captain's Quarters, and current decision authority to Helm.

### Domain-Agnostic Product Framing

The import confirms that Operator Harness is domain-agnostic but not personality-neutral.

The first shippable app should frame the product as a transferable operator system pattern:

- evidence before assertion;
- deterministic rails before agentic reasoning;
- local-first or privacy-bounded defaults;
- explicit approval before consequence;
- durable state outside chat memory;
- workflow as signal flow;
- calm interfaces that help operators perform;
- automation that proposes uncertainty instead of pretending certainty.

This means the Winship Operator Ship is the first personal implementation of a broader product doctrine. Future law, finance, clinic, agency, research, or operations deployments may use different vocabulary, but they should preserve evidence, authority, freshness, approval, and context-boundary semantics.

### Taste And Atmosphere Constraints

The import tightens the taste constraints. The app should feel like studio-console discipline applied to operational intelligence, with a calm Bridge / Captain's View and contextual widgets that appear only when useful.

Required constraints:

- high-trust Operator Harness / Mission Control;
- Mac-native restraint;
- calm late-night command room;
- window into the world;
- one compact VU/signal/evidence meter where useful;
- contextual temporary widgets rather than dashboard fill;
- local-first / sensitive-aware cues;
- evidence, state, routing, and approval visible without noise;
- visual beauty serving clarity and trust.

Hard avoids remain binding:

- generic corporate dashboard;
- dashboard grid as the main concept;
- chatbot home or assistant face;
- fake autonomy theater;
- pirate, naval, military, spaceship, literal game, or luxury-yacht styling;
- readable private data, real finance/legal/client/medical screenshots, or product-commitment screenshots;
- visual polish substituting for evidence, state, approval, or safety.

## What The Import Does Not Change

The import does not change these boundaries:

- The first app remains read-only planning/display first.
- The app must not execute work from visibility alone.
- Workspace Launch Profiles remain navigation-only.
- Launch Packets remain bounded review objects until separately approved.
- Approval Receipts bind one packet/action/scope only.
- UI State Claims still require evidence/freshness proof.
- Unknown remains unknown.
- Blocked means protected boundary, not panic.
- Freshness is target-scoped, not whole-system health.
- Mac desktop comes first; iOS remains later.
- No app name, product name, codename, mascot, logo, slogan, or brand identity is authorized here.
- PC WSL `/home/openclaw` is canonical. Mac `OpenClaw_Watch` is reflection/source-reference only.

The import also does not authorize image generation, final UI decisions, source-set generation, app implementation, backend/schema/SQLite work, ingestion, Mac import, file sync, cleanup, deletion, movement, private-data inspection, provider/model calls, runtime mutation, approval mutation, communications sends, financial account access, or bank access.

## Read-Only V1 Surface Mapping

| World model place | Read-only v1 app surface | Allowed v1 display | Must not imply |
| --- | --- | --- | --- |
| Bridge / Captain's View | Default first screen / ambient watch | active context, watch state, source freshness, blocked/review counts, next safe action hint, compact evidence meter | hidden action, surveillance, autonomous mutation, sensitive detail exposure |
| Helm | Next safe move / approval-adjacent decision instrument | current command, proposed action, evidence basis, risk reasons, confirm/defer/block posture | approval without receipt, execution, success, fake `AI recommends` authority |
| Chart Room | Evidence/freshness drawer or drill-down | source refs, manifest basis, freshness, unknowns, contradictions, route traces, packet readiness | runtime control, finance posting, certainty without evidence, private-content exposure |
| Engine Room | Runtime/system status surface, future only in read-only form | observed system facts, queue/model/agent lane summaries, sync/disk indicators when evidenced | service restart, self-heal, provider/model calls, mutation authority |
| Cargo Hold | Storage/staging/protected-source surface, future only in read-only form | storage manifests, staging candidates, blocked sensitive sources, local-only markers | deletion, cleanup, sync, ingestion, cloud movement, raw private previews |
| Radio Room | Communications status/draft-routing surface, future only in read-only form | draft refs, contact verification refs, channel state, blocked send reasons | auto-send, hidden message inspection, private-message exposure |
| Treasury / Purser's Office | Finance/receivables/obligations surface, future only in read-only form | invoice refs, receivable states, obligation cards, CPA-readiness markers, mismatch reasons | bank access, payment/posting, final financial truth, `AI accountant` autonomy |
| Studio Bay / Workshop | Creative production/client-project surface, future only in read-only form | project state, asset refs, delivery packet status, client approval state, blocked dependencies | DAW imitation, client/private leakage, delivery without approval |
| Ports | Context/domain/project selector | port/context cards, route previews, risk class, local-only boundary, next Launch Packet hint | cross-company data blending, permission escalation, literal game navigation |

Captain's Quarters, Dock / Land, Offices / Client Sites, and Transit are important for later planning, but they should not force v1 scope expansion. In v1 they are best represented as future mode constraints and breadcrumb rules, not separate implemented surfaces.

## Backend/Data-Contract Readiness Concepts To Plan Later

This addendum does not create schema. It does add concepts that 17/18 should plan before backend/schema/SQLite work begins.

Future conceptual fields or records to evaluate:

- `operator_place`: Bridge, Helm, Chart Room, Engine Room, Cargo Hold, Radio Room, Treasury, Studio Bay, Ports, or future scoped places.
- `authority_scope`: what kind of authority the surface represents, such as ambient watch, current command, evidence review, runtime observation, storage/staging, communications review, finance review, creative production, or context selection.
- `active_context`: personal ship, project, client, company, life domain, external site, or future scoped deployment.
- `allowed_surface`: which read-only surface may display the record.
- `forbidden_implications`: what the record must not imply when displayed.
- `context_transition`: explicit route between contexts or authority scopes.
- `sensitive_boundary`: local-only, sensitive, unknown, blocked, or unavailable visibility constraints.
- `evidence_home`: where the full evidence belongs when summarized elsewhere.
- `decision_home`: whether a proposed action belongs at Helm, in a Launch Packet review, or outside v1 entirely.

Future relationship rules to evaluate:

- A record can be visible on Bridge only if its evidence/freshness basis is summarized or linked.
- A proposed action belongs at Helm only as read-only planning unless a separate Approval Receipt and execution contract exist.
- Evidence summaries on Helm or Bridge must link back to Chart Room-style evidence basis.
- Runtime observations can surface on Engine Room but do not authorize service mutation.
- Storage and staging records can surface on Cargo Hold but do not authorize ingestion, cleanup, deletion, sync, or file movement.
- Ports and context selectors must not cross-contaminate records across companies, clients, projects, or life domains.
- Unknown or blocked records must not flow into claims, promotions, packets, or conversation summaries without explicit review rules.

These are contract-readiness concerns only. They should be expressed first in Markdown/table planning and static validation expectations before any JSON Schema, SQL DDL, SQLite database, fixture generation, ingestion, or app code exists.

## Relationship To 17 And 18

This document is an addendum to `17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md` and `18_BACKEND_DATA_CONTRACT_SHAPE_PLAN.md`. It is not a replacement for either file and does not edit them in this slice.

Before generating `04_BACKEND_DATA_CONTRACT_READINESS`, edit 17 to absorb this addendum. The 17 adjustment should:

- update freshness/source basis to mention the visual/spatial import and this addendum;
- preserve that the prior 24-file source set is stale relative to `bb635e6` for visual/world-model planning;
- add mode/place authority as an unresolved readiness topic before backend/schema work;
- add this addendum as the best candidate for the open content slot in the future 23-content-file source set, unless the operator chooses a broader full refresh that includes selected visual/research docs directly;
- add validation expectations that first-screen and data-contract planning preserve Bridge/Helm/Chart Room/Engine Room/Cargo Hold/Radio Room/Treasury/Studio Bay/Ports as authority-scoped surfaces, not decorative metaphors.

Edit 18 afterward only when the conceptual record-shape lane is active or if 18 will be included as current authority in a generated source set. The 18 adjustment should add place/surface/authority-scope concepts without creating schema. If 18 is not being used as current generation authority, this addendum can carry the bridge until that lane opens.

Answer: yes, `17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md` should be adjusted before source-set generation. This addendum is the planning input for that edit.

## Recommended Next Repo-Side Docs-Only Update

Next recommended update after this addendum is committed:

1. Edit `17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md` only.
2. Add this addendum to its source basis and candidate `04_BACKEND_DATA_CONTRACT_READINESS` file list.
3. Add a small section named `World-Model / Mode-Authority Readiness`.
4. Preserve all no-implementation boundaries.
5. Run `git diff --check` and the existing static checker/test only if the task explicitly asks for validation beyond docs diff checks.

Do not edit 18 in the same slice unless the operator explicitly asks to activate the record-shape lane.

## Hard Boundaries

This addendum does not authorize:

- app implementation;
- UI code;
- backend/schema/SQLite work;
- SQL DDL;
- SQLite DB creation;
- ingestion;
- fixture generation;
- Mac file import;
- sensitive/private inspection;
- file cleanup, move, delete, or sync;
- provider/model calls;
- runtime/service/approval mutation;
- communications sends;
- financial account or bank access;
- app naming, branding, logos, mascots, slogans, or product commitments.

PC WSL `/home/openclaw` is canonical. Mac `OpenClaw_Watch` is reflection/source-reference only.
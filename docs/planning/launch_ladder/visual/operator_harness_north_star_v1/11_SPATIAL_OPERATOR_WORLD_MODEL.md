# Spatial Operator World Model

## 1. Purpose

This file captures the broader future spatial interaction model behind Operator Harness / Mission Control.

It extends the Winship Operator Ship metaphor into a world model that can work in the current 2D desktop app while preserving boundaries a future spatial interface could render as dock, ship, rooms, ports, offices, client sites, and transit between scopes.

This is visual planning, taste, and interaction-model capture only. It does not authorize app implementation, runtime behavior, provider calls, file movement, sync, financial access, communications sends, or authority changes.

## 2. Core Thesis

Operator Harness should be designed so its modes can later become spatial places.

The core doctrine is:

Spatial movement equals authority and context transition.

The spatial model is not a pretty metaphor layered over ordinary tabs. It is a discipline for keeping work, evidence, authority, and consequence in their correct places.

The digital environment should train the operator's real-world operating instincts:

- evidence belongs in the Chart Room / source registry
- runtime health belongs in the Engine Room
- money work belongs in the Treasury / Purser's Office
- communication belongs in the Radio Room
- creative production belongs in the Studio Bay / Workshop
- private planning belongs in Captain's Quarters
- current decision authority belongs at the Helm
- context switches are explicit journeys, not accidental tab chaos

## 3. 2D Now, Spatial Later

The current product target is a 2D desktop app. The 2D app does not need literal rooms, travel animations, or spatial chrome.

It should preserve the same conceptual boundaries through:

- mode names and mode-specific surfaces
- strong breadcrumbs showing active context and authority scope
- visually distinct sensitive/local-only areas
- source, freshness, authority, and blocked-state indicators
- explicit transitions between project, client, company, and life-domain contexts
- controls that separate navigation, review, approval, execution, and evidence-backed result

The 2D app should avoid collapsing everything into generic tabs, dense dashboards, or a single chatbot stream. A future Apple Vision Pro or spatial computing version should be able to render the same model as places without changing the underlying authority doctrine.

## 4. Places And Authority Scopes

| Place | Authority scope | Work that belongs there | Work that does not belong there |
| --- | --- | --- | --- |
| Dock / Land | Lightweight real-world-accessible surface | Messages, reminders, quick status, lightweight approvals, Telegram-like interactions | Deep evidence review, runtime mutation, finance operations, private planning |
| Ship | Personal Operator Harness command vessel | Personal command environment, watch, routing, scoped rooms, operator authority | External organization data unless explicitly entered through a scoped port/client site |
| Bridge / Captain's View | Ambient watch window | Watch state, current world, status, source freshness, next safe action hints | Hidden action, fake autonomy, sensitive detail exposure |
| Helm | Current command authority | Steering, next safe action, approval, defer/block decisions | Background execution without approval, vague suggestions without evidence |
| Chart Room | Evidence and route authority | Source registry, evidence map, freshness, unknowns, contradiction review, route planning | Runtime controls, finance posting, private journaling |
| Engine Room | System/runtime authority | Runtime health, services, agents, local models, queues, disk, sync | Money decisions, communications sends, private notes, client content review |
| Cargo Hold | Storage and staging authority | Files, archives, backups, ingestion staging, protected storage | Deletion, sync, cloud movement, or ingestion without explicit authority |
| Radio Room | Communication authority | Drafts, mail, Telegram, contacts, inbound/outbound channel state | Auto-send implication, hidden message inspection, finance posting |
| Treasury / Purser's Office | Financial review authority | Invoices, receivables, obligations, ledger, CPA/tax readiness | Runtime repair, private reflection, casual chat, unapproved bank access |
| Studio Bay / Workshop | Creative production authority | Music, video, client projects, creative assets, delivery packets | Finance operations, private planning, cross-client data mixing |
| Captain's Quarters | Private operator authority | Private planning, reflection, goals, briefs, operating doctrine | External sends, runtime mutation, client data access without scope |
| Ports | Context selection authority | Projects, clients, companies, life domains, scoped launch destinations | Cross-port data blending, invisible authority changes |
| Office / Skyscraper / Client Site | External organization scope | Scoped organization workspace with its own data, roles, approvals, and work surfaces | Personal ship assumptions, cross-client leakage, inherited authority |
| Helicopter / Jet / Transit | Transition authority | Context transition and authority-scope change | Gimmick travel, implied execution, sync, provider calls, file moves |

## 5. Dock / Land Mode

Dock / Land is the lightweight real-world-accessible surface.

It is for messages, reminders, quick status, lightweight approvals, Telegram-like interactions, and short real-world interruptions. It should feel reachable without making the operator feel fully inside the ship.

Dock / Land can answer questions like:

- What needs my attention?
- What is safe to approve quickly?
- What changed since I last checked?
- Which journey should I enter next?

Walking from dock to ship means entering the operator's personal command environment. That transition should be explicit because it changes the operator's posture from quick-access triage to command.

## 6. Ship Mode

Ship Mode is the personal Operator Harness command vessel.

The ship is not a literal game space. It is the operator's durable command environment, organized into places that make work boundaries visible.

The ship contains:

- Bridge / Captain's View for ambient watch
- Helm for current command and approval
- Chart Room for evidence, sources, freshness, unknowns, and route planning
- Engine Room for runtime health, services, agents, models, queues, disk, and sync
- Cargo Hold for files, archives, backups, ingestion staging, and protected storage
- Radio Room for communications, drafts, mail, Telegram, and contacts
- Treasury / Purser's Office for invoices, receivables, obligations, ledger, and CPA/tax readiness
- Studio Bay / Workshop for music, video, client projects, and creative production
- Captain's Quarters for private planning, reflection, goals, briefs, and operating doctrine

Going to the Engine Room means inspecting system/runtime health. It does not mean inspecting finances, reading private notes, sending mail, or changing services.

## 7. Ports And Client Sites

Ports represent contexts: projects, clients, companies, life domains, and major work destinations.

A port can lead to an external organization workspace such as an office, skyscraper, or client site. That workspace has its own scoped data, roles, approvals, evidence, files, and work surfaces.

Going to a Texas office/client site, for example, means entering that organization's scoped OpenClaw build with separate permissions, evidence, files, approvals, and operating rules.

Leaving a port or client site means leaving that authority scope.

Ports must make boundaries explicit:

- what organization or domain is active
- what role or authority basis is active
- what data is local-only, sensitive, blocked, or unavailable
- what evidence is fresh enough to use
- what actions require approval
- what must never cross into another port

## 8. Transit As Context Switch

Transit is the model for context switching and authority-scope change.

Helicopter, jet, corridor, gangway, route line, or other transit language should only mean transition. It should not become gimmick travel, game navigation, or an excuse to hide work.

Transit can represent:

- moving from Dock / Land into the Ship
- moving from the Ship to a Port
- entering a client site or external organization workspace
- returning from a scoped site to the personal command environment
- leaving a sensitive/local-only area

A transit animation or transition state does not authorize provider calls, sync, file moves, email sends, bank access, runtime mutation, or inspection of private data.

## 9. Real-World Mental Model Training

The digital experience should help the operator act better outside the software.

The interface should reduce tab chaos, sloppy folder behavior, vague task switching, and mixed authority contexts by making every kind of work feel like it belongs in the right place.

The digital place model should teach:

- where things belong
- what kind of decision is being made
- what evidence is required
- what authority is active
- what is blocked
- what should be deferred
- what should never be mixed

This means the visual model has behavioral consequences. If the operator learns that evidence goes to the Chart Room, that instinct should transfer to real-world file organization, meetings, planning, audit trails, and client work.

The model should make sloppy mixing feel wrong:

- finance decisions should not feel like casual messages
- runtime health should not feel like creative review
- client work should not feel like personal planning
- source evidence should not be buried in chat
- private doctrine should not leak into external authority
- quick dock approvals should not feel like full command review

## 10. Safety And Authority Rules

Spatial metaphor must never imply access authority.

Rules:

- A beautiful room does not mean data is safe.
- A port/client site does not imply permission to inspect client data.
- A transit animation does not authorize provider calls, sync, file moves, email sends, bank access, or runtime mutation.
- Places must show freshness, source, authority basis, and local-only/sensitive boundaries.
- Sensitive/local-only areas must be visually and structurally distinct.
- Navigation is not approval.
- Approval is not execution.
- Execution is not success.
- Success requires evidence-backed result state.
- Source existence is not source authority.
- Context selection is not permission escalation.

The world model should make boundaries easier to see, not easier to bypass.

## 11. Future Apple Vision Pro / Spatial Computing Possibility

A future spatial computing version could render this model as a navigable operating world:

- Dock / Land as a lightweight surface for real-world-accessible interactions
- Ship as the personal command vessel
- Bridge / Captain's View as the ambient watch window
- Helm as the focused command and approval station
- Chart Room as the evidence and source registry space
- Engine Room as the runtime health and systems space
- Cargo Hold as protected file/archive/storage space
- Radio Room as communication and channel-routing space
- Treasury / Purser's Office as financial obligations and CPA-readiness space
- Studio Bay / Workshop as creative production space
- Captain's Quarters as private planning and doctrine space
- Ports as scoped contexts and launch destinations
- Office / Skyscraper / Client Site as external organization workspaces
- Transit as explicit context and authority-scope transition

This possibility should inform today's mode boundaries, language, and interaction model. It should not force today's 2D app into literal spatial novelty.

## 12. What This Does Not Authorize

This file does not authorize:

- final app UI decisions
- app implementation
- backend/schema implementation
- source-set generation
- image generation
- provider/model calls
- private or sensitive file inspection
- runtime/service mutation
- sync
- file moves
- ingestion
- email, Telegram, or other communications sends
- financial account access
- bank access
- autonomous agent behavior
- permission changes
- commits

It is a planning and taste artifact only.

## 13. Relationship To Existing Visual Packet Files

This file extends:

- `01_NORTH_STAR_AND_TASTE.md` by preserving the ship/world metaphor as a future spatial model even while the app remains 2D.
- `04_MODE_DIRECTIONS.md` by treating modes as future places with distinct work, evidence, and authority boundaries.
- `10_OPERATOR_SHIP_METAPHOR_MAP.md` by adding Dock / Land, external offices/client sites, transit, and real-world mental model training.

It should stay consistent with the hard avoids in `06_HARD_AVOIDS.md`: no generic AI assistant imagery, no fake autonomy, no over-literal ship costume, no unsafe authority implication, and no sensitive-data exposure.

## 14. Recommended Next Use

Use this file as input for future navigation/modeling docs.

Good next uses:

- mode/navigation architecture discussion
- spatial-ready information architecture notes
- authority-scope breadcrumb design
- real-world work-organization doctrine
- future Apple Vision Pro / spatial computing exploration
- visual prompt refinement without generating images

Do not use it as direct implementation authority. Any future build step needs a separate bounded implementation prompt, evidence basis, file scope, safety boundaries, and validation plan.

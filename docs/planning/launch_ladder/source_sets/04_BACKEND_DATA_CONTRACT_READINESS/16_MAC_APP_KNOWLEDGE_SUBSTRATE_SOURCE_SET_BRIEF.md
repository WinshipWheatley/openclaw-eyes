# Mac App Knowledge Substrate Source Set Brief

Status: docs/source-set generation brief for `03_MAC_APP_KNOWLEDGE_SUBSTRATE`. This file does not create implementation, UI code, backend/schema files, SQLite databases, ingestion scripts, provider/model calls, runtime behavior, audio assets, haptic behavior, notification behavior, or app naming.

Freshness:

- Generated/reviewed: 2026-05-02
- Source-set basis before generation: local commits through `33566561a9f9ec775cf6f0a7295386658bae60a9`
- Source basis: Mac desktop Mission Control fixture contract, first-screen composition spec, taste/atmosphere spec, sound/haptics quiet feedback addendum, Compiled Knowledge Substrate planning package, Launch Ladder authority/evidence contracts, and static validation map.
- Stale when: any included source file changes, source-set file membership changes, the naming boundary changes, implementation starts, or knowledge-substrate doctrine changes.
- Refresh trigger: regenerate the 24-file source set before the next serious ChatGPT Project planning pass or before backend/data-model/app implementation is requested.

## Purpose

`03_MAC_APP_KNOWLEDGE_SUBSTRATE` is the combined ChatGPT Project source set for the next serious app/knowledge planning pass. It is not an implementation source set.

The folder combines:

- Mac desktop Mission Control app planning;
- read-only fixture contracts;
- first-screen composition;
- taste/atmosphere posture;
- sound/haptics/quiet feedback posture;
- SQLite-backed Compiled Knowledge Substrate planning;
- naming boundary;
- no implementation, no ingestion, and no runtime boundaries.

It exists because `02_MAC_IOS_APP_BUILD` produced enough app-facing contracts that the next chat needs a compact but complete planning packet. This 03 source set should help plan the Mac desktop app and knowledge substrate together before any backend/data-model or Mac UI implementation begins.

## Position In The Source-Set Ladder

The current active source-set ladder is:

```text
01_CURRENT_PRODUCT_SPEC -> 02_MAC_IOS_APP_BUILD -> 03_MAC_APP_KNOWLEDGE_SUBSTRATE -> future backend/data-model source set
```

`03_MAC_APP_KNOWLEDGE_SUBSTRATE` is still planning context. It does not authorize schema work, SQLite implementation, file ingestion, UI implementation, runtime polling, provider/model calls, or private-data inspection.

The likely next folder after this one is a backend/data-model source set, but only after this combined app/knowledge planning pass decides which records, synthetic fixtures, schema style, and operator-promotion contracts are stable enough to formalize.

## Non-Negotiable App Boundaries

- Do not name the app.
- Do not invent product names, codenames, mascots, slogans, logos, or brand identity.
- Use only neutral phrases: Mac desktop app, Operator Harness app, personal operator console, Mission Control surface.
- Mac desktop app first; iOS companion later.
- The app is a personal/custom operator console for Winship/operator first.
- Workspace Launch Profiles are navigation-only.
- Launch Packets are bounded action objects for review and possible later execution.
- Launch Packet existence does not mean approval.
- Approval Receipts are explicit operator authorization bound to one packet/action/scope.
- UI State Claims require evidence/freshness proof.
- The Mission Control surface is read-only planning until a separate implementation slice is approved.

## Knowledge Substrate Doctrine

The Compiled Knowledge Substrate is central to the direction but not yet implementation.

Core phrase:

```text
SQLite stores the memory; markdown speaks it; HTML preserves shape; FTS finds it; compiled notes make it useful.
```

Preserve these rules:

- This is not vanilla RAG and not classic flat chunk-vector RAG.
- Retrieval finds candidates; compilation creates durable inspectable knowledge.
- SQLite is the canonical future local memory substrate concept.
- Markdown is an export/handoff surface, not the database authority.
- HTML/rich fragments preserve source shape.
- FTS5/search finds records quickly.
- Compiled notes make recurring knowledge useful.
- Raw files are evidence, not truth.
- Extracted text is parsed evidence, not truth.
- Rendered fragments preserve shape, not truth.
- Compiled notes are interpretation, not truth.
- Claims are evidence-backed and confidence-bounded, not truth by default.
- Operator promotions are explicit acceptance, rejection, historical marking, sensitivity marking, or exclusion.
- Unknown means unknown and defaults restricted.
- Sensitive content is local-only by default.
- No real business-file ingestion is authorized.
- No external model access to raw/extracted sensitive content is authorized.
- Secrets/credentials must never be summarized into prompts.

## Mission Control Planning Doctrine

The Mac desktop first screen should feel like a calm cockpit / personal command desk. It should show operating context, active lanes, current focus, next safe move, evidence/freshness, recent changes, and future knowledge context without implying hidden work.

The first screen must preserve:

- next safe move, not task-manager sprawl;
- knowledge context, not a RAG search box;
- blocked means protected boundary, not panic;
- unknown means unknown;
- local-ahead state must not be represented as synced/current without push evidence;
- nothing moves just because it is visible.

The Product Taste / Operator Experience Eval Spine must reject fake intelligence, vague agent status, hidden authority/execution, generic admin-panel energy, chatbot slop, noisy dashboard fill, and evidence buried too deeply to trust.

## Sound And Quiet Feedback Doctrine

Sound is off by default for v1. Quiet feedback is opt-in only. Critical information must never be sound-only.

If sound is ever evaluated later, it must be short, low-volume, low-frequency, non-melodic, and tied only to visible state transitions. This source set does not authorize audio assets, sound asset folders, haptic implementation, notification behavior, sound settings UI, or app code.

Forbidden patterns include AI thinking sounds, sci-fi sweeps, startup chimes, notification spam, casino/game pings, dramatic warning alarms, hidden-worker sounds, chatbot message sounds, ambient "system is alive" hum, and anything implying background action without visible evidence.

## What This Source Set Must Not Do

- No SwiftUI/AppKit implementation.
- No backend/API/schema implementation.
- No SQLite DB creation.
- No ingestion scripts.
- No real business-file scanning.
- No private-data, vault, log, LegalPrivate, secrets, Gmail, or cloud-drive inspection.
- No provider/model calls.
- No service control.
- No runtime mutation.
- No approval mutation or Guardian control.
- No audio assets, haptic implementation, notification behavior, or sound settings UI.
- No app/product/brand/codename/mascot/logo/slogan.

## Upload Rule

The generated folder must contain exactly 24 files total:

- 23 content files.
- 1 `MANIFEST.md`.

`CHAT_STAY_UP_TO_DATE.md` remains adjacent bridge context at the Operator Harness readiness root. It must not be copied into `03_MAC_APP_KNOWLEDGE_SUBSTRATE` and must not be counted inside the 24 files.

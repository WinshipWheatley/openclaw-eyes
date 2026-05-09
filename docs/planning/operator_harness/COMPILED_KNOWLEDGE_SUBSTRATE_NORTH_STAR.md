# Compiled Knowledge Substrate North Star / Activation Readiness Spec
Status: docs-only design capture / activation readiness spec. This file does not authorize SQLite implementation, ingestion, database creation, provider/model calls, embeddings, runtime wiring, Cassandra/Chief/Telegram activation, private-root inspection, Mac Watch mutation, commits, or pushes.
Current frontier reference: `a3da5ec feat(operator): add natural language question response path`
## 1. Executive Summary
OpenClaw is not building generic RAG.
OpenClaw is building a local Compiled Knowledge Substrate: a durable, inspectable, evidence-aware memory layer where SQLite is the local system-of-record and authority spine, retrieval finds candidate material, compilation turns evidence into structured notes and claims, and explicit operator promotions decide what becomes accepted working context.
The substrate should behave more like a local, evidence-backed LLM wiki than a pile of chunks in a vector database. Raw files remain evidence. Parsed text remains parsed evidence. Claims remain claims until reviewed. Draft compiled notes remain interpretation until promoted. Promoted compiled notes become scoped, source-backed working context only after explicit operator acceptance. Answers and actions must expose their source basis, freshness, confidence, sensitivity, and authority state.
Natural language can eventually ask the substrate useful questions, request bounded handoffs, or frame safe next moves. Natural language does not grant execution authority, ingestion authority, provider-call authority, private-root access, external-send authority, or runtime activation.
The readiness target is a safe local knowledge loop:
```text
source material -> parsed evidence -> observations -> claims -> draft compiled notes -> operator promotions -> promoted compiled notes -> grounded answers/actions
```

The key activation rule:

Retrieval finds candidates. Compilation creates durable inspectable knowledge. Operator promotion decides what becomes accepted working context.

## 2. What This Is

The Compiled Knowledge Substrate is the future local memory and evidence layer for Operator Harness. It should support:

* SQLite as the local system-of-record / authority spine;
* local-first source awareness;
* evidence provenance;
* source shape preservation;
* parsed text and extraction warnings;
* structured observations;
* confidence-bounded claims;
* durable draft compiled notes;
* scoped promoted compiled notes;
* explicit operator promotions;
* freshness and stale-condition tracking;
* sensitivity and export boundaries;
* human-readable conversation packets;
* Cassandra/Chief-facing answers that remain grounded and non-authorizing unless a separate Covenant grants authority.

The concept is inspired by Karpathy-style / LLM-wiki thinking:

* durable knowledge should be compiled, inspectable, and revisable;
* retrieval should not be the final answer;
* repeated context should become structured substrate instead of being rediscovered every chat;
* operator judgment should be represented explicitly, not inferred from model text.

The substrate is intended to make OpenClaw better at answering questions such as:

* What do we actually know?
* What evidence supports that?
* What is stale?
* What is contradicted?
* What is accepted working context?
* What is draft interpretation only?
* What is historical-only?
* What is sensitive or blocked from export?
* What should Cassandra or Chief say without overclaiming?
* What can be handed to a worker without granting authority?

## 3. What This Is Not

This is not generic vector RAG.

It is not:

* a chunk-and-embed-first retrieval pile;
* a chatbot memory dump;
* hidden canonical memory;
* automatic truth promotion;
* provider/model-call authorization;
* private-root ingestion authorization;
* legal/client/invoice/secrets access authorization;
* a runtime daemon;
* a Cassandra/Chief/Telegram integration plan;
* a database migration;
* a SQLite schema implementation;
* an embedding plan;
* a PageIndex dependency;
* a graph database commitment;
* an MCP/shared-memory activation;
* an approval engine;
* a substitute for Operator Action Covenant authority.

The substrate must not collapse into:

```text
split documents -> embed chunks -> retrieve top-k -> summarize as truth
```

That path loses document shape, weakens provenance, hides uncertainty, and makes model output feel more authoritative than the evidence supports.

## 4. Core Lifecycle

The required lifecycle is:

```text
raw source
  -> parsed evidence
  -> rendered fragments
  -> extracted observations
  -> claims
  -> draft_compiled_note
  -> operator promotions
  -> promoted_compiled_note
  -> answers/actions
```

### Raw Source

Raw source is the original material or source reference. It may be a repo document, Mac Watch support file, business file, legal file, invoice artifact, contract, email, markdown note, PDF, app record, or other local artifact.

Raw source status does not imply permission to read, parse, summarize, export, send, or call a model.

### Parsed Evidence

Parsed evidence is extracted text, metadata, or structural information derived from a source. It must preserve:

* source identifier;
* parser/extractor identity;
* extraction timestamp;
* warnings;
* quality/confidence;
* sensitivity;
* withheld reason, if any;
* source basis.

Parsed evidence is not truth. It is just a safer, more usable representation of a source.

### Rendered Fragments

Rendered fragments preserve source shape where structure matters. Examples:

* contract sections;
* email threads;
* tables;
* invoices;
* financial statements;
* pages;
* headings;
* lists;
* quoted passages;
* layout-sensitive fragments.

Rendered fragments exist because flat chunks often destroy meaning. They should carry page/section/region information and shape warnings.

### Extracted Observations

Extracted observations are bounded, source-backed statements pulled from parsed evidence or rendered fragments.

Examples:

* “This document names X as the counterparty.”
* “This invoice shows amount Y.”
* “This email thread contains a deadline.”
* “This planning rail states runtime launch is not authorized.”

Observations should remain close to source language and avoid interpretive overreach.

### Claims

Claims are normalized statements that can be reasoned over, contradicted, compiled, accepted, rejected, or marked historical.

Claims need:

* claim text;
* claim type;
* source basis;
* evidence references;
* confidence;
* sensitivity;
* contradiction state;
* freshness state;
* review state.

Claims are not accepted truth by default.

### Draft Compiled Notes

A draft_compiled_note is a durable, inspectable interpretation built from evidence, observations, and claims. It should be human-readable and cite its basis.

A draft compiled note should include:

* title;
* body;
* source basis;
* evidence references;
* claim references;
* confidence;
* limitations;
* contradictions;
* freshness state;
* sensitivity/export state;
* promotion status.

A draft compiled note is not accepted truth. It is the system’s generated or compiled interpretation awaiting operator review, rejection, historical marking, sensitivity marking, exclusion, or promotion.

### Operator Promotions

Operator promotions are explicit decisions that change the authority state of a claim, note, source, or classification.

Promotion examples:

* accepted;
* rejected;
* marked historical;
* marked sensitive;
* excluded;
* needs review.

Promotion is the boundary between “the system found or compiled this” and “the operator accepts this as current working context.”

### Promoted Compiled Notes

A promoted_compiled_note is a draft compiled note that the operator has explicitly accepted into working context.

A promoted compiled note must remain:

* scoped;
* source-backed;
* reviewable;
* freshness-aware;
* sensitivity-aware;
* supersedable;
* non-executing by itself.

Promotion does not erase source basis. Promotion does not grant runtime, external-send, provider/model, MCP, private-root, invoice, legal, commit, push, or destructive authority. It only says the note may be used as accepted working context within its named scope.

### Answers / Actions

Answers and action frames are downstream surfaces. They must ground themselves in evidence and promotion state.

An answer should distinguish:

* accepted truth;
* promoted compiled notes;
* draft compiled notes;
* unreviewed claims;
* raw evidence;
* stale evidence;
* contradicted claims;
* sensitive/no-export material;
* unknowns.

Actions remain governed by the Operator Action Covenant. A substrate answer does not grant execution authority.

## 5. Evidence Vs Truth Doctrine

The substrate must preserve the difference between evidence, interpretation, and authority.

Doctrine:

* Raw files are evidence, not truth.
* Parsed text is parsed evidence, not truth.
* Rendered fragments preserve shape, not truth.
* Extracted observations are bounded readings, not truth.
* Claims are evidence-backed hypotheses unless promoted.
* Draft compiled notes are interpretation unless promoted.
* Promoted compiled notes are scoped accepted working context, not universal truth.
* Operator promotions define accepted working context.
* Receipts are proof snapshots, not approval.
* Natural language is intent, not authority.
* Model output is advice, not authority.
* Unknown means unknown.

The system must never smooth over uncertainty just to produce a confident answer.

If evidence is stale, contradictory, incomplete, sensitive, or unreviewed, the answer should say so.

## 6. Authority States

The substrate should model explicit authority states.

### Raw Evidence

A source exists or is referenced. It has not necessarily been parsed, reviewed, or accepted.

Allowed meaning:

* “This source exists or has been identified.”

Not allowed meaning:

* “This source is true.”
* “This source is safe to export.”
* “This source may be sent to a model.”
* “This source may be used for action.”

### Parsed Evidence

Text, metadata, or structure was derived from a source.

Allowed meaning:

* “The system parsed this source into usable evidence with stated warnings.”

Not allowed meaning:

* “The parse is complete.”
* “The parse is correct.”
* “The content is safe.”
* “The content is accepted truth.”

### Extracted Claim

A bounded claim was extracted or normalized from evidence.

Allowed meaning:

* “There is a claim with evidence basis and confidence.”

Not allowed meaning:

* “The claim is accepted.”
* “The claim is current.”
* “The claim can drive action.”

### Draft Compiled Note

Evidence and claims were compiled into a durable human-readable note.

Allowed meaning:

* “The system has an inspectable interpretation.”

Not allowed meaning:

* “The operator accepts it.”
* “It is canonical truth.”
* “It grants permission.”
* “It can override sensitivity, freshness, or contradiction warnings.”

### Promoted Compiled Note / Accepted Truth

The operator or another explicit authority record has promoted a claim or draft compiled note into current working context.

Allowed meaning:

* “This may be used as accepted working context within its named scope.”

Constraints:

* It remains scoped.
* It remains source-backed.
* It can expire.
* It can be superseded.
* It does not grant action authority by itself.
* It does not override sensitivity or export rules.

### Rejected Claim

The operator or review process rejected the claim.

Allowed meaning:

* “Do not use this claim as support for answers or actions except to explain that it was rejected.”

### Historical Context

The operator marks a source, claim, or note as historically relevant but not current-state authority.

Allowed meaning:

* “This matters as history.”

Not allowed meaning:

* “This describes the current state.”

### Sensitive / No-Export Material

The source, fragment, claim, or note is sensitive, private, legal, invoice/finance-related, secret-bearing, or otherwise blocked from export.

Allowed meaning:

* “The material may be referenced only according to its metadata and policy boundary.”

Not allowed meaning:

* “It may be summarized externally.”
* “It may be sent to a provider.”
* “It may be shown in a worker prompt.”
* “It may be used without a sensitivity check.”

## 7. Retrieval Strategy

The retrieval strategy should be layered and local-first.

### SQLite Authority Spine

SQLite is the intended local system-of-record and authority spine for the Compiled Knowledge Substrate.

That means SQLite should eventually hold durable records for:

* source records;
* parsed evidence;
* rendered fragments;
* extracted observations;
* claims;
* draft compiled notes;
* promoted compiled notes;
* operator promotions;
* sensitivity states;
* freshness states;
* contradiction states;
* conversation packets;
* audit/substrate events.

SQLite is not authorized for implementation in this docs-only pass. The point here is architectural: the authority spine should be local, inspectable, queryable, portable, testable, and explicit.

SQLite records should answer:

* What is the source basis?
* What is the authority state?
* What is accepted, rejected, historical, stale, contradicted, or sensitive?
* Which compiled notes are draft versus promoted?
* What can be exported?
* What still needs operator review?

### FTS As First Candidate Retrieval Layer

FTS is the first candidate retrieval layer, not the authority layer.

FTS should help find likely relevant records across:

* sources;
* extracted text;
* rendered fragments;
* observations;
* claims;
* compiled notes.

FTS ranking is not truth. FTS ranking is not approval. FTS ranking is not promotion. A high-ranked result is only a candidate that must still pass source, freshness, sensitivity, contradiction, and authority-state checks.

### Document Structure / PageIndex-Style Candidate Strategy

OpenClaw should preserve document structure for future hierarchical traversal.

A PageIndex-style or vectorless/tree-retrieval strategy is a design principle and future candidate strategy, not a v0 dependency.

Many important documents are structured:

* contracts;
* legal pleadings;
* invoices;
* finance records;
* planning rails;
* packet handoffs;
* source-set bridges;
* command maps;
* long emails;
* app specs.

The actionable lesson is not to adopt a vendor benchmark, dependency, or PageIndex implementation now. The actionable lesson is to preserve hierarchy, headings, pages, sections, summaries, and provenance so future retrieval can traverse structure rather than flatten it away.

For v0, this means the data model should not destroy structure before the system knows how it will use it.

### Relational Edges First, Graph Engine Later

Relationship behavior should start as ordinary relational edge tables inside the local substrate.

Useful edge concepts may include:

* source-to-fragment;
* source-to-observation;
* observation-to-claim;
* claim-to-claim contradiction;
* claim-to-compiled-note;
* draft-note-to-promoted-note;
* entity-to-source;
* entity-to-claim;
* matter/project/person/company relationships;
* promotion-to-target;
* freshness-to-target.

A graph engine should be deferred until relationship queries prove they need it. The substrate should not begin with a graph database commitment. It should begin with explicit relational edges that can be inspected, tested, exported, and migrated later if necessary.

### Vectors Optional Later

Vectors may be useful later for broad semantic discovery, fuzzy similarity, clustering, deduplication, or candidate recall.

Vectors must remain optional and subordinate to:

* SQLite authority state;
* source provenance;
* document structure;
* FTS;
* relational edges;
* sensitivity;
* freshness;
* operator promotion.

Vectors are never the authority layer. Vectors are never required for v0. Vector similarity must never decide accepted truth, export permission, action authority, or promotion state.

No v0 activation should require embeddings.

## 8. Why Classic RAG Is Insufficient

Classic RAG is insufficient because OpenClaw’s core problem is not merely “find semantically similar chunks.”

OpenClaw needs to preserve:

* local system-of-record authority;
* source authority;
* source shape;
* chain of evidence;
* sensitivity boundaries;
* operator acceptance;
* stale/contradicted state;
* compiled durable notes;
* action authority boundaries.

Classic RAG often fails by:

* flattening structure into detached chunks;
* losing page/section context;
* retrieving plausible but non-authoritative passages;
* blending stale and current material;
* treating top-k recall as enough;
* producing answer text without durable memory updates;
* hiding contradictions;
* making model synthesis feel like truth;
* weakening privacy/export boundaries;
* failing to distinguish draft interpretation from accepted working context;
* failing to distinguish evidence from accepted working context.

For OpenClaw, retrieval is only a candidate-selection step. The real value is compiled, reviewable, promotable knowledge backed by a local authority spine.

## 9. What Is Already Built

The current built substrate is a static, non-live foundation. It does not activate runtime or database behavior.

Already built:

1. Mac Watch Markdown Index v0
    * Indexes Mac Watch markdown support material into a bounded metadata/report surface.
    * Mac Watch material remains support material, not canonical repo authority.
    * It must not be moved, renamed, deleted, or mutated by the substrate.
2. Evidence Packet Generator v0
    * Turns a topic into bounded evidence packets from the Mac Watch index.
    * Produces support packets with authority banners.
    * Uses deterministic local ranking and bounded content.
    * It is a support-material bridge, not a canonical authority engine.
3. Evidence Ranking Fix
    * Improves relevance for evidence packet selection.
    * Keeps evidence selection bounded and deterministic.
4. Operator Intent Core v0
    * Classifies natural operator language into safe intent frames.
    * Grants no execution authority.
    * Distinguishes status, next safe action, Codex prompt request, Gemini review request, commit review, activation readiness, approval-sensitive actions, unsafe ambiguity, and stop/wait.
5. Evidence Bridge v0
    * Maps natural language to evidence surface names, bridge domains, response frames, and Covenant posture.
    * Selects evidence by name only.
    * Does not run receipts, read files, call providers, call MCP, persist state, or execute actions.
6. Action Covenant v0
    * Defines the local approval object shape for future authority-bearing actions.
    * Captures action, risk, authority level, evidence basis, checked boundaries, rollback, expiry, and exact confirmation.
    * Blocks restricted authority in v0.
7. Operator Prompt/Handoff Generator v0
    * Creates deterministic, non-authorizing worker handoffs.
    * Separates canonical repo evidence from Mac Watch support material.
    * Includes validation commands, stop conditions, forbidden lanes, implementation boundaries, and no-authority language.
8. Natural-Language Question Response Path v0
    * Converts normal operator phrasing into direct answers or worker handoff frames.
    * Remains local, static, and non-live.
    * Does not call providers, inspect runtime, use persistence, call MCP, read files, or send externally.
9. Packet 07 Rails and Handoff
    * Packet 07 records doctrine, prompt discipline, receipt/read-model carry-forward, and gated activation readiness.
    * File 01 remains roadmap authority.
    * Active handoff remains train log only.
10. Existing Knowledge Substrate Planning Docs

* 01_NORTH_STAR.md defines the compiled substrate direction.
* 02_SQLITE_LAYER_MODEL.md sketches conceptual SQLite layers only.
* backend_retrieval_strategy_breadcrumb_20260506.md preserves future retrieval flexibility and PageIndex/vectorless-RAG caution.

## 10. What Is Missing Before Activation

Before activation, OpenClaw still needs design and proof for a real substrate loop.

Missing:

1. Explicit schema contract
    * Conceptual tables are not enough.
    * Need a reviewed shape for source records, parsed evidence, rendered fragments, observations, claims, draft compiled notes, promoted compiled notes, promotions, freshness, sensitivity, packets, and audit events.
2. Fixture-only test corpus
    * Need synthetic/non-private fixtures that exercise the lifecycle.
    * Fixtures should include structured docs, stale claims, contradictions, sensitivity flags, draft note states, promoted note states, and rejected states.
3. Parser/extractor boundaries
    * Need exact rules for what can be parsed, what must be withheld, and how warnings are recorded.
    * No private-root ingestion before this is proven.
4. Claim and compiled-note model
    * Need deterministic data shapes for observations, claims, draft compiled notes, promoted compiled notes, contradictions, limitations, and citations.
5. Promotion workflow
    * Need explicit operator promotion actions and state transitions.
    * Promotion must be inspectable and reversible or supersedable.
6. Sensitivity and export gates
    * Need no-export states to propagate into answers, worker prompts, and conversation packets.
    * Sensitive material must not leak through summaries.
7. Freshness model
    * Need stale conditions, source hashes/timestamps, refresh triggers, and “unknown freshness” handling.
8. Read-only query surface
    * Need a safe local query function that can answer against fixtures without mutation, providers, embeddings, private roots, SQLite runtime activation, or runtime wiring.
9. Conversation packet shape
    * Need bounded packets for ChatGPT/Codex/Gemini/project-chat handoffs that preserve source basis and authority state.
10. Receipt/status proof

* Need static receipts proving the substrate remains local-only, non-live, non-provider, non-MCP, non-embedding, and non-authorizing.

11. Integration boundary

* Need Cassandra/Chief-facing contracts that consume substrate answers without becoming live ingestion, live action, or hidden authority.

12. Activation gate

* Need an explicit Operator Action Covenant or equivalent future approval before any live activation, ingestion, external model call, database runtime, or runtime wiring.

## 11. What “Natural-Language Activation” Means And Does Not Mean

Natural-language activation means the operator can eventually speak normally and have the system classify, frame, ground, and route the request safely.

It can mean:

* classify intent;
* identify the relevant evidence surfaces;
* search candidate records;
* answer status questions;
* name the next safe move;
* prepare a bounded worker handoff;
* explain what evidence is missing;
* explain what authority is missing;
* distinguish draft compiled notes from promoted compiled notes;
* draft a Covenant frame for a named future action;
* distinguish accepted truth from unreviewed claims.

It does not mean:

* natural language grants execution authority;
* “do the next thing” means run actions;
* “launch it” means start runtime;
* “send it” means external send;
* “ask Gemini” means call a provider;
* “look in the files” means inspect private roots;
* “remember this” means write hidden canonical memory;
* “make this accepted” means promote without explicit operator decision;
* “compile this” means ingest sensitive content;
* “answer from memory” means ignore freshness, sensitivity, and source basis.

Natural-language activation must preserve the existing loop:

```text
intent -> evidence -> covenant -> visible frame
```

For knowledge substrate work, the expanded loop is:

```text
intent -> evidence candidates -> compiled knowledge state -> authority state -> covenant posture -> answer or handoff
```

## 12. Cassandra / Chief User-Facing Role

Cassandra and Chief should eventually be user-facing surfaces over the substrate, not hidden authorities.

Their future role:

* make the substrate feel usable in ordinary language;
* reduce operator context burden;
* answer status and memory questions;
* explain what is known, unknown, stale, sensitive, contradicted, accepted, rejected, draft-only, or promoted;
* prepare bounded handoffs;
* ask for missing evidence or explicit promotion;
* route authority-bearing requests through the Action Covenant.

They must not:

* ingest private files by default;
* inspect legal/client/invoice/secrets roots;
* call providers from repo code;
* use embeddings before an explicit approved lane;
* mutate Mac Watch files;
* wire Telegram/live listeners as part of this spec;
* start runtime services;
* write hidden memory;
* promote claims without operator decision;
* send external messages;
* execute actions from natural language alone.

Cassandra can be the conversational face. Chief can be the operational framing layer. The substrate remains the evidence and compiled-knowledge layer. SQLite is the future local authority spine. The Covenant remains the power boundary.

## 13. Smallest Safe Next Implementation Slice

The smallest safe next implementation slice is fixture-only and local.

Recommended slice:

Define a static fixture-backed Compiled Knowledge Substrate contract with no database runtime.

Scope:

* create synthetic fixtures only;
* define Python dataclasses or typed dictionaries for the lifecycle states;
* model raw source, parsed evidence, rendered fragment, observation, claim, draft compiled note, promotion, promoted compiled note, and answer packet;
* model relational edges as plain fixture data, not a graph engine;
* add tests proving evidence-vs-truth boundaries;
* add tests proving draft compiled notes are not accepted truth;
* add tests proving promoted compiled notes remain scoped and source-backed;
* add tests proving accepted/rejected/historical/sensitive states affect answers;
* add tests proving no provider/model/MCP/embedding/SQLite/runtime/private-root behavior;
* add a static status function or receipt shape.

Allowed files for a future implementation slice should be narrow and explicit, for example:

* a new compiled_knowledge_substrate.py contract module;
* a new tests/test_compiled_knowledge_substrate.py;
* fixture docs under a safe test fixture path if needed;
* optional receipt integration only after the contract tests are stable.

Acceptance criteria:

* no SQLite connection;
* no migrations;
* no ingestion;
* no private files;
* no provider calls;
* no embeddings;
* no MCP;
* no Cassandra/Chief live wiring;
* deterministic tests;
* clear distinction between evidence, claim, draft compiled note, promoted compiled note, accepted truth, rejected claim, historical context, and sensitive/no-export material.

## 14. Non-Goals For v0

The following are explicitly out of scope for v0:

* SQLite implementation;
* SQL DDL or migrations;
* database files;
* ingestion jobs;
* private-root scanning;
* legal/client/invoice/secrets inspection;
* Mac Watch file mutation;
* provider/model calls;
* embeddings;
* vector database setup;
* PageIndex dependency or implementation;
* graph database dependency or implementation;
* MCP integration;
* hidden shared-memory writes;
* Cassandra live listener wiring;
* Chief runtime wiring;
* Telegram integration;
* UI/dashboard/app work;
* external sends;
* invoice generation, reconciliation, or collection;
* legal advice/action;
* commit or push automation;
* automatic operator promotion;
* treating receipts as approval;
* treating natural language as execution authority.

## Activation Readiness Rule

The substrate is not activation-ready until it can answer, from safe fixtures, all of the following without live behavior:

1. What evidence supports this answer?
2. Which claims are accepted, rejected, historical, stale, contradicted, or sensitive?
3. Which compiled notes are draft-only and which are promoted?
4. Which source fragments are being used?
5. What is unknown?
6. What cannot be exported?
7. What requires operator promotion?
8. What requires an Operator Action Covenant before action?
9. What validation proves the substrate did not call providers, use embeddings, inspect private roots, mutate files, launch runtime, call MCP, create or connect to SQLite, or send externally?

Until then, the Compiled Knowledge Substrate remains a design and fixture-proof lane only.
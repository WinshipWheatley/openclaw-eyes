# Cross-Repo Split, HITL, And Module Boundary Reconciliation v0

## Purpose

This audit explains how Repo A, Repo B, SQLite/read-models, HITL/Guardian
approval authority, and module boundaries relate before any Cassandra/Chief
capability is imported, deleted, blocked, ported, split, or packaged.

This is audit/spec only. No data was imported. No runtime was modified. Repo B
was inspected only as source evidence and was not executed.

## Source Basis

- Repo A source and docs in `/home/openclaw`.
- Repo B source filenames and safe code references in
  `/home/openclaw_external/openclaw-runtime`.
- Generated Repo A read-models already checked into `generated/read_models`.
- Operator-provided historical visual topology description from the pre-split
  system.
- The "Open claw vault" Obsidian vault was mentioned as context, but no broad
  vault content was read in this lane. The old visual topology is treated as
  non-canonical operator-provided evidence, not current truth.

## A. Repo Split Model

### What Repo B Represents

Repo B is best modeled as the pre-split capability tree. It is not random legacy
trash. It contains a broad attempted operating-system map with Chief at the
center and domain clusters around it: Cassandra, Guardian/HITL, album, finance,
marketing, communications, analytics, business consulting, infrastructure,
website, Trinity audit, and data/memory.

Repo B is still reference-only for current work:

- `repo_b_execution_allowed=false`
- no env sourcing
- no service starts
- no direct Telegram/Gmail/email sends
- no direct imports into Repo A runtime

### What Repo A Represents

Repo A is the current governed/canonical direction after the split. It contains
the newer deterministic spine:

```text
telegram_agent_intake
-> intent_records
-> Work Board / Agent Work Packet
-> Operator Action / Guardian
-> receipts/read-models
```

Repo A also still contains some legacy-shaped runtime files, including Chief,
Cassandra, Guardian, HITL, and ad hoc state references. Repo A is canonical as a
repo, but not every file in Repo A is canonical authority for every concern.

### What SQLite/Read-Models Represent

SQLite and read-models are the best current authority check because they encode
bounded records, no-authority flags, receipts, and operator-facing summaries.
Examples:

- `telegram_agent_intake.py`
- `intent_router.py`
- `work_board.py`
- `agent_work_packet.py`
- `operator_action.py`
- `operator_action_inbox.py`
- `module_registry.py`
- `project_capsule.py`
- `estate_read_model.py`
- `finance_invoice_evidence_packet.py`
- `capital_hilton_invoice_packet.py`
- `cassandra_chief_memory_authority.py`

### What Must Never Be Assumed

Do not assume SQLite coverage is complete. Current SQLite/read-model coverage is
partial and uneven:

- many newer planning surfaces are governed and read-model-backed;
- older Chief/Cassandra/HITL runtime paths still use JSON/JSONL/CSV/Markdown;
- some current approval paths still use `approval_pending.json`;
- generated read-models can be stale or volatile;
- a read-model summary is not proof that runtime wiring is complete.

## B. Historical Capability Map

The old visual topology is useful evidence that Repo B was an operating-system
tree, not a pile of unrelated scripts. It is not current truth.

| historical cluster | current Repo A representation | split status | shared dependencies | current posture |
| --- | --- | --- | --- | --- |
| Album Production | `niles_album_matrix` draft module, `chief_album_*` legacy files, music tests/docs | partially copied | Chief router/session, memory, HITL, album CSV/state, future Niles | reference-only until Niles lane |
| Fundo | `chief_fundo_*` legacy files, world/domain registry hints | partial/legacy | Chief router/session, music/art memory | defer operator review |
| Finance & Billing | `finance_invoice_evidence_packet.py`, `capital_hilton_invoice_packet.py`, legacy Chief/Cassandra finance logic | partially governed rewrite | Cassandra fact intake, Chief routing, Guardian/HITL, finance evidence | composite stack, not Cassandra-only |
| Marketing | `chief_marketing_brain.py`, module registry concepts only | mostly legacy | Chief router, album/content state, communications | reference-only |
| Communications | `telegram_agent_intake.py`, `cassandra_listener.py`, `cassandra_outreach.py`, `chief_listener.py` | partially copied and governed | Telegram intake, Cassandra, Chief, Guardian, memory | operator_comms_stack |
| System Health | `agent_presence.py`, recovery clearance docs/scripts, generated read-models | governed rewrite with dirty residue | Agent presence, recovery clearance, systemd status | Repo A governed, but volatile snapshots dirty |
| Research Intelligence | Hermes advisory seed, reflection/integration legacy brains | partial | read-models, Work Board, context selection | advisory-only |
| Analytics | `chief_analytics_brain.py`, read-model/report concepts | mostly legacy | Chief, data/memory, finance/album logs | reference-only |
| Business Consulting | project capsule/module bundle surfaces | governed rewrite | module registry, project capsule, report bridge | Repo A planning-only |
| Infrastructure | systemd service templates, agent presence, service freeze docs | partial | recovery clearance, systemd, Work Board | governed where receipt-backed |
| Website | `chief_website_*` legacy files | mostly legacy | Chief router, content/marketing state | reference-only |
| Trinity Audit | `chief_trinity_brain.py`, audit docs | partial | Chief, evidence/read-models | reference/advisory |
| Data & Memory | `cassandra_chief_memory_authority.py`, corpus/estate/read-model surfaces | governed substrate emerging | all modules | substrate dependency |

Clusters that map most cleanly to current Repo A governed surfaces:

- System Health -> `agent_presence.py` and recovery clearance.
- Finance & Billing -> finance evidence packet surfaces.
- Business Consulting -> module registry, bundle planner, project capsule.
- Data & Memory -> memory authority, corpus/estate/read-models.

Clusters partially copied into Repo A:

- Communications
- Album Production
- Finance & Billing
- Chief control plane
- Guardian/HITL

Clusters missing or not yet reconciled:

- Marketing as a governed module
- Website as a governed module
- Fundo as a governed module
- Analytics as governed, non-authorizing read-models
- Trinity Audit as a formal advisory packet family

Clusters that depend on shared Chief / Data & Memory / HITL / LLM / Telegram
infrastructure:

- Finance & Billing
- Communications
- Album Production
- Marketing
- Calendar/email/contact workflows
- Research/analytics/advisory workflows

Clusters that should remain reference-only for now:

- Repo B daemon/watchdog/worker loops
- direct sender surfaces
- raw LLM/router fallback behavior
- album CSV write authority
- old approval/HITL JSON as active authority until reconciled

## C. Cross-Repo Capability Reconciliation Method

Every Repo B capability, thought, or workflow should be reconciled with these
questions before it is ported, wrapped, blocked, or used as evidence:

1. Does Repo A contain the same concept?
2. If yes, is it an exact copy, partial copy, governed rewrite, superseded
   version, or mixed state?
3. If partial, what was lost in the repo split?
4. Is the concept represented in SQLite/read-models?
5. Is current Repo A behavior more governed than Repo B behavior?
6. Does the concept require private/raw data, model calls, network, send, or
   runtime activation?
7. Does it touch approval authority?
8. What is the correct fate?

Required fates:

- `already_governed_in_repo_a`
- `repo_a_partial_needs_reconciliation`
- `port_logic_to_repo_a`
- `register_as_evidence_source`
- `extract_structured_memory_to_sqlite`
- `keep_repo_b_reference_only`
- `authority_conflict_reconcile_first`
- `block_no_go`
- `defer_operator_review`

Use these fates differently from the Cassandra/Chief source fates. These are
cross-repo capability fates, not file-ingest fates.

## D. HITL Authority Map

### Repo A Approval/HITL Surfaces

| surface | storage/authority | observed role | current classification |
| --- | --- | --- | --- |
| `operator_action.py` | SQLite `operator_action_*` tables | allowlisted local action request/approval/execution/receipt path | current governed action path |
| `operator_action_inbox.py` | SQLite import/rejection tables | imports sanitized action request JSON from inbox paths | current governed inbox path |
| `chief_approval_brain.py` | `/mnt/c/OpenClaw/logs/approval_pending.json`, vault approval log | blocking Tier 0/1/2 approval gate with HMAC-bound action text | current but legacy-shaped authority |
| `chief_guardian_sender.py` | Telegram send path via env | sends Guardian approval requests; fails closed for button approvals without Guardian token | current runtime approval delivery, external send |
| `chief_guardian_listener.py` | Telegram listener, `chief_approval_brain.record_decision`, `telegram_agent_intake` | receives Guardian button/code decisions and records governed listener metadata | current runtime approval listener |
| `chief_approval_bridge.py` | `/mnt/c/OpenClawShared/album/choice_pending.json` | non-blocking Chief workflow choice prompt | current/legacy workflow choice state |
| `hitl_pending_store.py` | `/mnt/c/OpenClaw/logs/hitl_pending_state.json`, `hitl_audit.jsonl` | Cassandra pending action store with toggle and transaction policy | mixed/current candidate, not SQLite |
| `hitl_action_service.py` | wraps `hitl_pending_store.py` | validation/idempotency/service API for HITL queue | mixed/current candidate |
| `hitl_pending_action.py` | `/mnt/c/OpenClaw/logs/hitl_pending_actions.json`, `hitl_audit.jsonl` | older pending action queue | parallel/mixed legacy path |
| `hitl_notification_service.py` | Guardian notification send/callback tokens, `hitl_notifications.jsonl` | sends/handles HITL approval notifications | current/legacy external approval path |
| `guardian_schema_harness.py` | staging-only harness | pure validation, explicitly guards live pending path | safe test harness |
| `agent_presence.py` recovery clearances | SQLite `agent_recovery_clearances` | local-only Cassandra recovery clearance, fixed argv, single-use | current governed recovery clearance |

### Repo B Approval/HITL Surfaces

Repo B contains the older approval stack:

- `chief_approval_brain.py`
- `chief_approval_policy.py`
- `chief_approval_bridge.py`
- `chief_guardian_sender.py`
- `chief_guardian_listener.py`
- `hitl_flowchart_gen.py`
- approval/HITL task files and queue concepts
- Google broker approval hooks
- Cassandra protected-window checks around `approval_pending.json`

Repo B's approval model is conceptually valuable but runtime-unsafe by default
because it is env/token-backed, Telegram-send-capable, JSON-state-backed, and
intertwined with execution loops.

### Current, Legacy, Mixed, Unknown

Current:

- `operator_action.py` / `operator_action_inbox.py` for governed local action
  records.
- `chief_approval_brain.py` for current Tier 2 Guardian approvals.
- `chief_guardian_listener.py` and `chief_guardian_sender.py` for current
  Guardian Telegram approval UX.
- `agent_presence.py` recovery clearance for Cassandra fixed recovery.

Mixed:

- `hitl_pending_store.py` and `hitl_action_service.py` because they are in Repo
  A and tested as code, but store authority in Windows-side JSON/JSONL rather
  than the SQLite operator action path.
- `hitl_pending_action.py` because it appears to be a parallel older pending
  action store.
- `chief_approval_bridge.py` because it handles workflow choices, not execution
  approval, but uses shared language and Telegram routing.

Legacy/reference:

- Repo B approval files.
- old task backlog files.
- historical HITL generated diagrams.

Unknown:

- whether any current live service is actively using every HITL surface at this
  moment was not checked through runtime activation or raw logs in this lane.

### Is Old HITL JSON Still Used By Current Repo A?

Yes, at least some JSON/JSONL approval state is still used by current Repo A
code:

- `chief_approval_brain.py` reads and writes
  `/mnt/c/OpenClaw/logs/approval_pending.json`.
- `chief_router.py` routes approval replies through `has_pending_approval`,
  `get_pending_info`, `parse_reply_code`, and `record_decision`.
- `chief_guardian_listener.py` applies button/code decisions through
  `chief_approval_brain.record_decision`.
- `cassandra_listener.py`, `cassandra_briefing_brain.py`,
  `chief_cassandra_failure.py`, and status/reporting surfaces inspect
  `approval_pending.json` as a live blocker signal.
- `hitl_pending_store.py` and `hitl_pending_action.py` use Windows-side HITL
  JSON/JSONL stores.

Therefore old HITL JSON/JSONL must not be globally classified as obsolete
`block_no_go` yet.

### Cassandra Recovery Clearance Flow

Cassandra recovery clearance is separate from the generic approval JSON state.
Repo A has a governed local clearance flow in `agent_presence.py`:

1. request local Cassandra recovery clearance;
2. optionally request Guardian approval for that clearance;
3. approve the local clearance only for `cassandra` and the fixed
   `cassandra_systemd_user_start` action;
4. run `recover_agent.py --execute` separately after clearance;
5. mark the clearance used and write a recovery receipt.

This path is single-agent, single-action, single-use, fixed-argv, local-CLI
only, and receipt-backed. It does not create a general Telegram approval path
or an arbitrary command path.

### Source Of Truth Now

For new action authority, the safest target source of truth is:

1. `operator_action.py` and `operator_action_inbox.py` for action records and
   receipts;
2. Guardian/HITL as a second-factor approval dependency;
3. existing `chief_approval_brain.py` only as a current runtime bridge until
   reconciled;
4. `agent_presence.py` recovery clearances for Cassandra recovery only.

### Approval Surfaces To Quarantine As Authority Conflict

Quarantine these as `authority_conflict_reconcile_first` until a dedicated
HITL reconciliation lane proves their exact status:

- `/mnt/c/OpenClaw/logs/approval_pending.json`
- `/mnt/c/OpenClaw/logs/hitl_pending_state.json`
- `/mnt/c/OpenClaw/logs/hitl_pending_actions.json`
- `/mnt/c/OpenClaw/logs/hitl_audit.jsonl`
- `/mnt/c/OpenClawShared/album/choice_pending.json`
- Repo B approval/HITL files

Quarantine does not mean delete. It means do not import them as truth, do not
use them to approve future actions, and do not call them obsolete until current
runtime dependencies are resolved.

## E. Updated Classification For Old HITL JSON/JSONL

Updated classification:

```text
authority_conflict_reconcile_first
```

Reason:

- some files previously called "old HITL" are still referenced by current Repo A
  runtime code;
- some files are historical or parallel stores;
- some files may be logs/audits rather than decision queues;
- old HITL JSON must not become active approval authority by import;
- current approval code must not be broken by blunt deletion/blocking.

What must be proven before blocking:

- no current Repo A runtime path reads the file as active approval state;
- no current service relies on the file for pending decision routing;
- the file is not the only receipt for a recent approval decision;
- tests prove equivalent governed behavior elsewhere.

What must be proven before migrating:

- target SQLite tables preserve scope, action hash, requester, decision,
  timestamp, and no-bypass posture;
- old approval records are historical receipts only unless re-approved through a
  current gate;
- imports do not create executable approvals.

What must be proven before deprecating:

- current runtime no longer checks that file;
- docs and operators know the replacement surface;
- a rollback/read-only archive plan exists.

## F. Module Boundary Analysis

### 1. Cassandra Boundary

Cassandra cannot be treated as a clean standalone module today.

Hard/runtime dependencies:

- `cassandra_listener.py` for Telegram intake/replies.
- `telegram_agent_intake.py` for governed receive proof.
- `cassandra_brain.py` for current assistant behavior.
- `chief_approval_brain.py` / Guardian for protected sends and brokered actions.
- `chief_cassandra_failure.py` for failure escalation.
- ad hoc memory/state files such as contact nicknames, finance state, reality
  notes, and correspondence state.

Optional/capability dependencies:

- finance evidence packets;
- Google broker/email/calendar paths;
- voice/TTS/Whisper paths;
- Work Board / Agent Work Packet projection;
- module registry and report bridge.

What breaks if Cassandra is split out alone:

- approval/send gating;
- contact identity resolution;
- finance invoice context;
- failure escalation;
- Work Board/intent projection;
- governed receive/read-model proof;
- live operator expectation that Cassandra/Clara can answer safely.

Cleanest seam:

- split only `cassandra_clara_fact_intake` as a receive-only, no-send,
  metadata-only module;
- keep response generation, send, email/calendar, contact, finance, and recovery
  behind the shared operator communications stack and Guardian/HITL.

### 2. Chief Boundary

Chief is not a clean standalone app module today. It is both:

- deterministic control-plane concept in Repo A; and
- legacy agent runtime/router in Repo A/Repo B-shaped files.

Chief depends on:

- Telegram listener/router;
- session state;
- approval policy/brain/Guardian;
- domain brains;
- memory/state files;
- LLM fallback in old runtime paths;
- Work Board/Operator Action in the newer direction.

Many surfaces depend on Chief:

- Cassandra in legacy role defers routing/approval/execution to Chief;
- billing/album/fundo/marketing/calendar/email paths route through Chief;
- Guardian approval UX is currently Chief-owned in code naming and flow.

Recommended boundary:

- `chief_control_plane` should be deterministic and governed in Repo A;
- legacy Chief runtime/router remains reference or wrapped until each domain
  route is reconciled.

### 3. Cassandra + Chief Coupling

Cassandra and Chief are separable only at the narrow fact-intake boundary.
Current evidence supports a combined communications/orchestration stack:

- Repo B `capability_registry.py` says Cassandra defers routing, approvals,
  album workflows, billing, and execution to Chief.
- Repo A `cassandra_brain.py` still says Cassandra defers approvals, album,
  billing, and execution to Chief.
- `chief_router.py` routes Cassandra messages as one path among many.
- `cassandra_listener.py` calls Cassandra directly but still consults
  `approval_pending.json` and Chief failure handling.

Therefore Cassandra-alone is a false module boundary for invoice/contact/email
workflows. The practical module is an `operator_comms_stack` with Cassandra,
Chief routing, governed intake, memory authority, and Guardian/HITL dependencies.

### 4. Guardian/HITL Coupling

Guardian/HITL can be a standalone substrate module, but every action-capable
module depends on it.

Minimum required interface:

- immutable action/request id;
- requester and source lane;
- sanitized action summary;
- payload hash or bounded payload reference;
- risk tier / approval requirement;
- decision and decider;
- decision timestamp;
- receipt id;
- no execution until a current, scoped approval exists;
- no approval from imported legacy JSON.

### 5. Memory Authority Coupling

Cassandra/Chief memory authority is not just a Cassandra module. It is a
substrate dependency used by Cassandra, Chief, finance, Niles/music, Guardian,
and future client/project capsules.

Recommended boundary:

- keep memory source cataloging and evidence-status vocabulary in a shared
  `memory_authority_substrate`;
- keep Cassandra/Chief-specific source candidates as one seeded source set
  inside that substrate;
- do not put album, finance, or approval truth under Cassandra just because
  Cassandra can talk about them.

### 6. Finance/AP Coupling

The Capital Hilton / invoice workflow is a composite:

- Cassandra/Clara receives operator facts and drafts communications;
- finance evidence packet surfaces hold invoice/receivable facts;
- Work Board tracks missing items and next moves;
- Guardian/HITL gates send, portal submission, or payment-facing action.

It should not be modeled as a pure Cassandra module. The module boundary should
be `finance_ap_invoice_stack`, with Cassandra as an intake/draft collaborator.

### 7. Historical Cluster Mapping

| old cluster | likely shape | current Repo A representation | missing split-era capability | dependency | extraction risk |
| --- | --- | --- | --- | --- | --- |
| Album Production | stack | `niles_album_matrix` draft, legacy `chief_album_*` | governed album matrix import | Chief, memory, future Niles, HITL | high |
| Fundo | module later | legacy `chief_fundo_*` | governed Fundo module/capsule | Chief, music memory | medium |
| Finance & Billing | composite stack | finance packets, Capital Hilton packet, Chief/Cassandra legacy finance | structured receivable import and send gate reconciliation | Cassandra, Chief, Guardian, memory | high |
| Marketing | module later | legacy marketing/content brains | governed content/marketing module | Chief, album/content state | medium |
| Communications | stack | Telegram intake, Cassandra/Chief/Guardian listeners | approval/send consolidation, contact memory | Cassandra, Chief, Guardian, memory | high |
| System Health | substrate/module | agent presence, recovery clearance | cleanup dirty presence residue | agent presence, systemd, receipts | medium |
| Research Intelligence | advisory module | Hermes seed, reflection/integration legacy | no-authority advisory read-model | read-models, Work Board | medium |
| Analytics | advisory/read-model | legacy analytics brain | governed analytics read-model | data/memory, finance, album | medium |
| Business Consulting | planning module | project capsule, bundle planner | report bridge/client bundle next layers | module registry, capsule | low-medium |
| Infrastructure | substrate | service docs, recovery clearance | runtime ownership map | agent presence, Operator Action | high |
| Website | module later | legacy website brains | governed website packet | Chief, content/marketing | medium |
| Trinity Audit | advisory module | legacy trinity brain/docs | formal advisory packet | evidence core, Chief | medium |
| Data & Memory | substrate | memory authority, estate/corpus/read-models | shared source-fate catalog maturity | all modules | medium |

### 8. Recommended Module Shapes

| proposed_module_or_stack | included surfaces | dependencies | can_live_separate_repo | reason | extraction_risk | recommended_fate |
| --- | --- | --- | --- | --- | --- | --- |
| `cassandra_clara_fact_intake` | `telegram_agent_intake.py`, Cassandra listener hook, intent links | Chief intent routing, Work Board, memory source catalog | later | receive-only seam is cleanest Cassandra slice | medium | already_governed_in_repo_a |
| `chief_control_plane` | `intent_router.py`, `governed_intake_spine.py`, subset of Chief deterministic routing | Work Board, Agent Work Packet, Guardian | later | deterministic control plane should stay canonical in Repo A first | high | repo_a_partial_needs_reconciliation |
| `guardian_hitl_gate` | `chief_approval_brain.py`, `chief_guardian_*`, `operator_action.py`, HITL stores | Operator Action, Telegram approval, receipts | later | standalone substrate, but current state is mixed | high | authority_conflict_reconcile_first |
| `operator_comms_stack` | Cassandra listener/brain, Chief listener/router, Telegram intake, Guardian listener | memory authority, HITL, Work Board | no for now | current communications are intertwined | high | repo_a_partial_needs_reconciliation |
| `finance_ap_invoice_stack` | finance packets, Capital Hilton packet, Cassandra fact intake, Work Board | Guardian/HITL, memory authority | later | invoice/AP is finance plus comms plus approval | high | repo_a_partial_needs_reconciliation |
| `memory_authority_substrate` | `cassandra_chief_memory_authority.py`, classification pattern, estate/corpus refs | SQLite/read-models, module registry | later | substrate across modules, not Cassandra-only | medium | already_governed_in_repo_a |
| `agent_runtime_stack` | listeners, services, watchers, recovery policy | agent presence, systemd, Guardian | no for now | too runtime-coupled and unsafe to split prematurely | high | keep_repo_b_reference_only |
| `deterministic_evidence_core` | corpus, approved evidence, finance evidence, read-model exports | SQLite/read-models | yes/later | good reusable substrate once coverage matures | medium | already_governed_in_repo_a |
| `album_production_matrix` / Niles | future Niles rows, legacy album matrix concepts | memory authority, Work Board, Guardian | later | album has its own domain and should not be absorbed into Cassandra/Chief | high | defer_operator_review |

Use existing module registry names where possible:

- `chief_intent_routing`
- `cassandra_clara_fact_intake`
- `guardian_hitl_gate`
- `niles_album_matrix`
- `hermes_next_lane_advisory`
- `planner_runner_registry`
- `report_bridge_sanitized_summary`
- `project_capsule_bundle_blueprint`

## G. Impact On Cassandra/Chief Memory Import Decisions

The prior operator-reviewed structured import plan remains mostly useful, but
HITL must be revised.

Remains approved for later structured import, if operator later approves:

- contacts and nicknames
- company/contact relationships
- allowed email recipients / email permission posture
- invoice facts
- receivable/payment tracking

Remains evidence-source-only:

- Chief session/task memory
- Windows-side logs

Remains summarize/extract-only:

- Cassandra notes
- billing tracker CSV/PDF paths
- calendar/event notes metadata
- correspondence metadata

Now authority-conflict/reconcile-first:

- old HITL JSON/JSONL state
- `approval_pending.json`
- `hitl_pending_state.json`
- `hitl_pending_actions.json`
- `hitl_audit.jsonl`
- `choice_pending.json`

Reason: current Repo A code still uses some of these files as live approval or
workflow state, while newer Operator Action/SQLite authority also exists.

Remains delete-local-residue candidate:

- untracked `polish_loop/tasks/chief-cassandra-failure-*.md` files, but only in
  an explicit cleanup lane with operator approval. They were not read here.

Remains deferred:

- dirty generated `agent_presence` snapshots
- album/song progress state until a Niles lane
- marketing/website/Fundo/analytics clusters until module-specific lanes

## H. Next Safe Implementation Lane

Recommended next lane:

```text
Guardian HITL Authority Reconciliation v0
```

Purpose:

- produce a read-model/spec that enumerates every current approval/HITL surface;
- distinguish active approval authority, workflow choice state, historical audit
  state, and obsolete residue;
- update Cassandra/Chief memory source fate from `block_no_go` to
  `authority_conflict_reconcile_first` for old HITL files;
- define the minimum Operator Action / Guardian bridge without enabling send or
  execution;
- add tests that imported or historical HITL records cannot approve actions.

Do not import raw HITL contents in that lane. It should inspect code paths,
schema, docs, and generated metadata only.

## Direct Answers

- Repo B should be kept as a pre-split capability tree reference, not runtime.
- Repo A is canonical direction, but contains mixed old/new authority surfaces.
- SQLite/read-model coverage is useful and improving, but not complete.
- Cassandra is not standalone for invoice/contact/email workflows.
- Chief is not standalone as a clean module yet; it is both control plane and
  legacy runtime.
- Cassandra + Chief currently form an operator communications/orchestration
  stack.
- Guardian/HITL is a substrate module, but current authority is mixed.
- Memory authority is a shared substrate, not Cassandra-only.
- Finance/AP should be a finance + Cassandra intake + Guardian composite.
- Old HITL JSON/JSONL should be `authority_conflict_reconcile_first`, not
  simply blocked, until current runtime dependencies are reconciled.

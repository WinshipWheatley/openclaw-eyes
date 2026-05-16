# OpenClaw Remaining Work Stratifier v0

Generated: `2026-05-16`

Evidence basis:

- Repo status and recent commits through `20d4094 feat(authority): dual-write Chief approval requests to SQLite`.
- Repo A docs, read-models, and safe source surfaces under `/home/openclaw`.
- Repo B filename/topology inspection only under `/home/openclaw_external/openclaw-runtime`.
- No runtime services were started, no data was imported, no external sends were made, and no raw private/log/secret content was inspected.

## A. Executive Summary

OpenClaw is in consolidation, not expansion.

Repo A is the canonical governed direction. Repo B is the pre-split capability tree and remains useful as design evidence, but it is not current runtime authority. SQLite/read-models are the best current authority check, but they are not complete coverage yet. Generated read-models are visibility and proof surfaces, not truth by themselves.

The main spine now exists in pieces: classification/tagging, module registry, bundle planning, estate topology, governed intake, Work Board, Agent Work Packets, Operator Action, finance evidence packets, Cassandra/Chief memory cataloging, and Guardian/HITL authority reconciliation. The main unfinished work is authority wiring and proof, especially around Guardian/HITL decision receipts and legacy JSON compatibility.

Mission Control should become the operator work surface. It should help Winship orient, decide, approve, and inspect proof. It should not become a backend dashboard full of implementation noise. Backend details should collapse into status, blockers, evidence, and next-safe-move cards with drill-down when needed.

Current priority: reconcile approval authority and memory facts before turning agents loose. Cassandra/Chief cannot safely do invoice/contact/email work until HITL decision/receipt parity and structured memory import are proven.

## B. Current Spine Status

| layer | status | evidence | next safe move |
| --- | --- | --- | --- |
| Classification/tagging substrate | partially built | `corpus_atlas.py`, `markdown_knowledge_atlas.py`, `generated/read_models/markdown_evidence.json`, `docs/operations/OPENCLAW_CLASSIFICATION_TAGGING_PATTERN_V0.md`, `cassandra_chief_memory_authority.py` | Run metadata-only source/Markdown dry-run lanes before any broad ingest or reorg. |
| Module registry / bundle planner | built for planning, not runtime | `module_registry.py`, `bundle_blueprint_planner.py`, `generated/read_models/approved_module_registry.json`, `generated/read_models/bundle_blueprint_planner.json` | Surface module/bundle posture in Mission Control; keep `runtime_authority=false`. |
| Estate topology | built for visibility | `estate_read_model.py`, `generated/read_models/estate_topology.json`; flags show `runtime_authority=false`, `estate_registry_schema_created=false`, `repo_split_allowed=false` | Use it as read-only topology input for Mission Control and future bundle planning. |
| Governed intake spine | partially built | `governed_intake_spine.py`, `telegram_agent_intake.py`, `intent_router.py`, generated intake/read-model outputs | Prove live listener receive paths and keep all send/reply authority blocked. |
| Work Board / Agent Work Packets | built as metadata/projection spine | `work_board.py`, `agent_work_packet.py`, `generated/read_models/work_board.json`, `agent_work_packets.json` | Improve Mission Control presentation and link blockers to next lanes. |
| Operator Action / Guardian HITL | partially built, authority transition in progress | `operator_action.py`, `operator_action_inbox.py`, `guardian_hitl_*`, `chief_approval_brain.py`; request-side Chief dual-write now exists | Implement Guardian HITL Decision Receipt Shadow v0; do not switch callers yet. |
| Cassandra/Chief memory authority | schema/read-model support built, real import blocked | `cassandra_chief_memory_authority.py`, `generated/read_models/cassandra_chief_memory_dry_run.json`, structured import plan | Operator reviews import categories, but actual import waits for HITL receipt proof. |
| Repo A / Repo B reconciliation | partially mapped | `docs/operations/CROSS_REPO_SPLIT_HITL_AND_MODULE_BOUNDARY_RECONCILIATION_V0.md`; Repo B file tree shows old capability clusters | Reconcile cluster by cluster; port logic only through Repo A governed contracts. |
| Remote-builder bridge | blocked | HITL docs mark remote-builder unsafe; no full Guardian-approved bridge exists | Write Remote Builder Bridge Spec after HITL request/decision receipts are proven. |
| Mission Control app | partially built/read-only direction | Current system map says Mac app consumes generated read-model posture and grants no backend authority | Add read-only module/bundle/estate/HITL/memory readiness surfaces; avoid backend dashboard sprawl. |
| MD/source ingest | partially built | `corpus_atlas.py`, `markdown_knowledge_atlas.py`, `markdown_evidence.json`, `source_inventory.json`, context-selection surfaces | Run source classification dry-run and operator packet before any reorg or raw body expansion. |
| Hard-drive/cloud/file ingest | not ready | Corpus roots and Mac mirror atlas patterns exist; broad ingest remains blocked by no-go/private boundaries | Metadata-only boundary plan first; no broad crawl, no file moves, no raw content. |
| Finance/invoice workflows | partially built | `finance_invoice_evidence_packet.py`, `capital_hilton_invoice_packet.py`, finance read-models and Work Board cards | Complete Capital Hilton missing-facts packet after safe structured memory import and explicit finance facts. |
| Music/album/Niles workflows | planned/draft | `niles_album_matrix` appears as draft module; Repo B has album cluster files | Plan Niles Album Production Matrix v0; do not import album CSV/raw notes into Cassandra memory. |

## C. Critical Blockers

1. Guardian HITL decision receipts are not mirrored into SQLite yet. Request-side Chief dual-write exists, but decision/denial/expiry/callback receipt parity is not complete.
2. Old JSON approval state is still compatibility-authority. `approval_pending.json` and HITL JSON/JSONL paths are still referenced by current Repo A code.
3. Cassandra/Chief memory import is not safe yet. Structured source categories are planned, but real import must wait for approval authority proof and operator category approval.
4. Dirty `agent_presence` generated files are volatile residue. They should not be committed as current truth until regenerated/reworked.
5. Remote-builder bridge is not implemented and remains blocked. It must wait for exact packet binding, approval receipts, and no raw command/freeform shell authority.
6. Mission Control is not caught up to the new read-model estate. It should show module/bundle/estate/HITL/memory posture, not raw backend internals.
7. Repo A/Repo B split is not fully reconciled. Repo B is a pre-split capability map with useful logic, but not a runtime source of truth.
8. MD/source classification exists but system-wide ingest/reorg is not safe yet. No-go/private boundaries need metadata-only dry-run and operator review.
9. Broad hard-drive/cloud ingest is not ready. It needs explicit boundaries, dry-run, rollback, and no destructive moves.
10. Cassandra/Clara live usefulness is gated by receive proof, memory authority, finance facts, and send-path approval.

## D. Immediate Critical Path

Recommended sequence from now until Cassandra/Chief can safely do useful invoice/contact/email work:

| rank | lane | goal | blocked by | expected output |
| --- | --- | --- | --- | --- |
| 1 | Guardian HITL Decision Receipt Shadow v0 | Mirror Chief approval decisions/denials/expiry into SQLite as observational receipts after request-side dual-write. | none beyond current residue | `guardian_hitl_approval_receipts` decision rows/read-model; callers still unswitched. |
| 2 | Guardian HITL Dual-Write Receipt Proof v0 | Prove request + decision + timeout/mismatch receipt equivalence under synthetic tests. | lane 1 | Operator packet saying what old JSON still owns and what SQLite can prove. |
| 3 | Cassandra HITL Proposal Shadow v0 | Mirror `hitl_pending_store` proposals safely without raw payload storage or authority expansion. | lanes 1-2 | Sanitized Cassandra HITL request mirrors and no-send/no-runtime receipts. |
| 4 | HITL Transition Criteria Review v0 | Define exactly when callers can switch and old JSON can later retire. | request/decision/proposal mirrors | Readiness packet for a future caller-switch lane, probably still not immediate. |
| 5 | Cassandra/Chief Memory Import Approval Review | Operator approves which structured categories can import later. | HITL proof posture | Approved category list for contacts, companies, email posture, invoice facts, receivables. |
| 6 | Cassandra/Chief Structured Fact Import v0 | Import approved structured facts only; keep messy notes/logs evidence-source-only. | operator approval and HITL posture | SQLite rows with source refs, trust/evidence status, no-send/no-runtime flags. |
| 7 | Cassandra/Clara Fact Packet Generation v0 | Generate governed fact packets from SQLite for contact/invoice/email drafting. | structured facts | Reviewable packets; no external send. |
| 8 | Capital Hilton Invoice Packet Completion v0 | Complete missing facts and packet posture from approved evidence. | finance facts and operator answers | Updated finance/AP packet, Work Board cards, no-send draft context. |
| 9 | Send-Path Approval Packet Spec v0 | Define exact email/Telegram send packet approval contract. | HITL parity and draft packets | Send remains blocked until explicit approved packet. |
| 10 | Cassandra/Clara Approved Draft/Send Lane | Only after exact approved packet and receipt contract exist. | all prior gates | Bounded draft/send workflow, if operator approves. |

## E. Parallel Lanes

| lane | can run now / wait | why | risk | expected value |
| --- | --- | --- | --- | --- |
| Mission Control Module/Bundle/Estate Visibility v0 | can run now | Read-models exist and are safe to display. | UI may become backend-dashboard noise. | Gives Winship a clear orientation surface. |
| Mission Control HITL/Memory Posture v0 | can run now after lane 1 is at least specified | Uses generated read-models; no runtime changes. | Mislabeling observational records as authority. | Shows what is safe, mixed, blocked, and waiting. |
| Remote Builder Bridge Spec v0 | docs-only can run now; implementation waits | Needs HITL contract shape but not live wiring for a spec. | Premature bridge could imply execution authority. | Prepares exact packet/receipt model. |
| MD/Source Classification Dry-Run v0 | can run now | Classification substrate exists. | Broad scan could hit no-go/private roots if careless. | Operator sees what docs/sources can be classified safely. |
| Niles Album Production Matrix Plan v0 | can run now as planning | Album cluster is separated enough for domain planning. | Importing old CSV/session notes as truth. | Keeps music workflow from being swallowed by Cassandra/Chief. |
| Review vault / Obsidian export | wait or minimal-export | Useful only as downstream generated review material. | Creating another authority surface. | Operator-friendly decisions/doctrine packet if kept non-authoritative. |
| Generated-state cleanup | can run now | Known dirty generated `agent_presence` residue remains. | Regeneration could hide live receive uncertainty. | Cleaner repo and less status fog. |
| Agent presence volatile snapshot cleanup | can run now as inspect-first | Presence residue is known and isolated. | Committing stale online/offline claims. | Removes confusion around Cassandra online vs reply-ready. |

## F. Repo A / Repo B Reconciliation Backlog

Repo B is the pre-split capability tree. It should be reconciled by capability, not bulk-ported.

| historical cluster | current Repo A representation | likely Repo B source cluster/files | status | module or stack shape | belongs in | next safe lane |
| --- | --- | --- | --- | --- | --- | --- |
| Album Production | `niles_album_matrix` draft module only | `chief_album_*`, album scripts/log concepts | partial | `niles_album_matrix` stack | module registry, future SQLite/evidence catalog, Mission Control later | Niles Album Production Matrix Plan v0 |
| Fundo | module not yet governed | `chief_fundo_*` | missing/unknown | future module | module registry and project capsule later | Fundo Capability Reconciliation Audit v0 |
| Finance & Billing | finance invoice packets, Capital Hilton packet, finance read-models | `chief_invoice_brain.py`, `chief_billing_brain.py`, finance/billing files | partial | `finance_ap_invoice_stack` | SQLite finance evidence, Work Board, Mission Control | Capital Hilton Invoice Packet Completion v0 |
| Marketing | no governed module beyond draft concepts | `chief_marketing_brain.py`, content/brand files | missing/reference-only | marketing/content module later | module registry, evidence catalog | Marketing Capability Reconciliation Audit v0 |
| Communications | Telegram intake, Cassandra/Chief/Guardian listeners, governed intake | `chief_listener.py`, `cassandra_listener.py`, `chief_guardian_*`, `chief_sms/email/phone` | partial/mixed | `operator_comms_stack` | governed intake, HITL, memory authority | Cassandra Live Receive Proof / Comms Stack Map |
| System Health | agent presence and recovery clearance docs/scripts | `chief_watcher_brain.py`, workers, service templates | partial | system health substrate | read-models, Work Board, Mission Control | Agent Presence Cleanup and Recovery Readiness v0 |
| Research Intelligence | Hermes/advisory seed concepts | `chief_reflection_brain.py`, `chief_integration_brain.py`, `chief_analytics_brain.py` | partial/reference-only | advisory module | Work Board/read-models, not authority | Hermes Next Lane Stratifier v0 |
| Analytics | evidence/read-model status exists, analytics legacy not reconciled | `chief_analytics_brain.py` | partial | advisory/read-model module | generated read-models, Mission Control | Analytics Read-Model Reconciliation v0 |
| Business Consulting | project capsule, bundle planner, report bridge | consulting/planning concepts in Repo B | governed foundation | planning module/stack | module registry, project capsule, report bridge | Mission Control Bundle Visibility v0 |
| Infrastructure | runtime activation gates, agent presence, local services docs | workers/watchers/service templates | partial/blocked | infrastructure substrate | read-models and explicit approval packets | Runtime Readiness Map v0 |
| Website | no governed website module yet | `chief_website_*` | missing/reference-only | website module later | module registry, Work Board | Website Capability Reconciliation Audit v0 |
| Trinity Audit | no current governed module except advisory docs | `chief_trinity_brain.py` | reference-only | advisory module | evidence/read-model docs | Trinity Audit Advisory Packet v0 |
| Data & Memory | memory authority substrate, corpus atlas, estate topology | `chief_memory_worker.py`, session/state files | partial | substrate | SQLite/evidence catalog/read-models | Memory Source Catalog Generalization v0 |

## G. Module/Stack Boundary Backlog

| boundary | shape | dependencies | separate repo later | extraction risk | current next move |
| --- | --- | --- | --- | --- | --- |
| `operator_comms_stack` | composite stack | Telegram intake, Cassandra, Chief, Guardian, memory authority | no for now | high | Map receive/reply/send boundaries after HITL receipts. |
| `chief_control_plane` | deterministic control-plane plus legacy runtime residue | intent router, Work Board, HITL, memory | later | high | Keep deterministic parts in Repo A; reconcile legacy router actions. |
| `cassandra_clara_fact_intake` | narrow module inside comms stack | governed intake, memory authority, finance packets | later | medium | Keep receive/fact intake, not standalone invoice/send authority. |
| `guardian_hitl_gate` | substrate module | Operator Action, Chief compatibility, HITL stores | later | high | Finish decision receipt shadow and proof. |
| `memory_authority_substrate` | substrate | corpus/source classification, SQLite, read-models | later | medium | Import only approved structured facts after HITL proof. |
| `finance_ap_invoice_stack` | composite stack | finance packets, Cassandra fact intake, Guardian, memory | later | high | Complete Capital Hilton packet after fact import/approval. |
| `remote_builder_bridge` | future bridge stack | Operator Action, Guardian, job packets, receipts | later | critical | Spec only until approval contract is fully proven. |
| `deterministic_evidence_core` | substrate | corpus atlas, markdown atlas, evidence/read-models | yes/later | medium | Run MD/source classification dry-run. |
| `niles_album_matrix` | domain module/stack | album metadata, Work Board, HITL for sends | later | high | Plan Niles matrix without raw session import. |
| `mission_control_work_surface` | app surface | generated read-models, Operator Action posture, Work Board | no, app can live separately but backend authority stays Repo A | medium | Add read-only posture screens before actions. |
| `source_classification_ingest` | ingest substrate | corpus, markdown atlas, no-go policy | later | high | Metadata-only dry-run and operator review. |
| `file_estate_ingest` | ingest substrate | corpus roots, Mac mirror atlas, source inventory | later | critical | Boundary spec only; no broad crawl. |

## H. MD/System-Wide Source Ingest Roadmap

Existing substrate:

- `corpus_atlas.py` records metadata/location, source role, sensitivity, retrieval/ingestion eligibility, canonicality, freshness, owner scope, client/instance fields, and no-go posture.
- `markdown_knowledge_atlas.py` classifies Markdown documents by document role, freshness, reorg status, sensitivity status, retrieval policy, world binding, and module topic.
- `generated/read_models/markdown_evidence.json` contains bounded approved excerpts and explicitly shows `full_raw_body_stored=false` and `raw_private_scan_allowed=false`.
- `source_inventory.json` exists as metadata-only allowlisted source context.
- `context_selection.py` can select bounded evidence packets without truth promotion.

Remaining work before system-wide Markdown/source classification:

1. Define safe roots and excluded roots first.
2. Run a metadata-only dry-run before any body read or reorg suggestion.
3. Produce an operator review packet with buckets: keep, archive later, evidence-source-only, no-go, unknown review.
4. Keep raw private/legal/tax/finance/bank/spreadsheet/Telegram/log bodies out of scope.
5. Treat generated read-models as evidence, not truth.
6. Never auto-reorganize, move, delete, rename, or rewrite Markdown without explicit operator approval.

## I. Hard-Drive/Cloud/File Ingest Roadmap

High-level prerequisites before broad ingest:

- explicit source inventory boundaries and no-go roots;
- metadata-only first pass;
- classification/tagging using the existing vocabulary;
- operator review packet before any import or file movement;
- OS-respecting folder plan;
- rollback plan;
- dry-run output with exact candidate counts;
- Mission Control visibility for candidates and risks;
- no destructive moves without explicit approval;
- no raw private/client/finance/bank/spreadsheet/log body reads by default;
- no cloud sync, upload, repo creation, or deployment side effects.

The current system has enough ingredients for a spec, not enough authority for broad ingest.

## J. Mission Control App Roadmap

Mission Control should eventually show:

- Work Board cards and next safe moves.
- Module/bundle/estate posture.
- HITL authority posture: current, mixed, compatibility-only, blocked, and receipt proof.
- Cassandra/Chief readiness and memory import posture.
- Finance/AP packet status, missing facts, and approval gates.
- Niles/album matrix posture once planned.
- Remote-builder requests only after packet/approval proof exists.
- Source/Markdown/file ingest candidates as review buckets, not raw content.

Mission Control should hide or collapse:

- raw backend tables unless needed for proof drill-down;
- raw private/client/bank/spreadsheet/Telegram/log contents;
- implementation details that do not change operator decisions;
- any UI that implies visibility equals approval or approval equals execution.

Next app lanes:

1. Mission Control Module/Bundle/Estate Visibility v0.
2. Mission Control HITL Authority Posture v0.
3. Mission Control Cassandra/Chief Memory Review v0.
4. Mission Control Finance/AP Packet Surface v0.
5. Mission Control Niles/Album Surface v0.
6. Mission Control Remote-Builder Request Surface v0, later.

## K. Human Review Surface / Obsidian Decision

A lightweight Obsidian/review vault may help only as downstream generated review material.

Recommended posture: `minimal-export/defer`.

Use it for:

- modules/stacks atlas;
- decisions;
- doctrine summaries;
- classification pattern summaries;
- operator review packets.

Do not use it for:

- live state;
- approval authority;
- backend truth;
- raw private/client data;
- replacement for Mission Control.

If a review vault is used, generate concise Markdown from read-models and keep Repo A SQLite/read-models canonical.

## L. Cleanup Backlog

| residue | classification | recommendation | risk | next lane |
| --- | --- | --- | --- | --- |
| `generated/read_models/agent_presence.json` | dirty generated volatile snapshot | regenerate/rework before commit | Committing may preserve stale Cassandra online/receive claims. | Agent Presence Volatile Snapshot Cleanup v0 |
| `generated/read_models/agent_presence_OPERATOR.md` | dirty generated volatile snapshot | regenerate/rework before commit | Operator-facing text could imply live readiness that is not proven. | Agent Presence Volatile Snapshot Cleanup v0 |
| `polish_loop/tasks/chief-cassandra-failure-20260513T234214.md` | local residue candidate | delete only in explicit cleanup lane | Deleting now could lose breadcrumb evidence; committing would preserve obsolete task noise. | Cassandra Failure Task Residue Cleanup v0 |
| `polish_loop/tasks/chief-cassandra-failure-20260513T235844.md` | local residue candidate | delete only in explicit cleanup lane | Same as above. | Cassandra Failure Task Residue Cleanup v0 |
| central generated checks | possibly stale from older `helm_state`, `evidence_freshness`, or `GENERATED_CURRENT_STATE` | defer unless touched by lane | Broad regeneration can create unrelated churn. | Generated Read-Model Freshness Cleanup v0 |

## M. Decision List For Operator

1. Approve the HITL transition strategy: request mirror -> decision receipt shadow -> proposal mirror -> proof -> later switch.
2. Approve or revise Cassandra/Chief memory import categories before real import.
3. Decide whether old HITL JSON should remain compatibility-authority until a full caller-switch proof exists. Current recommendation: yes.
4. Decide album progress handling: separate Niles matrix, not Cassandra memory.
5. Decide generated `agent_presence` cleanup: regenerate/rework versus delete residue.
6. Decide remote-builder risk level: spec now or wait until HITL proof.
7. Decide next Mission Control lane: module/bundle/estate visibility versus HITL posture.
8. Decide whether Obsidian/review vault export is useful as generated review material only.
9. Decide whether Capital Hilton missing facts are ready to provide as operator-confirmed facts.
10. Decide when Cassandra live receive proof should be revisited relative to HITL/memory work.

## N. Recommended Next 10 Lanes

| rank | lane name | goal | why now | blocked by | expected output | risk | inspect-first/no-edit | can implement immediately | operator approval needed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Guardian HITL Decision Receipt Shadow v0 | Mirror Chief approval decisions/denials/expiry into SQLite receipts. | Request dual-write is done; decisions are the next proof gap. | none | Decision receipt read-model; no caller switch. | medium-high | yes | yes, bounded | no for implementation if prompt is exact |
| 2 | Guardian HITL Dual-Write Proof Review v0 | Prove request/decision/expiry/mismatch parity. | Needed before any authority transition. | lane 1 | operator proof packet and transition criteria | medium | yes | yes | maybe for transition interpretation |
| 3 | Cassandra HITL Proposal Shadow v0 | Mirror Cassandra HITL proposals safely. | Needed before memory/import/send-adjacent work. | lanes 1-2 | sanitized proposal mirrors and receipts | high | yes | only after spec/inspection | no runtime switch |
| 4 | Agent Presence Volatile Snapshot Cleanup v0 | Resolve dirty presence read-model residue. | Current dirty files keep causing fog. | none | regenerate/rework/delete recommendation and clean status | low-medium | yes | yes, if bounded | maybe if deleting residue |
| 5 | Mission Control Module/Bundle/Estate Visibility v0 | Show safe module/bundle/estate posture. | Read-models exist and are low-risk. | none | app/read-model display plan or implementation | medium | yes | maybe after app inspection | yes if UI scope changes |
| 6 | Cassandra/Chief Memory Import Approval Review v0 | Operator approves import categories. | Memory plan exists but import is blocked. | HITL proof for action-adjacent categories | approval packet for structured import | medium | yes | docs/read-model only | yes |
| 7 | Cassandra/Chief Structured Fact Import v0 | Import approved structured facts only. | Unlocks useful Cassandra/Clara drafting. | lane 6 and HITL posture | SQLite facts with source/trust/no-send flags | high | yes | not until approval | yes |
| 8 | Capital Hilton Invoice Packet Completion v0 | Fill missing facts and update finance/AP packet. | High practical value once facts are confirmed. | operator facts, maybe memory import | updated packet and Work Board cards | medium | yes | after facts approved | yes for financial facts |
| 9 | MD/Source Classification Dry-Run v0 | Classify sources metadata-only across safe roots. | Ingest/reorg needs a map first. | safe root boundaries | operator review packet | medium-high | yes | yes if root list is bounded | yes for broad roots |
| 10 | Remote Builder Bridge Spec v0 | Define job packet/approval/receipt contract. | Useful but unsafe to implement yet. | HITL proof for implementation | docs/ready packet only | high | yes | spec only | yes before implementation |

## O. One-Page Operator Summary

OpenClaw now has the pieces of a governed operating system, but the pieces are still being tied together.

The good news: Repo A has real structure now. There is a module registry, bundle planner, estate topology, governed Telegram intake, Work Board, Agent Work Packets, Operator Action, finance packet machinery, Cassandra/Chief memory cataloging, and a Guardian/HITL SQLite contract. Chief approval requests now dual-write into SQLite as observational records without changing runtime authority.

The important caution: useful agents are still gated. Old approval JSON is still active compatibility authority. SQLite can see more, but it does not yet own the full approval lifecycle. Cassandra/Chief memory is cataloged but not imported as truth. Repo B is useful as the old capability tree, but it must not run or be bulk-ported.

Do not do these yet: enable broad sends, run Repo B, import messy memory as truth, switch approval callers, delete old HITL state, build a remote builder, or start broad file/cloud ingest.

Next best move: finish the Guardian HITL decision receipt shadow. That closes the biggest proof gap after request-side dual-write. After that, OpenClaw can prove approvals end-to-end, then safely approach Cassandra/Chief memory import and invoice/contact/email workflows.

What becomes possible after that: Cassandra can work from governed facts instead of old notes, finance packets can become more complete, Mission Control can show true readiness instead of backend fog, and future agents can receive bounded work packets without bypassing gates.

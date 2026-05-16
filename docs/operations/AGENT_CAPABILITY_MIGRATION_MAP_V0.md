# Agent Capability Migration Map v0

## Executive Summary

OpenClaw Core is the canonical authority. Repo B (`/home/openclaw_external/openclaw-runtime`) is read-only legacy evidence and must not be executed, imported as a runtime, or treated as a source of truth.

The six audit streams converge on one shared governed spine:

`intake -> intent/action record -> Work Board / Agent Work Packet -> Guardian approval when needed -> receipt/read-model -> Mission Control`

The immediate product direction is to migrate capability into one substrate instead of letting Chief, Cassandra, Guardian, Niles, Hermes, and Planner/Builder grow separate bridges. Legacy code can supply concepts, heuristics, and domain vocabulary. It must not bring over direct sends, daemon loops, raw shell/eval, CSV/log authority, volatile approval state, or private/client data paths.

## Combined Migration Map

| agent_or_system | repo_b_surface | inferred_capability | value | risk | recommended_fate | new_repo_a_home | migration_type | operator_decision_needed | stage_2_relevance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Chief | `chief_listener.py` | Telegram intake and operator front door | Shows conversational intake shape | Token/env-backed live listener and direct replies | Replace with governed intake contracts | `telegram_agent_intake.py`, `operator_intent_core.py`, `intent_router.py` | superseded | no | Use concept only; no live changes |
| Chief | `chief_router.py` | Routing, deferred/task capture, approval interruption | Useful deterministic phrases and next-safe-move posture | LLM fallback, route CSV, broad coupled router | Port deterministic logic only where missing | `intent_router.py`, `operator_intent_core.py` | port_logic_only | no | Add shared intake bridge, not router clone |
| Chief | `chief_worker.py`, `chief_watcher_brain.py`, `chief_memory_worker.py`, `chief_state_worker.py` | Background queue and state loops | Shows older daemon topology | Infinite loops, ad hoc logs/state, daemon resurrection | Block runtime behavior | `work_board.py`, read-model exporters | block_no_go | no | Explicit no-go in tests/docs |
| Chief | `chief_sender.py` | Telegram outbound send | None for Stage 2 | Direct external send, env token read | Block | none | block_no_go | no | Must remain blocked |
| Cassandra / Clara Reid | `cassandra_listener.py` | Telegram receive/reply listener | Useful receive classification and operator-facing posture | Direct replies, voice send, env token read, ad hoc route CSV | Wrap as dumb intake only | `telegram_agent_intake.py`, `intent_router.py` | wrap_as_dumb_intake | no | Synthetic-only intake bridge can reuse concept |
| Cassandra / Clara Reid | `cassandra_brain.py` | Assistant response, finance/AP drafts, follow-ups | Domain vocabulary and fact intake patterns | LLM/model calls, file writes, email/calendar sends, ad hoc JSON/CSV | Port logic only after policy review | `operator_intent_core.py`, finance packet modules, future draft packet | port_logic_only | yes | Only conservative classifier terms in Stage 2 |
| Cassandra / Clara Reid | `cassandra_outreach.py` | Outreach/follow-up analysis | Useful question-bundle and draft concepts | Telegram notify/send path, outreach state | Reference for future draft-only module | future draft packet / Guardian-gated action path | operator_review_required | yes | Not Stage 2 implementation |
| Cassandra / Clara Reid | `cassandra_capability.py` | Capability declaration | Helpful capability inventory vocabulary | Claims connected sends/voice/email as live capability | Convert to non-authorizing registry metadata | `module_registry.py` | port_logic_only | no | Seed `cassandra_clara_fact_intake` draft module |
| Cassandra / Clara Reid | `cassandra_watcher.py`, `cassandra_briefing_scheduler.py` | Watcher and scheduled briefings | Briefing cadence ideas | Subprocess, infinite loop, send_message | Block daemon; port briefing logic later | Work Board, future scheduler policy | block_no_go | yes | No daemon/watchdog in Stage 2 |
| Cassandra / Clara Reid | `cassandra_briefing_brain.py` | Briefing context and protected-window checks | Useful briefing readiness logic | Reads old JSON state and LLM calls | Reference only | future briefing packet module | reference_only | yes | Not Stage 2 |
| Cassandra / Clara Reid | `cassandra_whisper_relay.py` | Audio transcription relay | Confidence-gated intake idea | Whisper/model dependency, audio/private input path, logs | Defer | future approved input adapter module | defer | yes | Not Stage 2 |
| Guardian | `chief_guardian_listener.py` | Approval response listener | Useful second-factor interaction concept | Telegram approval dicts and direct bot edits/sends | Port policy ideas only | `operator_action.py`, `operator_action_inbox.py`, future Guardian gate | port_logic_only | yes | Registry seed only |
| Guardian | `chief_guardian_sender.py`, `chief_approval_brain.py` | Approval request delivery and pending state | Useful tiers, hashes, allowlist language | Env tokens, direct sends, subprocess, volatile pending JSON, execution coupling | Supersede with receipt-backed gate | `operator_action.py`, `hitl_pending_store.py`, `hitl_action_service.py` | superseded | yes | Do not wire execution |
| Niles / Niles Mercer | `chief_album_io.py`, `chief_album_mixer.py`, `chief_album_batch.py` | Album matrix, mix readiness, batch packet logic | High-value music/art production vocabulary | CSV authority, file overwrites, LLM calls | Port logic only to governed matrix later | future `niles_album_matrix` module | port_logic_only | yes | Seed draft module only |
| Niles / Niles Mercer | `chief_album_brain.py` | Album workflow brain and queue handling | Useful session/matrix workflow concepts | Subprocess, queue loops, URL/model calls, CSV writes | Reference only until module lane | future Music-Art packet surface | reference_only | yes | Not Stage 2 |
| Niles / Niles Mercer | `chief_musiclaw_brain.py` | Music-law advisory answers | Shows needed safety posture | Legal/CPA truth claims, LLM use, JSON writes | Block claims; keep advisory risk note | future Niles docs/tests | operator_review_required | yes | Add no-go note only |
| Hermes | `chief_reflection_brain.py`, `chief_integration_brain.py`, `chief_analytics_brain.py` | Reflection, readiness metrics, integration proposal sorting | Useful advisory shape | LLM calls, JSON source-of-truth claims, canonical-sounding outputs | Port as advisory-only non-authority | future Hermes stratifier / `work_board.py` | port_logic_only | yes | Seed advisory module only |
| Planner/Builder | `builder_watcher.sh`, `loop_supervisor.sh`, `loop_control.sh` | Runner registry, task tiering, watchdogs | Useful proof/tiering concepts | Claude/Codex/Gemini runner launch, kill paths, watchdog loops, status JSON authority | Block runtime; port concepts to Work Board | `work_board.py`, `agent_work_packet.py` | block_no_go | yes | No runner/watchdog implementation |
| Planner/Builder | `polish_loop/orchestrator.py` | PC/Mac loop orchestration and task promotion | Useful receipt/closeout concepts | Subprocess, arbitrary runner launch, mutable status, task spawning | Supersede with governed Work Board | `work_board.py`, `agent_work_packet.py`, receipt spine | superseded | yes | No loop activation |
| Shared legacy | `capability_registry.py` | Capability names and routing vocabulary | Useful seed vocabulary | Legacy registry is not authority | Convert to approved module metadata | `module_registry.py` | port_logic_only | no | Seed conservative module records |
| Shared Core | Repo A existing spine | Deterministic intake, route, Work Board, packets, actions, report bridge | Already canonical | Needs module/bundle vocabulary alignment | Extend, do not rebuild | `operator_intent_core.py`, `intent_router.py`, `work_board.py`, `agent_work_packet.py`, `module_registry.py`, `project_capsule.py`, `report_bridge.py` | already_covered | no | Direct Stage 2 target |

Controlled migration types used here: `already_covered`, `port_logic_only`, `wrap_as_dumb_intake`, `superseded`, `block_no_go`, `defer`, `operator_review_required`.

## Explicit No-Go List

- no Repo B execution
- no daemon/watchdog resurrection
- no raw shell/eval
- no direct Telegram send
- no SMTP send
- no raw client/private data export
- no ad hoc CSV/log state as authority
- no unapproved web/API/model execution
- no generated client repo creation in Stage 2

## Shared Spine

The shared migration spine is:

1. Intake captures an operator, local, or sanitized report signal.
2. A deterministic intent/action record stores a hash, bounded preview, source metadata, and authority flags.
3. Work Board and Agent Work Packet project the record into an operator-visible plan.
4. Guardian approval is required when an action would mutate, send, execute, deploy, or cross a sensitivity boundary.
5. Receipts and read-models show what happened or what remains blocked.
6. Mission Control reads the sanitized read-model posture, not raw private/client content.

## Modular Bundle Doctrine

Approved modules must be reusable, versioned, capability-scoped, authority-scoped, sensitivity-scoped, test-backed, and client-safe by default. A module selection is planning metadata unless a later explicit lane grants runtime authority.

OpenClaw Core is canonical. Client/project bundles are generated deployments or manifests, not new authority over Core. A Report Bridge returns sanitized status, proof, version, and health information only. It must not return private client contents unless the operator explicitly approves a specific data transfer.

Default authority remains `runtime_authority=false` for all mapped records and future module selections unless a later explicit approval lane changes that posture.

## Stage 2 Recommendation

Stage 2 is safe if it remains local, deterministic, non-executing, and bounded to:

- Approved Module Registry v0 alignment.
- Bundle Blueprint Planner v0 as local manifest planning only.
- Unified Governed Intake Spine v0 over existing deterministic routing.
- Work Board or Agent Work Packet projection only where existing APIs support it.
- Dedicated read-model/status visibility using existing generated read-model patterns.

Stage 2 must not become agent rebuild, live listener work, Repo B porting, external sends, runtime activation, client repo generation, deployment, or broad Mission Control mutation.

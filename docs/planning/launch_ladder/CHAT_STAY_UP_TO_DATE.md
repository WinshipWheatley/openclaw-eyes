# Chat Stay Up To Date

Status: repo-side delta bridge/template for Operator Harness ChatGPT Project sessions. This file is not a source-set folder, not a launch step, and not authority.

## Purpose

`CHAT_STAY_UP_TO_DATE.md` is the small delta layer that can be uploaded alongside one 24-file ChatGPT Project source-set folder when the repo has moved but a full source-set refresh would be wasteful.

The baseline remains the numbered source-set folder. This bridge is adjacent to the folders, not inside them, and is not counted in the 24 files.

The real bridge is this repo-side template plus the Mac readiness-root copy at `~/OpenClaw_Watch/operator_harness_readiness/CHAT_STAY_UP_TO_DATE.md`. The old Mac prototype file at `/Users/hwinshipwheatley/OpenClaw_Watch/.claude/Chat_Stay Up To Date.md` is prototype/example only and is not canonical. After the real Operator Harness bridge is verified at the readiness root, retire the `.claude` prototype by an explicit Mac cleanup step that deletes it or clearly archives it. Do not delete that prototype from this docs/test slice.

## Current Source-Set Baseline

| Field | Current value |
| --- | --- |
| Current source-set folder | `02_MAC_IOS_APP_BUILD` |
| Source-set ladder position | `02_MAC_IOS_APP_BUILD` of the current `01 -> 02 -> 03` ladder. |
| Source commit from latest audited `MANIFEST.md` | `df52ff4687d7dd8a32990658d557cb2b4d1371d9` |
| Latest repo changes since upload | Repo HEAD checked at slice start: `2c859ed docs(app): add mission control fixture contract`. This current docs/test-only slice creates a SQLite-backed Compiled Knowledge / RAG substrate planning package under `docs/planning/launch_ladder/knowledge_substrate/`. |
| Current chat focus | Mac Desktop App Planning - Compiled Knowledge Substrate planning contract inside `02_MAC_IOS_APP_BUILD`. |
| Next likely source-set folder | `03_BACKEND_AND_DATA_MODEL`, after app-facing fixture states, read-only display boundaries, knowledge-substrate concepts, and validation expectations are stable enough to formalize data/schema contracts. |
| Full 24-file refresh needed? | No, if the only change is a small docs/test clarification that does not alter included file count, withheld surfaces, or source-set purpose. |
| Bridge-only upload enough? | Yes, for small current-context updates that explain what changed since the latest `MANIFEST.md`. |

## Small Updates The Chat Should Know

- Launch Ladder is the operator-facing work progression toward a North Star.
- Source-Set Ladder is the slower ChatGPT Project context progression: `01_CURRENT_PRODUCT_SPEC -> 02_MAC_IOS_APP_BUILD -> 03_BACKEND_AND_DATA_MODEL -> future 04/05/etc.`.
- Source-set folders are not Launch Ladder steps. They are staged context packets that squeeze a specific type of planning or build value before the chat moves to the next source set.
- `CHAT_STAY_UP_TO_DATE.md` is adjacent to `CHATGPT_PROJECT_INGEST_OPERATOR_HARNESS/` and should not be copied into any numbered source-set folder.
- Each numbered folder remains exactly 23 content files plus `MANIFEST.md`, 24 upload files total.
- The Mac-audited Operator Harness baseline uses per-source-set `MANIFEST.md` files. The audit-build and law-program flows are legacy-but-usable prior art and should be upgraded later, not in this bridge slice.
- Workspace Launch Profiles are navigation helpers only: opening VS Code/workspace/files does not authorize tests, sync, commits, service commands, provider/model calls, or runtime work.
- Profile-to-packet handoff is explicit: a profile opens context only; a Launch Packet authorizes a bounded next action only after evidence/freshness, operator-readable scope, validation, authority, and stop conditions are present.
- Launch Packet exists does not equal approved. Approval Receipt records explicit operator authorization for one Launch Packet/action/scope, including evidence/freshness at approval time, expiry, replay, consumed, result, and revocation state.
- UI State Claim rules must keep profile available, packet available, approved, executed, succeeded, current/fresh, synced/tested/healthy/running, configured, observed, requested, and stale copy tied to explicit evidence.
- Product Taste / Operator Experience Eval Spine is part of the product contract before app planning. Taste means operator trust, calm control, clear authority hierarchy, legible evidence, sparse high-confidence actions, and zero fake intelligence.
- App planning must preserve anti-slop checks: no vague agent status, no fake intelligence language, no hidden authority/execution, no generic admin-panel energy, no chatbot slop, and no evidence-backed status copy buried too deeply to trust.
- Active source-set baseline is now `02_MAC_IOS_APP_BUILD` for app planning. The current slice adds the read-only Mac desktop Mission Control fixture contract and nine JSON fixtures under `docs/planning/launch_ladder/fixtures/mission_control/`.
- Mission Control fixture states must preserve the exact meanings of `profile_available`, `packet_available`, `launch_ready`, `approved`, `executed`, `succeeded`, `stale`, `blocked`, and `unknown`.
- The future app may display fixture records, but it must not execute from them.
- The knowledge-substrate planning package lives at `docs/planning/launch_ladder/knowledge_substrate/`. It is docs/test-only and prepares future SQLite-backed local memory thinking without creating a database, ingestion scripts, real file scanning, provider/model calls, app implementation, or backend/runtime implementation.
- Knowledge-substrate doctrine: this is not vanilla RAG and not classic flat chunk-vector RAG. SQLite stores the memory; markdown speaks it; HTML preserves shape; FTS finds it; compiled notes make it useful.
- Raw files are evidence, extracted text is parsed evidence, compiled notes are interpretation, claims are confidence-bounded, and operator promotions determine what is accepted, rejected, marked historical, marked sensitive, or excluded.
- Unknown means unknown; do not soften it into confidence. Sensitive and unknown content remains local-only/restricted by default.
- The Mac mirror for this planning package should be adjacent to Operator Harness readiness at `~/OpenClaw_Watch/operator_harness_knowledge_substrate/`, not inside `~/OpenClaw_Watch/operator_harness_readiness/` and not inside any numbered 24-file source-set folder.
- A Workspace Launch Profile that contains executable commands is malformed. Executable commands belong only in a Launch Packet or higher Launch Ladder action.
- This slice stays in `02_MAC_IOS_APP_BUILD`, does not move to `03_BACKEND_AND_DATA_MODEL`, does not create source-set folder `04`, does not create generated source-set scripts, and does not edit generated source-set folders.
- `Mac/iOS` is Apple-platform planning shorthand: Mac desktop app first, iOS companion later.
- Do not refresh the Mac mirror after every small docs/test slice; batch mirror refreshes at meaningful checkpoints unless source-set membership, withheld surfaces, manifest basis, or operator upload needs change.

## Source-Set Ladder Movement Criteria

Move from `01_CURRENT_PRODUCT_SPEC` to `02_MAC_IOS_APP_BUILD` when:

- the chat has extracted stable product requirements, authority boundaries, evidence/freshness expectations, and route-compression semantics;
- unresolved questions are app-facing rather than product/spec-facing;
- the next useful work needs UI states, read-only app fixtures, platform constraints, or native-client routing;
- the `01_CURRENT_PRODUCT_SPEC` folder is producing repeated summaries rather than new decisions.

Move from `02_MAC_IOS_APP_BUILD` to `03_BACKEND_AND_DATA_MODEL` when:

- app-facing workflow, view states, and read-only behavior are sufficiently clear;
- the next useful work needs record shapes, schemas, fixtures, validation rules, or ingest/generator contracts;
- UI discussion is blocked on data-model decisions rather than design choices.

By `03_BACKEND_AND_DATA_MODEL`, the chat should propose what folder `04` should contain. Candidate `04` folders should be justified by evidence from the first three stages, not created automatically.

## Stale And Drift Warnings

- If any included source file changed materially after the latest `MANIFEST.md`, prefer a full 24-file refresh.
- If repo `HEAD` has advanced beyond the source commit named in the latest `MANIFEST.md`, list the delta commits here before upload.
- If withheld surfaces, authority rules, security posture, source-set purpose, or folder membership changed, use a full 24-file refresh.
- If only a narrow docs/test alignment changed, a bridge-only upload is enough.
- If the chat cannot tell whether it is using baseline files or this bridge, stop and ask the operator to restate the active source-set folder and manifest commit.
- If `CHAT_STAY_UP_TO_DATE.md` appears inside a numbered source-set folder, treat that folder as malformed.

## Do Not Do Yet

- Do not treat the bridge as canonical authority.
- Do not use the bridge to authorize runtime mutation, service control, provider/model calls, private-data inspection, Gmail/Telegram behavior, Hermes runtime expansion, secrets handling, vault access, logs, LegalPrivate, or installed-unit checks.
- Do not create source-set folder `04` from this file.
- Do not replace a stale or malformed 24-file baseline with bridge text.

## Refresh Rule

Use bridge-only upload when the baseline folder remains structurally valid and the delta can be explained in this one file. Use full 24-file refresh when the baseline source set, folder purpose, file membership, manifest authority, withheld surfaces, or source commit basis must change.

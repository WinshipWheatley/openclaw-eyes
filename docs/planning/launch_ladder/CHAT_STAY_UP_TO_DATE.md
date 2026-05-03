# Chat Stay Up To Date

Status: repo-side delta bridge/template for Operator Harness ChatGPT Project sessions. This file is not a source-set folder, not a launch step, and not authority.

## Purpose

`CHAT_STAY_UP_TO_DATE.md` is the small delta layer that can be uploaded alongside one 24-file ChatGPT Project source-set folder when the repo has moved but a full source-set refresh would be wasteful.

The baseline remains the numbered source-set folder. This bridge is adjacent to the folders, not inside them, and is not counted in the 24 files.

The real bridge is this repo-side template plus the Mac readiness-root copy at `~/OpenClaw_Watch/operator_harness_readiness/CHAT_STAY_UP_TO_DATE.md`. The old Mac prototype file at `/Users/hwinshipwheatley/OpenClaw_Watch/.claude/Chat_Stay Up To Date.md` is prototype/example only and is not canonical. After the real Operator Harness bridge is verified at the readiness root, retire the `.claude` prototype by an explicit Mac cleanup step that deletes it or clearly archives it. Do not delete that prototype from this docs/test slice.

## Current Source-Set Baseline

| Field | Current value |
| --- | --- |
| Current source-set folder | `04_BACKEND_DATA_CONTRACT_READINESS` |
| Source-set ladder position | `04_BACKEND_DATA_CONTRACT_READINESS` of the current `01 -> 02 -> 03 -> 04` ladder. |
| Source commit from latest audited `MANIFEST.md` | The generated `04_BACKEND_DATA_CONTRACT_READINESS/MANIFEST.md` is upload authority after refresh. Do not hardcode a fast-changing generation commit in this bridge. |
| Latest repo changes since upload | Repo HEAD checked at source-set generation start: `a07e98f`. Repo clean, main ahead of origin/main by 7. Proof passed: py_compile, launch_ladder_contract_check.py with known freshness warning, pytest 17 passed, git diff --check, sync apply, ingest apply. 04 file count: 24 files, 23 content files plus MANIFEST.md. 04 includes 17_BACKEND_DATA_CONTRACT_READINESS_PLAN.md. |
| Current chat focus | Audit 04 before using it as the next ChatGPT Project baseline. |
| Next likely source-set folder | Next likely lane after audit: backend/data-contract shape planning, not backend implementation, schema, SQL DDL, SQLite DB creation, ingestion, fixtures, app implementation, app naming, runtime/service/approval mutation, private-data inspection, provider/model calls, or audio/haptic/notification implementation. |
| Full 24-file refresh needed? | Yes for the move from `03_MAC_APP_KNOWLEDGE_SUBSTRATE` to `04_BACKEND_DATA_CONTRACT_READINESS`; the generated 04 folder should be the baseline. |
| Bridge-only upload enough? | No for the 04 transition itself. Bridge-only upload remains enough for small later context deltas that do not change folder purpose, membership, withheld surfaces, or manifest authority. |

## Small Updates The Chat Should Know

### PC Storage Relief Launch Packet

- `20_PC_STORAGE_RELIEF_LAUNCH_PACKET_PLAN.md` now defines a docs/test-only, operator-approved PC storage relief packet for the `C:` crisis, low-risk cache cleanup planning, WSL relocation planning, `.wslconfig` memory policy planning, 2TB bridge-drive triage, and later sensitive-data relocation boundaries.
- The packet does not authorize cleanup, file deletion/movement, WSL export/import/unregister, drive reformatting, `.wslconfig` edits, private-content inspection, provider/model calls, OpenClaw runtime mutation, or source-set `05` generation. Proposed commands in it are inert future examples only and require explicit operator approval before execution.

### Future Lane: Receivables & Obligations Control

- Future Operator Harness module: weekly upcoming auto-pulls and expected receivables. This is not the current lane; current priority remains PC storage relief execution planning / storage-source registry stabilization.
- Receivables should have confidence scoring based on evidence: work completed, invoice created, invoice sent, delivery evidence, payment terms, expected date, and blockers.
- The operator action should be `Raise confidence`, not a hardcoded `Make invoice` button. Later, `Raise confidence` should prepare a bounded Launch Packet: identify blocker, gather evidence, draft invoice if needed, store invoice, prepare/send email only after operator approval, file/categorize sent email, and update receivable confidence.
- Gmail vs Apple Mail must be audited later as a Mail Dispatch Surface decision; do not hardcode either provider yet.
- Strong boundaries: no bank login, no bank scraping, no automatic invoice sending, no Gmail/Apple Mail mutation without explicit approval, no cloud model access to sensitive financial contents by default, and no CPA/tax data access unless local-only and explicitly authorized.

### Locally Confirmed OpenClaw 2026.4.24 Surfaces

- Backend/data-contract shape planning now distinguishes March/April 2026 public OpenClaw release prior art from locally confirmed CLI help entries for `OpenClaw 2026.4.24 (cbcfdf6)` at `/home/openclaw/.nvm/versions/node/v24.14.0/bin/openclaw`.
- Confirmed help-visible local surfaces are `acp`, `approvals`, `capability`, `exec-policy`, `infer`, `memory`, `sessions`, `status`, and `tasks`. This confirms CLI help-visible local surfaces only, not audited internal behavior, schemas, data models, storage, security behavior, runtime state, services, or private data.
- Mapping posture: `tasks` -> future task/worker/flow state cards; `sessions` -> future conversation/session continuity cards; `memory` -> future knowledge/evidence/freshness surface, but not truth by itself; `infer` / `capability` -> provider-call authority boundary; `exec-policy` / `approvals` -> policy/approval state cards; `acp` -> agent/crew communication lane visibility; `status` -> system health/status evidence, without overclaiming.
- Local OpenClaw CLI surfaces should be treated as upstream evidence sources for future Mission Control cards, not as direct authority to execute actions. Operator Harness / Mission Control should eventually surface, interpret, gate, and explain these upstream primitives rather than duplicating them blindly.

- Launch Ladder is the operator-facing work progression toward a North Star.
- Source-Set Ladder is the slower ChatGPT Project context progression: `01_CURRENT_PRODUCT_SPEC -> 02_MAC_IOS_APP_BUILD -> 03_MAC_APP_KNOWLEDGE_SUBSTRATE -> 04_BACKEND_DATA_CONTRACT_READINESS -> future 05/etc.`.
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
- Active source-set baseline is now `04_BACKEND_DATA_CONTRACT_READINESS` for backend/data-contract shape planning.
- Mission Control fixture states must preserve the exact meanings of `profile_available`, `packet_available`, `launch_ready`, `approved`, `executed`, `succeeded`, `stale`, `blocked`, and `unknown`.
- The future app may display fixture records, but it must not execute from them.
- The knowledge-substrate planning package lives at `docs/planning/launch_ladder/knowledge_substrate/`. It is docs/test-only and prepares future SQLite-backed local memory thinking without creating a database, ingestion scripts, real file scanning, provider/model calls, app implementation, or backend/runtime implementation.
- Knowledge-substrate doctrine: this is not vanilla RAG and not classic flat chunk-vector RAG. SQLite stores the memory; markdown speaks it; HTML preserves shape; FTS finds it; compiled notes make it useful.
- Raw files are evidence, extracted text is parsed evidence, compiled notes are interpretation, claims are confidence-bounded, and operator promotions determine what is accepted, rejected, marked historical, marked sensitive, or excluded.
- Unknown means unknown; do not soften it into confidence. Sensitive and unknown content remains local-only/restricted by default.
- The Mac mirror for this planning package should be adjacent to Operator Harness readiness at `~/OpenClaw_Watch/operator_harness_knowledge_substrate/`, not inside `~/OpenClaw_Watch/operator_harness_readiness/` and not inside any numbered 24-file source-set folder.
- A Workspace Launch Profile that contains executable commands is malformed. Executable commands belong only in a Launch Packet or higher Launch Ladder action.
- This transition creates the `04_BACKEND_DATA_CONTRACT_READINESS` generated source set. It does not move to backend implementation, schema, SQL DDL, SQLite DB creation, ingestion, fixtures, app implementation, app naming, runtime/service/approval mutation, private-data inspection, provider/model calls, or audio/haptic/notification implementation.
- `Mac/iOS` is Apple-platform planning shorthand: Mac desktop app first, iOS companion later.
- Do not refresh the Mac mirror after every small docs/test slice; batch mirror refreshes at meaningful checkpoints unless source-set membership, withheld surfaces, manifest basis, or operator upload needs change.

## Source-Set Ladder Movement Criteria

Move from `01_CURRENT_PRODUCT_SPEC` to `02_MAC_IOS_APP_BUILD` when:

- the chat has extracted stable product requirements, authority boundaries, evidence/freshness expectations, and route-compression semantics;
- unresolved questions are app-facing rather than product/spec-facing;
- the next useful work needs UI states, read-only app fixtures, platform constraints, or native-client routing;
- the `01_CURRENT_PRODUCT_SPEC` folder is producing repeated summaries rather than new decisions.

Move from `02_MAC_IOS_APP_BUILD` to `03_MAC_APP_KNOWLEDGE_SUBSTRATE` when:

- app-facing workflow, view states, and read-only behavior are sufficiently clear;
- Mission Control fixture contract, first-screen composition, taste/atmosphere, quiet feedback, and knowledge-substrate concepts are ready to combine;
- the next useful work is a source-set planning pass that aligns app posture with compiled knowledge direction before backend/data-model or UI implementation begins.

Move from `03_MAC_APP_KNOWLEDGE_SUBSTRATE` to `04_BACKEND_DATA_CONTRACT_READINESS` when:

- the combined 03 planning chat has decided schema style, synthetic fixture promotion, operator-promotion contracts, and evidence/freshness boundaries;
- backend/data-model work is no longer premature;
- app planning is blocked on formal records rather than taste, posture, or source-set context.

Move from `04_BACKEND_DATA_CONTRACT_READINESS` to a future source set when:

- the backend/data-contract shape planning is complete;
- the next safe step requires new implementation or schema definitions beyond planning.

By the end of `04_BACKEND_DATA_CONTRACT_READINESS`, the chat should propose what the next folder should contain. Candidate future folders should be justified by evidence from the first four stages, not created automatically.

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
- Do not create source-set folder `05` from this file.
- Do not replace a stale or malformed 24-file baseline with bridge text.

## Refresh Rule

Use bridge-only upload when the baseline folder remains structurally valid and the delta can be explained in this one file. Use full 24-file refresh when the baseline source set, folder purpose, file membership, manifest authority, withheld surfaces, or source commit basis must change.

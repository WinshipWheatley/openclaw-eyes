# Watch Prior-Art Canonicalization

Status: docs-only decision record. This file classifies Mac OpenClaw Watch prior art by filename/concept and repo-side evidence. It does not inspect Mac-local private data, runtime state, logs, secrets, vaults, LegalPrivate, Gmail bodies, installed units, or provider/model outputs.

Freshness:

- Generated/reviewed: 2026-05-02
- Source basis: repo-side Launch Ladder docs and research bundle, modular readiness ledger, MCP progressive discovery profiles, service-management freeze, validation map, Launch Ladder static checker/test, and the operator-provided Mac audit filename list.
- Stale when: Mac Watch cleanup happens, source-set folders are regenerated, Legal/audit-build ingest flows are upgraded, dashboard/runtime-watch docs are promoted, or a later audit finds repo-side canonical copies not considered here.
- Refresh trigger: update before promoting any Mac Watch loose Markdown file, dashboard pattern, handoff, model/router note, staging replay note, or generated readiness folder into Operator Harness docs/tests.

## Purpose

This decision record keeps Mac `OpenClaw_Watch` material useful without letting it become hidden authority. The Mac audit found loose Markdown files, generated/mirrored readiness folders, legacy source-set flows, and a prototype Chat Stay Up To Date file. Some are good prior art for Operator Harness dashboard, runtime watcher, status, evidence, handoff, and source-set patterns. None should become canonical merely because it exists on Mac.

The goal is to classify what should be promoted later, mirrored as derived context, archived, ignored, left Mac-local, or treated as unsafe/out of scope.

## Authority Rule

- Mac Watch loose files are prior-art candidates only.
- Repo docs/tests/scripts are canonical only when tracked, reviewed, and validated.
- Generated ingest/mirror folders are derived and non-canonical.
- Private/runtime/log/secret surfaces are out of scope for this decision record.
- The real Operator Harness bridge is repo-side at `docs/planning/launch_ladder/CHAT_STAY_UP_TO_DATE.md` and Mac-side at `~/OpenClaw_Watch/operator_harness_readiness/CHAT_STAY_UP_TO_DATE.md`.
- The old Mac prototype `.claude/Chat_Stay Up To Date.md` is not canonical and should be deleted or clearly archived only by a later explicit Mac cleanup step.

## Classification Vocabulary

| Classification | Meaning |
| --- | --- |
| canonical equivalent exists | The concept already has a tracked repo-side source of truth or validated planning home. Use the repo source, not the Mac loose file. |
| promote later | Worth turning into canonical Operator Harness docs/tests in a future scoped lane. Do not promote by copying raw Mac content. |
| maybe useful | Potentially relevant, but needs a separate safety/content review before use. |
| Mac-local scratch | Useful as a local working note or operator-facing mirror aid, but not a repo source of truth. |
| archive/delete later | Should be removed from active Mac Watch or archived once a replacement is verified. No deletion in this slice. |
| do not use / unsafe | Requires private data, logs, secrets, runtime inspection, provider outputs, LegalPrivate, Gmail bodies, installed units, or other out-of-scope surfaces. |
| generated mirror only | Derived copy from repo or PC-generated status. Useful for review/freshness checks, not canonical authority. |

## Candidate Classification Table

| Mac path/name | Likely concept | Repo-side equivalent if any | Classification | Promotion target if useful | Reason | Next action |
| --- | --- | --- | --- | --- | --- | --- |
| `operator_harness_readiness/CHAT_STAY_UP_TO_DATE.md` | Real Operator Harness delta bridge | `docs/planning/launch_ladder/CHAT_STAY_UP_TO_DATE.md`; Operator Harness sync/refresh scripts | canonical equivalent exists | Keep as generated Mac copy of repo bridge | Confirmed real bridge path; adjacent to ingest root and not inside 24-file folders. | Keep mirrored; do not edit on Mac as source of truth. |
| `.claude/Chat_Stay Up To Date.md` | Prototype bridge wording | `docs/planning/launch_ladder/CHAT_STAY_UP_TO_DATE.md` | archive/delete later | None; prototype wording only | Hidden `.claude` location risks confusing future chats now that real bridge exists. | Later explicit Mac cleanup: delete or archive after bridge verification. |
| `Mac Local AI Watch — READ ME.md` | Mac Watch authority/setup pattern | `mac_eyes/Winship/Mac Local AI Watch — READ ME.md`; Launch Ladder authority docs | canonical equivalent exists | Maybe cite in future dashboard/readiness design note | Repo-side copy states Mac Watch is reflection, not canonical repo authority. | Keep as prior-art authority pattern; do not make it Operator Harness law. |
| `Mirror Freshness.md` | Mirror freshness marker | Source-set freshness rules in `05_EVIDENCE_AND_FRESHNESS.md` and `08_SOURCE_SET_REFRESH_SYSTEM.md` | promote later | Operator Harness dashboard/runtime-watch prior-art lane | Good concept: mirror freshness should become a source/freshness widget, but raw generated marker is not canonical. | Capture pattern later with source, timestamp, command, commit, stale reason. |
| `Live Watch.md` | One-glance heartbeat/status | `mac_eyes/Winship/Live Watch.md`; dashboard/reporting row in modular ledger | promote later | Operator Harness dashboard/runtime-watch prior-art lane | Useful pattern for scan-level status, but live-state claims must not be copied as proof. | Promote only as UI pattern with evidence/freshness fields. |
| `Right now.md` | Current loop/task status | `mac_eyes/Winship/Right now.md`; `HUMAN_OPERATOR_UX_PATTERNS.md` | promote later | Operator Harness dashboard/runtime-watch prior-art lane | Useful for "what needs attention" view; may include generated operational state. | Strip to schema/pattern, not raw status. |
| `AI Big Picture.md` | Detailed diagnostics/status dump | `mac_eyes/Winship/AI Big Picture.md`; modular ledger; validation map | maybe useful | Runtime watcher/dashboard design lane | Contains useful provenance/receipt/status concepts but can mix live process/provider/headroom claims. | Review later with private/log/runtime redaction rules. |
| `AI Right now.md` | Detailed AI loop diagnostics | `mac_eyes/Winship/AI Right now.md`; modular ledger | maybe useful | Runtime watcher/dashboard design lane | Same diagnostic pattern as Big Picture, with potential live-state/provider surfaces. | Convert to a safe evidence card shape later. |
| `Big Picture.md` | Operator-facing system snapshot | `mac_eyes/Winship/Big Picture.md`; `03_GOAL_HORIZONS.md`; `09_MAC_IOS_APP_BUILD_BRIEF.md` | promote later | Atlas/dashboard first-screen design lane | Good product pattern for high-level scan view; current copy can imply live health. | Use as UX prior art only; require source/freshness/authority fields. |
| `Builder Right now.md` | Builder runner status | `mac_eyes/Winship/Builder Right now.md` | do not use / unsafe | Possible future builder evidence lane only | Repo-side copy includes embedded log excerpts and hardware/runtime details. This slice does not promote logs/runtime state. | Do not ingest raw. Later lane must define redaction and source limits. |
| `Planner Right now.md` | Planner/task queue status | `mac_eyes/Winship/Planner Right now.md` | maybe useful | Workspace Launch Profile / planner dashboard lane | Useful current-task pattern, but references runtime task paths and stale process state. | Promote only as navigation/status schema after safety review. |
| `What happened.md` | Recent activity log | No tracked repo-side copy found in this slice | maybe useful | Evidence trail/activity timeline lane | Activity timeline is useful, but raw Mac loose file may be generated and may include logs/private details. | Do not use content until exact repo-safe copy or sanitized packet exists. |
| `Chathandoff.md` | Chat session handoff | Legal handoff pattern exists at `docs/planning/openclaw_legal/law_program/OPENCLAW_LEGAL_CHAT_HANDOFF.md` | maybe useful | Source-set handoff template lane | Handoff freshness/authority rules are useful; loose Mac file is not canonical. | Compare later against repo handoff patterns, not raw Mac copy. |
| `Hermes Chat handoff.md` | Hermes advisory handoff | Hermes advisory packet contract and tests | maybe useful | Hermes advisory source-set/handoff lane | Could inform advisory handoff UX, but Hermes runtime/private state remains withheld. | Review later with Hermes packet-in/proposal-out boundary. |
| `audit handoff:updater.md` | Audit-build handoff | Audit-build source-set scripts; service freeze; validation map | maybe useful | Audit-build manifest/delta upgrade lane | Likely useful for legacy audit flow, but filename alone is not source authority. | Defer until audit-build upgrade planning. |
| `staging_replay_harness.md` | Staging replay/testing harness note | No tracked repo-side doc found; staging fixture path exists only as code/fixture concept | promote later | Evidence/replay harness planning lane | Replay harness is useful for Operator Harness evidence, but must be docs/test-only and synthetic unless separately scoped. | Create later plan from repo-safe sources; do not copy Mac note blindly. |
| `Operator_Outcome_and_System_Contract.md` | Operator outcome/system contract | Launch Ladder first principles, security/authority, recommended v1 architecture | promote later | Operator Harness product contract lane | Concept aligns with authority and outcome contracts, but no repo-side copy was found. | Draft later from canonical docs, not Mac loose text. |
| `OpenClaw System Orientation - Working Explainer.md` | System orientation explainer | Modular readiness ledger; Launch Ladder index; runtime map | promote later | Operator Harness onboarding/orientation lane | Useful orientation surface for future operators/clients; should be rebuilt from canonical repo docs. | Promote later as short orientation, not as authority. |
| `Google Contract.md` | Google/Gmail broker or integration contract | Modular ledger Google broker row; validation map Google/Cassandra tests | maybe useful | Google broker/productization lane | Could contain integration doctrine; may touch Gmail/private scopes. | Do not use until reviewed in a Google broker lane with no Gmail bodies. |
| `local_model_router.md` | Local/external model routing policy | Model routing row in modular ledger; `docs/operations/OPENCLAW_MODEL_FALLBACK_POLICY.md` if current | maybe useful | Model/router prior-art lane | Likely relevant but model/provider decisions are sensitive and time-varying. | Compare later to canonical model fallback policy and tests. |
| `cassandra_forensic_audit.md` | Cassandra boundary audit | `docs/handoffs/cassandra/cassandra_boundary_forensic_audit_20260415.md` | canonical equivalent exists | Cassandra boundary cleanup lane, not Operator Harness core | Repo-side handoff has boundary findings; not an Operator Harness dashboard source by itself. | Leave in Cassandra lane; cite only as boundary prior art. |
| `gemma_vs_nemotron_policy.md` | Local model policy comparison | Model routing/fallback policy and local model privacy boundary in modular ledger | maybe useful | Model/router prior-art lane | Model choice notes can go stale quickly and may invite provider/model claims. | Defer; require benchmark/freshness evidence. |
| `docs/recommendations/current_state_improvements.md` | Improvement backlog | No tracked repo-side copy found in this slice | maybe useful | Productization backlog intake lane | Could be useful, but no canonical copy verified. | Defer until repo-safe copy or sanitized excerpt exists. |
| `docs/security/security_warnings_from_feynman_2026-04-12.md` | External security risk assessment | `docs/security/security_warnings_from_feynman_2026-04-12.md`; MCP/service/model/security docs | canonical equivalent exists | Security hardening backlog, not Watch canonicalization | Repo-side doc states it is external assessment input, not live verification or canonical runtime authority. | Keep as security prior art; do not claim vulnerabilities without verification. |
| `operator_harness_readiness/00_launch_ladder` | Mirrored Launch Ladder docs | `docs/planning/launch_ladder/*.md` | generated mirror only | None | Derived copy for Mac review. Canonical files are in repo. | Leave as mirror; refresh via Operator Harness sync when needed. |
| `operator_harness_readiness/01_operator_harness_research` | Mirrored research bundle | `docs/planning/launch_ladder/operator_harness_research/*.md` | generated mirror only | None | Derived copy for Mac review. Canonical files are in repo. | Leave as mirror; refresh via Operator Harness sync when needed. |
| `openclaw_audit_build_readiness/00_current_handoff_checkpoint` through `10_future_work_backlog` | Legacy audit-build readiness mirror | Audit-build sync/refresh scripts and service-freeze/validation docs | generated mirror only | Audit-build manifest/delta upgrade lane | Useful legacy flow, but lacks current Operator Harness per-source-set manifest and adjacent bridge pattern. | Upgrade later; no cleanup now. |
| Legal `CHATGPT_PROJECT_INGEST_LEGAL` folders | Legal source-set flow | Legal planning docs under `docs/planning/openclaw_legal/law_program/` | generated mirror only | Legal manifest/delta upgrade lane | Legacy-but-usable; requires Legal-specific boundary review before bridge/manifest upgrade. | Do not upgrade in Operator Harness slice. |

## Specific Notes

### Operator Harness Bridge

The canonical bridge/template is `docs/planning/launch_ladder/CHAT_STAY_UP_TO_DATE.md`. The Mac readiness-root copy is `~/OpenClaw_Watch/operator_harness_readiness/CHAT_STAY_UP_TO_DATE.md`. It is adjacent to `CHATGPT_PROJECT_INGEST_OPERATOR_HARNESS/` and is not counted inside any numbered 24-file source-set folder.

### `.claude/Chat_Stay Up To Date.md`

The `.claude` file is prototype/example only. It should not be used as hidden authority, source-set authority, or a replacement for the Operator Harness bridge. After the real bridge is verified at the readiness root, a later explicit Mac cleanup prompt should delete it or clearly archive it.

### Legal Source-Set Flow

Legal has a legacy-but-usable source-set flow and repo-side handoff patterns. Do not upgrade or reuse it from Operator Harness by implication. A later Legal-specific lane should add per-source-set `MANIFEST.md` files plus an adjacent bridge only after confirming Legal boundaries, private matter exclusions, and upload rules.

### Audit-Build Source-Set Flow

Audit-build readiness folders are useful prior art for source-set staging, but they are generated mirror surfaces. A later audit-build lane should upgrade the flow to per-source-set manifests plus an adjacent delta bridge. Do not change audit-build folders or scripts from this Operator Harness prior-art record.

### Runtime Watcher / Dashboard Prior Art

`Live Watch.md`, `Right now.md`, `Big Picture.md`, `AI Big Picture.md`, `AI Right now.md`, `Builder Right now.md`, and `Planner Right now.md` are the richest dashboard prior-art cluster. Promote only the safe pattern: scan-level status, source/freshness fields, evidence links, stale reasons, and authority boundaries. Do not promote raw live-state claims, process counts, hardware readings, provider headroom, log excerpts, private paths, or runtime claims.

### Model / Router Prior Art

`local_model_router.md`, `gemma_vs_nemotron_policy.md`, and related model/router notes should stay in a later model policy lane. They must be compared against canonical model fallback policy, local model privacy boundaries, benchmark evidence, and validation map entries before any product or routing claim is made.

### Staging Replay / Harness Prior Art

`staging_replay_harness.md` is worth promoting later as an evidence/replay harness concept if it can be rebuilt from repo-safe, synthetic, docs/test-only sources. It must not imply runtime replay, private-data replay, provider calls, or service mutation.

## Recommended Next Actions

1. Write a Mac cleanup prompt for `.claude/Chat_Stay Up To Date.md` after verifying `~/OpenClaw_Watch/operator_harness_readiness/CHAT_STAY_UP_TO_DATE.md` exists and the current Operator Harness sync/refresh dry-runs pass.
2. Plan a later Legal source-set upgrade: per-source-set `MANIFEST.md` files plus an adjacent delta bridge, with Legal-specific private-data boundaries.
3. Plan a later audit-build source-set upgrade: per-source-set `MANIFEST.md` files plus an adjacent delta bridge.
4. Plan an Operator Harness dashboard/runtime-watch prior-art promotion lane that turns the safe parts of Watch files into schemas, fixture examples, and UX rules.
5. Plan a model/router prior-art lane only after confirming current canonical model fallback policy and benchmark/freshness requirements.
6. Do not delete loose Mac Markdown files until this decision record is reviewed.

## Explicit Non-Actions

- No Mac deletion from PC WSL.
- No runtime inspection.
- No service status claims.
- No private-data review.
- No generated-folder cleanup.
- No sync script execution.
- No provider/model calls.
- No LegalPrivate, Gmail body, vault, secret, log, or installed-unit inspection.
- No promotion of Mac loose files into canonical docs without a future scoped intake lane.

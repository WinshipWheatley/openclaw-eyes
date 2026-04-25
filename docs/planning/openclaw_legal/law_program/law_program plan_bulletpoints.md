

# OpenClaw Legal — Off-Network Planning Bullet Points

Context: These notes capture the planning work discussed while away from the home network / full PC-WSL OpenClaw runtime. The Mac-side OpenClaw_Watch workspace is non-canonical and may be stale. These are planning bullets to review and expand later into detailed MD files before asking Codex to create the actual build plan.

## Starting context from the PC/WSL build session

- Before going off-network, the legal v0 spine had been built, tested, documented, and checkpointed on the main PC/WSL OpenClaw system.
- The legal v0 spine included matter workspace, source registration, TXT/MD/PDF text-layer extraction, extract-all CLI, local search, Markdown report export, review packet export, deployment profile, demo fixture, CLI walkthrough, and checkpoint docs.
- The final proof command passed with `80 passed in 0.69s`.
- The next off-network task was not to keep coding blindly, but to define product/security/UX architecture contracts before continuing the build.

## Mac-side / off-network working constraints

- The MacBook Pro currently has `OpenClaw_Watch`, a small reflection/workbench, not the authoritative runtime.
- Mac-side docs are useful for planning, drafting specs, machine contracts, UX flows, and build prompts.
- The Mac-side view should not be treated as live truth for queues, runtime state, model availability, budget, or running agents.
- Any build plan created from this Mac context must be verified later against the PC/WSL canonical repo.
- Off-network work should focus on contracts, UX requirements, roadmap order, and careful architecture decisions.

## Core product direction

- OpenClaw Legal should ship as Version 1, not a loose prototype.
- Version 1 must be reusable as product architecture, not a one-off custom branch for the first law firm.
- The first firm’s deployment should be tailored through profile/config and installed modules, not hardcoded forks.
- Architecture must be extractable without bringing over sensitive data, matter data, firm names, client names, or firm-specific assumptions.
- Improvements built for Firm #2 must never affect Firm #1 unless Firm #1 explicitly installs the relevant update/module.
- Firm #2’s new work should become either a core update, a firm-specific profile setting, or a separate suite module.
- Long-term product shape may become a suite of related legal products/modules rather than one tangled product.

## Strict per-firm stability

- Firm #1 must not receive new Firm #2 options, menus, labels, workflows, or behavior changes by default.
- No surprise update should alter a firm’s working deployment.
- Updates should be divided into security, stability, module, and new-capability lanes.
- Security updates should avoid workflow expansion.
- Stability updates should preserve the existing contract.
- Module updates should be opt-in per firm.
- New modules should be invisible until explicitly installed.
- Each firm should pin module versions and be able to update deliberately.
- Update UX should show what changed, what does not change, risk level, rollback availability, migration needs, and tests passed.

## Data privacy and legal vault boundaries

- Real legal data must never live inside the OpenClaw code repo.
- Code can know how to process legal data; the repo must not contain legal data.
- Matter vaults should live outside the repo in a dedicated Legal Vault path.
- Legal matter data includes sources, extracted text, reports, review packets, audit logs, attorney notes, emails, transcripts, and matter metadata.
- Non-local LLMs must not inspect or process matter content by default.
- Support packets, update packets, and feature requests must exclude client data, firm names, matter names, privileged content, extracted text, and sensitive logs.
- Demo data inside the repo must be fake or synthetic only.
- Matter vaults are private runtime data and must be excluded from updates, commits, support packets, and non-local LLM access.

## Legal product roles / no internal OpenClaw mythology in UX

- The legal product should not expose names like Cassandra, Chief, Guardian, Hermes, or PI.
- Internal capabilities can be reused, but the legal UX should expose legal/operations roles only.
- Possible legal-facing roles include Intake Clerk, Evidence Clerk, Records Custodian, Privilege Screener, Chronology Clerk, Review Coordinator, Compliance Gate, and Systems Clerk.
- Each role must have exact allowed actions and forbidden actions.
- Avoid vague agent-personality framing in the sellable legal product.
- Do not call a system role “Senior Partner” if it implies legal judgment.
- Prefer role names that communicate bounded support work, not final legal authority.

## Unsupported file handling / Alternative Methods menu

- Unsupported files should appear in the confidence/status bar, e.g. `Unsupported files: 2 [Alternative methods]`.
- The Alternative Methods menu should give controlled options for dealing with unsupported files.
- The system should first try safe local classification and installed local handlers.
- The system should then attempt local capability build/repair if policy allows.
- “Request Feature” should not appear until the system has tried local handling/build or that attempt has been policy-blocked.
- The system should not lazily escalate unsupported files to Winship before attempting local solutions.
- Unsupported-file actions should be clear: try local capability, show non-local options, request feature after failed local build, ignore for now.
- Non-local options should be visible as options with privacy tradeoffs, not automatic actions.

## Local repair / capability build boundary

- A local repair/system clerk can inspect sanitized diagnostics, public analog fixtures, local module code, and non-sensitive test failures.
- It may propose, build, and test candidate handlers locally in a sandbox.
- It may not send real matter data externally.
- It may not install unverified packages.
- It may not enable cloud APIs for matter content.
- It may not change firm workflow.
- It may not send sensitive logs.
- It may not modify production handlers without approval.
- Production handler modification requires Winship approval by default, either always or through an explicit escalation path.
- The system may prepare proposed patch/update packages, tests, rollback notes, and risk summaries.
- For law-firm deployments, default policy should be propose first, apply only after approval.

## Sanitized feature request packets

- Feature request packets should contain diagnostics only, not the unsupported legal file.
- Include extension, MIME type, file size range, duration/page count if detectable, codec/container hints, local tools attempted, local build attempts, error messages, redacted stack traces, installed extractor versions, firm profile version, OpenClaw Legal version, and module needing support.
- Exclude actual file, sensitive filename, client name, matter name, firm name, extracted text, attorney notes, report content, full audit logs, and private absolute paths.
- The system should search for public analog files similar to the unsupported file by technical characteristics only.
- Public analog search should include the closest public file and several additional stress-test files so one fix generalizes.
- Public analog search must not include sensitive case facts, client names, police department names, or revealing filenames.
- Feature request packets should give Winship enough diagnostic context to build the missing capability without starting from scratch.

## Update manager / firm-facing updates

- The law firm should see an Update Available view from v1, not rely on invisible or ad hoc patching.
- The firm should be able to choose security updates, stability updates, module updates, and optional new modules.
- Updates should be minimally invasive and should not require Winship to remote in and patch manually.
- The update UI should explain included changes, risks, rollback, tests passed, migration requirements, and whether matter data is touched.
- Updates must be confidence-preserving and should not silently change working behavior.
- New features developed for one firm should return to other firms as explicit versioned updates/modules only when appropriate.
- The system should aim for low upkeep once the product is right.

## Connect menu / adding firm computers

- OpenClaw Legal should have a Connect menu for adding firm computers to the local system.
- A main firm computer / Mac Studio should act as the Primary Node.
- Additional lawyer workstations should be able to join as approved local nodes.
- Computers must not join silently.
- A new computer should request to join; the Primary Node or authorized operator should approve it.
- Each node should have explicit role, permissions, capabilities, and task classes.
- The Connect menu should show this computer, firm computers, pending join requests, node health, compute sharing, and matter sharing.
- Initial node architecture should be approval-based, permissioned, lease-driven, and primary-node authoritative.
- MCP may be useful later as a tool bridge, but it should not be assumed as the distributed task backbone.
- A simple local task queue / lease model should be considered first.

## Primary node / lawyer workstation model

- The Primary Node owns the vault, policy, updates, audit, task queue, model distribution, and orchestration.
- A lawyer’s MacBook Pro should function as both their personal legal workstation and an optional firm compute node when idle.
- Matter access should depend on attorney identity, approved device, and assigned/shared matter permission.
- The firm Primary Node has administrative/system access as the firm-controlled system of record.
- A lawyer should open the app and see assigned matters, shared review requests, and possibly firm queue items if permitted.
- If the lawyer owns/is assigned a case, their permissions should be pre-checked according to matter role and firm policy.
- A random device should not gain matter access merely because the user knows credentials.

## Review handoff between lawyers

- Lawyers should be able to send bounded review/opinion requests to other lawyers easily.
- This should feel like “Send for Review,” not like pushing a technical task to an agent node.
- Review request types may include opinion request, privilege review, timeline check, second look, draft review, or packet review.
- The receiving lawyer should see the request in a “Shared With Me” area.
- The handoff should include scoped materials, a note/question, and permissions limited to that review.
- The system should audit who sent it, who received it, what was shared, comments, approvals, flags, and return status.
- This workflow should enable collaboration without broad matter access expansion.

## Human-priority compute and workstation headroom

- Lawyer workstations can contribute idle compute only when doing so does not interfere with the lawyer’s use of the machine.
- Human control always preempts background processing.
- If the lawyer starts using the machine, the system should pause/checkpoint work, release the lease, and requeue if needed.
- Worker nodes should leave CPU/RAM/battery/thermal headroom.
- Resource modes may include Off, Conservative, Balanced, Performance, and Overnight Only.
- Lawyer laptops should default to Conservative or Balanced.
- Primary node should run the heaviest models and long-running synthesis tasks.
- Workstations should handle bounded tasks like hashing, extraction, search indexing, packet assembly, and lighter local model tasks only when appropriate.

## Distributed processing and task queue

- Distributed processing should begin with deterministic jobs, not distributed autonomous LLM agents.
- Safe distributed task types include hash, extract, search index, OCR later, report packet assembly, and bounded diagnostics.
- Each task should include task ID, matter ID, source/artifact ID, task type, required capability, eligible nodes, claimed node, lease expiration, status, and audit trail.
- Worker tasks should use leases so dropped laptops do not strand work.
- The Primary Node should validate returned artifacts before accepting them into the matter vault.
- Worker nodes should not retain matter data after task completion unless explicit policy allows encrypted caching.
- Distributed audit records should be written to the Primary Node.

## Discovery intake connector / external discovery systems

- Law firms likely already receive discovery through portals, cloud folders, emails, ShareFile/Box/Drive/OneDrive, practice systems, or prosecutor/court systems.
- OpenClaw Legal should eventually let a lawyer trigger discovery downloads/imports into the Primary Node.
- External discovery sources require explicit firm-approved connectors.
- Discovery should land in a staging area first.
- The system should verify completion, hash/register files, and move/record them into the matter vault.
- The local matter vault becomes the processing source of truth after ingestion.
- Connector credentials should stay on the Primary Node or approved credential store, not worker nodes by default.
- No silent downloads, no automatic deletion from external portals, and no external cloud analysis of matter content.

## Auto-processing policy for discovery intake

- Lawyers should be able to choose what happens after discovery download completes.
- Options should include start processing automatically, wait for attorney approval, or schedule after hours.
- Lawyers should be able to preemptively set processing to start the moment discovery lands.
- If multiple lawyers have batches queued, work should enter a visible queue.
- Processing policy should be matter-level or intake-batch-level.
- High-priority/rush batches may jump queue only according to firm policy.
- Large batches may require review or confirmation before processing.

## Processing queue and ETA system

- The firm should see a processing queue with statuses and estimated completion times.
- Queue statuses may include downloading, staged, registered, queued, processing, blocked, review ready, completed, failed.
- ETA should show estimated start time, completion time, blockers, and confidence.
- ETA creates operational clarity and helps justify adding more nodes.
- The system should be able to say how much faster work could finish with available nodes or additional nodes.
- The estimate should be conservative by default and should not overpromise.
- ETA should be based on workload type, file type, size, page count/duration, node hardware, model version, and observed local performance.

## Adaptive ETA and calibration

- ETA should not be a dumb static progress bar.
- New models, updates, and nodes should enter calibration mode until enough local performance samples exist.
- The system should show ETA confidence states: low, calibrating, medium, high, conservative estimate.
- A calibration bar should show progress while the system evaluates a new node/model/update.
- Once enough evidence exists, the ETA should become high-confidence.
- If a new model appears to save time, the system should show projected vs measured time savings and confidence level.
- If a new node is added, the system should estimate potential time savings conservatively until real samples are available.
- If performance varies or regresses, the ETA should say so plainly.

## Model distribution and staging

- Worker nodes should not independently download local language models.
- The Primary Node should download, verify, approve, and distribute model artifacts to worker nodes.
- Workers should continue using the current approved model while the new model stages in the background.
- Workers should validate checksums/signatures before using staged models.
- Workers should switch models only at safe task boundaries.
- This avoids random downloads on lawyer laptops and prevents downtime.
- Primary Node should own model version control and distribution.

## Active case recheck / model comparison

- When a new local model/update lands, the system may ask whether to evaluate it against active cases.
- The system should offer safe comparison on cached/extracted artifacts, selected matter recheck, wait until next processing batch, or do not use for this matter.
- New models should not silently replace existing legal outputs.
- Rechecks should produce comparison/delta reports showing improvements, regressions, and items needing attorney review.
- Existing reports/artifacts should remain available until the attorney/operator promotes new outputs.
- The UX should communicate whether a change is measured, projected, unknown, or risky.

## Buyer-facing confidence/status bar

- The legal UX should show a truthful status bar, not sycophantic reassurance.
- Suggested fields: local-only on/off, cloud tools off/on, matter audit on, sources count, extracted count, unsupported count, needs review count, packet readiness, ETA confidence.
- Unsupported files should be actionable through Alternative Methods.
- ETA confidence should be visible and honest.
- The UX should say “ready,” “partial,” “blocked,” “needs review,” “unsupported,” “no extractable text,” or “calibrating” rather than vague positivity.
- Operator confidence should reflect actual system quality and evidence state.

## Obsidian vs controlled app UX

- Obsidian can be useful as an optional attorney notes/review surface, but should not be the main sellable UX.
- Obsidian has too many ways for an operator to misfile, delete, sync, or misconfigure sensitive data.
- A controlled app/console is better for a firm-facing legal product.
- Tauri is likely a better future shell than raw Rust GUI or Obsidian-only UX.
- Tauri could call the existing Python legal CLI at first and display JSON results.
- A controlled app should limit actions, enforce boundaries, show status clearly, and reduce operator stress.
- Initial Tauri spike should prove CLI invocation, vault root selection, JSON display, no network, and no writes outside selected vault.

## Suggested future UX screens

- Matters screen: create/open matter, assignment status, safety status.
- Sources screen: add discovery files, show hashes, types, extraction status.
- Extract screen: run extract-all, show success/no_text/unsupported/failed.
- Search/Review screen: search terms, snippets, source IDs, filenames.
- Packet screen: generate review packet, show included/excluded artifacts.
- Connect screen: add/approve/view/pause/remove firm computers.
- Queue screen: active processing, ETA, blockers, available nodes.
- Updates screen: security/stability/module updates and optional modules.
- Alternative Methods screen: unsupported file repair/build/request workflow.

## High-level roadmap direction

- Do not jump straight to distributed LLM agents.
- Single-machine Legal v1 and strict product/data/update boundaries come first.
- Then identity, matter assignment, and Connect menu skeleton.
- Then review handoff workflow.
- Then worker node enrollment.
- Then deterministic distributed jobs.
- Then model routing/distributed local LLM tasks.
- Then local repair/build/update system.
- Then external discovery connectors.
- OCR, embeddings, LLM summaries, dashboards, Gmail/Calendar/Drive wiring, installer/runtime activation, and multi-user/concurrency should wait until the core contracts are strong.

## Contract names to expand into detailed MD files later

- LEGAL_DATA_NEVER_IN_REPO
- LEGAL_LOCAL_ONLY_MODEL_POLICY
- LEGAL_VAULT_PATH_CONTRACT
- LEGAL_EXPORT_BOUNDARY
- LEGAL_AI_ACCESS_CLASSIFICATION
- LEGAL_DEMO_DATA_ONLY_IN_REPO
- LEGAL_AUDIT_EVERY_ACTION
- LEGAL_PRODUCT_CORE_SEPARATION
- LEGAL_FIRM_IMMUTABILITY_CONTRACT
- LEGAL_FIRM_PROFILE_BOUNDARY
- LEGAL_ROLE_NAMING_CONTRACT
- LEGAL_ROLE_PERMISSION_CONTRACT
- LEGAL_UNSUPPORTED_LOCAL_BUILD_FIRST
- LEGAL_FEATURE_REQUEST_ESCALATION_GATE
- LEGAL_SANITIZED_SUPPORT_PACKET
- LEGAL_PUBLIC_ANALOG_FIXTURE_SEARCH
- LEGAL_UPDATE_LANE_CONTRACT
- LEGAL_NO_SURPRISE_UPDATE_CONTRACT
- LEGAL_MODULE_VERSION_PINNING
- LEGAL_LOCAL_REPAIR_AGENT_BOUNDARY
- LEGAL_CONNECT_MENU_CONTRACT
- LEGAL_NODE_ENROLLMENT_CONTRACT
- LEGAL_NODE_PERMISSION_CONTRACT
- LEGAL_PRIMARY_NODE_AUTHORITY_CONTRACT
- LEGAL_WORKER_TASK_LEASE_CONTRACT
- LEGAL_WORKER_DATA_RETENTION_CONTRACT
- LEGAL_DISTRIBUTED_AUDIT_CONTRACT
- LEGAL_NODE_HEALTH_CONTRACT
- LEGAL_DISTRIBUTED_UPDATE_CONTRACT
- LEGAL_LOCAL_NETWORK_DISCOVERY_CONTRACT
- LEGAL_ATTORNEY_WORKSTATION_CONTRACT
- LEGAL_MATTER_ASSIGNMENT_PERMISSION_CONTRACT
- LEGAL_REVIEW_HANDOFF_CONTRACT
- LEGAL_HUMAN_PRIORITY_NODE_CONTRACT
- LEGAL_RESOURCE_HEADROOM_CONTRACT
- LEGAL_PRIMARY_NODE_ORCHESTRATION_CONTRACT
- LEGAL_NODE_TASK_CLASS_CONTRACT
- LEGAL_DEVICE_TRUST_CONTRACT
- LEGAL_DISCOVERY_INTAKE_CONNECTOR_CONTRACT
- LEGAL_DISCOVERY_STAGING_CONTRACT
- LEGAL_DISCOVERY_AUTO_PROCESS_POLICY
- LEGAL_FIRM_PROCESSING_QUEUE_CONTRACT
- LEGAL_TASK_ETA_CONTRACT
- LEGAL_NODE_CAPACITY_RECOMMENDATION_CONTRACT
- LEGAL_CONNECTOR_CREDENTIAL_BOUNDARY
- LEGAL_ADAPTIVE_ETA_CONTRACT
- LEGAL_PERFORMANCE_CALIBRATION_CONTRACT
- LEGAL_MODEL_DISTRIBUTION_CONTRACT
- LEGAL_MODEL_STAGING_CONTRACT
- LEGAL_ARTIFACT_RECHECK_CONTRACT
- LEGAL_MODEL_COMPARISON_CONTRACT
- LEGAL_ETA_CONFIDENCE_DISPLAY_CONTRACT
- LEGAL_NODE_PERFORMANCE_HISTORY_CONTRACT
- LEGAL_UPDATE_VALUE_REPORTING_CONTRACT

## Immediate next planning step

- Review these bullet points and select roughly 8-12 areas that need their own detailed MD files.
- Expand those selected areas into implementation-ready contracts/specs.
- Then ask Codex in VS Code to read all the planning files and produce an actual PC/WSL build plan.
- That build plan should verify what has already been built in the full OpenClaw system, decide what can be reused, and order implementation with checkpoints.
# OpenClaw Substrate + Mission Control Checkpoint v1

Generated: `2026-05-14`

Backend HEAD inspected: `42c58bf fix(corpus): align expected Mac read-model mirror files`

This is a compact checkpoint after the backend substrate, E-drive transfer path,
Report Bridge, Project Capsule stack, Mac read-model mirror, and Mission Control
read-model refresh. It updates, but does not replace:

- `docs/operations/OPENCLAW_CURRENT_SYSTEM_MAP_V0.md`
- `docs/operations/OPENCLAW_SUBSTRATE_CHECKPOINT_HANDOFF_V0.md`
- `docs/operations/OPENCLAW_PROJECT_CAPSULE_STACK_V0_REPORT.md`
- `docs/operations/OPENCLAW_REPORT_BRIDGE_V0.md`
- `docs/operations/OPENCLAW_READ_MODEL_SHUTTLE_V0.md`

## 1. Canonical posture

- PC/WSL `/home/openclaw` is the canonical backend repo and evidence-processing authority.
- Business Ops ledger remains `.openclaw/business_ops/ledger.sqlite`.
- Mac roots are mirror/app roots, not backend authority.
- Raw files, generated read-models, reports, manifests, packets, and receipts are evidence surfaces, not truth by default.
- Truth and promotion require explicit gates; imports and read-model visibility do not grant authority.

## 2. Backend substrate completed layers

- Corpus Atlas v0.6: metadata, freshness, sensitivity, retrieval/ingestion eligibility, canonicality, world binding, reorg, mirror, and multi-root posture.
- Evidence Kettle v0.1: bounded `evidence_*` seed ingestion from generated read-model snapshots and receipt summaries.
- Local Tool Inventory v0: observed installed-tool metadata only.
- Tool Inventory read-model export: `tool_inventory.json` and `tool_inventory_OPERATOR.md`.
- Tool Intake Registry v0: candidate policy overlay; no candidate is approved or integrated.
- Tool Intake read-model export: `tool_intake.json` and `tool_intake_OPERATOR.md`.
- Context Selection / Knowledge Packet v0: deterministic evidence-grounded packet compiler.
- Context Selection read-model export: `context_selection.json` and `context_selection_OPERATOR.md`.
- Project Capsule Stack v0: synthetic demo capsule contract, query surfaces, template export, and no-authority planning posture.
- Project Capsule read-model export: `project_capsules.json` and `project_capsules_OPERATOR.md`.
- Synthetic demo capsule template: `generated/project_capsules/demo_project_capsule_v0/`.
- Legacy GitHub Repo Intake placeholder: `github_legacy_openclaw`, non-canonical and not imported.
- Module Registry v0: planning-safe reusable capability registry with no runtime activation.
- Report Bridge v0: E-drive sanitized report-package metadata import into `report_bridge_*`.
- Report Bridge read-model export: `report_bridge.json` and `report_bridge_OPERATOR.md`.
- Mac Mirror Atlas v0: manifest-only Mac root import into Corpus Atlas.
- Cross-Machine Read-Model Shuttle v0: E-drive package/apply/import loop for generated read-model mirrors.
- Current System Map v0: short orientation surface for the backend stack.
- Full-suite failure baseline v0: classified full-suite debt without fixes.

## 3. Generated read-model surfaces

Current expected generated read-model set:

- `generated/read_models/source_inventory.json`
- `generated/read_models/source_inventory.operator.txt`
- `generated/read_models/helm_state.json`
- `generated/read_models/helm_state.operator.txt`
- `generated/read_models/world_domain_registry.json`
- `generated/read_models/world_domain_registry.operator.txt`
- `generated/read_models/world_status.json`
- `generated/read_models/world_status.operator.txt`
- `generated/read_models/artifact_registry.json`
- `generated/read_models/artifact_registry.operator.txt`
- `generated/read_models/runtime_activation_gate.json`
- `generated/read_models/runtime_activation_gate.operator.txt`
- `generated/read_models/evidence_freshness.json`
- `generated/read_models/evidence_freshness.operator.txt`
- `generated/read_models/tool_inventory.json`
- `generated/read_models/tool_inventory_OPERATOR.md`
- `generated/read_models/tool_intake.json`
- `generated/read_models/tool_intake_OPERATOR.md`
- `generated/read_models/context_selection.json`
- `generated/read_models/context_selection_OPERATOR.md`
- `generated/read_models/project_capsules.json`
- `generated/read_models/project_capsules_OPERATOR.md`
- `generated/read_models/report_bridge.json`
- `generated/read_models/report_bridge_OPERATOR.md`
- `generated/read_models/generated_current_state.md`
- `generated/read_models/generated_next_actions.md`

Context packet surfaces:

- `generated/context_packets/context_packet_latest.json`
- `generated/context_packets/context_packet_latest.md`

Project capsule template surface:

- `generated/project_capsules/demo_project_capsule_v0/`

## 4. Mac mirror / shared drop status

- Mac generated read-model mirror observed files: `26`.
- Missing expected files: `0`.
- Extra files: `0`.
- Hash mismatches: `0`.
- Raw content imported: `false`.
- No-go/sensitive rows with content hashes: `0`.
- Shared drop paths:
  - Mac: `/Volumes/openclaw_e`
  - PC: `E:\openclaw`
  - WSL: `/mnt/e/openclaw`
- Manual Mac-to-PC dragging should no longer be needed for the read-model manifest loop when the share is mounted.
- The Mac generated-read-model mirror remains a mirror/app surface, not truth authority.

## 5. Mission Control app status

- Mac app checkpoint: `ec4d520 feat(app): surface substrate read models`.
- Mission Control remains read-only.
- It opens to Global Helm Overview.
- It now displays System Layers for:
  - `context_selection`
  - `project_capsules`
  - `report_bridge`
  - `tool_inventory`
  - `tool_intake`
- Boundary:
  - no backend execution
  - no networking
  - no writes
  - no persistence
  - no timers/polling
  - no action buttons
  - no runtime, agent, tool, model, or container activation
  - no fake live health

## 6. Explicitly blocked / future-gated

- `runtime_authority=false`
- `activation_allowed=false`
- `backend_execution=false`
- `dynamic_world_state=false`
- `strategic_gravity_supported=false`
- `agent_presence_supported=false`
- Tool execution is not authorized.
- Docker and Ollama are detected but not approved or integrated.
- No live client deployment.
- No remote management.
- No automatic client data intake.
- No truth promotion from imported packages.
- Report Bridge package arrival is evidence visibility only, not approval, freshness, truth, or authority.

## 7. Test / failure posture

- Scoped substrate tests have passed across recent corpus, evidence, tool, context, project capsule, shuttle, mirror, and report bridge lanes.
- Mac Mission Control Xcode build succeeded for the read-model refresh on the Mac-side lane.
- Full-suite collection remains blocked by missing `numpy` in `tests/test_cassandra_voice.py`.
- Current classified ignored-Cassandra baseline: `83 failed, 2623 passed, 1 skipped`.
- The full-suite failure baseline found no suspected regressions in the current substrate lanes.
- No broad full-suite fixes were attempted as part of these checkpoint lanes.

## 8. Operational no-go / environment notes

- C-drive Remote Desktop trace pressure was stabilized earlier.
- Old traces were moved to the E-drive no-go archive:
  `E:\.openclaw_sensitive_no_go\windows_openclaw_user_temp_moved_2026-05-14\RdClientAutoTrace_old_until_1145`
- Do not crawl, ingest, hash, summarize, or treat that archive as evidence.
- WSL VHD/swap files on C were not touched; any change there needs a separate planned shutdown/config/migration lane.
- `polish_loop/tasks/` remains untracked and should be left untouched unless explicitly opening a Cassandra/Chief cleanup lane.

## 9. Next recommended lanes

Recommended next lane:

**A. Project Capsule v0.1 / Real Template Workflow**

- Turn the synthetic capsule template into a repeatable generator for real-but-empty client/project repos.
- Keep no deployment authority, no client data access, no runtime authority, no tool execution, and no agent activation.
- Use Project Capsule, Module Registry, Tool Intake, Context Selection, and Report Bridge posture as planning inputs only.

Alternates:

**B. Legacy GitHub Repo Intake v0.1**

- Inspect older build repo material as a non-canonical legacy root.
- Classify reusable, superseded, stale, and dangerous material.
- Do not merge or promote anything yet.

**C. Mission Control Polish v0.1**

- Improve the System Layers display while keeping Mission Control strictly read-only.

**D. Report Bridge Sample Package v0**

- Create and import one synthetic package through `/mnt/e/openclaw/node_uplink/inbox`.
- Prove the bridge path end-to-end without real client data, runtime, deployment, or truth promotion.

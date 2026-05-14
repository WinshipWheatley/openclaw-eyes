# OpenClaw Substrate Checkpoint Handoff v0

Generated: `2026-05-14`

This is a compact current-stack handoff after the Mac generated-read-model mirror
and Cross-Machine Read-Model Shuttle v0 were proven end-to-end. It is a
checkpoint, not a replacement for the system map:

- System map: `docs/operations/OPENCLAW_CURRENT_SYSTEM_MAP_V0.md`

## 1. Current canonical posture

- PC/WSL `/home/openclaw` is the canonical backend repo and evidence-processing authority.
- Business Ops ledger remains `.openclaw/business_ops/ledger.sqlite`.
- Mac roots are mirror/app roots, not backend authority.
- Generated read-models, packet artifacts, reports, manifests, and receipts are evidence surfaces, not truth by default.
- Truth/promotion requires explicit gates; no runtime or client authority is implied.

## 2. Built substrate layers

- Corpus Atlas v0.6: metadata, freshness, sensitivity, retrieval/ingestion eligibility, canonicality, world binding, reorg, and multi-root posture.
- Evidence Kettle v0.1: bounded `evidence_*` seed ingestion from generated read-model snapshots and receipt summaries.
- Local Tool Inventory v0: observed installed-tool metadata only.
- Tool Inventory read-model export v0: generated tool posture with no activation authority.
- Tool Intake Registry v0: candidate policy overlay; no candidate is approved or integrated.
- Tool Intake read-model export v0: generated candidate policy posture.
- Context Selection / Knowledge Packet v0: deterministic evidence-grounded packet compiler.
- Context Selection read-model export v0: generated packet posture for app/agent-safe inspection.
- Mac Mirror Atlas v0: explicit manifest import into Corpus Atlas; metadata-only and non-canonical.
- Cross-Machine Read-Model Shuttle v0: package/apply/import workflow for PC-to-Mac read-model sync.
- Full-suite failure baseline v0: classified current full-suite debt without fixes.
- Current System Map v0: short orientation surface for the stack.
- Mission Control Mac app: read-only helm overview; no backend authority.

## 3. Generated read-model surfaces

Canonical PC/WSL generated read-model source:

- `generated/read_models/source_inventory.json`
- `generated/read_models/helm_state.json`
- `generated/read_models/world_domain_registry.json`
- `generated/read_models/world_status.json`
- `generated/read_models/artifact_registry.json`
- `generated/read_models/runtime_activation_gate.json`
- `generated/read_models/evidence_freshness.json`
- `generated/read_models/tool_inventory.json`
- `generated/read_models/tool_intake.json`
- `generated/read_models/context_selection.json`
- `generated/read_models/generated_current_state.md`
- `generated/read_models/generated_next_actions.md`

Operator companions are present for tool inventory, tool intake, context selection,
and the older `.operator.txt` read-model exports.

Context packet surfaces:

- `generated/context_packets/context_packet_latest.json`
- `generated/context_packets/context_packet_latest.md`

## 4. Mac / Mission Control mirror status

- Mac generated-read-model mirror root: `mac_generated_read_models`.
- Mac app root: `mac_mission_control_app`.
- Mac operating mirror placeholder: `mac_openclaw_mirror` registered but not scanned.
- Latest imported Mac generated-read-model manifest has `22` generated read-model files.
- `context_selection.json` missing: `no`.
- `context_selection_OPERATOR.md` missing: `no`.
- `tool_inventory.json` present.
- `tool_intake.json` present.
- Missing expected files: `0`.
- Mirror mismatches: `0`.
- Raw content imported: `false`.
- No-go/sensitive rows with content hashes: `0`.
- Mission Control remains a read-only consumer surface; it was not modified in this checkpoint.

## 5. Read-model shuttle status

- Cross-Machine Read-Model Shuttle v0 is implemented and proven.
- Prepare command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/prepare_mac_read_model_shuttle.py --format operator
```

- Import command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/import_mac_read_model_shuttle.py --manifest /mnt/c/openclaw/mac_generated_read_models_manifest.json --format operator
```

- A Mac-side package includes `payload/generated_read_models/`, `shuttle_manifest.json`, `APPLY_ON_MAC.sh`, and `README.md`.
- The Mac-side apply script copies generated read-models, verifies sizes/hashes, and writes an importable `mac_generated_read_models_manifest.json`.
- The latest returned manifest import succeeded with `22` paths, `22` safe hashes, `0` no-go rows, and `0` mismatches.
- Remaining manual work is only moving the package or returned manifest when no shared folder is available.

## 6. Known blocked / future-gated capabilities

- `runtime_authority=false`
- `activation_allowed=false`
- `backend_execution=false`
- `dynamic_world_state=false`
- `strategic_gravity_supported=false`
- `agent_presence_supported=false`
- Tool execution is not authorized.
- Docker and Ollama are detected but not approved or integrated.
- No model execution, container execution, remote access, or network authority is granted.
- No client deployment yet.
- No automatic Mac/PC daemon sync yet.
- No legacy GitHub repo intake yet.
- No project/client capsule generator yet.

## 7. Test / failure posture

- Cross-Machine Read-Model Shuttle scoped validation passed: `47 passed`.
- Context Selection read-model scoped validation passed: `53 passed`.
- Full suite collection remains blocked by missing `numpy` in `tests/test_cassandra_voice.py`.
- Current classified ignored-Cassandra baseline: `83 failed, 2623 passed, 1 skipped`.
- Failure baseline found no suspected regressions in the corpus/evidence/tool/context substrate lanes.
- No broad failure fixes were attempted as part of this checkpoint.

## 8. Known no-go / sensitive operational notes

- Do not crawl, ingest, hash, summarize, or treat E-drive sensitive archives as evidence.
- Recent C-drive cleanup moved old Windows Remote Desktop traces to:
  `E:\.openclaw_sensitive_no_go\windows_openclaw_user_temp_moved_2026-05-14\RdClientAutoTrace_old_until_1145`
- Breadcrumb remains at the original trace source:
  `OPENCLAW_OLD_TRACE_FILES_MOVED_TO_E_DO_NOT_CRAWL.txt`
- Legal/billing material moved earlier to an E-drive sensitive no-crawl boundary with C-side breadcrumbs.
- WSL VHD/swap files on C were not touched; any change there needs a separate planned shutdown/config/migration lane.
- `polish_loop/tasks/` remains intentionally untouched in this checkpoint.

## 9. Next recommended lane

Recommended next lane: **Project Capsule v0**.

Project Capsule v0 should begin the “build X for Y” client/project generator using
the existing corpus/evidence/tool/context/read-model substrate. It should remain
metadata-first and non-authorizing: no runtime activation, tool execution, client
deployment, remote management, or automatic truth promotion.

Alternate next lanes:

- **Legacy GitHub Repo Intake v0**: metadata-first intake of the old GitHub repo as non-canonical until explicitly promoted.
- **Mission Control Read-Model Refresh v0**: update the read-only Mac app to consume the newest generated read-model surfaces, especially `context_selection.json`.

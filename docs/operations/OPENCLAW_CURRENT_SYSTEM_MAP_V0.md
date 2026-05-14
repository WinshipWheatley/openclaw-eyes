# OpenClaw Current System Map v0

Generated: `2026-05-14`
Git HEAD inspected: `1696209 feat(corpus): add mac mirror manifest atlas`

This is the canonical short orientation surface for the current OpenClaw backend
substrate. Older or narrower maps remain supporting context, especially:

- `docs/operations/OPENCLAW_CURRENT_RUNTIME_MAP.md`
- `generated/read_models/generated_current_state.md`
- `generated/read_models/generated_next_actions.md`
- `docs/operations/OPENCLAW_FULL_SUITE_FAILURE_BASELINE_V0.md`

## 1. Current authority posture

- PC/WSL `/home/openclaw` is the canonical backend repo and evidence-processing authority.
- The Business Ops ledger is `.openclaw/business_ops/ledger.sqlite`.
- Mac roots are mirror/app roots, not backend authority.
- Raw files, reports, packets, manifests, and read-models are evidence surfaces, not truth by default.
- Generated read-model facts may be selected as evidence, but truth/promotion requires explicit gates.
- Unknown, needs-review, sensitive, and no-go material is excluded from retrieval/ingestion by default.

## 2. Current substrate layers

- Corpus Atlas v0.6: writes `corpus_*` tables; classifies metadata, freshness, sensitivity, retrieval eligibility, ingestion eligibility, canonicality, world binding, reorg candidates, and multi-root posture.
- Evidence Kettle v0.1: writes bounded `evidence_*` tables; ingests generated read-model snapshots and receipt summaries only; evidence is not truth.
- Local Tool Inventory v0: writes `tool_inventory_*`; records observed installed-tool metadata only. Latest inspected counts: `63` observed, `15` detected, `48` not detected.
- Tool Inventory read-model export: `generated/read_models/tool_inventory.json` and `tool_inventory_OPERATOR.md`; all activation/integration/runtime/network/model/container/remote flags remain false.
- Tool Intake Registry v0: writes `tool_intake_*`; records candidate policy rows only. Latest inspected counts: `39` candidates, `33` inventory-linked, `2` installed candidates.
- Tool Intake read-model export: `generated/read_models/tool_intake.json` and `tool_intake_OPERATOR.md`; no candidate is approved or integrated.
- Context Selection / Knowledge Packet v0: writes `context_selection_*`; latest packet selected `60` bounded evidence items for `world=build`, task `prepare Mission Control frontend prompt`; selected context is not truth promotion.
- Mac Mirror Atlas v0: imports explicit Mac metadata manifests into `corpus_*`; no Mac crawl, SSH, SCP, rsync, file copy, or raw body import.
- Full-suite failure baseline v0: classifies current full-suite failures without fixing them.
- Mission Control Mac app: read-only helm overview exists on the Mac side; it consumes generated/read-model posture and does not grant backend authority.

## 3. Generated surfaces

Key generated read-models:

- `generated/read_models/source_inventory.json`
- `generated/read_models/helm_state.json`
- `generated/read_models/world_domain_registry.json`
- `generated/read_models/world_status.json`
- `generated/read_models/artifact_registry.json`
- `generated/read_models/runtime_activation_gate.json`
- `generated/read_models/evidence_freshness.json`
- `generated/read_models/tool_inventory.json`
- `generated/read_models/tool_intake.json`
- `generated/read_models/generated_current_state.md`
- `generated/read_models/generated_next_actions.md`

Generated context packet surfaces:

- `generated/context_packets/context_packet_latest.json`
- `generated/context_packets/context_packet_latest.md`

Important staleness note: `generated_next_actions.md` still points at older Orientation Snapshot work. The current recommended lane is in section 8 below.

## 4. Mac mirror state

- `mac_generated_read_models` is imported cleanly as a non-canonical generated read-model mirror.
- `mac_mission_control_app` is represented via manifest as a non-canonical app root.
- `mac_openclaw_mirror` is registered as a future mirror root, not scanned.
- Latest generated read-model mirror report observed `20` generated read-model files.
- `tool_inventory.json` missing: `no`.
- `tool_intake.json` missing: `no`.
- Mirror mismatches: `0`.
- Mirror candidates: `matched_hash=90`, `candidate_not_scanned=80`.
- No-go/sensitive files with hashes: `0`.
- Raw content imported: `false`.
- Scoped Mac mirror validation: `25 passed`.
- Mac roots are metadata-only mirror/app records unless explicitly promoted later.

## 5. Explicitly blocked / future-gated

- `runtime_authority=false`
- `activation_allowed=false`
- `backend_execution=false`
- `dynamic_world_state=false`
- `strategic_gravity_supported=false`
- `agent_presence_supported=false`
- Tool execution is not authorized.
- Docker and Ollama are detected, but not approved or integrated.
- Ollama installed does not mean models may be run.
- Docker installed does not mean containers may be run.
- No client deployment yet.
- No remote management yet.
- No automatic Mac/PC sync yet.
- No legacy GitHub repo intake yet.
- No project/client capsule generator yet.

## 6. Test and failure posture

- Scoped substrate regression check from the failure baseline passed: `62 passed`.
- Context Selection scoped regression previously passed across the context/corpus/evidence/tool lanes.
- Full suite collection is blocked by missing `numpy` in `tests/test_cassandra_voice.py`.
- With `tests/test_cassandra_voice.py` ignored, the current baseline is `83 failed, 2623 passed, 1 skipped`.
- That differs from the earlier observed `82 failed, 2624 passed, 1 skipped`; use `83 failed, 2623 passed, 1 skipped` as the current classified baseline.
- No suspected substrate regressions were found in the failure baseline.
- Top failure buckets:
  - `test_double_signature_drift`: `39`
  - `cli_subprocess_import_path_failures`: `11`
  - `orientation_payment_status_context_contract_drift`: `11`
  - `identity_contact_fixture_drift`: `7`
  - `environment/dependency/fixture failures`: `3`
- No fixes were attempted in the failure-baseline lane.

## 7. Operational environment note

- C drive is currently stable at about `28G` free.
- Main recent pressure source was Windows Remote Desktop trace output under:
  `C:\Users\Open Claw\AppData\Local\Temp\DiagOutputDir\RdClientAutoTrace`
- Verified old traces were moved to:
  `E:\.openclaw_sensitive_no_go\windows_openclaw_user_temp_moved_2026-05-14\RdClientAutoTrace_old_until_1145`
- Breadcrumb left at source:
  `OPENCLAW_OLD_TRACE_FILES_MOVED_TO_E_DO_NOT_CRAWL.txt`
- Do not crawl, ingest, hash, summarize, or treat that E-drive archive as evidence.
- WSL VHD/swap files on C were not touched and require a separate planned shutdown/config/migration lane if ever addressed.

## 8. Next recommended build lane

Recommended next lane: **Context Packet Read-Model Export v0**.

Reason: Context Selection / Knowledge Packet v0 exists and already writes packet records plus
`generated/context_packets/` artifacts, but it does not yet have a stable
`generated/read_models/` surface for Mission Control and agent-safe consumption.

The lane should export bounded packet posture and no-authority flags into generated read-models
without changing generated central contracts unless explicitly justified.

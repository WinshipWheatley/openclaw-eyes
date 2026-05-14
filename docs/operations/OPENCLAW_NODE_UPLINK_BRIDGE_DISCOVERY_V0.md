# OpenClaw Node Uplink / Bridge Discovery v0

Date: `2026-05-14`

Purpose: reconcile existing bridge, shuttle, sync, import, export, manifest,
connector, client, and multi-root work before building any new Node Uplink layer.
This is discovery only. No Node Uplink implementation was added.

Current E-drive shuttle posture:

- Standard transfer root: Windows `E:\openclaw`, WSL `/mnt/e/openclaw`.
- Shuttle to Mac: `/mnt/e/openclaw/shuttle/to_mac`.
- Shuttle from Mac: `/mnt/e/openclaw/shuttle/from_mac`.
- Returned Mac generated read-model manifest: `/mnt/e/openclaw/mac_generated_read_models_manifest.json`.
- `C:\openclaw` / `/mnt/c/openclaw` is deprecated for shuttle use.

## Searched Terms And Areas

Terms searched across tracked repo surfaces and safe explicit directories:

- bridge, uplink, node, sync, shuttle, mirror, import, export, connector
- ingest, remote, client, capsule, deployment, manifest, broker, transport, relay
- handoff, report package, receipt batch, Mac, PC, WSL
- multi-root, multi-machine, multi-computer

Areas inspected:

- repo filenames via `git ls-files`
- `docs/operations/`
- `docs/planning/launch_ladder/`
- `docs/planning/project_packets/`
- `scripts/`
- `tests/`
- `generated/read_models/`
- `generated/context_packets/`
- active Python modules for shuttle, mirror, corpus, evidence, context, tools,
  project capsule, legacy intake, and module registry

Areas deliberately not inspected as raw content:

- `polish_loop/tasks/`
- private/no-go/sensitive roots
- legal/private/vault/secret paths except tracked file names surfaced by repo
  search

Exact `uplink` / `node uplink` terminology was not found in the repo.

## Existing Surfaces Found

| Surface | Status | Overlap With Node Uplink | Finding |
|---|---:|---|---|
| `read_model_shuttle.py` | current_active / candidate_to_extend | High | Packages generated read-model files, writes a manifest, produces a Mac apply script, and imports returned Mac manifests through the existing atlas path. This is the strongest active base. |
| `scripts/prepare_mac_read_model_shuttle.py` | current_active / candidate_to_extend | High | Current PC/WSL package command. Defaults now point to `/mnt/e/openclaw/shuttle/to_mac`. |
| `scripts/import_mac_read_model_shuttle.py` | current_active / candidate_to_extend | High | Current returned-manifest import command. It validates `mac_generated_read_models`, copies the manifest into `import_manifests/`, imports metadata, and reports mirror state. |
| `docs/operations/OPENCLAW_READ_MODEL_SHUTTLE_V0.md` | current_active | High | Operator contract for the safe Mac read-model shuttle. Updated to E-drive transfer paths. |
| `mac_mirror_atlas.py` | current_active / candidate_to_extend | High | Provides safe root manifest build/import, Corpus Atlas upsert, Mac root classification, mirror candidate matching, mismatch reports, and no-raw-body import boundaries. |
| `scripts/build_root_manifest.py` and `scripts/import_root_manifest.py` | current_active / candidate_to_extend | High | Existing manifest contract and import path for explicit roots. Useful for generalized node report packages. |
| `corpus_atlas.py` / `corpus_*` tables | current_active / candidate_to_extend | High | Already has multi-root metadata, root kinds, owner scopes, client/project placeholders, retrieval eligibility, ingestion eligibility, sensitivity, and canonicality. |
| `scripts/query_corpus_atlas.py` | current_active | Medium | Already reports multi-root, Mac roots, mirrors, generated-read-model mirrors, mismatches, retrieval, ingestion, and unknown review queues. |
| Evidence Kettle v0.1 | current_active / partial_overlap | Medium | Ingests bounded generated read-model snapshots and receipt summaries into `evidence_*`. It is a consumer/substrate layer, not a transport. |
| Context Selection v0 | current_active / partial_overlap | Medium | Builds bounded knowledge packets from evidence/context rows. Useful as downstream consumer of node reports, not as transport. |
| Tool Inventory / Tool Intake read-model exports | current_active / partial_overlap | Medium | Safe generated report surfaces that can be shipped through the existing shuttle/report package pattern. |
| Project Capsule v0 | current_active / partial_overlap | Medium | Client/project planning contract exists and is safe. It can eventually request node/report inputs without real client data or deployment authority. |
| Legacy Repo Intake v0 | current_active / partial_overlap | Medium | Represents `github_legacy_openclaw` as non-canonical and not imported. Useful precedent for non-authorizing external/root registration. |
| Module Registry v0 | current_active / partial_overlap | Medium | Lists reusable capabilities, including `read_model_shuttle`, `mac_mirror_atlas`, and `project_capsule`, with no activation authority. |
| `docs/planning/launch_ladder/22_CROSS_PLATFORM_BRIDGE_CONTRACT_BREADCRUMB.md` | planning_only / candidate_to_extend | High conceptually | Already defines the future bridge contract direction: stable packet contract, native adapters, authority basis, freshness, terminal state, audit receipt. It is not implementation. |
| `docs/planning/launch_ladder/20_DEPLOYMENT_TOPOLOGY_NODE_PORTABILITY_AND_OS_AGNOSTICISM.md` | planning_only | High conceptually | Defines node portability, deployment profiles, node capability manifests, and authority-domain separation. It warns against treating network topology as trust. |
| `docs/planning/launch_ladder/30_BACKEND_SOURCE_SET_BRIDGE_AND_EXCLUSION_PLAN.md` | planning_only / guardrail | Medium | Useful exclusion doctrine: discovered does not mean read; visible does not mean authorized; private roots and bridge payloads must not become backend authority. |
| `backend_sqlite_schema.py` provenance `bridge_ref` fields | partial_overlap / older schema concept | Low to Medium | Inert semantic schema includes bridge references in provenance records. It is not the active shuttle/import implementation. |
| `operator_evidence_bridge.py` | current_active / partial_overlap | Low | Deterministic response/evidence-name bridge. It does not read files, call providers, persist state, or transport packages. Conceptually useful, not a Node Uplink base. |
| `chief_approval_bridge.py` | current_active but unsafe_for_reuse here | Low | Runtime approval bridge for Chief/Telegram choices. It is not a report/package bridge and still references `/mnt/c/OpenClawShared/...`; do not extend for Node Uplink. |
| `google_access_broker.py` and Cassandra connector/relay code | current_active but unsafe_for_reuse here | Low | Live connector/broker domain for Gmail/calendar/contact workflows. Not appropriate for sanitized node report package import. |
| `mac_eyes/Launchers/*sync*.sh` | stale_or_legacy / unsafe_for_reuse | Medium historical overlap | Older PC-to-Mac sync scaffolding uses SSH/rsync and some watch/delete semantics. Keep as historical reference only; do not use as the new bridge base. |
| `scripts/sync_project_packets_to_mac.sh` | stale_or_legacy / unsafe_for_reuse | Medium historical overlap | One-way project packet mirror using SSH/rsync and `--delete` in apply mode. It conflicts with the no-network/no-delete posture for Node Uplink v0. |
| `sync_to_mobile.sh` | stale_or_legacy / unsafe_for_reuse | Low | SSH-based mobile vault sync plus process/status scraping. Not suitable for the current safe package/import pattern. |
| `docs/producer/PRODUCER_TOOL_BRIDGE_CONTRACT.md` | planning_only / domain-specific | Low | Tool-intent bridge contract for creative tooling. It reinforces "proposal is not execution" but is not a multi-node report bridge. |

## Direct Answers

1. **Is Node Uplink already built under another name?**
   No. The exact Node Uplink concept is not built as a named system. The closest
   active implementation is Cross-Machine Read-Model Shuttle v0 plus Mac Mirror
   Atlas v0.

2. **Is there an existing bridge we should extend?**
   Yes. Extend the current read-model shuttle / manifest import path, backed by
   Corpus Atlas multi-root metadata. Do not extend the older SSH/rsync sync
   scripts or runtime broker/connector bridges.

3. **Is the read-model shuttle already enough for local Mac/PC?**
   Yes for canonical PC/WSL generated read-model exports moving to the Mac
   generated-read-model mirror, then importing a returned metadata manifest. It
   needs only a thin generalized package contract to support broader sanitized
   node/report packages.

4. **Is there an older bridge that should be marked legacy/superseded?**
   Yes. The `mac_eyes/Launchers/*sync*.sh`, `scripts/sync_project_packets_to_mac.sh`,
   and `sync_to_mobile.sh` SSH/rsync sync paths should be treated as legacy
   scaffolding for this purpose. Some use remote access and delete/watch behavior,
   so they are not the right base for Node Uplink v0.

5. **Does anything warn against building this now?**
   Yes: `CORE_ARCHITECTURE_PRINCIPLES.md` requires audit before adding, one
   canonical source per concern, and the lightest capable mechanism. The audit
   shows enough active machinery exists that a new transport/control plane would
   be premature. A narrow package/import extension is acceptable; a daemon,
   remote bridge, MCP memory layer, network service, or runtime broker is not.

## Current Best Extension Point

Recommended base:

- `read_model_shuttle.py`
- `mac_mirror_atlas.py`
- `scripts/build_root_manifest.py`
- `scripts/import_root_manifest.py`
- `scripts/query_corpus_atlas.py`
- Business Ops ledger `.openclaw/business_ops/ledger.sqlite`
- Corpus Atlas `corpus_*` root/path/mirror tables
- Evidence Kettle / Context Selection as downstream consumers only

Recommended shape:

- Keep E-drive as the explicit transfer/drop root.
- Keep manual/operator transfer as the transport for v0.
- Define a sanitized package contract for read-models and reports.
- Import package metadata and safe generated/read-model facts into existing
  atlas/evidence surfaces.
- Treat every package as evidence/context, not truth.
- Keep node authority separate from package visibility.

## Options Considered

1. **Extend Read-Model Shuttle into a report-package bridge.**
   - Pros: smallest change, uses proven E-drive package path, reuses manifest
     import and Corpus Atlas multi-root semantics.
   - Cons: current naming is Mac/read-model specific; needs generalized package
     type and node metadata.
   - Verdict: recommended.

2. **Create a separate Node Uplink system from scratch.**
   - Pros: clean naming and broader abstraction from day one.
   - Cons: duplicates shuttle/mirror/import machinery and risks creating a
     second state system.
   - Verdict: reject for v0.

3. **Revive older SSH/rsync bridge scripts.**
   - Pros: some historical PC-to-Mac workflow exists.
   - Cons: network/SSH/rsync, path assumptions, possible delete/watch behavior,
     and stale authority semantics.
   - Verdict: reject for this lane.

## Recommended Name

Use this lane name:

**Node Uplink / Report Bridge v0**

Implementation naming should lean toward **Report Bridge** for code/table
surfaces because the first useful unit is a sanitized report/read-model package,
not a live node control channel. "Node Uplink" can remain the operator-facing
product label.

Avoid names that imply remote control, runtime activation, or trust, such as
"node broker", "agent bridge", "remote connector", or "sync daemon".

## Risks

- Duplicating the existing shuttle/mirror path with a parallel bridge system.
- Treating package arrival as approval, freshness, or truth.
- Accidentally reviving SSH/rsync/delete/watch behavior from older scripts.
- Reintroducing C-drive transfer writes after the shuttle standard moved to E.
- Letting node identity imply trust or client-data authority.
- Importing raw private files instead of generated read-model/report metadata.
- Allowing old bridge docs to launder stale planning into implementation truth.
- Confusing live connector brokers with offline report/package import.

## Recommendation

Proceed with Node Uplink only as a narrow **Report Bridge v0**:

- no network
- no daemon
- no runtime activation
- no agent activation
- no tool execution
- no raw private data
- no C-drive transfer writes
- no truth promotion

The first build should generalize the current shuttle package schema and import
path enough to accept sanitized report/read-model packages from named nodes.
It should not replace Corpus Atlas, Evidence Kettle, Context Selection, Mac
Mirror Atlas, or Project Capsule.

## Next Exact Implementation Prompt

Use this next only after operator approval:

```text
You are working in /home/openclaw on PC/WSL.

Lane:
Node Uplink / Report Bridge v0 — Thin Package Contract on Existing Shuttle

Goal:
Extend the proven E-drive Read-Model Shuttle and Mac Mirror Atlas path into a
minimal sanitized node report package workflow.

Base to extend:
- read_model_shuttle.py
- mac_mirror_atlas.py
- scripts/build_root_manifest.py
- scripts/import_root_manifest.py
- scripts/query_corpus_atlas.py
- Corpus Atlas corpus_* tables in .openclaw/business_ops/ledger.sqlite

Do not create a new transport/control plane.
Do not use SSH/SCP/rsync/network.
Do not write to /mnt/c/openclaw.
Do not run Docker or Ollama.
Do not activate agents/runtime/tools.
Do not import raw private data.
Do not treat package arrival as truth, approval, or freshness by itself.

Required v0:
1. Define a node_report_package manifest schema with:
   - package_id
   - generated_at
   - source_node_id
   - source_root_id
   - owner_scope
   - package_kind
   - allowed_data_classes
   - denied_data_classes
   - file records with size/hash/path/category/sensitivity/retrieval/ingestion labels
   - no-authority flags
2. Add an E-drive default package/drop root under:
   - /mnt/e/openclaw/node_uplink/to_pc
   - /mnt/e/openclaw/node_uplink/from_nodes
3. Package only generated read-models/operator reports/safe metadata from explicit allowlisted roots.
4. Add import validation that rejects raw bodies, unknown roots, no-go labels, and unsupported package kinds.
5. Write imported package metadata into existing Business Ops ledger using a separated report-bridge namespace only if corpus_* cannot represent it cleanly.
6. Link safe imported files back to Corpus Atlas roots where possible.
7. Add reports:
   - summary
   - nodes
   - packages
   - blocked
   - freshness
   - authority
8. Add tests proving no network/SSH/SCP/rsync/subprocess shell=True, no C-drive defaults, no deletes/moves, no raw bodies, no authority flags true, and existing shuttle/mirror tests still pass.

Stop before implementation if this duplicates existing shuttle/mirror semantics
instead of extending them.
```

## Validation

Only documentation was added in this lane. Run:

```bash
git diff --check
```

No code tests are required unless source behavior changes.

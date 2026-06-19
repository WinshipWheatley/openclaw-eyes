# OpenClaw Work Terrain Query Contract v0

## ELIWINSHIP Summary

This contract gives OpenClaw a safe way to ask focused terrain questions before reading bodies or acting on anything. It looks for metadata first: SQLite rows, Atlas metadata, generated read-models, operator summaries, stable-map sections, receipts, scripts, tests, commits when already available, and validation artifacts.

It does not decide what is current, stale, superseded, or ready to promote yet. It defines the query grammar that later relationship and classification lanes can use.

## What It Can Ask Later

- `chief_related_work_terrain`: Show me all Chief-related OpenClaw terrain. (agent-map bindings: chief_related_work_terrain::chief; unresolved actors: none)
- `capital_hilton_related_work_terrain`: Show me everything related to Capital Hilton. (agent-map bindings: capital_hilton_related_work_terrain::cassandra, capital_hilton_related_work_terrain::guardian; unresolved actors: none)
- `security_pass_related_work_terrain`: Show me all Security Pass and authority-boundary terrain. (agent-map bindings: security_pass_related_work_terrain::guardian, security_pass_related_work_terrain::hermes, security_pass_related_work_terrain::chief; unresolved actors: none)
- `niles_struna_related_work_terrain`: Show me all Niles, Struna, music, art, plugin, synth, and Mac-port terrain. (agent-map bindings: niles_struna_related_work_terrain::niles; unresolved actors: Struna)
- `repo_b_planner_builder_related_work_terrain`: Show me Repo B, planner, builder, orchestrator, and legacy runtime terrain. (agent-map bindings: repo_b_planner_builder_related_work_terrain::chief; unresolved actors: Operator)

## Agent Map Wiring

- Query target actors are bound to `agent_lane_registry.py::DEFAULT_AGENT_LANE_SEEDS` as context only.
- Unknown target actors stay unresolved/fail-closed and grant no routing, runtime dispatch, or action authority.
- Binding count: `8`.

## Bounded Body-Ingest Successor

- Read model: `generated/read_models/openclaw_markdown_body_ingest_query.json`
- This contract remains metadata-only; body reads live in the separate repo-allowlisted, byte-capped, snippet-only B8 lane.

## Safety Policy

- Metadata first: `true`
- Body ingestion by default: `false`
- Semantic review by default: `false`
- Repo B policy: Repo B is reference-only unless explicitly approved by a later bounded lane.
- Stable map policy: Stable map is app-facing reflection, not source truth.

## Why This Matters

A file existing does not make it current. A Markdown note does not make it doctrine. A worker report does not prove completion. A stable-map section is app-facing truth, not source truth. Terrain queries find references; later receipt and classification lanes decide what those references mean.

## What Remains Blocked

- Broad raw Markdown bodies, broad private roots, Mac private home folders, PC C-drive surfaces, email bodies, Coupa/browser sessions, credential stores, raw finance/private bodies, file moves/deletes/renames, model/tool/agent/runtime execution, network, git push/pull/fetch, Mac sync/import, and Mission Control Swift changes.

## Next Batch Lane

- Work Terrain Relationship Index: connect terrain results across source notes, built artifacts, receipts, and stable-map sections without deciding staleness yet.

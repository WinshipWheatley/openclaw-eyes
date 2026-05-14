# OpenClaw Corpus Atlas v0.5

Corpus Atlas v0.5 records metadata/location classifications in the existing
Business Ops ledger under `corpus_*` tables.

Boundary:
- It records path metadata, labels, generated read-model links, freshness
  signals, world bindings, and advisory reorg buckets.
- It does not ingest arbitrary raw text.
- It does not read or hash no-go/sensitive file contents.
- It does not move, delete, rename, mirror, activate, deploy, or wire agents.
- It preserves `runtime_authority=false`.

Commands:
- Build atlas: `python3 scripts/build_corpus_atlas.py --format operator`
- Query report: `python3 scripts/query_corpus_atlas.py --report summary`

Initial root:
- `root_id`: `pc_wsl_home_openclaw`
- `host_kind`: `pc_wsl`
- `absolute_root`: `/home/openclaw`

The schema is prepared for later Mac mirror/root ids, but this lane does not
scan Mac paths.


# OpenClaw Corpus Atlas v0.6

Corpus Atlas v0.6 records metadata/location classifications in the existing
Business Ops ledger under `corpus_*` tables.

New v0.6 gates:
- `retrieval_eligibility` separates "exists" from "safe for agent retrieval".
- `ingestion_eligibility` separates metadata registration from future Evidence
  Kettle raw-body intake.
- `canonicality` separates canonical current contracts from ordinary tracked
  source, generated snapshots, operator notes, historical files, scratch, and
  no-go boundaries.

Boundary:
- Unknown paths default to blocked or operator-review-required.
- Source files are `tracked_source`, not automatic source-of-truth facts.
- Generated read models are eligible as generated snapshots/read-model facts.
- No-go and sensitive paths are registered without raw reads or content hashes.
- Reorg and mirror rows are advisory only.
- Future Mac, legacy GitHub, and client roots can be represented, but are not
  scanned or imported in this lane.
- `runtime_authority=false`; no activation, networking, broker wiring, file
  moves, deletes, renames, or app changes are authorized.

Commands:
- Build atlas: `python3 scripts/build_corpus_atlas.py --format operator --write-report`
- Query report: `python3 scripts/query_corpus_atlas.py --report summary`
- Retrieval gate: `python3 scripts/query_corpus_atlas.py --report retrieval`
- Ingestion gate: `python3 scripts/query_corpus_atlas.py --report ingestion`
- Unknown queue: `python3 scripts/query_corpus_atlas.py --report unknown-review`
- Root registry: `python3 scripts/query_corpus_atlas.py --report multi-root`

Initial root:
- `root_id`: `pc_wsl_home_openclaw`
- `root_kind`: `operating_home_repo`
- `host_kind`: `pc_wsl`
- `owner_scope`: `internal_platform`
- `absolute_root`: `/home/openclaw`


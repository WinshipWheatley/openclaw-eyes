# OpenClaw Evidence Kettle v0.1

Evidence Kettle v0.1 writes a bounded `evidence_*` namespace into the existing
Business Ops ledger at `.openclaw/business_ops/ledger.sqlite`.

## Boundary

- Uses Corpus Atlas v0.6 `ingestion_eligibility` labels as the source gate.
- Includes only `generated_snapshot_only`, `receipt_summary_only`, and safe
  `ingest_allowed` rows.
- Excludes `needs_review`, `no_go`, `metadata_only`, `not_for_ingestion`, and
  sensitive/no-go rows.
- Reads generated snapshot files only from `generated/read_models/` and
  `Operator/GENERATED_*`.
- Stores receipt metadata summaries only; receipt bodies are not ingested.
- Stores deterministic generated read-model facts as evidence, not truth.
- Does not create canonical facts, activate runtime behavior, call networks,
  move files, or change Mission Control.

## Tables

- `evidence_ingestion_runs`
- `evidence_sources`
- `evidence_items`
- `evidence_item_labels`
- `evidence_world_bindings`
- `evidence_source_links`
- `read_model_snapshots`

## Commands

```bash
python3 scripts/build_evidence_kettle.py --plan-only --format operator
python3 scripts/build_evidence_kettle.py --format operator
python3 scripts/query_evidence_kettle.py --report summary --format operator
python3 scripts/query_evidence_kettle.py --report read-models --format operator
python3 scripts/query_evidence_kettle.py --report runtime-gate --format operator
python3 scripts/query_evidence_kettle.py --report future-gated --format operator
python3 scripts/query_evidence_kettle.py --report world --world build --format operator
```

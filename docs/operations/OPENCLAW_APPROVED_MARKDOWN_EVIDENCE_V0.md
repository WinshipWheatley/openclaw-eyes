# OpenClaw Approved Markdown Evidence v0

Status: implemented backend substrate.

Approved Markdown Evidence is the first safe body-light ingestion path for Markdown docs. It reads only docs already marked safe by Markdown Knowledge Atlas or a tiny explicit current-doc allowlist, then stores bounded headings/excerpts as parsed evidence.

## Source Policy

Eligible:

- `retrieval_policy=agent_retrievable`
- `sensitivity_status=normal_internal`
- or explicit current-doc allowlist in `markdown_evidence_ingestion.py`

Skipped:

- `needs_operator_review`
- `metadata_only`
- `blocked_no_go`
- `sensitive_metadata_only`
- `no_go`
- `unknown_review`

## Tables

- `markdown_evidence_runs`
- `markdown_evidence_sources`
- `markdown_evidence_items`
- `markdown_evidence_query_receipts`

## Generated Surfaces

- `generated/read_models/markdown_evidence.json`
- `generated/read_models/markdown_evidence_OPERATOR.md`

## Commands

Ingest:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/ingest_approved_markdown_evidence.py --format operator
```

Query:

```bash
python3 scripts/query_markdown_evidence.py --report summary --format operator
python3 scripts/query_markdown_evidence.py --report sources --format operator
python3 scripts/query_markdown_evidence.py --query "Mission Control" --format operator
```

Export:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/export_markdown_evidence_read_model.py --format operator
```

## Boundary

- Stores bounded headings/excerpts only, not full raw document bodies.
- Every item is `parsed_evidence_not_truth`.
- No embeddings or vector search.
- No model calls.
- No truth promotion.
- No private/no-go raw reads.
- No runtime, tool, network, file move, or file delete authority.

# OpenClaw Markdown Knowledge Atlas v0

Markdown Knowledge Atlas v0 adds a corpus-linked document role overlay in the
existing Business Ops ledger.

It is not a filesystem scanner and not a broad Markdown ingestion system. It
uses existing Corpus Atlas rows as the source path inventory and writes
document-specific classification rows under a separate `markdown_*` namespace.

## Tables

- `markdown_atlas_runs`
- `markdown_documents`
- `markdown_document_classifications`
- `markdown_document_links`
- `markdown_document_reorg_candidates`
- `markdown_document_supersession`
- `markdown_document_query_receipts`

## Classification Axes

Each Markdown document receives one value from each independent axis:

- `document_role`
- `freshness_status`
- `reorg_status`
- `sensitivity_status`
- `retrieval_policy`

The axes are intentionally separate. A document can be, for example,
`operation_doc + current + keep_current + sensitive_metadata_only + metadata_only`.

## Boundary

- Links back to `corpus_paths` where possible.
- Does not read or store full Markdown bodies.
- Does not read no-go/private Markdown raw.
- Does not scan all drives.
- Does not move, delete, rename, archive, or reorganize files.
- Reorg/archive rows are advisory only.
- Does not promote Markdown prose into truth.
- Does not activate agents, runtime, tools, Docker, Ollama, network, or Mission Control.

## Commands

```bash
python3 scripts/build_markdown_knowledge_atlas.py --format operator
python3 scripts/query_markdown_knowledge_atlas.py --report summary --format operator
python3 scripts/query_markdown_knowledge_atlas.py --report current --format operator
python3 scripts/query_markdown_knowledge_atlas.py --report stale --format operator
python3 scripts/query_markdown_knowledge_atlas.py --report handoffs --format operator
python3 scripts/query_markdown_knowledge_atlas.py --report canonical --format operator
python3 scripts/query_markdown_knowledge_atlas.py --report generated-status --format operator
python3 scripts/query_markdown_knowledge_atlas.py --report archive-candidates --format operator
python3 scripts/query_markdown_knowledge_atlas.py --report no-go --format operator
python3 scripts/query_markdown_knowledge_atlas.py --report agent-retrievable --format operator
```

## Future File Atlas Readiness

This is the first narrow Markdown/docs slice of a broader future OpenClaw File
Atlas. The schema preserves root metadata from Corpus Atlas so later lanes can
represent external drives, Mac mirrors, video/music drives, archive drives,
client project roots, client runtime roots, and no-go/private roots.

Those future-root hooks do not authorize broad drive scans or agent retrieval.

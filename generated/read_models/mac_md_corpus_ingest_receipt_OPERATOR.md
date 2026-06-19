# Mac Markdown Corpus Ingest Receipt

Status:
- Receipt status: `mac_orchestration_markdown_corpus_ingested`.
- Root indexed: `/Volumes/openclaw_e/orchestration`.
- SQLite artifact: `generated/system_knowledge/mac_md_corpus.sqlite`.
- SQLite size: `8536064` bytes.
- Markdown files scanned: `2246`.
- Documents ingested: `2246`.
- Paths excluded before body read: `8`.
- Sensitive path rows in documents by path hint: `0`.

Safety:
- Legal/Finance/MusicLaw exclusion enforced: `true`.
- Runtime/tool/model/network authority: `false`.
- File move/delete authority: `false`.
- Truth promotion: `false`.

Verification:
- `python3 -m pytest tests/test_md_corpus_ingest.py -q` => `6 passed in 0.37s`.
- `python3 -m py_compile md_corpus_ingest.py scripts/md_corpus_ingest.py` => OK.
- Real ingest command completed with `ingested_document_count=2246` and `excluded_path_count=8`.
- SQLite probe counted `md_corpus_runs=1`, `md_corpus_documents=2246`, `md_corpus_exclusions=8`.

Commit policy:
- The generated SQLite contains full allowed Markdown body text and is preserved as a local worktree artifact rather than committed.
- This branch commits the ingester, tests, wrapper, and receipt.

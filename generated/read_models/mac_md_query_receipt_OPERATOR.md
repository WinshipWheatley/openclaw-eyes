# Mac Markdown Query Receipt

Status:
- Receipt status: `mac_orchestration_markdown_query_completed`.
- Query: `send hold bypass`.
- Query ID: `mac_md_query_send_hold_bypass_20260618T2254`.
- Source corpus run: `mac_md_corpus_orchestration_20260618T2247`.
- Staleness run: `mac_md_staleness_orchestration_20260618T2251`.
- Result count: `5`.

Top results:
- `inbox/to-claude/CLAUDE-OPUS-AUDIT-CLAIM-V0-sendhold-bypass.md`: score `49`, staleness `done_or_superseded`.
- `inbox/to-claude/GEMINI-FINDING-pc-URGENT-L2-SEND-BYPASS.md`: score `39`, staleness `current_recent`.
- `inbox/to-claude/0025-sendhold-convergence-report.md`: score `36`, staleness `current_recent`.
- `inbox/to-claude/CROSS-LANE-C-to-B-exact-send-routeback-sendhold.md`: score `36`, staleness `current_recent`.
- `inbox/to-codex-B/B5-GROUNDED-unify-sendhold-filecheck.md`: score `36`, staleness `current_recent`.

Safety:
- Model calls: `false`.
- Vector search: `false`.
- Truth claimed: `false`.
- Runtime/tool/network authority: `false`.
- File move/delete authority: `false`.
- Legal/Finance/MusicLaw access remains denied by the source corpus exclusions.

Verification:
- `python3 -m pytest tests/test_md_corpus_ingest.py tests/test_md_staleness.py tests/test_md_query.py -q` => `18 passed in 1.29s`.
- Real query command completed and stored `md_query_receipts` row `mac_md_query_send_hold_bypass_20260618T2254`.

# Mac Markdown Staleness Receipt

Status:
- Receipt status: `mac_orchestration_markdown_staleness_classified`.
- Source corpus run: `mac_md_corpus_orchestration_20260618T2247`.
- Staleness run: `mac_md_staleness_orchestration_20260618T2251`.
- Documents classified: `2246`.
- Fresh window: `7.0` days.
- Stale threshold: `30.0` days.

Counts:
- `active_with_open_tasks`: `6`.
- `current_recent`: `1702`.
- `done_or_superseded`: `538`.

Examples with open work signals:
- `INTEGRATION_MAP.md`: open tasks `15`, TODO markers `0`.
- `MASTER_TODO.md`: open tasks `0`, TODO markers `1`.
- `artifacts/GOLIVE_RESULT.md`: open tasks `0`, TODO markers `1`.
- `inbox/to-codex-E/BRIEF_SENDGUARD_CARVEOUT_PACKET.md`: open tasks `7`, TODO markers `0`.

Safety:
- Advisory only: `true`.
- Runtime/tool/model/network authority: `false`.
- File move/delete/archive authority: `false`.
- Truth promotion: `false`.
- Legal/Finance/MusicLaw access remains denied by the source corpus exclusions.

Verification:
- `python3 -m pytest tests/test_md_staleness.py -q` => `6 passed in 0.60s`.
- Real staleness command completed over `2246` documents.
- SQLite probe counted `md_staleness_runs=1` and `md_staleness_documents=2246`.

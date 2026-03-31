title: auto-105-dashboard-accuracy-audit
goal: Audit and fix the dashboard generator to ensure all displayed information matches actual loop state. Eliminate stale or misleading signals.
scope:
- Review loop_dashboard_gen.sh for any remaining stale-signal patterns
- Verify "What Happened" event log correctly reflects actual orchestrator.log transitions
- Verify "Right Now" section accurately reflects current status.json
- Ensure event deduplication is working (no repeated identical events)
- Ensure timestamps are chronologically ordered within each run section
- Do not refactor the dashboard — only fix accuracy issues found
success condition:
- Regenerated dashboard matches current orchestrator state
- No duplicate events in the same time window
- Events are in correct chronological order
- "Smart Copilot Tip" correctly classifies all current issues
blockers/dependencies:
- Requires access to orchestrator.log and status.json
exact files likely to be touched first:
- mac_eyes/loop_dashboard_gen.sh
verification:
```bash
cd /home/openclaw && bash /home/openclaw/mac_eyes/loop_dashboard_gen.sh >/dev/null 2>&1 & sleep 2; pkill -f 'loop_dashboard_gen.sh' 2>/dev/null; cat /home/openclaw/mac_eyes/For\ Winship\ 2\ -\ What\ Happened.md | head -30
```

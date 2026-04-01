title: sys-002-token-usage-monitor
goal: Implement per-agent token usage monitor with limit-bust alerts.

Description:
Build a lightweight monitor that records model token usage by agent and time window, then emits warnings or hard stops when configured budgets are exceeded.

Verification:
- Monitor logs token usage entries with agent id, model, and timestamp.
- Threshold breach triggers an alert event with actionable metadata.
- Daily aggregate report can be generated from monitor logs.

title: sys-003-automation-roi-audit
profile: standard
goal: Have Chief analyze archive history and estimate total admin hours offloaded by the loop across the last 393 completed tasks.
scope:
- Scan /home/openclaw/polish_loop/archive for completed task artifacts and classify task types (ops, finance, communication, planning, docs).
- Estimate per-task manual time saved using bounded heuristics by class (low/med/high effort buckets).
- Generate a markdown report with totals: tasks analyzed, estimated minutes saved, estimated hours saved, and top 10 highest-ROI task categories.
- Include confidence notes and assumptions so estimates are auditable and adjustable.
- Save report to /mnt/c/OpenClawShared/openclaw-vault/System/Automation ROI Audit.md.
success:
- Report exists with reproducible calculation method and total hours-saved estimate.
- Report includes category breakdown and confidence/assumption section.
verification: |
  test -f "/mnt/c/OpenClawShared/openclaw-vault/System/Automation ROI Audit.md" && echo "roi-audit-ready"

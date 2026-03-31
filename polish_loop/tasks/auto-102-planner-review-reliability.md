title: auto-102-planner-review-reliability
goal: Improve planner review reliability so mac_review.md is produced before timeout.
scope:
- Analyze current loop behavior and logs for this issue.
- Implement minimal durable fix in the relevant loop scripts.
- Add a regression guard or test to prevent recurrence.
success condition:
- The recurring signal is reduced to zero across recent runs.
- A clear verification step is documented in pc_output.
blockers/dependencies:
- Coordinate with existing loop state machine and approval policy rules.
exact files likely to be touched first:
- polish_loop/orchestrator.py
- builder_watcher.sh
- mac_eyes/loop_dashboard_gen.sh

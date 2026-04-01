title: cleanup-stale-imports
profile: quick
goal: Remove unused imports from production Python files
scope:
- Scan chief_*.py and cassandra_*.py files for unused imports
- Remove imports that are not referenced in the file body
- Do not touch imports guarded by try/except or TYPE_CHECKING blocks
success:
- All modified files still import correctly and pass syntax check
generated_by: queue_balancer
generated_at: 2026-03-31T20:56:05.014646

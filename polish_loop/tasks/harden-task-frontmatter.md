title: harden-task-frontmatter
profile: quick
goal: Add frontmatter validation when tasks are loaded by orchestrator
scope:
- In orchestrator.py handle_idle(), validate promoted task has title: and goal: fields
- Log a warning and skip invalid tasks instead of promoting them
- Write a brief skip reason to the log
success:
- Orchestrator skips malformed tasks with a log message instead of crashing
generated_by: queue_balancer
generated_at: 2026-03-31T20:56:05.004108

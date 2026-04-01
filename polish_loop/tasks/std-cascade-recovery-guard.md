title: std-cascade-recovery-guard
profile: standard
goal: Add a cascade guard to _queue_manus_recovery_task in orchestrator.py to prevent infinite self-heal loops when recovery tasks themselves time out.

problem:
  When a task fails with builder_timeout_after_retry, orchestrator.py calls
  _queue_manus_recovery_task which queues a new auto-gen-NNN-manus-recovery task.
  If THAT recovery task also times out, another recovery task is queued, creating
  an infinite cascade: auto-gen-001 -> 002 -> 003 -> 004 -> 005 -> ...
  Confirmed in archive: 5 consecutive recovery tasks all failed builder_timeout.

scope:
- File: /home/openclaw/polish_loop/orchestrator.py
- Function: _queue_manus_recovery_task (line ~714)
- Change: Add early-return guard after the _TEST_DISABLE_SELF_HEAL_TASKS check.
  If failed_task matches "manus-recovery" or "auto-gen-\d+" pattern, skip queuing
  and log a WARN instead. This breaks the cascade at the first recovery failure.

implementation:
  In _queue_manus_recovery_task, after line 717 (after the _TEST_DISABLE check),
  add:

    import re  # already imported at top of file

    # Guard: never queue a recovery task for a task that is itself a recovery task
    if "manus-recovery" in failed_task or re.match(r"auto-gen-\d+", failed_task):
        log("WARN", f"Skipping self-heal for '{failed_task}' — already a recovery task; cascading would create infinite loop")
        return None

  The re module is already imported at the top of orchestrator.py so no new import needed.

success:
- _queue_manus_recovery_task returns None (without creating a file) when called
  for any task whose name contains "manus-recovery" or matches auto-gen-NNN.
- Existing unit tests still pass: python3 /home/openclaw/polish_loop/orchestrator.py --run-tests
- No new auto-gen recovery tasks appear in tasks/ after a recovery task times out.

verification:
  1. Run existing tests:
       cd /home/openclaw && source ~/chief_env/bin/activate
       python3 polish_loop/orchestrator.py --run-tests
     Expected: all tests pass (look for "All N tests passed")
  2. Manual spot-check of guard logic:
       python3 -c "
       import sys; sys.path.insert(0, '/home/openclaw/polish_loop')
       import orchestrator as o
       # Simulate: failing task is already a recovery task
       result = o._queue_manus_recovery_task('auto-gen-005-manus-recovery', 'builder_timeout_after_retry')
       print('Guard works (returned None):', result is None)
       "
     Expected: Guard works (returned None): True

rollback:
  If the guard causes problems, revert by removing the 4-line block added after
  the _TEST_DISABLE_SELF_HEAL_TASKS check. The function signature and all other
  behavior are unchanged. No data migration required.

priority: high
queued_by: auto-gen-005-manus-recovery pass 1
queued_at: 2026-04-01

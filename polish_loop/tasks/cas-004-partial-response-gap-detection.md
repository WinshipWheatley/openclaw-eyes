title: cas-004-partial-response-gap-detection
goal: When Cassandra receives a message she can only partially answer, she responds to what she can immediately, identifies the capability gaps, auto-generates a polish loop task to build the missing capability, and queues a follow-up so she can give a complete answer once upgraded.
scope:
- Add gap detection to cassandra_brain.py response flow:
  - After generating a reply via LLM, check if the reply contains hedging language ("I can't", "I don't have access", "I'm not able to", "that's beyond my current", "I'll need to check", etc.)
  - Also check cassandra_capability.py flags — if the user's request touches a capability where CONNECTED=False, that's a known gap
  - Classify each gap: what capability is missing (email_send, payment_verify, file_verify, future_action, sms, etc.)
- Implement partial response behavior:
  - Send the partial answer immediately via Telegram (what Cassandra CAN answer)
  - Append a natural line like: "I can't fully answer the rest right now, but I'm working on getting that capability. I'll follow up when I can."
  - Do NOT say "I'll ask Winship" or expose internal system details
- Auto-generate upgrade task:
  - Write a .md task file to /home/openclaw/polish_loop/tasks/ with:
    - title: cas-upgrade-{capability}-{timestamp}
    - goal: description of what capability is needed based on what the user asked
    - scope: inferred from the gap type and the original message
    - success: the capability flag becomes True or the specific action works
  - Only generate ONE task per capability gap (deduplicate — check if a cas-upgrade-{capability} task already exists in tasks/ or is currently running)
- Queue a follow-up:
  - Write to /mnt/c/OpenClaw/logs/cassandra_pending_followups.jsonl with:
    - timestamp, sender_name, original_message, partial_reply_sent, gap_type, upgrade_task_name, status: "pending"
  - When the upgrade task completes (detected by checking archive/ for the task name), Cassandra should:
    - Re-process the original message with the new capability
    - Send the follow-up response via Telegram
    - Update the followup record status to "completed"
- Add a follow-up checker that runs on each orchestrator idle transition or on a simple cron:
  - Scans cassandra_pending_followups.jsonl for status=pending
  - Checks archive/ for matching upgrade task completions
  - Triggers re-processing and follow-up send
- This behavior applies ONLY to messages from contacts in /home/openclaw/contact_nicknames.json (Draper, Dad, Mom for now) — identified by Telegram chat_id or sender name
  - Unknown senders or Winship himself get normal Cassandra behavior (no auto-upgrade)
success:
- Cassandra sends partial responses immediately when she can answer part of a question
- Gap detection identifies missing capabilities from both LLM hedging and capability flags
- Upgrade tasks auto-generated in polish_loop/tasks/ with deduplication
- Pending followups logged to cassandra_pending_followups.jsonl
- Follow-up checker re-processes and sends complete answer when upgrade is done
- Only active for designated contacts (contact_nicknames.json)
verification: |
  python3 -c "from cassandra_brain import detect_capability_gaps; print('gap detection importable')"
  test -f /mnt/c/OpenClaw/logs/cassandra_pending_followups.jsonl || echo 'followup log will be created on first use'
  ls /home/openclaw/polish_loop/tasks/cas-upgrade-* 2>/dev/null; echo 'checked for upgrade tasks'
depends_on: cas-002-email-send-capability
notes: |
  This is the core intelligence loop: Cassandra self-improves by detecting her own gaps and queuing upgrades.
  The follow-up checker should be lightweight — scan a small JSONL file, check archive/ for filenames.
  Do NOT auto-generate tasks for capabilities that require manual setup (OAuth scopes, API keys, etc.) — instead log those as "manual_required" in the followup record and notify Winship via Telegram.
  Keep the auto-generated task specs simple and conservative. Better to under-scope than over-scope.

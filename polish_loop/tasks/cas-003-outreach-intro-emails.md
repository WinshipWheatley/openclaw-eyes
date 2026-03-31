title: cas-003-outreach-intro-emails
goal: Build a one-time outreach flow where Cassandra introduces herself to Draper, Dad, and Mom via email with personalized context per recipient.
scope:
- Create /home/openclaw/cassandra_outreach.py — a standalone script that Cassandra can be told to run (or that can be triggered via Telegram command)
- The script reads contact_nicknames.json to resolve recipients to email addresses
- For each recipient, compose a personalized intro email:
  - FROM: Cassandra (via Winship's Gmail)
  - SUBJECT: something natural like "Hey [name] — an intro from Cassandra"
  - BODY: Introduce herself as Winship's AI assistant, explain the objective (helping test and improve the system), ask them to reply with questions/comments/concerns
  - For DAD: mention that financial questions are welcome (he can ask about invoices, payments, etc.)
  - For DRAPER: mention that work-related stuff is welcome (projects, scheduling, etc.)
  - For MOM: keep it warm and general
- Each email send goes through the existing email send pipeline (cas-002) with L2 Guardian approval per send
- After sending, Cassandra messages Winship on Telegram confirming what was sent and to whom
- Log all outreach sends to /mnt/c/OpenClaw/logs/cassandra_outreach.jsonl with timestamp, recipient, subject, status
- Do NOT hardcode any email addresses or real names in the script — read from contact_nicknames.json
- Include a --dry-run flag that shows what WOULD be sent without actually sending
success:
- cassandra_outreach.py exists and is runnable
- --dry-run shows 3 personalized emails without sending
- Each real send triggers L2 Guardian approval
- Telegram confirmation sent to Winship after each email
- Outreach log written to cassandra_outreach.jsonl
- Cassandra can be told "send the intro emails" via Telegram and it triggers the flow
verification: |
  python3 /home/openclaw/cassandra_outreach.py --dry-run 2>&1 | head -30
  test -f /home/openclaw/cassandra_outreach.py && echo 'script exists'
depends_on: cas-002-email-send-capability
notes: |
  This task depends on cas-002 (email send capability) being complete first.
  The builder should check that EMAIL_SEND_CONNECTED = True before implementing.
  If cas-002 is not done yet, write STATUS: BLOCKED in pc_output.md.
  PLACEHOLDER NAMES ONLY in code. Winship fills in contact_nicknames.json manually.

title: cas-002-email-send-capability
goal: Build the email send pipeline so Cassandra can compose and send emails through Gmail, with L2 Guardian approval for each send.
scope:
- Implement _exec_gmail_send() in google_access_broker.py — accepts to, subject, body (plain text), sends via Gmail API using the existing OAuth token
- The gmail.compose scope (https://www.googleapis.com/auth/gmail.compose) must be added to the broker's active scopes and the token refreshed to include it
- google_access_policy.py already has google.gmail.send as CLASS_C (L2) — keep this, every email send requires phone approval via Guardian
- Add a send_email(to, subject, body) handler in cassandra_brain.py that: (a) resolves recipient name to email via google_access_broker contacts lookup, (b) calls the broker to send, (c) confirms to user via Telegram
- Update cassandra_capability.py: EMAIL_SEND_CONNECTED = True
- Add nickname resolution: create a simple mapping file /home/openclaw/contact_nicknames.json with entries like {"dad": "real name", "mom": "real name", "draper": "real name"} — Cassandra checks this FIRST, then falls through to Google Contacts search
- Do NOT bypass the L2 approval gate. Every email send must go through Guardian.
- Handle case where recipient email can't be resolved: Cassandra should ask user to clarify
success:
- _exec_gmail_send() works in google_access_broker.py
- Cassandra can resolve "dad", "mom", "draper" to email addresses
- Email send goes through L2 Guardian approval
- EMAIL_SEND_CONNECTED = True in cassandra_capability.py
- contact_nicknames.json exists with placeholder entries (Winship fills in real names)
verification: |
  python3 -c "from google_access_broker import call; print('broker import ok')"
  grep -q 'EMAIL_SEND_CONNECTED = True' /home/openclaw/cassandra_capability.py && echo 'flag set'
  test -f /home/openclaw/contact_nicknames.json && echo 'nicknames file exists'
notes: |
  IMPORTANT: The Gmail OAuth token must be refreshed with the gmail.compose scope.
  This may require a one-time manual OAuth consent flow in a browser.
  The builder should document exactly what manual step is needed if the token refresh fails.
  Do NOT store any email addresses, real names, or PII in this task file or in code — use placeholders.

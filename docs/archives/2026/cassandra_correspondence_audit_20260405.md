# Cassandra Correspondence Audit — 2026-04-05

## Sources

- Primary conversation history: `/mnt/c/OpenClaw/logs/cassandra_conversations.jsonl`
- Pending follow-ups: `/mnt/c/OpenClaw/logs/cassandra_pending_followups.jsonl`
- Broker audit: `/mnt/c/OpenClaw/logs/google_access_audit.jsonl`

## What I found

- Total recorded Cassandra exchanges: `1546`
- Hedged/problematic replies detected by audit heuristic: `697`
- Dominant live failure class: payment questions falling through to `route=llm`
- Dominant concrete regression: payment questions sometimes receiving file/path verification replies

## Evidence counts

- `payment_query_hedged_via_llm`: `490`
- `payment_query_got_file_verify_reply`: `54`

## Recent concrete examples

1. `2026-04-04 22:50:06`
   User: `Did the Hilton payment come through?`
   Reply: `I can't verify file or path existence from here. That's a direct check on your end.`

2. `2026-04-04 22:47:26`
   User: `Did the Hilton payment come through?`
   Reply: `I can't verify deposit or payment status — no external access. What I have is the log entry. The account is the source of truth.`

3. `2026-04-05 01:12:00`
   User: `Did the Hilton payment come through?`
   Reply: `I can't verify that path. That's a direct check on your end.`

4. `2026-04-05 01:11:47`
   User: `Did the Hilton payment come through?`
   Reply: `I don't have that confirmed. Let me check for any follow-up emails or messages from Capital Hilton to see if there's any update.`

## Interpretation

- The most urgent cleanup is not rewriting old logs. The urgent cleanup is fixing the routing and reply-generation path that produced these bad replies.
- The payment-verification path exists in code, but the running Cassandra process was still producing `route=llm` responses. That makes restart + regression testing mandatory.
- Existing gap-task machinery is already useful for chat interactions, but email reply handling still needs a dedicated bridge and grounded review layer before inner-circle correspondence should be trusted.

## Actions taken in this pass

- Switched Cassandra email flow to brokered Gmail draft creation for review instead of direct send.
- Set review CC target to `winshiplive@gmail.com`.
- Added a focused regression test for payment routing and draft-intent routing.
- Queued follow-on tasks to clean up the correspondence failures and finish the safe email-reply path.

## Note

- I did not rewrite or delete historical conversation logs. They remain the source-of-truth record.

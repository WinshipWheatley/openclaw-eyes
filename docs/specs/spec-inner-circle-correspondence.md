# Inner-Circle Correspondence

This spec records the current known-good Cassandra email-ops behavior for inner-circle correspondence.

## Guaranteed Now

- Cassandra polls inbound Gmail reply metadata and reads grounded body text before composing a reply.
- Inbound replies from verified inner-circle contacts are processed at most once per message id.
- Auto-replies stay in the original Gmail thread by carrying thread and reply headers through draft and send.
- Relay-style encouragement messages preserve speaker, target, and destination-channel meaning.
- Relay-style Telegram operator updates stay short and grounded.
- Email replies remain review-grounded, draft first, and send only after Guardian approval.

## Relay-Style Operator Update

For structured relay notes such as "Let Winship know..." plus encouragement about Cassandra's progress:

- Telegram should send a short operator update, not a raw email dump.
- The update should preserve who said what about whom.
- Subject lines, preview dumps, and extra metadata should stay out of the relay update.

Current target shape:

- `Winship says he's pumped about my progress.`
- `Reply draft: ...`
- `Guardian approval is on the way.`

## Reply Composition Boundary

- Use deterministic relay composition only for clearly structured relay directives where semantic drift risk is high.
- Use the open-ended local-model composition path for simple conversational acknowledgments, thanks, scheduling, and other low-risk replies.
- In both paths, do not blur email-originated content into Telegram-originated content unless the inbound message explicitly requests Telegram as the follow-up channel.

## Key Files

- [`cassandra_brain.py`](/home/openclaw/cassandra_brain.py)
- [`cassandra_outreach.py`](/home/openclaw/cassandra_outreach.py)
- [`google_access_broker.py`](/home/openclaw/google_access_broker.py)

## Key Tests

- [`tests/test_cassandra_outreach.py`](/home/openclaw/tests/test_cassandra_outreach.py)
  - `test_process_inbound_email_replies_preserves_email_relay_meaning_for_winship`
  - `test_process_inbound_email_replies_preserves_explicit_telegram_destination`
  - `test_process_inbound_email_replies_uses_open_ended_model_path_for_simple_conversational_reply`
  - `test_process_inbound_email_replies_is_idempotent_across_repeat_polls`
- [`tests/test_send_truth.py`](/home/openclaw/tests/test_send_truth.py)
  - background draft/send approval coverage

## Regression Check

If later work changes this lane, re-run the narrow inbound correspondence tests before trusting live behavior.

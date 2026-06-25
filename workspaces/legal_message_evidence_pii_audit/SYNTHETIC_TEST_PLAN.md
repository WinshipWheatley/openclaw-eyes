# Synthetic Test Plan

To build the Legal Evidence ingestion and PII tiering system, we must develop a synthetic test corpus that mimics real-world legal complexities without risking actual PII exposure.

## Corpus Requirements
The synthetic SQLite database (`synthetic_sms.db`) must contain:
1. **Two Numbers, One Person:** `Person_A` uses `555-0101` from Jan to March, and `555-0199` from March to June.
2. **Interleaved Threads:** Some group chats include both of Person_A's numbers. Some 1:1 threads exist.
3. **Missing Timestamps:** Some messages lack precise UTC timestamps (simulating older SMS logs or carrier exports).
4. **Timezone Shifts:** Messages sent before and after DST changes, and from different logical timezones.
5. **Edited/Deleted Messages:** Simulating iMessage features (e.g., `edit_status=edited`).
6. **Attachments:** References to `.jpeg` files that must remain linked to the specific message.
7. **Ambiguous Identity:** A third number `555-0000` where it is unclear if it belongs to Person_A or a new `Person_C`.

## Evaluation Plan
- **Tokenization Stability:** Verify that `555-0101` consistently maps to `[PHONE_A1]` and `555-0199` maps to `[PHONE_A2]`, but both can be queried under `[PERSON_A]`.
- **Search Completeness:** Query "promises" and verify the LLM identifies the synthetic tokenized message, but the system returns the EXACT original string and correct hashes.
- **Detokenization Audit:** Verify that requesting a detokenized attorney view drops a permanent audit log entry and successfully rehydrates the exact original names.

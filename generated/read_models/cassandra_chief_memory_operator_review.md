# Cassandra/Chief Memory Operator Review Packet v0

Plain-English status:
- We found old Cassandra/Chief memory sources by name and category only.
- No raw data was imported.
- Old files are not truth.
- Cassandra/Chief cannot use these as authority yet.
- Next step is only an operator-approved structured import plan.

## 1. Safe to structure later
- allowed email recipients / email permission posture: allowed-recipient and email-thread posture refs (`import_structured_facts_to_sqlite`, risk=high)
- company/contact relationships: business contact relationship refs (`import_structured_facts_to_sqlite`, risk=medium)
- contacts and nicknames: contact nicknames and contact list refs (`import_structured_facts_to_sqlite`, risk=medium)
- invoice facts: finance state and billing record refs (`import_structured_facts_to_sqlite`, risk=high)
- receivable/payment tracking: invoice tracker and payment status refs (`import_structured_facts_to_sqlite`, risk=high)

## 2. Keep as evidence source only
- Cassandra notes: Cassandra reality notes ref (`summarize_or_extract_only`, risk=medium)
- Chief session/task memory: Chief session, queue, and route refs (`register_as_evidence_source_only`, risk=medium)
- Windows-side logs: Windows-side Cassandra/Chief runtime log refs (`register_as_evidence_source_only`, risk=high)
- billing tracker CSV/PDF paths: billing tracker CSV and PDF refs (`summarize_or_extract_only`, risk=high)
- calendar/event notes metadata: calendar and scheduler note refs (`summarize_or_extract_only`, risk=medium)
- correspondence metadata: conversation, correspondence, email, call, and SMS refs (`summarize_or_extract_only`, risk=high)

## 3. Block / do not trust
- old HITL JSON/JSONL state: legacy HITL approval JSON/JSONL refs (`block_no_go`, risk=critical)

## 4. Delete local residue candidate
- untracked polish_loop Cassandra failure tasks: two untracked Cassandra failure task prompts (`delete_local_residue`, risk=low)

## 5. Needs operator decision
- album/song progress state: album work, content, and scheduler refs (`defer_operator_review`, risk=medium)
- dirty generated agent_presence snapshots: dirty generated agent_presence read-model snapshots (`defer_operator_review`, risk=medium)

Safe next move:
- Review these buckets, then approve only the structured categories that should get a later import lane.

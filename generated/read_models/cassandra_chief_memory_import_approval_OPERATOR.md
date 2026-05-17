# Cassandra/Chief Memory Import Approval Receipt v0

Plain-English status:
- The operator approved category fates for the next bounded import lane.
- No data was imported.
- No raw content was read.
- Old files are not truth.
- Runtime authority did not change.

## Approved for later structured import
- contacts and nicknames: `approved_for_later_bounded_structured_import`; later import now=`false`.
- company/contact relationships: `approved_for_later_bounded_structured_import`; later import now=`false`.
- allowed email recipients / email permission posture: `approved_for_later_bounded_structured_import`; later import now=`false`.
- invoice facts: `approved_for_later_bounded_structured_import`; later import now=`false`.
- receivable/payment tracking: `approved_for_later_bounded_structured_import`; later import now=`false`.

## Evidence-source-only
- Chief session/task memory: `approved_evidence_source_only`; later import now=`false`.
- Windows-side logs: `approved_evidence_source_only`; later import now=`false`.

## Summarize/extract-only
- Cassandra notes: `approved_summarize_or_extract_only`; later import now=`false`.
- correspondence metadata: `approved_summarize_or_extract_only`; later import now=`false`.
- calendar/event notes metadata: `approved_summarize_or_extract_only`; later import now=`false`.
- billing tracker CSV/PDF paths: `approved_summarize_or_extract_only`; later import now=`false`.

## Reconcile-first / not imported
- old HITL JSON/JSONL state: `not_approved_for_import_reconcile_first`; later import now=`false`.

## Cleanup later only
- untracked polish_loop Cassandra failure tasks: `approved_cleanup_candidate_later_only`; later import now=`false`.

## Deferred
- album/song progress state: `deferred_not_approved_for_cassandra_chief_import`; later import now=`false`.
- dirty generated agent_presence snapshots: `deferred_not_approved_for_cassandra_chief_import`; later import now=`false`.

## What did not happen
- No legacy file bodies were opened or imported.
- Old HITL JSON/JSONL was not imported.
- Agent presence snapshots were not treated as truth.
- Cleanup candidates were not deleted.
- No send or runtime authority was granted.

## Next safe move
- HITL proof satisfied: `true`.
- Structured fact import safe now: `true`.
- Next lane: Cassandra/Chief Structured Fact Import v0.

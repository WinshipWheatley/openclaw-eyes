# Cassandra/Chief Structured Import Plan v0

Plain-English status:
- This is a decision packet, not an import.
- No raw data was read or imported.
- Old files are not truth.
- Cassandra/Chief cannot use these sources as authority yet.
- Approve categories only if you want a later bounded import/extraction lane.

## 1. Safe to import structured facts later
### allowed email recipients / email permission posture
- What it is: allowed-recipient and email-thread posture refs.
- Why it matters: Send permission posture must be governed and cannot come from old files alone.
- Recommended fate: `import_structured_facts_to_sqlite`.
- Import later, if approved: Reviewed structured metadata/facts only, into cassandra_chief_memory_email_permissions plus Operator Action / Guardian links.
- Do not import: Email addresses stay hashed/redacted unless explicitly approved.
- Risk if imported blindly: Unverified legacy claims could become apparent truth or expose private identifiers.
- Operator decision needed: yes.
- Next safe move: Operator approves or rejects this category for a later bounded structured import lane.

### company/contact relationships
- What it is: business contact relationship refs.
- Why it matters: Relationship edges are useful, but labels are not verified truth.
- Recommended fate: `import_structured_facts_to_sqlite`.
- Import later, if approved: Reviewed structured metadata/facts only, into cassandra_chief_memory_entity_relationships.
- Do not import: Summaries only; client/customer details stay redacted.
- Risk if imported blindly: Unverified legacy claims could become apparent truth or expose private identifiers.
- Operator decision needed: yes.
- Next safe move: Operator approves or rejects this category for a later bounded structured import lane.

### contacts and nicknames
- What it is: contact nicknames and contact list refs.
- Why it matters: Aliases and identity posture are structured enough for later governed import.
- Recommended fate: `import_structured_facts_to_sqlite`.
- Import later, if approved: Reviewed structured metadata/facts only, into cassandra_chief_memory_entities / aliases / contact_channels.
- Do not import: No raw chat IDs, phone numbers, private identifiers, or contact bodies in read-models.
- Risk if imported blindly: Unverified legacy claims could become apparent truth or expose private identifiers.
- Operator decision needed: yes.
- Next safe move: Operator approves or rejects this category for a later bounded structured import lane.

### invoice facts
- What it is: finance state and billing record refs.
- Why it matters: Invoice facts belong in existing finance evidence packet surfaces.
- Recommended fate: `import_structured_facts_to_sqlite`.
- Import later, if approved: Reviewed structured metadata/facts only, into finance_invoice_packet_* / finance_invoice_reconciliation_*.
- Do not import: No raw spreadsheet cells, bank data, tax/private bodies, or truth claims.
- Risk if imported blindly: Unverified legacy claims could become apparent truth or expose private identifiers.
- Operator decision needed: yes.
- Next safe move: Operator approves or rejects this category for a later bounded structured import lane.

### receivable/payment tracking
- What it is: invoice tracker and payment status refs.
- Why it matters: Receivable status can reduce burden only when evidence status is explicit.
- Recommended fate: `import_structured_facts_to_sqlite`.
- Import later, if approved: Reviewed structured metadata/facts only, into finance_invoice_packet_* / finance_invoice_reconciliation_* / Work Board.
- Do not import: Payment-provider and bank raw data blocked; payment facts are claims until confirmed.
- Risk if imported blindly: Unverified legacy claims could become apparent truth or expose private identifiers.
- Operator decision needed: yes.
- Next safe move: Operator approves or rejects this category for a later bounded structured import lane.

## 2. Register as evidence source only
### Chief session/task memory
- What it is: Chief session, queue, and route refs.
- Why it matters: Session/task files are volatile runtime state.
- Recommended fate: `register_as_evidence_source_only`.
- Import later, if approved: Metadata-only source registration and posture only, linked to source catalog, session snapshot metadata, Work Board.
- Do not import: No raw task bodies unless a later lane approves bounded excerpts.
- Risk if imported blindly: Noisy runtime state could look canonical and mislead future routing.
- Operator decision needed: yes.
- Next safe move: Keep as metadata-only evidence source unless the operator asks for a narrower extraction.

### Windows-side logs
- What it is: Windows-side Cassandra/Chief runtime log refs.
- Why it matters: Logs are useful for diagnosis but likely contain raw private/runtime content.
- Recommended fate: `register_as_evidence_source_only`.
- Import later, if approved: Metadata-only source registration and posture only, linked to cassandra_chief_memory_sources.
- Do not import: No raw log ingestion; safe labels and path hashes only.
- Risk if imported blindly: Noisy runtime state could look canonical and mislead future routing.
- Operator decision needed: yes.
- Next safe move: Keep as metadata-only evidence source unless the operator asks for a narrower extraction.

## 3. Summarize/extract only
### Cassandra notes
- What it is: Cassandra reality notes ref.
- Why it matters: Reality notes may be useful but messy notes remain evidence.
- Recommended fate: `summarize_or_extract_only`.
- Import later, if approved: Approved redacted summaries or metadata only, linked to cassandra_chief_notes plus source catalog.
- Do not import: No raw private notes by default.
- Risk if imported blindly: Private bodies or unsupported summaries could leak into Core.
- Operator decision needed: yes.
- Next safe move: Approve only a later redacted-summary extraction, not raw-content ingest.

### billing tracker CSV/PDF paths
- What it is: billing tracker CSV and PDF refs.
- Why it matters: Trackers/PDFs can support finance packets but raw parsing can expose private finance data.
- Recommended fate: `summarize_or_extract_only`.
- Import later, if approved: Approved redacted summaries or metadata only, linked to finance source links / finance evidence packet metadata.
- Do not import: No spreadsheet cells, PDF body extraction, bank details, or truth claims.
- Risk if imported blindly: Private bodies or unsupported summaries could leak into Core.
- Operator decision needed: yes.
- Next safe move: Approve only a later redacted-summary extraction, not raw-content ingest.

### calendar/event notes metadata
- What it is: calendar and scheduler note refs.
- Why it matters: Calendar notes can guide context but are not live calendar truth.
- Recommended fate: `summarize_or_extract_only`.
- Import later, if approved: Approved redacted summaries or metadata only, linked to cassandra_chief_calendar_note_metadata.
- Do not import: Titles/details hashed or summarized only; no raw calendar bodies.
- Risk if imported blindly: Private bodies or unsupported summaries could leak into Core.
- Operator decision needed: yes.
- Next safe move: Approve only a later redacted-summary extraction, not raw-content ingest.

### correspondence metadata
- What it is: conversation, correspondence, email, call, and SMS refs.
- Why it matters: Correspondence logs can contain private body text.
- Recommended fate: `summarize_or_extract_only`.
- Import later, if approved: Approved redacted summaries or metadata only, linked to cassandra_chief_correspondence_threads / events.
- Do not import: Do not ingest bodies; store metadata, hashes, and approved redacted excerpts only.
- Risk if imported blindly: Private bodies or unsupported summaries could leak into Core.
- Operator decision needed: yes.
- Next safe move: Approve only a later redacted-summary extraction, not raw-content ingest.

## 4. Block / do not trust
### old HITL JSON/JSONL state
- What it is: legacy HITL approval JSON/JSONL refs.
- Why it matters: Old approval files must not become active approval authority.
- Recommended fate: `block_no_go`.
- Import later, if approved: Nothing as authority. At most a blocked historical reference after a separate approval lane.
- Do not import: No active approvals, execution payloads, sends, command strings, or old HITL authority.
- Risk if imported blindly: Old approval state could bypass Guardian, approve actions, execute, or send.
- Operator decision needed: yes.
- Next safe move: Keep blocked; use Operator Action / Guardian for any real approval path.

## 5. Delete local residue candidate
### untracked polish_loop Cassandra failure tasks
- What it is: two untracked Cassandra failure task prompts.
- Why it matters: They are duplicate generated task prompts, not durable evidence.
- Recommended fate: `delete_local_residue`.
- Import later, if approved: Nothing. A future cleanup lane may record a deletion receipt if the operator approves.
- Do not import: No file body and no automatic deletion.
- Risk if imported blindly: Diagnostic evidence could be lost without a cleanup receipt.
- Operator decision needed: yes.
- Next safe move: Delete only in an explicit cleanup lane with operator approval; do not commit.

## 6. Needs operator decision
### album/song progress state
- What it is: album work, content, and scheduler refs.
- Why it matters: This belongs to Niles/music module authority.
- Recommended fate: `defer_operator_review`.
- Import later, if approved: Nothing in Cassandra/Chief yet. Route to future Niles Album Production Matrix only after operator review.
- Do not import: No raw album/session content in this lane.
- Risk if imported blindly: Ownership could drift into the wrong module or agent lane.
- Operator decision needed: yes.
- Next safe move: Operator chooses the owning future module or leaves it deferred.

### dirty generated agent_presence snapshots
- What it is: dirty generated agent_presence read-model snapshots.
- Why it matters: Generated runtime presence snapshots are volatile and currently dirty.
- Recommended fate: `defer_operator_review`.
- Import later, if approved: Nothing in Cassandra/Chief yet. Route to future agent presence volatile-snapshot cleanup only after operator review.
- Do not import: Generated metadata only; do not derive live receive proof from it.
- Risk if imported blindly: Ownership could drift into the wrong module or agent lane.
- Operator decision needed: yes.
- Next safe move: Operator chooses the owning future module or leaves it deferred.

## Global boundaries
- `data_imported=false`; `raw_content_read=false`; `old_files_are_truth=false`.
- `import_allowed_now=false` for every category.
- Old HITL state is not active approval authority.
- Delete-local-residue candidates are not auto-deleted.

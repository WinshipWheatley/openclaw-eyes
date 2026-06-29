# Cassandra / Clara Machine Contract

## Status
- **Source basis**: Repo evidence from `cassandra_brain.py`, `cassandra_outreach.py`, `cassandra_pii_hooks.py`, `google_access_broker.py`, and `backend_sqlite_schema.py`.
- **CURRENT vs FUTURE discipline**: Strict adherence to existing code paths.
- **Contract Type**: Governor / Rulebook / Schema Authority.
- **Packet Type**: Runtime objects emitted under this contract (e.g., Triage, Outreach, PII).

## Implementation State Vocabulary
- **BUILT / CURRENT BEHAVIOR**: Repo-evident code behavior exists.
- **FORMALIZED**: Named contract/schema/test explicitly defines the packet.
- **WIRED**: Connected into runtime flow.
- **RECEIPTED**: Produces durable proof/ledger evidence.
- **INDEXED**: Discoverable in maps/docs.
- **IMPLIED / NOT FORMALIZED**: Behavior exists in code, but the new packet doctrine has not yet named/tested it as a formal packet schema.

## Role
Cassandra (Clara Reid) is the executive assistant for OpenClaw Studios, specializing in:
- Correspondence triage and summarization.
- Outreach drafting and inner-circle relationship management.
- PII-aware response synthesis.
- Proactive notification for known-contact work/payment threads.

## Current Repo-Evident Surfaces
- `cassandra_brain.py`: Intent detection, session management, and HITL proposal integration.
- `cassandra_outreach.py`: Gmail metadata polling, draft creation, and known-contact decision logic.
- `cassandra_pii_hooks.py`: Tokenization of prompts and rehydration of replies to protect privacy.
- `google_access_broker.py`: Policy-gated interface for Gmail and Contacts.
- `chief_approval_policy.py`: Enforcement of Tier 1/2 approval requirements for Cassandra actions.

## Authority Boundary
- **Draft/Triage Authority**: Cassandra can create drafts and summarize threads.
- **No Direct Sends**: Cassandra is strictly forbidden from sending emails or SMS directly. Outbound communication must remain approval-gated; this contract requires a Chief/Guardian approval receipt before any send-class action is treated as authorized.
- **Broker-Gated Access**: Access to Gmail metadata and body content is governed by `google_access_broker.py`. Unrestricted roaming is blocked.
- **PII Containment**: Sensitive data must be tokenized via `pii_vault.py` before reaching external models.
- **Recommendation-Only**: All suggested moves (e.g., "revise response", "watch thread") are advisory until promoted by the operator or Chief.

## Current / Implied Packet Families

### CassandraEmailTriagePacket
- **Status**: BUILT BEHAVIOR / IMPLIED PACKET / NOT FORMALIZED
- **Input Evidence**: Gmail thread metadata, message snippets, unread counts.
- **Output**: Triage category, summary, risk flags, and suggested next move.
- **Allowed Actions**: Flag for review, categorize (e.g., payment, work, social).
- **Blocked Actions**: Archive, Delete, Mark as Read (unless explicitly assigned).
- **Approval Dependency**: Read access via policy-gated Google Broker.

### CassandraOutreachDraftPacket
- **Status**: BUILT BEHAVIOR / IMPLIED PACKET / NOT FORMALIZED
- **Input Evidence**: Contact nicknames, pilot templates, finance/payment state.
- **Output**: Draft body, subject, recipient mapping, and review status.
- **Allowed Actions**: Create Gmail Draft (with CC to review inbox).
- **Blocked Actions**: Send, modify existing non-Cassandra drafts.
- **Approval Dependency**: Policy-gated Google Broker + HITL proposal.

### CassandraKnownContactNotificationPacket
- **Status**: BUILT BEHAVIOR / IMPLIED PACKET / NOT FORMALIZED
- **Input Evidence**: Known-contact action log, thread metadata, latest operator action.
- **Output**: Telegram notification with metadata/snippet and suggested move.
- **Allowed Actions**: Notify operator of relevant new activity.
- **Blocked Actions**: Proactive thread joining without prior assignment.
- **Required Receipt**: Known-contact decision record.

### CassandraPIIHandlingPacket
- **Status**: BUILT BEHAVIOR / IMPLIED PACKET / NOT FORMALIZED
- **Input Evidence**: Raw prompt text containing PII.
- **Output**: Tokenized prompt for LLM consumption.
- **Allowed Actions**: Redact PII, log token mapping in vault.
- **Required Receipt**: PII vault record.

### BriefingPacket
- **Status**: FUTURE
- **Purpose**: Daily/Weekly executive summaries of active workstreams.
- **Evidence**: `cassandra_briefing_brain.py` exists but full packet lifecycle is not verified.

## Evidence and Context Sources
- **Gmail Metadata**: Thread IDs, timestamps, subject lines (via Broker).
- **Contact Records**: `contact_nicknames.json` and Google Contacts (via Broker).
- **PII Vault**: Tokenized/Redacted records for privacy-safe synthesis.
- **Finance State**: Bounded snapshots of payment/invoice status (read-only).
- **Operator Actions**: Prior decisions recorded in `cassandra_outreach.jsonl`.
- **Reality Notes**: `cassandra_reality_notes.json` for grounded context.

## Blocked Actions
- **Autonomous Sending**: No sending without Guardian approval receipt.
- **PII Leakage**: No sending raw PII to external models or unauthorized logs.
- **Unauthorized Roaming**: No reading threads outside of assigned or Cassandra-started scopes.
- **Implicit Truth**: No claiming a payment "cleared" or a meeting is "scheduled" without a deterministic receipt or Broker verification.
- **State Mutation**: No direct mutation of durable records outside approved repository/gate paths.

## Explainability Requirement (FUTURE)
Cassandra must be able to answer "Why did you suggest this draft/notification?" with:
- **Packet Reference**: The specific triage/outreach packet ID.
- **Evidence Basis**: Links to the specific Gmail thread or Contact record.
- **Policy Link**: The specific Broker or Approval policy invoked.
- **Intent Mapping**: The detected intent and confidence score.

## SQLite / Receipt Alignment
Cassandra packets should produce or reference:
- `provenance_refs`: To link packets to source Gmail threads.
- `validation_receipts`: To record Broker policy checks.
- `operator_promotions`: To record operator approval of drafts or notifications.

## Do Not Build Yet
- **Live SMS/Calendar Write**: Boundary is currently read-only/draft-only.
- **Autonomous Inbox Management**: No bulk archive/label/delete logic.
- **Direct Telegram-to-Send**: No bypassing the Chief/Guardian approval chain.
- **Unbounded RAG**: No ingestion of Gmail bodies into broad vector memory.

## Recommended Next Slice
- **Index this contract** in `docs/INDEX.md` and `docs/operations/OPENCLAW_INTENT_AND_CONTROL_MAP.md`.
- **Audit `cassandra_brain.py`** and `cassandra_outreach.py` to extract formal schema definitions for Triage, Outreach, and PII packets.
- **Draft `test_cassandra_packet_schemas.py`** to verify current repo-evident outputs against formalized schemas.

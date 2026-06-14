# Conversational Workflow Router Contract v0

ELIOPERATOR: Chat is the operator surface. The router decides what kind of work the message implies, then prepares human cards and backend package targets. Nothing executes just because a message was routed.

## What This Enables

A chat-first app can show what OpenClaw understood, what workflow is proposed, what is missing, what is blocked, and which future package/role lane is needed.

## How It Works

- A sanitized chat message becomes candidate intent.
- The router creates plain-language cards for the app.
- The router also identifies future role/package targets below deck.
- Receipts and readbacks decide truth.
- External actions remain gated.

## Capital Hilton Example Cards

### OpenClaw understood
- Goal: prepare Capital Hilton invoice workflow.
- Destination/contact: Annette appears to be the payment follow-up contact candidate.
- Companion invoice: Excel-generated / Winship-branded PDF invoice.
- Official payment rail: Coupa supplier portal / PO.
- Proof/source: Excel PDF plus Coupa/PO proof or reference.
- Still missing: confirmed PO/Coupa reference, confirmed recipient/contact, final artifact, Guardian approval.
- External actions: locked.

### Proposed workflow
- Confirm dates and rate.
- Prepare invoice artifact.
- Confirm PO/Coupa.
- Confirm contact.
- Prepare draft.
- Request approval.
- Send or submit only through gates.
- Read back proof.

### What is not happening
- No email sent.
- No Coupa access.
- No browser opened.
- No approval requested.
- No invoice submitted.

## Boundary

- No live chat parser or model call was used.
- No router dispatch, agent dispatch, procedure write, or workflow run occurred.
- No Cassandra draft or Guardian approval was created.
- No email draft/send, Coupa access/submit, invoice generation, attachment, payment tracking write, credential handling, or external action occurred.
- No Mac sync/import, Swift change, network, or push occurred.

Next safe move: Surface this read-model to Mac or build a future deterministic package writer.

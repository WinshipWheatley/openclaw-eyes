# OpenClaw Generic Receipt Spine v0

## Purpose

The generic receipt spine provides one flexible way to record evidence events in
the existing SQLite events/packets ledger without creating a new one-off writer
for every artifact, validation result, approval record, generated status, or
future product/domain document.

The spine uses a generic call shape:

```python
record_receipt(receipt_type="artifact_checkpoint", payload={...})
```

`receipt_type` distinguishes the receipt class. `payload_json` carries
type-specific details.

## Why This Avoids Writer Sprawl

Before this spine, receipt handling was mostly lane-specific: orientation
snapshot receipts, test proof receipts, action intent gate receipts, approval
records, outreach draft receipts, PII vault receipts, and truth packet decision
receipts each had their own writer shape.

Those writers remain valid. The generic spine is for metadata receipts that do
not need bespoke safety behavior. New docs-only or validation-only checkpoints
should prefer the generic shape before adding another narrow writer.

## Envelope Fields

The v0 envelope supports:

- `receipt_id`
- `receipt_type`
- `artifact_path`
- `commit_hash`
- `artifact_type`
- `artifact_status`
- `authority_status`
- `runtime_activation`
- `sqlite_meaning`
- `source_basis`
- `payload_json`
- `created_at`

The current implementation stores this envelope in the existing
`packets.packet_json_safe` field and stores a concise event row in `events`.
No schema migration is required.

## `receipt_record_only`

`sqlite_meaning: receipt_record_only` means the SQLite row is evidence/status
metadata only.

It does not mean:

- the artifact is runtime authority
- the artifact has been deployed
- a module has been activated
- an agent has been wired
- a broker has been connected
- a customer workflow is ready
- sensitive data may be processed

## Metadata-Only SQLite Posture

The generic receipt writer records metadata and caller-supplied
`payload_json`. It does not read artifact bodies and must not store full
Markdown document bodies in SQLite.

For artifact checkpoints, the intended payload is concise metadata such as
validation command labels, expected status, source basis, or proof references.

Full document text belongs in committed files, not in receipt rows.

## Compatibility With Existing Writers

Existing receipt writers were audited and left in place:

- `scripts/record_test_proof_receipt.py`
- `scripts/orientation_snapshot.py`
- `record_action_intent_gate_receipt`
- `record_approval_log_entry`
- `record_approval_request_record`
- `record_outreach_email_draft_receipt`
- `record_pii_vault_receipt`
- `append_truth_packet_decision_receipt`

They should remain separate when they enforce lane-specific safety rules,
redaction, command-output hashing, approval semantics, or model-boundary rules.

Future narrow writers may wrap `record_receipt()` when their behavior is simple
metadata evidence. Writers that need special redaction or denial logic should
continue to keep that logic explicit.

## What Receipts Do Not Authorize

A receipt is evidence, not permission.

Receipts do not authorize:

- runtime activation
- module activation
- broker connections
- agent wiring
- SQLite meaning beyond receipt storage
- generated-status mutation
- customer deployment
- autonomous action
- sensitive-data processing
- private data reads

## Remaining Duplication And Future Migration

Remaining duplication is intentional for v0. The current one-off writers carry
specific safety contracts and should not be mechanically migrated.

Future migration can happen one writer at a time when tests prove:

- existing receipt semantics are preserved
- redaction and no-body-storage behavior still hold
- execution authority remains false unless a separate approved lane says
  otherwise
- receipts remain evidence only

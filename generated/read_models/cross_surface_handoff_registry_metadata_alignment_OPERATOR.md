# Cross-Surface Handoff Registry Metadata Alignment

## ELIOPERATOR

This adds a standard metadata shape for future Mac/PC handoffs. It prepares post-office routing language without replacing the working bridge.

This is metadata-only. It does not create a post-office runtime, watcher, daemon, auto-import, auto-consume path, Telegram integration, agent dispatch, Mac Swift change, or external action.

## What Changed

- Defined the additive post_office_metadata fields future manifests/readbacks can include.
- Modeled aligned metadata for Performance Dates, PO/Coupa readback, delivery capture intake, invoice preview, and reusable facts.
- Recorded which fields are still missing instead of inventing values.

## What Did Not Change

- No existing package path changed.
- No existing manifest field was removed.
- No live intake semantics changed.
- No SQLite state changed.
- No Mac import or Swift code changed.
- No send, submit, browser, Coupa, Gmail, Telegram, model, agent, tool, or runtime action was added.

## Why It Matters

- Future packages can say what they are, which handler owns them, what lifecycle state they are in, and what authority applies.
- Mission Control can later render cleaner readback status without each package needing custom language.
- Protected or unavailable values stay explicit and fail-closed.

## Still Bespoke

- The current capture writers and shuttle packages stay in place.
- Reusable fact handoff remains future-only.
- Telegram/Cassandra remains compatibility-only, not live.

## Easier Later

- Readback package generation can attach one post-office metadata section.
- Mac can eventually route closeouts by artifact_type and lifecycle_state.
- Backend audits can compare manifests using shared field names.

## Machine Proof

- Package paths unchanged: True
- Existing manifest fields preserved: True
- Live behavior changed: False
- Live registry migration added: False
- External authority changed: False
- Raw private bodies included: False
- Content hash: `sha256:83d4697bc6c0d8ce90c796fac82b83d5554f8a3b40edd6454ac1915cbc479f30`

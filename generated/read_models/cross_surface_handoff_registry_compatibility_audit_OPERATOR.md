# Cross-Surface Handoff Registry Compatibility Audit

## ELIOPERATOR

The current Mac/PC handoff works, but each package still has custom instructions. The new post office contract can standardize labels and lifecycle without changing live behavior yet.

The audit says the Capital Hilton bridge is real and should not be ripped out. The practical move is metadata alignment: add post-office labels, lifecycle states, schema refs, reply routes, privacy classes, and idempotency/hash basis where missing.

## What Already Works

- Mission Control can emit bounded capture request JSON.
- Repo A can validate, write local SQLite receipt/state, and read back captured values.
- Mac-bound packages can render closeouts/readbacks without external authority.
- The PO/Coupa readback package already carries many future post-office metadata fields.

## Still Bespoke

- Earlier packages infer lifecycle from package purpose instead of explicit lifecycle_state.
- Package manifests use custom outbox/readback vocabulary instead of a shared artifact envelope.
- Artifact preview readback has a real file hash but no generic handoff idempotency key.

## Patch Later

- Add artifact_type, schema_ref, lifecycle_state, target_handler, reply route, privacy class, and role fields.
- Add idempotency/hash basis to outbox markers where the future generic handoff will create requests.
- Use the PO/Coupa readback manifest as the first template for registry-ready package metadata.

## Do Not Touch Yet

- Do not replace the working Mission Control capture intake.
- Do not rewrite shuttle copy/import behavior.
- Do not add a watcher, daemon, runtime queue, or auto-consume path.
- Do not build live Telegram/Cassandra integration in this migration.
- Do not route raw protected values through normal handoffs.

## No Big-Bang Plan

- Phase 0: Keep current rails intact; inventory intakes, readbacks, package manifests, and artifact previews.
- Phase 1: Add artifact_type/schema_ref/lifecycle/target_handler/reply route metadata to future read-models and manifests.
- Phase 2: Normalize WRITTEN, DUPLICATE_NOOP, READBACK_READY, RENDERED, BLOCKED, and REJECTED labels in readback outputs.
- Phase 3: Map existing handlers into the registry one by one, starting with Performance Dates and PO/Coupa posture.
- Phase 4: Only after audits and tests, consider a gated runtime; this audit does not create one.

Explicit non-goals:
- no file watcher
- no daemon
- no auto-import
- no live runtime queue
- no Telegram live integration
- no automatic agent dispatch
- no external actions
- no big-bang replacement

## Machine Proof

- All live authority flags false: True
- No migration or replacement performed: True
- Metadata-only package inspection: True
- Raw private bodies included: False
- Content hash: `sha256:765261f636b741eb0d8863bf71f84588187f1be979ae1141c2d0cb4b7e6ed97d`

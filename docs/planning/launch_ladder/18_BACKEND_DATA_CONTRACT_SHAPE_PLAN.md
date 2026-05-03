# Backend Data Contract Shape Plan

Status: docs/test-only planning artifact. This plan does not authorize implementation, backend/API/schema files, SQL DDL, SQLite DB creation, ingestion, fixture generation, provider/model calls, private-data inspection, runtime mutation, app implementation, app naming, or audio/haptic/notification implementation.

## 1. Purpose

This plan defines the first conceptual backend/data-contract shapes needed before any backend/schema/SQLite/ingestion/fixture work begins.

## 2. Non-goals

This artifact does not authorize implementation, backend/API/schema files, SQL DDL, SQLite DB creation, ingestion, fixture generation, provider/model calls, private-data inspection, runtime/service/approval mutation, app implementation, app naming, or audio/haptic/notification implementation. It does not create source-set folder 05 or authorize source-set 05 generation.

## 3. Contract Shape Principles

- records must separate raw source, extraction, rendering, classification, claim, compiled note, freshness, promotion, and conversation packet states
- discovered does not mean read
- extracted does not mean true
- classified does not mean safe
- compiled does not mean accepted
- promoted does not mean general authority
- unknown remains restricted
- sensitive/local-only must be representable without exposing content
- app-visible state must have evidence/freshness basis

## 4. First Conceptual Record Shapes

### source file record
- Represents: The existence and metadata of a discovered file.
- Minimum conceptual fields: id, uri, kind, discovered_timestamp, sensitivity.
- Must not imply: Permission to read, summarize, or export.
- App-facing use: To show existence in scope without proving analysis.

### extracted text record
- Represents: Parsed text derived from a source file.
- Minimum conceptual fields: id, source_id, parsed_text, warnings.
- Must not imply: Correctness, completeness, or safe export.
- App-facing use: To prove text was parsed.

### rendered fragment record
- Represents: A preserved structural representation of a source file.
- Minimum conceptual fields: id, source_id, html_ref, page_region.
- Must not imply: Claim or truth.
- App-facing use: Displaying original shapes for reference.

### artifact classification record
- Represents: Labels applied to a source regarding type and sensitivity.
- Minimum conceptual fields: id, source_id, artifact_type, sensitivity, confidence.
- Must not imply: Absolute safety.
- App-facing use: Filtering and warning operators about sensitivity.

### claim record
- Represents: A bounded statement with evidence and confidence.
- Minimum conceptual fields: id, statement, evidence_refs, confidence.
- Must not imply: Absolute truth or current state without freshness.
- App-facing use: Presenting verifiable information.

### contradiction record
- Represents: Conflicting evidence or claims.
- Minimum conceptual fields: id, conflicting_claim_refs, evidence_refs, status.
- Must not imply: Automatic adjudication or resolution.
- App-facing use: Flagging areas requiring operator review.

### compiled note record
- Represents: Durable operator-readable interpretation.
- Minimum conceptual fields: id, markdown_body, claim_refs, limitations.
- Must not imply: Fact without evidence, or operator acceptance.
- App-facing use: Structured knowledge display.

### freshness record
- Represents: The temporal validity of a target.
- Minimum conceptual fields: id, target_id, timestamp, stale_conditions, refresh_trigger.
- Must not imply: System-wide health or live status.
- App-facing use: Decorating UI components with current/stale badges.

### operator promotion record
- Represents: Explicit operator decisions (accept, reject, mark historical, mark sensitive, exclude).
- Minimum conceptual fields: id, target_id, decision, operator, scope.
- Must not imply: Broadened authority beyond the named scope.
- App-facing use: Reflecting human-in-the-loop decisions.

### conversation packet record
- Represents: A sanitized context object for handoff.
- Minimum conceptual fields: id, included_refs, withheld_surfaces, sensitivity_summary.
- Must not imply: Execution authorization or external model use.
- App-facing use: Presenting safe context bundles for review.

### blocked sensitive source record
- Represents: A source restricted due to policy.
- Minimum conceptual fields: id, reason, required_path.
- Must not imply: Content has been read or parsed.
- App-facing use: Showing a source exists but is intentionally restricted.

### unknown/unclassified artifact record
- Represents: An artifact lacking required evidence or classification.
- Minimum conceptual fields: id, missing_fields.
- Must not imply: Safety or confidence.
- App-facing use: Prompting operator intervention.

## 5. Relationship Rules

Records reference each other without collapsing states:
- extracted text references source file
- rendered fragment references source file or extracted text
- claim references evidence
- compiled note references claims/evidence
- freshness references the target it scopes
- promotion references explicit target/scope
- conversation packet references sanitized records only
- blocked sensitive source can prove blocked existence without exposing content

## 6. App-Facing State Mapping

- ready: packet prepared and approved
- blocked: sensitive/local-only constraints hit
- stale: freshness conditions violated
- unknown: missing evidence
- sensitive/local-only: restricted display
- evidence available: related evidence_refs exist
- approval/promotion available: valid target ready for decision
- contradiction present: conflicting claims detected
- packet prepared: conversation packet generated

This defines state semantics only, not UI implementation.

## 7. Future Fixture Topics

Future synthetic fixtures should eventually be created for these topics:
- A stale compiled note
- A blocked sensitive source
- A contradiction between claims
- A sanitized conversation packet

This artifact does not create fixtures.

## 8. Future Static Validation Expectations

Future static validation should prove:
- 18 plan exists
- required record shapes are named
- forbidden implementation authorizations are absent
- state-separation phrases are preserved
- unknown restricted and sensitive local-only are preserved
- app-facing states require evidence/freshness basis
- no source-set 05 generation occurs in this slice

## 9. Recommended Next Move

The next move after this artifact is:
- either one more docs/test planning slice for synthetic fixture design, or
- source-set generation for a future 05 only after the 18 plan is committed and audited

Do not recommend implementation yet.
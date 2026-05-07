# Storage Intelligence And Authorization

Status type: BUILT_TRUTH

## Purpose

Preserve storage intelligence, authorization, runtime presence, and source authorization substrate as built truth without granting cleanup, sync, private-root access, or activation.

## Source Inputs

- Packet 06 `12_STORAGE_INTELLIGENCE_AND_AUTHORIZATION.md`
- Packet 06 `15_SENSITIVE_ROOT_QUARANTINE_POLICY_AND_REGISTRY.md`
- Packet 06 `23_BROAD_SOURCE_SET_EXCLUSION_GUARD.md`
- Packet 06 final `00_ACTIVE_HANDOFF.md`

## What It Governs

- Authorization as explicit state.
- Runtime presence as evidence, not control.
- Source authorization scopes.
- Storage intelligence read models.
- Sensitive/private material represented by boundary labels, not content.

## Repo Implementation Pointers

- `backend_storage_intelligence.py`
- `backend_sqlite_repository.py`
- `openclaw_sensitive_policy.py`
- `tests/test_backend_storage_intelligence.py`

## Valid Future Lane Moves

- Sensitive-root and legal-export static contract hardening.
- Operator Harness storage/readiness read-model planning.
- Runtime authority and legacy gating review.
- No-private-root receipt refinements.

## Forbidden Drift

- Do not turn storage visibility into cleanup, deletion, movement, sync, ingestion, or crawl authority.
- Do not inspect private folders to classify content.
- Do not treat runtime presence as service-control authority.
- Do not summarize sensitive content from path metadata.

## Review Boundary

Review before storage, sensitive-root, runtime-presence, source registry, or Operator Harness Cargo Hold-style work.

## Why It Should Last 10-20 Moves

Storage and authorization boundaries are a recurring dependency for Packet 07 activation gates.

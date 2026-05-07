# Sensitive Root And Legal Export Boundaries

Status type: BOUNDARY_GUARD / FUTURE_LANE

## Purpose

Carry forward sensitive-root quarantine and legal export boundaries as metadata-only static policy. This rail blocks private-root inspection and legal/private content export until explicit future authority exists.

## Source Inputs

- Packet 06 `15_SENSITIVE_ROOT_QUARANTINE_POLICY_AND_REGISTRY.md`
- Packet 06 `19_LEGAL_CONTEXT_EXPORT_POLICY_PLAN.md`
- Packet 06 final `00_ACTIVE_HANDOFF.md`
- `openclaw_sensitive_policy.py`
- `tests/test_openclaw_receipts.py`

## What It Governs

- Path-string denylist/allowlist policy.
- Sensitive root as border checkpoint.
- Legal export policy as metadata-only and blocked-source-reference-only.
- No-echo behavior for denied paths.
- Distinction between legal planning and legal content access or action.

## Repo Implementation Pointers

- `openclaw_sensitive_policy.py`
- `scripts/openclaw_receipts.py`
- `backend_knowledge_packet.py`
- `tests/test_openclaw_receipts.py`
- `tests/test_backend_agent_context.py`

## Valid Future Lane Moves

- Add focused no-echo/static-policy tests.
- Define legal export metadata classes.
- Improve receipt wording for blocked legal/sensitive surfaces.
- Plan Operator Harness boundary displays.

## Forbidden Drift

- No private-root crawling, opening, reading, resolving, or listing.
- No legal-private content reads.
- No client/private matter summaries.
- No outside model access to legal roots.
- No legal advice, filing, external sending, or authority transfer.

## Review Boundary

Review before any prompt touches sensitive roots, legal-private folders, discovery, quarantine, legal product planning, legal app context, or legal exports.

## Why It Should Last 10-20 Moves

Sensitive and legal boundaries are high-stakes and recurring. Packet 07 should carry them as hard gates, not as implementation bait.

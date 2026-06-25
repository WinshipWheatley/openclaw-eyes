# Orchestrator Handoff: Legal Message Evidence and PII System

## Findings
- **PII Functionality Built:** Minimal. In-memory `pii_vault.py` (Fernet & Presidio), `cassandra_pii_hooks.py` interceptors, and a synthetic read-model `token_vault.py`.
- **Functionality Missing:** No secure tokenized Legal Sealed tier, no case isolation, no OS boundaries, no evidence provenance layer.
- **Verdict:** Unsafe to ingest raw legal messages today.

## What Can Be Done Manually Now
- Operators can acquire, hash, and safely store extraction databases (e.g., `sms.db`) locally outside of OpenClaw.

## What Can Run in Parallel
- Drafting the immutable `MessageEvidenceRecord` schema and serialization layer.
- Creating the `synthetic_sms.db` corpus for tests.
- Comparing extraction tools.

## What Must Wait (Series)
- Live evidence ingestion, agent search workflows, and building the secure SQLite Legal Sealed vault. These depend on Opus completing robust OS boundaries and token vault architectures.

## Smallest Next Engineering Unit
- Draft the `MessageEvidenceRecord` Python dataclasses with strict type validation (similar to the G2C records). Use synthetic fixtures exclusively.

## Branches & Collision Risks
- Gig-to-Cash (G2C) and Evidence Pilot branches are highly active. Do not overwrite `ar_gig_record.py` or `ar_gig_to_cash_serialization.py`. Build parallel schema files (`ar_message_evidence.py`).

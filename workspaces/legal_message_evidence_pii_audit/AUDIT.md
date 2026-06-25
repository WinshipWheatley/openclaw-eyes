# Legal Message Evidence and PII System Audit

## 1. Current State Inspection
- **Branch:** `codex/stress-fixes`
- **Worktrees:** Numerous active worktrees, including `agy-sonnet/g2c-005-scheduled-20260626` (which generated canonical serialization) and `g2c006-*` branches.
- **Opus Orchestrator:** Currently handling Gig-to-Cash (G2C) and the Capital Hilton Evidence Pilot.
- **Evidence Pilot:** Existing evidence registry (`ar_gig_to_cash_serialization.py`, `ar_gig_record.py` etc.) is actively under construction and review.

## 2. PII Router and Sensitive-Data Controls Audit
- Found `pii_vault.py`: Implements global Fernet encryption + regex/Presidio-based in-memory tokenization. Missing case isolation, missing irreversible redaction distinction, missing secure detokenization audit bounds, and uses global `<ENTITY_TYPE_N>` counters.
- Found `cassandra_pii_hooks.py`: In-memory interceptor for LLM prompts. Falls back to regex if Presidio is disabled. Rehydration occurs without robust identity isolation.
- Found `openclaw_sensitive_policy.py`: Static path policy preventing access to `.env` or `secret` filenames, but no content scanning.
- Found `token_vault.py`: A synthetic testing read-model only. No real production token vault substrate is active.

## 3. Capability Verdicts
- **Current PII router:** PARTIAL / UNSAFE FOR LEGAL SEALED (in-memory only, no case isolation).
- **Legal Sealed Tier:** MISSING.
- **Live Tokenization / Rehydration:** UNVERIFIED / PROPOSED for legal bounds. Agents can trivially bypass it via SQLite or uncontrolled shell paths.

**Verdict:** NO-GO UNTIL SPECIFIC CONTROLS EXIST. Do not ingest raw message history.

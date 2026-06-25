# PII Router Audit

## Existing Functionality
1. `pii_vault.py`:
   - Contains Fernet-based local key storage for basic `key: value` PII. 
   - Contains an in-memory `TokenMap` that uses Regex patterns to redact text (`[SECRET_1]`).
   - Contains a `PIIVault` class leveraging `presidio-analyzer` to tokenize entities (`<PERSON_1>`).
   - **Flaws:** Counters are global or per-call; case-isolation is non-existent. Token maps live in Python memory and disappear across agent turns unless manually passed. 

2. `cassandra_pii_hooks.py`:
   - Intercepts requests to the Cassandra LLM pipeline. Uses `presidio` or fallback regex. 
   - **Flaws:** Rehydrates blindly before sending to dashboard. No audit logging of who detokenized what for what matter.

3. `token_vault.py`:
   - A mock/synthetic read-model generator. Creates a schema with tables (`token_vault_metadata`, `tokenized_entities`, `token_revocations`, `token_audit_log`, `token_vault_receipts`) but explicitly notes it uses "Synthetic tokenization fixture only. No real sensitive values are exported."

4. `openclaw_sensitive_policy.py`:
   - A path-based gate. Scans filenames for `api_key`, `secret`, `vault`. It does not perform content redaction.

## Bypass Paths (Unsafe)
- Agents have unrestricted shell access (`Bash`), `SQLite` access, and filesystem read/write.
- Agents can read the raw evidence databases directly, bypassing `cassandra_pii_hooks.py`.
- OS-level user identities are shared between the Orchestrator, builder agents, and tools.
- There is no enforced OS-level separation of token mappings and encryption keys from the language model execution environment.

## Verdict
- **Classification:** PARTIAL, UNVERIFIED for legal evidence.
- The PII router is mostly policy scaffolding and in-memory interceptors. It is thoroughly inadequate for Legal Sealed Evidence processing.

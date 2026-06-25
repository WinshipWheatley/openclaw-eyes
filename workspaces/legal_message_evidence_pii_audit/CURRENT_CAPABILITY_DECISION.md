# Current Capability Decision

**What the Operator Can Do Now (Without OpenClaw):**
- Safely acquire and preserve the original mobile device backups, extraction database files, or exports.
- Compute SHA-256 hashes of the original extraction artifacts.
- Store the original artifacts securely outside of OpenClaw (e.g., encrypted local drives, legal hold storage).
- Document device and account ownership manually.

**What OpenClaw Can Do Now:**
- Nothing regarding raw legal message evidence. OpenClaw **must not** ingest, read, or process raw legal message history at this time. 

**Blocked Until Controls Exist:**
- Automated parsing of SMS/iMessage databases.
- Agent or LM review of messages containing PII or sensitive legal identities.
- Creation of working copies inside OpenClaw.

**Overall Verdict:** NO-GO UNTIL SPECIFIC CONTROLS EXIST. The current PII vault is a synthetic test construct (`token_vault.py`) or a basic in-memory LLM interceptor (`pii_vault.py`). There is no secure, isolated Legal Sealed evidence vault.

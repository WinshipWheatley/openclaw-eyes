# Tokenization Tier Contract

## Proposed Tier Model
- **Tier 0:** Public or intentionally publishable information.
- **Tier 1:** Internal operational information with low identity sensitivity.
- **Tier 2:** Standard PII (names, ordinary phone numbers, email addresses, usernames, addresses).
- **Tier 3:** Restricted sensitive PII (precise location, financial details, health details, intimate content, SSN/TIN).
- **Tier 4 (Legal Sealed Evidence):** Raw message history, identity mappings, attachments, case strategy, privileged material, and evidentiary data.

## Identity vs. Matter Sensitivity
Identity and matter sensitivity are two orthogonal axes. A message containing zero Tier 2 PII (e.g., "I will see you there") can still be Tier 4 Legal Sealed Evidence because its alteration or disclosure could compromise an active legal matter.

## Legal Sealed Requirements (Tier 4)
- **Separate Storage:** Untouched original evidence must live separately from working data, with OS ownership barriers.
- **Reversible Tokens:** Case-specific, reversible tokens (e.g., `PERSON_A`, `PHONE_A1`) must be used for working copies.
- **Token Vault:** A dedicated, protected token mapping service (or OS-secured SQLite vault) distinct from agent processes.
- **Strict Isolation:** Cross-case token isolation ensures the same person is not automatically linkable across unrelated matters without explicit operator bridging.
- **Audit Logging:** Every detokenization event must be logged (operator, matter, purpose, timestamp, fields revealed).
- **Evidentiary Facts Preservation:** Dates, times, message sequence, and exact wordings MUST NOT be destroyed or irreversibly redacted.

## Proposed Token Namespace
- `[PERSON_A]`
- `[PHONE_A1]` / `[PHONE_A2]`
- `[DEVICE_A1]`
- `[ACCOUNT_A1]`
- `[EMAIL_A1]`
- `[ADDRESS_A1]`
- `[LOCATION_A1]`
- `[THREAD_001]`
- `[ATTACHMENT_001]`

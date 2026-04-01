title: hitl-002-pii-vault-tokenization
profile: standard
goal: Add a PII Vault middleware/util that tokenizes sensitive content before any LLM call and supports secure detokenization after response processing.
scope:
- Implement /home/openclaw/pii_vault.py tokenization utility for emails, account-like numbers, and obvious identifiers.
- Replace detected sensitive segments with stable tokens like [SECRET_1], [SECRET_2].
- Persist mapping in-memory per-request/session and optionally encrypted store when needed.
- Add integration hook in Cassandra request flow before LLM prompt assembly.
- Add guardrails to prevent token map from being logged in plaintext.
- Add unit tests in /home/openclaw/tests/test_pii_vault.py for detection/tokenization/detokenization.
success:
- Sensitive strings are removed before LLM prompt construction.
- Tokens can be safely rehydrated when needed by trusted local path.
- Tests cover at least email + numeric identifier patterns.
verification: |
  python3 -c "from pii_vault import redact_text; print(redact_text('email a@b.com acct 1234567890')[0])"
depends_on: hitl-001-approval-pipeline-foundation
notes: |
  Keep this Python-native for current stack. A Node middleware mirror can be added later if web backend is introduced.

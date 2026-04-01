title: hitl-002c-presidio-tests-and-smoke
profile: surgical
goal: Add tests and a runnable smoke script for PIIVault tokenization/de-tokenization with name + credit card coverage.
scope:
- Add /home/openclaw/tests/test_pii_vault_presidio.py with unit tests for:
  - PERSON tokenization
  - EMAIL_ADDRESS tokenization
  - PHONE_NUMBER tokenization
  - CREDIT_CARD tokenization
  - LOCATION tokenization
  - round-trip detokenize correctness
- Add smoke script /home/openclaw/scripts/test_pii_vault_roundtrip.py:
  - input sentence includes a name and a credit card number
  - prints tokenized text and restored text
- Ensure tests are deterministic and avoid network calls.
- Document minimal dependency install command for Presidio packages in comments or notes.
success:
- Unit tests pass for entity tokenization and round-trip restoration.
- Smoke script demonstrates expected before/tokenized/after output.
verification: |
  python3 /home/openclaw/scripts/test_pii_vault_roundtrip.py
depends_on: hitl-002a-presidio-vault-class
notes: |
  Keep script lightweight and safe for local execution.

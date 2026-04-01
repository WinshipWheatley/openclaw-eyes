title: hitl-002a-presidio-vault-class
profile: standard
goal: Implement a Python-first PIIVault class using presidio-analyzer and presidio-anonymizer to tokenize and de-tokenize sensitive text for OpenClaw.
scope:
- Add or extend /home/openclaw/pii_vault.py with a modular `PIIVault` class.
- Initialize Presidio `AnalyzerEngine` for entities: PERSON, EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, LOCATION.
- Implement `tokenize(text: str) -> tuple[str, dict]` behavior that replaces entities with unique placeholders like <PERSON_1>, <EMAIL_ADDRESS_2>.
- Implement secure local-only mapping store in memory: self._vault = {"<TOKEN>": "original"}.
- Ensure deterministic token numbering within one tokenize call and no plaintext logging of sensitive values.
- Implement `detokenize(text: str) -> str` to restore placeholders from vault.
- Keep class importable and side-effect free for orchestrator usage.
success:
- PIIVault class tokenizes and detokenizes supported entities correctly.
- Placeholder format includes entity-type context and unique index.
- Vault mapping remains local in memory and is not emitted to logs.
verification: |
  python3 -c "from pii_vault import PIIVault; v=PIIVault(); t=v.tokenize('John Doe email john@example.com card 4111 1111 1111 1111')[0]; print(t); print(v.detokenize(t))"
depends_on: hitl-002-pii-vault-tokenization
notes: |
  Use Python-first implementation for current stack.
  If Presidio model deps are missing, fail gracefully with actionable error text.

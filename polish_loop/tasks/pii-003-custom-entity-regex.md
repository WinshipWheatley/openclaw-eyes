title: pii-003-custom-entity-regex
goal: Extend PII vault with custom regex entity rules for project-specific sensitive keywords.

Description:
Add custom entity recognizers for OpenClaw-specific identifiers and sensitive labels so tokenization catches project terms not covered by default Presidio recognizers.

Verification:
- Custom regex entities are loaded at startup without errors.
- Sample text containing project-specific keywords is detected and tokenized.
- Non-matching text does not trigger false positives for new entity rules.

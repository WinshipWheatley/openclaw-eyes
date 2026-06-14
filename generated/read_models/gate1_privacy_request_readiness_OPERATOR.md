# Gate 1 Privacy Request Readiness

Status: GATE1_PRIVACY_TRIGGER_READY_NO_LIVE_LM

What this proves:
- OpenClaw can classify privacy posture before a future LM1 package is built.
- Finance and private items require tokenized or summarized context.
- Raw file bodies, workbook cells, credentials, and unrelated client details stay out.

Fixtures:
- normal: LOW_METADATA (Allow metadata-only LM1 packaging; raw values still stay out by default.)
- client_finance: CLIENT_FINANCE_FILE_METADATA (Attach token/privacy declarations before LM1 packaging.)
- legal_confidential: CONFIDENTIAL_CLIENT_METADATA (Attach token/privacy declarations before LM1 packaging.)
- personal_private: PERSONAL_PRIVATE_METADATA (Attach token/privacy declarations before LM1 packaging.)
- strict_local_only: STRICT_PRIVATE_CLIENT_METADATA (Attach token/privacy declarations before LM1 packaging.)

Live models, tools, file reads, and external actions remain off.

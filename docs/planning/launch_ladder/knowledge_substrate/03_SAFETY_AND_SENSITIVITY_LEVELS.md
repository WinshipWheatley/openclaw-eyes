# Safety And Sensitivity Levels

Status: docs/test-only sensitivity contract. This file does not inspect private data and does not authorize ingestion, provider/model calls, or export.

## Default Rule

Unknown defaults restricted. Sensitive content is local-only by default.

No external model access to raw/extracted sensitive content unless sanitized through a future explicit approval path. Secrets/credentials must never be summarized into prompts.

Old business docs may contain client names, contracts, payments, tax details, publishing splits, private correspondence, or operational history.

## Sensitivity Levels

| Level | Meaning | Default posture | Allowed planning behavior | Forbidden implication |
| --- | --- | --- | --- | --- |
| `public_or_low_sensitivity` | Material already public or low risk. | Local review allowed. | May be represented in synthetic examples. | Still not permission to ingest real directories. |
| `business_internal` | Internal operations, vendor notes, invoices, procedures, non-public planning. | Local-only unless promoted. | May be classified and summarized only after future scoped ingestion approval. | Not safe for external model use by default. |
| `client_confidential` | Client/company records, private client names, deliverables, correspondence, or deal terms. | Restricted local-only. | Future app must show blocked or local-only state until operator approves scope. | Must not be exported or summarized into prompts automatically. |
| `financial_tax_accounting` | Payments, ledgers, bank/tax/accounting artifacts, invoices with sensitive details. | Restricted local-only. | Future app may classify presence and block details until explicit authority exists. | Must not imply current financial truth without accountant-grade evidence. |
| `music_law_publishing_sensitive` | Publishing splits, contracts, royalty details, rights, negotiations, catalog context. | Restricted local-only. | Future app should preserve high sensitivity and historical/current distinction. | Must not surface legal conclusions or external summaries without explicit approval. |
| `legal_sensitive` | Legal matter files, privileged context, attorney communications, LegalPrivate-adjacent material. | Blocked unless a future Legal-specific boundary exists. | This package may name the level only. | Must not inspect LegalPrivate or legal matter data. |
| `secrets_credentials` | Passwords, API keys, SSH keys, tokens, passphrases, credentials. | Always blocked. | Record only that a source is blocked due to credential risk, if discovered by a future approved classifier. | Must never be summarized into prompts, copied, unlocked, transmitted, or stored as compiled knowledge. |
| `unknown_unclassified` | Anything not yet classified. | Restricted. | Future app should show `unknown` or `blocked` until classified. | Must not be softened into confidence or treated as low sensitivity. |

## Local-First Rules

- Keep sensitive raw files and extracted text local-only by default.
- Use synthetic fixtures for planning and tests.
- Do not scan old business files in this docs/test slice.
- Do not call providers/models with raw or extracted sensitive content.
- Do not inspect Gmail, cloud drives, vaults, logs, LegalPrivate, secrets, or private directories.
- Do not let "conversation packet" mean "external model safe."

## Approval Path Placeholder

A future explicit approval path may allow sanitized summaries or specific conversation packets to leave the local machine. That path must define source scope, sensitivity filtering, evidence/freshness snapshot, redaction policy, withheld surfaces, expiry, and operator-readable purpose.

This file does not create that path.

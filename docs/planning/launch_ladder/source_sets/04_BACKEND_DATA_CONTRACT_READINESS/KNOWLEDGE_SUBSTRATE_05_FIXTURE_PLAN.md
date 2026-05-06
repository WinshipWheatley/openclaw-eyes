# Fixture Plan

Status: synthetic fixture plan only. This file names future fixture records and validation meanings; it does not create ingestion scripts, real fixtures from business files, a database, or app/backend implementation.

## Rule

Fixtures are synthetic only. Do not ingest real files. Do not scan user directories. Do not inspect private/vault/legal/business files.

## Planned Fixtures

| Fixture | Meaning | Expected validation rules |
| --- | --- | --- |
| `fixture_source_file_public_note.json` | Low-sensitivity discovered source example. | Must show `public_or_low_sensitivity`, source id/kind/hash/timestamp, and no ingestion authorization. |
| `fixture_source_file_business_internal_invoice.json` | Business-internal invoice-shaped source. | Must show `business_internal`, local-only default, payment/tax sensitivity warning, and no external model path. |
| `fixture_source_file_sensitive_contract_blocked.json` | Contract-shaped source blocked by sensitivity. | Must show `client_confidential` or `music_law_publishing_sensitive`, blocked state, and required future approval path. |
| `fixture_extracted_text_with_warning.json` | Parsed text with quality/extraction warnings. | Must show extractor, extracted timestamp, warnings, source basis, and parsed-evidence-not-truth boundary. |
| `fixture_rendered_fragment_html_and_plaintext.json` | Rich source shape preserved as HTML plus plaintext. | Must include rendered fragment id, HTML/plaintext refs, page/region, and sensitivity warning. |
| `fixture_artifact_classification_unknown.json` | Unknown/unclassified artifact. | Must default to `unknown_unclassified`, restricted posture, and no confidence-softening. |
| `fixture_claim_with_evidence.json` | Bounded evidence-backed claim. | Must include claim id/text, evidence refs, confidence, freshness, and not truth-by-default copy. |
| `fixture_claim_contradicted.json` | Conflicting claims or sources. | Must include contradiction state, conflicting claim refs, evidence refs, and no auto-resolution. |
| `fixture_compiled_note_historical_business_context.json` | Historical business context note. | Must state compiled note is interpretation, cite sources/claims, name limitations, and avoid current-state overclaiming. |
| `fixture_operator_promotion_mark_historical.json` | Operator marks a target historical. | Must include promotion id, operator, target, decision `marked_historical`, scope, timestamp, and no scope expansion. |
| `fixture_conversation_packet_safe_summary.json` | Sanitized synthetic handoff packet. | Must include included note/claim refs, withheld surfaces, sensitivity summary, freshness snapshot, and no execution/external-model authorization. |
| `fixture_blocked_secrets_source.json` | Secrets/credentials source blocked. | Must show `secrets_credentials`, always blocked, never summarized into prompts, and no copy/transmit/unlock behavior. |

## Negative Fixture Principles

- A discovered source is not an extracted source.
- Extracted text is not a compiled note.
- A compiled note is not an operator promotion.
- A claim is not truth by default.
- A conversation packet is not approval for execution or provider/model calls.
- Unknown means unknown.

## Timing

Create actual JSON fixtures only after this planning contract is accepted and the next source-set posture asks for backend/data-model fixtures. Do not create real-data fixtures.

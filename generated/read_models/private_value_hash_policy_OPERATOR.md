# Private Value Hash Policy

Purpose-bound HMAC match tokens are required for private value matching.

## Key Policy
- Protected key ref: `OPENCLAW_PRIVATE_VALUE_HMAC_KEY`
- Live integration ready: `false`
- Key material is never printed or exported.
- Test keys are not production keys.

## Hash Boundary
- Plain SHA-256 remains allowed for artifact integrity only.
- Plain SHA-256 is blocked for private names, emails, phone numbers, PO references, client labels, and source refs.
- HMAC output format: `hmac:v1:<purpose>:<digest>`.

## Blocked Uses
- plain_sha256_for_private_value_matching
- raw_value_in_read_model
- raw_value_in_log
- raw_value_in_model_context
- cross_purpose_hash_comparison
- production_use_of_test_key
- key_print_or_export
- dictionary_attack_prone_public_digest

## Authority
- No secret reveal.
- No production key exposure.
- No credential handling.
- No external action.

title: hitl-002b-presidio-integration-hooks
profile: standard
goal: Integrate PIIVault tokenization into Cassandra/LLM request path and detokenization into trusted local dashboard path.
scope:
- Add pre-LLM hook in Cassandra request flow to tokenize outgoing prompt text via PIIVault.
- Preserve token map in request/session context only (do not serialize raw PII to shared logs).
- Add post-processing hook for trusted local-only dashboard rendering to detokenize placeholders.
- Add config/toggle guard so integration can be enabled/disabled safely.
- Add negative-path handling: if PIIVault is unavailable, block unsafe send or apply strict fallback redaction.
- Add audit-safe logging that reports tokenization happened without exposing originals.
success:
- LLM-facing text is tokenized before send.
- Local dashboard can reconstruct approved data view via detokenization path.
- No plaintext PII appears in shared logs from this path.
verification: |
  python3 -c "print('integration hooks implemented')"
depends_on: hitl-002a-presidio-vault-class
notes: |
  Keep boundaries clear: tokenize before cloud/model calls, detokenize only in trusted local render paths.

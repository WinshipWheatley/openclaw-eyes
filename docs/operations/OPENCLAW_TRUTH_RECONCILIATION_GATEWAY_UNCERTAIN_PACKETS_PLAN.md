# OPENCLAW TRUTH RECONCILIATION GATEWAY UNCERTAIN PACKETS PLAN

- **Status:** Chunk 3A Docs-Only Contract
- **Objective:** Define uncertainty-aware model-boundary packets without weakening `MODEL_BLOCKED`.
- **Runtime scope:** No runtime behavior is implemented by this checkpoint.

## 1. Purpose

Truth Reconciliation Gateway v1 needs three distinct model-boundary outcomes so lower-confidence facts can be handled honestly without turning uncertainty into a bypass around source integrity.

The gateway must separate:

- **Source integrity:** whether the fact still points to an approved, intact, current source artifact.
- **Semantic certainty:** whether the claim has enough deterministic verification evidence to be treated as hard truth.

`MODEL_ALLOWED_UNCERTAIN` exists only for facts with intact provenance and acceptable source integrity where semantic verification is incomplete or lower-confidence. It must never admit facts that fail source integrity, provenance, policy, or mismatch checks.

## 2. Boundary Outcomes

### MODEL_ALLOWED_VERIFIED

Hard verified. `fact_text` may cross the model boundary and may be used directly by the answer layer.

Initial verified admission requires:

- The fact row is found.
- The matching truth registry entry is found.
- `source_file` matches the registry observed path.
- `source_file` is in `SOURCE_REGISTRY`.
- `source_content_hash` is present.
- The source file exists on disk.
- `disk_sha256(source_file) == truth_registry_entries.source_content_hash`.
- `source_content_hash_status` or current runtime equivalent is `current`.
- The transition path is a verified path such as `NO_DIFF_FOUND -> PACKET_READY -> MODEL_ALLOWED_VERIFIED`, or a successful mechanical repair path that discards stale candidates, recalls fresh data, rechecks, and reaches `RECHECK_PASSED -> PACKET_READY -> MODEL_ALLOWED_VERIFIED`.

### MODEL_ALLOWED_UNCERTAIN

Provenance intact and source integrity acceptable, but verification is incomplete, provisional, historical, or lower-confidence. `fact_text` may cross the model boundary only inside an uncertainty-aware packet with uncertainty metadata, confidence banding, provenance, and a restrictive `answer_boundary` that forces qualified language.

Initial uncertain admission requires:

- The fact row is found.
- The matching truth registry entry is found.
- `source_file` matches the registry observed path.
- `source_file` is in `SOURCE_REGISTRY`.
- `source_content_hash` is present.
- The source file exists on disk.
- `disk_sha256(source_file) == truth_registry_entries.source_content_hash`.
- `source_content_hash_status` or current runtime equivalent is `current`.
- Provenance fields needed by the uncertain packet are present or explicitly marked unavailable.
- The uncertainty reason is deterministic and explainable.
- `runtime_authority=false`.

`MODEL_ALLOWED_UNCERTAIN` is not a downgrade destination for corrupt or mismatched source material. It is a distinct model-boundary state for intact-source, lower-certainty claims.

### MODEL_BLOCKED

Unsafe, corrupt, source-mismatched, missing provenance, policy-blocked, stale after failed repair, or source-integrity-failed. `fact_text` must not cross the model boundary.

Blocked conditions include:

- Fact row missing.
- Truth registry entry missing.
- `source_file` and registry observed path disagree.
- `source_file` is not approved by `SOURCE_REGISTRY`.
- `source_content_hash` is missing.
- Source file is missing from disk.
- `disk_sha256(source_file) != truth_registry_entries.source_content_hash`.
- Hash status is not current and reconciliation is not allowed.
- Hash status repair is attempted but fresh recall and recheck do not pass.
- Policy forbids disclosure.
- Required provenance is missing rather than explicitly unavailable.

## 3. Mismatch Invalidation Remains Blocked

Source hash mismatch against an approved registry source remains `MODEL_BLOCKED`.

Reason: mismatch is a source-integrity failure, not merely semantic uncertainty. Once disk bytes differ from the recorded `source_content_hash`, the gateway can no longer prove that `fact_text` still corresponds to the approved source snapshot. Allowing that fact through as uncertain would convert `MODEL_ALLOWED_UNCERTAIN` into a loophole around the core v1 invariant.

Allowed mismatch handling remains limited to invalidation metadata when explicitly permitted by the existing reconciliation flag. The gateway must not replace `source_content_hash`, rebaseline hashes, mutate `fact_text`, ingest replacement docs, or expose blocked `fact_text`.

## 4. Candidate Uncertain Cases

These are design candidates for later implementation. They are not all implemented by this docs-only checkpoint.

- `verification_required=True` while source hash is current and provenance is intact.
- `verification_evidence_id` is missing while source registry and source hash are current.
- `historical_checkpoint` fact where the source is current, but the claim must be phrased historically rather than as present-tense hard truth.
- Extracted fact with intact source provenance and lower-confidence extraction metadata.
- Operator-promoted provisional working context that is accepted as provisional, but not runtime-verified or test-verified.

## 5. Required Uncertain Packet Fields

An uncertain packet must include:

- `status = MODEL_ALLOWED_UNCERTAIN`
- `uncertainty_status`
- `confidence_band`
- `uncertainty_reason`
- `fact_text`
- `source_file`
- `source_commit` if available
- `content_hash`
- `source_content_hash_status`
- `truth_source_id`
- `truth_status`
- `verification_required`
- `verification_evidence_id` if available
- `answer_boundary`
- `runtime_authority=false`
- `transitions`

If a field is unavailable but allowed to be unavailable, the packet must mark it explicitly rather than omitting it silently. If a field is required for source integrity or provenance and cannot be resolved, the outcome is `MODEL_BLOCKED`.

## 6. Confidence Bands

Chunk 3 should start with deterministic confidence bands instead of overfit numeric scoring.

- `high_provisional`: source integrity is current, provenance is complete, and only final deterministic verification evidence is missing or pending.
- `medium_provisional`: source integrity is current and provenance is intact, but the claim requires historical phrasing, review of extraction metadata, or other bounded qualification.
- `low_provisional`: source integrity is current and provenance is intact, but the packet depends on provisional operator-promoted working context or lower-confidence extraction metadata.

Numeric confidence scoring is deferred unless an existing deterministic scoring surface is already present. Any future numeric score must be explainable from stored fields and must not be assigned by an LLM as truth authority.

## 7. Answer Boundary Requirements

Uncertain packets must force qualified language. The answer layer must not state uncertain facts as hard truth.

Allowed qualification patterns include:

- "Based on currently available evidence..."
- "This appears to be..."
- "I would treat this as provisional..."
- "I cannot verify this as hard truth from the current deterministic checks..."

The `answer_boundary` must require the model to preserve the uncertainty status, confidence band, uncertainty reason, and provenance when using uncertain `fact_text`. It must also forbid converting uncertain facts into verified claims through phrasing, summarization, or omission of uncertainty metadata.

## 8. Implementation Guardrails

Chunk 3 implementation must not:

- Mutate SQLite as part of packet classification unless using an already-approved reconciliation path.
- Ingest new docs.
- Update source hashes.
- Replace `source_content_hash`.
- Expose `fact_text` for `MODEL_BLOCKED`.
- Wire Cassandra, Chief, or Niles.
- Add broad migrations.
- Weaken source hash mismatch blocking.
- Make LLMs authority for truth status.

Any runtime implementation must preserve the existing mismatch invalidation rule: source hash mismatch remains terminally blocked at the model boundary.

## 9. Recommended Next Chunk

Recommend landing Chunk 3A as this contract-only checkpoint. The current runtime surface still has `MODEL_ALLOWED` and `MODEL_BLOCKED`, so the safest next step is to let the contract settle before adding runtime packet behavior.

Recommend Chunk 3B as the smallest runtime implementation after this contract lands:

- Add explicit constants for `MODEL_ALLOWED_VERIFIED` and `MODEL_ALLOWED_UNCERTAIN`.
- Keep all current `MODEL_BLOCKED` conditions blocked, especially source hash mismatch.
- Add a narrow uncertain classification only after source integrity passes.
- Emit uncertainty fields and a restrictive `answer_boundary` for uncertain packets.
- Add focused tests proving verified, uncertain, and blocked behavior are distinct.
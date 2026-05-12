# OPENCLAW TRUTH RECONCILIATION GATEWAY V1 PLAN

- **Status:** Planning / Docs Checkpoint
- **Objective:** Controlled mechanical reconciliation and mandatory re-verification.

## 1. Purpose
Truth Reconciliation Gateway v1 introduces controlled, deterministic auto-reconciliation of mechanical metadata. It remains **blocking and read-only by default**. Write authority is only granted when the `--allow-reconciliation` flag is explicitly set. The goal is to resolve mechanical friction (stale hash status) while maintaining absolute truth integrity.

## 2. Core Invariant
**No stale candidate packet may cross the model boundary.** 

If any reconciliation write occurs in the database, the currently loaded candidate fact objects must be treated as toxic and discarded. The gateway must:
1. Discard current candidate facts.
2. Re-query SQLite for fresh data.
3. Re-check the recalled data against disk state.
4. Only then build a `MODEL_ALLOWED` truth packet.

## 3. Required MODEL_ALLOWED Condition
A `MODEL_ALLOWED` state can only be reached if:
- **`NO_DIFF_FOUND`**: Integrity check passed on the first attempt (v0 behavior).
- **`RECONCILIATION_APPLIED` -> `RECALLED_AFTER_RECONCILIATION` -> `RECHECK_PASSED`**: Integrity check failed initially, a repair was applied, and the fresh data passed a subsequent check.

## 4. Allowed Mechanical Repair
If `disk_sha256(source_file) == truth_registry_entries.source_content_hash` but `hash_status != 'current'`, the gateway may:
- Update `hash_status` to `'current'`.
- This repair is only allowed if `--allow-reconciliation` is set.

## 5. Allowed Mechanical Invalidation
If `disk_sha256(source_file) != truth_registry_entries.source_content_hash`, the gateway may:
- Set `hash_status = 'changed'`.
- Set `verification_required = 1`.
- Set `verification_invalidated_at = <timestamp>`.
- Set `invalidation_reason = "JIT hash mismatch detected"`.
- Downgrade `truth_status` to `'stale_possible'` **only if** the prior status was `'test_verified'` or `'runtime_verified'`.
- **Note:** This results in a `MODEL_BLOCKED` terminal state for that fact.

## 6. Forbidden Actions
V1 must **NOT**:
- Replace `source_content_hash` after a mismatch (requires explicit re-ingest).
- Mutate `fact_text`.
- Add new `SOURCE_REGISTRY` entries.
- Perform semantic truth upgrades (e.g., to `test_verified`).
- Allow LLM-authored truth updates.
- Scan drives or recursively discover files.
- Wire Cassandra/Chief/Niles (runtime consumption is separate).
- Rebaseline changed source hashes.

## 7. State Machine
- `CANDIDATE_SURFACED`: Facts identified in SQLite.
- `CHECK_RUNNING`: JIT source integrity check initiated.
- `NO_DIFF_FOUND`: Terminal success (v0 path).
- `DIFF_FOUND`: Mismatch or stale metadata detected.
- `RECONCILIATION_ALLOWED`: Repairable state and flag provided.
- `RECONCILIATION_BLOCKED`: Mismatch non-repairable or flag missing (Terminal Block).
- `RECONCILIATION_APPLIED`: SQL UPDATE committed to ledger.
- `RECALLED_AFTER_RECONCILIATION`: Old facts discarded; fresh query performed.
- `RECHECK_RUNNING`: Integrity check re-run on fresh data.
- `RECHECK_PASSED`: Integrity confirmed post-repair.
- `RECHECK_FAILED`: Integrity fails post-repair (Terminal Block).
- `PACKET_READY`: Verified facts packaged.
- `MODEL_ALLOWED`: Terminal Success.
- `MODEL_BLOCKED`: Terminal Failure.

## 8. Implementation Recommendation: Chunk 1
The first implementation phase should focus on **Mechanical Repair** only:
- Add the `--allow-reconciliation` flag to the gateway and harness.
- Preserve default read-only/blocking behavior.
- Implement the "Repair to Current" path (`disk_hash == source_hash`).
- Implement the mandatory **discard / re-query / re-check** loop.
- Add focused tests proving that no stale candidate data crosses the model boundary after a repair.

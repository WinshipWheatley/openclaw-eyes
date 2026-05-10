# OpenClaw Proof Drift Semantics v0

## Context
OpenClaw uses a deterministic proof-of-health system. Proofs are recorded in a ledger and tied to a specific Git `HEAD` hash. When new commits are made, existing proofs appear to "drift" because the current `HEAD` no longer matches the `head` recorded in the proof receipt.

In a continuous improvement loop, some commits only refresh generated read-model files (e.g., `Operator/GENERATED_CURRENT_STATE.md`). These refreshes should not invalidate the "CONFIRMED" status of proofs, as no functional code or logic has changed.

## Drift Classifications

### 1. CONFIRMED (Exact Match)
- **Status**: `PASS`
- **Relation**: `MATCH` (Current HEAD matches proof head)
- **Repo**: `CLEAN`
- **Meaning**: The proof is perfectly valid for the current state.

### 2. CONFIRMED (Safe Drift / Refresh)
- **Status**: `PASS`
- **Relation**: `DRIFT`
- **Repo**: `CLEAN`
- **Diff**: `git diff --name-only [proof_head]..HEAD` contains **only** safe generated files.
- **Meaning**: The proof is valid because only read-models or generated docs have changed.

### 3. WEAK (Dirty)
- **Status**: `PASS`
- **Repo**: `DIRTY`
- **Meaning**: The proof was recorded in a dirty repository. It might be valid, but it is not deterministic.

### 4. WEAK (Unsafe Drift)
- **Status**: `PASS`
- **Relation**: `DRIFT`
- **Diff**: Contains changes to source code, tests, or scripts.
- **Meaning**: The code has changed since the proof was recorded. The proof is no longer authoritative.

### 5. FAILING
- **Status**: `FAIL`
- **Meaning**: The proof failed. The system is unhealthy.

### 6. MISSING
- **Status**: None
- **Meaning**: No proof receipt exists for this manifest label.

## Safe Generated Files (v0)
The following files are considered safe for drift:
- `Operator/GENERATED_CURRENT_STATE.md`
- `Operator/GENERATED_NEXT_ACTIONS.md`

## Check Mode Policy
- `python3 scripts/audit_proof_coverage.py --check`
- **PASS**: `CONFIRMED (Exact Match)`, `CONFIRMED (Safe Drift)`.
- **FAIL**: `WEAK`, `FAILING`, `MISSING`.

Note: `WEAK (Dirty)` fails check mode in v0 to enforce clean proof cycles.

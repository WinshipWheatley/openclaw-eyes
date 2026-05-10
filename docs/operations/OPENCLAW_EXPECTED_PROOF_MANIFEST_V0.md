# OpenClaw Expected Proof Manifest v0

## Purpose
The Expected Proof Manifest maps deterministic proof labels to their underlying verification commands, evidence classes, and interpretation rules. It allows OpenClaw to identify which checks are expected, which are missing, and which are current, providing a ground-truth map for auditing "Business Ops Spine" health.

## v0 Proof Labels

| Label | Command | Evidence Class | Supported Surface |
|-------|---------|----------------|-------------------|
| `generated_status_check` | `python3 scripts/generate_operator_status.py --check` | `build_integrity` | Operator Status Read-Models |
| `ledger_inspector_summary` | `python3 scripts/inspect_business_ops_ledger.py --summary` | `ledger_health` | Business Ops Ledger |
| `orientation_snapshot_smoke` | `python3 scripts/orientation_snapshot.py --smoke` | `orientation_integrity` | System Orientation |
| `cassandra_status_wiring_tests` | `pytest tests/test_cassandra_status_wiring.py` | `wiring_verification` | Cassandra / Ops Integration |
| `business_ops_ledger_tests` | `pytest tests/test_business_ops_ledger.py` | `schema_integrity` | Business Ops Persistence |

## Manifest Fields Definition

- **label**: The unique identifier used in `test_proof_receipt` events.
- **command**: The exact shell command required to generate the proof.
- **evidence_class**: The category of evidence this proof provides (e.g., `build_integrity`, `wiring_verification`).
- **supported_surface**: The specific OpenClaw subsystem or document this proof validates.
- **freshness expectation**: How recently this proof should have been run (e.g., "per commit", "daily", "on demand").
- **clean-repo preferred/required**: Whether the proof requires `dirty=false` to be considered "Strong Evidence."
- **failure severity**: Impact of a failure (Low/Med/High/Critical).
- **sensitive-output risk**: Whether the command output might leak PII or secrets (must be Low for auto-reporting).
- **whether safe for morning brief**: Boolean; if true, can be summarized in the automated morning report.
- **whether safe to run manually only**: Boolean; if true, should not be invoked by autonomous agents.

## Important Doctrine

1. **A missing proof is not proof of failure.** Silence in the ledger may simply mean the check hasn't been run yet in the current window.
2. **A passing proof is not proof of whole-system health.** Proofs are narrow, deterministic slices of verification.
3. **A dirty proof is weaker than a clean proof.** Evidence recorded with uncommitted changes (`dirty=true`) is valuable for development but insufficient for "Confirmed" status.
4. **A failed proof is important evidence and should not be hidden.** Failure receipts provide critical audit trails for identifying regressions.

## Non-Goals
- **No Scheduler**: This manifest does not define *when* to run commands.
- **No Autonomous Runner**: This does not grant agents authority to execute these commands arbitrarily.
- **No Runtime Activation**: This is a documentation and auditing contract, not a runtime control system.
- **No Broad Discovery**: This is an explicit list of known-good proofs, not a generic test-discovery mechanism.
- **No Private Data Scan**: Manifested commands MUST NOT probe private roots or sensitive PII.
- **No Network/Device Probing**: Manifested commands are local-repo and ledger-centric only.
- **No Behavioral Change**: Implementing this manifest does not change the behavior of Guardian, Chief, or Cassandra.

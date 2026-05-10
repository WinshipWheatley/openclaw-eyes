# OpenClaw Evidence Sufficiency / Coverage Map v0

This document defines the deterministic evidence required for OpenClaw to claim "knowledge" of a domain. It prevents agents from hallucinating authority or speaking from stale/fuzzy memory without empirical proof.

## 1. Evidence Classes (Train Cars)

OpenClaw knowledge must be anchored to one or more of the following deterministic evidence classes:

- **repo state receipts**: Current Git HEAD, branch status, and working tree cleanliness.
- **generated status/read-model receipts**: Output from `scripts/generate_operator_status.py` and associated read-models.
- **ledger/packet receipts**: Events recorded in the SQLite Business Ops Ledger (`.openclaw/business_ops/ledger.sqlite`).
- **test/proof receipts**: Successful execution of validation scripts or unit tests.
- **runtime/service readiness receipts**: Verified heartbeat or config-check from a managed service.
- **Guardian/security check receipts**: Security policy audits and sensitive-root proximity checks.
- **subsystem morning brief receipts**: Machine-readable state summaries from independent subsystems.
- **Chief/Hermes/Cassandra lane receipts**: Explicit completion signals from specific agent lanes.
- **file/location inventory receipts**: Non-recursive, bounded directory listings or file existence proofs.
- **device/peripheral inventory receipts**: Verified connection status of local hardware (future).
- **network/node inventory receipts**: Verified status of internal network nodes (future).
- **permission/capability receipts**: Validated access tokens or OS-level permission checks.
- **external share/GitHub/email-thread scoped permission receipts**: Evidence of specific shared context (future).
- **operator promotion receipts**: Explicit instructions from the operator to promote a state or policy.
- **doctrine/manifesto compliance receipts**: Proof that a change adheres to repo-wide constraints.

## 2. Confidence Levels

Each domain is classified by its current evidence coverage:

- **Confirmed**: Sufficient deterministic evidence exists in the repository/ledger to claim truth.
- **Partially Covered**: Some evidence exists, but gaps remain or the state is transitioning.
- **Historical Only**: Information exists in logs or old files but is not verified in the current active state.
- **Unknown**: No deterministic evidence has been collected for this domain.
- **Explicitly Unsafe to Claim**: Evidence is missing AND the domain involves sensitive, risky, or side-effect-heavy actions.

## 3. Current Coverage (v0)

Based on the current repository state, the following domains are mapped:

| Domain | Confidence | Evidence Class |
| :--- | :--- | :--- |
| Orientation Snapshot | Confirmed | generated status/read-model receipts |
| Generated Status Read Models | Confirmed | repo state receipts, file inventory |
| Ledger Inspector | Confirmed | ledger/packet receipts |
| Cassandra Status Answer Path | Confirmed | test/proof receipts, ledger receipts |
| Broad Runtime Health | Unsafe to Claim | Unknown (No live heartbeat) |
| Whole-File-System Knowledge | Unknown | No broad scan allowed |
| Peripheral/Device Inventory | Unknown | No device probing implemented |
| Network/Node Map | Unknown | No network discovery implemented |
| Guardian Morning Security Brief | Planned/Partial | Needs doctrine/manifesto receipts |
| GitHub/Email-Thread Sharing | Future | No permission receipts implemented |

## 4. Grounding Rule

**A bot may not speak as if it knows a domain unless the coverage map says that domain has sufficient deterministic evidence.**

If evidence is missing, the bot must explicitly state: *"I do not have deterministic evidence for [Domain]."*

## 5. Morning Brief Growth Path

The path to human-readable synthesis must be built on a machine-contract layer first:
1. **Subsystem Reports**: Individual tools generate machine-readable status.
2. **Guardian Security Report**: Security policy audit of the state.
3. **Hermes Engineering Report**: Technical health and diff synthesis.
4. **Chief Synthesis**: High-level alignment check and prioritization.
5. **Cassandra Tasteful Human Report**: Final concise, grounded briefing for the operator.

## 6. Future Growth Pattern

1. Identify a small, reliable evidence loop.
2. Prove the loop with a test/receipt.
3. Add the evidence class to this map.
4. Inspect the evidence and generate read models.
5. Expose the domain to agents via gated capability checks.

## 7. Explicit Non-Goals

- No runtime activation of unmonitored services.
- No broad, recursive file system scans.
- No unauthorized private data access.
- No active device probing or network discovery.
- No automated external sharing without explicit operator promotion.
- No silent permission expansion.

# LAMD Monthly Auto-Send Implementation Plan

1. Add failing tests for fixed-surface drift, date eligibility, atomic monthly claims, enabled FreezeGuard at both admissions, no provider call while tripped, no automatic retry, sent verification, and idempotent G2C posting.
2. Implement the bounded orchestrator and state store with injected provider and ledger adapters.
3. Add a root brake broker, root/operator CLI, trip-only Guardian client, hardened system unit, and plan-first installer.
4. Add the daily disabled-by-default systemd service/timer and live runner that refuses unless the root-owned scope config is armed.
5. Run unit and fake-provider acceptance tests, syntax checks, and focused regressions.
6. Install only with operator-present privilege, run the exact installed clear/tripped acceptance, and arm only if all five settled gates pass.

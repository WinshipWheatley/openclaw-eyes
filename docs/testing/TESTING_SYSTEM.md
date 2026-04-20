# Testing System

This document outlines the testing strategy and hierarchy for the OpenClaw repository.

## Testing Hierarchy

1. **Smoke Tests**
   - Lightweight checks to ensure syntax and basic module loading.
   - Referenced in [RUNBOOK.md](../RUNBOOK.md).
   - Typically run manually before stack restarts.

2. **Integration Tests**
   - Validates multi-module workflows and logic (routing, brain decisions, etc.).
   - Located in the `tests/` directory.
   - Category-level groupings:
     - `test_cassandra_*`: Identity, outreach, and briefing logic.
     - `test_chief_*`: Approval, LLM routing, and session management.
     - `test_cut*`: Specialized outreach and evidence helpers.

3. **Specialized Harnesses**
   - High-fidelity staging and replay environments for complex batch or time-sensitive flows.
   - See [HARNESS_INDEX.md](./HARNESS_INDEX.md) for usage details.

## Running Tests

### Unit/Integration (pytest)
```bash
PYTHONPATH=. pytest tests/
```

### Smoke Checks
Refer to the "Smoke Tests" section of [RUNBOOK.md](../RUNBOOK.md) for module-specific one-liners.

## Test Data & Staging
- **Fixtures**: `tests/fixtures/` contains JSON/MD files for integration test cases.
- **Staging Root**: Harnesses use `staging/` to isolate file I/O during validation.

## Adding New Tests
- Use `pytest` for all new functional tests.
- Add or update the narrowest test that proves a change (Repo Rule).
- Follow existing naming patterns: `test_<module_name>.py`.

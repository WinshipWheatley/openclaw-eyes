# Ledger Invoice Steel Thread Candidate

The "Ledger Invoice Steel Thread" has been identified as a high-value first functional proof-of-concept (POC) candidate for the Operator Harness.

## Mac Source Status
- **Script**: `bank_csv_to_reconciliation_report.py` exists on the Mac.
- **Test**: Accompanying test suite exists on the Mac.
- **Capture**: `ledger_invoice_automation_capture/` contains research and logs.

## Candidate Status
- **Approved for Planning**: YES.
- **Approved for PC src Import**: NO.

## Integration Plan
1. **Sanitization**: All research notes and capture materials must be sanitized of real data before import.
2. **Review**: The script logic must be reviewed for alignment with PC architectural standards.
3. **Alignment**: Tests must be refactored to fit the PC repository's test structure.
4. **Phased Import**:
   - Step 1: Planning docs to `docs/planning/launch_ladder/ledger_invoice_steel_thread/`.
   - Step 2: Logic and Tests to `docs/research/` or similar for isolated validation.
   - Step 3: Final integration into `src/`.

## Boundary Reminder
Raw local capture materials (`local_capture/`) must remain excluded from the PC repository.

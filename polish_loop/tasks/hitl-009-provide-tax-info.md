title: hitl-009-provide-tax-info
profile: architect
goal: Securely provide the Tax ID (EIN) to Cassandra's 'Confirmed Knowledge' layer.
scope:
- Prompt Winship for the EIN/Tax ID number.
- Ensure the number is stored in a redacted or secured format in the 'Confirmed Knowledge' vault.
- Update agent prompts (Cassandra/Chief) to acknowledge that they now have this authority for financial filings.
success:
- Tax ID is available to agents for authorized filings.
- Cassandra confirms receipt.
verification: |
  python3 -c "print('Tax ID acquisition task queued')"
notes: |
  Essential for bridging the 'friction gap' in financial autonomous tasks.

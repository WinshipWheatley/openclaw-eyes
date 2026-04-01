title: test-002-pii-adversarial-testing
goal: Create adversarial PII test suite for typo and obfuscation bypass attempts.

Description:
Build a set of challenging test sentences that simulate misspellings, spacing tricks, symbol substitutions, and mixed-format identifiers to evaluate Presidio vault robustness.

Verification:
- Test suite includes at least one case each for typo, obfuscation, symbol substitution, and mixed-format attacks.
- Test run reports detection rate and lists failed cases.
- Any detected bypass case is persisted as a regression test fixture.

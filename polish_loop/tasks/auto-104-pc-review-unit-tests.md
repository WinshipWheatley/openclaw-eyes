title: auto-104-pc-review-unit-tests
goal: Add unit tests for the PC-side review fallback (pc_review_fallback.py) and verify it integrates correctly with the orchestrator.
scope:
- Write tests that validate the structural review logic in pc_review_fallback.py
- Test with valid pc_output.md (all sections present, correct PASS, STATUS:DONE)
- Test with invalid pc_output.md (missing sections, wrong PASS, STATUS:BLOCKED)
- Test file existence checking for claimed changed files
- Verify mac_review.md is correctly written with APPROVED/NEEDS_REWORK
- Do not modify the core orchestrator logic or pc_review_fallback.py unless a bug is found
success condition:
- All unit tests pass via: python3 -m pytest tests/test_pc_review_fallback.py -v
- Tests cover at least: valid approval, missing sections rejection, pass mismatch rejection, STATUS:BLOCKED rejection
blockers/dependencies:
- pc_review_fallback.py must exist at polish_loop/pc_review_fallback.py
- pytest must be available (pip install pytest if needed)
exact files likely to be touched first:
- tests/test_pc_review_fallback.py
- polish_loop/pc_review_fallback.py (only if bugs found)
verification:
```bash
cd /home/openclaw && python3 -m pytest tests/test_pc_review_fallback.py -v 2>&1 | tail -20
```

title: env-001-skill-pipeline-smoke
goal: Implement a first runnable PC-only smoke test that exercises the skill pipeline end-to-end across fixtures, loader, vetter, and search.
scope:
- Create a minimal smoke test that runs against the local fixture set.
- Verify loader can read fixture skills and return deterministic output.
- Verify vetter returns pass/fail results for the same fixture set.
- Verify search can rank at least one query against the loaded content.
- Keep the smoke test local, deterministic, and read-only.
- Do not add external service dependencies or package installs.
success condition:
- One command runs the smoke test locally on PC.
- Smoke test passes on the valid path and fails clearly on broken pipeline behavior.
- Smoke test covers fixture loading, vetting, and search in one bounded run.
- Output is deterministic enough for repeated verification.
blockers/dependencies:
- Depends on prior first-pass implementations of skill_loader, skill_vetter, search, and fixture files.
- Final exact CLI or module entrypoints may still vary slightly in early implementation.
exact files likely to be touched first:
- tests/test_skill_pipeline_smoke.py
- tests/fixtures/skills/

# ARCHIVED test strays — 2026-07-25

Moved out of tests/ because pytest tried to collect them and errored
("found no collectors"), breaking any globbed test run.

They are April editor/tool checkpoints of tests/test_chief_router_table.py.
NOTE: that live test file is UNTRACKED (gitignored), so git history does
NOT preserve these — that is why they are archived here, not deleted.

| file | bytes | sha256 |
|---|---|---|
| test_chief_router_table.py.checkpoint-20260408T220000 | 8482 | a6e62843c49fe2dd… |
| test_chief_router_table.py.checkpoint-20260409T020000 | 10105 | f5177b89d47780e8… |
| test_chief_router_table.py.checkpoint-20260409T134000 | 12143 | 40d342a64481e8bf… |
| test_chief_router_table.py.tmp | 12 | 6ae8a75555209fd6… |

Restore: `mv artifacts/archive/tests-strays-20260725/<file> tests/`

# OpenClaw Legacy Repo Intake v0

Legacy Repo Intake v0 registers a non-canonical placeholder for future old GitHub repo review.

Current placeholder:
- `root_id`: `github_legacy_openclaw`
- `root_kind`: `legacy_git_repo`
- `owner_scope`: `internal_platform`
- `canonical_status`: `non_canonical_until_promoted`
- `import_status`: `not_imported`

Commands:
- `python3 scripts/register_legacy_repo_intake.py --format operator`
- `python3 scripts/query_legacy_repo_intake.py --report summary --format operator`
- `python3 scripts/query_legacy_repo_intake.py --report roots --format operator`
- `python3 scripts/query_legacy_repo_intake.py --report promotion-candidates --format operator`
- `python3 scripts/query_legacy_repo_intake.py --report risks --format operator`

Boundary:
- No network access.
- No clone.
- No file import.
- No copying legacy code into the current repo.
- No truth promotion.
- Future intake requires a separate bounded lane, operator review, and promotion gates.

# OpenClaw Tool Intake Registry v0

Tool Intake Registry v0 records candidate policy metadata for useful external tools.

It writes a separated `tool_intake_*` namespace into `.openclaw/business_ops/ledger.sqlite` and links candidates to `tool_inventory_*` observations where possible.

## Boundary

- Candidate does not mean approved.
- Installed does not mean approved.
- Detected does not mean integrated.
- Sandbox later does not mean install.
- No candidate row authorizes installation, execution, integration, network access, model use, container use, remote access, runtime activation, or agent activation.

## Tables

- `tool_intake_runs`
- `tool_candidates`
- `tool_candidate_labels`
- `tool_candidate_use_cases`
- `tool_candidate_risks`
- `tool_candidate_inventory_links`
- `tool_candidate_status_history`

## Commands

```bash
python3 scripts/build_tool_intake.py --format operator
python3 scripts/query_tool_intake.py --report summary --format operator
python3 scripts/query_tool_intake.py --report category --category sqlite_exploration --format operator
python3 scripts/query_tool_intake.py --report high-fit --format operator
python3 scripts/query_tool_intake.py --report high-risk --format operator
python3 scripts/query_tool_intake.py --report sandbox-later --format operator
python3 scripts/query_tool_intake.py --report client-capsule --format operator
python3 scripts/query_tool_intake.py --report installed-candidates --format operator
python3 scripts/query_tool_intake.py --report not-detected-candidates --format operator
```

## Future Use

This registry is an intake and review surface only. Any future tool install, sandbox, integration, deployment, local-model, sync, or client-capsule lane needs its own explicit scope, tests, and operator approval path.

# Next Agent Migration Implementation Spec v0

## Stage 2 Lane

Recommended Stage 2 lane: `Modular Capability Migration Substrate v0`.

Stage 2 should implement local deterministic substrate only. It must not port Repo B, create live listeners, create send paths, inspect secrets/private data, run Repo B, create client repos, deploy anything, or activate daemons/watchdogs.

OpenClaw Core remains canonical. Stage 2 module and bundle records must keep `runtime_authority=false` unless a later explicit approval lane changes that boundary.

## Repo A Surfaces To Inspect First

Stage 2 should inspect these Repo A files first:

- `module_registry.py`
- `project_capsule.py`
- `report_bridge.py`
- `operator_intent_core.py`
- `intent_router.py`
- `telegram_agent_intake.py`
- `operator_action_inbox.py`
- `operator_action.py`
- `hitl_action_service.py`
- `hitl_pending_store.py`
- `work_board.py`
- `agent_work_packet.py`
- `openclaw_sensitive_policy.py`
- `scripts/build_module_registry.py`
- `scripts/query_module_registry.py`
- `scripts/export_read_models.py`
- `scripts/generate_operator_status.py`
- existing tests for module registry, Project Capsule, Report Bridge, intent router, Work Board, Agent Work Packet, and Telegram intake.

## Existing Surface Findings

An operator intent inbox-like surface already exists as:

- `telegram_agent_intake.py` for governed Telegram-facing update records.
- `intent_router.py` for deterministic `intent_records`.
- `operator_action_inbox.py` for imported action request files.

Work Board projection APIs already exist:

- `work_board.build_work_board(...)`
- `work_board.export_work_board_read_model(...)`
- `telegram_agent_intake.record_telegram_update(..., create_work_board_card=True)`
- `agent_work_packet.build_agent_work_packet(...)`

Agent Work Packet already exists:

- `agent_work_packet.py`
- `scripts/build_agent_work_packet.py`
- `scripts/export_agent_work_packets_read_model.py`

Project/client planning already exists:

- `project_capsule.py`
- `scripts/create_project_capsule.py`
- `scripts/query_project_capsules.py`
- `generated/project_capsules/demo_project_capsule_v0/`

Report Bridge already exists:

- `report_bridge.py`
- `scripts/import_report_bridge_package.py`
- `scripts/query_report_bridge.py`

Sensitivity policy already exists:

- `openclaw_sensitive_policy.py`

## Approved Module Registry Home

The approved module registry should live in `module_registry.py`. Do not create a duplicate registry unless a later inspection proves the existing registry cannot be extended safely.

Stage 2 should extend `module_registry.py` to support the doctrine fields:

- `version`
- `display_name`
- `world`
- `capabilities`
- `required_inputs`
- `optional_inputs`
- `sensitive_input_policy`
- `no_go_data_classes`
- `allowed_authority_level`
- `dependencies`
- `tests_required`
- `client_safe`
- `core_only`
- `report_bridge_summary_allowed`
- `status`
- `evidence_basis`
- `runtime_authority=false`

Seed conservative records:

- `chief_intent_routing`
- `cassandra_clara_fact_intake`
- `guardian_hitl_gate`
- `niles_album_matrix`
- `hermes_next_lane_advisory`
- `planner_runner_registry`
- `report_bridge_sanitized_summary`
- `project_capsule_bundle_blueprint`

Use `draft` or `blocked` unless implementation is already proven. Do not claim runtime implementation.

## Bundle Blueprint Planner Home

Create a new local deterministic module only if no equivalent exists:

- proposed file: `bundle_blueprint_planner.py`
- proposed scripts:
  - `scripts/plan_bundle_blueprint.py`
  - `scripts/export_bundle_blueprint_status.py`

The planner should accept structured pain-point text and target context, then produce a local manifest dictionary. It must not create repos, scan private files, call models, call APIs, write external paths, deploy, send, or shell out.

The manifest must set:

- `github_packaging_allowed=false`
- `deployment_allowed=false`
- `runtime_authority=false`

## Unified Governed Intake Spine Home

Do not duplicate the existing `intent_router.py` and `telegram_agent_intake.py` path. Add a small bridge only if needed:

- proposed file: `governed_intake_spine.py`
- proposed script: `scripts/query_governed_intake_spine.py`

The bridge should accept raw operator text and source metadata, call deterministic Repo A logic, create a governed intent record, optionally build a Work Board card or Agent Work Packet through existing APIs, and expose authority flags. It must store only bounded previews/hashes through existing router behavior.

If Work Board projection does not fit without broad refactor, Stage 2 should stop that subpart and record a blocker.

## Generated Read-Model Handling

`generated/read_models` is a checked-in generated-artifact path in this repo. Existing patterns prefer dedicated build/export functions and scripts, plus tests, rather than untracked manual outputs.

Stage 2 should add dedicated read-model export visibility for new substrate surfaces where straightforward:

- `generated/read_models/approved_module_registry.json`
- `generated/read_models/approved_module_registry_OPERATOR.md`
- `generated/read_models/bundle_blueprint_planner.json`
- `generated/read_models/bundle_blueprint_planner_OPERATOR.md`
- `generated/read_models/governed_intake_spine.json`
- `generated/read_models/governed_intake_spine_OPERATOR.md`

Do not integrate these into central `scripts/export_read_models.py` unless it is a small, well-tested addition. If central integration is non-trivial, leave it for a later lane and keep dedicated exporters.

## Exact Proposed Stage 2 Files

Create or update only the smallest safe set:

- update `module_registry.py`
- update `scripts/build_module_registry.py`
- update `scripts/query_module_registry.py`
- add `scripts/export_approved_module_registry_read_model.py` if needed
- add `bundle_blueprint_planner.py`
- add `scripts/plan_bundle_blueprint.py`
- add `scripts/export_bundle_blueprint_planner_read_model.py`
- add `governed_intake_spine.py`
- add `scripts/query_governed_intake_spine.py`
- add or update tests:
  - `tests/test_module_registry.py`
  - `tests/test_bundle_blueprint_planner.py`
  - `tests/test_governed_intake_spine.py`
  - `tests/test_agent_capability_migration_map.py`

## Stage 2 Tests

Tests should prove:

- module records load deterministically.
- new module records include authority, sensitivity, client safety, and report bridge fields.
- no module implies runtime authority.
- blocked/draft/client-safe/core-only fields behave as expected.
- bundle planning maps pain points conservatively.
- private/sensitive needs become `local_only_required` or `needs_operator_review`.
- GitHub packaging, deployment, and runtime authority are false.
- raw operator text becomes a deterministic governed intent record.
- unknown intent becomes review/triage, never execution.
- Work Board/Agent Work Packet projection works only through existing APIs.
- no LLM/API/network/subprocess calls are introduced.
- legacy daemon/watchdog surfaces are not imported or executed.
- migration map controlled vocabulary remains valid.

## Validation Commands

Run the narrowest complete validation:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/test_agent_capability_migration_map.py \
  tests/test_module_registry.py \
  tests/test_bundle_blueprint_planner.py \
  tests/test_governed_intake_spine.py \
  tests/test_intent_router.py \
  tests/test_work_board.py \
  -q
```

If central export integration is touched:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/export_read_models.py --check
```

If generated operator status is touched:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/generate_operator_status.py --check
```

Always run:

```bash
git diff --check
git diff --cached --check
git status -sb --untracked-files=all
```

## Stop Conditions

Stop Stage 2 if:

- Stage 1 artifacts are missing or contradict the repo.
- existing APIs require broad refactor.
- Repo B code would need to be run or imported.
- secrets, env files, raw private data, raw client data, bank data, raw spreadsheet cells, or sensitive Telegram logs would need inspection.
- network access, model calls, Telegram send/reply, SMTP, portal submission, repo creation, deployment, daemon loops, arbitrary shell, or runtime activation would be needed.
- central generated read-model integration becomes broad.
- tests fail for unclear reasons.
- the work becomes a broad agent rebuild.

## Commit and Push

If Stage 2 validation passes, commit with:

`feat(modules): add governed capability migration substrate`

Push to `origin/main` if possible. If SSH fails, HTTPS push is acceptable. If network/auth fails, leave the commit local and report exact status.

## Stage 2 Avoidance List

Stage 2 must avoid:

- copying Repo B runtime code.
- enabling Telegram, SMTP, Gmail, Calendar, or any external send path.
- using Claude, provider APIs, or model calls.
- creating client/customer repositories.
- deploying or packaging to GitHub.
- activating runtime services.
- adding watchdogs, daemons, loops, or arbitrary command execution.
- modifying Mission Control.
- touching `polish_loop/tasks`.

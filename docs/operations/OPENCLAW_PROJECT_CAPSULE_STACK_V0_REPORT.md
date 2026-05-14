# OpenClaw Project Capsule Stack v0 Report

Date: 2026-05-14

## Phases Completed

- Phase 1: Project Capsule v0 synthetic demo contract.
- Phase 2: Project Capsule generated read-model export.
- Phase 3: Synthetic demo capsule template export.
- Phase 4: Legacy GitHub Repo Intake v0 placeholder contract.
- Phase 5: Module / Capability Registry v0.
- Phase 6: Demo capsule to planning-safe module selection.
- Phase 7: Mission Control read-model refresh prompt/spec.
- Phase 8: Scoped validation and handoff report.

No phases were skipped or stopped.

## Changed Files

Core modules:
- `.gitignore`
- `project_capsule.py`
- `legacy_repo_intake.py`
- `module_registry.py`

Scripts:
- `scripts/create_project_capsule.py`
- `scripts/query_project_capsules.py`
- `scripts/export_project_capsule_read_model.py`
- `scripts/export_project_capsule_template.py`
- `scripts/register_legacy_repo_intake.py`
- `scripts/query_legacy_repo_intake.py`
- `scripts/build_module_registry.py`
- `scripts/query_module_registry.py`
- `scripts/update_project_capsule_modules.py`

Tests:
- `tests/test_project_capsule.py`
- `tests/test_project_capsule_read_model.py`
- `tests/test_project_capsule_template.py`
- `tests/test_legacy_repo_intake.py`
- `tests/test_module_registry.py`
- `tests/test_mission_control_read_model_refresh_prompt.py`

Docs/generated:
- `docs/operations/OPENCLAW_PROJECT_CAPSULE_V0.md`
- `docs/operations/OPENCLAW_LEGACY_REPO_INTAKE_V0.md`
- `docs/operations/OPENCLAW_MODULE_REGISTRY_V0.md`
- `docs/operations/MISSION_CONTROL_READ_MODEL_REFRESH_V0_PROMPT.md`
- `docs/operations/OPENCLAW_PROJECT_CAPSULE_STACK_V0_REPORT.md`
- `generated/read_models/project_capsules.json`
- `generated/read_models/project_capsules_OPERATOR.md`
- `generated/project_capsules/demo_project_capsule_v0/`

## Schemas Added

`project_capsule_*`:
- `project_capsule_runs`
- `project_capsules`
- `project_capsule_worlds`
- `project_capsule_tools`
- `project_capsule_boundaries`
- `project_capsule_receipt_requirements`
- `project_capsule_read_model_requirements`
- `project_capsule_next_moves`
- `project_capsule_modules`

`legacy_repo_intake_*`:
- `legacy_repo_intake_runs`
- `legacy_repo_intake_roots`
- `legacy_repo_intake_risks`

`module_registry_*`:
- `module_registry_runs`
- `module_registry_modules`
- `module_registry_required_inputs`
- `module_registry_generated_outputs`
- `module_registry_dependencies`

## Demo Capsule Summary

- `project_id`: `demo_project_capsule_v0`
- `client_id`: `demo_client`
- Name: Demo Client Operations Helper
- Status: `draft`
- Approval: `not_approved`
- Worlds: `build`, `communications`, `operations`
- Candidate tools: `copier`, `datasette`, `pocketbase`, `sqlite_utils`
- Boundaries: 3 allowed metadata classes, 4 forbidden/no-go classes
- Receipt requirements: 3
- Read-model requirements: 4
- Next moves: 3
- Selected modules: 7, all `not_activated`

## Read-Model Export Summary

- Exported `generated/read_models/project_capsules.json`.
- Exported `generated/read_models/project_capsules_OPERATOR.md`.
- Capsule count: 1.
- Demo capsule appears with 7 selected modules.
- All authority flags are false.

## Template Output

Path:
- `generated/project_capsules/demo_project_capsule_v0/`

Files:
- `README.md`
- `CAPSULE_CONTRACT.md`
- `BOUNDARIES.md`
- `RECEIPTS_PLAN.md`
- `READ_MODELS_PLAN.md`
- `TOOL_POLICY.md`
- `DEPLOYMENT_NOT_AUTHORIZED.md`
- `SUPPORT_POSTURE.md`
- `NEXT_SAFE_MOVE.md`
- `capsule.json`

## Legacy Root Placeholder

- `root_id`: `github_legacy_openclaw`
- `root_kind`: `legacy_git_repo`
- `owner_scope`: `internal_platform`
- `canonical_status`: `non_canonical_until_promoted`
- `import_status`: `not_imported`
- Imported roots: 0
- Promoted roots: 0
- Network/clone/file-import/truth-promotion flags: false

## Module Registry Summary

- Modules: 9
- Dependencies: 14
- Status counts: `available_planning=8`, `future_gated=1`
- Authority levels: `metadata_only=5`, `planning_only=2`, `read_only=2`
- Client-capsule suitability: `high=5`, `medium=4`

Demo capsule selected:
- `project_capsule`
- `corpus_atlas`
- `evidence_kettle`
- `context_selection`
- `tool_inventory`
- `tool_intake`
- `read_model_shuttle`

All selected modules remain `not_activated`.

## Mission Control Prompt

Prompt/spec path:
- `docs/operations/MISSION_CONTROL_READ_MODEL_REFRESH_V0_PROMPT.md`

It instructs the future Mac/Xcode lane to read:
- `context_selection.json`
- `project_capsules.json`
- `tool_inventory.json`
- `tool_intake.json`

It requires read-only display, no writes, no network, no backend execution, no action buttons, and no runtime/agent/tool activation.

## No-Authority Posture

- `runtime_authority=false`
- `deployment_authority=false`
- `client_data_access=false`
- `agent_activation_allowed=false`
- `tool_execution_allowed=false`
- `network_authority=false`
- `approval_status=not_approved`

No real client data, deployment, runtime activation, agent activation, Docker/Ollama execution, package install, network API, SSH/SCP/rsync, remote management, credential creation, or Mission Control app edit was introduced.

## Validation

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest \
  tests/test_project_capsule.py \
  tests/test_project_capsule_read_model.py \
  tests/test_project_capsule_template.py \
  tests/test_legacy_repo_intake.py \
  tests/test_module_registry.py \
  tests/test_mission_control_read_model_refresh_prompt.py \
  tests/test_context_selection.py \
  tests/test_context_selection_read_model.py \
  tests/test_evidence_kettle.py \
  tests/test_corpus_atlas.py \
  tests/test_tool_inventory.py \
  tests/test_tool_inventory_read_model.py \
  tests/test_tool_intake.py \
  tests/test_tool_intake_read_model.py \
  tests/test_read_model_shuttle.py \
  -q
```

Result:
- `98 passed in 47.10s`

## Recommended Next Lane

Recommended:
- Mission Control Read-Model Refresh v0 on the Mac, after syncing `project_capsules.json` and `project_capsules_OPERATOR.md` to the Mac generated read-model mirror.

Alternates:
- Legacy GitHub Repo Intake v0 live audit, still manifest/metadata-only and non-canonical.
- Project Capsule v0 operator review, before any real-client or deployment design.

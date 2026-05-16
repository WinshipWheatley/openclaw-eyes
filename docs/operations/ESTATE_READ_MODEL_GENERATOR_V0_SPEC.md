# Estate Read-Model Generator v0 Spec

## Purpose

Estate Read-Model Generator v0 should expose OpenClaw Core / Estate Hub topology without creating a new Estate Registry schema.

The generator must be a metadata-only read-model over existing Repo A primitives:

- static backend node/component schema definitions
- Corpus Atlas root registry metadata
- Project Capsule capsule/module links
- Module Registry capability posture
- generated read-model file posture
- Mac mirror/read-model mirror reports

It must not scan private roots, run Repo B code, activate runtime services, create client repos, send messages, deploy, or modify Mission Control.

## Architecture Choice

Three approaches were considered:

1. Add a new `estate_registry_*` schema.
   - Pro: direct tables for estate views.
   - Con: violates the current topology finding and duplicates `openclaw_nodes`, `corpus_roots`, and `project_capsule_*`.
   - Decision: reject.

2. Add a broad Mission Control or central export integration first.
   - Pro: one place to surface everything.
   - Con: expands into UI/export infrastructure while `export_read_models.py` and generated status checks already have unrelated stale outputs.
   - Decision: defer.

3. Build a dedicated generated read-model from existing primitives.
   - Pro: narrow, testable, non-authorizing, and follows existing dedicated exporter patterns.
   - Con: another read-model file pair, but no new canonical state.
   - Decision: recommended.

## Existing Primitives Prompt 2 Should Use

Prompt 2 should use these existing primitives, in this order:

1. `backend_sqlite_schema.py`
   - Use `sqlite_physical_schema_table("openclaw_nodes")`.
   - Use `sqlite_physical_schema_table("runtime_components")`, `component_capabilities`, `node_heartbeats`, and `component_heartbeats` only as static schema metadata.
   - Do not create, populate, or promote node records.

2. `backend_sqlite_runtime.py`
   - Relevant for tests only.
   - `create_in_memory_connection()`, `sqlite_runtime_table_columns()`, and related helpers can prove static schema shape in an isolated in-memory database.
   - Do not create a file-backed estate runtime database in Prompt 2.

3. `corpus_atlas.py`
   - Use `build_atlas_report()` and `query_report_section(section="multi-root")` for `corpus_roots` visibility.
   - Use `query_report_section(section="generated-read-models")` where generated read-model artifact rows are already recorded.
   - Do not run a broad corpus scan to make the estate read-model look fuller.

4. `project_capsule.py`
   - Use `build_project_capsule_report()` for capsule summaries.
   - Use `get_project_capsule()` for capsule detail, including `worlds`, `tools`, `boundaries`, `receipt_requirements`, `read_model_requirements`, `next_moves`, and `modules`.
   - Use module links from `project_capsule_modules` only as planning selections; they do not activate modules.

5. `module_registry.py`
   - Use the approved module registry read-model builder or seeded module registry metadata for module posture.
   - Include statuses, authority levels, `client_safe`, `core_only`, and `runtime_authority=false`.
   - Do not claim draft modules are implemented.

6. `generated_read_model_files.py`
   - Use `canonical_generated_read_model_records()` or `canonical_generated_read_model_expected_files()` to enumerate safe top-level `generated/read_models` files.
   - Respect `NO_GO_PARTS` and `NO_GO_FILE_HINTS`.
   - Do not include manifest, credential, token, private, ledger, SQLite, finance, legal, tax, or temporary files.

7. `mac_mirror_atlas.py`
   - Follow `query_mac_mirror_report_section(section="generated-read-model-mirror")`, `mac-roots`, and `mirrors` patterns.
   - Do not use `build_root_manifest()` in the estate generator because that path may inspect local paths and uses git subprocess metadata.
   - Do not import root manifests unless a later explicit lane asks for manifest import.

## Helper Availability Findings

`openclaw_nodes` is available through static schema constants and table-definition helpers only:

- `OPENCLAW_NODES_COLUMNS`
- `sqlite_physical_schema_table("openclaw_nodes")`
- `sqlite_physical_schema_table_names()`

There is no Repo A helper that returns live/current `openclaw_nodes` rows as estate topology data. Prompt 2 should represent this as:

- `node_schema_available=true`
- `node_records_proven=false` unless a current read-only data source already exists
- `node_data_source="static_backend_schema_only"`

`corpus_roots` is accessible through existing Corpus Atlas helpers:

- `build_atlas_report()`
- `query_report_section(section="multi-root")`

Low-level root helpers such as `_insert_root()` and `_root_registry()` are private implementation details. Prompt 2 should not depend on private helpers for production behavior. Tests may use public atlas builders or controlled SQLite fixtures, but should not run broad scans of `/home/openclaw`.

`project_capsule.py` exposes capsule/module link data through:

- `build_project_capsule_report()`
- `get_project_capsule()`
- `link_project_capsule_modules()` for tests or existing demo setup only

The returned capsule detail includes the `modules` array from `project_capsule_modules` with `module_id`, `selection_status`, `activation_status`, `authority_posture`, `runtime_authority`, `operator_review_required`, `source_basis`, and `notes`.

## Read-Model Pattern To Follow

Prompt 2 should follow the dedicated exporter pattern already used by:

- `scripts/export_project_capsule_read_model.py`
- `scripts/export_approved_module_registry_read_model.py`
- `scripts/export_bundle_blueprint_planner_read_model.py`
- `scripts/export_governed_intake_spine_read_model.py`

The generator should expose a pure builder, a formatter, and an exporter:

- `build_estate_read_model(...)`
- `format_estate_read_model(...)`
- `export_estate_read_model(...)`

The exporter should write checked-in generated artifacts under `generated/read_models/`.

## Exact Output Files Prompt 2 Should Create

Prompt 2 should create:

- `estate_read_model.py`
- `scripts/export_estate_read_model.py`
- `scripts/query_estate_read_model.py`
- `tests/test_estate_read_model.py`
- `generated/read_models/estate_read_model.json`
- `generated/read_models/estate_read_model_OPERATOR.md`

Prompt 2 may update:

- `.gitignore`, only if new root module/script/test files are ignored by the existing allowlist pattern.

Prompt 2 should not update:

- `scripts/export_read_models.py`
- `scripts/generate_operator_status.py`
- Mission Control code
- `polish_loop/tasks`
- Repo B files

## Required JSON Schema Fields

`generated/read_models/estate_read_model.json` should include at least:

- `schema_version`: `estate_read_model_v0`
- `read_model_version`: `estate_read_model_v0`
- `generated_at`
- `mode`: `metadata_only_estate_topology`
- `source_basis`
- `source_ledger_namespaces`
- `openclaw_core`
- `backend_node_schema`
- `corpus_roots`
- `project_capsules`
- `module_registry`
- `generated_read_models`
- `mac_mirror`
- `counts`
- `gaps`
- `recommended_next_lane`
- `claims_not_made`
- `authority_flags`
- top-level authority booleans:
  - `new_estate_schema_created=false`
  - `runtime_authority=false`
  - `deployment_allowed=false`
  - `repo_creation_allowed=false`
  - `network_authority=false`
  - `send_allowed=false`
  - `raw_client_content_required=false`
  - `private_data_accessed=false`
  - `mission_control_modified=false`

Recommended section details:

- `backend_node_schema`
  - `openclaw_nodes_schema_available`
  - `node_records_proven`
  - `tables`
  - each table: `table_name`, `related_schema_contract_surface`, `columns`, `retrieval_structure_fields`

- `corpus_roots`
  - `source`
  - `status`
  - `roots`
  - each root: `root_id`, `root_kind`, `host_kind`, `owner_scope`, `project_id`, `client_id`, `instance_id`, `root_label`, `status`, `canonical_status`, `import_status`, `mirror_of_root_id`, `lineage_source`, `path_display`, `path_redacted`

- `project_capsules`
  - `status`
  - `capsule_count`
  - `capsules`
  - each capsule: `project_id`, `client_id`, `project_name`, `owner_scope`, `status`, `approval_status`, `runtime_authority`, `deployment_authority`, `client_data_access`, `next_safe_move`, `selected_worlds`, `selected_modules`, `blocked_boundaries`

- `module_registry`
  - `module_count`
  - `modules`
  - each module: `module_id`, `status`, `allowed_authority_level`, `client_safe`, `core_only`, `runtime_authority`, `report_bridge_summary_allowed`

- `generated_read_models`
  - `safe_file_count`
  - `critical_files`
  - `files`
  - each file: `relative_path`, `size_bytes`, `sha256`, `hash_algorithm`

- `mac_mirror`
  - `generated_read_model_mirror`
  - `mac_roots`
  - `mirror_counts`
  - `missing_expected_files`
  - `extra_files`
  - `hash_mismatch_files`

## Required Operator Markdown Sections

`generated/read_models/estate_read_model_OPERATOR.md` should include:

- title: `# Estate Read-Model v0`
- "What this is"
- "What this is not"
- "Core / Node Schema"
- "Corpus Roots"
- "Project Capsules"
- "Modules"
- "Generated Read-Models"
- "Mac Mirror"
- "Gaps"
- "Authority Boundary"
- "Next Safe Move"

The operator Markdown must stay compact. It should summarize counts and high-signal gaps rather than listing every generated file if the list is long.

## Summarization And Redaction Rules

Prompt 2 must summarize or redact:

- raw client/customer data
- bank, tax, legal, CPA, spreadsheet-cell, inbox-body, Telegram-log, and credential/token material
- raw private file paths outside known internal OpenClaw roots
- raw SQLite row bodies or ledger internals beyond safe metadata fields
- raw manifest bodies
- raw runtime logs

Path handling:

- Internal known paths such as `/home/openclaw` may be displayed when they are already source-root metadata.
- Client/project/runtime roots must not display raw absolute paths. Use `path_redacted=true`, a stable hash, and safe metadata fields such as `root_id`, `root_kind`, `host_kind`, `owner_scope`, `project_id`, `client_id`, and `instance_id`.
- Mac mirror roots should be summarized from existing `corpus_roots` / `mac_mirror_atlas` metadata; do not crawl or verify Mac paths.

Content handling:

- Generated read-model files may be hashed and listed if `generated_read_model_files.py` marks them safe.
- Do not read generated files rejected by `NO_GO_PARTS` or `NO_GO_FILE_HINTS`.
- Do not include raw read-model body text in the estate read-model.

## Central Export Integration

Defer `scripts/export_read_models.py` integration.

Reason:

- The central exporter currently owns a specific standardized export set.
- Recent module/bundle/intake read-models use dedicated exporters.
- Existing `scripts/export_read_models.py --check` may fail due unrelated stale `helm_state.*` and `evidence_freshness.*`.

Prompt 2 should add a dedicated estate exporter and generated files only. A later lane can decide whether estate read-models join the central export set.

## Generated Operator Status Integration

Defer `scripts/generate_operator_status.py` integration.

Reason:

- It is a broad operator-state generator.
- Existing checks may fail due unrelated `Operator/GENERATED_CURRENT_STATE.md` drift.
- Prompt 2 should not expand the lane into generated status normalization.

## Generated Files

Generated files should be checked in if produced by the dedicated estate exporter:

- `generated/read_models/estate_read_model.json`
- `generated/read_models/estate_read_model_OPERATOR.md`

Do not hand-edit generated files. Generate them by running `scripts/export_estate_read_model.py`.

## Exact Prompt 2 Tests

Prompt 2 should add `tests/test_estate_read_model.py` proving:

- no new estate schema/table is created
- `openclaw_nodes` is represented from static schema metadata when no row helper exists
- `corpus_roots` are read through public Corpus Atlas report helpers or controlled fixtures
- `project_capsule` details include selected module links without activation authority
- generated read-model files are enumerated through `generated_read_model_files.py` filters
- private/client root paths are redacted
- all top-level authority flags are false
- no Repo B import or execution path exists
- no subprocess/network/send/deployment/repo creation path exists in `estate_read_model.py` or its scripts
- exporter writes JSON and operator Markdown under a supplied temp export root

Prompt 2 may also run existing focused tests:

- `tests/test_project_capsule_read_model.py`
- `tests/test_corpus_atlas.py`
- `tests/test_mac_mirror_atlas.py`

## Prompt 2 Validation Commands

Prompt 2 should run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_estate_read_model.py tests/test_project_capsule_read_model.py tests/test_corpus_atlas.py tests/test_mac_mirror_atlas.py -q
PYTHONDONTWRITEBYTECODE=1 python3 scripts/export_estate_read_model.py --format operator
PYTHONDONTWRITEBYTECODE=1 python3 scripts/query_estate_read_model.py --format operator
python3 -m json.tool generated/read_models/estate_read_model.json >/dev/null
git diff --check
git diff --cached --check
git status -sb --untracked-files=all
```

Prompt 2 should not require `scripts/export_read_models.py --check` or `scripts/generate_operator_status.py --check` for acceptance in this lane. If it runs them, it should report unrelated stale outputs without fixing them.

## Prompt 2 Stop Conditions

Stop Prompt 2 if implementation would require:

- a new `estate_*` SQLite schema or table
- private/client/raw data access
- raw bank, spreadsheet, tax, legal, inbox, Telegram log, or credential data
- Repo B execution or imports
- network, send, SMTP, Telegram, portal, deployment, or GitHub repo creation
- Mission Control UI changes
- Chief tenant-awareness implementation
- runtime activation, daemons, watchdogs, or service restarts
- broad corpus scans of `/home/openclaw` or private roots
- central `scripts/export_read_models.py` integration to make validation pass
- generated operator status normalization
- touching `polish_loop/tasks`
- broad refactors to Corpus Atlas, Project Capsule, Module Registry, or Mac Mirror Atlas

## Prompt 2 Readiness Decision

Prompt 2 is ready if it stays within the dedicated read-model/exporter path above.

No new estate schema is needed. Raw client contents are not required. Central export and generated status integration should be deferred.

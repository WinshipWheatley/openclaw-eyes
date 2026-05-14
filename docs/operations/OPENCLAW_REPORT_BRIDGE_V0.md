# OpenClaw Report Bridge v0

Purpose: import sanitized local report packages from known nodes into the
Business Ops ledger without creating a transport system or granting authority.

Default inbox:

```text
/mnt/e/openclaw/node_uplink/inbox
```

Package shape:

```text
report_bridge_manifest.json
payload/read_models/
payload/receipts/
payload/reports/
payload/artifacts_metadata/
README_NODE_UPLINK.md
```

## Boundary

- Report Bridge is metadata and safe report/read-model file records only.
- Package arrival is not approval, freshness, truth, runtime authority, or deployment authority.
- No source package is deleted, moved, renamed, archived, or reorganized.
- No raw bodies or real client data are accepted by default.
- No network, remote management, SSH, SCP, rsync, Docker, Ollama, model, tool, runtime, or agent behavior is introduced.
- The standard transfer/drop root is `E:\openclaw` / `/mnt/e/openclaw`; `C:\openclaw` is not a Report Bridge default.

## Manifest

Required manifest fields:

- `schema_version`: `openclaw.report_bridge.v0`
- `package_id`
- `generated_at`
- `node_id`
- `node_kind`
- `owner_scope`
- `project_id`, nullable
- `client_id`, nullable
- `package_kind`
- `source_root_id`
- `files`
- `sensitivity_summary`
- `allowed_data_classes`
- `forbidden_data_classes`
- `no_authority_flags`

Required no-authority flags must all be `false`:

- `runtime_authority`
- `deployment_authority`
- `remote_management_allowed`
- `agent_activation_allowed`
- `tool_execution_allowed`
- `model_execution_allowed`
- `container_execution_allowed`
- `network_authority`
- `truth_promotion_allowed`

Accepted file roles:

- `read_model`
- `operator_report`
- `report`
- `receipt_summary`
- `artifact_metadata`

## Commands

Import an explicit package:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/import_report_bridge_package.py \
  --package /mnt/e/openclaw/node_uplink/inbox/PACKAGE_FOLDER \
  --format operator
```

Import the newest package from the default inbox:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/import_report_bridge_package.py --format operator
```

Reports:

```bash
python3 scripts/query_report_bridge.py --report summary --format operator
python3 scripts/query_report_bridge.py --report packages --format operator
python3 scripts/query_report_bridge.py --report rejected --format operator
python3 scripts/query_report_bridge.py --report nodes --format operator
python3 scripts/query_report_bridge.py --report projects --format operator
python3 scripts/query_report_bridge.py --report latest --format operator
```

## Tables

Report Bridge uses a separated namespace in `.openclaw/business_ops/ledger.sqlite`:

- `report_bridge_runs`
- `report_bridge_packages`
- `report_bridge_files`
- `report_bridge_nodes`
- `report_bridge_projects`
- `report_bridge_import_receipts`
- `report_bridge_rejections`

## Future Use

Report Bridge can support future client/project reporting by accepting sanitized
node packages that declare project/client metadata, allowed data classes, denied
data classes, hashes, and authority boundaries. It does not remove the need for
operator approval before any real client-data, deployment, runtime, remote, or
tool-execution lane.

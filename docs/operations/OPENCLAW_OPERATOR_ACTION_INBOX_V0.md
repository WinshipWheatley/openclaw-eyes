# OpenClaw Operator Action Inbox v0

Purpose: import strict operator action request JSON files from the shared E-drive
drop into the existing Operator Action Path.

Flow:

```text
Mission Control drafts request JSON
-> shared E-drive drop
-> backend imports and validates
-> request enters pending approval
-> operator approves separately
-> backend executes separately
-> receipt/read-model updates
```

## Shared Drop

Standard paths:

- Mac: `/Volumes/openclaw_e/operator_actions/inbox`
- PC: `E:\openclaw\operator_actions\inbox`
- WSL: `/mnt/e/openclaw/operator_actions/inbox`

Reserved folders:

- `/mnt/e/openclaw/operator_actions/archive`
- `/mnt/e/openclaw/operator_actions/rejected`

v0 does not move or delete inbox files. Archive/reject movement requires a later
explicitly tested lane.

## Boundary

- Import does not approve actions.
- Import does not execute actions.
- Import does not add arbitrary shell.
- Import does not accept user-supplied command strings.
- Import does not run network, Docker, Ollama, SSH, SCP, rsync, package managers, agents, or runtime.
- Import does not write to `C:\openclaw` or `/mnt/c/openclaw`.
- Mission Control is not modified in this lane.

## Request Format

Schema version:

```text
operator_action_request_v0
```

Example:

```json
{
  "schema_version": "operator_action_request_v0",
  "request_id": "mission_control_refresh_report_bridge",
  "action_type": "export_report_bridge_read_model",
  "requested_by": "mission_control",
  "reason": "Refresh report bridge read-model",
  "created_at": "2026-05-14T23:50:00+00:00",
  "source": {
    "node_id": "mac_mission_control",
    "host_kind": "mac",
    "drop_path": "/Volumes/openclaw_e/operator_actions/inbox"
  },
  "authority": {
    "approval_required": true,
    "auto_approve": false,
    "execute_immediately": false,
    "arbitrary_shell_allowed": false,
    "runtime_activation_allowed": false,
    "agent_activation_allowed": false,
    "docker_allowed": false,
    "ollama_allowed": false,
    "network_allowed": false,
    "remote_control_allowed": false,
    "client_deployment_allowed": false,
    "file_delete_allowed": false,
    "file_move_allowed": false
  }
}
```

Allowed `action_type` values are the existing Operator Action Path allowlist:

- `export_context_selection_read_model`
- `export_report_bridge_read_model`
- `prepare_mac_read_model_shuttle`
- `query_generated_read_model_mirror`

## Commands

Import one file:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/import_operator_action_request.py \
  --file /mnt/e/openclaw/operator_actions/inbox/example.json \
  --format operator
```

Import all JSON files in the default inbox:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/import_operator_action_request.py --format operator
```

Query imports:

```bash
python3 scripts/query_operator_action_inbox.py --report summary --format operator
python3 scripts/query_operator_action_inbox.py --report imports --format operator
python3 scripts/query_operator_action_inbox.py --report rejections --format operator
```

Then refresh the operator actions read-model:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/export_operator_actions_read_model.py --format operator
```

## Tables

Operator Action Inbox v0 adds import provenance tables:

- `operator_action_inbox_imports`
- `operator_action_inbox_rejections`

Pending requests still live in the existing `operator_action_requests` table.

## Rejection Rules

Requests are rejected if:

- `schema_version` is not `operator_action_request_v0`
- `action_type` is not allowlisted
- `approval_required` is not `true`
- `auto_approve` is not `false`
- `execute_immediately` is not `false`
- any no-authority flag is `true`
- any command/shell/argv field is present
- JSON is malformed

Rejected request files are not deleted or moved in v0.

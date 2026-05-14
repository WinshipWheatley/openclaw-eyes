# OpenClaw Operator Action Path v0

Purpose: create the first real helm-gated backend action path while preserving
explicit operator control.

Flow:

```text
orient -> request -> review -> approve -> execute bounded work -> receipt -> updated helm state
```

## Boundary

- This is not arbitrary shell.
- This is not hidden approval.
- This is not runtime activation or agent activation.
- This is not Docker/Ollama execution.
- This is not network access, SSH/SCP/rsync, remote control, or client deployment.
- This is not file deletion, file moving, or reorganization.
- Requests do not auto-approve.
- Approvals do not auto-execute.
- Execution uses a hardcoded allowlist of command arrays only.

## Ledger Namespace

Operator Action Path v0 writes a separated namespace into:

```text
.openclaw/business_ops/ledger.sqlite
```

Tables:

- `operator_action_allowed_commands`
- `operator_action_requests`
- `operator_action_approvals`
- `operator_action_executions`
- `operator_action_receipts`
- `operator_action_rejections`

The lane also records request and approval signals through the existing
Business Ops receipt spine helpers. The `operator_action_*` namespace is the
canonical state for this bounded action lifecycle.

## Allowed Actions

Allowed action types:

- `export_context_selection_read_model`
- `export_report_bridge_read_model`
- `prepare_mac_read_model_shuttle`
- `query_generated_read_model_mirror`

No database row or user input may replace the hardcoded command array used for
execution.

## Commands

Request:

```bash
python3 scripts/request_operator_action.py \
  --action-type export_report_bridge_read_model \
  --requested-by operator \
  --reason "Refresh report bridge read-model" \
  --format operator
```

Approve:

```bash
python3 scripts/approve_operator_action.py \
  --action-id ACTION_ID \
  --approved-by operator \
  --approval-note "Approved bounded read-model refresh" \
  --format operator
```

Execute:

```bash
python3 scripts/execute_operator_action.py --action-id ACTION_ID --format operator
```

Export read-model:

```bash
python3 scripts/export_operator_actions_read_model.py --format operator
```

Reports:

```bash
python3 scripts/query_operator_actions.py --report summary --format operator
python3 scripts/query_operator_actions.py --report pending --format operator
python3 scripts/query_operator_actions.py --report allowed --format operator
python3 scripts/query_operator_actions.py --report executions --format operator
python3 scripts/query_operator_actions.py --report receipts --format operator
```

## Generated Read-Model

Exports:

- `generated/read_models/operator_actions.json`
- `generated/read_models/operator_actions_OPERATOR.md`

The read-model exposes request counts, approval counts, completion/failure
counts, latest action, allowed action types, and latest execution receipt
summary.

## No-Authority Flags

- `arbitrary_shell_allowed=false`
- `runtime_activation_allowed=false`
- `agent_activation_allowed=false`
- `docker_allowed=false`
- `ollama_allowed=false`
- `network_allowed=false`
- `remote_control_allowed=false`
- `client_deployment_allowed=false`
- `file_delete_allowed=false`
- `file_move_allowed=false`

## Next Mission Control Lane

Mission Control can later display `operator_actions.json` read-only:

- pending action requests
- explicit approval state
- last execution result
- receipt summary
- allowed action types

That Mac app lane should remain read-only first. App-side request creation should
be a separate lane with the same allowlist and explicit approval boundary.

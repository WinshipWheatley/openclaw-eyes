# Workroom WIP Limits

Status: `WORKROOM_WIP_LIMITS_READY`

This read-model limits active Workroom review load and highlights bottlenecks before agents create more review work.

## Limits

- `max_active_review_packets_per_channel`: `1`
- `max_pending_approvals_per_channel`: `0`
- `max_dead_letters_per_channel`: `2`

## Channels

### `build_mission_control_mac`

- WIP status: `clear`
- Active packets: `0`
- Review packets: `1`
- Pending approvals: `0`
- Dead letters: `0`
- Stage new work allowed: `true`
- Recommended action: Channel is clear; new staging may be considered only after explicit operator approval.

### `build_openclaw_backend`

- WIP status: `watch`
- Active packets: `1`
- Review packets: `1`
- Pending approvals: `0`
- Dead letters: `0`
- Stage new work allowed: `false`
- Recommended action: Finish the active review packet before staging optional new work.

### `build_request_response_service`

- WIP status: `watch`
- Active packets: `0`
- Review packets: `0`
- Pending approvals: `0`
- Dead letters: `1`
- Stage new work allowed: `false`
- Recommended action: Inspect the dead-letter backlog before staging optional new work.

### `build_workflow_router`

- WIP status: `watch`
- Active packets: `0`
- Review packets: `0`
- Pending approvals: `0`
- Dead letters: `1`
- Stage new work allowed: `false`
- Recommended action: Inspect the dead-letter backlog before staging optional new work.

### `build_workroom_review`

- WIP status: `pileup_risk`
- Active packets: `0`
- Review packets: `0`
- Pending approvals: `2`
- Dead letters: `0`
- Stage new work allowed: `false`
- Recommended action: Chief recommends finishing review and clearing pending approvals or dead letters before creating new packets.

### `finance_capital_hilton`

- WIP status: `blocked`
- Active packets: `0`
- Review packets: `0`
- Pending approvals: `3`
- Dead letters: `0`
- Stage new work allowed: `false`
- Recommended action: Do not stage new work. Resolve the protected Guardian gate before escalating or creating more packets.

### `finance_provider_gate`

- WIP status: `watch`
- Active packets: `0`
- Review packets: `0`
- Pending approvals: `0`
- Dead letters: `1`
- Stage new work allowed: `false`
- Recommended action: Inspect the dead-letter backlog before staging optional new work.

### `finance_st_annes`

- WIP status: `blocked`
- Active packets: `0`
- Review packets: `0`
- Pending approvals: `2`
- Dead letters: `0`
- Stage new work allowed: `false`
- Recommended action: Do not stage new work. Resolve the protected Guardian gate before escalating or creating more packets.

### `governance_guardian`

- WIP status: `watch`
- Active packets: `0`
- Review packets: `0`
- Pending approvals: `0`
- Dead letters: `1`
- Stage new work allowed: `false`
- Recommended action: Inspect the dead-letter backlog before staging optional new work.

### `operations_bridge`

- WIP status: `watch`
- Active packets: `0`
- Review packets: `0`
- Pending approvals: `0`
- Dead letters: `1`
- Stage new work allowed: `false`
- Recommended action: Inspect the dead-letter backlog before staging optional new work.

### `operations_mission_control`

- WIP status: `pileup_risk`
- Active packets: `0`
- Review packets: `0`
- Pending approvals: `0`
- Dead letters: `3`
- Stage new work allowed: `false`
- Recommended action: Chief recommends finishing review and clearing pending approvals or dead letters before creating new packets.

### `operations_permissions`

- WIP status: `watch`
- Active packets: `0`
- Review packets: `0`
- Pending approvals: `0`
- Dead letters: `1`
- Stage new work allowed: `false`
- Recommended action: Inspect the dead-letter backlog before staging optional new work.

## Boundary

- Read-model only.
- No workers or agents are run.
- No email, Gmail, browser, Coupa, ledger, workbook, PDF, mark-paid, submit, or git push authority.
- Chief recommends finishing review before creating new packets when any channel is not clear.

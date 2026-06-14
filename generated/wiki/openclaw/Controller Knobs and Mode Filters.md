# Controller Knobs and Mode Filters

Status: CONTROLLER_KNOB_MODE_FILTERS_READY

Controller knobs let Mission Control act like a controller instead of a dashboard. They change visibility, focus, proof verbosity, and staging depth without granting protected authority.

## Knobs

### zoom_level

- Allowed values: `moment`, `task`, `lane`, `world`, `system`
- Default: `task`
- Authority implications: None. Zoom only changes visibility and focus.

### delegation_depth

- Allowed values: `readback`, `plan`, `stage`, `safe_work`, `prepare_approval`, `execute_after_approval_blocked`
- Default: `readback`
- Authority implications: No delegation depth grants protected authority. execute_after_approval remains blocked and future-gated.

### proof_depth

- Allowed values: `none`, `summary`, `receipts`, `full_developer_proof`
- Default: `summary`
- Authority implications: None. Proof depth is display-only.

### urgency

- Allowed values: `park`, `normal`, `today`, `urgent`
- Default: `normal`
- Authority implications: None. urgent never bypasses gates.

### operator_mode

- Allowed values: `artist`, `finance`, `build`, `business`, `creative`, `system`
- Default: `system`
- Authority implications: None. Finance mode does not suppress Guardian or authority blockers; artist mode suppresses business noise unless critical.

## Filter Profiles

- `moment_default`: cards=`1` proof_depth=`summary` delegation=`readback`
- `system_zoom`: cards=`9` proof_depth=`summary` delegation=`readback`
- `artist_normal`: cards=`5` proof_depth=`summary` delegation=`readback`
- `finance_normal`: cards=`7` proof_depth=`summary` delegation=`readback`
- `urgent_finance`: cards=`6` proof_depth=`summary` delegation=`readback`
- `delegation_execute_blocked`: cards=`9` proof_depth=`summary` delegation=`execute_after_approval_blocked`
- `proof_none`: cards=`7` proof_depth=`none` delegation=`readback`
- `proof_summary`: cards=`7` proof_depth=`summary` delegation=`readback`
- `proof_receipts`: cards=`7` proof_depth=`receipts` delegation=`readback`
- `proof_full_developer`: cards=`7` proof_depth=`full_developer_proof` delegation=`readback`

## Rules

- Knobs change visibility, focus, and staging depth.
- Knobs do not grant protected authority.
- execute_after_approval remains blocked and future-gated.
- proof_depth=full_developer_proof is opt-in.
- artist mode suppresses business noise unless critical.
- finance mode does not suppress Guardian or authority blockers.

## Proof

- Unsafe true grants absent: `true`
- Validation errors: `0`



# LEGAL_MODEL_DISTRIBUTION_CONTRACT

## Purpose

OpenClaw Legal must control how local language models and model-related updates are downloaded, verified, distributed, staged, activated, and calibrated across the firm system.

Worker nodes should not independently download models. The Primary Node should own model acquisition, verification, approval, versioning, distribution, and rollout policy.

This contract prevents random model drift across lawyer workstations and keeps sensitive legal processing local, controlled, and auditable.

## Core doctrine

```text
The Primary Node downloads and verifies models.
Worker nodes receive approved models from the Primary Node.
Workers keep using the current approved model until the new model is safely staged and activated.
```

Model distribution must be boring, predictable, and auditable.

## Required behavior

- The Primary Node must own model download decisions.
- The Primary Node must verify model checksums/signatures where available.
- The Primary Node must record model version, source, checksum, size, date, and approved module usage.
- Worker nodes must not independently fetch models from the internet by default.
- Worker nodes must receive models from the Primary Node or an approved firm-local source.
- Worker nodes must validate received model artifacts before use.
- Worker nodes must stage new models in the background while continuing current approved work.
- Worker nodes must switch models only at safe task boundaries.
- The model registry must track which model version is active on each node.
- New models must enter calibration before being treated as high-confidence performance improvements.
- Model rollout must respect firm profile, installed modules, node capability, and update lanes.
- Model distribution must not send matter data externally.

## Primary Node responsibilities

The Primary Node should:

- check approved update/model registries
- download model artifacts once, not separately per worker
- verify checksum/signature
- record model metadata
- decide which modules may use the model
- decide which nodes are eligible
- distribute models over the firm-local network
- monitor staging progress
- approve activation policy
- track old/current/new model versions
- provide rollback to prior approved model where practical
- update ETA/calibration state after rollout

The Primary Node is the model authority for the firm deployment.

## Worker Node responsibilities

Worker nodes should:

- report hardware capability
- report available disk/RAM/thermal/battery status
- receive only approved model artifacts
- validate checksum/signature before staging
- stage models without blocking current work
- keep using current model until safe switch
- activate at task boundary or approved maintenance window
- report model status back to Primary Node
- participate in calibration after activation
- refuse model-dependent tasks if model version/policy is mismatched

Worker nodes must not:

- independently download models from public internet by default
- activate unverified models
- switch model mid-task unless the task is explicitly checkpoint-safe
- keep obsolete models indefinitely without policy
- use a model for a module not approved by the Primary Node

## Model lifecycle

### 1. Available

The Primary Node sees a model/update available from an approved source.

### 2. Downloading

The Primary Node downloads the model artifact.

### 3. Verified

The Primary Node verifies checksum/signature and records metadata.

### 4. Approved for staging

The model is approved for specific modules/nodes.

### 5. Distributing

The model is pushed to eligible worker nodes over the local firm network.

### 6. Staged

Worker nodes have received and verified the model, but have not necessarily activated it.

### 7. Active

A node uses the model for approved task classes.

### 8. Calibrating

The model is being measured on real local workloads.

### 9. High-confidence / rollback / retired

The model either becomes high-confidence, is rolled back, or is retired.

## Safe switching behavior

Workers should not wait idly for a new model if they can continue safe work with the current approved model.

Expected behavior:

```text
Current task uses Model A.
Primary Node distributes Model B in background.
Worker stages Model B.
Current task completes.
Worker switches to Model B for next eligible task.
Calibration begins.
```

If a task is not safe to switch, the worker should finish or checkpoint before activation.

## Update lane interaction

Model updates must follow the legal update lane system.

Examples:

- checksum/signature verification fix: Security Update
- model runtime crash fix: Stability Update
- improved model for an installed module: Installed Module Update
- new model-powered capability: Optional New Module

A model must not become active in a firm deployment merely because it is available. It must be selected by policy, module, and update lane.

## Node eligibility

Not every node should receive every model.

Eligibility may depend on:

- node class
- hardware capability
- free disk space
- RAM/unified memory
- thermal/battery profile
- compute-sharing mode
- installed module set
- matter permissions
- firm policy

Example:

```text
Primary Node: eligible for largest local model.
Attorney MacBook: eligible for small/medium model only when idle.
Observer Node: not eligible for model execution.
```

## Calibration relationship

After a model becomes active, it should enter calibration.

The system should measure:

- task type
- workload class
- node ID
- model version
- throughput
- failure rate
- pause/requeue behavior
- quality/delta metrics where available
- ETA impact

The model should not be described as improving performance until evidence supports that claim.

Detailed ETA behavior is defined in `LEGAL_ADAPTIVE_ETA_CONTRACT`.

## Active case recheck prompt

When a new model is staged or activated, the system may ask:

```text
A new local model is available.
Would you like to evaluate it against active cases using cached artifacts?
```

Options may include:

- Run safe comparison on cached/extracted artifacts
- Run on selected matter
- Wait until next processing batch
- Do not use for this matter

The system must not silently replace existing legal outputs. It should create comparison/delta artifacts first.

## Model registry requirements

The model registry should track:

- model ID
- display name
- version
- source
- checksum/signature
- file size
- downloaded timestamp
- approved modules
- eligible node classes
- active nodes
- staged nodes
- retired/rollback status
- calibration state
- performance history link

This registry should be firm-local and should not contain matter content.

## UX requirements

The Updates or Connect menu should show model state clearly.

Examples:

```text
Primary Node
Model: Evidence Extractor v1.2
Status: Active, calibrating
ETA confidence: Medium
```

```text
Attorney B MacBook
Current model: ReviewLite v1.1
New model: ReviewLite v1.2 staged
Switching after current task
```

```text
Paralegal iMac
Model distribution paused: insufficient disk space
```

The UX should explain model updates without hype:

```text
Projected time saved: unknown until calibration completes.
```

or:

```text
Measured time saved: about 1h 10m on this workload.
Confidence: High.
```

## Required safeguards

- Verify model artifacts before use.
- Do not activate unverified models.
- Do not let worker nodes download models independently by default.
- Do not send matter data to model providers.
- Do not let model updates alter firm workflow without proper update lane approval.
- Do not silently replace existing legal outputs after model change.
- Keep old model available for rollback where practical.
- Audit download, verification, staging, activation, rollback, and retirement.

## Forbidden behavior

- Do not allow each worker to fetch arbitrary models from the internet.
- Do not run unverified model artifacts.
- Do not activate a model for a module that has not approved it.
- Do not force model activation mid-task.
- Do not claim performance improvement before calibration.
- Do not include matter data in model telemetry or support packets.
- Do not let Firm #2 model/module choices affect Firm #1 by default.
- Do not auto-enable cloud model fallback for matter content.

## Acceptance tests / proof points

A future PC/WSL implementation should prove this contract with checks such as:

- Worker node cannot independently download a model by default.
- Primary Node records model metadata before distribution.
- Model checksum/signature mismatch blocks activation.
- Worker stages a model before activation.
- Worker does not switch model mid-task unless task is checkpoint-safe.
- Node eligibility prevents oversized model assignment.
- Model activation is audited.
- New model enters calibration state.
- ETA does not claim measured speedup before samples exist.
- Model update lane is validated before activation.
- Firm #2 model install does not affect Firm #1.
- Matter data is excluded from model distribution telemetry.

## Failure behavior

If model distribution cannot proceed safely, the system should fail closed or continue using the prior approved model.

Examples:

- If checksum verification fails, block model activation.
- If worker lacks disk/RAM, skip that node and report reason.
- If Primary Node is unavailable, worker uses current approved model only.
- If model activation fails, roll back to prior model where practical.
- If model registry is inconsistent, pause model-dependent tasks.
- If calibration shows regression, mark model as performance-risk and require review before broader rollout.

## Notes for first law-firm v1 deployment

- The first firm may run mostly on the Primary Node at first.
- Model distribution can start as a contract and registry before full worker rollout.
- Do not overbuild distributed model execution before vault/profile/update boundaries are strong.
- Worker nodes should be allowed to keep working with current models while updates stage.
- Primary Node ownership of model downloads is a key trust feature for law offices.
- The firm should see updates as improving an already-working local system, not destabilizing it.

## Suggested implementation phases

1. Single-node model registry on Primary Node.
2. Update lane classification for model updates.
3. Model metadata/checksum recording.
4. Worker eligibility model.
5. Local model staging status.
6. Firm-local model distribution.
7. Safe task-boundary activation.
8. Calibration and ETA integration.
9. Active case artifact comparison hooks.

## Likely future modules/files to inspect or build later on PC/WSL

Planning targets only; verify against the PC/WSL repo before implementation:

- `legal/model_registry.py`
- `legal/model_distribution.py`
- `legal/model_policy.py`
- `legal/model_staging.py`
- `legal/update_manager.py`
- `legal/node_registry.py`
- `legal/performance_history.py`
- `legal/model_comparison.py`
- `tests/test_model_distribution_contract.py`
- `tests/test_model_staging.py`
- `tests/test_model_checksum_verification.py`
- `tests/test_node_model_eligibility.py`
- `tests/test_model_calibration.py`

## Relationship to other contracts

This contract depends on:

- `LEGAL_UPDATE_LANE_CONTRACT`
- `LEGAL_CONNECT_MENU_CONTRACT`
- `LEGAL_FIRM_IMMUTABILITY_CONTRACT`

This contract supports:

- `LEGAL_ADAPTIVE_ETA_CONTRACT`
- `LEGAL_MODEL_COMPARISON_CONTRACT`
- `LEGAL_ARTIFACT_RECHECK_CONTRACT`
- `LEGAL_NODE_PERFORMANCE_HISTORY_CONTRACT`
- `OPENCLAW_LEGAL_CONSOLE_V0_controlled_UX_spec`

If this contract is weak, local AI capability will drift across computers and become hard to trust.
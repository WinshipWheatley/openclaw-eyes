# LEGAL_ADAPTIVE_ETA_CONTRACT

## Purpose

OpenClaw Legal must provide processing estimates that are useful, conservative, evidence-based, and honest about uncertainty.

The ETA system should adapt when new local models, software updates, or worker nodes are added. It should begin with conservative estimates, measure real local performance, show calibration confidence, and only promote high-confidence estimates after enough relevant samples exist.

This contract defines ETA confidence, calibration behavior, time-savings reporting, and how the system should avoid overpromising.

## Core doctrine

```text
ETA is not a static progress bar.
ETA is a measured operational forecast with confidence.
```

The system should say:

- what it estimates
- how confident it is
- why confidence is low/medium/high
- what changed after a new model/update/node
- what time savings are projected vs measured
- when it is still calibrating

The default posture should be conservative.

## Required behavior

- ETAs must be labeled with confidence.
- ETAs must be conservative by default when evidence is limited.
- New models, updates, and nodes must enter calibration before being treated as high-confidence improvements.
- The system must distinguish projected time savings from measured time savings.
- The system must update estimates as real local samples are collected.
- The system must show when performance is uncertain, unstable, or regressing.
- The system must avoid fake precision.
- The system must preserve historical performance data by task type, node, model version, and workload class.
- ETA changes caused by updates/nodes should be auditable.
- Lawyers/operators should be able to understand what affects the estimate.

## ETA confidence states

### Unknown

Used when there is not enough data to estimate responsibly.

Example:

```text
ETA unavailable — no performance history for this workload type yet.
```

### Low confidence

Used when only rough technical characteristics are available.

Example:

```text
Estimated completion: about 9-12 hours
Confidence: Low — first batch of this type on this system.
```

### Calibrating

Used when a new node, model, update, or workload class is being measured.

Example:

```text
Estimated completion: about 6h 20m
Confidence: Calibrating — new model update is being measured on active workload.
Calibration: 42%
```

### Medium confidence

Used when some local samples exist, but variance remains.

Example:

```text
Estimated completion: about 4h 50m
Confidence: Medium — 18 similar files processed on this node/model mix.
```

### High confidence

Used when enough relevant local samples exist and performance variance is acceptable.

Example:

```text
Estimated completion: about 3h 40m
Confidence: High — based on 210 similar files processed by this node/model mix.
```

### Performance unstable

Used when performance varies too much to trust a normal estimate.

Example:

```text
ETA unstable — Attorney B MacBook is alternating between idle and user-active.
```

## Conservative vs likely vs best-case estimates

The normal lawyer-facing ETA should show the conservative estimate by default.

Admin/War Room views may show ranges:

```text
Conservative ETA: 5h 40m
Likely ETA: 4h 50m
Best-case ETA: 4h 10m
Confidence: Medium
```

For ordinary users, prefer:

```text
Estimated completion: about 5h 40m
Likely faster if current speed holds.
```

Do not show fake precision such as `5h 37m 12s` unless the task is nearly complete and precision is justified.

## Calibration bar

When a new model, update, or node is being evaluated, the UI should show a calibration bar.

Example:

```text
Calibrating new node performance
[██████░░░░] 62%
ETA confidence: Medium
```

Suggested states:

- Gray: unknown / not enough samples
- Blue: calibrating
- Green: high confidence
- Yellow: performance variance high
- Red: regression or failure detected

Text must accompany color so the UX is accessible and truthful.

## New model/update behavior

When a new local model or relevant update lands, the system should not instantly claim speed improvements.

Initial state:

```text
New local model available: Evidence Extractor v1.2
Status: Installed on Primary Node
Calibration: 0%
Projected time saved: unknown
Confidence: Low
```

After early samples:

```text
Calibration: 28%
Early estimate: may reduce active discovery processing by about 45-70 minutes.
Confidence: Low
```

After more samples:

```text
Calibration: 76%
Observed speedup: 18% on similar PDF extraction tasks.
Estimated time saved: about 1h 05m.
Confidence: Medium
```

After enough evidence:

```text
Calibration complete.
ETA confidence: High.
New estimate: about 4h 55m.
Measured time saved vs prior model: about 1h 18m.
```

## New node behavior

When a new computer joins the firm system, the ETA system should treat it as uncalibrated.

Initial state:

```text
New node added: Attorney B MacBook Pro
Status: Approved worker
Capabilities: PDF extraction, hashing, search indexing, small-model review
Calibration: 0%
Projected queue reduction: up to about 2h 15m
Confidence: Low
```

After real work:

```text
Calibration: 64%
Observed throughput: 37 files/minute on text extraction
Current projected queue reduction: about 1h 40m
Confidence: Medium
```

After stability:

```text
Node calibrated.
Current queue ETA reduction: about 1h 52m.
Confidence: High.
```

## Time-savings reporting

The system may show time saved by updates or nodes, but it must label the claim.

Allowed labels:

- Projected time saved
- Early estimate
- Measured time saved
- Potential time saved
- Unknown
- Regression detected

Examples:

```text
Projected time saved with this new node: up to about 2 hours.
Confidence: Low — no completed tasks yet.
```

```text
Measured time saved with new model: about 1h 10m on this batch.
Confidence: High.
```

The system should not say a new model/node saved time until it has measured enough evidence.

## Performance history model

The system should store local performance history with fields such as:

- task type
- workload class
- file type
- file size range
- page count range
- duration range for media
- source count
- model version
- extractor/module version
- node ID
- node hardware profile
- compute-sharing mode
- started timestamp
- completed timestamp
- throughput
- failure rate
- pause/requeue events
- confidence score
- variance

Performance history should stay local to the firm unless explicitly sanitized for support.

## Workload-specific metrics

ETA should use workload-specific metrics.

Examples:

- PDF text extraction: pages/minute or files/minute
- OCR: pages/minute
- audio transcription: audio minutes per compute minute
- video processing: GB/hour or media minutes/hour
- local LLM review: tokens/sec, docs/hour, or artifacts/hour
- search indexing: MB/sec or documents/minute
- review packet creation: artifacts/minute

Do not use generic computer speed alone.

## Relationship to queue and nodes

The firm processing queue should use adaptive ETA data when available.

When node availability changes, the ETA should update.

Examples:

- node joins
- node leaves
- node becomes user-active
- node pauses due to battery/thermal pressure
- node completes calibration
- model update stages or activates
- task failure rate changes

The ETA should explain meaningful changes:

```text
ETA updated: Attorney B MacBook became unavailable because user is active.
```

```text
ETA improved: Paralegal iMac completed calibration and is now assigned to extraction tasks.
```

## Required UX behavior

The UX should show:

- estimated completion
- confidence state
- reason for confidence state
- calibration progress when relevant
- projected vs measured time savings
- available node impact
- blockers that affect ETA
- whether estimate is conservative

The UX should avoid:

- fake precision
- hype
- unexplained estimate changes
- hiding uncertainty
- blaming lawyers for using their computers

## Artifact recheck relationship

When a new model/update lands, the system may ask:

```text
A new local model is available.
Would you like to evaluate it against active cases using cached artifacts?
```

Options may include:

- Run safe comparison on cached/extracted artifacts
- Run on selected matter
- Wait until next processing batch
- Do not use for this matter

New outputs should not silently replace existing legal outputs. Comparison/delta reporting belongs to `LEGAL_MODEL_COMPARISON_CONTRACT` and `LEGAL_ARTIFACT_RECHECK_CONTRACT`.

## Forbidden behavior

- Do not show high-confidence ETA without enough evidence.
- Do not claim measured time savings from projected data.
- Do not silently change estimates without reason where the change is material.
- Do not use real matter performance history in support packets unless sanitized.
- Do not treat a new model or node as calibrated immediately.
- Do not overpromise reductions from adding hardware.
- Do not blame user activity as failure.
- Do not replace existing legal outputs just because a new model may perform better.

## Acceptance tests / proof points

A future PC/WSL implementation should prove this contract with checks such as:

- New workload with no history shows low/unknown confidence.
- New node starts in calibration state.
- New model starts in calibration state.
- ETA confidence increases only after enough samples.
- Projected and measured time savings are labeled differently.
- ETA updates when node becomes unavailable.
- ETA updates when node completes calibration.
- Performance variance prevents high-confidence ETA.
- High-confidence ETA requires sufficient relevant samples.
- Support packet generation excludes raw matter performance data unless sanitized.
- UI explanation is generated for material ETA changes.

## Failure behavior

If ETA cannot be computed safely, the system should say so plainly.

Examples:

- If no relevant history exists, show low confidence or ETA unavailable.
- If node performance is unstable, show performance unstable.
- If model version is unknown, block model-based ETA improvement claims.
- If performance history is corrupt, ignore it and recalibrate.
- If worker nodes are unavailable, recalculate with Primary Node only.
- If calibration fails, mark the node/model as untrusted for ETA contribution until rechecked.

## Notes for first law-firm v1 deployment

- First implementation can use conservative estimates and simple task history.
- Do not need complex machine learning for ETA at first.
- Start by recording task durations and displaying confidence labels.
- Add calibration states before promising node/model time savings.
- This feature becomes commercially strong once the firm can see that more nodes or better local models reduce queue time.
- Accurate uncertainty is better than impressive but wrong estimates.

## Suggested implementation phases

1. Record task start/end times for single-machine queue tasks.
2. Show simple conservative ETA with confidence labels.
3. Add workload classes and task-type performance history.
4. Add node-aware ETA changes.
5. Add model/update calibration states.
6. Add projected vs measured time-savings reporting.
7. Add calibration bar UX.
8. Add artifact recheck/model comparison hooks.

## Likely future modules/files to inspect or build later on PC/WSL

Planning targets only; verify against the PC/WSL repo before implementation:

- `legal/eta.py`
- `legal/performance_history.py`
- `legal/task_queue.py`
- `legal/node_registry.py`
- `legal/model_registry.py`
- `legal/model_distribution.py`
- `legal/model_comparison.py`
- `legal/artifact_recheck.py`
- `tests/test_adaptive_eta.py`
- `tests/test_eta_confidence_states.py`
- `tests/test_model_calibration.py`
- `tests/test_node_calibration.py`
- `tests/test_update_value_reporting.py`

## Relationship to other contracts

This contract depends on:

- `LEGAL_FIRM_PROCESSING_QUEUE_CONTRACT`
- `LEGAL_CONNECT_MENU_CONTRACT`
- `LEGAL_MODEL_DISTRIBUTION_CONTRACT`

This contract supports:

- `LEGAL_UPDATE_VALUE_REPORTING_CONTRACT`
- `LEGAL_MODEL_COMPARISON_CONTRACT`
- `LEGAL_ARTIFACT_RECHECK_CONTRACT`
- `OPENCLAW_LEGAL_CONSOLE_V0_controlled_UX_spec`

If this contract is weak, the product will show progress without earning trust.

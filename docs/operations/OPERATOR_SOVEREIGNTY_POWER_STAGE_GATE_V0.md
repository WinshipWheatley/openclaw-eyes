# Operator Sovereignty Power-Stage Gate v0

## Purpose

OpenClaw must stay useful without becoming hidden surveillance, manipulation,
or uncontrolled execution machinery. This contract defines the staged controls
required before higher-power capabilities can be enabled.

The machine contract is `operator_sovereignty_power_stage_gate_v0`.

## Doctrine

OpenClaw should be context-aware because it uses visible, scoped, consented,
provenance-backed evidence. It must not rely on hidden raw capture, private-life
profiling, or behavioral manipulation.

The system must not become something the operator would unplug if he knew
exactly what it was doing. It also must not pretend it is safer than it is.

## Model

This is a calibrated watchdog/sentinel model, not an autonomous immune system.

The watchdog monitors authority surfaces:

- read-model freshness and mirror trust
- packet authority flags
- approval scope and payload hashes
- safe service posture exposed by existing status surfaces
- generated proof/read-model outputs
- estate node routing and wrong-environment guidance

It does not monitor:

- private operator behavior
- hidden raw capture
- broad private files
- raw Telegram, Gmail, calendar, bank, spreadsheet, or secret content
- ambient personal life

## Stages

| Stage | Name | Current posture |
| --- | --- | --- |
| 1 | Visibility / read-model / review packet | Current conservative stage |
| 2 | Approval request generation | Partly modeled, not crossed |
| 3 | Credential/PII broker + browser automation preparation | Blocked future stage |
| 4 | Real send/submit/browser/spreadsheet execution | Blocked future stage |
| 5 | Client deployment / remote nodes / autonomous repair | Planned blocked future stage |

## Stage Crossing Rules

Stage 2 approval packets do not imply execution authority. They require clear
scope, packet integrity, anti-ambiguity, receipts, and no implicit authority
escalation before becoming executable.

Stage 3 cannot be crossed without protected credential/PII broker controls,
secret visibility minimization, scoped access receipts, leakage tests, and an
explicit operator approval model.

Stage 4 cannot be crossed without hard stop/containment mechanisms, tamper
checks, authority-surface monitoring, operator-controlled recovery, scoped
execution receipts, and staged alerting.

Stage 5 cannot be crossed without stronger authentication, out-of-band recovery,
client boundary protections, severity-matched reactivation, and a rule that
severe compromise cannot recover by ordinary restart without operator
verification.

## Alert Severity

- Low: stale, missing, or inconsistent read-model/mirror state.
- Medium: unexpected authority request or suspicious scope expansion.
- High: possible secret/PII exposure, unauthorized send/submit/browser/runtime
  path, or unexplained service/authority change.
- Red: suspected compromise, loss of operator control, malicious override, or
  behavior that resists operator sovereignty.

Low-level mismatch does not trigger red alert. Red alert is reserved for severe
compromise and loss-of-control conditions.

## Authority Boundary

This contract does not add runtime authority, send/submit authority, browser
automation, credential/PII access, client deployment, kill scripts, service
control, Mission Control app changes, broad private scanning, or autonomous
self-repair.

## Generated Outputs

- `generated/read_models/operator_sovereignty_power_stage_gate.json`
- `generated/read_models/operator_sovereignty_power_stage_gate_OPERATOR.md`

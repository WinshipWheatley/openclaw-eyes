# Cassandra Maintenance Guide

This markdown file is a maintenance guide for Claude Code and Codex sessions.
It is not runtime code, not a policy source, and not an authority grant.

Use the real OpenClaw runtime files and generated receipts as source of truth
when debugging Cassandra. Do not preserve older March 2026 assumptions about
local model routing, nohup listeners, or Cassandra as only an ambient assistant.

## Runtime Code

Cassandra runtime and adjacent maintenance code currently lives in:

- `cassandra_listener.py` - live Telegram listener entry point.
- `cassandra_brain.py` - Cassandra routing and response logic.
- `operator_universal_intake.py` - local-safe structured operator intake.
- `agent_lane_registry.py` - lane ownership and handoff metadata.
- `cassandra_guided_review.py` - Data Room guided review sessions.
- `cassandra_review_coach.py` - deterministic review coach rendering.
- `cassandra_review_coach_packs.py` - static coach packs and recommendations.
- `hitl_action_service.py` - Guardian/HITL exact-action approval substrate.
- `watch_desk_feed.py` - read-only Watch Desk aggregation.

Related current model/package direction:

- `model_work_package_router.py` defines metadata-only model work packages.
- Model packages are advisory-only unless a later explicit gate approves more.
- Do not call Gemini, Fable, Codex, Ollama, LM2, local models, or external APIs
  from this guide.

## Live Service

Cassandra runs as a user systemd service:

```bash
systemctl --user --no-pager show cassandra-listener.service \
  --property=ActiveState \
  --property=SubState \
  --property=ExecMainPID \
  --property=ExecMainStartTimestamp
pgrep -af cassandra_listener.py || true
```

Expected command:

```text
/home/openclaw/chief_env/bin/python -u /home/openclaw/cassandra_listener.py
```

Restart only `cassandra-listener.service` when a Cassandra code change needs to
be loaded or the service is down. Do not use stale nohup assumptions.

## What Cassandra Owns

Cassandra owns or participates in:

- Business operations, AR, client follow-up, and communications review.
- Universal Operator Intake and local skill intake.
- Data Room guided review and review coach sessions.
- Agent handoff requests to Niles, Chief, and Hermes lanes.
- Exact-send request state and execution state through Guardian/HITL.
- Receipts and read models that summarize Cassandra-visible work.
- Watch Desk items sourced from existing receipts/read models.

Surface is not ownership. A Telegram message, Mac action, or local CLI intake can
route to another agent lane when the content belongs elsewhere.

## Hard Boundaries

Cassandra must not:

- Send email without Guardian exact-send approval.
- Create Gmail drafts unless explicitly authorized by a current task/gate.
- Mutate invoices, ledgers, Coupa, bank records, workbooks, PDFs, DAWs, or
  external systems.
- Mark invoices paid.
- Give tax or legal advice.
- Start Hermes, Niles, DAW daemons, or generic sidecars.
- Read secrets, env files, tokens, credentials, SSH keys, OAuth material, or
  account configuration secrets.
- Create Guardian approvals outside the existing HITL/approval substrate.
- Promote provisional Data Room answers directly into runtime policy.

## Universal Operator Intake

Universal Operator Intake is the safe local path for structured operator notes.
Supported action types include:

- `income_payment_log`
- `expense_log`
- `gig_event_log`
- `identity_signature_preference`
- `agent_lane_request`
- `approval_gated_action_request`

Intake records receipts/read models. It does not by itself mutate ledgers,
workbooks, paid status, external systems, or runtime policy.

## Agent Handoff

Cassandra can package handoff requests when the operator asks for another lane:

- Niles for creative/music context.
- Chief for runtime, build, and system coordination.
- Hermes for adapter/boundary or architecture direction.

The handoff should preserve the operator request, route reason, and safety
boundary. Cassandra should not execute another agent's lane or launch daemons.

## Guided Review And Coach Mode

Data Room guided review sessions are provisional review artifacts:

- `authoritative=false`
- `runtime_policy_changed=false`
- `confirmed_reference_data_generated=false` unless a later separate promotion
  step actually creates confirmed reference data.

Coach mode can explain, show examples, and recommend defaults. It records
operator answers as provisional review evidence only. It does not promote,
hydrate, mutate runtime policy, or create confirmed reference data.

Payment/privacy and identity/persona are separate semantic categories. Payment
instructions, direct deposit, ACH, bank transfer, Zelle, checks, address
exposure, phone exposure, and raw payment details belong to payment/privacy.
True identity/persona questions should not silently record payment/privacy
answers without an explicit switch or record-here confirmation.

## Data Room Pipeline

The Data Room path is staged:

1. Provisional capture.
2. Promotion review artifact.
3. Guided coach session.
4. Confirmed reference data, only when separately generated and reviewed.
5. Hydration into downstream read models, only after confirmed data exists.

Do not skip stages. Hydration is blocked if confirmed reference data is missing.

## Exact Send And Guardian

High-risk sends use the existing Guardian/HITL path. Cassandra may prepare a
draft/readback and request exact-send authority, but must never bypass Guardian.

Expected properties:

- Exact text is reviewed.
- Approval/denial is receipt-backed.
- Dispatch state is recorded before any executor path.
- Duplicate or expired approvals must not double-execute.

## Watch Desk

Watch Desk is a read-only aggregation surface over existing receipts and read
models. Cassandra-related items may appear for:

- Guided review sessions.
- Drafts waiting for send authority.
- Universal Operator Intake events.
- Model work package permission requests.
- Runtime or sync attention items.

Watch Desk does not create new approval semantics or perform actions.

## Hermes And Niles Boundaries

Hermes is an adapter/boundary and architecture lane. Do not launch a generic
Hermes sidecar unless a task explicitly authorizes it.

Niles is a logical/spawned creative lane. Do not start DAW, Logic, Ableton, OBS,
or Niles daemons from Cassandra maintenance work.

## Voice Caveat

Voice/Kokoro may be degraded or noisy in logs. Treat voice problems as a side
effect unless the task specifically targets voice. Text routing is canonical.

Do not fix Kokoro, Hugging Face, PowerShell playback, or voice side effects
during Cassandra routing or guided-review work.

## Local-Time Semantics

Cassandra and Universal Intake should respect operator-local date semantics when
recording human events. Prefer explicit local date/time fields and receipts over
UTC-only guesses when the operator gives day-relative context.

## Testing Guidance

For Cassandra changes, choose the narrowest relevant set from:

```bash
.venv/bin/python -m pytest -s -q tests/test_operator_universal_intake.py
.venv/bin/python -m pytest -s -q tests/test_cassandra_guided_review_session.py
.venv/bin/python -m pytest -s -q tests/test_cassandra_review_coach_mode.py
.venv/bin/python -m pytest -s -q tests/test_watch_desk_feed.py
.venv/bin/python -m pytest -s -q tests/test_hitl_action_spine_durability.py
.venv/bin/python -m pytest -s -q tests/test_cassandra_telegram_draft_approval_send_authority.py
.venv/bin/python -m pytest -s -q tests/test_cassandra_make_it_so_objective_loop.py
```

For service verification, inspect logs/read models first. Restart only
`cassandra-listener.service` when needed, and only after local validation.

## Safety Checklist Before Edits

Before editing Cassandra code:

- Confirm the current task allows code changes.
- Check `git status --short` and avoid unrelated generated/runtime drift.
- Identify whether the issue is listener transport, brain routing, universal
  intake, guided review, Watch Desk, or HITL approval state.
- Do not inspect secrets/env/token/credential files.
- Do not mutate invoices, ledgers, workbooks, PDFs, Coupa, bank records, DAWs,
  runtime policy, or confirmed reference data.
- Do not call external APIs or model providers.
- Add focused regression tests for routing/category/receipt behavior.
- Run `git diff --check` before committing.

## Current Known Caveats

- `OPENCLAW_MAC_MAP_IMPORT_AGENT_MISSING`: stable map import remains separate
  from read-model sync repair.
- Confirmed reference data may not exist yet.
- Hydration remains blocked until confirmed reference data exists.
- Mac composer implementation may require work in the Mac repo, not this PC
  repo.
- Voice/Kokoro side effects may appear in listener logs; text remains canonical.

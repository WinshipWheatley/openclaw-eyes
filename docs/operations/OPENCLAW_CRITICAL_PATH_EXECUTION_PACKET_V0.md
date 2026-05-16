# OpenClaw Critical Path Execution Packet v0

Generated: `2026-05-16`

Evidence basis:

- `docs/operations/OPENCLAW_REMAINING_WORK_STRATIFIER_V0.md`
- `docs/operations/OPENCLAW_REMAINING_WORK_STRATIFIER_READY_PACKET.json`
- `docs/operations/OPENCLAW_CODEX_ARC_AND_HANDOFF_DOCTRINE_V0.md`
- Guardian HITL reconciliation, contract, disposition, adapter, shadow, and dual-write compatibility docs/read-models
- Cassandra/Chief memory authority schema, dry-run, and structured import plan
- Estate, module registry, and bundle planner read-models

No feature work was implemented. No data was imported. Runtime authority was not changed.

## A. Current Phase

OpenClaw is in **authority reconciliation**.

The current work is not about adding agent autonomy. It is about proving the governed spine before Cassandra, Chief, remote builders, send paths, broad ingest, or Mission Control action surfaces get more power.

Current framing:

- Repo A is the canonical governed direction.
- Repo B is the pre-split capability tree and reference evidence, not current runtime authority.
- SQLite/read-models are the best current authority check, but coverage is not complete.
- Mission Control should become the operator work surface, not a backend dashboard.
- The immediate priority is HITL request and decision proof before memory import or action expansion.

## B. Next Best Lane

Next best lane:

`Guardian HITL Decision Receipt Shadow v0`

The first prompt for that lane must be:

`Guardian HITL Decision Receipt Shadow v0 - Inspection Plan`

This is required by the Codex Arc doctrine because the lane touches approval authority. The first step should inspect the exact Chief approval decision paths and return a plan without editing files.

## C. Why This Lane

The Chief request-side dual-write exists, but decision/denial/expiry receipts are not mirrored into SQLite yet. That means SQLite can observe request creation but cannot yet prove the full approval lifecycle.

This lane unblocks:

- HITL request + decision equivalence proof.
- A later Cassandra HITL proposal shadow lane.
- A later transition criteria review for retiring compatibility JSON safely.
- A safer path toward Cassandra/Chief memory import approval.

This lane keeps blocked:

- Cassandra/Chief real memory import.
- Remote-builder bridge implementation.
- Any Telegram/Gmail/email send expansion.
- Broad file, hard-drive, cloud, or Markdown ingest.
- Caller switching from old HITL JSON to SQLite.
- Deletion or retirement of old HITL JSON/JSONL.

It comes before Cassandra/Chief memory import because memory import decisions need a trustworthy approval/receipt surface. It comes before the remote-builder bridge because remote build packets require exact approval binding and receipt proof. It comes before send-path expansion because send actions need explicit packet approval and no raw command/freeform approval. It comes before broad file ingest because ingest decisions must not outrun authority and review gates.

## D. Lane Dependency Chain

1. `Guardian HITL Decision Receipt Shadow v0 - Inspection Plan`
   - No-edit inspection gate.
   - Output: exact decision seam, tests, stop conditions, implementation prompt.

2. `Guardian HITL Decision Receipt Shadow v0`
   - Mirror Chief approval decisions/denials/expiry into SQLite as observational receipts.
   - Old JSON remains runtime-authoritative.
   - No callers switch.

3. `Guardian HITL Dual-Write Receipt Proof v0`
   - Prove request + decision + timeout/mismatch receipt equivalence under synthetic tests.
   - Output: operator proof packet and readiness posture.

4. `Cassandra HITL Proposal Shadow v0`
   - Mirror Cassandra HITL proposal records into the canonical contract shape with safe hashes/metadata only.
   - No raw payload import and no approval authority expansion.

5. `HITL Transition Criteria Review v0`
   - Define what must be true before any caller switch or old JSON retirement can be considered.

6. `Cassandra/Chief Memory Import Approval Review v0`
   - Operator approves or rejects structured import categories.
   - No data import yet unless explicitly approved by the lane.

7. `Cassandra/Chief Structured Fact Import v0`
   - Import only approved structured facts.
   - Keep messy notes/logs/files as evidence-source-only or summarize/extract-only.

8. `Cassandra/Clara Fact Packet + Capital Hilton Completion v0`
   - Generate governed fact packets from SQLite and complete the Capital Hilton invoice packet.
   - Send/reply remains blocked until a later approved send packet lane.

## E. Parallel-But-Not-Now Lanes

These lanes can provide value, but should not interrupt the authority critical path:

| lane | posture | reason |
| --- | --- | --- |
| Mission Control module/bundle/estate visibility | parallel later | Read-models exist, but the app should not distract from HITL proof. |
| Mission Control HITL/memory posture | after decision shadow is specified | Useful for visibility, risky if observational records are mislabeled as authority. |
| Obsidian/review vault export | defer/minimal | Useful only as generated review material, not live state or authority. |
| Niles Album Production Matrix planning | parallel later | Valuable but not blocking Cassandra/Chief invoice/contact/email readiness. |
| Hard-drive/cloud/file ingest | wait | Needs no-go boundaries, metadata-only dry-run, rollback, and operator review. |
| System-wide Markdown classification | wait or dry-run only | Classification substrate exists, but broad source ingest needs explicit boundaries. |
| Remote Builder Bridge Spec | docs-only later | Implementation remains blocked until approval receipts are proven. |
| Repo B capability reconciliation | staged later | Repo B is valuable reference, but bulk porting would create risk. |
| Agent presence cleanup | inspect-first cleanup lane | Known residue should be resolved without committing stale online/readiness claims. |

## F. Operator Decision List

Before the next three lanes, Winship needs only a small set of decisions:

1. After the no-edit inspection, decide whether the proposed decision receipt implementation seam is acceptable if Codex finds ambiguity.
2. After decision receipt implementation, decide whether the proof packet is strong enough to proceed to Cassandra HITL proposal shadow.
3. Decide whether agent presence residue cleanup should run in parallel or continue to wait.

No operator approval is needed to run the first no-edit inspection prompt.

## G. Prompt Pack

### Prompt 1: Immediate Next Lane

```text
You are Codex working in /home/openclaw on PC/WSL.

Lane: Guardian HITL Decision Receipt Shadow v0 - Inspection Plan

Goal:
Inspect and plan the first safe decision-receipt shadow implementation. Do not edit files yet.

This is the no-edit inspection gate required by:
docs/operations/OPENCLAW_CODEX_ARC_AND_HANDOFF_DOCTRINE_V0.md

Hard boundaries:
Do not implement. Do not modify runtime behavior. Do not delete old HITL JSON/JSONL. Do not disable approval paths. Do not switch callers. Do not import data. Do not enable agents. Do not send Telegram/Gmail/email. Do not run Repo B code. Do not inspect secrets, env files, raw Telegram logs, raw private/client data, bank/spreadsheet cells, or no-go roots. Do not touch polish_loop/tasks. Do not commit dirty agent_presence generated files. Do not approve or persist raw command/freeform shell text.

Known residue:
- generated/read_models/agent_presence.json
- generated/read_models/agent_presence_OPERATOR.md
- polish_loop/tasks/chief-cassandra-failure-20260513T234214.md
- polish_loop/tasks/chief-cassandra-failure-20260513T235844.md

First:
cd /home/openclaw
git status -sb --untracked-files=all
git --no-pager log --oneline --decorate -12
pwd

Stop if unexpected tracked changes exist beyond known residue.

Read:
- docs/operations/OPENCLAW_CRITICAL_PATH_EXECUTION_PACKET_V0.md
- docs/operations/GUARDIAN_HITL_SQLITE_DUAL_WRITE_COMPATIBILITY_SPEC_V0.md
- docs/operations/GUARDIAN_HITL_SQLITE_COMPATIBILITY_ADAPTER_PLAN_V0.md
- docs/operations/GUARDIAN_HITL_SQLITE_AUTHORITY_CONTRACT_V0.md
- generated/read_models/guardian_hitl_dual_write_compatibility.json
- generated/read_models/guardian_hitl_shadow_adapter.json
- generated/read_models/guardian_hitl_surface_disposition.json

Inspect safe code only:
- guardian_hitl_dual_write_compatibility.py
- chief_approval_brain.py
- chief_guardian_listener.py if present
- chief_router.py
- chief_guardian_sender.py if present
- guardian_hitl_sqlite_authority_contract.py
- tests/test_guardian_hitl_dual_write_compatibility.py
- tests/test_chief_approval_brain.py
- tests/test_guardian_hitl_sqlite_authority_contract.py

Repo B may be inspected read-only for approval/HITL names and logic references only. Do not import or execute Repo B.

Task:
Return an inspection report only. Do not edit files.

Report:

A. Current repo state
- branch/HEAD
- dirty state
- whether safe to proceed

B. Current Chief decision flow
- files/functions involved
- where decisions, denials, expiries, callbacks, or typed approval codes are handled
- current state store
- whether old JSON remains authoritative
- whether raw command/freeform shell approval risk appears

C. Proposed decision receipt shadow slice
- exact function/adapter seam
- exact SQLite observational target
- decision receipt kinds
- idempotency key plan
- TTL/expiry handling
- mismatch/no-request-mirror handling
- failure behavior
- rollback behavior

D. Files to change in implementation prompt
List exact files.

E. Tests to add/update
List exact tests.

F. Stop conditions
List what should stop implementation.

G. Implementation prompt
Write the next Codex prompt for actual implementation, but do not run it.

Validation:
git diff --check
git status -sb --untracked-files=all

Do not commit.

Final sentinel lines:
DECISION_RECEIPT_INSPECTION_COMPLETE=YES or NO
SAFE_TO_IMPLEMENT=YES or NO
FILES_EDITED=NO
RUNTIME_AUTHORITY_CHANGED=NO
NEXT_STEP=<implement or stop>
```

### Prompt 2: Second Lane

```text
You are Codex working in /home/openclaw on PC/WSL.

Lane: Guardian HITL Decision Receipt Shadow v0

Goal:
Implement the bounded decision-receipt shadow slice approved by the prior no-edit inspection. Old chief_approval_brain / approval_pending.json remains runtime-authoritative. SQLite receives observational decision receipts only.

Hard boundaries:
Do not delete old HITL JSON/JSONL. Do not disable approval paths. Do not switch callers. Do not enable agents. Do not send Telegram/Gmail/email. Tests must mock or avoid Guardian send behavior. Do not import data. Do not inspect secrets/env/raw logs/private data. Do not run Repo B code. Do not touch polish_loop/tasks. Do not commit dirty agent_presence generated files. Do not approve or persist raw command/freeform shell text.

Known residue:
- generated/read_models/agent_presence.json
- generated/read_models/agent_presence_OPERATOR.md
- polish_loop/tasks/chief-cassandra-failure-20260513T234214.md
- polish_loop/tasks/chief-cassandra-failure-20260513T235844.md

First:
cd /home/openclaw
git status -sb --untracked-files=all
git --no-pager log --oneline --decorate -12
pwd

Stop if unexpected tracked changes exist beyond known residue.

Read:
- prior Guardian HITL Decision Receipt Shadow inspection report from this conversation/context
- docs/operations/OPENCLAW_CRITICAL_PATH_EXECUTION_PACKET_V0.md
- docs/operations/GUARDIAN_HITL_SQLITE_DUAL_WRITE_COMPATIBILITY_SPEC_V0.md
- generated/read_models/guardian_hitl_dual_write_compatibility.json
- guardian_hitl_dual_write_compatibility.py
- chief_approval_brain.py
- guardian_hitl_sqlite_authority_contract.py
- tests/test_guardian_hitl_dual_write_compatibility.py
- tests/test_chief_approval_brain.py

Stop if the inspection report did not mark SAFE_TO_IMPLEMENT=YES.

Implement:

1. Extend guardian_hitl_dual_write_compatibility.py.
   - Use the existing dual-write SQLite path and tables.
   - Add fail-open helpers for observational decision receipts.
   - Do not read live approval_pending.json directly.
   - Accept safe legacy decision context from the existing Chief decision path.
   - Store hashes and safe metadata only.
   - Do not persist raw action text, raw command text, full approval_context, or freeform shell.
   - Required flags remain:
     - runtime_authority=false
     - dual_write_enabled=true
     - caller_switched=false
     - old_hitl_deleted=false
     - legacy_json_authoritative=true
     - raw_content_stored=false

2. Wire the exact Chief decision seam identified by inspection.
   - Write observational SQLite decision receipts only after the legacy path applies or rejects a decision.
   - If no matching request mirror exists, write a mismatch/warning receipt only if safe, or report the gap.
   - Adapter failure must not change Chief approval outcome.
   - Do not alter legacy approval behavior.

3. Update export/read-model output.
   - Update scripts/export_guardian_hitl_dual_write_compatibility_read_model.py if needed.
   - Generated output remains:
     - generated/read_models/guardian_hitl_dual_write_compatibility.json
     - generated/read_models/guardian_hitl_dual_write_compatibility_OPERATOR.md
   - Include decision receipt counts, mismatch counts, and next safe move.

4. Add/update tests.
   - tests/test_guardian_hitl_dual_write_compatibility.py
   - tests/test_chief_approval_brain.py

Tests must prove:
- no caller switch
- no old JSON deletion
- old JSON remains authoritative
- decision receipt helper is fail-open
- idempotency key is stable
- TTL/expiry is represented
- no real Telegram/Guardian send occurs
- no raw action/command/freeform shell/full approval_context is stored
- raw command-looking payloads are rejected or reduced to safe hashes/labels only
- decision receipt is not a new approval authority
- mismatch/no-request-mirror cannot approve
- adapter failure does not block Chief decision flow
- Repo B is not imported/executed
- generated JSON/operator output shape is valid

Validation:
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tests/test_guardian_hitl_dual_write_compatibility.py tests/test_chief_approval_brain.py tests/test_guardian_hitl_sqlite_authority_contract.py -q
PYTHONDONTWRITEBYTECODE=1 python3 scripts/export_guardian_hitl_dual_write_compatibility_read_model.py --format json
PYTHONDONTWRITEBYTECODE=1 python3 scripts/export_guardian_hitl_dual_write_compatibility_read_model.py --format operator
python3 -m json.tool generated/read_models/guardian_hitl_dual_write_compatibility.json >/dev/null
git diff --check
git diff --cached --check
git status -sb --untracked-files=all

Commit only if validation passes:
git add <changed files>
git commit -m "feat(authority): shadow Guardian HITL decision receipts"
git push origin main

Final report:
- changed files
- decision receipt behavior implemented
- proof that runtime authority did not change
- proof that raw command/action text is not stored
- validation results
- commit hash
- push status
- remaining residue
- next recommended lane

Final sentinel lines:
DECISION_RECEIPT_SHADOW_COMPLETE=YES or NO
RUNTIME_AUTHORITY_CHANGED=NO
CALLERS_SWITCHED=NO
OLD_HITL_DELETED=NO
SAFE_TO_IMPORT_CASSANDRA_CHIEF_MEMORY=NO
NEXT_RECOMMENDED_LANE=Guardian HITL Dual-Write Receipt Proof v0
```

### Prompt 3: Third Lane

```text
You are Codex working in /home/openclaw on PC/WSL.

Lane: Guardian HITL Dual-Write Receipt Proof v0

Goal:
Create a proof/read-model packet that evaluates whether Chief request mirrors plus decision receipts are coherent enough to proceed toward Cassandra HITL proposal shadow. This is proof and visibility only.

Hard boundaries:
Do not switch callers. Do not delete old HITL JSON/JSONL. Do not disable approval paths. Do not enable agents. Do not send Telegram/Gmail/email. Do not import data. Do not inspect secrets/env/raw logs/private data. Do not run Repo B code. Do not touch polish_loop/tasks. Do not commit dirty agent_presence generated files. Do not mark Cassandra/Chief memory import safe unless the proof criteria explicitly support it.

Known residue:
- generated/read_models/agent_presence.json
- generated/read_models/agent_presence_OPERATOR.md
- polish_loop/tasks/chief-cassandra-failure-20260513T234214.md
- polish_loop/tasks/chief-cassandra-failure-20260513T235844.md

First:
cd /home/openclaw
git status -sb --untracked-files=all
git --no-pager log --oneline --decorate -12
pwd

Stop if unexpected tracked changes exist beyond known residue.

Read:
- docs/operations/OPENCLAW_CRITICAL_PATH_EXECUTION_PACKET_V0.md
- docs/operations/GUARDIAN_HITL_SQLITE_DUAL_WRITE_COMPATIBILITY_SPEC_V0.md
- generated/read_models/guardian_hitl_dual_write_compatibility.json
- generated/read_models/guardian_hitl_dual_write_compatibility_OPERATOR.md
- guardian_hitl_dual_write_compatibility.py
- guardian_hitl_sqlite_authority_contract.py
- related tests

Task:
Build the smallest proof/read-model surface for HITL dual-write receipt health.

Expected outputs:
- docs/operations/GUARDIAN_HITL_DUAL_WRITE_RECEIPT_PROOF_V0.md
- generated/read_models/guardian_hitl_dual_write_receipt_proof.json
- generated/read_models/guardian_hitl_dual_write_receipt_proof_OPERATOR.md

The proof must answer:
- Are request mirrors present?
- Are decision receipts present?
- Do decision receipts bind to request mirrors?
- Are mismatches or missing request mirrors visible?
- Did runtime authority remain unchanged?
- Did old JSON remain authoritative?
- Are callers still unswitched?
- Is Cassandra/Chief memory import still blocked or ready for operator review?
- Is remote-builder still blocked?
- What is the next safe move?

Add tests if a code/export surface is created.

Validation:
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest <new_or_changed_tests> -q
python3 -m json.tool generated/read_models/guardian_hitl_dual_write_receipt_proof.json >/dev/null
git diff --check
git diff --cached --check
git status -sb --untracked-files=all

Commit only if validation passes:
git add <changed files>
git commit -m "feat(authority): add Guardian HITL dual-write receipt proof"
git push origin main

Final report:
- changed files
- proof finding
- whether request/decision receipt parity is proven
- whether runtime authority changed
- whether old HITL was deleted
- whether Cassandra/Chief memory import remains blocked
- validation results
- commit hash
- push status
- next recommended lane

Final sentinel lines:
HITL_DUAL_WRITE_PROOF_COMPLETE=YES or NO
RUNTIME_AUTHORITY_CHANGED=NO
CALLERS_SWITCHED=NO
OLD_HITL_DELETED=NO
SAFE_TO_IMPORT_CASSANDRA_CHIEF_MEMORY=NO
NEXT_RECOMMENDED_LANE=Cassandra HITL Proposal Shadow v0
```

## H. Stop Map

Stop the whole critical path if any of these conditions appear:

- HITL authority ambiguity increases instead of narrowing.
- A lane requires raw/private data, raw logs, secrets, env values, bank/spreadsheet cells, or no-go roots.
- A lane requires running Repo B code.
- A lane tries to enable agents, runtime services, sends, deploys, or remote-builder behavior.
- A lane tries to approve raw command text or freeform shell.
- A lane tries to switch callers before receipt proof.
- A lane tries to delete old HITL JSON/JSONL before replacement proof.
- Stale generated status is mistaken for live authority.
- Unexpected tracked changes appear beyond known residue.
- Mission Control scope drifts into backend implementation before authority proof.
- Broad file/cloud/Markdown ingest tries to read raw content before metadata-only dry-run and operator review.

## One-Page Operator Summary

OpenClaw is in the part where we prove the brakes before giving the car more engine.

The next best move is not Cassandra memory import, Mission Control polish, remote builder, or send-path work. The next best move is to prove Guardian/HITL decisions in SQLite without changing live behavior.

What matters now:

- Chief approval requests are mirrored into SQLite, but decisions are not proven there yet.
- Old JSON approval state is still compatibility-authority.
- Cassandra/Chief memory import and email/invoice usefulness must wait for approval proof.
- Remote-builder and send paths remain blocked.

Next best action:

Run the no-edit `Guardian HITL Decision Receipt Shadow v0 - Inspection Plan` prompt, then implement only if it finds a clean seam.

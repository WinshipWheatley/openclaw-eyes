

# LEGAL_UPDATE_LANE_CONTRACT

## Purpose

OpenClaw Legal updates must be understandable, selectable, confidence-preserving, and safe for firms that already have a working deployment.

This contract defines the update lanes that separate security fixes, stability fixes, installed-module updates, and optional new capabilities. It exists to prevent surprise workflow changes and to make sure Firm #2’s progress never changes Firm #1’s system unless Firm #1 explicitly chooses that update.

## Core doctrine

```text
Updates must not silently change a firm’s working behavior.
```

Every update must be classified before it can be shown, installed, or applied.

The update system must answer:

1. What kind of update is this?
2. What firm/module/profile does it affect?
3. Does it change workflow or only fix behavior?
4. Does it touch matter data?
5. Can it be rolled back?
6. What tests passed?
7. Is the firm explicitly choosing it?

## Update lanes

### 1. Security Updates

Security updates address vulnerabilities or privacy/safety defects.

Examples:

- vault path escape fix
- support packet sanitization fix
- local-only enforcement fix
- permission bypass fix
- unsafe export path fix
- update signature verification fix
- model-distribution checksum fix

Required behavior:

- clearly labeled as security updates
- strongly recommended when relevant
- minimal workflow impact
- no unrelated feature expansion
- no new optional modules bundled in
- explicit warning if workflow impact is unavoidable
- **Validation:** Updates that affect extraction, OCR, review/support packets, Alternative Methods, checker behavior, timelines, contradiction candidates, model behavior, or substantive workflow outputs must be validated against relevant **Known-Answer Fixtures** and regression sentinels on the Developer Reference Bench before release. Pure security/config/documentation changes still require appropriate proof, but do not automatically require full fixture validation.

Security updates may be the only lane eligible for highly streamlined installation, but they must still disclose what changes.

### 2. Stability Updates

Stability updates fix bugs while preserving the existing contract.

Examples:

- extraction crash fix
- failed report export fix
- queue retry bug fix
- ETA display bug fix
- review packet packaging bug fix
- node heartbeat bug fix

Required behavior:

- preserve current workflow
- preserve existing CLI/API behavior where possible
- disclose affected modules
- include tests passed
- avoid new menu items or workflow choices

### 3. Installed Module Updates

Installed module updates improve modules a firm already uses.

Examples:

- improved PDF text-layer extraction
- improved review packet formatting
- faster local search
- better unsupported-file diagnostics
- improved Connect menu node status
- improved ETA calibration for installed queue module

Required behavior:

- apply only to firms that have the module installed
- respect module version pins
- disclose behavior changes
- allow opt-in/update selection
- preserve rollback where practical

### 4. Optional New Modules

Optional new modules add new capabilities that are not installed by default.

Examples:

- OCR module
- email evidence module
- timeline module
- privilege screener module
- discovery connector module
- distributed worker processing module
- public analog fixture search module

Required behavior:

- invisible in day-to-day workflow unless installed
- clearly marked as optional
- requires explicit firm/operator install
- must not alter existing workflows by merely existing in the update catalog
- must include privacy/security notes before installation

## Required update metadata

Every update package should include a manifest with:

- update ID
- version
- lane
- affected module(s)
- required current version range
- target version
- risk level
- whether workflow changes
- whether matter data is touched
- whether migration is required
- whether restart is required
- rollback availability
- tests passed
- checksum/signature information
- release notes
- compatibility notes
- install conditions
- firm/profile impact statement

## Firm-facing update UX

The law firm should see an Update Available area that separates updates by lane:

```text
Security Updates
Stability Updates
Installed Module Updates
Optional New Modules
```

Each update should show:

- what changes
- what does not change
- risk level
- affected modules
- whether current workflow changes
- whether matter data is touched
- tests passed
- rollback availability
- recommended action

The UI should support actions such as:

```text
Install Security Updates
Install Selected Stability Updates
Update Selected Modules
View Optional Modules
Defer
Rollback / View Installed Version
```

The UI should not pressure the firm with vague hype. It should provide enough information for confidence.

## No-surprise rules

- New modules must not appear in Firm #1’s normal workflow just because Firm #2 requested them.
- Existing firm deployments must not see new menu items unless the relevant module is installed or the update is explicitly accepted.
- Update previews must disclose UI changes.
- Workflow-changing updates must require explicit approval.
- Security updates must not smuggle in unrelated feature changes.
- Stability updates must not become feature updates.
- Optional new modules must remain optional.

## Matter data boundary

Updates must not include matter-vault data.

Update packages must not contain:

- source files
- extracted matter text
- transcripts
- reports
- review packets
- attorney notes
- raw matter audit logs
- firm/client/matter names unless required for local firm profile and approved

If an update requires migration over matter data, the migration must run locally inside the firm environment and must explain:

- what data it reads
- what data it writes
- whether it changes existing artifacts
- rollback/backup behavior
- proof command or validation check

## Local repair and update proposals

A local repair/system clerk may propose an update package after diagnosing a failed capability or unsupported file.

Allowed:

- build/test in sandbox
- use sanitized diagnostics
- use public analog fixtures
- produce proposed patch/update package
- produce test output
- produce rollback note
- produce risk summary

Forbidden without approval:

- modifying production handlers
- changing firm workflow
- installing unverified packages
- enabling cloud APIs for matter content
- sending sensitive logs externally
- sending real matter data externally

By default, proposed updates require Winship approval before production promotion.

## Model and node update interaction

Model updates and node-capability updates must also use update lanes.

- A checksum/signature fix is a security update.
- A model runtime crash fix is a stability update.
- A better model for an installed module is an installed module update.
- A new optional model-powered module is an optional new module.

New models should be staged by the Primary Node, distributed to approved worker nodes, and calibrated before being treated as high-confidence performance improvements.

## Acceptance tests / proof points

A future PC/WSL implementation should prove this contract with checks such as:

- Every update manifest must declare a lane.
- Unknown update lanes are rejected.
- Security updates cannot include unrelated optional modules.
- Stability updates cannot add new workflow menus.
- Optional new modules are not visible in normal Firm #1 UX unless installed.
- Installed module updates only apply to installed modules.
- Firm module version pins are respected.
- Workflow-changing updates require explicit approval.
- Update packages cannot include matter-vault files.
- Update manifest must include tests passed and rollback status.
- Rollback metadata is required for non-trivial module updates where practical.
- Update catalog display separates security, stability, module, and optional updates.

## Failure behavior

If an update cannot be safely classified, block it pending review.

Examples:

- If lane is missing, block installation.
- If the update touches matter data but does not disclose migration behavior, block installation.
- If an update attempts to expose a new module in an existing firm UX without install approval, block installation.
- If an update claims to be security but includes unrelated features, reclassify or block.
- If checksum/signature verification fails, block installation.
- If rollback metadata is required but missing, warn or block depending on risk.
- If update compatibility cannot be determined, require human review.

## Notes for first law-firm v1 deployment

- The first firm should see updates as controlled, not scary.
- Version 1 should ship with update lanes even if the updater is initially simple.
- The firm should not need Winship to remote in and patch manually for ordinary updates.
- The firm should be able to install security updates separately from optional modules.
- Firm #1’s workflow must remain pinned unless explicitly changed.
- The update UX should help the firm trust that improvements will not break what already works.

## Likely future modules/files to inspect or build later on PC/WSL

Planning targets only; verify against the PC/WSL repo before implementation:

- `legal/update_manager.py`
- `legal/update_manifest.py`
- `legal/update_policy.py`
- `legal/module_registry.py`
- `legal/module_versioning.py`
- `legal/firm_profile.py`
- `legal/local_repair.py`
- `legal/model_distribution.py`
- `tests/test_update_lane_contract.py`
- `tests/test_update_manifest_validation.py`
- `tests/test_no_surprise_updates.py`
- `tests/test_update_package_no_matter_data.py`

## Relationship to other contracts

This contract depends on:

- `LEGAL_PRODUCT_CORE_SEPARATION`
- `LEGAL_FIRM_IMMUTABILITY_CONTRACT`
- `LEGAL_VAULT_PATH_CONTRACT`

This contract supports:

- `LEGAL_NO_SURPRISE_UPDATE_CONTRACT`
- `LEGAL_MODULE_VERSION_PINNING`
- `LEGAL_MODEL_DISTRIBUTION_CONTRACT`
- `LEGAL_UNSUPPORTED_LOCAL_BUILD_FIRST`
- `LEGAL_LOCAL_REPAIR_AGENT_BOUNDARY`
- `LEGAL_CONNECT_MENU_CONTRACT`

If this contract is weak, updates become a source of fear instead of confidence.
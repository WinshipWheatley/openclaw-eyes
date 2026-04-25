

# LEGAL_FIRM_IMMUTABILITY_CONTRACT

## Purpose

A law firm’s working OpenClaw Legal deployment must remain behaviorally stable once it is operating correctly.

Firm #2’s needs, settings, modules, labels, UX preferences, workflow choices, or custom capability work must never affect Firm #1 unless Firm #1 explicitly installs or enables the relevant update/module.

This contract protects firms from surprise changes after updates. It also protects OpenClaw Legal from becoming an unmaintainable set of hidden custom forks.

## Core doctrine

A firm deployment that works must keep working.

No update, module, setting, menu item, label, connector, workflow, model policy, role name, or UI option may appear or change inside a firm’s deployment unless one of these is true:

1. It is a security update that does not expand workflow behavior.
2. It is a stability/bug-fix update that preserves the existing product contract.
3. The firm explicitly installs or enables the module/update.
4. The firm explicitly changes its own profile/config.

“Available as an option somewhere in the product” is not enough. If Firm #1 did not choose it, Firm #1 should not see it.

## Required behavior

- Each firm deployment must pin product, module, profile, and policy versions.
- New modules must be invisible to a firm until explicitly installed or enabled.
- Firm-specific profile changes must affect only that firm.
- Firm #2 work must be classified before reuse: security update, stability update, module update, new optional module, firm-specific profile change, or suite-module candidate.
- Updates must show what changes, what does not change, risk level, test status, rollback availability, and whether matter data is touched.
- Security updates must be narrow and should not introduce new UX/workflow options unless required to fix the vulnerability.
- Stability updates must preserve existing workflows and APIs.
- Module updates must be opt-in or pinned per firm.
- New modules must not appear in existing firm UX unless deliberately installed.
- Firm deployments should support rollback for module/stability updates wherever practical.
- Build plans must state whether a change can affect existing deployments.

## Forbidden behavior

- Do not let Firm #2’s requested workflow appear in Firm #1 by default.
- Do not add new menu items to Firm #1 because another firm needed them.
- Do not silently change labels, role names, workflow steps, export behavior, update behavior, connector availability, or model routing.
- Do not auto-enable new modules.
- Do not treat “available option” as safe if it changes a firm’s visible UX.
- Do not push workflow-changing updates as routine patches.
- Do not bundle unrelated feature changes into security updates.
- Do not modify a firm profile as part of a generic product update unless explicitly approved by that firm/operator.
- Do not remove old behavior without a compatibility path or explicit migration approval.
- Do not let update code infer that a firm wants a module because another firm installed it.

## Update lanes

### 1. Security lane

Security updates fix vulnerabilities, privacy leaks, local-only enforcement bugs, unsafe export paths, unsafe support packets, permission bypasses, or similar issues.

Security updates may be recommended strongly, but they must avoid workflow expansion. If a security fix requires visible workflow change, the update must clearly say so before installation.

### 2. Stability lane

Stability updates fix bugs while preserving behavior.

Examples:

- extraction crash fix
- queue retry bug fix
- broken report export fix
- incorrect ETA confidence display fix
- update verification bug fix

Stability updates must not introduce new UX concepts or default-enabled behavior.

### 3. Module lane

Module updates improve already-installed modules. They should respect each firm’s pinned module version and update preferences.

Examples:

- improved PDF text-layer extractor
- better review packet formatting
- improved unsupported-file diagnostics
- faster local search implementation

Module updates should be explicit and reversible where practical.

### 4. New capability lane

New capabilities are invisible unless a firm chooses to install them.

Examples:

- OCR module
- email evidence module
- timeline module
- privilege screener module
- external discovery connector
- distributed worker node processing

New capabilities must not appear in Firm #1 just because Firm #2 bought or requested them.

## Firm profile isolation

Firm profiles must be isolated.

A profile may define:

- firm display labels
- enabled modules
- module versions
- approved connectors
- role labels
- workflow defaults
- update preferences
- device permissions
- processing policies
- local model policy
- vault path

A change to one profile must not modify another profile.

A global product update may provide new available module packages in the update registry, but each firm’s installed set must remain unchanged unless the firm/operator selects the update.

## UX requirements

The update UX should show updates in separate lanes:

```text
Security Updates
Stability Updates
Installed Module Updates
Optional New Modules
```

Each update should display:

- title
- version
- lane
- risk level
- affected module(s)
- what changes
- what does not change
- whether workflow changes
- whether matter data is touched
- whether restart is required
- whether migration is required
- rollback availability
- tests passed
- recommended action

For optional modules, the UX should say:

```text
Not installed. This will not affect your current workflow unless you install it.
```

For existing firms, new optional modules should not appear in ordinary day-to-day workflow screens unless installed.

## Acceptance tests / proof points

A future PC/WSL implementation should prove this contract with checks such as:

- Create Firm A and Firm B profiles with different enabled modules; verify changes to Firm B do not alter Firm A.
- Add a new optional module to the registry; verify it is not visible in Firm A’s normal UX unless installed.
- Install a module for Firm B; verify Firm A’s installed module list is unchanged.
- Apply a security update; verify it does not add workflow/menu changes unless explicitly marked.
- Apply a stability update; verify existing commands/API behavior still pass compatibility tests.
- Attempt to apply a workflow-changing update as a security update; verify the system blocks or requires explicit approval.
- Attempt to modify another firm’s profile through a generic update; verify the update is blocked.
- Verify update manifests declare lane, affected modules, risk level, migration requirement, and rollback availability.
- Verify firm module versions remain pinned until explicitly updated.

## Failure behavior

If an update threatens firm immutability, the system should fail closed.

Examples:

- If an update would expose a new module/menu to a firm that did not install it, block or quarantine the update.
- If an update cannot classify its lane, require human review.
- If a module update changes workflow behavior, reclassify it as workflow-changing and require explicit install/approval.
- If an update tries to modify firm profile data without approval, block it.
- If rollback metadata is missing for a non-security update that requires migration, warn clearly before installation.

## Notes for first law-firm v1 deployment

- The first deployment must be stable enough that the firm can trust updates.
- Do not make the first firm feel like a beta tester whose workflow changes every time another firm asks for something.
- Firm #1’s profile and installed module set should become a pinned baseline.
- Firm #2 improvements should become explicit update artifacts, not invisible behavior drift.
- Firm #1 should be able to keep working on its pinned version if it does not want new modules.

## Likely future modules/files to inspect or build later on PC/WSL

Planning targets only; verify against the PC/WSL repo before implementation:

- `legal/update_manager.py`
- `legal/update_manifest.py`
- `legal/module_registry.py`
- `legal/firm_profile.py`
- `legal/profile_store.py`
- `legal/update_policy.py`
- `legal/tests/test_firm_immutability.py`
- `legal/tests/test_update_lanes.py`
- `legal/tests/test_module_version_pinning.py`
- `legal/tests/test_profile_isolation.py`

## Relationship to other contracts

This contract depends on:

- `LEGAL_PRODUCT_CORE_SEPARATION`
- `LEGAL_VAULT_PATH_CONTRACT`

This contract supports:

- `LEGAL_UPDATE_LANE_CONTRACT`
- `LEGAL_NO_SURPRISE_UPDATE_CONTRACT`
- `LEGAL_MODULE_VERSION_PINNING`
- `LEGAL_CONNECT_MENU_CONTRACT`
- `LEGAL_MODEL_DISTRIBUTION_CONTRACT`
- `LEGAL_UNSUPPORTED_LOCAL_BUILD_FIRST`

If this contract is weak, every new buyer risks breaking earlier buyers.
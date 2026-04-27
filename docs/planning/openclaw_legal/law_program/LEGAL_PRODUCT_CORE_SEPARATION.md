

# LEGAL_PRODUCT_CORE_SEPARATION

## Purpose

OpenClaw Legal must ship as a reusable product architecture, not as a one-off custom build for the first law firm.

The first firm can receive a tailored deployment, but the tailoring must live in firm profile/config, installed modules, and private matter vault data — not in forked product code or hardcoded assumptions.

This contract defines the separation between:

1. **OpenClaw Legal Core** — reusable product code and generic legal workflow modules.
2. **Firm Profile** — firm-specific configuration, labels, enabled modules, policies, update pins, and approved devices.
3. **Matter Vault** — private client/matter data, discovery files, extracted artifacts, reports, attorney notes, and audit logs.
4. **Suite Modules** — optional legal-product modules that can be installed only when a firm explicitly chooses them.

The goal is that after Firm #1 says the system works, the architecture can be extracted and sold to Firm #2 without carrying over firm names, client facts, matter data, or one-off custom assumptions.

## Core doctrine

Reusable product code can know how to process legal data.

Reusable product code must never contain real legal data.

A firm deployment must be built from portable code plus firm-local configuration plus private runtime data. These must not collapse into one tangled system.

This separation is reinforced by:
- The **Dual-Lane Development Model** (see `OPENCLAW_LEGAL_GOVERNING_PRINCIPLES.md` Principle 15), which strictly separates Synthetic R&D (Lane A) from Real Matter Local-Only execution (Lane B).
- The **IP / Pilot / Ownership Doctrine** (see `OPENCLAW_LEGAL_GOVERNING_PRINCIPLES.md` Principle 16), which defines developer ownership of product architecture and firm ownership of matter data.

## Product layers

### 1. OpenClaw Legal Core

The Core contains reusable product logic, generic workflows, module APIs, tests, docs, and update mechanisms.

Core may include matter workspace logic, source registration, hashing, extraction modules, local search, report generation, review packet export, CLI/API surfaces, updater framework, Connect menu framework, task queue framework, role/permission framework, module registry, local-only enforcement code, and generic tests.

Core must not include firm names, client names, matter names, real discovery files, extracted real matter text, real legal reports, attorney notes, privileged content, firm-specific workflow hacks, or paths that only make sense for one deployment.

### 2. Firm Profile

The Firm Profile defines how the reusable product behaves for a specific law firm.

Firm Profile may include firm display name, local vault root path, enabled modules, pinned module versions, local-only/cloud policy, role labels, device enrollment rules, update lane preferences, connector approvals, processing defaults, node/resource policies, and attorney/matter assignment rules.

Firm Profile must not include matter content, discovery files, privileged material, raw extracted text, attorney work product, or full audit logs.

### 3. Matter Vault

The Matter Vault is private runtime data. It is the firm’s local evidence/work-product space.

Matter Vault may include matter folders, source files, extracted text, transcripts, reports, review packets, audit logs, attorney notes, generated work product, and support diagnostics before sanitization.

Matter Vault must never be committed to the product repo, included in update packages, sent to non-local LLMs by default, included in feature request packets, used as generic training/example data, or copied into reusable product docs.

### 4. Suite Modules

A suite module is a reusable capability that may be installed in one or more firm deployments.

Examples include discovery review, email evidence, OCR, timeline, privilege screening, immigration packets, family law, civil litigation, and unsupported-file handlers.

Firm #2’s new feature should become a suite module only if it can be made generic and safe. It must not silently appear in Firm #1’s system.

## Required behavior

- Product code must be portable across firms.
- Firm-specific configuration must live in firm profiles, not hardcoded code.
- Matter data must live in firm-local vaults outside the product repo.
- New reusable capabilities must be packaged as modules or core updates.
- Firm-specific customizations must not become hidden assumptions in Core.
- Every artifact must be classifiable as Core, Firm Profile, Matter Vault, Suite Module, or Support Packet.
- Build plans must explicitly state which layer they modify.
- Update packages must not include private matter data.
- Feature request packets must be sanitized before leaving a firm deployment.
- Public/synthetic fixtures must be used for reusable tests.

## Forbidden behavior

- Do not fork product code per firm unless explicitly marked temporary.
- Do not hardcode firm names, attorney names, client names, or matter names into Core.
- Do not put real legal data in the repo.
- Do not use real matter data as test fixtures.
- Do not allow Firm #2 changes to affect Firm #1 by default.
- Do not expose new modules/options to a firm unless that firm explicitly installs or enables them.
- Do not let a support/update path collect private data as a convenience.
- Do not let non-local LLMs inspect matter vaults by default.
- Do not mix deployment config and legal evidence in the same artifact.

## Layer classification rule

Every future change should answer:

1. Is this Core product code?
2. Is this Firm Profile/config?
3. Is this Matter Vault private data?
4. Is this a Suite Module candidate?
5. Is this a sanitized support/update artifact?

If the answer is unclear, stop and classify before building.

## Acceptance tests / proof points

A future PC/WSL implementation should prove this contract with checks such as:

- Creating a new firm profile without modifying Core product files.
- Creating two firm profiles with different labels/modules and proving they do not affect each other.
- Verifying matter vault paths are outside the product repo.
- Verifying support packets exclude matter data, firm names, client names, and extracted text.
- Verifying update packages do not include matter vault contents.
- Verifying synthetic/demo fixtures are the only fixtures inside the repo.
- Verifying new module installation is explicit per firm.
- Verifying Firm #2 module settings are not visible in Firm #1 by default.
- Verifying non-local/cloud tools cannot traverse into configured matter vaults.

## Failure behavior

If product/data separation is violated, the system should fail closed.

Examples:

- If a matter vault path is inside the product repo, block creation/import and show a clear error.
- If a support packet contains sensitive data indicators, block export and generate a sanitization failure report.
- If an update package contains firm or matter data, block installation.
- If a build step cannot classify its layer, require human review before continuing.
- If a module tries to alter another firm’s profile by default, block the update.

## Notes for first law-firm v1 deployment

- Firm #1 should receive a working Version 1 deployment, not a prototype branch.
- Firm #1’s custom setup must be represented as profile/config and installed modules wherever possible.
- Once Firm #1 says the system works, the reusable architecture should be extractable without copying Firm #1’s data, name, matters, or internal procedures.
- Firm #2 improvements should return to Firm #1 only as explicit security/stability updates or opt-in module updates.
- Firm #1’s working behavior should remain stable after Firm #2 work unless Firm #1 explicitly installs a change.

## Likely future modules/files to inspect or build later on PC/WSL

Planning targets only; verify against the PC/WSL repo before implementation:

- `legal/deployment_profile.py`
- `legal/module_registry.py`
- `legal/vault_policy.py`
- `legal/support_packet.py`
- `legal/update_manager.py`
- `legal/firm_profile.py`
- `legal/installer.py`
- `tests/test_product_core_separation.py`
- `tests/test_firm_profile_isolation.py`
- `tests/test_vault_outside_repo.py`

## Relationship to other contracts

This contract is upstream of:

- `LEGAL_FIRM_IMMUTABILITY_CONTRACT`
- `LEGAL_VAULT_PATH_CONTRACT`
- `LEGAL_UPDATE_LANE_CONTRACT`
- `LEGAL_NO_SURPRISE_UPDATE_CONTRACT`
- `LEGAL_MODULE_VERSION_PINNING`
- `LEGAL_SANITIZED_SUPPORT_PACKET`
- `LEGAL_CONNECT_MENU_CONTRACT`

If this contract is weak, the product risks becoming an unmaintainable custom branch for each law firm.
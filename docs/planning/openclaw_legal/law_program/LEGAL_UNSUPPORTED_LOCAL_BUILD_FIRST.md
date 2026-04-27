

# LEGAL_UNSUPPORTED_LOCAL_BUILD_FIRST

## Purpose

Unsupported files must not immediately become manual support work for Winship or a reason to use non-local/cloud tools.

OpenClaw Legal should first attempt safe local classification, installed local handlers, and a bounded local capability build/repair path. Only after that fails, or is explicitly blocked by policy, should the system show a Request Feature escalation.

This contract defines the Alternative Methods flow for unsupported files.

## Core doctrine

```text
Unsupported does not mean external.
Unsupported means local diagnosis first.
```

The system must treat unsupported files as a controlled workflow:

1. Detect unsupported file.
2. Classify technical characteristics locally.
3. Try existing local handlers.
4. Try local capability build/repair if policy allows.
5. Generate sanitized diagnostics.
6. Unlock Request Feature only after local attempts fail or are policy-blocked.

This workflow is supported by the **Dual-Lane Development Model** (see `OPENCLAW_LEGAL_GOVERNING_PRINCIPLES.md` Principle 15):
- **Lane A (Synthetic R&D)** is where new handlers are prototyped and validated using synthetic data/public analogs and external tools.
- **Lane B (Real Matter Local-Only)** is where these handlers are executed against real matter data using only local, deterministic tools.

## Required behavior

- Unsupported files must appear in the confidence/status area.
- Unsupported files must be actionable through an Alternative Methods menu.
- The system must first classify the file locally where possible.
- The system must try existing installed local handlers before escalation.
- The system must check the local capability registry for possible handlers.
- If policy allows, the system must attempt a local build/repair path in a sandbox.
- Local build attempts must use sanitized diagnostics and synthetic/public fixtures, not real matter data.
- Request Feature must remain hidden until local handling/build has failed or been blocked by policy.
- The system must record each attempt in the matter/system audit trail.
- Unsupported handling must preserve the original source file.
- Unsupported handling must not mutate production handlers without approval.
- Unsupported handling must not send matter data externally.

## Alternative Methods menu

The status bar may show:

```text
Unsupported files: 2  [Alternative methods]
```

The Alternative Methods menu should show actions based on current state.

### Before local attempts

Available actions:

- Try local capability
- View technical details
- Ignore for now

Request Feature should not be visible yet.

### After existing-handler failure

Available actions:

- Try local capability build
- View failed attempts
- View non-local options and risks
- Ignore for now

Request Feature should still be hidden unless local build is blocked by policy.

### After local build failure or policy block

Available actions:

- Request feature
- Export sanitized support packet
- View public analog candidates
- View non-local options and risks
- Ignore for now

Request Feature becomes visible only at this stage.

## Local capability attempt stages

### 1. Local classification

The system should try to determine:

- extension
- MIME type
- file signature / magic bytes if safe
- size range
- page count if document-like
- duration/codec/container if media-like
- whether the file may be text, binary, archive, image, audio, video, email, or proprietary container

Classification must not require external upload.

### 2. Installed handler attempt

The system should try existing approved local tools/handlers.

Examples:

- existing PDF text-layer extraction
- text/Markdown extraction
- known email parser
- known media metadata extractor
- known archive inspector

If no handler exists, record that clearly.

### 3. Local build/repair attempt

If firm policy allows, the Systems Clerk may attempt a local build/repair path.

Allowed:

- inspect sanitized diagnostics
- inspect local code/docs
- generate candidate handler in sandbox
- use public analog fixtures
- run tests locally
- prepare a proposed update package
- prepare rollback/risk notes

Forbidden:

- sending real matter data externally
- installing unverified packages
- enabling cloud APIs for matter content
- changing firm workflow
- sending sensitive logs
- modifying production handlers without approval

### 4. Promotion gate

A successful local build does not automatically become production behavior unless policy explicitly allows that class of update.

Default law-firm deployment policy:

```text
Build/test in sandbox: allowed
Production handler modification: Winship approval required
Workflow-changing update: firm/operator approval required
Matter-data externalization: forbidden
```

## Request Feature gate

Request Feature should appear only after one of these is true:

- local classification completed and no installed handler exists
- installed handler failed
- local build/repair attempt failed
- local build/repair is blocked by firm policy
- required package/tool is unavailable and cannot be safely installed locally

The UI should explain why Request Feature is now available:

```text
Local handling failed.
A sanitized feature request can be prepared without including the legal file or matter contents.
```

## Sanitized support packet handoff

When Request Feature is used, the system should generate a sanitized packet for Winship/build support.

It may include:

- file extension
- detected MIME type
- file size range
- page/duration range if detectable
- codec/container hints if applicable
- local tools attempted
- local build attempts
- error messages
- redacted stack traces
- installed extractor versions
- OpenClaw Legal version
- firm profile version
- module needing support
- public analog candidate list
- stress-test public fixture list

It must exclude:

- the actual unsupported file
- sensitive filename if revealing
- client name
- matter name
- firm name
- extracted text
- attorney notes
- report content
- full audit logs
- private absolute paths
- privileged content

## Public analog fixture search

The system should help find public files similar to the unsupported file so Winship can build/test without sensitive data.

Search should use technical characteristics only, such as:

- file extension
- MIME type
- container type
- approximate size range
- approximate duration
- page count
- codec hints

The system should not use:

- client names
- case facts
- matter names
- police department names
- source filenames if revealing
- any content from the legal file

The packet should include:

- closest public analog candidate
- several additional public stress-test files
- reason each file was selected
- source URL/license if available
- suggested regression-test use

## Non-local options

Non-local options may be shown as information, but not used automatically.

The UI should explain:

- what the non-local option is
- what data it would require
- privacy risk
- whether firm policy allows it
- whether attorney/operator approval is required

Matter content must not be sent to non-local tools by default.

## UX requirements

The unsupported-file UX should be calm and truthful.

Example states:

```text
Unsupported: local classification pending
Unsupported: no installed handler
Unsupported: local build attempt running
Unsupported: local build failed
Unsupported: feature request available
Unsupported: ignored for now
```

The UI should avoid vague reassurance. It should say what has been tried, what failed, and what options remain.

## Acceptance tests / proof points

A future PC/WSL implementation should prove this contract with checks such as:

- Unsupported file creates an unsupported status, not a crash.
- Alternative Methods menu appears for unsupported files.
- Request Feature is hidden before local attempts.
- Installed local handlers are attempted before escalation.
- Local build attempt runs only if policy allows.
- Request Feature appears only after local build failure or policy block.
- Support packet excludes real file content and sensitive names.
- Support packet includes sanitized diagnostics.
- Public analog search uses technical characteristics only.
- Production handler modification requires approval.
- Non-local options do not transmit matter content automatically.
- Audit log records classification, handler attempt, build attempt, and escalation.

## Failure behavior

If unsupported handling cannot proceed safely, the system should fail closed.

Examples:

- If the file cannot be classified safely, show unknown/unsupported and do not upload it.
- If a local handler crashes, record failure and preserve the source file.
- If the support packet cannot be sanitized, block Request Feature export.
- If a local build tries to modify production code without approval, block it.
- If non-local option would require matter content and policy forbids it, disable the option.
- If public analog search risks leaking sensitive terms, block the search and ask for sanitized technical parameters.

## Notes for first law-firm v1 deployment

- Unsupported-file handling is part of trust, not a side feature.
- The system should show the firm that it tried reasonable local methods before asking for outside help.
- Feature requests should feel easy for the firm but safe for privacy.
- Winship should receive useful diagnostics and public analog candidates, not sensitive legal material.
- The first version can keep local build attempts conservative and proposal-only.

## Likely future modules/files to inspect or build later on PC/WSL

Planning targets only; verify against the PC/WSL repo before implementation:

- `legal/unsupported.py`
- `legal/capability_registry.py`
- `legal/local_repair.py`
- `legal/support_packet.py`
- `legal/public_analog_search.py`
- `legal/update_manager.py`
- `legal/compliance_gate.py`
- `tests/test_unsupported_local_build_first.py`
- `tests/test_feature_request_gate.py`
- `tests/test_support_packet_sanitization.py`
- `tests/test_public_analog_fixture_search.py`

## Relationship to other contracts

This contract depends on:

- `LEGAL_PRODUCT_CORE_SEPARATION`
- `LEGAL_VAULT_PATH_CONTRACT`
- `LEGAL_ROLE_NAMING_CONTRACT`

This contract supports:

- `LEGAL_UPDATE_LANE_CONTRACT`
- `LEGAL_LOCAL_REPAIR_AGENT_BOUNDARY`
- `LEGAL_SANITIZED_SUPPORT_PACKET`
- `LEGAL_PUBLIC_ANALOG_FIXTURE_SEARCH`
- `OPENCLAW_LEGAL_CONSOLE_V0_controlled_UX_spec`

If this contract is weak, unsupported files will either become manual chaos or create privacy leaks.
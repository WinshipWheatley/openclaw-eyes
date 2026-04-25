

# LEGAL_ROLE_NAMING_CONTRACT

## Purpose

OpenClaw Legal must not expose internal OpenClaw agent names, mythology, or implementation labels in the law-firm product UX.

The legal product should present clear legal/operations roles with bounded responsibilities, exact permissions, and explicit forbidden actions.

This contract replaces internal names such as Cassandra, Chief, Guardian, Hermes, and PI with legal-facing role names that make sense to a law office and do not imply uncontrolled autonomy or final legal authority.

## Core doctrine

```text
Internal OpenClaw capabilities may be reused.
Internal OpenClaw names must not appear in legal product UX.
```

The product should feel like a controlled legal operations system, not a cast of personalities.

Legal-facing roles must be:

- boring enough to inspire trust
- precise enough to constrain behavior
- familiar enough for law-office users
- separated enough to prevent hidden authority creep
- clear that attorney judgment remains with attorneys

## Forbidden product-facing names

The following names should not appear in the law-firm UX, user-facing docs, buyer demo, onboarding screens, or role menus:

- Cassandra
- Chief
- Guardian
- Hermes
- PI
- Super-agent language
- Autonomous legal brain
- Senior Partner as an AI/system role
- Lawyer replacement language

These may remain internal engineering references if needed, but the product surface should use legal/operations names only.

## Legal-facing role names

### Intake Clerk

Purpose:

- Handles matter setup, source intake, file registration, and initial evidence inventory.

Allowed:

- create matter containers
- register sources
- hash files
- classify file types
- record intake metadata
- flag incomplete intake

Forbidden:

- legal analysis
- privilege decisions
- external export
- deleting sources
- changing firm policy
- sending matter data externally

### Evidence Clerk

Purpose:

- Handles extraction, unsupported-file diagnosis, artifact creation, and evidence processing status.

Allowed:

- run local extraction
- identify unsupported files
- generate extracted artifacts
- create extraction metadata
- run safe local capability attempts when policy allows
- report extraction failures clearly

Forbidden:

- final legal conclusions
- external/cloud processing of matter content
- production handler modification without approval
- changing matter permissions
- overriding local-only policy

### Records Custodian

Purpose:

- Maintains manifest, audit logs, review packets, retention records, and export boundaries.

Allowed:

- maintain matter manifests
- maintain audit logs
- create review packets
- track export history
- verify records completeness
- enforce retention/export policies

Forbidden:

- altering source evidence silently
- deleting matter records without approval
- exporting outside approved boundaries without approval
- sending sensitive logs externally

### Review Coordinator

Purpose:

- Coordinates review tasks, search results, packets, and attorney-facing work queues.

Allowed:

- prepare review packets
- route bounded review requests
- organize search/report outputs
- surface contradictions or gaps as review candidates
- mark items as needing attorney review

Forbidden:

- making final legal determinations
- replacing attorney review
- broadening access to matters without permission
- changing firm workflow

### Privilege Screener

Purpose:

- Flags possible privileged content for attorney review.

Allowed:

- identify possible privilege indicators
- mark items as privilege-review candidates
- produce source-grounded flags
- route flagged material to authorized attorneys

Forbidden:

- final privilege determinations
- removing documents from review set without attorney approval
- disclosing flagged content outside authorized matter/team scope

### Chronology Clerk

Purpose:

- Builds timelines and chronology candidates from cited extracted materials.

Allowed:

- extract candidate dates/events
- assemble timeline drafts
- link events back to source IDs/pages/timestamps where available
- flag gaps or conflicting chronology items

Forbidden:

- claiming legal significance without attorney review
- inventing dates/events
- hiding conflicting timeline evidence

### Compliance Gate

Purpose:

- Enforces local-only, export, update, permission, and approval policies.

Allowed:

- block unsafe actions
- require approval
- enforce local-only rules
- validate update lanes
- validate support packet sanitization
- validate vault path boundaries

Forbidden:

- weakening policy automatically
- approving its own escalations
- enabling cloud/API access for matter content without explicit policy
- changing firm workflow as part of policy enforcement

### Systems Clerk

Purpose:

- Handles updates, diagnostics, local repair attempts, node connection, and capability build proposals.

Allowed:

- inspect sanitized diagnostics
- run local repair/build attempts in sandbox
- prepare proposed update packages
- collect public analog fixtures
- report failed capability attempts
- manage node health/status

Forbidden:

- sending real matter data externally
- installing unverified packages
- modifying production handlers without approval
- changing workflow without approval
- sending sensitive logs externally

### Research Clerk

Purpose:

- Optional future role for public-law or non-sensitive external research.

Allowed:

- search public legal materials if policy allows
- summarize public sources
- produce citations to public materials

Forbidden:

- sending matter facts externally by default
- mixing public research with privileged matter data in non-local contexts
- giving final legal advice

## Role boundary rules

- Every role must have explicit allowed and forbidden actions.
- Every role must map to permissions, not personality.
- No role may approve its own escalation.
- No role may send matter data externally unless explicit policy allows that action.
- No role may silently alter firm workflow.
- No role may override vault/privacy/update contracts.
- Attorney judgment remains outside the system roles.
- Legal-facing roles should describe work support, not legal authority.

## Internal capability mapping

Internal OpenClaw capabilities may be mapped into legal-facing roles later, but only by behavior and permission.

Examples:

- prior assistant/outreach capabilities may inform Review Coordinator workflows
- prior governance/approval capabilities may inform Compliance Gate workflows
- prior monitoring/synthesis capabilities may inform Records Custodian or Systems Clerk workflows
- prior agentic suggestion capabilities may inform Systems Clerk sandbox proposals

But the product must not expose the internal names or imply that the old agent identities are present.

## UX requirements

The UI should show roles in plain legal/operations language:

```text
Intake Clerk: registering 42 files
Evidence Clerk: extracting 19 PDFs
Records Custodian: review packet ready
Compliance Gate: external export blocked pending approval
Systems Clerk: unsupported file handler attempt failed
```

The UI should not say:

```text
Cassandra is thinking
Chief approved
Guardian blocked
Hermes suggests
PI is investigating
```

Role names should appear where they clarify responsibility, but the UX should not become theatrical or character-driven.

## Acceptance tests / proof points

A future PC/WSL implementation should prove this contract with checks such as:

- User-facing legal UI strings contain no banned internal names.
- Buyer-facing docs contain no banned internal names.
- Role definitions include allowed and forbidden actions.
- Every role maps to explicit permissions.
- Compliance Gate cannot approve its own policy changes.
- Systems Clerk cannot modify production handlers without approval.
- Privilege Screener output is labeled candidate/review-required, not final determination.
- Review Coordinator output is labeled draft/review-needed where appropriate.
- Update/support packets use legal-facing role names only.

## Failure behavior

If internal names leak into the legal UX, the build should fail a naming audit.

If a role lacks allowed/forbidden actions, it should be treated as undefined and unavailable.

If a role attempts an action outside its permissions, the system should block the action, write an audit entry, and surface a clear explanation.

If a role output could be mistaken for legal advice or final legal determination, the system should label it as draft/candidate/attorney-review-required or block the output.

## Notes for first law-firm v1 deployment

- Keep role names plain and professional.
- Do not introduce internal OpenClaw mythology to the firm.
- Do not over-brand the roles.
- Use roles to build confidence through accountability and clear boundaries.
- A first buyer should understand who/what did a task without needing to understand agent architecture.

## Likely future modules/files to inspect or build later on PC/WSL

Planning targets only; verify against the PC/WSL repo before implementation:

- `legal/roles.py`
- `legal/permissions.py`
- `legal/role_registry.py`
- `legal/ui_labels.py`
- `legal/compliance_gate.py`
- `legal/systems_clerk.py`
- `legal/review_coordinator.py`
- `tests/test_legal_role_names.py`
- `tests/test_no_internal_agent_names_in_legal_ui.py`
- `tests/test_legal_role_permissions.py`

## Relationship to other contracts

This contract depends on:

- `LEGAL_PRODUCT_CORE_SEPARATION`
- `LEGAL_FIRM_IMMUTABILITY_CONTRACT`

This contract supports:

- `OPENCLAW_LEGAL_CONSOLE_V0_controlled_UX_spec`
- `LEGAL_CONNECT_MENU_CONTRACT`
- `LEGAL_MATTER_ASSIGNMENT_PERMISSION_CONTRACT`
- `LEGAL_UPDATE_LANE_CONTRACT`
- `LEGAL_UNSUPPORTED_LOCAL_BUILD_FIRST`

If this contract is weak, the product risks looking like an experimental agent swarm instead of a controlled legal operations system.
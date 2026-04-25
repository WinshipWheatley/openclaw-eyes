

# LEGAL_MATTER_ASSIGNMENT_PERMISSION_CONTRACT

## Purpose

OpenClaw Legal must control matter access through attorney identity, approved devices, explicit matter assignment, and bounded sharing.

A lawyer should be able to open the app on their approved workstation and see the cases assigned to them. If another lawyer needs an opinion or second look, they should be able to send a scoped review request without granting broad matter access.

This contract defines how assigned matters, shared review work, device trust, and permission boundaries should function.

## Core doctrine

```text
Matter access requires attorney identity + approved device + matter assignment/share + firm policy.
```

No single factor is enough.

- A valid user on an unapproved device should not get matter access.
- An approved device with the wrong user should not get matter access.
- A lawyer should not see another lawyer’s matter unless assigned or explicitly shared.
- A review handoff should share only what is needed for that review.
- The Primary Node remains the firm-controlled system of record.

## Identity and device model

### Attorney identity

The user identity represents the person using the system.

It may include:

- attorney name / display label
- role
- bar/license metadata if firm chooses
- firm user ID
- authentication status
- matter assignments
- review permissions

The product should avoid exposing sensitive identity metadata unnecessarily in support packets or reusable product docs.

### Approved device

The device identity represents a trusted firm computer.

It may include:

- device ID
- device display name
- node class
- assigned user
- enrollment status
- local capabilities
- compute-sharing policy
- last seen
- local model status

A device must be enrolled/approved before it can access matter data.

### Matter assignment

Matter assignment links a user to a matter with a permission set.

Assignments may include:

- owner attorney
- assisting attorney
- paralegal/reviewer
- observer/read-only
- administrator
- temporary reviewer

Assignments should be explicit, auditable, and revocable.

## Permission classes

### Matter Owner

Typical permissions:

- view matter dashboard
- view registered sources
- search extracted text
- create notes
- generate reports
- request review from another lawyer
- create review packets
- approve selected matter-level processing actions if firm policy allows

Restricted by default:

- delete source evidence
- export outside vault
- enable cloud tools
- change firm-wide policy
- install updates

### Assisting Attorney

Typical permissions:

- view assigned matter materials
- search extracted text
- create review notes
- respond to review requests
- propose report edits

Restricted by default:

- change matter policy
- external export
- delete sources
- broaden access to other users

### Paralegal / Review Staff

Typical permissions:

- intake review
- source organization
- extraction status review
- search and tagging if enabled
- prepare draft review packets

Restricted by default:

- final legal determinations
- privilege determinations
- external export
- changing attorney assignments

### Observer / Read-Only Reviewer

Typical permissions:

- view specifically shared materials
- comment if allowed
- respond to a bounded request

Restricted by default:

- full matter browsing
- source export
- packet creation
- workflow changes
- update approval

### Firm Administrator

Typical permissions:

- manage users/devices
- manage firm profile
- manage vault settings
- approve node enrollment
- approve updates if policy allows
- assign matter permissions

Restricted by default:

- substituting legal judgment for attorneys
- silently viewing all matter content unless firm policy explicitly grants administrative access

## Lawyer workstation experience

When a lawyer opens OpenClaw Legal on an approved workstation, they should see:

```text
My Matters
Shared With Me
Review Requests
Recent Work
Firm Queue, if permitted
```

The system should make it obvious:

- which matters are assigned to the lawyer
- what permissions the lawyer has in each matter
- what review requests are pending
- what files are blocked/unsupported
- whether the device is allowed to process work in the background

The lawyer should not need to understand the underlying node/task system to do normal work.

## Review handoff workflow

Lawyers should be able to send bounded review/opinion requests to other lawyers.

Examples:

- Send for Review
- Opinion Request
- Privilege Review
- Timeline Check
- Draft Review
- Packet Review
- Second Look

A review handoff should include:

- sender
- recipient
- matter ID
- scoped materials
- question/note
- permission scope
- due date, optional
- status
- audit trail

The receiving lawyer should see it under:

```text
Shared With Me
Review Requests
```

The handoff should not automatically grant full matter access unless the sender explicitly has authority and the firm policy allows it.

## Scoped sharing

Scoped sharing should support sending:

- one source file reference
- one report section
- one search result set
- one review packet
- one timeline segment
- one privilege-candidate bundle
- one note/draft for comment

Scoped sharing should include expiration/revocation where practical.

The system should record:

- what was shared
- why it was shared
- who shared it
- who received it
- when it was opened/reviewed, if tracked
- when it was returned/resolved

## Primary Node authority

The Primary Node owns the authoritative permission state.

Attorney workstations may cache permission state for usability, but must refresh/validate when performing sensitive actions such as:

- export
- packet creation
- external share
- assignment changes
- update approval
- cloud/non-local option use
- production handler modification

If the Primary Node is unreachable, the workstation should fail closed for sensitive actions and allow only policy-approved offline work if explicitly configured.

## Required behavior

- Matter access must require user identity, approved device, matter assignment/share, and firm policy.
- Assignments must be auditable and revocable.
- Review handoffs must be scoped and auditable.
- Workstations must show only assigned/shared matters by default.
- The Primary Node must remain authoritative for permissions.
- Sensitive actions must revalidate permissions where practical.
- Shared review requests must not automatically broaden full matter access.
- Permission labels must be understandable to law-office users.
- Access failures must explain the missing requirement: user, device, assignment, or policy.

## Forbidden behavior

- Do not grant access based only on network presence.
- Do not grant access based only on device enrollment.
- Do not grant access based only on user login without device trust.
- Do not let one lawyer see another lawyer’s matter unless assigned/shared.
- Do not broaden review handoff access silently.
- Do not let worker-node compute permissions imply attorney viewing permissions.
- Do not let administrative device access automatically become legal review access unless firm policy says so.
- Do not allow offline sensitive actions without explicit offline policy.
- Do not use internal OpenClaw names in permission UX.

## UX requirements

Access explanations should be plain and actionable.

Examples:

```text
You cannot open this matter from this computer because this device is not approved for matter access.
```

```text
You have a review request for this packet, but not full matter access.
```

```text
This action requires Matter Owner permission or Firm Administrator approval.
```

```text
Primary Node unavailable. Export actions are paused until permissions can be verified.
```

The UX should avoid vague denial messages. It should tell the user what requirement is missing without exposing sensitive details.

## Acceptance tests / proof points

A future PC/WSL implementation should prove this contract with checks such as:

- Approved user on approved device can see assigned matter.
- Approved user on unapproved device cannot see matter.
- Approved device with wrong user cannot see matter.
- Lawyer cannot see another lawyer’s matter unless assigned/shared.
- Review handoff grants scoped access only.
- Revoked review request removes access.
- Worker compute permission does not grant viewing permission.
- Export requires permission revalidation.
- Primary Node unavailable blocks sensitive actions by default.
- Access denial explains whether user, device, assignment, or policy failed.
- Permission changes are audited.

## Failure behavior

If access cannot be verified, the system should fail closed.

Examples:

- If user identity is unknown, block matter access.
- If device is not enrolled, block matter access.
- If assignment is missing, show no matter or block access.
- If Primary Node is unavailable, block sensitive actions unless offline policy explicitly allows them.
- If review scope cannot be resolved, block the handoff.
- If permission cache is stale, require refresh before sensitive action.

## Notes for first law-firm v1 deployment

- Start with simple roles and explicit assignments.
- Do not overbuild complex permission hierarchies before the first firm validates the workflow.
- Make the lawyer experience simple: assigned matters, shared requests, and clear blocked actions.
- Firm Primary Node should remain the authority even if workstations are useful locally.
- Review handoff may become commercially valuable before full distributed compute.

## Likely future modules/files to inspect or build later on PC/WSL

Planning targets only; verify against the PC/WSL repo before implementation:

- `legal/identity.py`
- `legal/device_trust.py`
- `legal/matter_permissions.py`
- `legal/assignment_store.py`
- `legal/review_handoff.py`
- `legal/permission_cache.py`
- `legal/connect_menu.py`
- `legal/audit.py`
- `tests/test_matter_assignment_permissions.py`
- `tests/test_review_handoff_scope.py`
- `tests/test_device_trust_access.py`
- `tests/test_primary_node_permission_authority.py`

## Relationship to other contracts

This contract depends on:

- `LEGAL_PRODUCT_CORE_SEPARATION`
- `LEGAL_VAULT_PATH_CONTRACT`
- `LEGAL_ROLE_NAMING_CONTRACT`
- `LEGAL_CONNECT_MENU_CONTRACT`

This contract supports:

- `LEGAL_FIRM_PROCESSING_QUEUE_CONTRACT`
- `LEGAL_HUMAN_PRIORITY_NODE_CONTRACT`
- `LEGAL_RESOURCE_HEADROOM_CONTRACT`
- `OPENCLAW_LEGAL_CONSOLE_V0_controlled_UX_spec`

If this contract is weak, the system may process work correctly but expose the wrong matter to the wrong person or device.
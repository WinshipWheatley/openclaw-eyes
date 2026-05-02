# Mac Desktop Mission Control Fixture Contract

Status: docs/test-only fixture contract for app planning. This file does not create a SwiftUI/AppKit app, backend/API/schema implementation, runtime call, service control, provider/model call, approval mutation, or live integration.

Freshness:

- Generated/reviewed: 2026-05-02
- Active source-set baseline: `02_MAC_IOS_APP_BUILD`
- Source commit from active `MANIFEST.md`: `df52ff4687d7dd8a32990658d557cb2b4d1371d9`
- Source basis: Mac/iOS App Build Brief, Routing and Workspaces, Launch Ladder Model, Evidence and Freshness, Security and Authority, Human Operator UX Patterns, Recommended V1 Architecture, and `CHAT_STAY_UP_TO_DATE.md`.
- Stale when: app-state copy, fixture field shape, evidence/freshness proof rules, Workspace Launch Profile boundary, Launch Packet boundary, Approval Receipt lifecycle, or Product Taste / Operator Experience Eval Spine changes.
- Refresh trigger: update before any Mac desktop app implementation, backend/schema slice, generated source-set script, or app fixture loader is built.

## Purpose

This contract defines the first read-only Mac desktop Mission Control fixture set. It gives the future app planner concrete records to display without creating app code or execution behavior.

The fixtures are canonical repo planning/test fixtures, not generated ingest files. They live beside the Launch Ladder docs so the static checker can validate the contract before Mac desktop implementation starts.

## Location

Fixture directory:

```text
docs/planning/launch_ladder/fixtures/mission_control/
```

Required fixtures:

- `fixture_fresh_navigation_profile.json`
- `fixture_malformed_executable_profile.json`
- `fixture_packet_available_not_approved.json`
- `fixture_approval_receipt_valid.json`
- `fixture_approval_receipt_expired.json`
- `fixture_stale_evidence_route.json`
- `fixture_blocked_missing_authority.json`
- `fixture_ui_claim_without_evidence.json`
- `fixture_operator_experience_golden_overview.json`

## Hard Boundaries

This fixture contract must preserve the first-app boundary:

- No SwiftUI/AppKit implementation.
- No backend/API/schema implementation.
- No runtime calls.
- No service control.
- No provider/model calls.
- No Gmail/Telegram actions.
- No Hermes runtime expansion.
- No private-data, vault, log, LegalPrivate, or secrets inspection.
- No approval mutation or Guardian control.
- Workspace Launch Profiles are navigation-only.
- Launch Packets are bounded action objects for review until separately approved.
- Approval Receipts are explicit operator authorization for one packet/action/scope.
- UI State Claims require evidence/freshness proof.
- Product Taste / Operator Experience Evals must reject AI slop.

## Common Fixture Shape

Every Mission Control fixture must include:

```yaml
fixture_id: "stable fixture id matching the file name without .json"
fixture_type: "workspace_launch_profile | launch_packet | approval_receipt | launch_route | ui_state_claim | mission_control_overview"
app_surface: "mac_desktop_mission_control_read_only"
source_set_baseline: "02_MAC_IOS_APP_BUILD"
source_manifest_commit: "df52ff4687d7dd8a32990658d557cb2b4d1371d9"
ui_state: "profile_available | packet_available | launch_ready | approved | executed | succeeded | stale | blocked | unknown"
hard_boundaries: "explicit no-runtime/no-provider/no-private/no-approval-mutation flags"
evidence_refs: "visible proof refs, empty only for malformed evidence-negative fixtures"
freshness: "source basis, commit, generated/reviewed timestamp, stale conditions, refresh trigger"
expected_validation: "static checker expectation for valid/invalid state and forbidden implications"
```

The first app may display these fixtures. It must not execute from them.

## App-State Rules

Mission Control copy must preserve these meanings:

| App state | Meaning |
| --- | --- |
| `profile_available` | Navigation context exists only. It can open machine, folder, workspace, files/tabs, or prompt hints. |
| `packet_available` | A bounded Launch Packet object exists for operator review only. It is not approved. |
| `launch_ready` | Preconditions appear satisfied for operator review only. It is not launch authorization. |
| `approved` | A current Approval Receipt permits one named packet/action/scope only. |
| `executed` | The action was attempted. This does not mean success. |
| `succeeded` | Execution result plus validation evidence proves success. |
| `stale` | Source basis, timestamp, evidence, or freshness is no longer valid. |
| `blocked` | Authority, evidence, freshness, validation, or scope is missing or invalid. |
| `unknown` | The app lacks evidence. Do not soften this into confidence. |

The app must not collapse profile, packet, approval, execution, and result into one "agent progress" object.

## Golden Fixtures

Golden fixtures are valid records that the app can render as read-only Mission Control examples:

- `fixture_fresh_navigation_profile.json`: profile available means navigation context exists only.
- `fixture_packet_available_not_approved.json`: packet available means bounded action object exists for review only.
- `fixture_approval_receipt_valid.json`: approved means one Approval Receipt permits one named packet/action/scope.
- `fixture_approval_receipt_expired.json`: expired receipt is a valid record but cannot authorize execution.
- `fixture_stale_evidence_route.json`: stale route blocks launch-ready copy and shows stale reason.
- `fixture_blocked_missing_authority.json`: blocked route shows missing authority clearly.
- `fixture_operator_experience_golden_overview.json`: calm overview with North Star, route, authority, freshness, evidence, blocker, and next safe action.

## Malformed Fixtures

Malformed fixtures are intentionally invalid records used to prove the checker rejects bad app states:

- `fixture_malformed_executable_profile.json`: a Workspace Launch Profile with executable commands is invalid.
- `fixture_ui_claim_without_evidence.json`: `healthy/current/tested/running/synced` style claims without source commit, timestamp, artifact, and evidence are invalid.

Malformed fixtures must be labeled as malformed and must never be treated as app-launch examples.

## Static Validation Expectations

The static checker must verify:

- All nine required fixture files exist and parse as JSON.
- Every fixture names `mac_desktop_mission_control_read_only`.
- Every fixture names `02_MAC_IOS_APP_BUILD` and source manifest commit `df52ff4687d7dd8a32990658d557cb2b4d1371d9`.
- Every fixture preserves the hard boundaries: no runtime calls, no service control, no provider/model calls, no Gmail/Telegram action, no Hermes runtime expansion, no private/log/vault/LegalPrivate/secrets inspection, no approval mutation, and no app execution.
- Workspace Launch Profiles contain only navigation actions and a `required_next_launch_packet_for_execution` handoff.
- Workspace Launch Profiles with executable command fields are invalid.
- Launch Packet fixtures are review-only until a valid Approval Receipt is present.
- Approval Receipt fixtures bind to exactly one packet/action/scope and do not broaden scope.
- Expired receipts cannot authorize execution.
- UI claims using `healthy`, `current`, `tested`, `running`, or `synced` without evidence are invalid.
- `unknown` remains unknown when evidence is absent.
- Product Taste / Operator Experience golden fixtures expose evidence, authority, freshness, and next safe action without fake intelligence, fake urgency, hidden authority, chatbot slop, or generic admin-panel collapse.

## App Implementation Blockers

These questions do not block this planning slice, but they should block Mac desktop implementation:

- What exact local fixture loader path will the Mac desktop app use?
- Which UI test runner will validate the Product Taste / Operator Experience Eval Spine?
- How will the app display expired Approval Receipts without making them look actionable?
- How will the app show `unknown` without nudging the operator toward false confidence?
- Which backend/schema slice will later formalize these JSON shapes without changing the read-only first-app boundary?

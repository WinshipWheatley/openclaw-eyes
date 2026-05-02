# Human Operator UX Patterns

## Purpose

This document describes UX patterns for an Operator Harness that supports a skilled human operator without creating hidden autonomy, false certainty, or approval fatigue.

## Source Basis

- Human-AI UX: [Microsoft Guidelines for Human-AI Interaction](https://www.microsoft.com/en-us/research/?p=564561), [Google PAIR Guidebook](https://pair.withgoogle.com/guidebook-v2/), [Google PAIR Explainability + Trust](https://pair.withgoogle.com/guidebook-v2/chapter/explainability-trust/), and [NIST Four Principles of Explainable AI](https://www.nist.gov/publications/four-principles-explainable-artificial-intelligence).
- Human factors: Parasuraman/Sheridan/Wickens automation taxonomy, [Onnasch et al. meta-analysis](https://journals.sagepub.com/doi/pdf/10.1177/0018720813501549), and Bainbridge's "Ironies of Automation."
- Accessibility and UI reliability: [WCAG 2.2](https://www.w3.org/TR/WCAG22/) and platform sandbox/keychain guidance from [Apple](https://developer.apple.com/documentation/security/protecting-user-data-with-app-sandbox), [Electron](https://www.electronjs.org/docs/latest/tutorial/security), and [Tauri](https://v2.tauri.app/security/capabilities/).

## Confirmed Best Practices

Help the user form a correct mental model. Microsoft and Google HAI guidance both emphasize showing system capability, uncertainty, recovery paths, and changes over time. The operator should know what the harness observed, inferred, and cannot know.

Use explanations when they change decisions. NIST's explainability principles require explanations that are meaningful to the intended recipient. A long explanation is not automatically better; the UI should expose enough rationale to support approval, rejection, or investigation.

Calibrate trust instead of maximizing trust. Google PAIR warns that confidence displays can help or mislead depending on user context. For OpenClaw, the goal is not to make the operator trust the harness more; it is to help them trust it accurately.

Keep humans in the loop where failure recovery matters. Automation literature shows higher automation can reduce workload in normal operation but worsen situation awareness and failure performance. Approval UX should keep the operator oriented before action, not only after a failure.

Respect attention. Operational dashboards often overwhelm users with status. The harness should use progressive disclosure: scan-level status first, exact packet/evidence drilldown second.

## Operator UX Model

The harness should have five main operator views:

1. Atlas View

Shows deployments, systems, subsystems, source-set freshness, active ladders, and evidence status. It should answer "where are my builds and what needs attention?"

2. Ladder View

Shows the staged path toward a North Star task. It should answer "what route am I on and what approval is next?"

3. Packet View

Shows the exact action object. It should answer "what will happen if I approve?"

4. Evidence View

Shows proof artifacts and validation results. It should answer "what actually happened?"

5. Drift View

Shows stale source sets, changed workspaces, missing evidence, and route assumptions that are no longer valid. It should answer "what can I no longer rely on?"

## Confidence And Freshness Display

Use separate indicators for separate ideas:

- Freshness: how recently source state was observed.
- Completeness: whether required source areas are included.
- Confidence: how strongly the harness supports an inference.
- Validation: whether a check passed.
- Authority: whether the operator has approved the exact packet.

Do not collapse these into one score. A packet can be fresh but risky, validated but unapproved, or high confidence but incomplete.

Recommended display:

- `Fresh`: source set has current commit/hash/timestamp and no stale reason.
- `Stale`: source changed or TTL expired.
- `Unknown`: source cannot be verified without out-of-scope inspection.
- `Blocked`: verification would require private data, secrets, logs, or forbidden runtime state.

Use small chips for scan, then a detail drawer:

- Source observed at.
- Source path or manifest.
- Commit/hash.
- Validator used.
- Missing inputs.
- Deferred checks.

## Approval UX

Approval should bind to exact content:

- Packet hash.
- Target deployment.
- Tool/machine/workspace.
- Scope and exclusions.
- Stop conditions.
- Validation requirements.
- Secret-handling statement.
- Parallel bundle, if any.

The approval screen should show a concise diff from the previous packet version. If the packet changes after approval, approval becomes invalid.

Guardian may approve or deny exact packets, but Guardian must not collect or handle secrets. If the next step requires a password, passphrase, token, hardware key tap, passkey, or OS credential prompt, the UI should route the operator to local/manual entry and record only that a credential step was required, not the credential.

## Pattern Recommendations

- Use "review, approve, launch, verify" as the core rhythm.
- Show one primary next action, but always show why it is safe or blocked.
- Put exclusions next to scope, not in a separate settings page.
- Show "what this packet cannot do" as clearly as "what this packet will do."
- Treat stale and blocked as normal states, not errors to hide.
- Require reason capture for operator overrides.
- Make evidence browseable by ladder, deployment, packet, date, and source set.

## Risks And Anti-Patterns

- Single confidence score that blends freshness, quality, and permission.
- Approval fatigue from repeated low-risk prompts while high-risk approvals are visually similar.
- "AI says" language without source or validation.
- Console-only state that disappears after the session.
- Hiding blocked states because they are visually inconvenient.
- Copy-to-clipboard secret flows.
- Modal sprawl where the operator cannot compare packet, route, and evidence.

## OpenClaw Recommendation

Design the v1 UI as a local evidence browser and packet approval surface. Avoid a command-center fantasy. The operator should feel more oriented, not more managed.


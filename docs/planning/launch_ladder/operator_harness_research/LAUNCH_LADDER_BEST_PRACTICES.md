# Launch Ladder Best Practices

## Purpose

A Launch Ladder is a staged path toward a North Star task. It is not just a task board, Kanban board, runbook, or dashboard. Its job is to compress ambiguity into an operator-approved sequence of launch packets with visible evidence, freshness, risks, and deferred work.

## Source Basis

- Flow and work visualization: [Kanban University Kanban Guide](https://kanban.university/kanban-guide/) and [Open Guide to Kanban](https://kanbanguides.org/open-guide-to-kanban/2025.7/pdf/open-guide-to-kanban.en-us.pdf).
- Operational execution: [Google SRE postmortem culture](https://sre.google/sre-book/postmortem-culture/), [Google SRE eliminating toil](https://sre.google/sre-book/eliminating-toil/), [Atlassian incident management](https://www.atlassian.com/incident-management), and [Microsoft Azure Well-Architected Operational Excellence](https://learn.microsoft.com/en-us/azure/well-architected/operational-excellence/).
- Automation and human control: [Microsoft Guidelines for Human-AI Interaction](https://www.microsoft.com/en-us/research/?p=564561), [Google PAIR Explainability + Trust](https://pair.withgoogle.com/guidebook-v2/chapter/explainability-trust/), and [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework).
- Structured records: [Google Cloud ADR overview](https://cloud.google.com/architecture/architecture-decision-records), [JSON Schema](https://json-schema.org/specification), and [OpenAPI Specification](https://www.openapis.org/).

## What A Launch Ladder Is

A Launch Ladder is a progressive, staged path from intent to verified outcome. Each rung should answer:

- What decision or action does this rung advance?
- What source set is being used?
- What exact machine, tool, workspace, and constraints apply?
- What evidence proves completion?
- What freshness or drift risks exist?
- What work is intentionally deferred?
- What approval is required before the next rung?

The ladder is goal-shaped. A task board is inventory-shaped. Kanban is flow-shaped. A runbook is procedure-shaped. A dashboard is status-shaped. A Launch Ladder should borrow from all four without becoming any one of them.

## Differences From Adjacent Tools

Task board:

- Tracks units of work.
- Usually does not encode execution packets, machine context, source freshness, or evidence requirements.
- Risk: "done" becomes a status label instead of proof.

Kanban board:

- Visualizes work in process, policies, flow, and feedback.
- Useful for managing load and bottlenecks.
- Risk: flow optimization does not guarantee that each step has enough authority, validation, or proof.

Runbook:

- Lists steps for repeatable operations.
- Useful for incidents and standard operational tasks.
- Risk: static procedures drift from current repo, machine, and tool state.

Dashboard:

- Shows status and metrics.
- Useful for scanning.
- Risk: it can produce awareness without a safe next action.

Launch Ladder:

- Converts a North Star task into staged launch packets.
- Each rung has explicit authority, source set, execution context, validation, evidence, and stop conditions.
- It is not a backlog. It is a controlled route to launch.

## Confirmed Best Practices

Make policies explicit. Kanban guidance emphasizes explicit workflow policies and feedback loops. For a Launch Ladder, explicit policy means every rung declares what counts as ready, approved, blocked, complete, and stale.

Keep operators oriented. Human-AI interaction guidance recommends showing what the system can do, what it cannot do, when it is uncertain, and how the user can recover. A ladder should keep "where am I, why this next, what happens if I approve" visible.

Treat operational records as learning assets. SRE postmortems and runbooks work because they capture context and follow-up actions. Launch Ladder evidence should preserve the reason for decisions, not only the final state.

Limit toil but do not erase understanding. SRE toil guidance supports automating repetitive, tactical work, but also warns that automation should not eliminate human understanding. The ladder can prefill packets and validations, but it should keep rationale and deferred checks visible.

Use structured contracts for repeatability. JSON Schema/OpenAPI-style contracts reduce ambiguity between UI, CLI, validators, and future clients. Launch packets should be schema-validated before approval.

## Route Compression

Route Compression offers three views:

- Direct Route: the shortest safe sequence that reaches the North Star with minimal scaffolding.
- Balanced Route: the default route that includes enough discovery, validation, and evidence to avoid fragile work.
- System Route: the expanded route that includes architecture cleanup, source refresh, documentation, and broader drift checks.

Compression must not hide deferred work. Every compressed route should show:

- Rungs included now.
- Rungs deferred.
- Assumptions accepted.
- Validation skipped or postponed.
- Risk introduced by compression.
- A re-expansion path back to the System Route.

The operator should never approve "Direct Route" as a vibe. They should approve a concrete route object with its deferred-work manifest.

## Launch Packet Structure

Minimum packet fields:

```yaml
packet_id: "lp-YYYYMMDD-shortname"
packet_version: 1
north_star: "Concrete outcome"
route_type: "direct | balanced | system"
operator_intent: "Plain English task"
authority:
  approval_required: true
  approved_by: null
  approval_time: null
  approval_scope: "exact-packet-hash"
target:
  deployment_id: "personal/openclaw/main"
  machine: "pc-wsl | mac | codex-desktop | future-client"
  workspace: "/absolute/or/declared/workspace"
  tool: "codex | shell | chatgpt-project-source-refresh | manual"
source_set:
  manifest_path: "docs/source_sets/example.md"
  commit: "git-sha-or-null"
  generated_at: "ISO-8601"
  freshness_state: "fresh | stale | unknown | blocked"
scope:
  include_paths: []
  exclude_paths:
    - ".chief.env"
    - ".google-secrets/"
    - "LegalPrivate/"
    - "vaults/"
constraints:
  no_private_data: true
  no_runtime_mutation: true
  no_provider_calls: true
  no_secret_handling: true
execution:
  commands: []
  human_steps: []
  parallel_bundle: null
validation:
  required_checks: []
  evidence_required: []
stop_conditions:
  - "Unexpected credential prompt"
  - "Path outside declared scope"
  - "Validation failure"
rollback:
  strategy: "manual review | revert commit | no mutation expected"
evidence:
  trail_path: "docs/evidence/..."
  expected_artifacts: []
deferred_work: []
```

## Evidence Trail Structure

Each ladder rung should write or link to evidence:

- Packet hash and route type.
- Source set used.
- Commands or manual steps performed.
- Validation output summary.
- Decisions and assumptions.
- Files changed, if any.
- Exclusions honored.
- Freshness status after completion.
- Deferred work carried forward.

Evidence should be human-readable Markdown with optional structured front matter for indexing.

## OpenClaw Recommendations

- Implement ladders as Markdown plus a validated packet schema before building a complex UI.
- Make route compression a view over a full route graph, not a separate hidden plan.
- Require every ladder to start with a North Star, explicit non-goals, and validation gates.
- Use compact status chips: `ready`, `needs approval`, `running`, `blocked`, `stale`, `validated`, `deferred`.
- Add "why this rung" and "what this unlocks" to each rung.
- Keep ladder history immutable enough to audit. Supersede rungs instead of silently rewriting them.

## Risks And Anti-Patterns

- A ladder becomes a prettier Kanban board.
- Rungs are named with verbs but lack exact launch packets.
- Direct Route hides skipped validation.
- Parallelism is added before write-set and stop-condition rules exist.
- Evidence is only screenshots or terminal logs instead of structured proof.
- Source freshness is shown as a color without a timestamp, source, or reason.


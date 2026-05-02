# Multi-Deployment Control Plane

## Purpose

This document researches how OpenClaw should represent multiple personal, client, company, agent, subsystem, and module deployments safely. It uses "control plane" as an architectural analogy, but recommends that v1 remain an inventory, routing, approval, and evidence plane, not a live mutating fleet controller.

## Source Basis

- Control-loop and desired/observed state: [Kubernetes controllers](https://kubernetes.io/docs/concepts/architecture/controller/) and [OpenGitOps principles](https://opengitops.dev/).
- Operational reliability: [Google SRE](https://sre.google/), especially postmortems and toil reduction.
- Security and inventory: [NIST CSF 2.0](https://www.nist.gov/node/1840561), [NIST SP 800-53 Rev. 5](https://csrc.nist.gov/Pubs/sp/800/53/r5/upd1/Final), and [NIST SP 800-207 Zero Trust](https://www.nist.gov/publications/zero-trust-architecture-0).
- Local-first design: [Local-first software](https://martin.kleppmann.com/2019/10/23/local-first-at-onward.html).
- Event interoperability: [CloudEvents](https://cloudevents.io/) and [OpenTelemetry signals](https://opentelemetry.io/docs/concepts/signals/).

## Confirmed Best Practices

Separate desired state from observed state. Kubernetes and GitOps patterns work because they distinguish what should be true from what is currently true. OpenClaw should model desired launch routes separately from observed evidence.

Use versioned, immutable history for operational intent. GitOps guidance relies on versioned declarations. For OpenClaw, packet and ladder revisions should be content-addressed or hash-bound so approvals remain auditable.

Inventory comes before control. NIST CSF and SP 800-53 both depend on knowing system boundaries, assets, access controls, and audit scope. A Multi-OpenClaw Atlas should first answer "what exists, where, under whose authority, with what freshness?"

Resource-centric security beats perimeter assumptions. NIST Zero Trust frames access decisions around resources and continuous evaluation. OpenClaw should not assume that "same machine" or "same operator" means all deployments can be freely cross-accessed.

Events need standard metadata. CloudEvents and OpenTelemetry show the value of consistent metadata for event routing, diagnostics, and traces. Evidence and packet events should have stable IDs, timestamps, subjects, sources, and correlation IDs.

## V1 Atlas Model

The Multi-OpenClaw Command Atlas should represent:

- Operator domains: personal, client, company, experimental.
- Deployments: a concrete OpenClaw-style build in a workspace or device context.
- Systems: product or operational systems inside a deployment.
- Subsystems/modules: bounded areas that may have their own source sets and launch ladders.
- Ladders: active or archived staged routes.
- Packets: exact launch objects.
- Evidence trails: proof artifacts and validation summaries.
- Source sets: curated folders or manifests for ChatGPT Projects or other manual context refreshes.
- Boundaries: forbidden areas, credential boundaries, runtime boundaries, legal/private exclusions.

## Deployment Registry

Minimum registry fields:

```yaml
deployment_id: "client/acme/openclaw-main"
display_name: "Acme OpenClaw Main"
domain: "client"
authority_owner: "operator"
workspace:
  path: "/declared/path/or/null"
  platform: "pc-wsl | mac | windows | linux | codex-desktop | future"
  access_mode: "read-only-index | local-approved-launch | manual-only"
boundaries:
  forbidden_paths: []
  private_data_policy: "do-not-inspect"
  runtime_mutation: "forbidden-v1"
  provider_calls: "forbidden-v1"
source_sets:
  - id: "chatgpt-project-refresh"
    manifest: "..."
    freshness: "fresh | stale | unknown | blocked"
systems: []
last_observed:
  time: "ISO-8601"
  method: "manual | local-scan | packet-evidence"
evidence_root: "docs/evidence/..."
```

The registry should not store secrets, tokens, passphrases, vault paths requiring inspection, or private content summaries.

## Control Plane Boundaries

V1 should support:

- Local inventory of declared deployments.
- Manual or local-safe discovery of public project files.
- Launch Ladder creation and packet validation.
- Evidence indexing and drift reporting.
- Source-set refresh folder generation.
- Operator-approved local command launch only within declared scope.

V1 should not support:

- Remote mutation of client/company systems.
- Continuous background reconciliation.
- Cross-machine daemons.
- Credential brokering.
- Runtime service mutation.
- Cloud sync of private deployment state.
- Hidden telemetry collection.

## Three Architecture Approaches

Approach A: Repo-native Atlas plus local index

- Store registry, ladders, packets, and evidence as Markdown/YAML/JSON in the repo.
- Use a lightweight local index for search and UI speed.
- Best fit for v1 because it preserves auditability and avoids a premature control plane.

Approach B: Local desktop app with embedded database

- Use a desktop shell to index multiple workspaces and display the Atlas.
- Stronger UX, but higher risk of hidden state and platform-specific permission issues.
- Good v2 candidate after schemas stabilize.

Approach C: Service-backed fleet control plane

- Central server receives deployment state and dispatches actions.
- Useful for enterprise fleet management, but violates v1 constraints around local-first authority, no hidden autonomy, and no runtime mutation.
- Defer until there is proven demand and a formal security model.

Recommended: Approach A now, with schema discipline that preserves Approach B later.

## OpenClaw Recommendations

- Treat Atlas nodes as references to evidence and packets, not as remote handles.
- Add `access_mode` to every deployment so the UI cannot imply launch authority where none exists.
- Require per-deployment exclusions and private-data policy.
- Use stable identifiers that do not leak client secrets or legal matter names.
- Show boundary warnings when moving from personal to client/company contexts.
- Keep "observed" and "desired" visually distinct.

## Risks And Anti-Patterns

- Atlas becomes a remote admin panel.
- Client deployments are mixed with personal deployments without visual authority boundaries.
- A stale source set is used to approve a live action.
- The registry stores sensitive summaries or credential hints.
- Background discovery scans private folders.
- Local-first is abandoned before the local artifact model is stable.


# Evidence Freshness And Drift Detection

## Purpose

This document defines how OpenClaw should structure evidence trails, freshness indicators, source-set manifests, and drift detection for an Operator Harness and Launch Ladder system.

## Source Basis

- Observability and operational evidence: [OpenTelemetry signals](https://opentelemetry.io/docs/concepts/signals/), [Google SRE postmortem culture](https://sre.google/sre-book/postmortem-culture/), and [Google SRE eliminating toil](https://sre.google/sre-book/eliminating-toil/).
- Desired/current state and drift: [Kubernetes controllers](https://kubernetes.io/docs/concepts/architecture/controller/) and [OpenGitOps principles](https://opengitops.dev/).
- Provenance and supply chain evidence: [SLSA provenance](https://slsa.dev/provenance), [SLSA security levels](https://slsa.dev/spec/v1.0/levels), and [in-toto](https://in-toto.io/).
- Decision records: [Google Cloud ADR overview](https://cloud.google.com/architecture/architecture-decision-records).
- Security/logging exclusions: [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) and [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html).

## Confirmed Best Practices

Evidence should be structured enough to query and human-readable enough to audit. SRE postmortems and ADRs work because they capture what happened, why it happened, and what follows.

Freshness must be attached to observations, not opinions. A source-set claim should name when and how it was observed, what commit/hash/path it came from, and what could not be inspected.

Drift detection compares declared state with observed state. Kubernetes and GitOps patterns separate desired state from current state; OpenClaw can use that distinction without adding continuous reconciliation.

Provenance needs where, when, how, and from what. SLSA and in-toto guidance make this concrete for software artifacts. OpenClaw evidence can use the same basic shape for launch packets and docs.

Logs can leak sensitive data. OWASP logging guidance warns against recording secrets, sensitive data, and other disallowed content. Evidence Trails should summarize validation without dumping unsafe raw logs.

## Evidence Trail Format

Recommended Markdown front matter:

```yaml
evidence_id: "ev-YYYYMMDD-shortname"
packet_id: "lp-YYYYMMDD-shortname"
packet_hash: "sha256:..."
deployment_id: "personal/openclaw/main"
ladder_id: "ladder-..."
route_type: "direct | balanced | system"
source_set_id: "source-refresh-main"
source_commit: "git-sha-or-null"
source_manifest_hash: "sha256:..."
operator: "local-operator-id"
started_at: "ISO-8601"
completed_at: "ISO-8601"
freshness_state: "fresh | stale | unknown | blocked"
validation_state: "passed | failed | partial | not-run"
secret_policy: "no-secrets-recorded"
private_data_policy: "not-inspected"
```

Recommended body sections:

- Summary.
- Packet scope.
- Source set used.
- Steps performed.
- Validation results.
- Files changed or artifacts created.
- Exclusions honored.
- Drift observations.
- Deferred work.
- Follow-up recommendations.

## Freshness Model

Freshness state should be deterministic:

- `fresh`: observed source matches declared commit/hash and TTL has not expired.
- `stale`: declared source changed, TTL expired, or dependent evidence predates source changes.
- `unknown`: freshness cannot be established from available non-private context.
- `blocked`: freshness would require forbidden private/log/vault/secret/runtime inspection.

Every freshness indicator should include:

- `observed_at`.
- `observed_by`.
- `source_ref`.
- `hash_or_commit`.
- `ttl_policy`.
- `stale_reason`.
- `blocked_reason`.

## Drift Types

Source drift:

- Files changed after source-set generation.
- Manifest excludes a path now required by a packet.
- Source-set refresh folder no longer matches repo commit.

Packet drift:

- Packet changed after approval.
- Target workspace changed.
- Command list changed.
- Scope or exclusions changed.

Evidence drift:

- Evidence predates the current packet.
- Validation was run against a different source set.
- Evidence artifact missing or moved.

Deployment drift:

- Deployment registry path changed.
- Platform changed.
- Access mode changed.
- Boundary policy changed.

Policy drift:

- Forbidden path list changed.
- Approval class changed.
- v1 non-goals changed.

## UI Pattern

Use compact indicators:

- `Fresh`
- `Stale`
- `Unknown`
- `Blocked`
- `Validated`
- `Partial`
- `No Evidence`

Clicking an indicator should reveal the evidence and source details. Do not use color alone. Do not display a single "health score" for a ladder or deployment.

## OpenClaw Recommendations

- Add source-set manifests before adding complex source refresh automation.
- Hash launch packets and source manifests.
- Mark approval invalid if packet hash changes.
- Treat missing evidence as a first-class state.
- Generate drift reports as Markdown under the same research/planning or evidence tree.
- Never use raw logs as evidence in v1.
- Make "blocked by private-data policy" a success of the boundary system, not a failure.

## Risks And Anti-Patterns

- Evidence trails that are only terminal dumps.
- Freshness badges without timestamps or source links.
- Drift detection that scans forbidden folders.
- Overwriting evidence instead of superseding it.
- Treating "not checked" as "passed."
- Raw logs accidentally capturing secrets, legal content, or private user data.
- A source-set refresh that silently includes too much.


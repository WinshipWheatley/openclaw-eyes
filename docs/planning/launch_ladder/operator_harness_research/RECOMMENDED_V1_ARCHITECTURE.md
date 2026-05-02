# Recommended V1 Architecture

## Purpose

This document gives a concrete v1 architecture recommendation for the Operator Harness, Launch Ladders, Launch Packets, Evidence Trails, Route Compression, Parallel Step Bundles, source-set refresh, and the future Multi-OpenClaw Command Atlas.

## Source Basis

- Local-first and artifact-first: [Local-first software](https://martin.kleppmann.com/2019/10/23/local-first-at-onward.html), [OpenGitOps principles](https://opengitops.dev/), and [Google Cloud ADR overview](https://cloud.google.com/architecture/architecture-decision-records).
- Control and evidence patterns: [Kubernetes controllers](https://kubernetes.io/docs/concepts/architecture/controller/), [SLSA provenance](https://slsa.dev/provenance), [OpenTelemetry signals](https://opentelemetry.io/docs/concepts/signals/), and [Google SRE](https://sre.google/).
- Security: [NIST SP 800-207](https://www.nist.gov/publications/zero-trust-architecture-0), [NIST SP 800-218](https://csrc.nist.gov/pubs/sp/800/218/final), [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html), and [OWASP Logging](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html).
- Human-AI UX: [Microsoft Human-AI Guidelines](https://www.microsoft.com/en-us/research/?p=564561), [Google PAIR](https://pair.withgoogle.com/guidebook-v2/), and [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework).

## Recommendation

Build v1 as a repo-native, local-first harness with schema-validated artifacts and a thin local UI/CLI.

Canonical state:

- Markdown/YAML/JSON files in the workspace.
- Git history for review and provenance.
- Content hashes for packets and approval binding.

Non-canonical acceleration:

- Optional local index for search.
- Optional local UI cache.
- Rebuildable from artifacts.

Execution:

- Local command adapter only.
- Executes exact approved packets.
- Enforces scope, exclusions, risk class, and stop conditions.
- Writes evidence.

No v1 service/runtime mutation, private/log/vault/legal inspection, provider calls, credential brokering, cloud sync, or hidden background autonomy.

## Three Approaches Considered

Approach 1: Repo-native artifact harness

- Pros: fits local-first; transparent; easy to audit; low infrastructure; future clients can read stable schemas.
- Cons: less polished initial UX; indexing/search may be basic.
- Verdict: recommended for v1.

Approach 2: Desktop command center

- Pros: better visual Atlas and approval UX; easier cross-workspace browsing.
- Cons: higher platform/security burden; hidden app database risk; IPC permission design needed.
- Verdict: v2 after schemas and validators are proven.

Approach 3: Service-backed control plane

- Pros: multi-device and multi-client coordination; centralized policy.
- Cons: violates v1 local-first constraints; major threat model; risk of hidden autonomy and credential pressure.
- Verdict: explicitly out of scope for v1.

## Core Components

1. Schema package

- `LaunchPacket`
- `LaunchLadder`
- `EvidenceTrail`
- `SourceSetManifest`
- `DeploymentRegistry`
- `ApprovalRecord`
- `ParallelStepBundle`
- `DriftReport`

2. Policy package

- Forbidden paths.
- Risk classes.
- v1 non-goals.
- Secret-handling rules.
- Private-data boundaries.

3. Validator package

- Schema validation.
- Path boundary validation.
- Packet hash validation.
- Approval validity.
- Freshness validation.
- Parallel write-set collision validation.

4. Artifact generator

- Markdown ladder docs.
- Launch packet docs.
- Evidence trail docs.
- Drift reports.
- Source-set manifests.

5. Local adapter

- Runs approved local commands.
- Captures safe summaries.
- Stops on forbidden paths, credential prompts, validation failure, or scope expansion.

6. Local UI

- Atlas browser.
- Ladder browser.
- Packet approval surface.
- Evidence browser.
- Drift/freshness view.

## Directory Sketch

```text
docs/planning/launch_ladder/
  ladders/
  packets/
  evidence/
  source_sets/
  drift_reports/
  registry/
  operator_harness_research/
```

The exact directory names can change, but the separation should remain: plans, packets, evidence, source sets, drift, registry, research.

## Launch Flow

1. Operator states North Star task.
2. Harness drafts Direct, Balanced, and System routes.
3. Operator chooses or edits route.
4. Harness generates launch packet.
5. Validator checks schema, scope, exclusions, freshness, and risk class.
6. Operator reviews exact packet hash.
7. Guardian may approve/deny exact packet.
8. Local adapter runs only approved local actions.
9. Evidence Trail is written.
10. Drift/freshness state updates.

## Recommended V1 Defaults

- `route_type`: Balanced.
- `provider_calls`: false.
- `runtime_mutation`: false.
- `private_data_inspection`: false.
- `credential_handling`: operator-local only.
- `parallel_bundle_execution`: planning/validation only until proven.
- `evidence_required`: true.
- `packet_hash_required`: true.
- `approval_expires_on_packet_change`: true.

## Build Order

1. Define schemas and policy constants.
2. Build packet/source/evidence validators.
3. Build Markdown artifact generators.
4. Build source-set refresh manifest generator.
5. Build drift report generator.
6. Build CLI around the above.
7. Build local UI as read/approve/browse shell.
8. Add controlled local launch adapter.
9. Add Parallel Step Bundle validation.
10. Consider desktop shell.

## OpenClaw-Specific Decisions

- The Operator Harness is not a new authority layer.
- The Multi-OpenClaw Command Atlas is an indexed map over declared deployments and artifacts in v1.
- Launch Ladders are staged approval/evidence routes, not generic project boards.
- Launch Packets are exact action contracts.
- Evidence Trails are repo-side proof artifacts.
- Source-set refresh is local and manual-provider-friendly.
- Guardian approves packet hashes, not intentions.

## Risks And Mitigations

- Risk: app database becomes hidden source of truth.
  Mitigation: make index rebuildable from artifacts.

- Risk: operator approves stale packet.
  Mitigation: packet hash plus source freshness gate.

- Risk: route compression hides skipped work.
  Mitigation: deferred-work manifest required.

- Risk: parallel lanes collide.
  Mitigation: write-set collision validator and stop-on-overlap.

- Risk: secrets leak into evidence.
  Mitigation: no raw logs, secret redaction, credential prompt stop condition.

- Risk: Atlas implies remote control.
  Mitigation: `access_mode` on every deployment and no v1 remote mutation.


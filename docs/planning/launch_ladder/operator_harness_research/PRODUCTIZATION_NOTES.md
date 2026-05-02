# Productization Notes

## Purpose

This document turns the research into product guidance: what OpenClaw should build first, what v1 should not do, and how to avoid overbuilding the Operator Harness, Launch Ladders, and Multi-OpenClaw Command Atlas.

## Source Basis

- Product safety and human-AI design: [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework), [Microsoft Human-AI Guidelines](https://www.microsoft.com/en-us/research/?p=564561), and [Google PAIR Guidebook](https://pair.withgoogle.com/guidebook-v2/).
- Operational excellence: [Microsoft Azure Well-Architected Operational Excellence](https://learn.microsoft.com/en-us/azure/well-architected/operational-excellence/), [Google SRE](https://sre.google/), and [Atlassian incident management](https://www.atlassian.com/incident-management).
- Secure-by-design and local-first: [CISA Secure by Design](https://www.cisa.gov/securebydesign), [NIST SSDF](https://csrc.nist.gov/pubs/sp/800/218/final), and [Local-first software](https://martin.kleppmann.com/2019/10/23/local-first-at-onward.html).
- Architecture records and schemas: [Google Cloud ADR overview](https://cloud.google.com/architecture/architecture-decision-records), [JSON Schema](https://json-schema.org/specification), and [CloudEvents](https://cloudevents.io/).

## Product Thesis

OpenClaw should not productize "autonomous agents." It should productize operator leverage:

- Better context packaging.
- Safer launch decisions.
- Clearer approval boundaries.
- Faster evidence review.
- Freshness and drift awareness.
- Multi-build orientation without cross-build leakage.

The best v1 is a harness that makes the operator more accurate, faster, and less overloaded while preserving authority.

## Confirmed Best Practices

Start with standardization before automation. Operational excellence guidance emphasizes standard processes and safe deployment before heavy automation. For OpenClaw, schemas and artifacts come before live orchestration.

Make security the default path. CISA and NIST SSDF guidance favor secure-by-design defaults. The product should block forbidden actions by default and make safe local work easy.

Show capability and limits. Human-AI UX guidance recommends communicating what the system can and cannot do. Product copy and UI should avoid implying the harness knows more than its source sets support.

Use durable records. ADRs, postmortems, and evidence artifacts reduce future confusion. OpenClaw should make records part of the workflow, not an afterthought.

## Product Surfaces

1. Launch Ladder Builder

- Takes a North Star task.
- Creates Direct, Balanced, and System route candidates.
- Shows deferred work and assumptions.
- Produces launch packets.

2. Launch Packet Validator

- Checks required fields.
- Checks forbidden paths.
- Checks source freshness.
- Checks risk class.
- Checks approval hash.

3. Evidence Browser

- Shows proof by ladder, packet, source set, deployment, and date.
- Highlights missing or stale evidence.

4. Source-Set Refresher

- Generates declared source-set folders/manifests for manual use in provider contexts.
- Applies v1 exclusions.
- Records freshness metadata.

5. Atlas Registry

- Lists deployments and boundaries.
- Shows status without live mutation.
- Links to ladders, packets, and evidence.

## What V1 Should Not Do

- No service/runtime mutation.
- No hidden background agents.
- No private/legal/vault/log inspection.
- No credential storage or brokering.
- No provider/model calls unless explicitly scoped later.
- No remote multi-machine orchestration.
- No cloud sync.
- No mobile execution client.
- No autonomous route execution.
- No generalized workflow engine.

## What To Build First

1. Schemas

- LaunchPacket.
- EvidenceTrail.
- SourceSetManifest.
- DeploymentRegistry.
- ApprovalRecord.
- ParallelStepBundle.

2. Validators

- Required fields.
- Forbidden paths.
- Packet hash.
- Approval validity.
- Freshness.
- Risk class.

3. Markdown generators

- Ladder doc.
- Packet doc.
- Evidence doc.
- Drift report.

4. Minimal CLI

- `new-ladder`.
- `validate-packet`.
- `refresh-source-set`.
- `write-evidence`.
- `drift-report`.

5. Local UI

- Browse artifacts.
- Show status chips.
- Compare packet versions.
- Route to approved local commands only after validator passes.

## Pricing/Packaging Notes

Potential product tiers should be based on deployment complexity, not autonomy:

- Personal: single operator, local artifacts, source-set refresh, evidence browser.
- Professional: multiple deployments, client boundaries, advanced drift reports.
- Studio/Company: team review workflows, signed packets/evidence, policy packs.

Avoid pricing around "number of agents" in v1. That pushes the product narrative toward autonomy rather than operator-controlled launch quality.

## Adoption Wedge

The narrow wedge is "make ChatGPT/Codex/Gemini project context refresh and launch evidence reliable." This is valuable without requiring a full control plane:

- Source-set manifests.
- Freshness checks.
- Launch packets.
- Evidence trails.
- Drift reports.

Once that is useful, the Atlas becomes a natural index over real artifacts.

## OpenClaw Recommendations

- Ship the packet/evidence/freshness loop before the Atlas becomes elaborate.
- Productize "no hidden autonomy" as a trust feature.
- Use conservative defaults and explicit expansions.
- Treat route compression as a premium clarity feature, not a shortcut around validation.
- Keep all v1 artifacts readable without the app.

## Risks And Anti-Patterns

- Building a dashboard before packets and evidence exist.
- Selling autonomy before approval architecture is mature.
- Adding a desktop app before schemas stabilize.
- Mixing client/company systems in demos without boundary controls.
- Treating source-set refresh as a provider integration instead of a local artifact workflow.
- Letting "multi-agent" branding overpower operator authority.


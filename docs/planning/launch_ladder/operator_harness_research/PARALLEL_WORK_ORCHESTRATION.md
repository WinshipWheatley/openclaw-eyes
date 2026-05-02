# Parallel Work Orchestration

## Purpose

This document defines safe first principles for Parallel Step Bundles: one operator-approved action that can launch multiple independent work lanes only when collisions, validations, commit boundaries, and stop conditions are explicit.

## Source Basis

- Concurrency and workflow controls: [GitHub Actions concurrency](https://docs.github.com/actions/concepts/workflows-and-actions/concurrency), [GitHub Actions workflow syntax](https://docs.github.com/actions/learn-github-actions/workflow-syntax-for-github-actions), and [CloudEvents](https://cloudevents.io/).
- Control loops and state boundaries: [Kubernetes controllers](https://kubernetes.io/docs/concepts/architecture/controller/) and [OpenGitOps](https://opengitops.dev/).
- Human-supervisory automation: Parasuraman/Sheridan/Wickens automation taxonomy and [Onnasch et al.](https://journals.sagepub.com/doi/pdf/10.1177/0018720813501549).
- Operational reliability: [Google SRE postmortem culture](https://sre.google/sre-book/postmortem-culture/) and [Google SRE toil guidance](https://sre.google/sre-book/eliminating-toil/).
- Structured validation: [JSON Schema](https://json-schema.org/specification).

## Confirmed Best Practices

Concurrency needs conflict control. GitHub Actions concurrency exists because simultaneous runs can conflict, waste resources, or deploy out of order. OpenClaw bundles need explicit collision policy before parallel launch.

Parallel work needs independent ownership. Work lanes should have disjoint write sets or a declared merge owner. If two lanes can edit the same file or mutate the same subsystem, they are not independent.

Control loops need clear desired state. Kubernetes controllers work against declared state. Parallel bundles should declare the desired result and let each lane produce evidence against that result.

Automation should not move the operator out of failure recovery. Human factors research warns that higher automation can reduce situation awareness. Bundle UI must show lane state, stop reasons, and evidence without hiding the live topology.

## Parallel Step Bundle Requirements

A bundle is valid only if it includes:

- Bundle ID and packet hash.
- North Star task.
- Lane list.
- Lane ownership.
- Write sets.
- Read sets.
- Forbidden paths.
- Tool/machine/workspace per lane.
- Validation per lane.
- Bundle-level validation.
- Commit boundary per lane or explicit no-commit policy.
- Collision policy.
- Stop conditions.
- Evidence path per lane.
- Merge/integration plan.
- Operator approval binding.

## Bundle Schema Sketch

```yaml
parallel_bundle:
  bundle_id: "psb-YYYYMMDD-shortname"
  independence_claim: "Lanes touch disjoint docs only"
  approval_scope: "exact-bundle-hash"
  collision_policy:
    overlapping_write_sets: "deny"
    changed_shared_file: "stop"
    validation_failure: "stop-bundle"
  lanes:
    - lane_id: "lane-a"
      owner: "local-agent-or-operator"
      target:
        workspace: "/declared/workspace"
        tool: "codex"
      write_set:
        - "docs/planning/a.md"
      read_set:
        - "docs/planning/"
      forbidden_paths:
        - ".chief.env"
        - ".google-secrets/"
        - "LegalPrivate/"
      validation:
        - "git diff --check"
      evidence_path: "docs/evidence/lane-a.md"
      stop_conditions:
        - "unexpected credential prompt"
        - "write outside write_set"
        - "validation failure"
  integration:
    merge_owner: "operator"
    commit_boundary: "one commit after bundle validation"
    final_validation:
      - "git status -sb --untracked-files=all"
      - "git diff --check"
```

## Valid Bundle Patterns

Good candidates:

- Independent research docs in separate files.
- Independent source-set refresh manifests for separate deployments.
- Read-only audits of different modules.
- Test runs that do not mutate shared state.
- Documentation updates with disjoint write sets.

Poor candidates:

- Multiple lanes editing the same architecture file.
- Runtime/service mutation.
- Credential-bearing tasks.
- Tasks requiring private/legal/vault/log inspection.
- Work where lane B depends on lane A's result.
- Cross-client/company actions without separate approvals.

## Route Compression And Parallelism

Parallelism should not be hidden inside a compressed route. If a Direct Route includes a Parallel Step Bundle, the route summary must show:

- Number of lanes.
- Write sets.
- Integration owner.
- Bundle stop policy.
- Deferred validation.
- Evidence paths.

The operator should be able to expand the bundle before approval.

## OpenClaw Recommendations

- In v1, support bundle planning and validation before supporting bundle execution.
- Allow one-button launch only for Class 0-3 local work with disjoint write sets.
- Deny bundles that touch forbidden paths, credentials, runtime state, or external services.
- Add a preflight collision checker for write sets.
- Require per-lane evidence and a bundle evidence summary.
- Prefer a single integration point after all lanes pass validation.

## Risks And Anti-Patterns

- "Parallel" used as a synonym for "faster" without independence proof.
- Shared file edits delegated to multiple lanes.
- Bundle approval that does not include lane details.
- A lane silently continuing after another lane fails.
- Commit boundaries omitted, making review impossible.
- Evidence merged into one summary with no per-lane proof.
- Parallel launch across client systems without authority separation.


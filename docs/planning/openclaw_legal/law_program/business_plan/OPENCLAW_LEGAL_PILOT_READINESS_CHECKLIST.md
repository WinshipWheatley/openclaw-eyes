# OpenClaw Legal Pilot Readiness Checklist

## 1. Purpose

This checklist is an internal decision gate before any real law-firm outreach, synthetic/public demo, or paid pilot decision.

It is not buyer-facing copy. It is not a sales promise. It is not real deployment approval. It exists to keep OpenClaw Legal from becoming emergency discovery support, broad custom development, legal-adjacent judgment work, or a stress trap.

Use this checklist after reading the first-pilot scope and buyer brief. The checklist is stricter than both. A buyer can sound interested and still be a no-go.

## 2. Verdict model

Use only these outcomes:

- **Go to synthetic/public demo**: safe to show a narrow synthetic or public-safe demo only. No real matter. No paid pilot promise. No real deployment claim.
- **Conditional Go to paid pilot planning**: safe to schedule a planning session for written scope, payment, support, data, hardware, backup, and attorney-review terms. This is not approval to implement new features.
- **No-Go / pause**: stop the deal path until the risk changes. Do not soften the boundary by building custom features, accepting raw matter access, or offering cheap open-ended support.

Default to the stricter verdict when facts are unclear.

## 3. Required proof before demo

Before any real law-firm outreach or demo, confirm:

- [ ] Synthetic demo validation package exists.
- [ ] Current Legal Console checkpoint is known.
- [ ] Demo uses no real matter.
- [ ] Any demo Run action is limited to `Run Synthetic Dry Run` under the synthetic demo validation package, fixed synthetic values, and sanitized status-only output; Real-matter GUI Run and Reset remain disabled and not presented as available.
- [ ] Support boundary is understood before speaking with the firm.
- [ ] Buyer brief and first-pilot scope doc are current.
- [ ] No internal OpenClaw agent names in UX.
- [ ] Roadmap items are labeled as roadmap, not built capability.
- [ ] Real deployment remains No-Go until separately proven.

If any item is missing, use internal planning only or pause.

## 4. Required proof before paid pilot planning

Before paid pilot planning, confirm:

- [ ] First workflow selected.
- [ ] Accepted file types selected.
- [ ] Unsupported file policy accepted.
- [ ] Support window selected.
- [ ] Emergency/court-deadline support excluded or priced separately.
- [ ] Hardware owner or funder identified.
- [ ] Backups, retention, restore testing, and offboarding responsibility assigned.
- [ ] No-legal-advice and attorney-review language accepted.
- [ ] Payment, scope, and support terms drafted.
- [ ] No raw matter remote-support expectation.
- [ ] Synthetic demo passed first.
- [ ] Buyer understands built features versus roadmap.
- [ ] Buyer accepts that unsupported files do not create emergency support obligations.

If these are not ready, the only acceptable outcomes are Go to synthetic/public demo or No-Go / pause.

## 5. Hard No-Go conditions

Any single condition below is enough to stop or pause:

- [ ] Buyer needs emergency support.
- [ ] Buyer expects legal conclusions or privilege calls.
- [ ] Buyer requires unsupported critical file types immediately.
- [ ] Buyer refuses data, hardware, backups, retention, or offboarding responsibility.
- [ ] Buyer expects full e-discovery replacement.
- [ ] Buyer wants broad remote raw-matter access.
- [ ] Buyer needs Run/Reset GUI behavior as a condition of pilot.
- [ ] Buyer needs Connect/queue/ETA/model distribution now.
- [ ] Buyer wants unlimited support or open-ended custom work for a narrow setup fee.
- [ ] Buyer treats roadmap modules as included deliverables.
- [ ] Buyer will not accept attorney review and not legal advice boundaries.
- [ ] Buyer wants real deployment before data, support, liability, hardware, backup, and offboarding terms are written.

Do not reinterpret a hard no-go as a feature request.

## 6. Support burden check

Before proceeding, answer bluntly:

- [ ] Can this be supported without harming life/music priorities?
- [ ] Is support bounded to written hours and written scope?
- [ ] Is custom work paid separately?
- [ ] Is there a clean exit/offboarding path?
- [ ] Is the buyer calm enough to be a first pilot?
- [ ] Can ordinary support happen through sanitized diagnostics by default?
- [ ] Is there no expectation of on-call court-deadline rescue?
- [ ] Would this still feel acceptable after the first week of support friction?

If support feels open-ended, the verdict is No-Go / pause.

## 7. Technical readiness check

Before moving beyond demo planning, confirm:

- [ ] Local spine current.
- [ ] Synthetic demo passes.
- [ ] Support packet concept works.
- [ ] Alternative Methods concept works.
- [ ] Legal Console remains bounded.
- [ ] No private data in repo.
- [ ] No OpenClawLegalPrivate under /home/openclaw.
- [ ] No cloud/LLM matter path.
- [ ] Current known limitations are written.
- [ ] Real matter stays outside prompts, repo, public fixtures, support packets, and update packages.
- [ ] Unsupported, failed, and no-text files are surfaced honestly.
- [ ] `Run Synthetic Dry Run` remains limited to synthetic demo validation; Reset, Real-matter GUI Run, arbitrary bridge execution, real matter through the app, and broader Run/Reset behavior remain deferred unless separately planned and approved.

If technical proof is unclear, use synthetic/public demo only or pause.

## 8. Commercial readiness check

Before paid pilot planning, confirm:

- [ ] Setup fee structure selected.
- [ ] Support/update plan structure selected.
- [ ] Paid add-ons identified.
- [ ] No cheap open-ended support.
- [ ] First-pilot discount, if any, is tied to feedback and limited scope.
- [ ] Buyer understands roadmap versus built features.
- [ ] Hardware cost is firm-funded, covered by signed terms, or deliberately kept as internal demo/lab hardware.
- [ ] Pricing does not imply unlimited file-type support, emergency coverage, or full firm IT service.
- [ ] Custom handlers, extra training, extra nodes, connectors, and advanced modules have a paid path.

If the economics depend on vague future goodwill, pause.

## 9. Documentation readiness check

Before outreach, demo, or paid pilot planning, confirm:

- [ ] First pilot scope current.
- [ ] Buyer brief current.
- [ ] Support boundary current.
- [ ] Go/No-Go criteria current.
- [ ] Synthetic demo validation current.
- [ ] Any buyer-facing language reviewed for overpromising.
- [ ] File-type limits are written plainly.
- [ ] Emergency support exclusions are written plainly.
- [ ] No-legal-advice and attorney-review language is written plainly.
- [ ] Built, prototype-only, and roadmap items are separated.

If docs cannot state the boundary cleanly, the buyer conversation is not ready.

## 10. Decision log template

Copy this template for each candidate firm or workflow.

```text
Date:
Candidate firm:
Proposed workflow:
File types:
Support window:
Hardware plan:
Backup/offboarding plan:
Verdict:
Reasons:
Conditions before proceeding:
```

Use plain reasons. If the true reason is stress, scope, liability, money, hardware, unsupported files, or buyer temperament, say so internally.

## 11. Next-step rule

If checklist produces Conditional Go, next step is a planning session, not implementation.

If checklist produces No-Go, do not build custom features to rescue the deal.

If checklist produces Go to synthetic demo, use synthetic/public demo only.

Any next implementation slice still needs its own scoped plan, proof commands, and explicit approval, especially anything involving real matter workflows, arbitrary bridge execution, changes to `Run Synthetic Dry Run`, Reset, Real-matter GUI Run, Connect, queue/ETA, OCR/model distribution, file pickers, new file types, unsupported-file feature expansion, cloud/external model processing, or raw matter support.

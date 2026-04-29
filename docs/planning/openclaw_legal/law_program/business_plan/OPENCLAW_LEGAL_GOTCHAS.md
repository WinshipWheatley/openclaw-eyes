

# OpenClaw Legal — Gotchas and Risk Register

## Purpose

This document identifies the traps that could make OpenClaw Legal too expensive, too custom, too hard to support, legally risky, technically brittle, or commercially unclear.

The goal is not to talk the project to death. The goal is to decide whether the project is worth pursuing, where it can fail, which risks are acceptable, and what must be mitigated before money, time, credibility, or client trust are put at risk.

This should be treated as a decision filter and risk register.

Use `OPENCLAW_LEGAL_SUPPORT_BOUNDARY.md` as the operating boundary for support scope, buyer expectations, data access, hardware responsibility, rush support, and offboarding.

## Current strategic question

OpenClaw Legal is potentially valuable, but only if the first deployment is scoped tightly enough to become a reusable product foundation.

The key question is:

```text
Can this become a private local discovery product that firms will pay for, or will it become an expensive custom support burden?
```

The answer depends on:

- first-firm pain level
- first-firm budget
- strict product/core separation
- local data boundaries
- realistic v1 scope
- support expectations
- hardware strategy
- build discipline
- pricing discipline
- ability to reuse the architecture for Firm #2

## Early decision rule

This is worth pursuing if:

- the first firm has real discovery pain
- the first firm has a real budget
- the first workflow is narrow and concrete
- the buyer understands v1 limits
- legal data boundaries are enforced before real matter use
- the first deployment can become reusable product architecture
- support/update obligations are bounded
- hardware cost is paid for or contractually covered

This is not worth pursuing yet if:

- the firm expects a finished enterprise e-discovery platform immediately
- the firm expects unlimited custom work for a small setup fee
- sensitive legal data would enter the repo or non-local model context
- the first buyer will not tolerate a focused v1 scope
- hardware/software spend is fronted on vibes without agreement
- every unsupported file becomes an emergency manual support job
- updates and modules cannot be made firm-isolated

## Top-level risk summary

Highest-risk areas:

1. Hardware purchase timing
2. Build-cost runaway
3. Custom first-firm trap
4. Sensitive-data leakage
5. Unsupported-file support burden
6. Overpromising e-discovery scope
7. Weak UX / false confidence
8. Model-size fantasy
9. Connector complexity
10. Update/support obligations

The project is promising only if those risks are controlled deliberately.

---

## 1. Hardware timing gotcha

### Gotcha

Buying the most expensive Mac Studio immediately could lock the project into a major cost before the first buyer scope, payment structure, and real processing bottlenecks are proven.

### Why it matters

A 256GB M3 Ultra Mac Studio may be powerful enough for many local workflows, but if the eventual product truly benefits from 512GB unified memory and much larger models, the first machine may become awkwardly positioned.

It could become:

- the first firm’s Primary Node
- Winship’s dev/test lab machine
- a demo appliance
- a fallback Primary Node
- a worker node after a future upgrade
- a sunk-cost distraction

### Early warning signs

- hardware is purchased before signed scope/payment
- buyer has not agreed to hardware ownership
- expected model sizes keep changing
- no benchmark proves the expensive machine is needed
- build plan assumes future hardware that does not exist yet
- the product depends on a custom-order machine arriving on time

### Mitigation

- Build and test the product spine on the existing OpenClaw PC/WSL setup first.
- Use the MacBook/off-network workspace for planning, mockups, and contracts.
- Price hardware explicitly in the first deployment.
- Make the firm buy the Primary Node, or cover it through a signed setup agreement.
- If Winship buys the first Mac Studio personally, treat it as an OpenClaw Legal dev/demo/test appliance, not as a guaranteed firm asset.
- Benchmark actual Legal v0 tasks before deciding what hardware tier is required.

### Decision rule

Do not personally front a maxed-out Mac Studio unless it is acceptable to keep it as a long-term OpenClaw Legal lab/demo machine.

If the firm needs it, the firm should pay for it or sign a deployment agreement that covers it.

---

## 2. Hardware upgrade path gotcha

### Gotcha

If the firm starts on a 256GB Mac Studio and later a 512GB Mac Studio becomes available, the migration path must be clear before the first install.

### Why it matters

The old machine will still have value, but unclear ownership and migration plans can create confusion.

Questions:

- Does the firm own the old Primary Node?
- Does it become a worker node?
- Does it become backup/failover?
- Does Winship buy it back or keep it for testing?
- Who pays for the new machine?
- How is the Legal Vault migrated?
- How are model registries and node identities migrated?

### Early warning signs

- hardware ownership is vague
- migration plan is “we’ll figure it out later”
- old machine contains sensitive data without clear wipe/retention policy
- model distribution assumes one permanent Primary Node
- no backup/restore process exists

### Mitigation

- Define hardware ownership in the deployment agreement.
- Define Primary Node migration as a supported paid service or future module.
- Build backup/export/restore procedures before promising hardware upgrades.
- Treat old Primary Node as one of these explicitly:
  - firm-owned worker node
  - firm-owned backup/failover node
  - returned/sanitized dev/demo machine
  - retired and wiped

### Decision rule

Do not promise a future hardware upgrade path until vault backup/restore, model registry migration, and node identity migration are designed.

---

## 3. Model-size fantasy gotcha

### Gotcha

Large 160GB, 310GB, or 400GB local models sound impressive, but the product may not need them first.

### Why it matters

The foundation of OpenClaw Legal is not a giant model. It is:

- vault boundary
- source registration
- extraction
- search
- review packets
- audit trail
- permissions
- queue
- update lanes
- unsupported-file workflow
- controlled UX

A huge local model does not fix weak product architecture.

### Early warning signs

- architecture decisions center on model size before workflow is proven
- the pitch sounds like “big model for lawyers”
- basic search/extraction/reporting is not stable yet
- no task-specific benchmark shows giant model advantage
- smaller models or deterministic tools are ignored

### Mitigation

- Build deterministic legal spine first.
- Benchmark local models only on tasks that actually need them.
- Use model routing by task class.
- Treat giant models as premium/local-review modules, not the core product.
- Keep attorney review central.
- Make performance claims only after calibration.

### Decision rule

Do not buy or architect around giant models until the product has a proven task that benefits materially from them.

---

## 4. Build-cost runaway gotcha

### Gotcha

Spending thousands of dollars on Codex, Claude Code, API credits, and subscriptions could be rational if the work is tightly scoped, but wasteful if agents wander across too many features.

### Why it matters

A $5,000 build sprint could produce a serious v1 foundation — or a pile of half-finished modules.

### Early warning signs

- prompts ask for many features at once
- no proof commands after each slice
- no checkpoint after each commit
- no rollback points
- agents edit unrelated dirty files
- architecture contracts are skipped
- cost is not tracked per outcome

### Mitigation

- Build in small, testable slices.
- Require short plans before editing.
- Require exact files changed.
- Require tests/proof commands.
- Commit each clean slice.
- Avoid sprawling “build the whole suite” prompts.
- Use expensive models only for architecture-critical work.
- Use cheaper/local tools for routine implementation where possible.

### Decision rule

Do not start a high-cost build sprint until the first 3–5 implementation slices are defined with proof commands and stop points.

---

## 5. Custom first-firm trap

### Gotcha

The first firm’s needs could become hardcoded product behavior.

### Why it matters

If Firm #1 becomes a custom branch, Firm #2 becomes a rebuild. That kills scale.

### Early warning signs

- firm name appears in core code
- matter-specific assumptions enter product docs/tests
- firm workflow is coded directly instead of configured
- modules are not separated
- Firm #2 feature work would require touching Firm #1 behavior

### Mitigation

- Enforce Product Core / Firm Profile / Matter Vault separation.
- Put firm-specific behavior in profile/config.
- Put reusable capabilities in modules.
- Use synthetic/public fixtures in the repo.
- Build per-firm immutability tests.

### Decision rule

Any feature that cannot be classified as Core, Firm Profile, Matter Vault, Suite Module, or Support Packet should stop until classified.

---

## 6. Sensitive-data leakage gotcha

### Gotcha

If real matter data enters the repo, support packets, non-local model prompts, cloud APIs, or reusable docs, the product’s core promise collapses.

### Why it matters

Legal buyers are trusting the system with privileged and confidential data.

### Early warning signs

- real PDFs or extracted text used as fixtures
- support packet includes filenames/client names/matter facts
- non-local LLM reads vault paths
- prompts include case details
- update package includes matter logs
- developer tools search everything indiscriminately

### Mitigation

- Legal Vault outside repo.
- Vault path guard.
- Support packet sanitizer.
- Non-local LLM block for vault paths.
- Synthetic/public test fixtures only.
- Redacted diagnostics only.
- Fail-closed when uncertain.

### Decision rule

If a workflow cannot prove it excludes matter data from repo/support/cloud/non-local contexts, block it.

---

## 7. Support burden gotcha

### Gotcha

If the product requires constant manual patching, remote access, or emergency handler fixes, it is not yet a scalable product.

### Why it matters

A product that creates open-ended support expectations can consume all available time and kill profitability.

### Early warning signs

- every unsupported file becomes a direct call to Winship
- no support packet format
- no update lanes
- no clear included vs paid support boundary
- firm expects unlimited custom development
- no diagnostics or reproducible public analog fixtures

### Mitigation

- Define support tiers.
- Build Alternative Methods workflow.
- Gate Request Feature until local attempts fail.
- Generate sanitized support packets.
- Use public analog fixtures.
- Charge for custom modules/handlers where appropriate.
- Avoid remote access to sensitive matter data.

### Decision rule

Do not sell open-ended support. Every support category must be included, paid, or out of scope.

---

## 8. Unsupported-file gotcha

### Gotcha

Real discovery will include weird files. If unsupported files are hidden or vague, the firm loses trust. If every unsupported file becomes emergency custom work, Winship loses bandwidth.

### Why it matters

Unsupported files are inevitable.

### Early warning signs

- unsupported files just say “failed”
- no technical diagnostics
- no local-first attempt
- no public analog fixture search
- no Request Feature gate
- no pricing/support boundary for new handlers

### Mitigation

- Alternative Methods menu.
- Local classification first.
- Installed handler attempts.
- Local sandbox build attempt if allowed.
- Request Feature after local failure/policy block.
- Sanitized feature request packet.
- Public analog/stress-test files.

### Decision rule

Unsupported-file handling must be a product workflow before the first serious deployment.

---

## 9. Overpromising e-discovery scope gotcha

### Gotcha

Pitching OpenClaw Legal as a complete Relativity replacement too early creates impossible expectations.

### Why it matters

The first product should sell the local discovery foundation, not pretend to be a mature enterprise e-discovery platform.

### Early warning signs

- pitch says “full e-discovery replacement”
- buyer expects every file type
- buyer expects privilege decisions
- buyer expects full portal integration immediately
- buyer expects no human review

### Mitigation

- Pitch private local discovery infrastructure.
- Define v1 supported scope.
- Label roadmap modules clearly.
- Keep attorney review central.
- Use “expandable module roadmap,” not “does everything.”

### Decision rule

If the buyer needs a mature enterprise e-discovery suite on day one, OpenClaw Legal v1 may not be the right fit yet.

---

## 10. UX false-confidence gotcha

### Gotcha

If the UX says everything is fine when work is partial, blocked, unsupported, or low-confidence, lawyers will lose trust when reality appears.

### Why it matters

A legal product must be honest.

### Early warning signs

- too many green checks
- unsupported files buried
- ETA shown without confidence
- “done” used when attorney review is pending
- AI outputs look final
- blocked states are unclear

### Mitigation

- Persistent confidence/status bar.
- Clear states: partial, blocked, unsupported, needs review, calibrating.
- ETA confidence labels.
- Source-grounded snippets.
- Draft/candidate labels for AI-assisted outputs.
- No sycophantic status language.

### Decision rule

If the UX cannot state uncertainty clearly, the feature is not ready for legal use.

---

## 11. Connector complexity gotcha

### Gotcha

“Set it up with their ingest, email things, yada yada” can explode into a major integration project.

### Why it matters

Portals, email systems, cloud drives, and practice management systems each have auth, permissions, API limits, export quirks, and privacy risks.

### Early warning signs

- connectors are included in v1 without scoping
- no credential boundary
- worker nodes receive connector credentials
- portal scraping is assumed easy
- email ingestion includes privileged content without policy
- external systems become canonical

### Mitigation

- Start with local/staging-folder intake.
- Treat connectors as optional modules.
- Store credentials only on Primary Node or approved secure store.
- Pull into vault before processing.
- Keep external systems non-canonical after ingestion.
- Build one connector at a time.

### Decision rule

Do not promise a connector until the exact source system, auth path, data boundary, and support obligations are scoped.

---

## 12. Update chaos gotcha

### Gotcha

If updates change workflow unexpectedly, firms will fear updating or blame the system for broken procedures.

### Why it matters

Trust depends on working deployments staying stable.

### Early warning signs

- new menu items appear without install
- Firm #2 features show up in Firm #1
- security updates include feature changes
- rollback is unavailable
- update notes are vague
- matter data migration is unclear

### Mitigation

- Update lanes.
- Module version pinning.
- No-surprise update contract.
- Firm profile isolation.
- Update manifests with risk/tests/rollback.
- Explicit install for optional modules.

### Decision rule

No workflow-changing update should install without explicit approval.

---

## 13. Ownership gotcha

### Gotcha

Hardware, software license, models, updates, generated artifacts, and support rights can become ambiguous.

### Why it matters

Ambiguity creates disputes and support confusion.

### Early warning signs

- firm does not know whether they own the Mac Studio
- unclear whether license is transferable
- local models have unclear redistribution rights
- generated outputs ownership is not stated
- support/update rights are vague

### Mitigation

- Define hardware ownership.
- Define software license terms.
- Define update/support terms.
- Define model license/redistribution rules.
- Define data/artifact ownership: firm owns matter data and generated matter artifacts.
- Define what Winship may keep: sanitized diagnostics, generic code, public fixtures, reusable modules.

### Decision rule

Do not deploy before ownership/support boundaries are written down.

---

## 14. Model licensing gotcha

### Gotcha

Not every local model is safe to use, redistribute, or bundle in a commercial legal deployment.

### Why it matters

A model may have license limits, redistribution restrictions, commercial-use restrictions, or unclear terms.

### Early warning signs

- model is downloaded casually
- workers receive model copies without license review
- model provider terms are unknown
- commercial redistribution is assumed
- support packet includes model artifacts

### Mitigation

- Review model licenses before deployment.
- Track model source, version, license, checksum.
- Avoid redistributing models unless permitted.
- Prefer firm-local downloads or approved distribution where legally allowed.
- Keep model registry metadata.

### Decision rule

No model should ship/distribute to a firm deployment unless commercial use and distribution method are allowed.

---

## 15. Security/compliance gotcha

### Gotcha

Local does not automatically mean secure or compliant.

### Why it matters

Firms care about confidentiality, privilege, access control, audit, retention, and data handling.

### Early warning signs

- “it runs locally” treated as complete security
- no user/device permissions
- no export approval
- no audit trail
- no vault path guard
- no retention/delete policy
- worker nodes cache data without rules

### Mitigation

- Vault path contract.
- Matter assignment/device permission model.
- Export boundaries.
- Audit every significant action.
- Worker data retention policy.
- Update/support sanitization.
- Clear backup/restore plan.

### Decision rule

Do not pitch privacy/security as a core value until the core boundaries are demonstrably enforced.

---

## 16. Testing-data gotcha

### Gotcha

Without realistic synthetic/public test data, bugs cannot be safely reproduced and handlers cannot be improved without touching real legal data.

### Why it matters

A reusable legal product needs test data that mimics discovery without containing confidential information.

### Early warning signs

- real firm files used in tests
- no public analog files
- no synthetic matter fixture
- unsupported-file bugs require the real file
- support packets lack enough diagnostics

### Mitigation

- Build synthetic demo matters.
- Use public analog files by technical characteristics.
- Maintain stress-test fixture sets.
- Generate sanitized support packets.
- Keep regression tests tied to public/synthetic fixtures.

### Decision rule

No handler should require real matter data to reproduce a bug if a sanitized/public analog can be created.

---

## 17. Pricing gotcha

### Gotcha

Underpricing creates unlimited obligations. Overpricing before proof may kill the deal.

### Why it matters

The first deployment must fund real work without promising enterprise maturity.

### Early warning signs

- open-ended support included
- custom work bundled for free
- hardware cost not accounted for
- support/update expectations are vague
- buyer expects all roadmap modules included
- pricing does not distinguish base vs custom modules

### Mitigation

- Define package tiers.
- Separate setup, support, modules, and custom work.
- Treat hardware explicitly.
- Define included support window.
- Charge for new modules/handlers where appropriate.
- Keep v1 scope narrow.

### Decision rule

Do not quote until scope, hardware, support, and must-have modules are understood.

---

## 18. Expansion-path gotcha

### Gotcha

If everything is built into one giant app with no module boundaries, future expansion becomes risky.

### Why it matters

OpenClaw Legal needs to become a suite/module architecture if Firm #2 needs different capabilities.

### Early warning signs

- feature flags are informal
- modules cannot be installed separately
- update manager does not know module boundaries
- firm profiles cannot pin module versions
- tests require all features installed

### Mitigation

- Core + modules + firm profiles from the start.
- Version each module.
- Make optional modules invisible unless installed.
- Keep module contracts separate.
- Add tests for module isolation.

### Decision rule

No new major capability should be built without deciding whether it is Core or Module.

---

## 19. First buyer credibility gotcha

### Gotcha

A flaky first deployment can damage the relationship and kill future sales momentum.

### Why it matters

The first firm is not just a buyer. It is the proof that this can become a product.

### Early warning signs

- demo is mostly promises
- real workflow not tested
- unsupported files dominate
- UX is confusing
- support boundaries are unclear
- privacy claims are not proven

### Mitigation

- Pilot a narrow workflow.
- Use a representative discovery batch.
- Be honest about roadmap.
- Show what works and what fails.
- Keep v1 small and reliable.
- Have rollback/checkpoint plans.

### Decision rule

Do not deploy broadly until a narrow real workflow works reliably end-to-end.

---

## 20. “Worth my time?” gotcha

### Gotcha

This project may be exciting but not worth the time if the first buyer cannot pay, scope, tolerate v1 limitations, or validate repeatable product value.

### Why it matters

The opportunity cost is high. This could consume months of engineering and support time.

### Early warning signs

- buyer likes the idea but has no budget
- buyer wants everything before paying
- buyer cannot define first workflow
- buyer expects legal advice automation
- buyer refuses local hardware cost
- buyer will not accept phased roadmap
- no path to Firm #2 exists

### Mitigation

- Ask hard discovery questions early.
- Define paid pilot scope.
- Keep first workflow narrow.
- Get hardware/payment agreement before major purchases.
- Build reusable architecture, not custom services.
- Treat unsupported/custom work as paid module work.

### Decision rule

Proceed only if there is a real paid pilot path, a narrow first workflow, and a credible route to reusable product architecture.

---

## Immediate pre-build checklist

Before major spending or build sprint:

- [ ] Identify first firm’s exact discovery workflow.
- [ ] Identify file types in their real workflow.
- [ ] Confirm budget range.
- [ ] Confirm hardware ownership/payment path.
- [ ] Define v1 scope.
- [ ] Define what is roadmap only.
- [ ] Define support boundaries.
- [ ] Confirm local-only expectation.
- [ ] Confirm whether any connectors are required for v1.
- [ ] Confirm no real legal data enters repo/non-local prompts.
- [ ] Define first three implementation slices.
- [ ] Define proof commands/checkpoints.
- [ ] Decide whether Mac Studio purchase is firm-funded, contract-covered, or Winship-owned lab hardware.

## Current Mac Studio decision note

Current best judgment:

```text
Do not buy the most expensive machine until first buyer scope and payment structure are clearer.
```

Better immediate strategy:

- build product spine on existing PC/WSL OpenClaw setup
- use MacBook for planning/mockups/docs
- price first deployment so hardware is firm-paid or covered by signed setup agreement
- if Winship buys a Mac Studio first, treat it as OpenClaw Legal dev/demo/test lab hardware
- do not make the project depend on a future 512GB machine before the v1 workflow is proven

If a 256GB Mac Studio is later replaced by a 512GB unit, decide explicitly whether the 256GB machine becomes:

- firm-owned worker node
- firm-owned backup/failover node
- Winship dev/test/model benchmark machine after sanitization
- demo appliance
- retired/wiped hardware

## Bottom line

OpenClaw Legal is worth exploring if it stays disciplined:

```text
narrow first workflow
local-first data boundary
strict product/core separation
firm-paid or contract-covered hardware
bounded support
visible UX truth
module-based expansion
small tested build slices
```

It becomes dangerous if it turns into:

```text
huge hardware bet
unbounded custom firm project
AI hype pitch
unsupported-file emergency machine
cloud/privacy contradiction
or a giant app with no module boundaries
```

The gotchas are manageable if they are treated as product requirements, not afterthoughts.
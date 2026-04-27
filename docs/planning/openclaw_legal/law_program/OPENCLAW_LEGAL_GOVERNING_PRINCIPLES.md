# OpenClaw Legal — Governing Principles

## Purpose

This is the anti-drift constitution for OpenClaw Legal.

It exists to stop the project from becoming slop, liability, custom-service chaos, or life-ruining support work.

Future agents should treat this file as governing planning law for the OpenClaw Legal package. It does not prove implementation status. It defines how future work must behave.

## Governance-change warning

Changes to this file should be deliberate and treated as governance changes, not routine prose cleanup.

## 1. Handoffs expire

Handoff files are current-state artifacts.

They tell the next chat where the project is right now. They are not permanent doctrine.

When a handoff becomes stale, archive it, replace it, or clearly mark it obsolete. Do not let old handoffs compete with current truth.

## 2. PC/WSL is implementation authority

The canonical implementation authority is the PC/WSL repo at:

```text
/home/openclaw
```

This Mac workspace is planning and reflection.

Mac docs may inform future work. They must not be treated as proof that code exists, tests pass, or implementation choices have already been made.

## 3. Go/no-go beats optimism

`business_plan/OPENCLAW_LEGAL_GO_NO_GO_LAUNCH_CRITERIA.md` sits above business optimism.

If the go/no-go gate says stop, the pitch, buyer enthusiasm, model excitement, hardware dreams, and revenue ideas do not overrule it.

No-go beats momentum.

## 4. No real legal data leakage

Real legal data must not enter:

- the product repo
- prompts
- support packets
- update packages
- public fixtures
- non-local LLM contexts
- casual debug logs
- planning documents

If sensitive matter data is needed to diagnose something, the workflow is wrong until a safe, scoped, approved, and sanitized path exists.

## 5. Firm isolation is mandatory

Firm #2 must never affect Firm #1 by default.

No surprise menu changes.

No surprise workflow changes.

No silent module changes.

No shared firm state.

No cross-firm data reuse.

Every firm must be isolated by profile, matter vault, permissions, enabled modules, update lane, and support boundary.

## 6. Product boundaries must stay separated

These are separate things and must remain separate:

- OpenClaw Legal Core
- Firm Profile
- Matter Vault
- optional modules
- support packets
- update packages
- demo fixtures
- buyer-facing materials

Do not blur them for convenience.

Matter data is not product code. Firm config is not core architecture. Support packets are not a back door into private files.

## 7. Build slices must be small and proven

Every future implementation slice must be:

- small
- tested
- reversible
- proof-backed
- tied to existing repo inspection
- narrow enough to understand

No sprawling multi-feature build pass.

No "while we are here" expansion.

No broad refactor without a direct safety or product-boundary reason.

## 8. Planning docs do not trigger implementation

Do not implement broadly from these Mac planning docs.

Before implementation, Codex must inspect the canonical `/home/openclaw` repo, read the existing Legal v0 code/tests/checkpoints, and map what already exists against these contracts.

The first output after returning to PC/WSL should be a build plan, not a code spree.

## 9. No legal advice or attorney replacement

OpenClaw Legal must not present itself as:

- a lawyer
- legal advice
- attorney replacement
- final privilege authority
- final fact finder
- final legal conclusion engine
- guaranteed discovery completeness engine

The system may organize, process, surface, label, queue, search, summarize, and support review workflows.

Final legal judgment belongs to attorneys.

## 10. Unsupported files are local-first

Unsupported files do not automatically mean external escalation.

The system should try local-first handling before escalation:

- identify the file
- classify the failure
- check installed local handlers
- attempt safe local extraction/repair when allowed
- mark unsupported clearly
- produce sanitized support/request artifacts only when needed

Escalation must be bounded, sanitized, and explicit.

## 11. Updates must be lane-based and non-surprising

Updates must be organized by lane:

- security
- stability
- installed module
- optional new module
- firm-requested custom work

Updates must disclose impact before activation.

No silent workflow changes.

No surprise feature injection.

No Firm #2 update path modifying Firm #1 by default.

## 12. The business must stay bounded

OpenClaw Legal is viable only if the business stays:

- bounded
- remote-manageable
- support-limited
- contractually scoped
- paid enough to justify burden
- reusable beyond one firm
- protected from emergency litigation support expectations

If it becomes a custom legal-ops support job, it is failing.

## 13. Personal burden is a launch blocker

If personal stress, liability exposure, support burden, or emergency responsibility rises too high, no-go wins.

Do not rationalize a bad support model because the product is interesting.

Do not accept life-ruining support obligations for a vague future payoff.

Do not let sunk cost override the gate.

## 14. Bigger models are not the foundation

Bigger models and bigger hardware are not the foundation of OpenClaw Legal.

The foundation is:

- clear matter boundaries
- local-first workflow
- reliable audit/status output
- firm isolation
- safe support packets
- controlled updates
- narrow tested slices
- truthful buyer promises

Model size is secondary.

Hardware ambition is secondary.

Boundaries and workflow proof come first.

## 15. Dual-Lane Development Model

OpenClaw Legal operates in two distinct lanes to balance R&D speed with strict data safety:

- **Lane A: Synthetic Product R&D Lane**
  - Uses synthetic, public-safe, or fake data only.
  - External LLMs and tools (ChatGPT, Gemini, Claude, etc.) may be used for fixture generation, prototype validation, drafting expected outputs, benchmark comparison, and module R&D.
  - This is where future capabilities (screenshots, PDFs, audio/video, timelines) are explored.
  - **Rule:** No real matter data, client names, firm confidential information, personal case data, or sensitive personal data may ever enter this lane.

- **Lane B: Real Matter Local-Only Lane**
  - Uses real personal matter data or firm evidence.
  - External LLMs/tools are prohibited by default.
  - Only local deterministic tools are allowed until local models are explicitly approved.
  - **Rule:** Real matter outputs are attorney-review aids only, never legal advice or conclusions.

**Shared Core, Separate Data:** Both lanes use the same reusable OpenClaw Legal product core (source registration, hashing, vault boundaries, search, reports, etc.). Data rules must never mix. Fake data is where we experiment; real data is where we prove trust.

## 16. IP / Pilot / Ownership Doctrine

OpenClaw Legal operates under a clear ownership boundary to protect both the firm's data and the developer's product:

- **Developer-owned product:** OpenClaw Legal code, architecture, reusable modules, generalized workflows, docs, prompts, test fixtures, update mechanisms, and non-confidential improvements remain developer-owned unless a separate written agreement says otherwise.
- **Firm-owned matter data:** The firm owns its source files, matter data, confidential information, firm-specific configuration, generated matter outputs, review packets, reports, and work product created from its matter data.
- **License/deployment, not transfer:** A firm pays for a scoped pilot, deployment, support, or license. It does not receive ownership of the reusable OpenClaw Legal product core.
- **Reusable improvements:** Generalized fixes, reusable modules, and product features developed during a pilot may be reused in future OpenClaw Legal deployments, provided no firm confidential information or matter content is included.
- **Custom work boundaries:** Firm-specific customizations stay in the firm profile, configuration, or matter vault where possible. Exclusive custom development must be separately priced and explicitly agreed in writing.
- **Hardware ownership:** Firm matter data should run on firm-owned production hardware. Developer hardware, accounts, tools, subscriptions, and internal build systems remain developer-owned.
- **Matched Reference Bench:** For higher-tier deployments, a developer-owned reference bench may be used to match the firm’s hardware tier for issue reproduction and update validation. This bench uses only synthetic data or sanitized diagnostics; real firm data is prohibited unless explicitly agreed in writing.
- **Validated Update Pipeline:** We do not experiment on the firm’s live system. The reference bench should be used to test new models, modules, and fixes before they are offered to the firm. Firm production systems should receive only packaged, tested updates with clear release notes, risk labels, and explicit approval for workflow-changing updates. New tools must not be silently deployed to firm production.

## 17. Attorney-Gated QA / Review-and-Rework Doctrine

OpenClaw Legal is designed for high-stakes accuracy, not just creative generation. The system operates on a controlled "first pass, verification, and attorney-authorized rework" cycle:

- **Separation of Pass and Proof:** The system creates a first-pass output (e.g., timeline, summary). A separate evidence-verification checker then performs a second pass to decompose the output into claims and verify them against source records.
- **Evidence-Verification Pass, Not Opinion Pass:** The checker asks specific, factual questions: Can the claim be proven from source? Is the source ID/page/frame correct? Is the quote accurate? Did the system skip relevant evidence or overstate confidence?
- **Flag-Based Trust Calibration:**
  - **Green flag:** High-confidence, source-supported insight. Green does not mean legally true; it means the system found supporting evidence.
  - **Yellow flag:** Caution, ambiguity, or lower confidence. Requires attorney expertise or deeper review.
  - **Red flag:** Possible system error, unsupported claim, bad extraction, or citation failure.
- **Attorney-Controlled Rework Loop:** The lawyer reviews flags and decides on an action: approve rework, reject flag, defer, mark for manual review, or mark attorney-reviewed.
- **No Silent Fixes:** The system reworks only lawyer-approved items. It must never silently change legal outputs without an attorney-authorized review step.
- **No Legal Conclusions Without Review:** The system may surface candidates and evidence, but final legal judgment and conclusions remain strictly under attorney control.
- **Verification Strategy:** Future checker validation should utilize **Known-Answer Fixtures / Validation Sentinels** to ensure the verification pass itself is reliable.
- **Lane Compliance:** In Lane B (Real Matter), the checker must be local-only by default. External checker prototypes may only be used in Lane A with synthetic data.

## 18. Known-Answer Fixtures / Validation Sentinels Doctrine

Known-answer fixtures are the primary mechanism for calibrating and proving the system’s reliability before it is trusted with real matter data. This doctrine establishes the use of seeded, synthetic, and public-safe evidence packs for truth-testing:

- **Seeded Validation:** Known-answer fixtures are deliberately seeded with known expected answers, known contradictions, known OCR challenges, timestamp mismatches, source-citation errors, or review packet issues. 
- **Proof Before Trust:** Known-answer fixtures are how the system proves it can catch known problems before it is allowed near real matter data.
- **Strict Lane Isolation:** Known-answer fixtures are **Lane A (Synthetic R&D)** only. They may be generated or evaluated using external LLMs/tools only in Lane A.
- **No Matter Contamination:** Do not mix fake validation traps into real matter data. Do not place fake evidence into a real matter vault. Real matter data or firm matter data must never be used as known-answer fixtures.
- **Functional Scope:** Fixtures are used to benchmark and validate OCR accuracy, checker/flag reliability, timeline/contradiction detection, support packet sanitization, and regression testing after updates.
- **System Integration:** Known-answer fixtures support the **Attorney-Gated QA** doctrine, the **Validated Update Pipeline**, and the **Developer Reference Bench**. Hardware capability claims must be benchmarked against these fixtures where relevant.
- **Calibration, Not Substitution:** These fixtures calibrate the system’s "trust meters" and the attorney's trust in the checker. They do not replace the need for final attorney review of real matter outputs.

## 19. Hardware Ladder / Capability Tiers Doctrine

OpenClaw Legal operates on the principle that the firm is buying private local discovery infrastructure, not a chatbot. Hardware is a local discovery asset that keeps matter data local and determines which workflows are practical.

- **Modest Hardware Proves Workflow:** Modest hardware establishes the private local discovery spine (vault, source registration, hashing, text extraction, search, reports, review packets, Alternative Methods).
- **Stronger Hardware Expands Capability:** Stronger hardware makes heavier local discovery intelligence practical (faster OCR, audio/video extraction, timeline candidates, larger local models). It determines speed and capacity. Stronger hardware does not remove the need for attorney review.
- **Hardware Tiers:**
  - *Foundation tier:* Proves local spine; limited OCR/media workflows.
  - *Professional tier:* Faster batching; practical OCR; comfortable small/medium local models.
  - *Media Intelligence tier:* Stronger OCR throughput; audio/video extraction; richer timeline/contradiction workflows.
  - *Private AI Appliance tier:* Larger local models; heavy media workloads; strict benchmark validation required.
- **Sober Capability Claims:** Use sober language (candidate hardware paths, validated baseline, production tier). No hype language ("singularity", "best lawyer ever"). Do not claim exact machines support future workloads unless benchmarked. All capability claims require benchmark validation.
- **Reference Bench vs. Production:**
  - *Firm Production Hardware:* Firm matter data runs on firm-owned production hardware meeting the validated baseline for the desired tier.
  - *Matched Reference Bench:* A developer-owned matched reference bench acts as support infrastructure for higher-tier deployments. It is used to reproduce issues, benchmark modules, and validate updates safely.
  - *No Real Data on Bench:* No real firm data is allowed on the developer reference bench by default. Use synthetic/sanitized diagnostics.
- **Validated Update Pipeline:** We do not experiment on the firm's live system. Updates must be tested on the reference bench first, and only packaged, tested updates are offered to firm production.
- **Budget Framing:** Pricing should be scoped as pilot/buildout pricing. Development/tooling budgets can include developer-owned reference hardware/environment, but the firm is not "buying the developer a laptop." Production hardware remains firm-owned and separate.

## 20. Personal Matter Local-Only Usage Doctrine

The user's real personal legal matter is strictly **Lane B**.

Personal case data must stay local-only. The development/tooling budget is for engineering and synthetic R&D, not for processing real matter data through external AI. Fake data is where we experiment. Real data is where we prove trust.

No external LLMs or external tools may process the user’s personal matter contents. This explicitly prohibits:
- ChatGPT
- Gemini
- Claude
- Codex
- Anthropic, OpenAI, or Google processing
- Any non-local tool reading raw case files, texts, notes, screenshots, transcripts, exports, or extracted text

**Currently Safe Local Capabilities:**
The current system may be used locally on personal matter data only for capabilities that already exist and are safe:
- source registration and hashing
- TXT, MD, and text-layer PDF extraction
- local search
- Markdown reports
- review packets
- sanitized support packets
- Alternative Methods
- local capability policy states

**Currently Unsupported Capabilities:**
The system does not yet fully support (and personal matter data must not be used to experiment with):
- screenshots or scanned PDFs without OCR
- audio/video transcription
- video frame OCR
- source-linked timeline candidates
- contradiction candidates
- broad local LM synthesis

**Outputs:**
Outputs from the user’s personal matter must be source-linked, attorney-review framed, and local-only. They are not legal advice and not legal conclusions.

The user may generate local-only outputs from their personal matter to help their lawyers save time and to demonstrate that the system is trusted enough for sensitive local work.

**Strict Prohibitions:**
Personal matter content must not leak into Lane A. Do not use personal matter content in:
- synthetic fixtures
- public demos
- external LLM prompts
- benchmark packs
- product docs
- non-local debugging

Personal matter outputs can demonstrate trust/value only through local artifacts or sanitized descriptions.

## Final rule

When in doubt, choose the path that keeps OpenClaw Legal:

```text
bounded
local-first
firm-isolated
attorney-reviewed
support-limited
test-proven
reversible
and honest about what exists
```

Anything else is drift.

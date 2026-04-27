# OpenClaw Legal — Chat Handoff

## Purpose

This handoff is for a new ChatGPT or Codex session.

The new chat should use this file to orient, then verify current facts before acting.

## Authority warning

`OPENCLAW_LEGAL_GOVERNING_PRINCIPLES.md` governs this package.

If this handoff conflicts with governing principles, governing principles win unless intentionally updated.

This handoff is current-state guidance, not permanent doctrine.

PC/WSL Legal v0 was audited in `/home/openclaw` before the first safety slice was implemented.

The new chat should use the handoff to orient, not as implementation proof.


This file summarizes:

- what was already built in the canonical PC/WSL OpenClaw repo
- what was planned in the Mac `OpenClaw_Watch` workspace
- the critical product/safety/business doctrine
- the recommended next step

## Freshness rule

This handoff is session-current, not permanent doctrine.

This file should be the live handoff that new ChatGPT/Codex sessions check first, but it must be replaced when material facts change.

Replace and archive this handoff when any of these happen:

- PC/WSL Codex produces a materially newer implementation map
- Legal v0 changes materially
- the next 3–5 build slices are chosen
- a first firm/pilot scope becomes concrete
- the business/go-no-go decision changes
- the Mac planning docs get reorganized

When stale, move the old file to:

```text
law_program/archive/
```

Use a dated name such as:

```text
OPENCLAW_LEGAL_CHAT_HANDOFF_2026-04-25_mac-planning.md
```

Then replace `law_program/OPENCLAW_LEGAL_CHAT_HANDOFF.md` with a fresh current handoff.

Any new chat, Codex session, or implementation agent should treat this freshness rule as a first-order instruction. If the handoff appears stale, stop and ask for or create a replacement before relying on it.

## Canonical implementation authority

The canonical implementation repo is:

```text
/home/openclaw
```

That repo lives on the PC/WSL OpenClaw system and remains the implementation authority.

The Mac workspace is:

```text
/Users/hwinshipwheatley/OpenClaw_Watch
```

The Mac workspace is a planning/reflection surface. It is not canonical implementation truth.

Do not implement blindly from the Mac planning docs. First verify the current PC/WSL repo state.

## Known Legal v0 work already built on PC/WSL

The Legal v0 foundation was built in `/home/openclaw` before this Mac planning session, then audited in the canonical PC/WSL repo.

Before the first safety slice, the focused Legal v0 suite was verified at:

```text
80 passed
```

Verified Legal v0 pieces include:

- `legal/matter_workspace.py`
  - matter workspace creation
  - manifest
  - audit log
  - source copy/registration
  - SHA-256 source tracking

- `legal/local_ingestion.py`
  - local extraction for `.txt`
  - local extraction for `.md`
  - text-layer `.pdf` extraction through local `pdftotext` path
  - unsupported / no-text / failed extraction statuses

- `legal/local_search.py`
  - literal case-insensitive search over extracted text

- `legal/search_report.py`
  - Markdown search report export

- `legal/review_packet.py`
  - folder-based review packet export
  - manifest/audit/extracted/report packet structure

- `legal/deployment_profile.py`
  - local-first deployment profile helper
  - default profile
  - legal-facing `role_labels` in new default profiles
  - validation
  - save/load stable JSON

- `legal/cli.py`
  - CLI wrapper over the legal APIs
  - known commands:
    - `create-matter`
    - `add-source`
    - `extract`
    - `extract-all`
    - `search`
    - `report`
    - `review-packet`
    - `support-packet`
    - `default-profile`

- `scripts/demo_legal_matter_workflow.py`
  - deterministic demo workflow

- `scripts/demo_legal_mock_discovery.py`
  - synthetic mock discovery CLI run-through
  - strict `--vault-root` demo outside `/home/openclaw`

- Legal docs/checkpoints
  - `legal/README.md`
  - `legal/CLI_DEMO_WALKTHROUGH.md`
  - `legal/CHECKPOINT.md`

- Legal tests
  - focused Legal v0 suite passed before the safety slice: `80 passed`

## Completed first safety slice

The first Legal safety slice is implemented in `/home/openclaw`.

Commit:

```text
f086b3c feat(legal): enforce matter vault path boundaries
```

New file:

- `legal/path_guard.py`

Updated implementation files:

- `legal/matter_workspace.py`
- `legal/local_ingestion.py`
- `legal/local_search.py`
- `legal/search_report.py`
- `legal/review_packet.py`

Implemented behavior:

- matter roots are canonicalized/resolved before use
- matter workspaces resolving under `/home/openclaw` are rejected
- symlink/traversal into the product repo is rejected
- manifest `stored_path` values are validated before extraction/search/report/review-packet trust them
- tampered `stored_path` values outside the matter root fail closed

Proof:

- `py_compile` passed for changed legal modules
- focused new/updated path-guard tests: `7 passed`
- full focused Legal suite after the slice: `87 passed in 1.37s`

Remaining risks:

- review packets remain content-bearing and are not sanitized support packets
- firm/update/profile policy boundaries remain future slices

## Completed second safety slice

The second Legal safety slice is implemented in `/home/openclaw`.

Commit:

```text
9474b7c feat(legal): add optional vault root allowlist
```

The slice added optional strict Legal Vault allowlist behavior.

Strict mode is opt-in through:

- `allowed_vault_roots` in Legal APIs
- `--vault-root` in CLI matter-root workflows
- optional `storage.vault_roots` validation in deployment profiles

Calls without a vault root preserve the existing repo-boundary guard behavior from the first safety slice.

Updated implementation files:

- `legal/path_guard.py`
- `legal/matter_workspace.py`
- `legal/local_ingestion.py`
- `legal/local_search.py`
- `legal/search_report.py`
- `legal/review_packet.py`
- `legal/cli.py`
- `legal/deployment_profile.py`

Updated tests:

- `tests/test_matter_workspace.py`
- `tests/test_legal_cli.py`
- `tests/test_deployment_profile.py`

Implemented behavior:

- configured vault roots are canonicalized/resolved
- vault roots under `/home/openclaw` are rejected
- matter roots outside configured vault roots are rejected when strict mode is provided
- symlinked/traversal vault roots into the product repo are rejected
- temp/synthetic workflows remain allowed when strict vault mode is not provided

Proof:

- `py_compile` passed for changed legal modules
- focused vault/profile/CLI tests: `43 passed`
- vault/approved focused test subset: `11 passed, 32 deselected`
- full focused Legal suite after the slice: `98 passed in 0.89s`

Remaining risks:

- strict vault roots are still opt-in, not mandatory for all real deployments
- profile support validates `storage.vault_roots` when present but does not yet make profiles the source of truth for CLI workflows
- review packets remain content-bearing and are not sanitized support packets
- firm/update/profile policy boundaries remain future slices

## Completed handoff refresh after vault allowlist

Commit:

```text
132830a docs(legal): update handoff after vault allowlist
```

## Completed third safety slice

The sanitized support packet v0 slice is implemented in `/home/openclaw`.

Commit:

```text
202d7f0 feat(legal): add sanitized support packet
```

New file:

- `legal/support_packet.py`

Updated files:

- `legal/cli.py`
- `tests/test_support_packet.py`
- `tests/test_legal_cli.py`
- `.gitignore` narrow allowlist for `legal/support_packet.py` and `tests/test_support_packet.py`

CLI command added:

```text
support-packet --root ... [--vault-root ...] [--packet-name ...]
```

Implemented behavior:

- `export_support_packet()` creates a separate sanitized support artifact path
- support packets are distinct from review packets
- packets write under `support/support-packet-*/support_packet.json` inside the matter root
- packets include counts, file extensions, size ranges, source status diagnostics, module info, and explicit exclusion proof
- packets exclude source files, extracted text, review packet contents, attorney notes, matter/client names, sensitive filenames, private absolute paths, and raw audit logs

Proof:

- `py_compile` passed for `legal/support_packet.py` and `legal/cli.py`
- support-packet focused tests: `6 passed, 12 deselected`
- full focused Legal suite after the slice: `104 passed in 1.07s`

Remaining risks:

- support packet v0 is minimal
- it does not yet include unsupported-file Alternative Methods
- it does not include public analog fixture search
- it does not make escalation/support policy decisions
- unrelated Cassandra/Chief/Hermes dirty files remain outside Legal

## Completed role-label cleanup

Commit:

```text
efc9c70 fix(legal): use legal-facing role labels
```

Implemented behavior:

- default deployment profiles now emit `role_labels`, not `agent_labels`
- default role IDs/labels are legal-facing:
  - `intake_clerk`: Intake Clerk
  - `evidence_clerk`: Evidence Clerk
  - `records_custodian`: Records Custodian
  - `review_coordinator`: Review Coordinator
  - `compliance_gate`: Compliance Gate
  - `systems_clerk`: Systems Clerk
- `validate_deployment_profile()` still accepts legacy saved profiles with `agent_labels`
- Legal README no longer directly lists internal OpenClaw agent names

Proof:

- `py_compile` passed for `legal/deployment_profile.py`
- focused deployment profile / CLI tests: `31 passed`
- full focused Legal suite after the slice: `107 passed in 1.05s`

Remaining risks:

- legacy saved profiles with `agent_labels` still validate by design
- no on-disk profile migration exists yet
- planning docs may still mention forbidden names as “do not expose” examples

## Completed synthetic mock discovery demo harness

Commit:

```text
7e238de test(legal): add mock discovery demo harness
```

New files:

- `scripts/demo_legal_mock_discovery.py`
- `tests/test_legal_mock_discovery_demo.py`

Usable command:

```bash
python3 scripts/demo_legal_mock_discovery.py /tmp/openclaw_legal_mock_discovery_run
```

Implemented behavior:

- creates a synthetic mock discovery batch under a temp/demo-safe vault root outside `/home/openclaw`
- uses strict `--vault-root` mode
- registers TXT, MD, text-layer PDF, valid synthetic no-text PDF behavior, and unsupported fake extension
- runs `extract-all`, search, report, review packet, and sanitized support packet
- verifies product repo data written: `false`

Demo output summary from the initial implementation pass:

- source count: `5`
- extracted: `3`
- unsupported: `1`
- no_text: `0`
- failed: `1`
- search results: `3`
- report generated
- review packet generated
- support packet generated
- product repo data written: `false`

Note: this initial placeholder behavior was superseded by the later no-OCR PDF status hardening slice.

Proof:

- `pytest -q tests/test_legal_mock_discovery_demo.py`: `1 passed`
- full focused Legal suite including demo test: `108 passed in 1.22s`

## Completed status consistency fix

Commit:

```text
068212e fix(legal): align extraction status diagnostics
```

Implemented behavior:

- extraction now records private per-source `extraction_status`, `extraction_extractor`, timestamp, and reason in the matter manifest for every attempted source
- tracked statuses include `extracted`, `unsupported`, `no_text`, and `failed`
- support packets prefer manifest extraction status over inferred status
- failed attempted PDF extraction no longer appears as `pending`
- mock discovery demo status counts now match support packet diagnostics
- sanitized support packet boundaries remain preserved: no source content, extracted text, private paths, or sensitive filenames

Demo rerun status counts:

- extracted: `3`
- failed: `1`
- no_text: `0`
- pending: `0`
- unsupported: `1`
- product_repo_data_written: `false`

Proof:

- `py_compile` passed for changed Legal modules/scripts
- support/demo focused tests: `7 passed`
- ingestion/pdf focused tests: `19 passed`
- full focused Legal suite: `109 passed in 1.18s`

Remaining gaps:

- `pending` still means extraction was never attempted
- the initial placeholder scanned-style PDF behavior was superseded by the later no-OCR PDF status hardening slice
- unsupported-file Alternative Methods is still not implemented

## Completed Alternative Methods next-action model

Commit:

```text
328eaf1 feat(legal): add alternative methods actions
```

New files:

- `legal/alternative_methods.py`
- `tests/test_alternative_methods.py`

Updated files:

- `legal/cli.py`
- `scripts/demo_legal_mock_discovery.py`
- `tests/test_legal_cli.py`
- `tests/test_legal_mock_discovery_demo.py`

CLI command added:

```bash
python3 -m legal.cli alternative-methods --root ... [--vault-root ...]
```

Implemented behavior:

- `alternative_methods_for_matter()` returns deterministic JSON-ready records for unsupported, failed, or no_text sources
- output excludes source text, extracted text, filenames, private paths, and raw audit logs
- `request_feature` remains locked by default
- no OCR, UI, local repair/build, request-feature export, or public analog search was implemented
- mock discovery demo now reports `alternative_methods_count`

Demo rerun summary:

- alternative_methods_count: `2`
- extracted: `3`
- failed: `1`
- no_text: `0`
- pending: `0`
- unsupported: `1`
- product_repo_data_written: `false`

Proof:

- `py_compile` passed for `legal/alternative_methods.py`, `legal/cli.py`, and `scripts/demo_legal_mock_discovery.py`
- focused Alternative Methods/CLI/demo tests: `20 passed`
- full focused Legal suite: `115 passed in 1.27s`

Remaining gaps:

- `try_local_capability` is only an action label
- `request_feature` stays locked unless a future policy enables escalation
- OCR is not implemented
- public analog fixture search is not implemented

## Completed no-OCR PDF status hardening

Commit:

```text
20312df fix(legal): harden no-text PDF status
```

Updated files:

- `scripts/demo_legal_mock_discovery.py`
- `tests/test_pdf_ingestion.py`
- `tests/test_alternative_methods.py`
- `tests/test_support_packet.py`
- `tests/test_legal_mock_discovery_demo.py`

Implemented behavior:

- mock discovery demo now uses a valid synthetic no-text PDF instead of a malformed placeholder PDF
- valid no-text PDF reports `no_text`, not `failed`
- malformed/minimal PDF remains `failed`, not `no_text`
- Alternative Methods surfaces `ocr_module_needed` for valid no-text PDF
- support packet diagnostics preserve `no_text`
- OCR is still not implemented

Demo rerun summary:

- source_count: `5`
- extracted: `3`
- unsupported: `1`
- no_text: `1`
- failed: `0`
- pending: `0`
- alternative_methods_count: `2`
- product_repo_data_written: `false`

Proof:

- `py_compile` passed
- focused PDF/Alternative Methods/support/demo tests: `22 passed`
- full focused Legal suite: `117 passed in 1.46s`

Remaining gaps:

- OCR is still not implemented
- local repair/build is not implemented
- public analog fixture search is not implemented
- malformed/corrupt PDFs correctly remain `failed`

## Completed local capability policy/stub

Commit:

```text
92e16e5 feat(legal): add local capability policy states
```

New file:

- `legal/local_capability_policy.py`

Updated files:

- `legal/alternative_methods.py`
- `tests/test_alternative_methods.py`

Implemented behavior:

- Alternative Methods items now include deterministic local capability policy metadata:
  - `local_capability_state`
  - `local_capability_kind`
  - `local_capability_reason_category`
  - `request_feature_state`
- unsupported unknown extension maps to `local_capability_not_attempted` / `unknown_local_handler`
- no-text PDF maps to `local_capability_not_installed` / `ocr`
- failed PDF maps to `local_capability_failed_safely` / `pdf_text_extraction`
- `request_feature` remains locked by default
- no manifest mutation
- no new CLI command
- no OCR
- no local repair/build

Demo rerun summary:

- source_count: `5`
- extracted: `3`
- unsupported: `1`
- no_text: `1`
- failed: `0`
- pending: `0`
- alternative_methods_count: `2`
- product_repo_data_written: `false`

Proof:

- `py_compile` passed for `legal/local_capability_policy.py`, `legal/alternative_methods.py`, and `tests/test_alternative_methods.py`
- focused Alternative Methods/support/demo tests: `13 passed`
- full focused Legal suite: `117 passed in 1.27s`

Remaining gaps:

- OCR is still not implemented
- local repair/build and sandbox execution are still not implemented
- public analog search and request-feature export are still not implemented
- support packet diagnostics were not enriched in this slice

## Dual-Lane Development Model

OpenClaw Legal now adopts a **Dual-Lane Development Model** to balance innovation with data safety:

- **Lane A: Synthetic Product R&D Lane**
  - For experimenting with synthetic/public-safe data.
  - External LLMs/tools are permitted for R&D and fixture generation.
  - No real matter data allowed.

- **Lane B: Real Matter Local-Only Lane**
  - For processing real evidence/matter data.
  - External LLMs/tools are prohibited by default.
  - Only local deterministic tools allowed until local models are approved.

Both lanes share the OpenClaw Legal product core but maintain strict data separation. Fake data is for experimentation; real data is for proving trust.

## Strong Product Roadmap

The "Strong Product" vision for OpenClaw Legal is **Private local discovery intelligence for law firms.** The current foundation is the safe local spine that makes the strong product trustworthy.

Phased capability ladder:
1. **Current local discovery spine:** Vault, registration, extraction (text/PDF), search, packets.
2. **Local drop-folder intake:** Streamlined staging and import.
3. **OCR for screenshots/scanned PDFs:** Processing text messages and image-only discovery.
4. **Audio/video extraction:** Transcription and frame-based OCR.
5. **Timestamp/text metadata:** Extracting visible time references and metadata.
6. **Timeline candidates:** Automated draft chronology from multi-source evidence.
7. **Contradiction candidates:** Identifying factual inconsistencies across sources.
8. **Attorney-gated QA/rework loop:** Human-in-the-loop review and refinement of candidates.
9. **Later local LM synthesis:** Advanced analysis under strict Lane B rules.

The roadmap ensures that high-value outputs (timelines, contradictions) remain source-linked attorney-review aids, never substitute legal advice.

## What was planned in the Mac workspace

The Mac planning session created and organized a planning package under:

```text
/Users/hwinshipwheatley/OpenClaw_Watch/law_program
```

The planning package includes technical/product contracts, UX specs, business planning docs, risk docs, and launch decision gates.

## Technical/product contracts created or populated

These documents define product architecture, safety boundaries, update behavior, role naming, vault separation, node connection, queueing, ETA, and model distribution:

- `LEGAL_PRODUCT_CORE_SEPARATION.md`
- `LEGAL_FIRM_IMMUTABILITY_CONTRACT.md`
- `LEGAL_VAULT_PATH_CONTRACT.md`
- `LEGAL_ROLE_NAMING_CONTRACT.md`
- `LEGAL_UNSUPPORTED_LOCAL_BUILD_FIRST.md`
- `LEGAL_UPDATE_LANE_CONTRACT.md`
- `LEGAL_CONNECT_MENU_CONTRACT.md`
- `LEGAL_MATTER_ASSIGNMENT_PERMISSION_CONTRACT.md`
- `LEGAL_FIRM_PROCESSING_QUEUE_CONTRACT.md`
- `LEGAL_ADAPTIVE_ETA_CONTRACT.md`
- `LEGAL_MODEL_DISTRIBUTION_CONTRACT.md`
- `OPENCLAW_LEGAL_CONSOLE_V0_controlled_UX_spec.md`
- `LEGAL_V1_CONTRACT_INDEX.md`

## Business planning docs created or populated

These documents define the buyer problem, business plan, pitch deck, mockups, pricing, gotchas, opportunity models, and go/no-go launch criteria:

- `business_plan/BUSINESS_PLAN_INDEX.md`
- `business_plan/OPENCLAW_LEGAL_BUYER_PROBLEM_STATEMENT.md`
- `business_plan/OPENCLAW_LEGAL_BUSINESS_PLAN.md`
- `business_plan/OPENCLAW_LEGAL_PITCH_DECK_OUTLINE.md`
- `business_plan/OPENCLAW_LEGAL_VISUAL_MOCKUP_BRIEF.md`
- `business_plan/OPENCLAW_LEGAL_PRICING_AND_POSITIONING.md`
- `business_plan/OPENCLAW_LEGAL_GOTCHAS.md`
- `business_plan/OPENCLAW_LEGAL_BUSINESS_MODEL_OPPORTUNITIES.md`
- `business_plan/OPENCLAW_LEGAL_GO_NO_GO_LAUNCH_CRITERIA.md`

## Critical doctrine

The following points are binding planning doctrine for the next chat:

- Mac `OpenClaw_Watch` docs are planning/reflection only.
- PC/WSL `/home/openclaw` is canonical implementation authority.
- **Dual-Lane Development Model** is mandatory: Lane A uses only synthetic/public-safe data and may use external tools; Lane B uses real matter data and is local-only by default.
- **Personal Matter Local-Only Usage Doctrine** is mandatory: The user's personal matter is strictly Lane B. No external LLM or tool may process personal case contents. Local-only capabilities may be used to generate attorney-review aids, not legal advice. Personal matter content must not leak into Lane A (no fixtures, prompts, or demos).
- **IP / Pilot / Ownership Doctrine** is mandatory: Developer owns reusable product core and reference bench; Firm owns private matter data, work product, and production hardware; Validated Update Pipeline (test on bench first, then offer packaged updates) is required.
- **Attorney-Gated QA / Review-and-Rework Doctrine** is mandatory: System creates first pass; separate checker performs evidence-verification (claims verification against source records); flag model (Green/Yellow/Red); attorney-controlled rework loop; no silent fixes; no legal conclusions without review.
- **Known-Answer Fixtures / Validation Sentinels Doctrine** is mandatory: Use seeded synthetic/public-safe evidence packs to benchmark and validate OCR, checker reliability, and update safety; Lane A only; no matter contamination.
- **Hardware Ladder / Capability Tiers Doctrine** is mandatory: Firm buys private local discovery infrastructure, not a chatbot; hardware tiers affect speed and capacity; developer reference bench is separate from firm production hardware; capability claims must be benchmarked; no unvalidated hype.
- **Strong Product Roadmap:** Current work is the safe local spine; future phases include OCR (screenshots/scanned), A/V extraction, timeline candidates, and contradiction detection.
- Do not implement blindly from Mac docs.
- First inspect existing Legal v0 code, tests, docs, and commits.
- No real legal data should enter the repo, prompts, support packets, update packages, or non-local LLM context.
- Legal product UX must not expose internal OpenClaw agent names such as Cassandra, Chief, Guardian, Hermes, or PI.
- Legal-facing roles should use plain law-office labels such as Intake Clerk, Evidence Clerk, Records Custodian, Review Coordinator, Compliance Gate, and Systems Clerk.
- The Go/No-Go Launch Criteria sits above the business plan.
- This should become a bounded product/support business, not a stressful law-firm emergency support job.
- Firm #2 changes must never affect Firm #1 unless Firm #1 explicitly installs/enables them.
- Matter Vault must stay separate from product core and firm profile.
- Unsupported files must use local-first Alternative Methods before feature-request escalation.
- Updates must be lane-based: security, stability, installed module updates, and optional new modules.
- Primary Node should own vault, policy, audit, updates, model distribution, and orchestration.
- Worker/lawyer nodes must not silently join or receive broad matter access by default.
- ETA must be conservative, confidence-labeled, and calibrated before high-confidence claims.
- Huge local models are not the product foundation; deterministic vault/source/search/report/audit/queue boundaries come first.

## Current strategic posture

OpenClaw Legal should be framed as:

```text
Private local discovery infrastructure for law firms that need control, speed, auditability, and predictable cost.
```

It should not be framed as:

- an AI lawyer
- a lawyer replacement
- a generic chatbot
- a complete enterprise e-discovery replacement on day one
- a system that gives legal advice
- a system that removes the need for attorney review

The first sellable version should focus on a controlled local foundation:

- Legal Vault boundary
- matter/source tracking
- hashing
- local extraction
- search
- reports
- review packets
- audit trail
- visible status
- unsupported-file workflow
- update/profile architecture

## Business/launch caution

The user is willing to invest upfront time and build effort, but does not want this to become:

- a painful daily operations job
- a law-firm emergency support desk
- a source of lawsuit risk
- an unlimited custom development trap
- a personally stressful on-call role

The business should aim for passive-ish or remote-managed income where possible, with bounded setup, bounded support, paid modules, clear legal disclaimers, and strict support limits.

No real firm deployment should happen without:

- written scope
- payment/hardware agreement
- support boundary
- liability limitation
- no-legal-advice language
- attorney review requirement
- data ownership terms
- local-only/data residency expectations
- update/support terms
- emergency/rush support pricing or exclusion
- permission to use only sanitized diagnostics for product improvement

## Recommended next step

The next practical slice should be local staging/drop-folder intake for mock discovery.

The goal is to let fake/public-safe discovery files be dropped into a local staging folder and imported into a matter.

Do not jump to email import, cloud import, real discovery, OCR, UI, connectors, distributed workers, model distribution, or cloud connectors.

The next slice should remain small, testable, reversible, and Legal-only. It should include exact files, tests, proof commands, and rollback/checkpoint expectations.

The likely best next engineering move is still not distributed compute or huge local models. It is continuing boundary hardening around the Legal v0 spine.

## What not to do next

Do not immediately build:

- distributed worker nodes
- model distribution
- full desktop app
- OCR pipeline
- email/video/audio ingestion
- cloud connectors
- email/portal ingest
- privilege screening
- legal advice/synthesis
- broad LLM review modules
- hardware leasing operations

Those are later modules or business decisions. They should follow boundary hardening and first workflow proof.

## Next-chat instruction

The new chat should verify current repo state, read this handoff, then help choose and execute only the next small Legal safety/product-boundary slice.

The new chat should not spend time re-summarizing every planning doc unless asked.

The next useful output is either a tight Codex implementation prompt for the chosen slice or a direct implementation pass if the user asks Codex to proceed in `/home/openclaw`.

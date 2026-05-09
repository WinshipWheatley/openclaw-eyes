# Plugin Domain Registry v0

**Artifact Type:** Plugin Domain Registry / Planning Surface
**Status:** Read-only planning artifact. This registry **does NOT claim any active plugins exist**. It is a durable registry for future OpenClaw plugin/workflow-package domains.

## Doctrine

- **No plugin until the job domain is known.**
- **No plugin without a boundary.**
- **No plugin without deterministic checks.**
- **No plugin without an owner/use-case.**
- **No plugin without an activation condition.**
- **No plugin if the domain is too big and secretly contains multiple workflows.**

## Terminology & Boundaries

- **Prompts** are one-off.
- **Skills** are reusable process knowledge.
- **Scripts/Hooks** are deterministic enforcement.
- **MCP/Connectors** are controlled access layers.
- **Plugins/Workflow Packages** bundle a bounded repeatable job.
- **Plugin domains should emerge from repeated real work**, not from novelty or plugin theater.

## Status Scale

- **candidate**: Identified as a potential domain based on repeated work.
- **designed**: Boundaries, inputs, outputs, and requirements mapped.
- **scaffolded**: Initial boundary files and tests created but inactive.
- **implemented**: Logic built but pending final integration/activation.
- **active**: Live and authorized for execution.
- **deprecated**: Retired or replaced.
- **blocked**: Development halted due to unresolved risks or missing prerequisites.

---

## Candidate Domains

### 1. Architecture & Map Gate
- **Domain name:** Architecture & Map Gate
- **Artifact type:** candidate plugin/workflow domain, not active plugin
- **Value space:** Ensures safe codebase navigation by looking up built/unbuilt territory before planning, preventing duplicated work and unapproved custom builds.
- **Job owned:** Architecture intake, Map Room lookup, frontier check, duplicate-work prevention, no-build/prior-art check, boundary framing.
- **Does not own:** Editing files directly, moving folders, runtime launch, approval, private-root access, or final commit authority.
- **Activation trigger:** Starting a new task, receiving a new feature request, or mapping a proposed solution.
- **Inputs:** User request, current frontier, existing `docs/navigation_maps/`.
- **Outputs:** Safe navigation path, prior-art warnings, and boundary framing context.
- **Required maps:** Map Room Index, Frontier Maps, No-Build / Prior-Art Sources.
- **Required scripts/hooks/checks:** `map_room_query.py`, `operator_frontier_map.py`, receipt checks.
- **Authority boundaries:** Strictly read-only navigation lookup.
- **Forbidden actions:** Mutating maps, directly editing code, granting approval, launching execution.
- **Right-size check:** One coherent workflow validating "what exists and what is allowed" before any work begins. It does not mix validation with execution.
- **Current status:** implemented
- **Proof required before activation:** Deterministic lookup tests, Map Room Query v0 completion, receipt integration.

### 2. File Territory / Cleanup
- **Domain name:** File Territory / Cleanup
- **Artifact type:** candidate plugin/workflow domain, not active plugin
- **Value space:** Makes repository hygiene and structural evolution safer by pre-validating moves and enforcing explicit path-dependency safety.
- **Job owned:** Path lookup, dependency scan, candidate move plans, dry-run validation, rollback proof.
- **Does not own:** Actual move/delete/rename/archive until separately approved.
- **Activation trigger:** Proposal to refactor paths, organize folders, or remove stale files.
- **Inputs:** Target paths, dependency scans (`FILE_PATH_DEPENDENCY_SCAN.json`).
- **Outputs:** Dry-run readiness receipt, candidate move plan, rollback steps.
- **Required maps:** `FILE_TERRITORY_CLEANUP_READINESS_MAP.md`, `DEPENDENCY_OWNER_CANDIDATE_MOVE_MAP.md`.
- **Required scripts/hooks/checks:** `scripts/file_path_dependency_scan.py`, dry-run validators.
- **Authority boundaries:** Analysis and planning only. Blocks on explicit approval.
- **Forbidden actions:** Performing the physical file move/delete/rename/archive.
- **Right-size check:** Focuses entirely on evaluating the safety of a move, strictly separating the "checking" from the "doing."
- **Current status:** scaffolded
- **Proof required before activation:** Robust dry-run command validation, exact rollback process documentation.

### 3. No-Build / Prior-Art
- **Domain name:** No-Build / Prior-Art
- **Artifact type:** candidate plugin/workflow domain, not active plugin
- **Value space:** Saves time and system complexity by forcing reliance on existing, proven tools instead of reinventing the wheel.
- **Job owned:** Checking whether existing tools solve the problem before custom build.
- **Does not own:** Installing tools, adding dependencies, connecting services, or approving external tools.
- **Activation trigger:** Any proposal to build a new tool, service, or integration.
- **Inputs:** Proposed functionality or feature.
- **Outputs:** Match with existing tools or a cleared path to build.
- **Required maps:** `NO_BUILD_PRIOR_ART_SOURCES.md`.
- **Required scripts/hooks/checks:** `map_room_query.py` prior-art lookup.
- **Authority boundaries:** Recommendation and blocking lookup only.
- **Forbidden actions:** Installing packages, altering configuration to enable tools, or unilaterally approving a new dependency.
- **Right-size check:** A single question workflow: "Do we already have this?"
- **Current status:** candidate
- **Proof required before activation:** Comprehensive catalog of existing tools and deterministic lookup matching logic.

### 4. Receipt / Completion Gate
- **Domain name:** Receipt / Completion Gate
- **Artifact type:** candidate plugin/workflow domain, not active plugin
- **Value space:** Ensures work is factually complete and verifiable before it is declared done, preserving system truth.
- **Job owned:** Final proof, tests, receipts, git diff checks, boundary report.
- **Does not own:** Deciding failed tests are acceptable or granting authority.
- **Activation trigger:** The conclusion of a task or before proposing a final review.
- **Inputs:** Git diff, test outputs, receipt command outputs.
- **Outputs:** Pass/Fail gate status, combined boundary report.
- **Required maps:** `VALIDATION_MAP.md`, Validation Policy.
- **Required scripts/hooks/checks:** `scripts/openclaw_receipts.py`, `pytest`.
- **Authority boundaries:** Deterministic verification surface.
- **Forbidden actions:** Forcing a pass on failure, altering tests to make them pass falsely, executing workarounds for broken boundaries.
- **Right-size check:** Strictly an enforcement mechanism at the end of a cycle, keeping verification distinct from implementation.
- **Current status:** scaffolded
- **Proof required before activation:** 100% test coverage of the receipt tool and robust git-state analysis.

### 5. Sensitive Boundary
- **Domain name:** Sensitive Boundary
- **Artifact type:** candidate plugin/workflow domain, not active plugin
- **Value space:** Protects critical legal, financial, and private areas of the system from accidental traversal or exposure.
- **Job owned:** Path policy, private-root checks, legal/finance/music-law data boundaries.
- **Does not own:** Reading private content unless explicitly authorized through the correct gate.
- **Activation trigger:** Any file lookup, read, or write targeting explicitly defined sensitive zones (e.g., `mac_eyes`, `OpenClawLegalPrivate`).
- **Inputs:** Target paths, explicit policy overrides if any.
- **Outputs:** Access denial or heavily audited, read-only proof of bounds.
- **Required maps:** Map Room Query fallback boundaries, Sensitive Root documentation.
- **Required scripts/hooks/checks:** Path guard scripts, `no-private-root-check` receipt.
- **Authority boundaries:** Strictly enforces denial; cannot grant access.
- **Forbidden actions:** Extracting private data, writing to private roots, modifying legal templates, or overriding policy without explicit Operator presence.
- **Right-size check:** Purely a firewall workflow. It exists only to block and log, not to read or modify.
- **Current status:** scaffolded
- **Proof required before activation:** Zero-trust path guard tests, verifiable fallback on any unknown path.

### 6. Map Room Query / Navigation Lookup
- **Domain name:** Map Room Query / Navigation Lookup
- **Artifact type:** candidate plugin/workflow domain, not active plugin
- **Value space:** Provides deterministic, read-only answers to where things are and whether they can be touched, without dangerous live filesystem walks.
- **Job owned:** Answering where things are, what depends on them, whether cleanup is blocked, and what proof source supports the answer.
- **Does not own:** Cleanup execution, Cassandra wiring, runtime access, or private-root traversal.
- **Activation trigger:** Agent needs to know file status, dependency risk, or territory rules.
- **Inputs:** Query term (path, script, or domain).
- **Outputs:** Classification bucket, safe/unsafe posture, and cleanup allowed boolean.
- **Required maps:** `DEPENDENCY_OWNER_REVIEW.json`, Map Room navigation guides.
- **Required scripts/hooks/checks:** `map_room_query.py`.
- **Authority boundaries:** Read-only data access to JSON/Markdown truth files.
- **Forbidden actions:** Scanning the live system via `os.walk`, checking SQLite, invoking embeddings, accessing MCP, moving files.
- **Right-size check:** A focused lookup layer acting purely as a dictionary against durable truth files. It isolates the "query" from the "action".
- **Current status:** implemented
- **Proof required before activation:** Comprehensive tests proving it only reads the dictionary and correctly returns fallback safety block on unknown/private roots.
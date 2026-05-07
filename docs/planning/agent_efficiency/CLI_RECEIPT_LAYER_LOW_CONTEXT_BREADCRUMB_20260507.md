# CLI Receipt Layer / Low-Context Agent Interface Breadcrumb

## 1. Purpose
Capture the CLI Receipt Layer concept as a future OpenClaw efficiency/safety lane. This planning document is purely a breadcrumb for inclusion in a future `24_files` source-set batch.

## 2. Core Principle
- **Deterministic tools make facts cheap:** Extracting repo state, checking validations, and auditing changes should not cost LLM context or tokens.
- **Context substrate makes relevance cheap:** By maintaining targeted receipts, facts, and documents, we only supply the agent with exactly what it needs for the task.
- **LLMs spend tokens on judgment, drafting, patching:** Rather than using credits for repeated repo/status discovery, LLM power is strictly preserved for decision-making, content drafting, and proposing bounded patches.

## 3. Two Sides of the Coin
- **CLI receipt side:** Deterministic scripts inspect the local world (repo, files, state, calendar) safely and emit compact, static receipts.
- **RAG/context side:** A context substrate selects the right receipt, fact, or doc for the given actor/task based on policy.
- **Together:** They drastically reduce context load, token burn, and the risk of hallucination or drift by replacing massive text dumps with bounded, highly-relevant summaries.

## 4. Proposed Future Command Catalog
*These are ideas only, not currently implemented.*

- `openclaw repo-check` : Emits a high-level summary of git status, branch, and recent commits.
- `openclaw validation backend-sqlite` : Runs SQLite schema checks and returns a pass/fail receipt.
- `openclaw handoff-check <packet>` : Validates that the active handoff aligns with the latest git state.
- `openclaw source-set-status <packet>` : Reports on the integrity and readiness of the `24_files` source-set.
- `openclaw docs-only-guard --allowed <path>` : Enforces that pending diffs only modify the specified documentation paths.
- `openclaw changed-files-receipt` : Generates a compact list of files changed against the main branch.
- `openclaw lane-readiness <lane>` : Checks if the prerequisites for a specific task lane are met.
- `openclaw sensitive-root-policy --metadata-only` : Scans allowed sensitive root metadata without reading contents.
- `openclaw invoice-reconcile-audit --draft-only` : Generates a dry-run billing reconciliation ledger for review.
- `openclaw actor-context-policy-check` : Verifies that a generated context export adheres to actor permissions.
- `openclaw no-private-root-check` : Scans to ensure no unauthorized private operator folders are targeted.
- `openclaw breadcrumb-index` : Lists all tracked planning breadcrumbs for context inclusion.
- `openclaw prompt-pack <lane>` : Assembles a minimal, low-context prompt specifically tailored to the given lane.
- `openclaw next-lane-candidates <packet>` : Evaluates current receipts to propose the next logical task lanes.
- `openclaw commit-readiness` : Assesses all local checks, handoffs, and diffs to approve a commit payload.

## 5. Standard Receipt Shape
Recommended Markdown and JSON-ish field structure for deterministic output:

```json
{
  "status": "READY | NOT_READY",
  "timestamp": "2026-05-07T00:00:00Z",
  "command_version": "0.1.0",
  "repo_state": "clean",
  "changed_files": [],
  "validation_summary": "Passed all sqlite backend checks.",
  "boundary_warnings": [],
  "allowed_files": ["docs/planning/..."],
  "forbidden_files": ["24_files/..."],
  "required_reads": [],
  "source_set_refs": [],
  "next_candidate_lanes": [],
  "risk_flags": [],
  "operator_approval_required": true,
  "confidence": "HIGH"
}
```

## 6. Architecture Fit
This CLI layer conceptually integrates into the OpenClaw ecosystem by connecting to:
- **SQLite semantic records:** Populating deterministic states into the database.
- **Context export receipts:** Acting as the raw input for context bridges.
- **Actor profiles:** Restricting which receipts can be generated or read.
- **Sensitive root policy:** Acting as the strict enforcer before LLM engagement.
- **Source registry:** Validating `24_files` paths against the canonical list.
- **24_files railroad tracks:** Enforcing bounded, docs-only or narrow implementation lanes.
- **Active handoff train:** Updating the operational snapshot automatically.
- **Cassandra chase-money lane:** Providing the initial raw ledger receipt.
- **Future Operator Harness UI:** Giving the operator a visual dashboard of all generated CLI receipts.

## 7. Timing Recommendation
- **BREADCRUMB_FIRST:** This is purely a conceptual roadmap.
- **Do not implement now** while the source-set renewal and backend handoff work are actively being stabilized.
- Consider a tiny read-only v0 implementation only *after* the next `24_files` renewal.

## 8. Smallest Future Implementation Slice
A potential v0 prototype (future):
- Single entrypoint, e.g. `openclaw_receipt_cli.py` (or equivalent command wrapper).
- Strictly read-only operation.
- No private roots access.
- No network capabilities.
- No model calls.
- Wraps existing validation commands instead of duplicating logic.
- Outputs a compact Markdown/JSON receipt.
- Requires tests proving deterministic output and guaranteeing no private path traversal.

## 9. Risks / Watch-Items
- CLI becoming a hidden authority that bypasses established handoffs.
- CLI mutating state unexpectedly instead of remaining read-only.
- Stale receipts being treated as the current truth by an LLM.
- Receipt over-compression hiding critical nuance.
- Duplicated logic between CLI tools and existing test harnesses.
- Agents over-trusting summaries instead of requesting source files when needed.
- Too many CLIs creating an unmanageable maintenance burden.
- Accidental external model calls being triggered by CLI execution.
- Inadvertent private-root traversal during metadata gathering.
- Adding write-capable commands before a strict authorization policy is ready.

## 10. Next Safe Action
- Keep this document strictly as a breadcrumb / source candidate for now.
- Include it in the next `24_files` renewal consideration.
- **Do not implement** any CLI tools or commands until selected as an explicitly bounded lane.

## Hard Boundaries
- **No implementation** (this is planning only).
- **No private-root access**.
- **No sensitive data reads**.
- **No model/provider calls**.
- **No network** access or transmission.
- **No mutation** of codebase state.
- **No 24_files edits**.
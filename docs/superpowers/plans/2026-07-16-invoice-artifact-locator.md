# Invoice Artifact Locator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Locate and verify the canonical invoice PDF for a client and service period using deterministic provenance, with a bounded agentic miss handoff.

**Architecture:** A standalone locator scans only configured invoice package and handoff roots for manifests, validates client/period/workbook/PDF provenance, excludes quarantine, and groups byte-identical PDFs. Request integration exposes verified candidates and stages an agentic fallback packet only when deterministic lookup misses.

**Tech Stack:** Python 3.12 standard library, JSON, pathlib, SHA-256, pytest.

## Global Constraints

- Search only allowlisted roots; no broad user-directory scan.
- Reject `.openclaw_scope_quarantine` paths.
- Never choose among non-identical valid candidates by modification time alone.
- No attachment delivery, external send, workbook mutation, or authority widening.
- Agentic fallback may rank metadata-only misses but cannot override deterministic verification.

---

### Task 1: Manifest-first deterministic locator

**Files:**
- Create: `invoice_artifact_locator.py`
- Create: `tests/test_invoice_artifact_locator.py`

**Interfaces:**
- Produces: `locate_invoice_artifacts(client_ref: str, service_period: str, *, roots: Sequence[Path]) -> dict[str, Any]`

- [ ] **Step 1: Write failing locator tests**

```python
result = locator.locate_invoice_artifacts("st_annes", "2026-06", roots=[root])
assert result["status"] == "FOUND"
assert result["canonical_candidate"]["invoice_number"] == "3"
assert result["canonical_candidate"]["source_sheet"] == "June 2026"
assert result["canonical_candidate"]["amount"] == 875.0
assert len(result["canonical_candidate"]["duplicate_pdf_paths"]) == 2
```

Add pins for quarantine exclusion, hash mismatch, no candidate, and two non-identical valid candidates returning `AMBIGUOUS`.

- [ ] **Step 2: Verify red**

Run:
`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/openclaw/chief_env/bin/python -m pytest -q -o addopts='' tests/test_invoice_artifact_locator.py`

Expected: import failure for `invoice_artifact_locator`.

- [ ] **Step 3: Implement locator**

Normalize `st-annes` and `st_annes` to the same client key. Walk only the passed roots for `invoice_manifest.json`; skip any path containing `.openclaw_scope_quarantine`. Validate manifest schema, client, period, sibling `invoice.xlsx` and `invoice.pdf`, declared hashes, source sheet, status, amount, invoice number, and send-receipt presence. Group candidates by PDF SHA-256.

- [ ] **Step 4: Verify green**

Run the Task 1 command and require all tests pass.

- [ ] **Step 5: Commit**

```bash
git add invoice_artifact_locator.py tests/test_invoice_artifact_locator.py
git commit -m "feat: add deterministic invoice artifact locator"
```

### Task 2: Request integration and bounded miss packet

**Files:**
- Modify: `workflow_package_queue.py`
- Modify: `workflow_package_request_consumer.py`
- Modify: `openclaw_request_processor.py`
- Modify: `tests/test_workflow_package_request_consumer.py`

**Interfaces:**
- Consumes: `locate_invoice_artifacts(...)`
- Produces: `artifact_locator_result` and optional `agentic_fallback_packet`

- [ ] **Step 1: Write exact-message `1655` red test**

Assert the St. Anne's June PDF request reaches the workflow consumer, returns one canonical artifact identity from duplicate copies, names workbook sheet `June 2026`, invoice `3`, `$875`, draft/never-sent, and preserves false external-action flags.

- [ ] **Step 2: Verify red**

Run only the exact-message test and require failure because no locator result exists.

- [ ] **Step 3: Integrate deterministic lookup**

Detect artifact-location wording only when client and period are resolved. Store verified metadata in detail disclosure; keep operator prose compact. On `NOT_FOUND`, emit a metadata-only fallback packet with the normalized query, allowlisted roots, rejection reasons, and `model_call_performed: false`. Do not call a model while the envelope disallows model calls.

- [ ] **Step 4: Verify owning and canonical gates**

Run workflow queue/consumer/processor/service suites and the canonical 18-file gate with zero failures.

- [ ] **Step 5: Commit and receipt**

```bash
git add workflow_package_queue.py workflow_package_request_consumer.py openclaw_request_processor.py tests/test_workflow_package_request_consumer.py
git commit -m "feat: route invoice artifact location requests"
```

Publish a Sol receipt for Fable. Keep live attachment delivery outside this change.


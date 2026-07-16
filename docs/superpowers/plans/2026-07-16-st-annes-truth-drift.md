# St. Anne's Invoice Truth-Drift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect workbook-to-worklog drift without mutation and render the real St. Anne's June blocker.

**Architecture:** A focused module reads a manifest-backed workbook in read-only mode, verifies the workbook hash, extracts the declared sheet's invoice facts, and compares them with the hygiene read model. It emits a local read model consumed by the existing queue renderer.

**Tech Stack:** Python 3.12, `openpyxl` read-only mode, JSON, SHA-256, pytest.

## Global Constraints

- Workbook owns invoice content; work-log/SQLite is a one-way derived mirror.
- No workbook, ledger, paid-state, send-state, or approval mutation.
- Missing, malformed, ambiguous, or hash-mismatched sources fail closed.
- The exact operator response must say dry-run passed, nothing sent, workbook has seven June services for $875, and the mirror has zero confirmed events.

---

### Task 1: Read-only drift detector

**Files:**
- Create: `st_annes_invoice_truth_drift.py`
- Create: `tests/test_st_annes_invoice_truth_drift.py`

**Interfaces:**
- Produces: `build_truth_drift(manifest_path: Path, hygiene_path: Path, *, generated_at: str) -> dict[str, Any]`
- Produces: `write_truth_drift(payload: Mapping[str, Any], output_path: Path) -> Path`

- [ ] **Step 1: Write failing fixture tests**

Create an `.xlsx` fixture with sheet `June 2026`, invoice number `3`, seven dated service rows at `$125`, label `TOTAL DUE`, and cached total `$875`. Write a sibling manifest whose workbook hash matches and a hygiene model with `business_confirmed_ready_event_ids: []`.

```python
payload = drift.build_truth_drift(manifest, hygiene, generated_at=FIXED_NOW)
assert payload["status"] == "DRIFT_DETECTED"
assert payload["workbook_truth"]["service_count"] == 7
assert payload["workbook_truth"]["total_due"] == 875.0
assert payload["mirror_truth"]["confirmed_event_count"] == 0
assert payload["machine_proof"]["workbook_mutation_performed"] is False
assert workbook_sha_after == workbook_sha_before
```

- [ ] **Step 2: Verify red**

Run:
`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/openclaw/chief_env/bin/python -m pytest -q -o addopts='' tests/test_st_annes_invoice_truth_drift.py`

Expected: import failure for `st_annes_invoice_truth_drift`.

- [ ] **Step 3: Implement minimal detector**

Use `openpyxl.load_workbook(path, read_only=True, data_only=True)`. Resolve the local workbook as `manifest_path.parent / "invoice.xlsx"`, verify `package_workbook_sha256`, require the declared `source_sheet`, count dated service rows with numeric line amounts, and locate the total by the `TOTAL DUE` label rather than a fixed row.

Return `SOURCE_UNAVAILABLE` for missing inputs, `HASH_MISMATCH` for a bad workbook hash, `DRIFT_DETECTED` when workbook service count differs from mirror confirmation count, otherwise `IN_SYNC`. Every receipt includes false performed/authority flags.

- [ ] **Step 4: Verify green and failure cases**

Add tests for missing sheet, malformed hygiene IDs, and hash mismatch. Run the Task 1 command and require all tests pass.

- [ ] **Step 5: Commit**

```bash
git add st_annes_invoice_truth_drift.py tests/test_st_annes_invoice_truth_drift.py
git commit -m "feat: detect St Annes invoice truth drift"
```

### Task 2: Render drift instead of false absence

**Files:**
- Modify: `workflow_package_queue.py`
- Modify: `openclaw_request_processor.py`
- Modify: `tests/test_workflow_package_request_consumer.py`
- Test: `tests/test_workflow_package_queue.py`

**Interfaces:**
- Consumes: `generated/read_models/st_annes_invoice_truth_drift.json`
- Produces: `operator_display["missing_items"]` and layered `missing_items_short`

- [ ] **Step 1: Write exact-message red test**

```python
assert response["one_line_answer"] == (
    "The St. Anne's invoice dry-run passed and nothing was sent. "
    "The June workbook has 7 services totaling $875, while the work-log mirror has 0 confirmed."
)
assert response["missing_items_short"] == [
    "Reconcile workbook billables into the work-log mirror"
]
```

- [ ] **Step 2: Verify red**

Run the exact message `1652` test and require it fail on the old zero-billables sentence.

- [ ] **Step 3: Implement drift-aware renderer**

Load the drift read model with strict client/period/status validation. Prefer `DRIFT_DETECTED` facts over hygiene-only readiness. If the drift model is absent or malformed, retain the existing fail-closed readiness-unavailable wording.

- [ ] **Step 4: Verify owning and composition gates**

Run queue, workflow consumer, request processor, and response service suites. Then run the canonical 18-file composition gate and require zero failures.

- [ ] **Step 5: Commit**

```bash
git add workflow_package_queue.py openclaw_request_processor.py tests/test_workflow_package_queue.py tests/test_workflow_package_request_consumer.py
git commit -m "fix: surface St Annes workbook mirror drift"
```

### Task 3: Generate local receipt and hand off

**Files:**
- Create locally: `generated/read_models/st_annes_invoice_truth_drift.json`
- Create: `Operator/from-codex/SOL-ST-ANNES-TRUTH-DRIFT-READY-20260716.md`

- [ ] **Step 1: Run detector against the verified June handoff**

Use the manifest under `codex_mac_bridge/from-codex-mac/invoice_handoffs/st-annes-2026-06-real-pdf-20260704T231607/` and the current hygiene read model.

- [ ] **Step 2: Inspect receipt**

Require `DRIFT_DETECTED`, `7`, `875.0`, `0`, hash verification true, and all mutation/send flags false.

- [ ] **Step 3: Publish engineering receipt**

Record commits, red/green evidence, exact source refs, and the fact that promotion/send/mutation remain held for Fable review.


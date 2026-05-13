<!--
GENERATED FILE - DO NOT EDIT MANUALLY
This file is programmatically generated from repository evidence.
Durable truth comes from receipts, tests, and committed source.
-->

# GENERATED CURRENT STATE
## 1. Confirmed System State
- Ledger Status: active
- Active Handoff: This handoff is the train. The roadmap authority is 24_files/01_PROJECT_SOURCE_SET_INDEX_AND_RAIL_MAP.md.
- SQLite Ledger v0 exists, and Cassandra `handle()` is wired to record event/packet receipts.
- Business Ops Packet v0 is defined for intent-based capability gating.
- Operator Doctrine root files exist in `Operator/`.
- Orientation Snapshot v0 tool exists and is verified (read-only).
- The current checkpoint may use the active handoff, but durable truth comes from committed repo docs/source, receipts, tests, and explicit operator promotions.

## 2. Recent Verification Receipts
Deterministic evidence proofs from the ledger (excludes status self-checks).
Strongest recent clean proof: [PASS] business_ops_ledger_tests head=942d3e00

- 2026-05-11 17:09 [APPROVAL_REQUEST] [SQLITE_VERIFIED] Manual test of approval request visibility (No Decision/No Execution)
- 2026-05-10 22:37 [PASS] business_ops_ledger_tests exit=0 head=942d3e00
- 2026-05-10 22:37 [PASS] cassandra_status_wiring_tests exit=0 head=942d3e00
- 2026-05-10 22:37 [PASS] orientation_snapshot_smoke exit=0 head=942d3e00
- 2026-05-10 22:37 [PASS] ledger_inspector_summary exit=0 head=942d3e00

### Module Atlas Artifact Checkpoints
**Evidence:** committed docs/code artifacts have metadata-only SQLite checkpoint receipts.
**Boundary:** recorded checkpoint only; not runtime authority. No full Markdown/code body is ingested.
**Blocked:** no module, agent, broker, customer deployment, or runtime behavior is activated or authorized by these receipts.
**Next safe move:** review docs/tests/receipts; runtime activation still requires a separate approved lane.

| Artifact | Receipt Time | Checkpoint | Authority Boundary |
| --- | --- | --- | --- |
| `tests/test_module_manifest_validation.py` | 2026-05-12 21:40 | recorded `validation-proven` | `authority=no-runtime-authority`; `runtime_activation=false`; `sqlite=receipt-record-only`; `body=not-ingested` |
| `scripts/validate_module_manifests.py` | 2026-05-12 21:40 | recorded `validation-proven` | `authority=no-runtime-authority`; `runtime_activation=false`; `sqlite=receipt-record-only`; `body=not-ingested` |
| `docs/module_atlas/OPENCLAW_MODULE_MANIFEST_VALIDATION_CONTRACT_V0.md` | 2026-05-12 21:40 | recorded `validation-proven` | `authority=no-runtime-authority`; `runtime_activation=false`; `sqlite=receipt-record-only`; `body=not-ingested` |
| `docs/module_atlas/OPENCLAW_SYNTHETIC_MODULE_MANIFEST_EXAMPLES_V0.md` | 2026-05-12 21:40 | recorded `inert` | `authority=no-runtime-authority`; `runtime_activation=false`; `sqlite=receipt-record-only`; `body=not-ingested` |
| `docs/module_atlas/OPENCLAW_MODULE_MANIFEST_DRAFT_SCHEMA_V0.md` | 2026-05-12 21:40 | recorded `inert` | `authority=no-runtime-authority`; `runtime_activation=false`; `sqlite=receipt-record-only`; `body=not-ingested` |
| `docs/module_atlas/OPENCLAW_MODULE_ATLAS_V0.md` | 2026-05-12 21:40 | recorded `docs-only` | `authority=no-runtime-authority`; `runtime_activation=false`; `sqlite=receipt-record-only`; `body=not-ingested` |

## 3. Source Inventory
Bounded Source Inventory v0

Evidence:
- 13 explicit allowlisted source records are known as metadata-only context.
- Records carry path, type, size, Git status when available, sensitivity label, authority label, and inclusion reason.
- Source groups: module_atlas_documentation=3, module_atlas_validation_contract=1, module_manifest_validator=1, operator_status_doctrine=1, operator_status_script=1, receipt_bootstrap_script=1, receipt_spine_doctrine=1, validation_test=4.
- Body ingest is `false` for every record.

Boundary:
- Inventory is allowlist-only; it does not scan the whole repo or hard drives.
- `body_ingested=false`; SQLite is untouched; records are source metadata, not source bodies.
- Authority labels describe documentation/receipt/validation posture only; they do not grant runtime authority.

Blocked:
- 8 no-go boundary examples are represented without stat, scan, or body read.
- Secrets, private data, legal, tax, CPA/finance, AppData, and runtime logs remain outside source inventory.
- Blocked examples: `.chief.env`; `.google-secrets/`; `Private/`; `Legal/`; `Tax/`; `CPA/`; `C:/Users/Winship/AppData/`; `.openclaw/runtime_logs/`.
- No agents, modules, brokers, customer deployment, external tools, or runtime behavior are activated.

Next safe move:
- Use `--format json` as metadata-only agent context; promote any body access or accepted working context in a separate approved lane.

## 4. Truth Substrate Summary
Registry-governed canonical facts and source documents.
- **Facts**: 83 (71 doctrine, 12 historical)
- **Candidate Truth Posture**: 0 VERIFIED, 83 UNCERTAIN, 0 BLOCKED sources
- **Runtime Authority**: False
- **Coverage**: 9/9 SOURCE_REGISTRY documents
- **Readiness**: READY

> Truth substrate status is read-only, a read-model of candidate posture. Truth status describes candidate verification posture, not live runtime health, agent authority, or terminal gateway decisions.

## 5. Active Lane & Doctrine
Hardening the "Business Ops Spine" (deterministic intent, bounded capability, SQLite Ledger) and canonicalizing the "Operator Doctrine" (North Star, Manifesto, Anti-drift) into a concise Orientation Contract.

## 6. Tool & Surface Boundaries
### Allowed Tools
- Repository-local file reading and surgical editing.
   - Shell commands for status, testing, and non-destructive operations.
   - Read-only repo inspection and test commands are allowed for Orientation Snapshot; ledger writes require a separate bounded lane.
   - Classification of intent via `operator_intent_core.py`.

### Forbidden Surfaces
- Private roots (`.google-secrets`, `.chief.env`, etc.).
   - Legal/Client/Private folders.
   - External provider/model APIs without an Action Covenant.
   - Credentials, tokens, and billing logic.

## 7. North Star
Make daily life lighter without becoming hidden authority. The computer becomes a natural extension of the operator. The machine carries the weight; the operator keeps the crown.

## 8. Safety & Staleness
- **Runtime Health**: Not checked by this generator. Refer to `docs/operations/` or live diagnostics.
- **Staleness**: This file is stale if the git HEAD has changed or if confirmed facts (e.g. active lane, contract items) have been modified since the generation timestamp.
- **Privacy**: No PII or raw sensitive data is stored in this read-model.
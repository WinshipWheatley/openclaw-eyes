# Task G2C-006: SQLite Data-Access Layer (append-only versioned store)

## Acceptance Criteria
**Version / Hash:** 20260625-G2C006-v1
**Architecture owner:** Opus (this spec). Implementation may be split to Sonnet; Gemini audits before merge.
**Depends on:** G2C-005 (canonical serialization, MERGED `563e740b`) + the four domain records (G2C-001/002/003A/004A).

---

## A. Architecture Principles (binding — violations fail the audit)

1. **Append-only, immutable.** The store NEVER mutates or deletes an existing row. A row, once written, is final. "Update status" is **append a new superseding version**, never an in-place `UPDATE`/`DELETE`. (This is the corrective contract from the Step-2 audit — G2C-003/004 drifted by embedding mutable/derived states.)
2. **Versioned snapshots, current is derived.** Each record's "current" state is **derived** from the append-only history, never stored as a mutable flag. Derived/aggregate financial states (e.g. `partially_paid`, `paid_in_full`) are **forbidden** — they belong to future payment-allocation logic, not this store.
3. **Idempotent ingest.** Every record carries `idempotency_key`. Re-appending the *same* logical write (same `idempotency_key` + byte-identical canonical payload) is a **no-op** returning the existing row. Same `idempotency_key` with *different* content is a hard **IdempotencyConflict** error.
4. **Extend, don't compete.** This store persists the four domain records only. It MUST NOT create a competing provenance/evidence ledger. `source_ref` is stored as an **opaque reference** to the shared evidence registry — never copied/duplicated.
5. **Canonical payload is the source of truth.** Each row stores the exact `to_json(record)` (G2C-005) plus its `canonical_sha256`. Reads reconstruct via `from_json` (strict). Typed/indexed columns are *derived* from the record and MUST equal the payload — verified at write time.
6. **Authority boundary.** Pure local persistence of facts. NO money movement, payment execution, bank, send, email, Telegram, workbook, or network behavior — and no method that could. Reads/appends of facts only.

---

## B. Scope & Target Files

- `ar_gig_to_cash_store.py` — the DAL.
- `tests/test_ar_gig_to_cash_store.py` — the test suite.
- DB path is **injectable** (constructor arg). Canonical default (operator decision D2): **`/home/openclaw/state/gig_to_cash/gig_to_cash.sqlite3`** — the module creates the parent dir on first open (no established canonical-state dir exists today). Never the polish-loop `control_plane.sqlite3`, generated read-models, or any vault path. **Test DBs (D2):** use a **temp FILE** DB for transaction / foreign-key / concurrency tests; `:memory:` is acceptable ONLY when the *same connection* is retained for the whole test. The canonical JSON stored inside the authoritative SQLite row is the record of truth — distinct from, and does not make authoritative, any generated JSON file.
- Do **not** modify the four domain-record modules or `ar_gig_to_cash_serialization.py`. If a genuine contract defect blocks the DAL, **stop and report** — do not silently change a model.

---

## C. Schema (DDL — exact; SQLite)

`PRAGMA foreign_keys = ON;` `PRAGMA journal_mode = WAL;` Common columns on every record table:
`ingestion_seq INTEGER PRIMARY KEY AUTOINCREMENT`, `ingested_utc TEXT NOT NULL` (ISO-8601 UTC, supplied by caller or `strftime`), `canonical_json TEXT NOT NULL`, `content_sha256 TEXT NOT NULL`, `idempotency_key TEXT NOT NULL UNIQUE`, `lifecycle_state TEXT NOT NULL`.

1. **`gig_records`** — single-identity, **CREATE-ONCE** (operator decision D1 — NOT latest-ingested). Cols: `gig_id TEXT NOT NULL UNIQUE` + common. **Exactly one row per `gig_id`.** `get_current` returns that row; there is no version chain and no "latest" semantics. Gig **lifecycle changes are NOT supported in G2C-006** — they await a future contract that adds explicit `gig_version_id` + `supersedes_gig_version_id`. Uniqueness from `UNIQUE(gig_id)` + `UNIQUE(idempotency_key)`.
2. **`work_session_records`** — correction-pointer. Cols: `work_session_id TEXT NOT NULL`, `gig_id TEXT NOT NULL`, `supersedes_session_id TEXT NULL` + common. Current(work_session_id) = the row whose `work_session_id` is not referenced by any other row's `supersedes_session_id`. Index `(work_session_id)`, `(gig_id)`, `(supersedes_session_id)`.
3. **`invoice_records`** — full version chain. Cols: `invoice_id TEXT NOT NULL`, `invoice_version_id TEXT NOT NULL UNIQUE`, `supersedes_invoice_version_id TEXT NULL`, `source_ref TEXT NOT NULL` + common. Current(invoice_id) = the version not referenced by any `supersedes_invoice_version_id`. Index `(invoice_id)`, unique `(invoice_version_id)`.
4. **`expected_receivable_records`** — full version chain, FK to a specific invoice version. Cols: `receivable_id TEXT NOT NULL`, `receivable_version_id TEXT NOT NULL UNIQUE`, `invoice_id TEXT NOT NULL`, `invoice_version_id TEXT NOT NULL`, `supersedes_receivable_version_id TEXT NULL`, `source_ref TEXT NOT NULL` + common. **FK** `(invoice_version_id)` → `invoice_records(invoice_version_id)` (a receivable must reference an already-stored immutable invoice version). Current(receivable_id) = version not superseded.
5. **`schema_migrations`** — `version INTEGER PRIMARY KEY`, `applied_utc TEXT NOT NULL`, `description TEXT NOT NULL`.

Referential rule: enforce hard FK only on **internal immutable version links** (receivable→invoice_version). Cross-domain refs (`counterparty_ref`, `billing_*_ref`, `worker_ref`, `source_ref`, `work_session.gig_id`) are **soft** text references (they point outside this store / to the evidence registry) — validated as non-empty by the record contract, not FK-constrained here.

---

## D. Operations (exact contracts)

Class `GigToCashStore(db_path: str)`; `open()`/context-manager applies migrations idempotently.

1. `append(record) -> AppendResult` — accept any of the 4 record types (reject others with `TypeError`). Serialize via `to_json`; compute `canonical_sha256`. **Idempotency:** if `idempotency_key` exists → compare `content_sha256`: equal ⇒ no-op, return existing (`created=False`); differ ⇒ raise `IdempotencyConflict`. For versioned types, `*_version_id` must be globally unique (UNIQUE enforces). **GigRecord create-once (D1):** beyond idempotency, a GigRecord whose `gig_id` already exists is a no-op IFF the stored `content_sha256` is identical (`created=False`); a **different** payload for an existing `gig_id` raises `GigImmutableConflict` — gigs never gain hidden versions. Insert in **one transaction** (`BEGIN IMMEDIATE`). Returns the stored identity + `created` flag.
2. `get_current(record_type, logical_id) -> record | None` — reconstruct the current snapshot via `from_json`; return `None` if absent.
3. `get_version(record_type, version_id) -> record | None` — versioned types only (`TypeError` for Gig).
4. `list_history(record_type, logical_id) -> list[record]` — full append-only chain, oldest→newest.
5. `supersede(prior_logical_id, new_record) -> AppendResult` — the ONLY "update_status". Validate: `new_record`'s logical id == `prior_logical_id`; for versioned types `new_record.supersedes_*_version_id` must equal the current version's `*_version_id`; for WorkSession `new_record.supersedes_session_id == current.work_session_id`. Then `append(new_record)` transactionally. The prior row is **never touched** (test asserts its `content_sha256` unchanged + row count grows by exactly 1). **`supersede` is NOT supported for GigRecord** (raises `UnsupportedOperation`) — gig lifecycle changes await the future gig-version contract (D1).
6. Integrity on read: if a stored row's `content_sha256` ≠ `sha256(canonical_json)`, raise `IntegrityError`. `from_json` strictness (unknown/missing fields, dup keys, NaN) applies on every read.

No `delete`, no `update`, no money/send/bank method anywhere in the public or private surface.

---

## E. Transactions, Migrations, Isolation

- **Transactions:** every write is a single `BEGIN IMMEDIATE` … `COMMIT` (atomic); failure rolls back leaving zero partial rows. Concurrent writers serialize on the immediate lock.
- **Migrations:** forward-only, ordered, recorded in `schema_migrations`. `open()` applies any unapplied migration in a transaction and is **idempotent** across reopens (no double-apply). Migration #1 = the full DDL in §C. Unknown/newer DB schema version than the code supports ⇒ refuse to open (`MigrationError`), never silently downgrade.
- **Isolation:** the DB is a dedicated file; the store opens only that path; it never reads/writes another component's DB.

---

## F. Required Tests (exact coverage — independent of the implementation)

Author the tests to the *contract*, not the implementation (the Step-2 drift happened because a worker's own tests encoded an invalid contract). Cover, at minimum:
1. **Migration:** fresh `open()` creates all tables + records migration #1; reopening twice does not re-apply or duplicate; `schema_migrations` has exactly the applied rows.
2. **Round-trip per type (×4):** append → `get_current`/`get_version` returns an object **equal** to the input (canonical-JSON equality), for all four record types incl. optional-null fields.
3. **Idempotency:** re-append identical record ⇒ `created=False`, row count unchanged; same `idempotency_key` + different content ⇒ `IdempotencyConflict`; row count unchanged.
4. **Versioning/supersede:** append v1, `supersede`→v2 ⇒ `get_current` is v2, `get_version(v1)` still v1, `list_history` = [v1, v2], and **v1's row `content_sha256` is unchanged** + total rows grew by exactly 1. Invalid supersede linkage (wrong logical id / wrong supersedes pointer) ⇒ rejected.
5. **Append-only invariance:** no public/private path performs `UPDATE`/`DELETE` (assert via SQL row immutability across operations).
6. **FK integrity:** receivable referencing an absent `invoice_version_id` ⇒ rejected; referencing a present one ⇒ accepted.
7. **Strict read:** a row with tampered `canonical_json` (sha mismatch) ⇒ `IntegrityError`; an unsupported/forbidden payload ⇒ rejected by `from_json`.
8. **Authority/exclusions:** the store exposes no money/send/bank/network method; tests run entirely on a temp/`:memory:` DB; no shared/production/vault path is opened.
9. **Determinism:** stored `canonical_json` is byte-identical to `to_json(record)`; `content_sha256` matches.

---

## G. Build & Review Plan (Opus-owned, split to Sonnet, Gemini-audited)

1. **Opus (done):** this durable spec — schema, identity model, operation contracts, invariants, authority boundary.
2. **Sonnet-A:** implement `ar_gig_to_cash_store.py` strictly to §C–§E. No deviation; if blocked by a contract defect, stop + report.
3. **Sonnet-B (independent):** implement `tests/test_ar_gig_to_cash_store.py` strictly to §F — written against this spec, **not** against Sonnet-A's code, so the tests can catch an invalid implementation.
4. **Opus:** reconcile A+B, run the suite, review the diff for scope + principle adherence (append-only, no derived states, authority boundary), confirm no domain-model/G2C-005 edits.
5. **Gemini:** adversarial audit against this spec (contract drift, hidden mutation, authority leakage, FK gaps) before merge.
6. **Merge:** cherry-pick onto `codex/stress-fixes` + durable spec, re-verify on the integrated branch (the G2C-005 pattern). G2C-007 stays BLOCKED until then.

---

## H. Architecture decisions — RESOLVED (operator, 2026-06-25)
- **D1 — Gig versioning: RESOLVED → create-once.** GigRecord is create-once (§C.1, §D.1, §D.5): unique `gig_id`, same key+payload returns existing, changed payload for an existing `gig_id` raises `GigImmutableConflict`, and gig lifecycle changes are deferred to a future contract with explicit `gig_version_id` + `supersedes_gig_version_id`. No hidden version semantics.
- **D2 — DB location/name: RESOLVED → approved.** Module `ar_gig_to_cash_store.py`; canonical DB `/home/openclaw/state/gig_to_cash/gig_to_cash.sqlite3`; injectable path; temp-file DBs for tx/FK/concurrency tests (`:memory:` only with a retained connection); canonical JSON in the SQLite row is the record of truth.

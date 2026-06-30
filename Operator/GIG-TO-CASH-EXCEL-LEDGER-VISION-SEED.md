# Gig-to-Cash → Excel/Ledger Vision — PARKED DESIGN SEED

Status: **PARKED.** Captured 2026-06-30 from operator. Do NOT build yet. The G2C bridge
(Codex P7) stays DORMANT (`g2c_db_path=None` at `cassandra_brain.py:6734`) until this whole
flow is designed. This is the future home for the "make gigs/payments/repairs a shared,
booked, Excel-reflected capability" work. Pick up only after the operator says go.

## The operator's real workflow (3 areas to master)
1. **Pre-SQLite staging space** — where a parsed intake (payment/gig/expense/repair) lands
   first for the operator to see + validate BEFORE it touches the real books.
2. **The actual SQLite space** — the canonical Gig-to-Cash store (`ar_gig_to_cash_store`,
   default `/home/openclaw/state/gig_to_cash/gig_to_cash.sqlite3`). Promoted from staging
   only on operator confirmation.
3. **The actual Excel artifacts** — the invoice workbook gets updated (or a **work-order**
   if it's a Niles/technical item), and the ledger gets updated. The later part of step 3 is
   tied to the ledger.

## The confirmation flow (NOT a cryptic one-line flip — this is the UX requirement)
- Operator says to the relevant agent (Cassandra / Niles / whoever): **"Show me what you
  have for X."**
- Operator sees it via Telegram / the app / wherever needed.
- Operator can **confirm and/or ask for adjustments**, and **see the adjustments** once made.
- Operator says **"looks good"** → that flips it from staging INTO the books (step 2→3).
- Then the downstream business artifacts update automatically (invoice workbook / work-order /
  ledger). The operator must never have to go figure out how to take it to the next step.

## Invoice workbook structure (operator's real system)
- **One workbook per company** that gets invoiced.
- Each workbook has **a separate page per invoice**; each invoice has **its own invoice number**.
- A **new invoice** must reflect the **previous invoices' paid status**: it carries forward
  what's still owed. If a previous invoice is unpaid, the new invoice **includes that prior
  balance in its total** (rolling unpaid forward).

## Ledger structure (operator's real ledger)
- The ledger workbook has **tax pages**. The system must be able to update the ledger.
- The **ledger page has 3 sections**:
  1. **Top** — items that have been **reconciled**.
  2. **Middle** — where **new bank data** is loaded (manually today; eventually the system loads it).
  3. **Bottom** — **upcoming payables & receivables.** ("Estimated" is the operator's word but
     it's really **predicted/known-incoming**: if it's down there, the operator KNOWS it's
     coming. This is the cash-flow forecast — what the money situation will look like as
     payable/receivable dates move into the future vs what the current bank balance shows; the
     ledger matches it against in-processing items.)
- The system needs to **keep the bottom section's payable/receivable totals updated**, AND
  **know what's currently in the ledger** so it can "keep a lookout" (watch for matching items).

## Existing automation to wire up (don't rebuild — the operator already has scaffolding)
- The invoices and ledger already have **the beginnings of automation written in by the
  ChatGPT that lives inside Excel** (Excel-proficient).
- There's **also a Claude Excel-specific integration in there, not yet used.**
- Eventually/soon: wire all of this so the system masters the 3-area workflow end to end.

## What's needed when we build this (operator will provide)
- The **ledger file path** and the **invoice workbook paths** (operator offered to give them).
- A read of the **current ledger/invoice state** so the system knows what exists.

## Modeling gaps this implies (from the architecture map, for the future build)
- G2C is **receivables-only today**. Expenses + **outbound TD/repair payouts** (accounts
  PAYABLE) have **no record type** — needs a new payable/expense dataclass + serialization +
  migration v2 + store handlers + a normalization branch. (`expense_log` parses but
  `_write_g2c_normalization` returns unsupported.)
- The intake read model (`operator_intake_events.json`) is a single JSON file rewritten
  wholesale with **no locking** — fine for one serialized writer (Cassandra) but a second live
  writer (Niles) can race; needs concurrency handling before multi-agent live writes.
- Overlap is computed transiently but **not persisted**; no per-agent claimed/acknowledged
  state; no live agent→agent notify bus (only poll). These matter for the staging→confirm UX.

## Related
- Maps to [[project_gig_to_cash]]. Architecture map that grounds this: workflow run
  `wf_886020fc-cf3` (full output in the session task dir).

# Lighter Days v0

Status: agent-built slice set in the collaborative `docs/specs/` lane. Review required before activation. Not runtime law.

Generated: 2026-09-02. Branch: `claude/lighter-days` (off the live lane, includes the egress grader fix).

Purpose: make the two things the operator asked for real inside the existing machine, without new authority.
"Help me become the best musician I can be" and "do work that pays so well that money stops being a thought."
The system's own north star already says it: convert creative work, obligations, and financial complexity into
prepared paths, evidence, and next safe actions, so daily life feels lighter. These slices do exactly that and
nothing more: every one is prepare-only, deterministic, fail-closed, and reversible.

## What lands

| Slice | Files | What it does for the operator | Authority |
|---|---|---|---|
| Open AR aging | `open_ar_aging.py`, `config/receivable_terms.v1.json`, `scripts/export_open_ar_aging.py` | Every open row in the ONE money source gets a due date, days past due, a bucket, and one next action. One line in the morning brief. | read-only |
| Gig ledger bridge | `gig_ledger_bridge.py`, `scripts/land_gig.py` | A gig said out loud becomes a GigRecord, a draft InvoiceRecord, and an open ExpectedReceivable in the G2C store, so it shows in the money truth the same day. Dry-run by default; `--apply` writes. | local ledger write, idempotent; never marks paid |
| Capital Hilton PO cycle | `capital_hilton_po_cycle.py`, `config/capital_hilton_po_cycle.v1.json`, `scripts/export_capital_hilton_po_cycle.py` | Knows each PO's cap and what is invoiced, counts uninvoiced performances, and when a new PO is needed drafts the request email to AP as a local `.eml` and raises one attention event. | draft only; Coupa and sending stay manual and gated |
| Live rig as data | `config/live_rig.v1.json`, `live_rig.py`, `scripts/export_live_rig.py`, rig KB seeds, `showprofile.py` looper and cue rules | LIVE-RIG.md becomes a read model: budget, open loops by owner, deal terms side by side, and a proposed X32 channel map plus a `.scn` artifact that answers the two open routing questions as proposals. The producer doctrine and rubric under `docs/producer/` and `config/producer/` were already on the live lane and are the taste reference these slices point at. | artifact only; loading a scene on real hardware stays refused |
| Practice loop | `practice_loop.py`, `config/practice_targets.v1.json`, `scripts/export_practice_plan.py`, Cassandra hook | Repertoire, sessions, confidence, streaks, and a daily plan. "practiced Blue Weather 30 min" logs it; "what should I practice" plans it; no model runs. One line in the morning brief. | local store only |
| Album row seeding | `scripts/seed_album_rows.py` | Seeds rows for the nine songs the planner cannot see. Dry-run by default. | album CSV write with `--apply` |
| Timers | `systemd/user/openclaw-open-ar-aging`, `openclaw-capital-hilton-po-cycle`, `openclaw-practice-plan` | Three daily exports before the 08:00 brief. | oneshot, NoNewPrivileges |
| Portability | `operator_truth_store.py`, voice modules, topology registry, one test | The live lane compiles on Python 3.11 as well as 3.12. | none |

## Activation on the PC, in order

1. `git fetch origin claude/lighter-days && git checkout claude/lighter-days`, then run the focused tests listed in the branch's commits, then `scripts/green_gate.sh claude/lighter-days` before promoting.
2. Seed the music side: `python3 scripts/seed_album_rows.py` (review), then `--apply`; send "cancel album" once on Telegram.
3. Practice: `python3 -c "import practice_loop as p; s=p.PracticeStore(str(p.DEFAULT_DB_PATH)); p.seed_album_repertoire(s); p.seed_targets(s, 'config/practice_targets.v1.json')"`, then on Telegram: "what should I practice".
4. Money facts: fill `config/capital_hilton_po_cycle.v1.json` performances as they happen; run `python3 scripts/export_capital_hilton_po_cycle.py`; read the draft under `generated/email_drafts/capital_hilton_po_cycle/`.
5. Timers: `bash scripts/install_openclaw_stack.sh --apply` renders every template; enable the three new timers with `systemctl --user enable --now openclaw-open-ar-aging.timer openclaw-capital-hilton-po-cycle.timer openclaw-practice-plan.timer`.
6. Land a gig from Telegram text on the PC: `python3 scripts/land_gig.py "Dane asked me to play Oct 17 at 49 West for $500"` (dry run), then `--apply`. The client comes from the contacts registry (Dane resolves to Live Arts MD today); when the sentence names a different venue the dry run prints a `Check:` line and the fix is `--client 49_west --client-name "49 West"`. Then `python3 scripts/export_receivables_month_bounded.py` so the ONE money source shows the row.

## What this does not do

No send is performed anywhere. SEND_HOLD, Guardian, and the exact-send phrase are untouched. No Coupa, browser, bank, or provider call. No audio is read. The Hilton PO request is a draft the operator sends, until the day a per-client trust policy exists.

## Next after this

Graduated trust per client so St. Anne's monthly invoice can go from prepared to sent with one tap; a bank-alert watcher feeding `bank_email_reconcile`; the practice loop learning from the X32 scene and the setlist once the Hilton fifteen arrive.

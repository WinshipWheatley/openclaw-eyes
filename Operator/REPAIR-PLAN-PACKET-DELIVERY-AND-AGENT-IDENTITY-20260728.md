# Repair plan — packet content delivery, and agent identity on Telegram

**Date:** 2026-07-28 · **Author:** Opus-PC · **Trace:** read-only
**Evidence:** `fleet_coord/PRODUCT/TELEGRAM-PACKET-ACCEPTANCE-20260728.md` (0 PASS / 1 PARTIAL / 5 FAIL)
**Status:** plan + exact tests. Nothing deployed, activated, restarted, sent, or gate-changed.

---

## SEAM 1 — packet selected, contents never delivered

### What was observed

Maestro named `chief_status_rail.json` as its selected packet and answered `UNKNOWN`.
The file exists: 30,226 bytes, `generated/read_models/chief_status_rail.json`, mtime
2026-07-26. So selection worked and delivery did not.

### Root cause, located

`maestro_context_packet.py`, the sqlite canonical-facts loader, docstring at **line 2672**:

```
- Returns [] gracefully on ANY error (missing file, locked db, etc.).
```

The implementation honours that literally. Distinct `return []` paths cover a missing
ledger file, absent `canonical_facts` / `fts_canonical_facts` tables, and
`sqlite3.OperationalError`. The live service runs with `OPENCLAW_PACKET_SOURCE=sqlite`
(drop-in `flip.conf` on `openclaw-request-response.service`), so this loader is the
production path.

**The defect is not the empty list. It is that empty is ambiguous.**
`[]` means both *"retrieval failed"* and *"there are no relevant facts."* The LM cannot
tell those apart, so it does the honest thing available to it and says `UNKNOWN`. The
agent is not lying; it is being lied to by its own retrieval layer.

This directly violates the standing rule that fallbacks must name the real failure.
A nice-sounding empty result is the same class of defect as a nice-sounding message.

### Repair

**R1.1 — make retrieval failure a value, not an absence.** The loader returns a result
object carrying `facts` plus `retrieval_status` ∈ `{OK, LEDGER_MISSING, TABLES_MISSING,
QUERY_FAILED, EMPTY_BY_QUERY}`. `EMPTY_BY_QUERY` is the only status where zero facts
means zero facts.

**R1.2 — surface the status in the packet, not just the log.** When status is not `OK`
or `EMPTY_BY_QUERY`, the packet carries a named retrieval failure and the answer must
render it: *"UNKNOWN — chief_status_rail selected, ledger unreadable (TABLES_MISSING)"*
rather than bare `UNKNOWN`. A refusal that names what it looked in is actionable; a
bare one is not.

**R1.3 — no silent `except`.** Every swallow logs the exception type and the resolved
ledger path. Currently a missing table and a locked database are indistinguishable in
the output.

**R1.4 — assert the contract at the seam.** If a packet declares a `source_ref` it must
carry at least one fact from that source, or a retrieval status explaining why not.
Naming a source you did not read is the packet-layer version of a receipt naming an
artifact that isn't there.

**Explicitly NOT in scope:** changing what the loader is allowed to read, widening
actor scope, or making failure fall back to the flat-file source. Fallback chaining is
how the ambiguity got here.

### Regression tests — `tests/test_packet_retrieval_status.py`

| Test | Asserts |
|---|---|
| `test_missing_ledger_reports_LEDGER_MISSING_not_empty` | status is named; `facts == []` alone never returned |
| `test_missing_tables_reports_TABLES_MISSING` | absent `canonical_facts` is distinguishable from an empty query |
| `test_operational_error_reports_QUERY_FAILED` | locked/corrupt db surfaces, does not vanish |
| `test_a_genuinely_empty_query_reports_EMPTY_BY_QUERY` | the one legitimate empty; **non-vacuity** — without it every test above passes trivially |
| `test_retrieval_failure_reaches_the_rendered_answer` | end-to-end: failure status appears in the answer text, not only the log |
| `test_a_declared_source_ref_carries_facts_or_a_reason` | R1.4 contract, over every source_ref in a built packet |
| `test_no_bare_except_returns_empty_in_the_loader` | AST scan: no `except` whose body is `return []` without recording a status |

**Mutation check (required before claiming this fixed):** revert R1.1 and confirm
tests 1–3 and 5 fail. If they still pass, they are testing the wrong thing — which is
exactly what happened to me earlier tonight on the SEND_HOLD ordering.

---

## SEAM 2 — agent identity on Telegram

### What was observed

Searching `Cassandra` in the macOS Telegram app matched a **real human contact named
Carter**, and the test message was sent there before correction. The agent's chat
header reads `Casandra bot` (one `s`) while the sidebar label reads `Cassandra`.

### Trace, read-only

- Six agents have distinct bot tokens by variable name — `MAESTRO_BOT_TOKEN`,
  `CASSANDRA_BOT_TOKEN`, `CHIEF_BOT_TOKEN`, `GUARDIAN_BOT_TOKEN`, `NILES_BOT_TOKEN`,
  `HERMES_BOT_TOKEN`. **Names only; no value was read and no secret file was opened.**
- A canonical mapping is specified: `agent_lanes.telegram_bot_username` and
  `agent_lanes.telegram_display_name`, with `@openclaw_cassandra_bot` asserted in
  `tests/test_t016_synthetic_e2e.py:26-28`.
- **I could not locate a production `CREATE TABLE agent_lanes`.** The contract appears
  to be test-fixture-only. Treat the registry as *specified but unproven in production*
  until someone shows the live table.
- Hermes' `channel_directory.json` lists exactly **one** Telegram target — the operator
  DM. The six agent bots are absent from the directory Hermes builds, so there is no
  runtime source of truth binding agent → chat.

**Root cause:** identity is resolved by *human search over display names* — a fuzzy,
collision-prone namespace shared with real contacts — because no machine-checkable
agent→chat binding is enforced at the surface.

### Repair

**R2.1 — make the registry real.** A production `agent_lanes` row per agent:
`agent_id`, `telegram_bot_username`, `telegram_display_name`, `chat_id`. Canonical,
one row per agent, no nulls.

**R2.2 — bind by username, never by display name.** Every outbound agent message
resolves its target through `telegram_bot_username`. Display names are cosmetic and
must never select a chat.

**R2.3 — refuse ambiguity.** If a target resolves to zero or more than one chat, or to
a chat whose username does not match the registry, **refuse and name it.** Do not pick
the best match. Best-match is what sent a message to Carter.

**R2.4 — identity banner.** Every agent turn is prefixed `AGENT / ROLE / @bot_username`
so the operator can see who they are talking to without trusting a sidebar label.

**R2.5 — reconcile display names.** `Casandra bot` vs `Cassandra` is a live mismatch
between the running bot and the intended registry. Correcting it is a **BotFather
change on the operator's own account** — his keyboard, not an agent's.

**R2.6 — gate the approval surface on identity.** Until R2.1–R2.4 pass, the draft
approval engine must not emit a preview containing a nonce over Telegram. A preview
that can land in the wrong chat is worse than no preview: it teaches the wrong human
what a valid approval looks like.

### Regression tests — `tests/test_agent_telegram_identity.py`

| Test | Asserts |
|---|---|
| `test_every_agent_has_exactly_one_registry_row` | six agents, no nulls, no duplicates |
| `test_targets_resolve_by_username_not_display_name` | renaming the display name does not change resolution |
| `test_an_ambiguous_target_is_refused_not_guessed` | two matches → refusal naming both; **the Carter regression** |
| `test_a_display_name_collision_with_a_human_contact_is_refused` | exact reproduction: a human contact whose name fuzzy-matches an agent |
| `test_username_mismatch_between_registry_and_chat_refuses` | catches `Casandra bot` vs `@openclaw_cassandra_bot` |
| `test_every_agent_turn_carries_the_identity_banner` | R2.4, over all six agents |
| `test_no_nonce_preview_is_emitted_while_identity_is_unproven` | R2.6 interlock, fail-closed |
| `test_resolution_succeeds_for_a_correctly_registered_agent` | **non-vacuity** — proves the resolver can say yes |

---

## Sequencing

1. **SEAM 2 first.** It is the only defect that has already reached a real person, and
   it gates whether the approval surface may be used at all.
2. **SEAM 1 second.** Without it every agent is honest and useless, which is safe but
   not a product.
3. Re-run the exact six-agent battery. Pass = 6/6 direct answers or correctly *named*
   `UNKNOWN`, 6/6 provenance, zero misroutes, zero gated actions, **twice, with no
   human relay.**

Routing (Cassandra/Chief) and persona dominance (Niles) are real and remain queued
behind these two; they are not traced here because the instruction scoped this to the
packet seam and the identity mapping.

---

*Read-only trace. No deploy, activation, restart, external send, gate change, or secret
access occurred. Bot token variable names were enumerated; no value was read.*

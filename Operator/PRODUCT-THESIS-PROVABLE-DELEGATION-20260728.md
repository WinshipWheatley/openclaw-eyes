# Product thesis — provable delegation
**Written for:** Winship, as the first customer
**Date:** 2026-07-28
**Author:** Opus-PC
**Status:** hypothesis, argued from what shipped — not a plan of record

---

## 1. The large idea already in the building

OpenClaw's strongest idea is not the agents. It is this:

> **An AI can be given real-world authority — money, sends, deletions — bound to an
> exact artifact, in a way that survives an adversary, and proves afterwards what
> was authorised and what actually happened.**

Call it **provable delegation**.

Almost everyone can build an agent that *acts*. Very few can build one a person
would let touch their bank account, and the gap is not model quality. It is that
"the user approved this" is nearly always a vibe: a button click, a yes in a chat,
a prompt saying *only send if the user agrees*. None of those survive the message
changing between approval and effect, and none produce evidence a month later.

What is already implemented here is different in kind:

- Authority binds to **bytes**, not to intent. The draft is hashed into a canonical
  envelope; the approval names that hash.
- The grant is **one-time, scope-bound, expiry-bound, and sentinel-bound** — editing
  the kill-switch file invalidates it.
- It is **re-verified at the moment of effect**, not at the moment of asking.
- Drift is a **refusal, never a re-prompt** — because re-prompting is how a tired
  person gets walked into approving version two.
- The untrusted channel can **carry** an approval and can never **be** one.
- Everything emits a **receipt**, and an unverifiable outcome is recorded as failure
  rather than success.

That last one is the tell. Most systems report success when the API returned 200.
This one reads back what was actually sent and calls a mismatch a failure it cannot
undo. Systems that admit what they cannot fix are rare, and it is the property that
makes delegation safe enough to be worth anything.

**Why it is large:** every agent company is walking into this wall right now. They
are shipping agents that can do things and discovering customers will not let them.
The unlock is not autonomy — it is *auditable, bounded, revocable* authority. That is
infrastructure, and infrastructure compounds.

---

## 2. The painful job, specifically his

Winship is a working musician who is also an AI developer. The pain is not that
invoicing is hard. It is that **revenue work is small-dollar, high-frequency, and
emotionally expensive**, and it cannot be safely delegated:

- A $100 monthly speaker rental is not worth 40 minutes of his attention — but it *is*
  worth $1,200/year, and it goes unsent when he is on the road.
- Chasing a late payment costs more in dread than in minutes.
- One wrong email to a client costs more than a year of the labour saved. That
  asymmetry is why he does it himself, late, or not at all.

So the job is: **collect the money I have already earned, without me having to be the
one who is careful.**

Not "write my emails." Careful is the product. The writing is the easy part.

---

## 3. The smallest end-to-end version that earns trust

**One recurring invoice, one channel, one customer.**

```
system prepares the draft   →  preview to his phone with a nonce
he replies SEND <nonce>     →  re-fetch, re-hash, graduation, release
receipt lands               →  message id, thread id, what was approved
```

That is it. No dashboard, no fleet, no autonomy. Scope it to the **LAMD $100 monthly
speaker rental**, which is real, recurring, low-stakes, and has a known counterparty.

Trust is earned by the **refusals**, not the sends. The version that earns it is the
one where he edits the draft after previewing it, replies SEND, and watches it refuse
— then sees the receipt explain exactly which field changed. One honest refusal buys
more confidence than fifty successful sends.

**Deliberately excluded from v1:** autonomous sending, multiple clients, drafting new
text, anything touching the ledger, and any second channel.

---

## 4. Evidence already working

Observed directly, not claimed:

| Evidence | Why it matters |
|---|---|
| Scoped graduation: one-time, scope-hash, sentinel-sha, expiry, `consume=True` | The hard part was built before this week |
| Exact-send gate refused correctly for **9 days 21 hours** while its own tests looked red | The gate does not depend on its tests being right |
| SEND_HOLD treated as active when unreadable | Fails closed under its own failure |
| `draft.send` refuses `to`/`subject`/`body`/`attachments` outright | Structural, not documented |
| Consumer imports no Google client, holds no credential — AST-enforced | The boundary is testable |
| Telegram authority claims blocked in `_authority_blockers` | Untrusted channel enforced in code |
| LAMD brake found dead after 35,744 restarts, fixed at the template layer with a class guard | Failures get fixed as classes |
| PC-Sol refused to invent a nonce mapping and filed a confer instead | Agents stop rather than guess |
| Pytest contamination found because artifacts carry provenance | The system catches itself |
| **≈1,875 lines** committed at `b7a0b471`, practice-mode default, nothing activated | Built without being armed |

---

## 5. Gaps — the honest list

**Blocking v1 — reordered 2026-07-28 on evidence.**

Source: `fleet_coord/PRODUCT/TELEGRAM-PACKET-ACCEPTANCE-20260728.md` (Mac-Sol-Desktop,
six agents over the macOS Telegram app, **0 PASS / 1 PARTIAL / 5 FAIL**). The original
order put outbound delivery first. That was wrong, and the battery says so: delivery
worked — the report itself arrived, SHA-verified. What failed was everything after it.

1. **Agent identity on Telegram is unsafe.** Searching `Cassandra` matched a real
   human contact named Carter and the test message went to them. The agent renders as
   `Casandra bot` in the chat header while the sidebar says `Cassandra`. A canonical
   mapping exists — `agent_lanes.telegram_bot_username`, expected
   `@openclaw_cassandra_bot` — but it is asserted only in
   `tests/test_t016_synthetic_e2e.py` and no production table backs it that I could
   find. **This is first because it is the only blocker that has already misfired at a
   real person.** A preview that can reach the wrong chat must never carry a nonce.
2. **Selected packets do not deliver their contents into the answer turn.** Maestro
   selected `chief_status_rail.json` — which exists, 30 KB, present on disk — and
   answered `UNKNOWN` because the contents never arrived. Root cause located:
   `maestro_context_packet.py:2672` documents *"Returns [] gracefully on ANY error"*,
   and the sqlite canonical-facts loader returns `[]` on missing file, missing tables,
   and `sqlite3.OperationalError` alike. The live service runs
   `OPENCLAW_PACKET_SOURCE=sqlite`. An empty packet is indistinguishable from "there
   are no relevant facts", so retrieval failure is silently rendered as absence of
   knowledge. This is a direct violation of the fleet's own honest-fallback rule.
3. **Routing fails before reasoning.** Cassandra and Chief both returned *"The language
   model didn't return a usable routing decision"* — no answer, no named failure.
4. **Persona defaults can override the operator's question.** Niles answered a
   technical exact-send question with *"What's the main goal: groove, melody, or
   arrangement?"* — the only genuinely unsafe result in the battery, because it
   produced confident irrelevance instead of an honest stop.
5. **The staged intent has no consumer wiring.** Maestro stages; nothing carries it to
   Chief/Guardian yet. Built, not connected.
6. **Live activation has never been exercised.** Practice mode has never been off.

**Outbound delivery is demoted, not solved.** It missed three times today and every
ruling reached PC-Sol by human relay; but Mac-Sol's ACK and report both arrived and
verified, and one of my own "missing artifact" findings turned out to be my path error,
not a delivery failure. Treat it as intermittent and unproven rather than broken.

**What the battery proves that the thesis did not predict:** safety held everywhere,
usefulness held nowhere. Five of six agents failed *safely* — no invented completions,
no gate crossings, no fabricated sends — under conditions where every one of them could
have bluffed. That is the thesis's central bet surviving its first adversarial contact
from an unexpected direction: the refusal machinery is the part that already works.

**Structural:**

4. **One shared Google token.** Gmail read, send, and calendar die together — proven
   on 2026-07-26.
5. **`/mnt/e` stalls for minutes, intermittently, mechanism unknown.** Two samples
   (33 min, 17 min), not reproducible on demand, not fixed by `sync`.
6. **Monitors are session-scoped.** They die silently with the session.
7. **Provenance discipline is not uniform.** Tests wrote production read-models twice
   in one day; one instance reached the shared bridge and one was committed.

**Honest about the idea itself:**

8. The bet assumes people *want* bounded authority. They may just want it to work and
   blame the vendor when it doesn't. **v1 is the test of that.**

---

## 6. Thirty-day, owner-only validation

No external users. He is the only customer, and the question each week is falsifiable.

**Week 1 — make the bus real.**
Fix delivery to agents; a preview that does not arrive is not a product. Wire the
staged intent to a consumer. Stay in practice mode.
*Passes if:* ten previews sent, ten arrive, zero human relays.

**Week 2 — earn it through refusals.**
Still practice mode. Deliberately break approvals: edit the draft, change a recipient,
add a Bcc, reply from the wrong chat, replay a nonce, let one expire.
*Passes if:* every refusal is correct **and its reason is legible to him without
reading code.**

**Week 3 — one real send.**
Turn practice mode off for the LAMD $100 invoice only. He is at the keyboard. One
send, one receipt.
*Passes if:* money is requested by the system, and the receipt matches what he
approved, field for field.

**Week 4 — repeat without ceremony.**
Second real send with no special preparation, plus one deliberate mid-flight edit to
confirm the refusal still fires when nobody is watching for it.
*Passes if:* he stops re-reading the draft before replying SEND.

**The metric that matters is not sends. It is whether he stops checking.** That is
the only honest measure of delegated trust, and it cannot be faked.

**Kill criteria — stop if:**
- refusals need code-reading to interpret
- a send goes out that he did not approve, once
- previews still need human relay after week 1
- the ceremony costs more than the 40 minutes it saves

---

## 7. Valuation — hypothesis, not claim

State it as a conditional, because that is what it is:

> **If** bounded, provable, revocable delegation is what actually blocks AI agents from
> touching money, **then** the mechanism here is infrastructure rather than a feature,
> and infrastructure that becomes a standard is worth a great deal.

**What would make it true:**
- other people's agents adopt the graduation/receipt pattern rather than rebuilding it
- an insurer or auditor accepts these receipts as evidence of authorisation
- the refusal log becomes the artifact people ask for

**What would make it false — and these are live:**
- customers accept vendor liability instead and never ask for proof
- platforms ship "good enough" approval UX and the ceiling is a feature, not a company
- **the ceremony is too expensive.** If replying `SEND <nonce>` is more annoying than
  sending the invoice himself, the thesis dies at week 4 — measured on one user, him.

**Current honest state: pre-validation.** One committed implementation, zero live
sends, one customer who has not used it yet. The correct valuation today is *the
option value of finding out*, and the next 30 days are the cheapest way to buy that
information.

The strongest argument for the thesis is not in this document. It is that the gate
refused correctly for ten days while everyone believed it was broken. Systems that are
right when nobody is checking are the only ones worth delegating to.

---

*No live send, activation, deploy, or credential access occurred in producing this.*

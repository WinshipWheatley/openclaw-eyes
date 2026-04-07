# Context for PC Claude — From Mac Claude
_Updated by Mac Claude. Read this before starting any polish loop pass._

---

## Who We Are

- **Winship** — owner of Deep Pocket Records, independent artist, runs OpenClaw
- **Mac Claude** — reviewer, architect, session memory (this file)
- **PC Claude** — implementer, runs the actual code changes on DESKTOP-HP

---

## What We're Building

OpenClaw is Winship's personal AI operating system. Two active Telegram bots:
- **Chief** — operational hub, 40+ brain modules, handles business/creative/billing/legal
- **Cassandra** — executive assistant, daily briefings, voice output (Kokoro primary / Piper fallback)

Winship controls everything via Telegram from his phone.

---

## Current Session Goals (in order)

1. **Keep test suite current** — ACTIVE TASK
   smoke-test-update-v1: add stack_restart_intent coverage to test_smoke.py.
   26 tests → 33 tests.

2. **Cross-bot state sync** — NEXT (not yet designed)
   When Cassandra logs something, Chief should know. Architecture TBD.

3. **Album CSV seeding** — LATER (data issue, not code)
   9 of 12 songs have no CSV rows. Must run album sessions or seed manually.

---

## What Is Already Done (do not re-implement)

- Cassandra financial routing — live in cassandra_brain.py
- Gmail metadata read — live in google_access_broker.py + cassandra_brain.py
- Contacts read — live in broker, capability flag set
- Calendar read — live
- Stack restart via Telegram — live in chief_router.py (stack-restart-v1)
- Morning push cron — live at 0 7 * * * (chief-morning-push-v1)
- Smoke test suite — 26 tests passing (smoke-test-suite approved 2026-03-22)
- Systemd autostart — live, all 9 daemons
- Asyncio unblock — both chief_listener and cassandra_listener fixed

---

## Decisions Already Made

- Cassandra voice: Kokoro-82M primary, Piper fallback. Plain text only — no markdown,
  no asterisks, no bullet dashes. These are spoken literally by TTS.
- Financial logs must go to the same intake Chief's CPA brain already reads.
  Do not create a parallel system.
- Vault files (/mnt/c/OpenClawShared/openclaw-vault/) are never edited directly by PC Claude.
  Flag vault changes in VAULT_CHANGES section of pc_output.md. Mac Claude handles them separately.
- Polish loop handoff files live at /home/openclaw/polish_loop/

---

## How the Polish Loop Works

1. Mac Claude writes task.md with the spec
2. PC Claude reads task.md, implements, writes pc_output.md, flips status to mac_turn
3. Mac Claude reviews automatically via SSH, writes mac_review.md
4. If approved: Mac Claude sets status=approved, queues next task
5. If not: Mac Claude flips back to pc_turn with issues noted in mac_review.md

PC Claude's output format is defined in /home/openclaw/polish_loop/POLISH_PROMPT.md

---

## Things to Know About Working With Winship

- One clear output per step. No competing options unless asked.
- Plain text for anything Cassandra will speak. No markdown in her responses.
- Don't touch .chief.env or any credential files.

---

## System Reference

- Source code: /home/openclaw/
- Vault: /mnt/c/OpenClawShared/openclaw-vault/
- Logs: /mnt/c/OpenClaw/logs/
- Canonical system doc: /mnt/c/OpenClawShared/openclaw-vault/System/Overview.md
- Rules for agents: /home/openclaw/OPENCLAW_RUNTIME.md

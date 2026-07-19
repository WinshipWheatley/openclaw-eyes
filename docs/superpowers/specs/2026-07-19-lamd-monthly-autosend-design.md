# LAMD Monthly Auto-Send and Operable Brake Design

Date: 2026-07-19
Mission: `LAMD-OPERABLE-BRAKE-AND-MONTHLY-AUTOSEND-PROOF`
Authority: operator grant relayed in `OPUS-ARM-LAMD-MONTHLY-AUTOSEND-20260718.md`, constrained by the five settled gates in `OPUS-ACK-SETTLE-FINAL-AUTOSEND-GATE-CONCEDED-20260718.md`.

## Fixed surface

Only `(client=live_arts_md, stream=speaker_rental)` may run unattended. Each cycle is the current calendar month, becomes eligible on day 16, is exactly USD 100.00, and targets `Accountant@liveartsmd.org`. The source package must identify the Speaker Rentals workbook/sheet, carry a finalized/validated PDF, and bind all artifact hashes. Any drift refuses before provider access.

The scheduler runs daily after the 16th so a machine-off miss can catch up within the same month. It never selects or sends a prior month. A brake refusal is a terminal attempt receipt, not a queued action; a later daily invocation is a fresh admission attempt. Once a monthly send claim exists, no automatic retry is permitted after any ambiguous or terminal outcome.

## Operable Linux brake

A root system service owns `/var/lib/openclaw-authority/lamd-autosend-brake.json` and `/run/openclaw-authority/lamd-autosend-brake.sock`. State uses `fleet_freeze_state_v1`: `PLANNED` is clear; `FROZEN` is tripped. Every write is atomic, root-owned, mode `0644` (world-readable status, never world-writable), generation-incremented, and records actor, reason, and UTC time. Read access is necessary because the provider process is unprivileged; the file contains no secret.

The broker admits:

- `status` from local clients;
- operator `trip` and `clear` only from a root peer, reached through `sudo`/PAM;
- Guardian `trip` only from the configured openclaw UID whose peer PID is in the exact `chief-guardian-listener.service` control group;
- no Guardian clear operation and no message/content command surface.

This prevents inbox/calendar/message payloads from becoming brake authority. The Guardian helper is a local callable only; it is not registered in any listener handler.

## Send transaction

The orchestrator performs:

1. eligibility, authority-config, operator-stop, package, amount, recipient, stream, service-month, and artifact-hash checks;
2. enabled `FreezeGuard` check against the installed root-owned state;
3. an atomic SQLite insert for unique `(live_arts_md, speaker_rental, YYYY-MM)`;
4. a second enabled `FreezeGuard` check immediately before the injected provider adapter;
5. exactly one provider call;
6. terminal classification: `SENT_VERIFIED`, `UNKNOWN_OUTCOME`, or `SEND_FAILED_NO_RETRY`;
7. after `SENT_VERIFIED`, an idempotent paired `issued` InvoiceRecord and `open` ExpectedReceivableRecord due on the send date;
8. `LEDGER_REPAIR_REQUIRED` if posting fails, without another send.

The live adapter must reuse the exact-send scoped SEND_HOLD graduation and broker rails. Tests use only a fake provider. No test may create a Gmail draft, call Gmail, move money, or mutate the live G2C store.

## Arming boundary

The timer and service ship disabled. The installer initializes a clear root-owned brake state and an unarmed root-owned scope config. Arming requires all unit tests plus an installed-path acceptance that shows clear state calls the fake provider once and tripped state calls it zero times with an honest refusal and no queued release. If root installation or either trusted trip path is unavailable, status is `UNARMED`.

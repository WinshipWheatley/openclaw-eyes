# Codex work packet — Maestro front-door: stop bypassing the brain + tell the truth in telemetry

**Owner:** Codex (code-heavy). **Reviewer:** Opus + operator live-check.
**Branch:** work on `codex/stress-fixes` (or a child branch off it); commit in small reviewable steps.
**Repo root:** `/home/openclaw` (WSL distro `Ubuntu-E`, the real OpenClaw stack).

## 0. HOW TO RUN THIS PACKET (read first — execution order + output protocol)

**Scope is CROSS-REPO.** This box has ~134 git repos (main `openclaw` + `sidecars/hermes` + `sidecars/gbrain_upstream` + `.openclaw/agents/*` state repos + `.nemoclaw/source` + 135 `worktrees/*` copies + embedded mirrors). The primary stack is `/home/openclaw`, but before concluding anything is "absent" or "the only copy," sweep the catalog `system_catalog.sqlite3` (tables `scans`,`repos`) and the relevant repos. Do NOT edit code inside `worktrees/*` (throwaway copies) or `sidecars/*` upstreams unless a section explicitly says so.

**Two modes — obey the label on each section:**
- **BUILD** sections (A, B, C, D, E, F, G, I): implement the fix. TDD (red→green) AND the non-snowglobe live verification in each section. Commit in small steps on `codex/stress-fixes`. Do NOT push unless the operator asks.
- **AUDIT-ONLY** section (H — Fin): investigate deeper and RETURN A RECOMMENDATION. **Build nothing, change no code.** We decide after, then send a final build prompt.

**Execution order (do in this order; each builds on the prior):**
1. **A — telemetry truth** (foundational: once the envelope mirrors the brain receipt, every later live-check is trustworthy; without this you're flying blind).
2. **B — status/capability questions route to the brain** (+ the doctrine-fact actor validator from H#5 can land here as a small guard).
3. **C — Hermes gateway crash-loop** (live outage; quick win; unblocks demoing D).
4. **G — Clara Reid / Cassandra persona reconciliation** (small, clarifies identity before deeper agent work).
5. **D — fleet no-response watchdog.**
6. **E — vision/image input** (Tesseract reuse first).
7. **F — check→books reasoning** (depends on E; honor the confirm-don't-assume rule).
8. **I — humor-as-health-signal gate** (depends on A — humor must read a truthful health receipt).
9. **H — Fin architecture AUDIT** (analysis only; recommend; build nothing).

**OUTPUT PROTOCOL (how to report back):**
- **To the operator, in the CLI:** a plain-English summary — what you did per section, what passed, what's blocked, and your Fin recommendation. Human-readable, no machine dumps.
- **Machine-readable results file:** write `/home/openclaw/Operator/CODEX-FLEET-WORK-RESULTS.md` with, per section: `status` (done/partial/blocked), `files_changed`, `commits` (sha + subject), `tests` (command + pass/fail counts), and the **non-snowglobe live verification output** (paste the before/after probe tables / the live reply text + the `protected_generate_audit.jsonl` correlation). For **H (Fin)**: the full audit findings, the recommendation (Option 1 vs Option 2), and open questions. The operator copies this file's contents back to the reviewing agent (Opus) for audit. Tell the operator that path in your CLI summary.

## The problem (observed LIVE, not in a test bubble)

Operator messages to Maestro go: Telegram → `maestro_listener` (writes a request file to
`/mnt/e/openclaw/mission_control_capture_requests/inbox`) → `openclaw_request_processor`
(the `openclaw-request-response` systemd service) → response file in
`/mnt/e/openclaw/mission_control_responses/to_mac` → listener relays it back.

I reproduced the live behavior by injecting real requests through the actual processor
(via `maestro_listener.build_operator_maestro_chat_request` + `write_bridge_request`) and
correlating with the brain's own audit log `/mnt/c/OpenClaw/logs/protected_generate_audit.jsonl`:

| Question | Delivered answer | Brain actually ran (audit) | Envelope `selected_model_backend` |
|---|---|:--:|:--:|
| "how is my week shaping up" | "you're in the thick of it, but things are holding steady" | YES | NONE_DETERMINISTIC |
| "tell me about Fin" | "Fin's got a tight leash — can't send money/emails/invoices on its own" | YES | NONE_DETERMINISTIC |
| "what can you help me with?" | "Here is the truthful readback from current generated state." | **NO** | NONE_DETERMINISTIC |
| "what's on my schedule today?" | "couldn't reach your calendar… re-run --auth" | NO | NONE_DETERMINISTIC |
| "are you using your brain?" | "I'm using both — my brain and a few well-tuned canned responses" | YES | NONE_DETERMINISTIC |

Two distinct, confirmed bugs:

### Bug A — telemetry lies about brain usage (observability)
`openclaw_request_processor.py` (~lines 1927–2002) builds `selected_model_backend` /
`model_selection_reason` / `machine_proof.model_call_performed` from an **agent→backend voice
map**, not from the actual `protected_generate` receipt. When the real brain receipt's backend
isn't threaded into `proof_response`, it falls through to:
`selected_model_backend = "NONE_DETERMINISTIC"`,
`"No live model backend selected; deterministic processor handled this response (<voice_reason>)."`
**Result: every response — even ones the brain genuinely answered — reports `NONE_DETERMINISTIC`
and `model_call_performed=False`.** This made the response receipts untrustworthy and caused a
wrong "the brain isn't engaging" diagnosis. Ground truth only lived in
`protected_generate_audit.jsonl`.

### Bug B — capability/status questions bypass the brain (UX)
`maestro_cassandra_responder.py`:
- `classify_frontdoor_intent(text)` (~line 263) → `_is_status_capability_intent(normalized)`
  (~line 288) returns intent `status_capability_readback` (~line 289).
- That intent routes to `build_truthful_status_capability_answer(...)` (~lines 459–462, defined
  ~956), a **deterministic readback that never calls the brain**, and the operator gets a canned
  placeholder ("Here is the truthful readback from current generated state.") instead of a real
  answer. This classifier is keyword-brittle: "what can you help me with?" and capability-phrased
  questions get hijacked, while near-identical conversational phrasings ("tell me about Fin") reach
  the brain. The operator experienced this as Maestro "not answering."

## Fix goals

**Bug A (fix first — it's the observability you need to trust everything else):**
- Thread the real brain receipt into the response envelope. When `protected_generate` (via
  `maestro_cassandra_responder._answer_with_maestro_brain`) actually invoked the model, the
  response's `selected_model_backend` must reflect it (e.g. `LOCAL_OLLAMA` + the model id like
  `qwen3:8b-q4_K_M`), `model_selection_reason` must say the brain answered, and
  `machine_proof.model_call_performed` must be `True` with `route` (e.g. `local_ollama_frontdoor`).
- When the response really was deterministic (no model call), keep the honest deterministic
  labeling. The field must become a faithful mirror of the brain receipt, not a guess from the
  voice map.
- Trace where the brain receipt's `model_call_performed` / `route` / model id are available in the
  processor (the brain card / `machine_proof` produced by `maestro_cassandra_responder`) and plumb
  them into the `proof_response` that lines 1927–2002 read.

**Bug B (the real UX fix):**
- Stop emitting a placeholder readback for conversational capability/status questions. Preferred
  approach: route `status_capability_readback`-class questions **through the brain** with the
  capability/status facts injected into the context packet (reuse
  `build_truthful_status_capability_answer`'s data source — the capability index read-model — but
  as *packet facts the brain answers from*, not as a canned string). The operator should get a
  real, conversational, grounded answer ("Here's what I can actually do for you right now: …"),
  not a placeholder.
- Tighten `_is_status_capability_intent` so genuine conversation isn't hijacked; only route to a
  deterministic path if there's a real reason, and if so the deterministic answer must contain the
  ACTUAL capability content (never the bare "Here is the truthful readback…" placeholder).
- Do **not** change the deterministic safety routing for `send_reply_email_action`,
  `workflow_or_business_action`, `calendar_or_briefing`, `operator_truth_correction/query` — those
  intentionally stage/gate and must stay deterministic + fail-closed.

## Hard constraints (do not regress)
- Grounding + fail-closed stays intact: the brain must not invent facts; when no packet fact
  supports an answer it still says so (the existing protected_generate grounding contract).
- Graded PII tokenization through `protected_generate` is preserved (no raw PII to the model
  beyond current policy).
- SEND_HOLD / money / external-send authority stays ungranted and deterministic.
- Per-agent aware, NOT a Maestro snowglobe: the routing + telemetry fixes must hold for the other
  agents that share this front-door (Cassandra/Niles/Chief/Hermes/Guardian), not just Maestro.
- No new always-on external/cloud model calls; local ollama brain only.

## NON-SNOWGLOBE acceptance gate (required — unit tests alone are NOT sufficient)
A green unit test does not prove the live pipeline changed. You MUST verify through the real
processor:

1. Unit tests (TDD) for both fixes in `tests/` (intent routing → brain; telemetry mirrors the
   brain receipt). Red first, then green.
2. **Live processor proof.** Restart the service after the change
   (`systemctl --user restart openclaw-request-response`), then inject the SAME 5 probe questions
   through the real path and show the new behavior:
   ```
   python: maestro_listener.build_operator_maestro_chat_request(q, message_id=…, chat_id=authorized_user_id())
           maestro_listener.write_bridge_request(req)
           # poll /mnt/e/openclaw/mission_control_responses/to_mac/openclaw_response_for_mac_<request_id>.json
   ```
   Acceptance:
   - "what can you help me with?" now returns a real capability answer AND
     `protected_generate_audit.jsonl` shows `model_call_performed=True` for it (brain ran), OR a
     deterministic answer that contains the actual capabilities (no placeholder).
   - For every brain-answered probe, the response envelope's `selected_model_backend` is the real
     backend (e.g. `LOCAL_OLLAMA`/model id) and `machine_proof.model_call_performed=True` — i.e.
     the envelope now AGREES with `protected_generate_audit.jsonl`.
   - The deterministic-by-design intents (calendar/send/workflow) still route deterministically.
   - Paste the before/after live probe table in the PR description.

## Deliverables
- Small, reviewable commits on `codex/stress-fixes` (Bug A and Bug B separable).
- New/updated unit tests (TDD).
- The live before/after probe table (the non-snowglobe proof) in the PR/commit body.
- Note any file you touched that is gitignored runtime (none of the above core files are gitignored
  — `maestro_cassandra_responder.py` and `openclaw_request_processor.py` are tracked).

## Key files
- `maestro_cassandra_responder.py` — `classify_frontdoor_intent`, `_is_status_capability_intent`,
  `build_truthful_status_capability_answer`, `_answer_with_maestro_brain`.
- `openclaw_request_processor.py` — backend/telemetry mapping ~1927–2002; brain/CHAT response
  assembly ~1077–1205.
- `protected_generate.py` — the brain receipt (`model_call_performed`, `route`, model id) source.
- `maestro_listener.py` — `build_operator_maestro_chat_request` / `write_bridge_request` (the live
  injection harness for the acceptance gate).


---

# ADDENDUM — additional fleet issues (investigated live, 2026-06-29)

---

# ADDENDUM — Findings C/D/E/F (append to CODEX-MAESTRO-BRAIN-ROUTING-FIX.md)

This addendum extends the existing packet (Bug A: telemetry-mislabel; Bug B: status-capability readback bypasses the brain) with four investigated areas. Each is reuse-first: it wires or unblocks subsystems that already exist on this box rather than building new infra.

## Build order and why

Two dependency chains, ordered fastest-unblock → foundational → capstone:

1. **C — Hermes gateway crash-loop** first. It is a live 7-day outage with a one-line unblock, restores a real chat surface, and becomes the concrete down→up fixture the no-response heal needs to prove itself.
2. **D — Fleet no-response self-heal** second. The watchdog can only be demoed non-snowglobe against a *real* silent agent; Hermes (silent while flapping, quiet once C lands) is exactly that fixture. It also reuses Hermes' loop spine.
3. **E — Vision/image input** third. It is the foundational input rail; **vision-input must land before check-reasoning is useful** (an image's vendor/amount/date has to arrive somehow). The interim `operator_note` path lets E and F overlap, but E should land first so F has real input.
4. **F — Check-image → books reasoning** last. It is the capstone that joins four existing islands and depends on E for the live image→fields step.

---

## C/D/E/F — C: Hermes is offline on Telegram (gateway crash-looping on a stale PID lock)

**Observed symptom (operator's words):** "I text Hermes and get nothing back — Hermes has been dark for days."

**Current state (grounded):**
- Hermes is not a `*_listener.py`; it runs as its own sidecar gateway under `/home/openclaw/sidecars/hermes/`, launched by `hermes-gateway.service` (enabled, PartOf openclaw-stack.target). The OpenClaw truthfulness gate is layered on via `openclaw_hermes_gateway_policy.py` monkeypatching `GatewayRunner._handle_message` (lines 208-250). `hermes_observer.py` is a separate fleet-watch loop, not the chat surface.
- `systemctl --user is-active hermes-gateway.service` = `activating` (auto-restart); journal: "restart counter is at 3386" (~7 days flapping). No live Hermes process exists.
- Token/config are fine: ExecCondition passes (status=0), `sidecars/hermes_home/logs/gateway.out` prints "Hermes Gateway Starting…" each cycle. The ONLY error every restart: `ERROR gateway.run: PID file race lost to another gateway instance. Exiting.` → exit 1 → `Restart=on-failure` loop. `gateway.out` is now 128 MB.
- Blocking artifact: `/home/openclaw/sidecars/hermes_home/gateway.pid` (mtime 2026-06-22, contains `{"pid": 5285,…}`). PID 5285 is dead (`kill -0 5285` → no such process). `HERMES_HOME` resolves `_get_pid_path()` to exactly this file.

**Root cause / gap:** A logic conflict in `sidecars/hermes/gateway/status.py`. Boot in `gateway/run.py:11261` calls `get_running_pid()` (status.py:575); the dead PID triggers `_cleanup_invalid_pid_path(cleanup_stale=True)` (status.py:600→215), which delegates the delete to `remove_pid_file()` (status.py:300-319). But `remove_pid_file()` has an atexit ownership guard — `if file_pid is not None and file_pid != os.getpid(): return` — so it **refuses to unlink a foreign-PID file**. A stale file *by definition* has a foreign dead PID, so the guard always blocks cleanup. The file survives; `--replace` termination (run.py:11262-11346) is skipped ("no instance to replace"); then `write_pid_file()`'s `os.open(O_CREAT|O_EXCL)` (status.py:227) hits `FileExistsError` → "PID race lost" → exit 1 → repeat forever. The guard is correct for atexit handoff, wrong as the stale-cleanup mechanism.

**Fix spec for Codex (reuse-first, no new infra):**
- **A) Immediate unblock (OS-state, one-time, operator/Codex):** `rm -f /home/openclaw/sidecars/hermes_home/gateway.pid`, `: > /home/openclaw/sidecars/hermes_home/logs/gateway.out`, `systemctl --user restart hermes-gateway.service`. The next start wins the `O_EXCL` race and opens polling. **Governance:** `/home/openclaw/.claude/commands/hermes.md` (lines 32, 80, 127) says to leave a crash-looping gateway stopped — so bringing Hermes **online is an explicit operator GO**, not a silent action.
- **B) Durable code fix in `sidecars/hermes/gateway/status.py`:**
  - Add `force: bool = False` to `remove_pid_file()` that bypasses the `file_pid != os.getpid()` guard when True; have `_cleanup_invalid_pid_path()` (215-224) call `remove_pid_file(force=True)` (it only runs after the record is already proven dead). Keep default `force=False` for the `atexit.register(remove_pid_file)` path (run.py:11476) so handoff safety is preserved.
  - Belt-and-suspenders in `write_pid_file()` (227-249): on `FileExistsError`, re-call `get_running_pid()`; if None (stale), `os.unlink(path)` and retry `O_CREAT|O_EXCL` **exactly once**; if a live PID is found, re-raise so a genuine concurrent `--replace` still loses. Reuse `get_running_pid`/`_read_pid_record`/`_looks_like_gateway_process`.
  - After B lands, update `hermes.md` to note the crash loop was a stale-PID bug (now fixed), so the "leave it stopped" guidance isn't applied to a healthy gateway.

**Hard constraints:** Per-agent surface — this is Hermes' own gateway, not the Maestro snowglobe. Billing-safe: the unit already sets `HERMES_OPENCLAW_DISABLE_EXTERNAL_FALLBACK=1`; confirm `config.yaml` providers point only to local ollama (aux `qwen3:4b`) before it serves traffic — **no postpaid path reachable**. Money/send stays Guardian-gated through the existing policy patch. Bringing it online requires the explicit operator GO above.

**Non-snowglobe verification:**
1. After unblock: `systemctl --user is-active hermes-gateway.service` → `active` and **steady** (restart counter stops climbing); `journalctl --user -u hermes-gateway.service -n 30` shows no more "PID file race"/"Exiting"; `gateway.out` shows the Telegram adapter connected/polling. Exactly one process: `ps -eo pid,cmd | grep run_openclaw_hermes_gateway` → one PID, and `cat sidecars/hermes_home/gateway.pid` holds that live PID.
2. **Live round-trip:** text Hermes on `TELEGRAM_HOME_CHANNEL 8615325274`; confirm a reply arrives (exercises `_handle_message` through the truthfulness patch end-to-end).
3. Regression test (so it can't recur): in a temp `HERMES_HOME`, write `gateway.pid` with a known-dead PID; assert `get_running_pid()` returns None AND the file is gone, then `write_pid_file()` succeeds with no `FileExistsError`. Land alongside `tests/test_openclaw_hermes_sidecar.py` and the sidecars gateway suite.

*Open: why did 5285 die without atexit cleanup on 2026-06-22 (SIGKILL? reboot? the very `--replace` race the comment warns of)? A quick look prevents the orphan recurring before B lands.*

---

## C/D/E/F — D: Fleet no-response self-heal (texted an agent, got silence, nothing notices)

**Observed symptom (operator's words):** "I messaged an agent and never heard back — and nothing in the system flagged that the agent went dark."

**Current state (grounded):** Every self-heal loop grades an OUTPUT the agent emits while running — none detect the ABSENCE of output.
- `chief_watcher_brain.py` (chief-watcher-brain.service, active) only watches finance/album state: billing CSV (`find_billing_alerts` 115-151), album CSV (`find_album_alerts` 208-220), re-send stuck approval (`check_once` 307-358). No liveness logic.
- `hermes_observer.py` `DEFAULT_OBSERVERS` (112-115) = `_brain_quality_observer` (75-85) + `_fleet_health_observer` (88-109, reads `sync_health.json status`). Neither detects "sent but no response." Its routing spine IS reusable: `authorize_route` (52-68, Chief vs Guardian via real `openclaw_hermes_gateway_policy`), `route_to_chief` (160-193), `run_hermes_fleet_loop` (223-320, file-once lifecycle). Cron `30 */3 * * *`.
- `self_monitor.py` reads `protected_generate_audit.jsonl` for latency + `deterministic_fallback_used` rate only (41-92) — i.e. only when the brain DID run. `autonomous_self_check.py` files those gaps with full lifecycle but is **not on cron**. Neither covers liveness.
- `generated/read_models/agent_presence.json` is rich per-agent (actual_state, last_seen_at, blocker, `recovery_actions` carrying exact `systemctl --user start …` argv) but **stale/unreliable as a trigger**: last_seen_at = 2026-06-17 (12 days old) and it reports hermes `online` while the gateway crash-loops. `sync_health.json` is PC-file-mirror health, not agent liveness.
- The bus is fully file-based and live: requests `/mnt/e/openclaw/mission_control_capture_requests/inbox/mission_control_*request*.json` (216 files; envelope carries `lane`, `request_id`, `source_request_id`, `created_at`, `operator_message`); responses `/mnt/e/openclaw/mission_control_responses/to_mac/openclaw_response_for_mac_*.json` (each with `source_request_filename`+`source_request_id`+`internal_status`); a `processing` marker; a join index `response_manifest.json`. `openclaw_request_processor.py` only writes a `service_failed_*` / `FAILED_WITH_REASON` response when the service is RUNNING and catches an exception. When a listener/processor is DOWN, the request sits in the inbox with no marker and no response — pure undetected silence.

**Root cause / gap:** A no-response is the absence of a receipt; no observer is positioned to see it. There is no detector that **joins the deposited-request bus against the published-response bus** and flags any request older than timeout T whose `source_request_filename` appears in NO response and has no processing marker — fleet-wide, attributed per agent via the request `lane`. There is no diagnosis step (systemctl probe / last `service_failed` exception / `recovery_actions`), and no wiring into the self-heal loop. The one liveness read-model is too stale to be the trigger.

**Fix spec for Codex (reuse the existing loop; build nothing in the factory):**
1. New module `no_response_watchdog.py` (sibling of `hermes_observer.py`), `no_response_observer() -> list[dict]` matching the observer contract `{id, problem, evidence, build_goal, severity, source}`:
   - Read inbox (default `/mnt/e/openclaw/mission_control_capture_requests/inbox`, injectable for tests) for `mission_control_*request*.json`; parse `created_at`, `lane`, `request_id`, `source_request_id`.
   - Build answered-set from `response_manifest.json` + the `to_mac` dir. **JOIN BY FIELD** (`source_request_filename`/stem), NOT by inbox membership — requests stay in the inbox after being answered (telegram_594, telegram_102 verified present despite having responses; `_archive` is not reliable drainage).
   - A request is "silent" if `now - created_at > T` (e.g. 180s) AND no response AND no processing marker. Group by `lane`→agent.
   - Diagnose per agent (read-only): `systemctl --user is-active <service>` for the lane's service; read `agent_presence.json` `recovery_actions`/`blocker`; if a `service_failed` response exists, pull `why_it_happened`. Emit one suggestion per affected agent, severity high (e.g. id `no_response_<agent>`, evidence = "<n> requests to <agent> (lane <lane>) unanswered >Ts; oldest <id> at <created_at>; is-active=<state>; last service_failed: <exception|none>").
2. Register it: append `no_response_observer` to `hermes_observer.DEFAULT_OBSERVERS` (line 112). That one change inherits routing + Chief/Guardian authorization + file-once/retry/auto-close + Guardian gating via `run_hermes_fleet_loop → route_to_chief → self_improvement_request._default_file_fn → admit_with_safety_check`.
3. **Required companion edit:** add a package profile for the new gap id(s) to `_SELF_IMPROVEMENT_PACKAGE_PROFILES` in `self_improvement_request.py` (130-230) — `compile_self_improvement_package` (255-267) rejects unknown ids by design (`SelfImprovementPackageError`). Bound `allowed_files` (watchdog module + tests + the relevant listener/processor) and `tests_to_run`. For pure process-down, phrase `build_goal` as restart/recover so `_touches_privileged_domain` routes to Guardian (systemd edits are in `_COMMON_FORBIDDEN_ACTIONS`; `autorecovery_allowed=false`).
4. Scheduling: cron `no_response_watchdog`/hermes_observer at ~10-15 min (tighter than 3h) AND install `autonomous_self_check.py` to cron (currently absent). **Do NOT auto-restart services.** Reuse `_ensure_chief_env()` (self_improvement_request.py:35) so the Guardian send works from cron.

Do NOT modify the factory, `openclaw_request_processor`, or any systemd unit.

**Hard constraints:** Detection only — the watchdog **never auto-restarts**; a down service is a privileged restart that `authorize_route` sends to Guardian (operator restarts). Per-agent attribution via `lane`, not a Maestro-only view. Grounding intact: every suggestion's evidence is a real bus join + a live systemctl probe, never invented. No model is held alive to poll — it runs on cron and exits.

**Non-snowglobe verification:**
1. Integration: `tests/test_no_response_watchdog.py` with temp inbox + temp to_mac. Old `created_at`, no matching response → one suggestion for that lane's agent. Add a matching response → returns `[]`. Add only a `processing` marker → does NOT fire.
2. Loop wiring: `hermes_observer.run_hermes_fleet_loop(observers=(no_response_observer,), file_fn=<stub>, …)` → stub receives the suggestion; receipt is route=chief filed (or route=guardian for a restart-phrased goal) — proving authorization + file-once + Guardian gate with no factory change.
3. **Real-bus ground truth (read-only):** run against LIVE dirs. `telegram_594` HAS a `service_failed` response → must NOT fire (it got a reply, even a failure one). A live request with no response → must fire. With C still pending, `systemctl --user is-active hermes-gateway.service` = `activating` → the diagnosis step must surface that as the cause for any unanswered Hermes-lane request. After C lands and Hermes drains its inbox, the watchdog must go quiet — the live down→up demo.
4. Factory (gated): with the profile added, `_default_file_fn` against a test ledger → a PROPOSED task + Guardian BUILDOK/BUILDNO — filed Guardian-gated, never auto-built.

*Open: confirm whether non-Maestro agents' inbound lands in this same inbox (every live request seen is `lane=telegram_pc_maestro_listener`) or per-agent surfaces — if the latter, the watchdog needs a lane→service map (`DEFAULT_AGENT_LANE_SEEDS` in `canonical_doctrine_facts.py` is a candidate). Per-request-type timeout T (a WORKFLOW_PACKAGE build legitimately exceeds a CHAT). Treat the systemctl probe as authoritative, `agent_presence.json` as context only.*

---

## C/D/E/F — E: Vision/image input — a photo (e.g. a check screenshot) goes nowhere

**Observed symptom (operator's words):** "I sent a photo of a check to an agent and got dead silence — read the picture."

**Current state (grounded):** The stack is **end-to-end text-only for images**; a photo matches no handler and is silently dropped.
- **Listeners:** `maestro_listener.py:587` registers ONLY `MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)`; `handle_message` (520-521) hard-returns `if not update.message or not update.message.text`. `cassandra_listener.py:675-676` registers TEXT + VOICE only — but its `handle_voice` (593) is the reusable download pattern: `voice_file = await update.message.voice.get_file()` then `download_to_drive(ogg_path)` (616-617) → transcribe → feed text into intake. `producer_listener.py:101-102` = TEXT + COMMAND. **No `filters.PHOTO`/`filters.Document` handler exists anywhere in the repo** (only matches are inside the bundled telegram lib under `.cache`).
- **Models (`chief_llm.py`, no multimodal):** `nemotron_call` (258) and `openrouter_call` (307) both send `"messages":[{"role":"user","content":<plain string>}]` (269, 335) — no image content blocks. Local ollama payload (994-1036) is `{"model","prompt","stream":False}` — no `images:[base64]` array. `select_frontdoor_model` ladder (750) is text names only. `ollama list` = 14 models, **all text-only** (no llava/llama3.2-vision/qwen2.5-vl/moondream).
- **Processor "image" refs are NOT vision input:** `image_pixels` is in `RAW_BODY_KEYS` (openclaw_request_processor.py:518, a value that gets REDACTED); `IMAGE_MODEL_CLOUD_GATED` (2310) is about image *generation* blocked; `live_attachment_allowed: False` (478) is a default-off gate.
- **Reusable OCR already works on this box:** `oclaw_doctools.py:45 ocr_image(image_path)` shells `tesseract` (`/usr/bin/tesseract`, confirmed installed; pdftotext + ffmpeg + PIL present). `legal_process.py:156 process_ocr()` already routes an image → `ocr_image` → text — but wired ONLY into legal evidence, never the chat front door.
- **Mac path:** `openclaw_chat_request_processor.py` FILE_METADATA_REQUEST (509) returns "File reference captured … body was not read" (528), how_to_fix = "request governed extraction when that rail exists" (535) — a rail never built. `operator_file_metadata_intake` stores only size/extension/hash/label, never bytes (`live_file_body_ingestion_allowed: False`).

**Root cause / gap:** Four independent gaps: (1) no `filters.PHOTO`/`filters.Document.IMAGE` handler on any listener, and text handlers early-return on empty `update.message.text` — image updates never enter intake. (2) `chief_llm` providers hardcode text `content` and the ollama payload omits `images`, so even an existing vision model is unreachable. (3) no vision model pulled; OpenRouter vision content-array shape not built. (4) the attachment/file-body rail is intentionally default-OFF and the promised "governed extraction rail" was never built, while working Tesseract OCR stayed siloed in legal.

**Fix spec for Codex (reuse-first, three phases — prefer the $0 local Tesseract path that already works):**
- **Phase 1 — receive + store (clone the voice handler):** add `app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_photo))` next to `cassandra_listener.py:675-676` (replicate to `maestro_listener.py:587` etc). `handle_photo` mirrors `handle_voice` (593-621): `f = await update.message.photo[-1].get_file()` (or `update.message.document.get_file()`), `await f.download_to_drive(path)` into a per-request dir, sha256 the bytes, capture `update.message.caption`. Feed through the SAME request builder used for text, adding an attachment ref `{local_path, sha256, mime, caption}` — analogous to how voice injects its transcript.
- **Phase 2 — extract (reuse OCR; default-ON, $0):** default = `oclaw_doctools.ocr_image(path)` (same call `legal_process.process_ocr:159` uses) → route "OCR text + caption" into the existing text brain (`maestro_context_packet → protected_generate / responder`). For a check, the existing finance intent (`business_ops_intent`/`ar_invoice_record`) can pull vendor/amount/date. No new model, no gate, no spend. **Optional better-vision (local first, $0 floor, preferred):** `ollama pull llama3.2-vision` (or qwen2.5vl); add an `images:[base64]` branch to the ollama payload (chief_llm 994-1036) and a vision lane in `select_frontdoor_model` (750). **Prepaid OpenRouter vision fallback (capped, gated):** extend `openrouter_call` (307) to send the content-array `[{type:text},{type:image_url,image_url:{url:"data:image/jpeg;base64,…"}}]` to a vision model, ONLY when `external_model_packet_policy` passes (sanitized + cloud_allowed + Guardian) AND a prepaid key with a per-key cap is set — fail-closed back to local Tesseract.
- **Phase 3 — deferred "noted, will reprocess":** when no extractor is available, reuse `operator_file_metadata_intake` to store path+sha256, reply "image received — I can't read it yet, I'll reprocess when vision is on," write a pending marker keyed by `source_ref_id`. A small cron worker (niles/chief worker pattern) drains pending markers once OCR/vision is enabled — converting today's dead-end into a real deferred queue.

**Hard constraints:** **Local-ollama-vision first** (and Tesseract OCR is the $0 default that already works); **prepaid OpenRouter vision only as a capped fallback gated by `external_model_packet_policy` + Guardian — NEVER postpaid**; fail-closed to the local path on exhaustion. Per-agent (the handler lands on each listener, not a Maestro-only inlet). Grounding intact — OCR/vision text is fed verbatim into the existing packet, the model is not asked to guess. No money moves and nothing is sent from reading an image.

**Non-snowglobe verification (real pipeline, not a unit test):**
0. Standalone sanity that OCR works here today: `python3 -c "import oclaw_doctools; print(oclaw_doctools.ocr_image('<check.png>'))"` returns the check text (tesseract installed).
1. **Send a real check screenshot to the live Maestro/Cassandra bot.** Confirm: the listener downloads it (a file lands in the request dir, its sha256 logged), the envelope carries the attachment ref + OCR text, and the agent's REPLY names the vendor / amount / date matching the actual check.
2. If vision is off, confirm the deferred reply + a pending marker that the cron worker later drains into an extraction.
3. Watch live: `journalctl --user -u cassandra-listener -u openclaw-request-response -f` while sending.

*Open: which agent owns check/finance photos (Cassandra vs Chief vs a finance lane)? Confirm a prepaid+capped OpenRouter key exists before enabling hosted vision — else stay local-Tesseract-only. A local vision model (~7-8GB) must fit the ~16GB box alongside the text ladder without re-triggering the known shared-lane timeout/recitation issue.*

---

## C/D/E/F — F: Check-image → books reasoning (vendor+amount+date → match amount due → "did you deposit it?" → bank ledger + tax item → tag to gig & Reynolds Tavern)

**Observed symptom (operator's words):** "When I show you a check, recognize who paid me and how much, match it to what that gig owed me on the books, ask if I deposited it, and once I say yes, expect it in the bank and log it as a tax item — and tag the check to the Reynolds Tavern gig."

**Current state (grounded):** Four reusable subsystems exist; they are NOT connected.
- **(1) G2C domain (built+tested, UNWIRED, empty on disk):** `ar_gig_record.py` (GigRecord), `ar_invoice_record.py` (InvoiceRecord: total_minor_units/currency_iso/due_date_iso/lifecycle draft|approved|issued|voided), `ar_expected_receivable_record.py` (ExpectedReceivableRecord: expected_minor_units/lifecycle open|disputed|satisfied|written_off|cancelled + resolution_ref on terminal states, lines 5-11,18-29,56-58), `ar_work_session_record.py`. Store `ar_gig_to_cash_store.py` — append-only versioned SQLite, `append/get_current/list_history/supersede`; `DEFAULT_DB_PATH=/home/openclaw/state/gig_to_cash/gig_to_cash.sqlite3` (line 26); `supersede()` flips a receivable open→satisfied with resolution_ref (764-779). `command grep` for the store finds ONLY its own files — no live importer; **the DB does not exist on disk** (zero ExpectedReceivable rows — no "amount due" physically exists). `gig_intake.py` (Reynolds-aware, hardcodes "Reynolds Tavern"/"7 Church Circle, Annapolis, MD" 209-222) records to `business_ops_ledger`, NOT the G2C store.
- **(2) Evidence/artifact tagging (built+LIVE — the real image-drop path):** `evidence_intake.py` imported live by `openclaw_request_processor.py:34`, `openclaw_request_router.py:20`, `operator_controller_event_router.py`. Accepts `VERIFIED_EVIDENCE_INTAKE_REQUEST_V0`, classifies payment screenshots financial_sensitive/local_only/external-blocked (`classify_privacy` 466-495), detects invoice ref by regex (`_detect_invoice_ref` 429-435), classifies a payment_state, TAGS via current_world_ref/current_thread_ref/claimed_client_ref/claimed_workflow_ref (630-712) → `evidence_intake.sqlite` + `artifact_lineage_registry.sqlite` (748-911). Does **NO** ledger mutation / NO paid marking (AUTHORITY_BOUNDARY 92-109). Deposit lifecycle already exists: `PAYMENT_PROOF_STATES` payment_proof_candidate → payment_processing_evidence_received → payment_arrival_expected → payment_arrived_unverified → ledger_recording_pending_operator_review → ledger_recorded → rejected_or_test (59-67). `niles_album_evidence_intake_boundary.py` is the entity-scoped precedent (album-only).
- **(3) Finance read-models + live reasoning:** `finance_thread_index.json` (capital_hilton/live_arts_md/st_annes, world=finance), `finance_invoice_reconciliation.json` (a CODE-INVENTORY triage model, not a live matcher), `reynolds_gig_setup_status.json` (gig_ref reynolds_tavern_2026_06_27, contact Sally). Live reasoning is in `cassandra_brain.py`: `_detect_payment_verify_intent` (2713), `_handle_payment_verification_request` (2721, checks Gmail + `chief_cpa_brain.get_recent_income` 2740-2750), `_looks_like_operator_financial_event` ("i deposited" 2798-2819), `_fetch_payment_verify_context` (5456), income capture (~1891). None consult the ExpectedReceivable store or the evidence artifact.
- **(4) Tax-item logging (built, wired):** `chief_cpa_brain.py` — `log_entry(amount, description, category, entry_type='income'|'expense')` (207), `get_recent_income(days)` (234), `find_duplicate_today(amount)` (246), schedule_c_gross/1099-NEC/quarterly (40-115,300-312). Source of truth `/mnt/c/OpenClawShared/business/expense_log.json` (31). Referenced by `operator_universal_intake.py` (957-1003,1246-1248) and `cassandra_brain.py`.

Image understanding itself is **E's** job; here vendor/amount/date arrives via `operator_note` or a future vision step.

**Root cause / gap:** G2C was built spec-first but never wired/seeded, so the typed "books" layer (ExpectedReceivable = amount due) is dormant and its DB doesn't exist. Live payment reasoning grew separately in cassandra_brain/chief_cpa_brain against `expense_log.json` + Gmail; evidence_intake grew as a standalone recorder. No bridge joins a tagged evidence artifact → the receivable books → the CPA/tax log. Specifically missing: (1) evidence-artifact→receivable match (the regex invoice ref is never looked up; check amount never compared to `expected_minor_units`); (2) the books to match against (empty DB); (3) the open→satisfied transition driven from a payment signal; (4) the "did you deposit it?" driver; (5) deposit-confirmed→tax-item bridge with provenance; (6) a gig/vendor-scoped tag on the artifact (evidence tags thread/client/workflow, not gig_id/receivable_id). The deliberate authority boundaries (evidence_intake never mutates ledger; G2C is pure local persistence) are correct and must be preserved — the missing piece is an operator-confirmed, Guardian-gated reasoning bridge, not a loosening.

**Fix spec for Codex (ONE new module `check_evidence_books_bridge.py`, records/reasoning only; never sends/moves money; write no new persistence engine):**
- **A) Seed the books (prerequisite):** a small seeder (or extend `gig_intake.emit_gig_handoff_packets`) that from confirmed `gig_intake` fields calls `create_gig_record → create_invoice_record(lifecycle="approved", total_minor_units, currency_iso, due_date_iso) → create_expected_receivable(invoice_id, invoice_version_id, counterparty_ref="reynolds_tavern", expected_minor_units, currency_iso="USD", due_date_iso, lifecycle="open")` and `GigToCashStore(DEFAULT_DB_PATH).append(...)`. Creates the Reynolds receivable. Reuse the `ar_*` records + store verbatim.
- **B) Match (new bridge, read-only over the books):** `match_check_to_receivable(evidence_record)` — take recorded evidence_intake output (artifact carries `claimed_client_ref`=vendor, invoice_ref via `_detect_invoice_ref`, amount from operator_note); open `GigToCashStore` read-only; resolve the counterparty's current Invoice/ExpectedReceivable via `get_current`; compare check minor units to `expected_minor_units` + currency. Return `{receivable_id, gig_id, expected_minor_units, due_date_iso, amount_matches}`. No mutation.
- **C) Ask (reuse lifecycle + card):** on match, emit a deterministic card via `evidence_intake.build_dynamic_card` shape: headline "Reynolds Tavern check — matches receivable", summary "$X check matches the $X due on invoice <ref> for the <date> gig. Did you deposit it?"; advance artifact payment_state payment_proof_candidate→payment_arrived_unverified (states at 59-67). No paid marking.
- **D) On operator "YES, deposited" (operator-confirmed, Guardian-gated — per the untrusted-channel rule the Telegram text alone cannot authorize the write):** two records-only effects — (i) satisfy the receivable: build a superseding ExpectedReceivableRecord (lifecycle="satisfied", resolution_ref=artifact_ref) and `GigToCashStore.supersede(receivable_id, new)`; (ii) log the tax item: `chief_cpa_brain.log_entry(amount, description=f"{vendor} gig {gig_date}", category=schedule_c, entry_type="income")` guarded by `find_duplicate_today(amount)`, stamping artifact_ref+gig_id+receivable_id as provenance; (iii) expect-in-bank: leave a `cassandra_brain` `pending_income_followup` (~456) marker so a later bank-ledger confirm flips payment_arrived_unverified→ledger_recorded. Reuse `chief_cpa_brain` verbatim; do NOT write a new income store.
- **E) Tag the image to gig + vendor:** reuse the `artifact_lineage_registry` write in evidence_intake (`_insert_artifact_lineage_row`, `source_workflow_ref`) — pass `gig_id` as `source_workflow_ref`, and add a thin `gig_evidence_link` row (artifact_ref, gig_id, receivable_id, vendor=reynolds_tavern). Vendor is already on the artifact via `claimed_client_ref`.
- **F) Reach it from chat:** wire the bridge into `cassandra_brain` `_handle_payment_verification_request` (2721) and `_looks_like_operator_financial_event`/income capture (2798-2819) so that, for a vendor with an open receivable, they call `match_check_to_receivable` and the deposit-confirm path instead of only Gmail + expense_log. Deterministic-first; LLM for phrasing only.

**Hard constraints:** Money/send stays Guardian-gated — the deposit-confirm write (receivable satisfy + cpa income) waits on the Guardian/in-session gate; "yes I deposited it" in chat is treated as operator-*reported* (advances state, drafts the entry), the actual write does not fire from the untrusted Telegram text alone (matches `feedback_factory_gating_model`). No email/Gmail/send, no browser/Coupa, no paid-marking outside Guardian — the only mutations are the receivable supersede (records) and the cpa income entry (records). Grounding intact: match is a real read of the seeded books, amounts compared not guessed. Vendor/amount/date arrive from the operator_note (or **E's local-vision-first** step) — this module assumes E's input rail and inherits its billing rule (local first; prepaid-capped OpenRouter only via gate; never postpaid). Per-agent (lands in Cassandra's payment surface, not a Maestro snowglobe). Preserve both existing authority boundaries (evidence_intake never mutates ledger; G2C is pure local persistence).

**Non-snowglobe verification (real pipeline; `sqlite3` CLI is absent — query via `python3 -c "import sqlite3…"`):**
1. **Seed + prove books exist:** run the seeder; python-query `/home/openclaw/state/gig_to_cash/gig_to_cash.sqlite3` → gig/invoice/expected_receivable each have the Reynolds row; `GigToCashStore.get_current(ExpectedReceivableRecord, receivable_id).lifecycle_state=="open"` with `expected_minor_units == the Reynolds fee`.
2. **Real evidence drop through the live processor:** write a `VERIFIED_EVIDENCE_INTAKE_REQUEST_V0` (intended_use="payment_proof", claimed_client_ref="reynolds_tavern", operator_note citing invoice ref + $amount) into the inbox pattern (`EVIDENCE_INTAKE_REQUEST_PATTERNS`, openclaw_request_processor.py:101-128) and run the processor path. Assert an `evidence_intake.sqlite` row + `artifact_lineage` row + dynamic card, payment_state classified, AND `machine_proof.ledger_mutation_performed`/`paid_marking_performed == false`.
3. **Run the bridge:** `match_check_to_receivable(record)` → `amount_matches` True, returns the seeded receivable_id/gig_id; the card asks "did you deposit it?" and payment_state advanced to payment_arrived_unverified.
4. **Simulate operator-confirmed YES (Guardian-gated):** the deposit-confirm path → (a) `get_current(receivable).lifecycle_state=="satisfied"` with `resolution_ref==artifact_ref`; (b) `chief_cpa_brain.get_recent_income(days=1)` shows the new income entry == check amount carrying artifact_ref+gig_id provenance; (c) `find_duplicate_today` prevents a second log on re-run (idempotent); (d) the `gig_evidence_link` row ties artifact_ref→gig_id→reynolds_tavern.
5. **Reach it from chat (true integration):** "Did the Reynolds check clear?" routes via `_handle_payment_verification_request` and reports the receivable match; "I deposited the Reynolds check for $X" runs the confirm path and logs the tax item. Assert no Gmail send / no paid-marking occurred.
6. **Authority regression:** `evidence_intake.unsafe_true_grants(payload)==[]`; only DB writes are the receivable supersede + cpa income entry. Run the existing suites: `tests/test_evidence_intake.py`, `tests/test_evidence_intake_live_route.py`, `tests/test_ar_gig_to_cash_store.py`, `tests/test_ar_expected_receivable_record.py`, `tests/test_cassandra_payment_verify.py`, `tests/test_finance_invoice_reconciliation.py`, plus a new `tests/test_check_evidence_books_bridge.py` for the end-to-end chain.

*Open: one canonical vendor key to join evidence↔receivable (Reynolds is in `reynolds_gig_setup_status.json` but not `finance_thread_index.json` — add it, or map gig_ref→counterparty_ref). Amount source: operator_note until E's local vision lands (evidence_intake deliberately does not OCR, raw_ocr_text_stored=false). Confirm the income category for gig performance (schedule_c_gross). Confirm "yes I deposited it" is operator-reported (drafts) but the income/receivable write waits on the Guardian gate. Decide whether a future bank-ledger confirm (payment_arrived_unverified→ledger_recorded) is required before counting as fully reconciled, or operator deposit-confirmation suffices for the tax item.*

---

## OPERATOR REFINEMENTS (fold into the check-image / G2C section when the addendum is added)

- **Do NOT assume payment implies the gig was already played.** The operator can be paid BEFORE
  performing (deposit / advance / retainer). When a recognized check matches a gig's amount-due,
  the system must treat "this gig was played & paid" as an **assumption to confirm, not a fact** —
  ASK ("I see a Reynolds Tavern check for the gig amount — have you played this one yet, or is it
  an advance/deposit?") and only set played/paid state from the operator's answer. Generalize:
  surface inferred causal stories as confirmations, never log them as truth without confirmation.
  Keep the confirmation SHORT (operator dislikes verbose replies); the underlying reasoning/linkage
  must still be correct.

- **Hermes must be directly operator-facing (fold into the Hermes section).** Hermes is the
  operator's OpenClaw consultant / systems engineer — NOT only an internal observer for Chief and
  the other agents. The fix is not merely "stop being silent"; it's a real two-way chat: the
  operator texts Hermes and gets a grounded, conversational answer in Hermes' voice ("elegant,
  precise systems advisor"). Wire Hermes' INBOUND chat the same way maestro/cassandra are wired
  (listener -> request envelope -> `openclaw_request_processor` -> brain via the front-door
  profile, with Hermes' agent id so the per-agent voice applies — NOT a Maestro snowglobe), and
  feed his answers from his existing systems/fleet context (reuse `hermes_observer.observe_fleet`,
  sync_health / agent_presence / build-state read-models) so he can actually answer "what do you
  see across the fleet?", "why is X broken?", "what should we build next?". Authority stays gated:
  Hermes advises + can route build suggestions through the existing gateway (normal->Chief,
  privileged->Guardian); he does not gain send/money/mutation authority from being chattable.

---

## G — Clara Reid / Cassandra persona reconciliation (BUILD)

**Operator decision (final):** Cassandra is the INTERNAL identity (the operator's executive
assistant). **"Clara Reid"** is the SAME agent's **client-facing / non-inner-circle register** —
the toned-down outward voice she uses with clients and outsiders. ONE agent, TWO registers
(internal = Cassandra; external = Clara Reid). Authority is identical in both registers and stays
advisory_only with sends/ledger/paid-marks Guardian-gated.

**Current state (grounded):** the codebase is INCONSISTENT about this:
- `agent_lane_registry.py:243` (`telegram_display_name="Clara Reid"`) + `telegram_agent_intake.py:49`
  (`outward_name="Clara Reid"`, note: "Internal agent is Cassandra; outward-facing identity is
  Clara Reid") + `cassandra_clara_fact_packet.py:31` (`EXTERNAL_PERSONA="Clara Reid"`) correctly
  model Clara as Cassandra's outward NAME.
- BUT `agent_voice_profiles.py` + `frontdoor_prompt.py:37` model **`clara` as a SEPARATE
  speaker_ref/persona**, and `agent_handoff_registry.py:277` has a `clara_to_cassandra_internal_review`
  handoff — i.e. treated as two agents.
- **Typo:** canonical is **"Clara Reid"** (81 occurrences) but **"Clara Reed"** appears 5x incl.
  `canonical_doctrine_facts.py:141`.

**Fix spec:**
1. Make every config reflect ONE agent, two registers: `clara` is Cassandra's external voice
   register, NOT a separate agent. Reconcile the `agent_voice_profiles`/`frontdoor` separate-speaker
   modeling + the handoff registry so the internal↔external switch is a **register/tone switch on
   one agent**, not an inter-agent handoff. Keep the tone-down behavior (client-facing => Clara Reid
   voice; inner-circle => Cassandra).
2. Fix all "Clara Reed" -> "Clara Reid" (start at `canonical_doctrine_facts.py:141`; grep the 5 sites).
3. Do not change authority: both registers stay advisory_only; sends/ledger Guardian-gated.

**Non-snowglobe verification:** through the live pipeline, confirm a client-facing surface renders
"Clara Reid" while an inner-circle/operator surface renders "Cassandra", SAME agent id + SAME
authority. Grep proves zero "Clara Reed" remain.

---

## H — Fin: the finance-agent architecture question (AUDIT ONLY — recommend, build NOTHING)

**This section is analysis. Do not create an agent, do not register a lane, do not add a token,
do not delete the residual string yet. Return a recommendation; the operator decides; a final build
prompt follows.**

### Head-start facts (already established — verify, then go deeper)
- **"Fin" is a phantom name, not an agent.** It exists only as prose in ONE shared-doctrine fact
  (`canonical_doctrine_facts.py:145`, SD-4 roster sentence: "...niles (...), fin (finance/invoicing/
  AR/AP/ledger)...") and the matching live ledger row (`.openclaw/business_ops/ledger.sqlite`
  `canonical_facts.SD-4` + its FTS index). It is NOT in `DEFAULT_AGENT_LANE_SEEDS`
  (`agent_lane_registry.py:123`), NOT in the live `agent_lanes` table, has NO `FIN_BOT_TOKEN`, NO
  listener, NO process, NO authority.
- **Provenance:** written by an LLM build agent on 2026-06-21 (`git a41f8f67`, "curated grounded
  shared-doctrine facts"), placed in SD-4 + 5 facts' `allowed_actors`. Partially pruned 2026-06-22
  (`git c758265a`, "remove dead 'fin' actor… operator confirmed unknown/unused") which cleared
  `allowed_actors` (5->0) but LEFT the SD-4 roster sentence — that residue is why Maestro still
  recites "fin." Backup `.openclaw/business_ops/ledger.sqlite.bak.fin` still holds the 5 pre-prune rows.
- **Finance today is owned by Cassandra** (lane: "business ops, AR, income/payment/expense/gig logs…",
  worlds incl. finance). **Chief's "brains" are NOT agents** — ~30 unprivileged `chief_*_brain.py`
  reasoning libraries (`handle(text)->replies`), read/draft-only; CPA=`chief_cpa_brain.py`,
  music-lawyer=`chief_musiclaw_brain.py`, publicist=`chief_marketing_brain.py`. **Authority never
  lives in a brain** — send/money/ledger is a separate Guardian + approval-gate layer
  (`finance_invoice_reconciliation.py` NO_AUTHORITY_FLAGS all False). Cassandra ALREADY imports
  `chief_cpa_brain` as her finance library — i.e. the live pattern is **agent owns lane, calls brain
  for reasoning, Guardian gates money/send.**

### Audit asks (go deeper, CROSS-REPO)
1. **Cross-repo sweep:** confirm "fin" exists nowhere else (sweep all repos via `system_catalog`,
   `.openclaw/agents/*`, sidecars, worktrees, every ledger/read-model). Is the SD-4 sentence + its
   ledger row + FTS the ONLY residue? Any FIN_BOT_TOKEN / fin listener anywhere at all?
2. **Finance fragmentation:** the brains audit flagged finance source-of-truth is fragmented
   (`chief_cpa_brain` expense_log.json, billing CSV, G2C records, `finance_invoice_*` tables). Map it
   fully and recommend a single source of truth — this matters whether or not Fin is created.
3. **Handoff gap (gates everything):** confirm there is NO live agent-to-agent handoff mechanism
   today (there's an `agent_handoff_registry` but apparently no live executor). Scope what wiring a
   real "Maestro routes money-talk to the finance owner" handoff would take — because a new Fin is
   unreachable/unroutable without it (would be a snowglobe).
4. **Governance guard:** an LLM wrote a non-existent actor into "grounded canonical" doctrine facts
   and it slipped the "LLM must not write unverified canonical truth" contract. Specify a validator
   that cross-checks every actor named in a doctrine fact's text/`allowed_actors` against
   `DEFAULT_AGENT_LANE_SEEDS` + the live `agent_lanes` table so a phantom actor cannot be admitted
   again. (This guard is worth building regardless — flag it for section B.)

### Decision to RECOMMEND (with authority-scoping tradeoffs)
- **Option 1 — No Fin:** finish the cleanup (remove the residual SD-4 string + reseed the ledger
  row/FTS so it can't reappear; confirm no re-seed reads `.bak.fin`) + add the governance validator.
  Finance stays in Cassandra's lane. Simplest, already-diversified, lowest surface.
- **Option 2 — Make Fin a real agent:** register `fin` in `agent_lane_registry` with a finance lane
  + its own token/listener; Fin OWNS finance and CALLS Chief's CPA/financial brains (NOT *is* the
  brain); money/send stays Guardian-gated; Cassandra/Clara narrows to client-relations + exec-assist.
  Better specialization per the operator's "deep lane each" design — but only viable once the live
  handoff (ask #3) exists, else it's an unreachable identity.
- Recommend one, with reasoning grounded in the authority model (agent≠brain; Guardian gates money).
  Note that Option 2 should be bundled with wiring real handoff, not done standalone.

**Deliverable for H:** the audit + recommendation + open questions in
`Operator/CODEX-FLEET-WORK-RESULTS.md` under a "## H — Fin audit" heading. No code changes.

---

## I — Humor as a health signal (gate the comedy on real system state) (BUILD)

**Operator rule — TWO dials.** The agents should feel like competent crew on the Starship
Enterprise — professional, warm, focused — **not a roster of comedians.**
- **Dial 1 — baseline is sparing/professional.** Humor is RARE and RESERVED for moments that matter
  (a genuine win, a real moment of connection, a just-healed hiccup) — never constant quipping,
  forced metaphors, or zingers (the "trying too hard" espresso-machine voice the operator already
  rejected with "that's a little much"). Default register = capable crew member, not entertainer.
- **Dial 2 — health gate.** Even that rare humor only fires when the system is actually functioning
  correctly (or just auto-healed). It is a DIAGNOSTIC SIGNAL that things are right — earned by real
  health, the sibling of the jargon rule (NO_JARGON, `agent_voice_response_layer.py`), realizing the
  "comedy-as-diagnostic" intent.
Throughout this section, "humor ALLOWED" means **permitted-and-sparing**, never
expected-on-every-healthy-reply.

**The rule, precisely:**
- Humor is ALLOWED only when the reply is genuinely healthy: the brain actually answered THIS turn
  (`model_ok`, NO deterministic fallback — read the REAL receipt, which is why this depends on Bug A),
  grounding intact, and the subsystem the message concerns is functioning.
- Humor is SUPPRESSED — reply goes plain/straight, no jokes/metaphors/zingers — whenever the response
  is a fallback, an error, a "can't reach X / broken / degraded" report, or otherwise signals
  something is wrong. A joke over a broken state is a FALSE "all's well" signal and is forbidden.
  Concrete example to fix: the current calendar-auth failure ("couldn't reach your calendar… re-run
  --auth") must come back PLAIN, never witty.
- NUANCE (the one allowed broken-state joke): wit IS allowed about something that broke IF the system
  AUTO-FIXED it — humor then signals "it hiccuped, I caught and healed it, we're good," which is
  itself a correctness signal. Tie this strictly to a self-heal that actually LANDED, never to an
  unresolved failure.

**Why it depends on A:** the gate must read the TRUTHFUL health signal (`model_call_performed` /
fallback / route from the brain receipt + the subsystem status), not a guess — you cannot gate humor
on health if the health flag lies (the exact Bug A defect). Build A first.

**Fix spec (reuse the voice layer):** gate the conversational-lane humor (the social branch in
`frontdoor_prompt.py` that raises temperature for casual replies, + `agent_voice_response_layer.py`)
on a health predicate derived from the real receipt + the subsystem state the reply touches. When
unhealthy, drop to a plain "straight, no-wit" register (the lane already has a low-key/natural mode —
extend it).

**A per-agent humor calibration ALREADY EXISTS and was built — Niles = most humorous … Guardian =
least.** FIND it first (likely `agent_voice_profiles.py` or a humor/personality config — grep for
humor/wit/levity/personality per agent) and REUSE it; do not rebuild or flatten it. The two dials
above modulate ON TOP of each agent's existing level: even Niles drops to straight when something's
broken; Guardian stays dry regardless of health. Per-agent aware, never a Maestro snowglobe. Verify
the calibration ordering still holds after the change (Niles > … > Guardian) on healthy replies.

**Non-snowglobe verification (live):** inject probes through the real pipeline and confirm
(1) a clean healthy reply MAY carry wit; (2) a degraded reply (force a fallback, or the live calendar
error) returns PLAIN — zero humor; (3) an auto-healed event MAY carry the "fixed it" wit. Paste the
live replies + their receipts (`model_ok` vs fallback) into the results file.
- `protected_generate_audit.jsonl` (`/mnt/c/OpenClaw/logs/`) — ground-truth brain-call log for
  correlation.

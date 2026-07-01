# Codex packet — close the Hermes recommend→build pipe (2026-06-29)

**Owner:** Codex. **Reviewer:** Opus + operator. **Branch:** `codex/stress-fixes`. **Repo:** /home/openclaw.

## Context (already done by Opus — don't redo)
Hermes (the sidecar consultant) is now GROUNDED: `sidecars/hermes_home/SOUL.md` got an
`<openclaw_grounding>` block + a new `sidecars/hermes_home/OPENCLAW_INVENTORY.md` (map always-on,
territory on-demand). So he should stop suggesting generic SaaS and reference real OpenClaw components.

A workflow traced the recommend→build pipe and found there are TWO Hermes paths that don't connect:
- **PATH A = the sidecar** (the Hermes the operator talks to on Telegram, qwen3:4b). Produces advisory
  text → **dead end, no way to file a build.**
- **PATH B = the fleet loop** (`hermes_observer.py`, cron `30 */3 * * *` — CONFIRMED installed). Wired
  ~90% to the factory but only fires on health *metrics*, and silently fails for two signal ids.

This packet fixes both. Verify each with TDD; respect Guardian gates; don't self-approve prod-state
writes; commit small on codex/stress-fixes; don't push.

---

## GAP 1 (P0, small) — fleet loop silently fails for 2 signal ids
`self_improvement_request._SELF_IMPROVEMENT_PACKAGE_PROFILES` has profiles for `high_fallback` and
`no_response_{maestro,cassandra,chief,guardian,niles,hermes}`, but is **missing**:
- `responses_slow` (emitted by `self_monitor` when >30% of replies are slow)
- `fleet_sync_degraded` (emitted by `hermes_observer._fleet_health_observer` from
  `generated/read_models/sync_health.json`)

Both raise `SelfImprovementPackageError` → caught in `route_to_chief` → `filed=False` → added to the
"failed" retry list → retried every 3h forever, never landing. The loop looks alive but two of its
three signal sources are dead.

**Fix:** add the two profiles to `_SELF_IMPROVEMENT_PACKAGE_PROFILES` in
`/home/openclaw/self_improvement_request.py`:
- `responses_slow`: latency-focused; allowed_files ~ `["maestro_listener.py","self_monitor.py",
  "tests/test_maestro_fast_ack.py","tests/test_self_monitor.py"]`; success = "slow-reply source
  identified; a bounded latency fix proposed; no prod service auto-restart."
- `fleet_sync_degraded`: read-only diagnosis; allowed_files ~ `["no_response_watchdog.py",
  "hermes_observer.py","tests/test_hermes_observer.py"]`; success = "stalled sync source identified in
  evidence; NO auto-restart of production services; recovery proposal is Guardian-gated."
Match the existing profile shape exactly (look at `high_fallback`).
**Acceptance:** TDD — a test that `compile_self_improvement_package("responses_slow")` and
`("fleet_sync_degraded")` each return a valid package (no `SelfImprovementPackageError`); the existing
hermes_observer tests still pass; every gap_id the loop can emit now has a profile.

---

## GAP 2 (the real one) — the conversational Hermes can't file a build
This is the operator's actual ask: "when Hermes recommends THE RIGHT THING, there's a clear way to get
it built." Today PATH A (the sidecar he talks to) stops at advisory text. Only PATH B (automated
metrics) reaches the factory. We need: **a grounded conversational Hermes recommendation → a filed,
Guardian-gated build request in the factory** — reusing the existing, proven gate (NOT a new gate).

**Design (reuse, don't reinvent):**
1. Give the sidecar Hermes a **structured "propose a build" capability** — e.g. a skill/tool in
   `sidecars/hermes_home/skills/` (he loads skills already) OR a CLI/bridge command that emits a
   structured proposal `{id, title, build_goal, evidence, touched_scope_hint}` rather than free text.
   He should only PROPOSE (consistent with his bounded advisory role + SOUL.md).
2. Bridge that proposal into the EXISTING path: `hermes_observer.route_to_chief()` /
   `self_improvement_request._default_file_fn(gap, "hermes")` →
   `polish_loop/build_request_intake.admit_with_safety_check` → PROPOSED + Guardian BUILDOK/BUILDNO.
   Requester stays `"hermes"` (not in OPERATOR_REQUESTERS) so it ALWAYS goes through Guardian approval —
   no self-approve. A free-form Hermes goal needs a package profile or a generic "advisory_build_proposal"
   profile with conservative allowed_scope + mandatory Guardian escalation.
3. Keep it **operator-in-the-loop**: a Hermes conversational proposal should surface to the operator
   (and/or Chief) for a yes before it files — Hermes proposes, human/Guardian dispositions, factory builds.

**Hard constraints:** Hermes stays bounded-advisory (he proposes, never executes/approves/enqueues
directly — see SOUL.md + HERMES_PROPOSAL_SCHEMA.md). Every sidecar-originated build is Guardian-gated.
No new approval authority. Local-first. This is the meatiest item — design it small and reviewable;
if it's too big for one pass, land the structured-proposal emit first, then the bridge.
**Acceptance:** a (test/sim) Hermes proposal flows end-to-end to a PROPOSED control-plane task with a
Guardian approval prompt; tapping BUILDOK promotes it to READY; tapping BUILDNO drops it; Hermes never
files anything that skips the gate.

---

## GAP 3 (small, hygiene) — vendored AGENTS.md noise in Hermes's prompt
The sidecar's system-prompt "context files" loader falls back to `os.getcwd()` =
`/home/openclaw/sidecars/hermes/` because `TERMINAL_CWD` is NOT set in `hermes-gateway.service`. That
dir has a **vendored upstream `AGENTS.md`** (a generic dev guide) which wins the priority chain and
leaks into his prompt as noise — competing with SOUL.md's grounding.
**Fix:** set `Environment=TERMINAL_CWD=/home/openclaw` in `hermes-gateway.service` (+ the `.in`
template at `/home/openclaw/systemd/user/hermes-gateway.service.in`), OR otherwise stop the vendored
AGENTS.md from being selected, so the loader doesn't pull upstream noise. Verify the rendered system
prompt no longer includes the vendored AGENTS.md.

## Output protocol
Plain-English CLI summary + machine results to `Operator/CODEX-HERMES-RECOMMEND-BUILD-PIPE-RESULTS.md`
(per item: status, files, commit shas, tests, before/after). Don't push.

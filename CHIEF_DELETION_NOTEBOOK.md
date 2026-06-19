# CHIEF DELETION NOTEBOOK — parked candidates for the gate harness
_Created 2026-06-19 from DEAD-CODE-AUDIT-REPORT (Opus + 7 Haiku finders + adversarial verify). Full report: `/mnt/e/openclaw/orchestration/inbox/to-claude/DEAD-CODE-AUDIT-REPORT.md`._

## GOVERNING RULE (Winship, 2026-06-19)
**BUILD FIRST. DELETE NOTHING YET.** This is not greenfield — we do not remove anything we may need. Every entry below is a **deletion HYPOTHESIS**, not an order. A candidate is removed ONLY after it survives Chief's decision gates *with verification* (and even then via the recoverable quarantine commit). Chief must never begin by generating (or deleting) — outcome and existence first.

## How a candidate exits this notebook
Each candidate is run through the gates. The two that decide deletion:
- **EXISTENCE gate** — should this behavior/component exist at all? (If the outcome no longer needs it → candidate for removal.)
- **MECHANISM gate** — can the desired outcome be satisfied by *deletion / reuse / config / data-correction / an existing capability* rather than keeping it?
A candidate may only move to `QUARANTINE-APPROVED` when: (1) it passes EXISTENCE+MECHANISM as removable, AND (2) a fresh verification proves it dead at delete-time (`rg=0` incl. dynamic `importlib`/`getattr`, no live caller, no read-model/runtime `read_text` load), AND (3) it is not on the live serving path (or, if it is, Winship signs off). Otherwise → `KEEP` (with the refuting evidence recorded, so we don't re-litigate it).

State machine per candidate: `PENDING-GATE → (gates) → QUARANTINE-APPROVED | KEEP | NEEDS-WINSHIP`.

---

## Dataset A — high-confidence removable hypotheses (rg=0, no live serving) — ALL `PENDING-GATE`
_The audit's adversarial pass already pre-cleared these of the false "superseded-by-control_plane" premise; they are dead on their own rg=0 merits. Still must pass the gates + a fresh delete-time rg=0 before removal._

| Candidate | Why-dead (audit evidence) | Restore ref | State |
|---|---|---|---|
| `steel_thread_lane_template_registry.py` (49KB) | 0 module imports; pre-control-plane lane dispatch | `git show HEAD:` | PENDING-GATE |
| `cross_machine_worker_dispatch_package.py` (51KB) | rg=0; pre-control-plane fleet dispatch | `git show HEAD:` | PENDING-GATE |
| `spawned_worker_package_lifecycle.py` (22KB) | rg=0; manual fleet lifecycle | `git show HEAD:` | PENDING-GATE |
| `lm2_canonical_worker_spine_consolidation.py` (18KB) | rg=0; lm2 pilot | `git show HEAD:` | PENDING-GATE |
| `lm_bounded_operator_orchestration.py` | rg=0; `MODE=contract_only_no_live_lm` | `git log -S` | PENDING-GATE |
| lm2 retry-chain trio (`lm2_structured_output_retry_approval_packet`, `lm2_room_backed_worker_pilot_postmortem`, `lm2_room_backed_worker_structured_output_retry`) | internal 3-file cycle, 0 external imports | `git log --all` | PENDING-GATE |
| `chief_invoice_brain.py` | `RETIRED=True` tombstone; fail-closed stub | `git show 4bc843e4` | PENDING-GATE |
| `agent_voice_response_layer.py`, `agent_response_voice_modes.py` | snow-globed read-model generators; orphan export+test | `git show 704f472c` / `28cc735a` | PENDING-GATE |
| zero-byte/dups: `Chief_listener.py`, `cassandra_tts_backends_branch.py`, `cassandra_finance_state.py`, `cassandra_sovereign_briefing.py` | empty / case-collision dup / shim | branch history | PENDING-GATE |
| untracked root scratch (`chief_log_patch`, `add_proof`, `fix_checker`, `patch_17`, `patch_test`, `map_room_patch`, `inventory_sqlite`, `prove_contract`, `prove_route`, `audit_prune*`, `audit_brains*`, `patch_checker`, `tmp_generate_audit`, `generate_reports`, `invoice_generator`, `eval_contracts`, `file_integrity`, `finance_watchdog`, `summarize_models`, `dashboard_stubs`, `real_stubs`) | no `__main__`; rg=0; untracked | **NOT in git history → snapshot to `.audit-quarantine/` before any removal** | PENDING-GATE |
| `cassandra_tts_backends.py` (24.5KB), `cassandra_voice_branch.py` (24.5KB), `hitl_dashboard.py` (35.6KB orphan FastAPI) | rg=0; abandoned experiments / orphan surface | git history | PENDING-GATE |
| `polish_loop/flip_to_mac.py`, `polish_loop/pc_output_recovery.py` | rg=0 helpers | `git show HEAD:` | PENDING-GATE |
| `polish_loop/recommend_action.py` | rg=0 BUT verify cited `recommend_action.py:42-52` in parked-state evidence | `git show HEAD:` | **PENDING-GATE (resolve `handle_parked` ref FIRST)** |
| planning-packet quad (2 JSON + `scripts/export_operator_planning_ready_packets.py` + its test) | closed export↔test loop, no live consumer | `git show c5a5c774:` | PENDING-GATE |
| `tests/test_launch_ladder_static_contract.py:896-902` | duplicate `test_backend_data_contract_shape_plan_is_documented` shadows line 882 | `git show HEAD:` | PENDING-GATE |

## Dataset B — `KEEP` (verify REFUTED them as live; recorded so we never re-propose)
- **`polish_loop/orchestrator.py` ENTIRE** — the live PC daemon. `POLL_INTERVAL`, `write_status`/`_write_status_raw` (23 callers), all `handle_*` cycle dispatchers, the `while True` loop. The "superseded by control_plane.py" premise is FALSE — `control_plane.py` is branch-only, imported nowhere on the serving branch.
- **`openclaw_request_processor.py`** voice-authorship fns + `FUTURE_REQUEST_PATTERNS` family — called every request / actively matched in `classify_request_filename()`.
- **`generated/read_models/*.json` (382) — NEVER batch-delete.** `cassandra_email_calendar_capability_reconciliation.json` gates authorization at `cassandra_brain.py:2322`; `active_machinery_classification_orchestrator.py` iterates the set; `read_model_shuttle.py` mirrors 202 to Mac. rg=0 missed runtime `read_text()`.
- **238 `scripts/export_*.py`** — these PRODUCE the read_models; per-file audit only, never batch.

## Dataset C — `NEEDS-WINSHIP` (provably unreferenced but inside the live served module)
- `openclaw_request_processor.py:185 PROVIDER_FAMILIES`, `:194 INTERRUPTION_POLICIES` — AST-confirmed unreferenced, but editing the live `openclaw-request-response.service` module → Winship sign-off.

---
**Next:** wire this notebook into a Chief **decision-gate harness** (build packet — see routing) that runs each `PENDING-GATE` candidate through OUTCOME→EXISTENCE→MECHANISM→…→verification and emits the verdict. Until that harness exists and a candidate clears it, **nothing here is deleted.**

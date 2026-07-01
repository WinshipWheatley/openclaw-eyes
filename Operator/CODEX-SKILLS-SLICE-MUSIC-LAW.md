# Codex build packet — Skills system: vertical slice (`music_law_advisory`)

**Owner:** Codex. **Reviewer:** Opus + operator live-check. **Branch:** `codex/stress-fixes`.
**Repo root:** `/home/openclaw` (WSL `Ubuntu-E`).
**Design:** `Operator/SKILLS-CAPABILITY-ROUTER-DESIGN.md` · **Audit:** `Operator/SKILLS-AUDIT-RESULTS.md`.

This is **deliverable B** from the design: the THIN machinery to prove ONE skill end-to-end live.
**Scope discipline:** `music_law_advisory` is a single-skill, single-model knowledge task — it does
NOT need the full capability-router decompose-to-local-chain. Build registry → tier-select →
packet-attach → live execute, plus the live resource-probe. The decompose/resource-*scheduler* router
is a LATER packet, once this slice proves the loop. Do not over-build.

## 0. HOW TO RUN (read first)
- Cross-repo aware; primary stack `/home/openclaw`; don't edit `worktrees/*` or `sidecars/*`.
- Do **S1 → S2 → S3 → S4** in order. Each is **BUILD**: TDD (red→green) AND the non-snowglobe LIVE
  verification in that item (green unit test alone ≠ acceptance). Commit small. **Do NOT push.**
- **STOP-RULE SCOPE:** if a SPECIFIC step is a Guardian-gated prod-state write (e.g. seeding the
  skills table into the live `system_catalog.sqlite3`), SKIP ONLY THAT STEP — emit the exact command,
  mark `operator_pending` — and CONTINUE the rest. Do not self-approve; do not abandon the packet.
- **REUSE, do not rebuild** (audit-confirmed these EXIST): `skill_loader.py` + `skill_vetter.py`
  (ingestion+validation), `step_executor.py` + `model_aware_decomposer.py` (planner+executor),
  `capability_skill_registry_metadata_delta.py` (gate classification), `model_router_policy.select_model_class`,
  `chief_llm.select_frontdoor_model` + `_ollama_model_sizes`, the skill-creator `SKILL.md` format.
- **Output:** (1) plain CLI summary; (2) machine results to `Operator/CODEX-SKILLS-SLICE-RESULTS.md`
  (per item: status, files, commit shas, tests, live-verify output). State that path in the summary.

## S1 — Runtime skill registry (one truth store)
**Gap (audit GAP-A):** `capability_skill_registry_metadata_delta` holds gate-classification metadata,
not invocable skills; there's no `(skill_id, owner_agent, triggers, tools, authority, tiers, …)` store.
**Build:** add a `skills` table to **`system_catalog.sqlite3`** (EXTEND the existing catalog scan —
do NOT fork a second truth store), populated by `skill_loader.load_skills()` reading `SKILL.md`
files. A skill record carries: `skill_id, owner_agent, triggers (list), tools (brains/read-models it
may call), authority (advisory_only | references_gated_action), capability_needed
(simple-extraction | multi-step-reasoning | …), tiers{simple, rich}`. Validate on load with
`skill_vetter` + the doctrine-style actor/tool validator (every `owner_agent`/`tools` entry must
exist in `DEFAULT_AGENT_LANE_SEEDS` / the real registries — reuse the P1 validator pattern).
**Live verify:** `skill_loader.load_skills()` populates the `skills` table; a query returns the
registered skill with its tiers; the validator rejects a skill referencing a non-existent agent/tool.

## S2 — Author the `music_law_advisory` skill (reuse `chief_musiclaw_brain`)
**Build:** a `SKILL.md` (skill-creator format) `music_law_advisory`. `owner_agent`: chief (the
music-law lane); reachable when Maestro/Cassandra get a music-legal question. `tools`:
`chief_musiclaw_brain` (the existing WIRED-LIVE knowledge body — wrap it, don't rebuild) + the music
read-models. `authority: advisory_only` — it ADVISES on splits/sync/sample-clearance/publishing and
**must preserve the existing "flag when a real entertainment lawyer is needed" safety**
(`chief_musiclaw_brain._ensure_musiclaw_safety`); it never takes legal action / sends / signs.
- `tiers.simple`: a tight checklist a local 8b can follow (identify the question type → pull the
  relevant musiclaw facts → answer plainly → ALWAYS append the real-lawyer flag when stakes are real).
- `tiers.rich`: the full multi-step reasoning for a capable model (precedent, the live Ten Fingers /
  Log Rhythm dispute context, edge cases) — still advisory, still lawyer-flagged.
**Live verify:** the skill record loads + validates; both tiers render; the real-lawyer-flag text is
present in both.

## S3 — Selection + tier-attach into the live packet (audit GAP-B, the biggest)
**Gap:** `maestro_context_packet` has no skill surface today. **Build:** when a request matches a
registered skill's `triggers`, the packet builder (1) selects the skill, (2) picks the tier by the
running model's class — **reuse `model_router_policy.select_model_class` / `select_frontdoor_model`**
(simple for local 8b, rich for capable) — and (3) injects that tier's `SKILL.md` body into the SAME
context packet the brain already receives (front-door via `maestro_context_packet`; keep the
build/factory path via `task_routing` in mind but the slice only needs the front-door). Per-agent
aware (deliver in the owner agent's voice/lane; not a Maestro snowglobe). **Authority unchanged** —
the skill text can say "use the musiclaw brain" but grants no new authority; sends/legal stay gated.
**Live verify (THE proof):** inject a real music-law question through the live pipeline (e.g. "how do
publishing splits work on a 50/50 co-write with a topliner?") → the packet carries the
`music_law_advisory` skill (correct tier for the running model), the brain answers grounded in the
musiclaw knowledge, the answer includes the real-lawyer flag, and the receipt records the skill was
applied. Correlate with `protected_generate_audit.jsonl` (model_ok). Paste the live reply + receipt.

## S4 — Live resource probe (kill the dead 12GB constant)
**Gap (audit):** `protected_generate.py:1136` never passes real capacity, so `select_frontdoor_model`
budgets against a hardcoded ~12GB — the "resource-aware" model selection is not actually live.
**Build:** a tiny non-model probe (reuse-friendly): `nvidia-smi --query-gpu=memory.free,memory.total`
(works on this box via `/usr/lib/wsl/lib/nvidia-smi` → ~5GB free of 6GB) + `/proc/meminfo MemAvailable`
+ `GET http://localhost:11434/api/ps` (resident model size_vram). Thread `available_vram_gb` +
`available_ram_gb` into `select_frontdoor_model` so model fit is judged against REAL capacity. This is
the foundation the future resource-aware serial/parallel scheduler needs.
**Live verify:** the selector logs the REAL free VRAM/RAM (not 12GB) for a live front-door reply.

## Hard constraints
- Reuse the existing modules above; do not rebuild them. One truth store (`system_catalog.sqlite3`).
- Authority never travels with a skill; music-law stays advisory + real-lawyer-flagged; no sends/legal.
- Grounding intact (no invented law/facts); local models first; per-agent, not a Maestro snowglobe.
- Seeding the live skills table is a prod-state write → operator-gated (emit command, do not self-approve).

## Deliverable
A working, live-proven `music_law_advisory` skill: registered → selected → tier-attached → answered
through the real pipeline, with the resource probe live — proving the skill loop end-to-end on the
cheapest sufficient model. Results + live-verify output in `Operator/CODEX-SKILLS-SLICE-RESULTS.md`.

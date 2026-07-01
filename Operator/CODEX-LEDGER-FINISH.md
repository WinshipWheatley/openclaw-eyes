# Codex packet — finish the one-knowledge-ledger (polish-loop grounding + remaining fold-ins) 2026-06-29

**Owner:** Codex. **Reviewer:** Opus + operator. **Branch:** `codex/stress-fixes`. **Repo:** /home/openclaw.
Builds on `Operator/CODEX-ONE-KNOWLEDGE-LEDGER.md` (done: context_source + the contract test + agent
builders repointed + system_catalog ingest + Hermes inventory from ledger). Two gaps remain.

## PART A — ground the POLISH LOOP build packet in the ledger (operator's "the polish loop too")
The agent context packets now source from the ledger and are enforced by
`tests/test_context_packet_ledger_contract.py`. The **polish-loop builder context is NOT** — it's
assembled by `polish_loop/worker_runtime.py::build_task_package_markdown` (the build-task package the
local builder agent, ornith:9b, receives) and it does not touch `context_source` or the ledger. So the
code-building agent isn't grounded in the robust store.

**Fix:** have `build_task_package_markdown` pull a "what OpenClaw already has / where things live"
system-context section from the ledger via `context_source` (same source the agents use), so builds
reason over the real system instead of guessing. Keep it bounded/capped (the builder context is
already large — a tight ledger-grounded section, not a dump) and honor the ledger's
`corpus_sensitivity_labels` (no legal/vault/secret bodies into a build packet).
**Bring it under the guarantee:** either register the polish-loop build packet in
`context_packet_builder_registry` (so the contract test asserts ledger provenance on its system-context
facts too), or add a parallel contract test for build packets. The point: a polish-loop build packet
that bypasses the ledger must FAIL the build, same as the agent packets.
**Acceptance:** TDD — the contract (or a build-packet contract) covers the polish-loop packet and
asserts ledger provenance; a build-task package built in a test carries ledger-sourced system context.

## PART B — build fold-ingests for the 6 REMAINING satellites (so they can actually be retired)
`scripts/reconcile_knowledge_satellites.py` did a READ-ONLY diff and showed these satellites carry
UNIQUE data, but only `system_catalog.sqlite3` has a fold ingest. The rest have NO ingest, so their
unique data is NOT in the ledger and they MUST NOT be archived yet:
- `generated/system_knowledge/openclaw_system_knowledge_registry.sqlite` — 11 unique tables (the
  semantic gold: system_component, capability, agent_role, authority_boundary, known_unknown, etc.;
  `build_task` is a separate concern — skip it).
- `generated/system_knowledge/operator_controller_event_router.sqlite` — 5 unique tables.
- `generated/system_knowledge/proof_to_response_runtime.sqlite` — 6 unique tables.
- `generated/system_knowledge/sqlite_governance_registry.sqlite` — 3 unique tables (and this is the
  store to RECORD the "one knowledge ledger" policy in — see CODEX-ONE-KNOWLEDGE-LEDGER governance).
- `generated/system_knowledge/agentic_chain_inspector.sqlite` — 4 unique tables.
- `/mnt/e/openclaw/generated/read_models/openclaw_filesystem_atlas.sqlite` — 9 unique tables
  (atlas_runs, directory_inventory, graph_edges/nodes, inventory_roots, map_room_territories,
  move_candidates, repo_inventory — this feeds the Map Room).

**Fix:** build a fold-ingest per satellite (or one generic ledger-fold tool driven by the reconcile
output) that writes each satellite's UNIQUE tables into the ledger as `knowledge_*` tables with
provenance, mirroring `scripts/ingest_system_catalog_to_ledger.py`. Each is `--confirm`-gated and
NON-DESTRUCTIVE (write into the ledger; verify queryable; the operator archives the satellite only
after). After Part B, EVERY satellite has a verified fold path, so the archive step in the
one-knowledge-ledger results becomes safe to run for all of them.
**Acceptance:** a dry-run per satellite reports the target ledger table + row counts;
`--confirm` (operator-run) folds + verifies; the reconcile re-run shows `unique_fold_in == 0` for each
(everything now `already_present`). Do NOT self-`--confirm` prod writes — propose the operator commands.

## PART C — repoint the skill catalog default + make "fold" COMPLETE before archive (lesson learned)
Live incident 2026-06-30: archiving `system_catalog.sqlite3` broke skill matching, because the
ingest folded only `knowledge_repo_roots` (repos) and MISSED the `skills` table — `skill_loader`
read the ledger, found 0 skills, and the music-law skill went dark until the skill was re-persisted
into the ledger. Two durable fixes:
1. **Repoint `skill_loader.py` `DEFAULT_CATALOG_PATH`** from `/home/openclaw/system_catalog.sqlite3`
   (now archived) to the ledger `/home/openclaw/.openclaw/business_ops/ledger.sqlite`, so a no-arg
   `load_registered_skills()` cannot break. (The live packet path already passes the ledger explicitly
   via `maestro_context_packet._system_catalog_path`; this is defense-in-depth + correctness.) Make
   skill persistence write to the ledger by default too.
2. **A fold is only "done" when ALL of a satellite's unique tables are in the ledger AND every consumer
   of the old path is repointed/verified.** The reconcile must report `unique_fold_in == 0` across
   EVERY table (not a subset) before the operator archives, and the ingest tooling must enumerate the
   consumers of each satellite path (grep for the file path) and confirm none break post-archive.
   Add a `--verify` mode to the ingest/reconcile that fails if any unique table remains OR any live
   consumer still references the soon-to-be-archived path.
**Acceptance:** `load_registered_skills()` with no args returns the ledger skills; a pre-archive
`--verify` gate proves complete-fold + zero live consumers before any satellite is archived.

## Hard constraints
Non-destructive; operator-gated prod writes (propose commands, don't self-confirm); back up the ledger
before writes; reuse context_source/the existing ingest pattern; TDD; local-first; respect Guardian
gates; commit small on codex/stress-fixes; don't push.
## Output
`Operator/CODEX-LEDGER-FINISH-RESULTS.md` (per item: status, files, shas, tests, dry-run outputs,
operator commands).

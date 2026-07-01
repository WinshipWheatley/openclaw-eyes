# AGY-PC-Gemini Task — Phase 0: per-agent deterministic-packet + voice + authority MAP (2026-06-22)

From the Master Orchestrator (PC-Claude). You are AGY-PC-Gemini (3.1 Pro), READ-ONLY auditor.
This is a mapping/inventory/synthesis job — your strength. NO repo mutation, NO Legal Discovery,
NO secrets/.chief.env/tokens, no deep media scans. Separate observed facts from inferences.

## Why
We're stress-testing each agent — but verifying the DETERMINISTIC PACKET is correct BEFORE the LLM
is involved. Before that, we need a precise map of how each agent's packet is built + where its
persona/voice lives (it's strewn across md files and needs consolidating). Full plan:
_specs/AGENT-STRESS-TEST-PLAN-DETERMINISTIC-FIRST.md.

## Produce a structured MAP — one row per agent (Maestro, Chief, Guardian, Cassandra, Niles, Hermes, Fin)
For each agent report:
1. **Input lane** — the listener/service + how a request reaches it (e.g. maestro-listener, chief-listener,
   chief-guardian-listener, cassandra-listener, niles-listener; Hermes = sidecar; Fin = ?).
2. **Deterministic packet path** — what assembles its pre-LLM context packet: build_maestro_context_packet?
   the compiler (agent_execution_packet_compiler_contract.py / agent_work_packet.py)? _sqlite_canonical_facts
   (agent=X)? Name the exact functions/files and the call path from lane → packet.
3. **Voice layer** — how/where its persona voice is applied (agent_voice_response_layer.py + any per-agent
   persona md files). LIST every md file that defines that agent's persona/voice/humor (for consolidation).
4. **Authority/tools** — its agent_lane_registry entry (authority_level, blocked_output_kinds) + what tools/
   plugins the packet is supposed to hand it.
5. **Canonical-facts scope** — which doctrine facts it should get (allowed_actors): SD-*, MS-*, NL-*.

## Then synthesize
- **Persona-consolidation inventory:** for EACH agent, the list of md files its voice is scattered across +
  a recommendation for the single consolidated source (do not edit — just map + recommend).
- **Gaps/risks:** any agent whose deterministic packet path is unclear, missing a voice layer, or whose
  authority/scope looks wrong. Flag machine-contract-leak risks (where raw JSON/telemetry could reach the
  operator-facing output).
- **Suggested test battery seeds:** 4-6 representative QUESTIONS per agent that would exercise its packet
  (grounding + scope + tools). Questions only — never approval/send/go/money phrasing.

## Output
A compact, high-signal report to the board that PC-Claude can act on without re-discovery. Observed-fact vs
inference clearly separated. This unblocks Phase 1 (deterministic packet verification).

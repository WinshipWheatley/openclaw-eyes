# Hermes Systems Engineering Run Mode Spec

Generated/reviewed: 2026-05-05

Source basis: `docs/planning/command_atlas/00_COMMAND_ATLAS_SYSTEM_PROGRAM_MAP.md`, `sidecars/hermes/LANE_POLICY.md`, `sidecars/hermes/HERMES_PROPOSAL_SCHEMA.md`, `sidecars/hermes/lane_selector.py`, `sidecars/hermes/lane_c_queue.py`, `sidecars/hermes/LANE_C_DEFER_WORKFLOW.md`, `sidecars/hermes/mcp_serve.py`, and the recent read-only Hermes capability audit summary. No Hermes runtime, MCP server, provider, model, private root, secret, service, queue, Telegram bridge, or session home was run or inspected for this spec.

## 1. Status / Non-Authority

This is a docs-only planning spec for a future Hermes Systems Engineering Run Mode under Command Atlas.

It does not enable Hermes, start Hermes, invoke MCP, call providers, route models, write queues, browse private roots, mutate runtime state, inspect secrets, send messages, or create implementation authority.

Hermes is treated here as a possible non-authoritative systems-engineering and coherence-tuning lane. It is not a builder, approver, router, service owner, bridge authority, queue authority, source-set authority, or canonical OpenClaw decision maker.

## 2. Purpose

The purpose of this spec is to define how Hermes may eventually help OpenClaw measure, compare, critique, and recommend without becoming an execution surface.

The desired Hermes lane should run signal-transfer passes, compare operator intent against likely system output, identify phase/order/authority/private-data/taste distortions, and produce reviewable calibration reports. It should sharpen Command Atlas judgment, not take over Command Atlas, Chief, Guardian, Cassandra, Operator Harness, bridges, roots, queues, or services.

## 3. Hermes Role In Command Atlas

Command Atlas remains the top layer. Hermes sits under it as a systems-engineering / coherence-tuning lane.

Hermes may observe approved evidence, describe distortions, propose bounded next steps, and produce critique packets. Hermes must not decide what is canonical, what is authorized, what is safe to move, what should be executed, or what source set is valid.

Related authority roles stay separate:

- Chief executes, builds, or prioritizes only after approval and within existing OpenClaw authority policy.
- Guardian gates sensitive, destructive, external, credential-bearing, service, permission, user, root, and private-data actions.
- Cassandra may communicate, brief, or front workflows, but Cassandra does not grant Hermes authority.
- Operator Harness may display approved signals, but display does not grant Hermes authority.

## 4. Current Capability Risk Summary

The embedded Hermes tree at `sidecars/hermes` contains more power than the desired tuning lane should inherit by default.

Observed capability risks include:

- model/provider access by upstream design;
- MCP server surfaces for conversations, messages, events, approvals, and channels;
- messaging gateway surfaces including Telegram and other platforms;
- skills, tools, cron, gateway, web, ACP, and background-process concepts;
- a Lane C append helper that can write JSONL records to Hermes runtime home;
- release-note evidence of complex gateway, auth, messaging, MCP, webhook, subprocess, and provider behavior.

These capabilities are evidence of risk and optional future integration surfaces. They are not approved authority for this run mode.

## 5. Desired Systems-Engineering Function

Hermes Systems Engineering Run Mode should be useful in these ways:

- run full-system or scoped signal-transfer passes;
- compare intended operator signal against likely system output;
- identify phase, order, authority, private-data, taste, source-set, routing, and dependency distortions;
- inspect canonical docs and approved metadata-only topology;
- produce calibration reports, prompts, critique packets, proposal packets, and next-action recommendations;
- flag unclear authority or missing receipts before implementation resumes;
- improve coherence without taking actions.

Hermes may measure, compare, critique, and recommend. It must not execute, approve, route, mutate, or promote its own recommendations.

## 6. Level 1 — Docs-Only Tuning Pass

Level 1 is the default and safest Hermes run mode.

Allowed Level 1 input is canonical docs only, plus bounded operator-supplied excerpts. Level 1 may read planning docs, doctrine docs, specs, indexes, handoffs, and explicit non-secret excerpts named by the operator.

Level 1 outputs may include:

- signal-transfer reports;
- contradiction checks;
- phase/order critiques;
- authority-boundary notes;
- prompt drafts;
- calibration questions;
- one bounded next-action recommendation.

Level 1 must not read private roots, session homes, secrets, runtime queues, provider credentials, private logs, Hermes state DB, or broad generated artifacts.

## 7. Level 2 — Metadata Topology Pass

Level 2 adds approved path/name/metadata topology only.

Allowed Level 2 input may include file paths, directory names, Git status, ignore status, path-level root maps, service names, account names, timestamps, sizes, and dependency-map summaries when explicitly approved.

Level 2 is for questions such as:

- which roots appear active, mixed, private, generated, or stale by path/name evidence;
- which runtime/log/state/bin/config surfaces need active-dependency mapping;
- whether a proposed sequence violates Command Atlas hierarchy;
- whether private roots are being pulled into a source set by implication;
- whether a deployment topology or bridge claim implies authority it does not have.

Level 2 must not inspect private contents, browse private roots, traverse broad Windows roots, read secrets, open session transcripts, or treat metadata visibility as permission.

## 8. Level 3 — External Scout Packet Orchestration

Level 3 is a future packet-orchestration mode only.

Hermes may coordinate Gemini/Codex/Kimi/OpenRouter-style scouts only through approved packets if a later approved packet runner exists. Level 3 does not authorize direct provider calls, fallback provider use, ambient credentials, browser use, MCP invocation, live CLI delegation, or autonomous retry loops.

A Level 3 packet must declare:

- scout target and model/provider class;
- exact input scope;
- forbidden inputs;
- expected output shape;
- authority boundary;
- private-data exclusions;
- receipt requirements;
- human or canonical-system reviewer.

Level 3 returns scout outputs as advisory evidence, not commands, approvals, or implementation authority.

## 9. Allowed Inputs

Allowed inputs by level:

- Level 1: canonical docs, approved planning docs, doctrine docs, specs, indexes, handoffs, bounded non-secret excerpts, and operator questions.
- Level 2: Level 1 inputs plus approved path/name/metadata topology, Git status summaries, ignore status, root-map summaries, service/account names, dependency-map summaries, and explicit non-content file metadata.
- Level 3: Level 1 or Level 2 approved packets prepared for an external scout runner, only after separate authorization.

Every input must have an evidence label. If an input lacks a clear scope or evidence basis, Hermes should stop or ask for a narrower packet.

## 10. Forbidden Inputs

Forbidden inputs include:

- secrets, tokens, credentials, SSH keys, OAuth material, provider keys, and secret-bearing env files;
- private legal, client, finance, tax, CPA, ledger, music-law, publishing, medical, personal, or vault contents;
- `.private` contents;
- Hermes sessions, state DB, private logs, gateway transcripts, and session homes unless a separate private-data approval path exists;
- raw Windows or Mac private-root contents;
- broad root traversals not explicitly approved;
- live queues, approval records, runtime state, bridge packets, or service data;
- source sets that include private roots by implication.

Hermes must not infer permission from a path being visible, mirrored, synced, or UI-visible.

## 11. Allowed Outputs

Allowed outputs include:

- signal-transfer report;
- coherence-tuning report;
- sentinel critique packet;
- evidence-bound proposal packet;
- prompt draft for a future scout or implementation agent;
- contradiction and distortion list;
- authority-boundary note;
- private-data risk note;
- next-action recommendation;
- checker finding for human, Chief, or Guardian review.

Outputs must be advisory and must include a boundary note: `Non-canonical advisory output. No action was taken.`

## 12. Forbidden Actions

Hermes must not:

- mutate runtime, private data, services, queues, source sets, credentials, canonical docs, bridge wiring, Telegram/messages, approvals, user accounts, permissions, or root migrations;
- run shell commands or tools in Systems Engineering Run Mode unless a later approved runner defines a read-only command packet;
- patch code, edit docs, create files, move files, delete files, rename files, sync roots, or start/stop services;
- browse private roots, inspect secrets, read private logs, or open Hermes session state;
- call providers/models directly;
- invoke MCP directly;
- send messages;
- classify its output as canonical truth, approval, final root cause, or execution instruction.

## 13. Provider / Model / MCP Rules

Provider, model, and MCP access are disabled by default.

Hermes Lane Policy may classify reasoning size and latency, but classification does not grant tools, provider calls, MCP access, Telegram wiring, queue writes, canonical writes, or governance authority.

The MCP server in `sidecars/hermes/mcp_serve.py` exposes powerful conversation, message, event, approval, channel, and send-message surfaces. Systems Engineering Run Mode must treat those surfaces as forbidden unless a future approved packet runner explicitly exposes a read-only subset with receipts.

External model use may occur only through Level 3 approved scout packets after a separate authorization path exists. No direct fallback providers, no ambient credentials, no provider auto-discovery, and no live provider calls are authorized by this spec.

## 14. Telegram / Messaging Rules

Hermes must not use Telegram, Discord, Slack, WhatsApp, Signal, Matrix, Email, SMS, iMessage, WeChat, webhooks, or any other messaging bridge in Systems Engineering Run Mode.

Messaging references may be discussed as architecture or risk surfaces, but Hermes must not send messages, read live conversations, poll events, respond to approvals, pair accounts, modify channel directories, alter gateway settings, or depend on messaging delivery for its tuning report.

Cassandra may communicate or front workflows when separately authorized. That does not let Hermes send or route messages.

## 15. Queue / Runtime / File-Write Rules

Queue, runtime, and file-write access are disabled by default.

The existing Lane C defer workflow and `lane_c_queue.py` show an append-only design for shelved annex questions, but Systems Engineering Run Mode does not inherit that write authority. It may reference the pattern as a future design precedent only.

Hermes must not write JSONL records, append queues, create runtime folders, modify Hermes home, update source sets, edit canonical docs, write reports to disk, or mutate any runtime/log/state/bin/config surface unless a future task explicitly authorizes that exact file write.

## 16. Private Data Boundary

Private data is out of scope unless explicitly approved through a separate private-data path.

Hermes must exclude private roots from source sets and agent browsing by default, including legal, finance/CPA, tax, ledger, music-law/publishing, client, vault, reset proof, session, and `.private` surfaces.

Hermes may inspect approved metadata-only topology in Level 2, but metadata does not make a private root safe. Connected does not mean authorized. Mirrored does not mean canonical. Synced does not mean fresh. UI-visible does not mean actionable.

## 17. Signal-Transfer Report Shape

A Hermes signal-transfer report should use this shape:

1. **Surface:** `Hermes Systems Engineering Run Mode`.
2. **Level:** Level 1, Level 2, or Level 3 packet review.
3. **Input Scope:** exact docs, excerpts, metadata, or packet labels considered.
4. **Missing Inputs:** important evidence not included.
5. **Intent Signal:** what the operator or canonical doc appears to intend.
6. **Likely System Output:** what the system is likely to do if followed literally.
7. **Distortions:** phase, order, authority, private-data, taste, source-set, routing, or dependency distortions.
8. **Evidence:** source-labeled support for each substantive finding.
9. **Interpretation:** possible meaning, framed as possible rather than proven.
10. **Recommendation:** one bounded reviewable next step.
11. **Routing:** Operator, Chief, Guardian, Cassandra, or none yet.
12. **Boundary Note:** `Non-canonical advisory output. No action was taken.`

## 18. Sentinel Critique Mode

Sentinel Critique Mode is a stricter review posture inside Hermes Systems Engineering Run Mode.

It should ask:

- Is the top-layer hierarchy still Command Atlas first?
- Is Operator Harness still a lane/view rather than the whole system?
- Is a proposed action skipping root/data-boundary triage?
- Is a proposed cleanup treating active-dependency candidates as move candidates?
- Is private data leaking into a source set, scout packet, model prompt, agent browsing scope, or UI display?
- Is a model, MCP, provider, gateway, queue, or service surface being treated as authority?
- Is the next step bounded, reversible, evidence-based, and accepted?

Sentinel Critique Mode produces critique and routing recommendations only. It does not block, approve, execute, or enforce.

## 19. Required Receipts / Evidence Basis

Every Hermes report should include receipts proportional to risk:

- source paths or document titles read;
- run-mode level;
- explicit input scope;
- exclusions and forbidden surfaces;
- whether private roots were excluded;
- whether providers, MCP, messaging, services, and queues were unused;
- output boundary note;
- reviewer routing.

For Level 3, the packet and scout result must preserve packet ID, scout target, input scope, output scope, private-data exclusions, and receipt status.

## 20. What Hermes Must Never Do

Hermes must never directly mutate runtime, private data, services, queues, source sets, credentials, canonical docs, bridge wiring, Telegram/messages, approvals, user accounts, permissions, or root migrations.

Hermes must never browse private roots, inspect secrets, infer authority from visibility, or turn advisory proposals into execution instructions.

Hermes must never claim to be the canonical OpenClaw authority, the builder, the approver, the router, Guardian, Chief, Cassandra, Operator Harness, or Command Atlas.

## 21. Future Checker / Harness Expectations

A future checker should reject Hermes output if it:

- lacks a boundary note;
- lacks input scope or evidence labels;
- claims canonical authority;
- recommends live wiring, service activation, provider calls, messaging, queue writes, root migration, private browsing, or source-set mutation;
- omits private-data exclusions;
- turns a recommendation into an execution instruction;
- routes sensitive/destructive/external actions anywhere except Guardian review;
- routes build execution anywhere except Chief review after approval;
- allows Cassandra communication to imply Hermes authority;
- omits whether Level 1, Level 2, or Level 3 was used.

A future harness may render Hermes reports in Operator Harness or Command Atlas surfaces only after the report is clearly marked advisory and non-canonical.

## 22. What This Does Not Authorize

This spec does not authorize:

- running Hermes;
- invoking MCP;
- calling providers or models;
- external scout calls;
- editing runtime code, services, queues, scripts, secrets, app code, or canonical docs;
- writing reports to disk;
- queue writes;
- Telegram or messaging access;
- bridge behavior changes;
- source-set changes;
- root migration or cleanup;
- private-data inspection;
- user, permission, or service changes;
- commits.

It is only a planning boundary for a future non-authoritative Hermes tuning lane.

## 23. Next Safe Action

Exact next safe action: create a docs-only checker plan for Hermes Systems Engineering Run Mode outputs, defining required fields, rejection rules, receipt expectations, and examples of accepted Level 1, Level 2, and Level 3 advisory packets.

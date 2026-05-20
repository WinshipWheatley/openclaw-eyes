# Operator Awareness Nested Lane + Mission Package Spine v0

Status:
- Deterministic nested-lane and mission-package read-model contract only.
- Extends the existing Operator Awareness + Agent Package Spine; it does not replace the gap-item spine.
- No live chat, agent, actor/model, tool, plugin, browser, OAuth, account, send, submit, approval, Mission Control app, Repo B, or runtime authority is added.

## Top-Level Lane
- `system_awareness_discovery`: System Awareness / Discovery.
- Job: show what OpenClaw knows, partly knows, knows it does not know, has not discovered, needs Winship memory comparison for, and must classify or block.
- Current helm mode: `DEVELOPER_MODE_BUILD_MODE`; noisy because OpenClaw is still being assembled.
- Next safe detour: Operator Memory Comparison or Discovery/Classification detour for one named missing item.

## Nested Lanes
- `chief`: Chief | attention `NEEDS_DISCOVERY_CLASSIFICATION` | confidence `MEDIUM_TRUST` | detour `Chief Test Harness Capability Classification`
- `cassandra`: Cassandra | attention `NEEDS_PROOF` | confidence `MEDIUM_TRUST` | detour `Cassandra Draft Identity Reference Rail or Capital Hilton Protected Proof Metadata Population`
- `guardian`: Guardian | attention `QUIET` | confidence `HIGH_TRUST` | detour `Guardian package review only when a future lane asks for clearance metadata.`
- `niles`: Niles | attention `NEEDS_CONTEXT` | confidence `MEDIUM_TRUST` | detour `Niles Real Album Metadata Intake`
- `hermes`: Hermes | attention `NEEDS_OPERATOR_MEMORY_COMPARISON` | confidence `LOW_TRUST` | detour `Hermes Status Memory/Proof Review`
- `repo_b_leftovers`: Repo B leftovers | attention `NEEDS_DISCOVERY_CLASSIFICATION` | confidence `UNKNOWN_FAIL_CLOSED` | detour `Repo B Leftover Classification Packet`
- `mission_control_design_memory`: Mission Control design memory | attention `NEEDS_CONTEXT` | confidence `HIGH_TRUST` | detour `Mission Control Design Memory Classification Packet`
- `capital_hilton`: Capital Hilton | attention `NEEDS_PROOF` | confidence `MEDIUM_TRUST` | detour `Capital Hilton Protected Proof Metadata Population`
- `struna`: Struna | attention `NEEDS_CONTEXT` | confidence `MEDIUM_TRUST` | detour `Struna Project Metadata Classification`
- `cue_parser_brain_dump_parser`: Cue parser / brain dump parser | attention `NEEDS_DISCOVERY_CLASSIFICATION` | confidence `LOW_TRUST` | detour `Cue Parser Intake Classification`
- `tool_plugin_registry`: Tool/plugin registry | attention `NEEDS_CONTEXT` | confidence `HIGH_TRUST` | detour `Tool/Plugin Registry Capability Classification`
- `model_router`: Model router | attention `NEEDS_DISCOVERY_CLASSIFICATION` | confidence `LOW_TRUST` | detour `Model Actor Candidate Classification`
- `future_domain_workflow_lanes`: Future domain/workflow lanes | attention `NEEDS_DISCOVERY_CLASSIFICATION` | confidence `UNKNOWN_FAIL_CLOSED` | detour `Future Domain Lane Classification`

## Sublane Exposure
- Each sublane should expose: known, partly_known, known_unknown, not_discovered, needs_winship_memory_comparison, blocked_not_authorized, safe_next_detour, confidence_level, package_available, what_would_make_lane_quiet.
- Operator memory comparison may identify a gap, but it is not truth by itself.
- Package available means previewable metadata; it does not mean dispatchable execution.

## Actor / Agent / Package
- Actor/model: The language model is the actor.
- Agent/character: The agent is the character/persona the actor plays, such as Chief, Cassandra, Guardian, Niles, or Hermes.
- Package: The package is the script, role sheet, context, tools/capabilities metadata, clearance, steps, stop conditions, boundaries, and proof/receipt requirements.
- Candidate model labels are metadata only: Gemini 5.4 / 5.5, Gemini 3.1 Pro, Gemini Flash, Gemini Flash Lite.

## Mission Package Fields
- actor_model_candidate, agent_character, mission, stakes_why_it_matters, context_included, context_excluded, plugins_capabilities_allowed, plugins_capabilities_forbidden, security_clearance, steps, stop_conditions, proof_receipt_requirements, confidence_inputs, detour_path_if_confidence_insufficient, chat_workspace_target, authority_boundary.
- Package hash placeholder: `sha256:5c15920626974bc7927f8ace156dfa14dcf593faa73d14ffd8b38041890711f0`.

## Deterministic vs Future-Gated
- Deterministic now: nested lane grammar, package field contract, confidence/detour posture, source references, and operator Markdown.
- Future-gated: live chat/workspace launch, actor/model execution, agents, plugins/tools, accounts, sends, approvals, and runtime execution.

## Check-Engine vs Lane Attention
- Lane attention: A domain/workflow needs operator attention, more classification, more context, proof, or build-out.
- Check-engine: The OpenClaw system itself is malfunctioning, stale, unsafe, blocked, internally inconsistent, or failing proof/trust.
- Check-engine becomes a Chief diagnostic/package problem.

## Quiet Helm
- Quiet condition: All lanes are fully tracked, parked on purpose, or blocked with proof, and no check-engine state is active.
- A quiet lane is fully understood, intentionally parked, or explicitly blocked, and does not keep demanding operator attention.

## Mission Control Can Show Now
- The System Awareness / Discovery top lane.
- Nested sublanes and their known/partial/known-unknown/undiscovered/blocked posture.
- Actor/model versus agent/character distinction.
- Mission package fields and package-preview-only body.
- Confidence and bounded detour recommendations.
- Check-engine versus normal lane-attention distinction.
- Future-gated chat/workspace target metadata.

## Future-Gated
- live chat/workspace launch
- model actor execution
- agent activation
- plugin/tool wiring
- browser/OAuth/account access
- Gmail/calendar/Coupa/Telegram access
- send/submit/approval/runtime authority
- broad old .md/chat/design archive ingestion
- Mission Control app code changes

## SQLite / Ledger Receipt
- Existing safe pattern: `business_ops_ledger.record_receipt`.
- Receipt meaning: metadata-only `generated_status`, receipt-record-only, no runtime authority.
- Raw prompt/chat/design archive bodies are not stored.

## Next Safe Lane
- Mission Control Nested Lane Readback and Awareness Map Surface v0

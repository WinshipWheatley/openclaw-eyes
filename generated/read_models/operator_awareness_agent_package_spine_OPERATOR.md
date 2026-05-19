# Operator Awareness + Agent Package Spine Contract v0

Status:
- Deterministic read-model contract only.
- Primary human layers: ELI5 current truth and human operator detail.
- Machine proof stays underneath.
- Package preview exists, but no agent, actor, model, tool, browser, OAuth, account, send, or runtime authority is added.

## ELI5 Summary
- OpenClaw remembers durable facts and posture in SQLite-backed records and generated read-models.
- Mission Control should show what OpenClaw knows, partly knows, knows it does not know, and has not discovered yet.
- Winship compares that map against memory to spot missing X without memory becoming truth by itself.
- Missing things become safe discovery/classification work, then tracked read-model data or explicit blockers.
- Agents/characters such as Chief, Cassandra, Guardian, Niles, Hermes, and Report Bridge interpret domain context.
- Actors/models are only future performers of a role; this contract stores recommendation metadata, not execution.
- Mission Control should display deterministic human-readable truth from the package, not hand-authored Swift guesses.
- Machine proof stays underneath as source read-models, receipts, classifications, blockers, and boundaries.
- The package preview shows what context would be sent later, including included and excluded surfaces.
- When trust is full, confidence stays display-quiet.
- When trust is not full, the helm should explain what is missing and what would raise confidence.
- A detour is a small bounded workspace for adding memory, context, proof, or classification before running or sending anything.
- Nothing live runs from this contract: no model call, tool, agent, browser, OAuth, Gmail, calendar, Coupa, send, or runtime authority.

## Current Truth
- Knows: Capital Hilton, Cassandra, Chief, Guardian, Niles/Struna, protected proof references, work packets, and cross-repo awareness are visible as read-model-backed surfaces. Review packets, proof rails, approval request specs, work-board cards, dropped intents, and capability metadata can be shown as deterministic posture.
- Partly knows: Capital Hilton needs Coupa/Excel proof, Niles needs real album metadata, Hermes status needs memory/proof review, Google/Apple calendar merge needs clarification, Agentic loop workflow needs discovery/classification, Chief test harness needs discovery/classification, Brain-dump / cue parser needs discovery/classification, Repo B leftovers need tagging or blocking
- Knows it does not know: Capital Hilton needs Coupa/Excel proof, Niles needs real album metadata, Hermes status needs memory/proof review, Google/Apple calendar merge needs clarification, Agentic loop workflow needs discovery/classification, Chief test harness needs discovery/classification, Brain-dump / cue parser needs discovery/classification, Repo B leftovers need tagging or blocking
- Has not discovered yet: Capital Hilton needs Coupa/Excel proof, Niles needs real album metadata, Hermes status needs memory/proof review, Google/Apple calendar merge needs clarification, Agentic loop workflow needs discovery/classification, Chief test harness needs discovery/classification, Brain-dump / cue parser needs discovery/classification, Repo B leftovers need tagging or blocking
- Winship memory comparison: Capital Hilton needs Coupa/Excel proof, Niles needs real album metadata, Hermes status needs memory/proof review, Google/Apple calendar merge needs clarification, Agentic loop workflow needs discovery/classification, Chief test harness needs discovery/classification, Brain-dump / cue parser needs discovery/classification, Repo B leftovers need tagging or blocking
- Blocked: Capital Hilton needs Coupa/Excel proof, Niles needs real album metadata, Hermes status needs memory/proof review, Google/Apple calendar merge needs clarification, Agentic loop workflow needs discovery/classification, Chief test harness needs discovery/classification, Brain-dump / cue parser needs discovery/classification, Repo B leftovers need tagging or blocking
- Next safe move: Show the awareness map, let Winship identify missing X, then use a bounded non-live detour to classify or capture proof before package use.

## Awareness Gap Items
- `capital_hilton_coupa_excel_proof`: Capital Hilton needs Coupa/Excel proof | confidence `MEDIUM_TRUST` | detour `Capital Hilton Protected Proof Metadata Population`
- `niles_real_album_metadata`: Niles needs real album metadata | confidence `MEDIUM_TRUST` | detour `Niles Real Album Metadata Intake`
- `hermes_status_memory_proof_review`: Hermes status needs memory/proof review | confidence `LOW_TRUST` | detour `Hermes Status Memory/Proof Review`
- `google_apple_calendar_merge_clarification`: Google/Apple calendar merge needs clarification | confidence `LOW_TRUST` | detour `Calendar Context Discovery / Memory Comparison`
- `agentic_loop_workflow_classification`: Agentic loop workflow needs discovery/classification | confidence `UNKNOWN_FAIL_CLOSED` | detour `Agentic Loop Workflow Classification`
- `chief_test_harness_classification`: Chief test harness needs discovery/classification | confidence `LOW_TRUST` | detour `Chief Test Harness Capability Classification`
- `brain_dump_cue_parser_classification`: Brain-dump / cue parser needs discovery/classification | confidence `LOW_TRUST` | detour `Cue Parser Intake Classification`
- `repo_b_leftovers_tag_or_block`: Repo B leftovers need tagging or blocking | confidence `UNKNOWN_FAIL_CLOSED` | detour `Repo B Leftover Classification Packet`

## Button Metadata
- `INSPECT_LARGER_DESCRIPTION`: Inspect Larger Description (READ_ONLY)
- `SHOW_PACKAGE_PREVIEW`: Show Package Preview (READ_ONLY)
- `WHY_NOT_FULL_CONFIDENCE`: Why Not Full Confidence? (READ_ONLY)
- `DETOUR_TO_RAISE_CONFIDENCE`: Detour to Raise Confidence (FUTURE_GATED)
- `PROCEED_ANYWAY_IF_SAFE`: Proceed Anyway, if safe (FUTURE_GATED)
- `KEEP_PARKED`: Keep Parked (CAPTURE_ONLY)
- `MARK_NEEDS_OPERATOR_MEMORY_COMPARISON`: Mark Needs Operator Memory Comparison (CAPTURE_ONLY)
- `START_DISCOVERY_CLASSIFICATION`: Start Discovery/Classification (FUTURE_GATED)

## Package And Confidence
- Package hash placeholder: `sha256:f0daad9120da4c883502d586b213a32f03c02196c5d099196b4d9c306db22707`.
- Overall confidence posture: `MEDIUM_TRUST`.
- Confidence visible in helm: `true`.
- Full trust display policy: confidence is quiet when posture is `FULL_TRUST_DISPLAY_QUIET`.

## Boundaries
- Operator memory may identify gaps, but it is not treated as proof or truth.
- Unknown or missing context fails closed.
- Detours are bounded and non-live.
- No Repo B body inspection, Repo B execution, tools, agents, models, browser, OAuth, credentials, Gmail, calendar, Coupa, sends, Mission Control app changes, security pass, or runtime authority were added.

## Next Recommended Lanes
- Hermes Status Memory/Proof Review
- Calendar Context Discovery / Memory Comparison
- Repo B Leftover Classification Packet

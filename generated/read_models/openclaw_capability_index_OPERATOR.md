# OpenClaw Capability Index

Status: CAPABILITY_INDEX_READY
Headline: Portable capability index ready

OpenClaw indexed generic capabilities separately from workflow bindings and fixtures. The index is safe for intent validation and gap discovery, but it grants no live authority.

## Counts
- Generic capabilities: 26
- Live implemented local rails: 4
- Contract only: 3
- Future gated: 1
- Blocked unsafe: 1
- Workflow bindings: 5
- Fixture/example records: 5
- Proposal candidates: 3

## Top Generic Capabilities
- request_processing
- request_response_service
- route_aware_heartbeat
- file_metadata_intake
- protected_secret_intake
- status_readback
- workflow_package_compilation
- dry_run
- completion_proof_aggregation
- outbound_message_draft

## Top Gaps
- gap:live_lm_intent_interpreter
- gap:live_portal_submit_adapter
- gap:live_video_generation

## Quarantined Proposals
- proposal:client_cockpit_visual_event_renderer
- proposal:outbound_message_draft_binding_adapter
- proposal:source_ref_parser_fixture_binding

## Boundary
- No live capability execution.
- No registry mutation.
- No model call or agent dispatch.
- No workflow run or external action.
- No secret reveal, credential handling, or raw-body ingestion.

Next safe move: Use tenant-filtered query results when binding capabilities to real workflow context.

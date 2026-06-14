# Known Unknowns

Status: UNKNOWN

## Short human summary
This page aggregates explicit unknowns, missing proof, unavailable inputs, and fail-closed states surfaced by the local registries/read-models.

## Confirmed facts
- Known unknown count: 14.
- Unknowns are not resolved by prose; upstream evidence must change.

## Known unknowns
- Why Codex Web commits were not reachable from GitHub remotes. [generated/read_models/openclaw_estate_topology_registry.json]
- Whether Mac app should get a GitHub remote and backup/PR flow. [generated/read_models/openclaw_estate_topology_registry.json]
- Whether PC /home/openclaw and Mac /Users/.../Eyes should both track openclaw-eyes long-term. [generated/read_models/openclaw_estate_topology_registry.json]
- Whether openclaw-runtime should be the canonical home for Chief/Cassandra/Guardian runtime. [generated/read_models/openclaw_estate_topology_registry.json]
- Which repo Hermes should read first for estate-wide task planning. [generated/read_models/openclaw_estate_topology_registry.json]
- How Mac bridge permission failures should be represented. [generated/read_models/openclaw_estate_topology_registry.json]
- missing_proof: Live Arts MD manual send receipt [generated/read_models/chief_dynamic_workflow_deferred_build.json]
- capability_gaps: Gmail/Safari DOM automation is low confidence [generated/read_models/chief_dynamic_workflow_deferred_build.json]
- operator_decisions_required: Approve final workflow orchestrator rules [generated/read_models/chief_dynamic_workflow_deferred_build.json]
- required_facts: Live Arts MD manual send proof capture [generated/read_models/chief_dynamic_workflow_deferred_build.json]
- unsafe_claims: Invoice sent [generated/read_models/chief_dynamic_workflow_deferred_build.json]
- unsafe_claims: Ledger updated [generated/read_models/chief_dynamic_workflow_deferred_build.json]
- Intent: Hermes, synthesize current posture. [generated/read_models/build_now_vs_hold_queue_posture.json]
- Mission Control read-model refresh [generated/read_models/build_now_vs_hold_queue_posture.json]

## Tension / contradiction signals
- Reference target unavailable: estate_topology_registry_read_model_mirror resolved as MISSING.
- Mac local path unreachable from PC: /Users/hwinshipwheatley/Eyes is marked LOCAL_PATH_UNREACHABLE.
- Mac bridge unavailable: openclaw_eyes_registry_review_branch has mac_bridge_status=MAC_BRIDGE_UNAVAILABLE.
- Mac bridge unavailable: openclaw_eyes_main_branch has mac_bridge_status=MAC_BRIDGE_UNAVAILABLE.
- Codex Web commit unreachable: openclaw-eyes commit 33e00a6 is recorded as unreachable.
- Codex Web commit unreachable: openclaw-eyes commit 4ca4ed42171c23d60ef89493559808ef2789a19e is recorded as unreachable.
- Workflow readiness conflicts with attachment or approval: live_arts_md_bundle says ready but attachment_ready or approval_ready is false/missing.
- PDF export package missing required fields: live_arts_md_bundle.developer_end_to_end_card is PDF export ready but missing: invoice_id, selected_sheet_label, output_bridge_path.
- Artifact placeholder is not selected-invoice proof: /mnt/e/openclaw/artifacts/invoice_workbooks/live_arts_md_invoice_2026-1001.pdf is marked INVALID_PLACEHOLDER and not trusted as selected invoice artifact.
- Artifact placeholder is not selected-invoice proof: /Users/hwinshipwheatley/Desktop/Live_Arts_MD_Speaker_Rental_Invoice_September_May_2026.pdf is marked NOT_TRUSTED_EXISTING_MULTI_PAGE_PDF and not trusted as selected invoice artifact.

## Next useful actions
- Resolve unknowns in the owning registry/read-model or receipt source.
- Prefer operator confirmation only when repo evidence says operator memory/review is required.
- Regenerate after upstream evidence changes.

## What not to do
- Do not infer answers to unknowns in generated Markdown.
- Do not treat missing inputs as present.
- Do not erase contradictions for readability.

## Source refs / input read-model refs
- generated/system_knowledge/openclaw_estate_topology_registry.sqlite (estate_topology_registry_sqlite)
- generated/read_models/openclaw_estate_topology_registry.json (estate_topology_registry)
- generated/system_knowledge/openclaw_reference_resolver.sqlite (reference_resolver_sqlite)
- generated/read_models/openclaw_reference_resolver.json (reference_resolver)
- generated/read_models/external_system_knowledge_registry_index.json (external_system_knowledge_registry_index)
- generated/read_models/openclaw_authority_semantics_registry.json (authority_semantics_registry)
- generated/read_models/openclaw_business_object_layer_audit.json (business_object_layer_audit)
- generated/read_models/openclaw_lane_capability_harvest.json (lane_capability_harvest)
- generated/read_models/live_arts_md_invoice_review_bundle.json (live_arts_md_invoice_review_bundle)
- generated/read_models/invoice_review_bundle.json (invoice_review_bundle)
- generated/read_models/hermes_mission_sentinel.json (hermes_mission_sentinel)
- generated/read_models/hermes_chief_build_handoff.json (hermes_chief_build_handoff)
- generated/read_models/purpose_bound_automation_charter.json (purpose_bound_automation_charter)
- generated/read_models/hermes_gravity_controller.json (hermes_gravity_controller)
- generated/read_models/chief_dynamic_workflow_deferred_build.json (chief_dynamic_workflow_deferred_build)
- generated/read_models/openclaw_estate_node_registry.json (openclaw_estate_node_registry)
- generated/read_models/estate_topology.json (estate_topology)
- generated/read_models/build_now_vs_hold_queue_posture.json (build_now_vs_hold_queue_posture)
- generated/read_models/work_terrain_build_cue_reconciliation_queue.json (work_terrain_build_cue_reconciliation_queue)
- generated/external_registries/openclaw-eyes/openclaw_system_knowledge_registry.json (openclaw_system_knowledge_registry_ff49c5bc4e)
- generated/external_registries/openclaw-eyes/openclaw_system_knowledge_registry.sqlite (openclaw_system_knowledge_registry_61df5235c0)
- generated/external_registries/openclaw-eyes/openclaw_system_knowledge_registry_OPERATOR.md (openclaw_system_knowledge_registry_fc9549f5cc)
- generated/external_registries/openclaw-eyes/openclaw_system_knowledge_registry_SCHEMA.sql (openclaw_system_knowledge_registry_d500da978d)
- generated/external_registries/openclaw-eyes/openclaw_system_knowledge_registry_SEED.sql (openclaw_system_knowledge_registry_b7961063f8)

Last generated timestamp: 2026-05-31T21:39:09+00:00

Generated understanding view. Registry/read-models/receipts remain source of truth.

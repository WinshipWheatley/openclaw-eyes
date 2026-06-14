# OpenClaw Context Wiki

Status: CONFIRMED

## Short human summary
This is a generated, evidence-grounded Markdown view over local OpenClaw registries and read-models. It is for browsing and orientation only; registry/read-model/receipt sources win on every disagreement.

## Confirmed facts
- SQLite/read-models/receipts are source of truth; generated wiki pages are views.
- Regenerate with `python3 scripts/export_openclaw_context_wiki.py`.
- Compiler v0 does not use an LM and does not synthesize unsupported claims.
- The compiler writes generated wiki pages plus generated/read_models/openclaw_context_wiki_index.json and generated/read_models/openclaw_context_wiki_index_OPERATOR.md.
- The compiler boundary flags explicitly deny service starts, email, browser, Coupa, workbook reads, PDF export, ledger mutation, production mutation, and git publication.
- Pages generated: 12.
- Business-object audit freshness: FRESH.
- Business-object audit generated_at: 2026-05-31T21:35:23+00:00.
- Business-object audit inputs tracked: 14.
- Business-object audit missing inputs: none.
- Business-object audit stale reasons: none.

## Known unknowns
- none

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
- Regenerate after upstream registries/read-models change.
- Fix upstream registries or read-models when the wiki disagrees with evidence.
- Review generated/read_models/openclaw_context_wiki_index_OPERATOR.md for a compact operator summary.

## What not to do
- Do not manually edit generated wiki pages as source truth.
- Do not use the wiki to override SQLite registries, read-models, or receipts.
- Do not infer sent, paid, approved, exported, submitted, or reachable states without source evidence.
- Do not add live automation or LM calls to v0.

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

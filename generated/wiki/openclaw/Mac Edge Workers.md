# Mac Edge Workers

Status: PARTIAL

## Short human summary
Mac edge work is represented as scoped local execution/helper responsibility. PC emits safe packages/read-models; Mac owns Excel/PDF helper and app-side permission architecture.

## Confirmed facts
- Mission Control app: owner=openclaw-mission-control / MAC_APP; status=CONFIRMED; rule=Swift app source belongs in the Mac app repo.
- Mac Excel Edge Worker: owner=openclaw-mission-control / MAC_APP; status=CONFIRMED; rule=Mac-local Excel/PDF helper code belongs with the Mac app/helper architecture.
- Access Broker: owner=split / SPLIT_MAC_UI_BACKEND_POLICY; status=PARTIAL; rule=Swift UI surface belongs in Mac app; policy/registry side belongs in backend when present.
- bridge/mirror transport: owner=transport / BRIDGE_TRANSPORT; status=PARTIAL; rule=/mnt/e/openclaw <-> /Volumes/openclaw_e is transport, not source truth.
- Mac Excel PDF edge worker package: required_capability=MAC_EXCEL_PDF_EXPORT; execution_venue=MAC_LOCAL; no_workbook_cell_read=True.
- Access requirements: ['WORKBOOK_ACCESS', 'OUTPUT_FOLDER_PERMISSION', 'APPLE_EVENTS']; permission repair action=Grant file/folder access via Access Broker.

## Known unknowns
- Access Broker remains PARTIAL: Do not collapse UI and policy ownership into one repo without evidence.
- bridge/mirror transport remains PARTIAL: Mac bridge permission failures are represented as partial access on the Mac bridge path.
- Whether Mac app should get a GitHub remote and backup/PR flow. [generated/read_models/openclaw_estate_topology_registry.json]
- Whether PC /home/openclaw and Mac /Users/.../Eyes should both track openclaw-eyes long-term. [generated/read_models/openclaw_estate_topology_registry.json]
- How Mac bridge permission failures should be represented. [generated/read_models/openclaw_estate_topology_registry.json]

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
- Resolve Access Broker/helper permission shape before retrying Mac Excel export.
- Keep Mac helper work local, scoped, and receipt-backed.
- Mirror generated read-models only after bridge access is verified.

## What not to do
- Do not run Mac Excel/PDF export from the PC wiki compiler.
- Do not make Mac local paths reachable claims from PC when resolver marks them unreachable.
- Do not grant UI, helper, or file permissions implicitly.

## Source refs / input read-model refs
- generated/read_models/openclaw_estate_topology_registry.json (estate_topology_registry)
- generated/read_models/openclaw_reference_resolver.json (reference_resolver)
- generated/read_models/live_arts_md_invoice_review_bundle.json (live_arts_md_invoice_review_bundle)

Last generated timestamp: 2026-05-31T04:30:01+00:00

Generated understanding view. Registry/read-models/receipts remain source of truth.

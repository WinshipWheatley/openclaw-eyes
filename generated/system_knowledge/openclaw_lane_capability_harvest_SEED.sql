INSERT INTO lane VALUES ('live_arts_md_invoice_lane', 'Live Arts MD invoice lane', 'invoice', 'live_arts_md', 'live_arts_md_invoice_workflow', 'ACTIVE_STEEL_THREAD', 'Selected invoice and scoped PDF package are present; proof, approval, send, and payment remain gated.', '/home/openclaw PC_BACKEND', '[
  "generated/read_models/live_arts_md_invoice_review_bundle.json",
  "live_arts_md_invoice_review_bundle.py",
  "simple_invoice_event_bridge_rail_registry.py"
]', 'Current mini steel thread for simple invoice state, Event Bridge action, PDF package, manual proof, payment watch, and authority boundary.', 'Reuse the selected-invoice state path, scoped artifact package, Event Bridge action shape, and no-authority guard pattern.');
INSERT INTO lane VALUES ('capital_hilton_invoice_lane', 'Capital Hilton invoice lane', 'complex_invoice', 'capital_hilton', 'capital_hilton_invoice_workflow', 'PARTIAL', 'Complex invoice rail is partially modeled and blocked on invoice selection, supplier portal/Coupa proof, artifact, and approval gates.', '/home/openclaw PC_BACKEND', '[
  "generated/read_models/invoice_review_bundle.json",
  "generated/read_models/capital_hilton_invoice_delivery_steel_thread.json",
  "capital_hilton_invoice_delivery_steel_thread.py"
]', 'Next lane should reuse invoice rails while adding supplier portal proof, PO/Coupa posture, multi-invoice review, and approval complexity.', 'Keep supplier portal and Coupa capabilities as extensions, not defaults for simple invoice lanes.');
INSERT INTO lane VALUES ('st_annes_invoice_lane', 'St. Anne''s invoice lane', 'simple_invoice', 'st_annes', 'st_annes_invoice_workflow', 'PARTIAL', 'Planned simple-invoice generalization with fixtures and Event Bridge handler evidence, but no completed business lane.', '/home/openclaw PC_BACKEND', '[
  "simple_invoice_workflow_fixtures.py",
  "client_invoice_workflow_framework.py",
  "generated/read_models/simple_invoice_event_bridge_rail_registry.json",
  "generated/read_models/openclaw_event_bridge_contract.json"
]', 'After Capital Hilton, prove the simple invoice rail generalizes without inheriting Coupa, supplier portal, or PO blockers.', 'Use the same simple rail and explicitly exclude Capital Hilton-specific portal/PO extensions.');
INSERT INTO harvested_capability VALUES ('capability:simple_invoice_rail', 'Simple invoice rail', 'WORKFLOW_RAIL', 'live_arts_md_invoice_lane', 'PROVEN', 1, '[
  "capital_hilton_invoice_lane",
  "st_annes_invoice_lane",
  "recurring_invoice_workflow"
]', '[]', '[
  "generated/read_models/simple_invoice_event_bridge_rail_registry.json",
  "client_invoice_workflow_framework.py"
]', '[
  "tests/test_simple_invoice_event_bridge_rail_registry.py",
  "tests/test_client_invoice_workflow_framework.py"
]', 'Simple clients must not inherit Coupa, PO, or supplier portal blockers by default.');
INSERT INTO harvested_capability VALUES ('capability:invoice_candidate_selection', 'Invoice candidate selection and collapse', 'WORKFLOW_RAIL', 'live_arts_md_invoice_lane', 'PROVEN', 1, '[
  "st_annes_invoice_lane",
  "recurring_invoice_workflow"
]', '[]', '[
  "generated/read_models/live_arts_md_invoice_review_bundle.json"
]', '[
  "tests/test_simple_invoice_event_bridge_rail_registry.py"
]', '');
INSERT INTO harvested_capability VALUES ('capability:selected_invoice_summary_state', 'Selected invoice summary state', 'DATA_ACCESS_PATTERN', 'live_arts_md_invoice_lane', 'PROVEN', 1, '[
  "st_annes_invoice_lane",
  "capital_hilton_invoice_lane"
]', '[]', '[
  "generated/read_models/live_arts_md_invoice_review_bundle.json"
]', '[
  "tests/test_openclaw_business_object_layer_audit.py"
]', '');
INSERT INTO harvested_capability VALUES ('capability:event_bridge_prepare_pdf_action', 'Event Bridge Prepare PDF action', 'EVENT_BRIDGE_ACTION', 'live_arts_md_invoice_lane', 'PARTIAL', 1, '[
  "st_annes_invoice_lane",
  "capital_hilton_invoice_lane",
  "Telegram compact invoice action"
]', '[]', '[
  "generated/read_models/openclaw_event_bridge_contract.json",
  "openclaw_event_bridge_adapter.py"
]', '[
  "tests/test_openclaw_event_bridge_contract.py"
]', 'Must keep authority_boundary false-valued and no-authority guards in the allowed guard fields.');
INSERT INTO harvested_capability VALUES ('capability:pdf_artifact_package', 'Scoped PDF artifact package', 'ARTIFACT_POLICY', 'live_arts_md_invoice_lane', 'PARTIAL', 1, '[
  "st_annes_invoice_lane",
  "capital_hilton_invoice_lane"
]', '[]', '[
  "generated/read_models/live_arts_md_invoice_review_bundle.json"
]', '[
  "tests/test_openclaw_business_object_layer_audit.py"
]', 'Reusable package policy is present; Mac Excel export/helper path remains separately gated.');
INSERT INTO harvested_capability VALUES ('capability:manual_send_proof', 'Manual send proof receipt', 'PROOF_RECEIPT', 'live_arts_md_invoice_lane', 'PARTIAL', 1, '[
  "st_annes_invoice_lane",
  "client_comms_follow_up"
]', '[]', '[
  "generated/read_models/live_arts_md_invoice_review_bundle.json"
]', '[]', 'Proof capture is required before send/payment claims; no email sending authority is implied.');
INSERT INTO harvested_capability VALUES ('capability:payment_watch', 'Read-only payment watch', 'PAYMENT_WATCH', 'live_arts_md_invoice_lane', 'PARTIAL', 1, '[
  "st_annes_invoice_lane",
  "payment_proof_intake_lane",
  "ledger_handoff_readiness_lane"
]', '[]', '[
  "generated/read_models/live_arts_md_invoice_review_bundle.json"
]', '[]', 'Payment watch is readiness-only until proof/ledger gates are explicit.');
INSERT INTO harvested_capability VALUES ('capability:authority_boundary', 'No-authority invoice boundary', 'AUTHORITY_PROFILE', 'live_arts_md_invoice_lane', 'PARTIAL', 1, '[
  "capital_hilton_invoice_lane",
  "st_annes_invoice_lane",
  "payment_proof_intake_lane"
]', '[]', '[
  "generated/read_models/openclaw_authority_semantics_registry.json",
  "generated/read_models/openclaw_event_bridge_contract.json"
]', '[
  "tests/test_openclaw_event_bridge_contract.py"
]', '');
INSERT INTO harvested_capability VALUES ('capability:mac_pc_bridge_response', 'Mac/PC bridge scoped response', 'SERVICE_PATTERN', 'live_arts_md_invoice_lane', 'PARTIAL', 1, '[
  "capital_hilton_invoice_lane",
  "st_annes_invoice_lane",
  "Mac Excel helper/export execution"
]', '[]', '[
  "openclaw_request_response_service.py",
  "generated/read_models/openclaw_event_bridge_contract.json"
]', '[]', '');
INSERT INTO harvested_capability VALUES ('capability:supplier_portal_proof', 'Supplier portal proof intake', 'PROOF_RECEIPT', 'capital_hilton_invoice_lane', 'PARTIAL', 1, '[
  "complex_invoice_lanes"
]', '[
  "live_arts_md_invoice_lane",
  "st_annes_invoice_lane"
]', '[
  "generated/read_models/invoice_review_bundle.json",
  "capital_hilton_protected_proof_intake.py"
]', '[]', 'Proof intake is reusable; actual portal access/submission remains blocked without explicit authority.');
INSERT INTO harvested_capability VALUES ('capability:coupa_po_extension', 'Coupa/PO extension', 'DATA_ACCESS_PATTERN', 'capital_hilton_invoice_lane', 'PLANNED', 1, '[
  "complex_invoice_lanes"
]', '[
  "live_arts_md_invoice_lane",
  "st_annes_invoice_lane"
]', '[
  "generated/read_models/invoice_review_bundle.json",
  "capital_hilton_coupa_po_retrieval_automation_candidate.py"
]', '[]', 'Must remain a protected extension, never the default simple-invoice rail.');
INSERT INTO harvested_capability VALUES ('capability:multi_invoice_review', 'Multi-invoice review and selection', 'WORKFLOW_RAIL', 'capital_hilton_invoice_lane', 'PARTIAL', 1, '[
  "complex_invoice_lanes"
]', '[
  "single_invoice_simple_lanes"
]', '[
  "generated/read_models/invoice_review_bundle.json"
]', '[]', '');
INSERT INTO harvested_capability VALUES ('capability:guardian_approval_gates', 'Guardian approval gates', 'UI_PATTERN', 'capital_hilton_invoice_lane', 'PARTIAL', 1, '[
  "capital_hilton_invoice_lane",
  "client_comms_follow_up",
  "ledger_handoff_readiness_lane"
]', '[]', '[
  "generated/read_models/invoice_review_bundle.json",
  "generated/read_models/capital_hilton_review_packet_approval.json"
]', '[]', '');
INSERT INTO harvested_capability VALUES ('capability:st_annes_simple_generalization', 'St. Anne''s simple invoice generalization', 'WORKFLOW_RAIL', 'st_annes_invoice_lane', 'PLANNED', 1, '[
  "future_simple_invoice_lanes"
]', '[
  "coupa_supplier_portal_extensions"
]', '[
  "simple_invoice_workflow_fixtures.py",
  "generated/read_models/simple_invoice_event_bridge_rail_registry.json"
]', '[
  "tests/test_simple_invoice_event_bridge_rail_registry.py",
  "tests/test_client_invoice_workflow_framework.py"
]', 'Should prove generalization without importing Capital Hilton portal/PO complexity.');
INSERT INTO capability_dependency VALUES ('dependency:selected_summary_requires_candidate_selection', 'capability:selected_invoice_summary_state', 'capability:invoice_candidate_selection', 'REQUIRED', 'Selected summary must be derived from a confirmed candidate receipt/state.');
INSERT INTO capability_dependency VALUES ('dependency:pdf_package_requires_selected_summary', 'capability:pdf_artifact_package', 'capability:selected_invoice_summary_state', 'REQUIRED', 'Scoped artifact package requires invoice id, sheet, and selected summary.');
INSERT INTO capability_dependency VALUES ('dependency:prepare_pdf_extends_event_bridge', 'capability:pdf_artifact_package', 'capability:event_bridge_prepare_pdf_action', 'EXTENDS', 'The package is delivered through the Event Bridge action contract.');
INSERT INTO capability_dependency VALUES ('dependency:payment_watch_requires_send_proof', 'capability:payment_watch', 'capability:manual_send_proof', 'BLOCKED_BY', 'Payment watch becomes meaningful only after manual send or send receipt.');
INSERT INTO capability_dependency VALUES ('dependency:capital_coupa_extends_simple_invoice', 'capability:coupa_po_extension', 'capability:simple_invoice_rail', 'EXTENDS', 'Capital Hilton adds portal/PO posture on top of invoice rails.');
INSERT INTO capability_dependency VALUES ('dependency:portal_proof_requires_authority', 'capability:supplier_portal_proof', 'capability:authority_boundary', 'REQUIRED', 'Portal proof must remain receipt-only until explicit authority exists.');
INSERT INTO capability_dependency VALUES ('dependency:guardian_gates_require_proof', 'capability:guardian_approval_gates', 'capability:supplier_portal_proof', 'OPTIONAL', 'Capital Hilton approval quality improves after portal/proof evidence is captured.');
INSERT INTO capability_dependency VALUES ('dependency:st_annes_replaces_capital_extensions', 'capability:st_annes_simple_generalization', 'capability:coupa_po_extension', 'REPLACES', 'St. Anne''s should prove the simple lane does not inherit Coupa/PO extension.');
INSERT INTO lane_reuse_plan VALUES ('reuse:live_arts_to_capital_hilton', 'live_arts_md_invoice_lane', 'capital_hilton_invoice_lane', '[
  "capability:simple_invoice_rail",
  "capability:event_bridge_prepare_pdf_action",
  "capability:authority_boundary",
  "capability:manual_send_proof"
]', '[
  "capability:supplier_portal_proof",
  "capability:coupa_po_extension",
  "capability:multi_invoice_review",
  "capability:guardian_approval_gates"
]', '[
  "live Coupa submit",
  "ledger posting",
  "email send"
]', '[
  "tests/test_capital_hilton_protected_proof_intake.py",
  "tests/test_capital_hilton_review_packet_approval.py"
]', 'NEEDS_ADAPTER');
INSERT INTO lane_reuse_plan VALUES ('reuse:live_arts_to_st_annes', 'live_arts_md_invoice_lane', 'st_annes_invoice_lane', '[
  "capability:simple_invoice_rail",
  "capability:event_bridge_prepare_pdf_action",
  "capability:invoice_candidate_selection",
  "capability:pdf_artifact_package",
  "capability:payment_watch"
]', '[
  "capability:st_annes_simple_generalization",
  "client-specific workbook/profile adapter"
]', '[
  "Coupa",
  "supplier portal",
  "purchase order blockers"
]', '[
  "tests/test_simple_invoice_event_bridge_rail_registry.py",
  "tests/test_client_invoice_workflow_framework.py"
]', 'PLANNED');
INSERT INTO lane_reuse_plan VALUES ('reuse:invoice_sequence_to_payment_proof_intake', 'st_annes_invoice_lane', 'payment_proof_intake_lane', '[
  "capability:payment_watch",
  "capability:manual_send_proof",
  "capability:authority_boundary"
]', '[
  "payment proof intake receipt"
]', '[
  "ledger posting"
]', '[
  "future:test_payment_proof_intake_registry"
]', 'PLANNED');
INSERT INTO next_lane_candidate VALUES ('payment_proof_intake_lane', 'payment proof intake', 'payment_proof', 'Reuses invoice proof/payment watch and adds one receipt intake for payment evidence.', '[
  "payment_watch",
  "manual_send_proof",
  "authority_boundary"
]', '[
  "payment proof receipt intake"
]', 2, 9, 2, 'High leverage after invoices because it turns sent invoices into tracked receivables.', 1, 'local deterministic codex', '[
  "invoice steel-thread sequence proven"
]', '[
  "do not post ledger",
  "do not access bank without explicit authority"
]', 'PLANNED');
INSERT INTO next_lane_candidate VALUES ('ledger_handoff_readiness_lane', 'ledger handoff readiness', 'ledger_readiness', 'Reuses proof/approval/payment evidence to prepare a no-post ledger handoff.', '[
  "payment_watch",
  "proof_receipts",
  "guardian_approval_gates"
]', '[
  "ledger handoff readiness packet"
]', 3, 8, 4, 'Useful after payment proof exists, but posting remains out of scope.', 2, 'local deterministic codex', '[
  "payment proof intake proven",
  "approval gates proven"
]', '[
  "do not post ledger"
]', 'PLANNED');
INSERT INTO next_lane_candidate VALUES ('client_comms_follow_up_lane', 'client comms follow-up', 'client_comms', 'Reuses Clara draft/proof/approval shape and adds follow-up scheduling/readiness.', '[
  "manual_send_proof",
  "guardian_approval_gates",
  "clara_draft"
]', '[
  "follow-up readiness receipt"
]', 4, 7, 3, 'Good adjacent lane once send/proof rails are stable.', 3, 'local deterministic codex', '[
  "manual proof capture proven"
]', '[
  "do not send email"
]', 'PLANNED');
INSERT INTO next_lane_candidate VALUES ('recurring_invoice_workflow_lane', 'recurring invoice workflow', 'recurring_invoice', 'Reuses simple invoice rail and adds recurrence policy.', '[
  "simple_invoice_rail",
  "candidate_selection",
  "payment_watch"
]', '[
  "recurrence policy"
]', 5, 7, 4, 'Useful after St. Anne''s proves simple-lane generalization.', 4, 'local deterministic codex', '[
  "St. Anne''s lane proven"
]', '[
  "do not infer workbook data"
]', 'PLANNED');
INSERT INTO next_lane_candidate VALUES ('estimate_quote_workflow_lane', 'estimate/quote workflow', 'estimate_quote', 'Reuses approval/proof shape but adds a new pre-invoice object.', '[
  "guardian_approval_gates",
  "client_comms"
]', '[
  "quote lifecycle"
]', 6, 5, 4, 'Later adjacent business object after receivable rails are stable.', 5, 'local deterministic codex', '[
  "invoice rails stable"
]', '[
  "do not send quotes"
]', 'PLANNED');
INSERT INTO next_lane_candidate VALUES ('gig_settlement_packet_lane', 'gig settlement packet', 'settlement_packet', 'Reuses proof packet and adds settlement summary object.', '[
  "proof_receipts",
  "payment_watch"
]', '[
  "settlement packet"
]', 6, 5, 4, 'Useful for performance workflows after invoice rails.', 6, 'local deterministic codex', '[
  "payment proof intake proven"
]', '[
  "do not mutate ledger"
]', 'PLANNED');
INSERT INTO next_lane_candidate VALUES ('contract_proof_packet_lane', 'contract/proof packet workflow', 'contract_packet', 'Reuses proof/approval packet machinery for contract evidence.', '[
  "proof_receipts",
  "guardian_approval_gates"
]', '[
  "contract packet policy"
]', 6, 4, 5, 'Park until invoice proof patterns are stable.', 7, 'local deterministic codex', '[
  "proof packet evals"
]', '[
  "do not sign contracts"
]', 'PLANNED');
INSERT INTO next_lane_candidate VALUES ('telegram_compact_invoice_action_lane', 'Telegram compact invoice action', 'compact_surface', 'Reuses Event Bridge action but adds compact UI surface.', '[
  "event_bridge_prepare_pdf_action",
  "authority_boundary"
]', '[
  "compact invoice command"
]', 7, 4, 5, 'Do not prioritize before object rails are proven.', 8, 'local deterministic codex', '[
  "invoice lanes proven"
]', '[
  "do not do generic Telegram polish"
]', 'PLANNED');
INSERT INTO next_lane_candidate VALUES ('mac_excel_helper_export_execution_lane', 'Mac Excel helper/export execution', 'mac_helper', 'Targets unresolved Mac-local export helper capability.', '[
  "pdf_artifact_package",
  "mac_pc_bridge_response"
]', '[
  "Mac local helper worker"
]', 7, 5, 6, 'Important only when explicitly targeting the Mac permission/helper problem.', 9, 'mac bounded implementation package', '[
  "local bridge stable",
  "helper architecture approved"
]', '[
  "do not remote/cloud relay first"
]', 'PLANNED');
INSERT INTO next_lane_candidate VALUES ('service_supervision_recovery_action_lane', 'service supervision recovery action', 'service_supervision', 'Reuses service supervision and keeper patterns for recovery receipts.', '[
  "service supervision",
  "change sentinel"
]', '[
  "recovery action receipt"
]', 5, 6, 3, 'Infrastructure-adjacent; keep behind business-object rail work.', 10, 'local deterministic codex', '[
  "current service keeper stable"
]', '[
  "do not run proofs or Chief from keeper"
]', 'PLANNED');
INSERT INTO hermes_recommendation VALUES ('hermes_recommendation:finish_invoice_steel_thread_sequence', '2026-05-31T21:39:09+00:00', 'finish_invoice_steel_thread_sequence', 'Live Arts, Capital Hilton, and St. Anne''s are not all proven. Finish the invoice steel-thread sequence before opening a new adjacent lane.', '[
  "generated/read_models/live_arts_md_invoice_review_bundle.json",
  "generated/read_models/invoice_review_bundle.json",
  "generated/read_models/simple_invoice_event_bridge_rail_registry.json"
]', '[
  "Live Arts PDF/proof/payment gates stable",
  "Capital Hilton supplier portal/Coupa/approval extension proven",
  "St. Anne''s simple invoice generalization proven"
]', 'completed reusable invoice steel-thread sequence', '[
  "simple invoice rail",
  "Event Bridge Prepare PDF action",
  "proof receipts",
  "authority boundary",
  "payment watch"
]', 'HIGH', 'Hermes should keep the build order on Live Arts -> Capital Hilton -> St. Anne''s until those lanes prove the reusable invoice rail.', 'chief_build_task:finish_invoice_steel_thread_sequence');
INSERT INTO capability_gap VALUES ('gap:invoice_steel_thread_not_all_proven', 'Invoice steel-thread sequence not all proven', '[
  "live_arts_md_invoice_lane",
  "capital_hilton_invoice_lane",
  "st_annes_invoice_lane"
]', 'three-lane invoice generalization proof', 'Hermes should not select the next business lane until the reusable invoice rail survives simple, complex, and second-simple cases.', 'HIGH', 'Finish Live Arts, then Capital Hilton, then St. Anne''s with proof receipts and tests.', '/home/openclaw', 'local deterministic codex', 'OPEN');
INSERT INTO capability_gap VALUES ('gap:mac_excel_helper_export_execution', 'Mac Excel helper/export execution unresolved', '[
  "live_arts_md_invoice_lane",
  "st_annes_invoice_lane"
]', 'Mac-local helper/permission architecture for Excel PDF export', 'PDF artifact packages remain candidates until a valid local export receipt exists.', 'HIGH', 'Build a bounded Mac helper work package after local bridge/schema stability is proven.', 'Mac app/helper repo', 'bounded Mac implementation package', 'OPEN');
INSERT INTO capability_gap VALUES ('gap:capital_hilton_supplier_portal_proof', 'Capital Hilton supplier portal/Coupa proof extension', '[
  "capital_hilton_invoice_lane"
]', 'supplier portal proof and PO/Coupa posture without submit authority', 'Capital Hilton is the intended complex-invoice proof of reuse plus one hard extension.', 'HIGH', 'Keep Coupa/portal as protected proof intake first; do not build submit automation.', '/home/openclaw', 'local deterministic codex', 'OPEN');
INSERT INTO capability_gap VALUES ('gap:lane_reuse_evals', 'Lane reuse eval coverage', '[
  "all_invoice_lanes",
  "future_lanes"
]', 'eval pattern proving reused capability does not import lane-specific blockers', 'St. Anne''s must prove that simple invoice rails do not inherit Capital Hilton Coupa/PO complexity.', 'MEDIUM', 'Add fixture tests per lane reuse plan before promoting capability status to PROVEN.', '/home/openclaw', 'local deterministic codex', 'OPEN');
INSERT INTO capability_gap VALUES ('gap:ledger_handoff_readiness_not_posting', 'Ledger handoff readiness is not ledger posting', '[
  "ledger_handoff_readiness_lane",
  "payment_proof_intake_lane"
]', 'no-post ledger handoff packet after proof/approval', 'Posting must stay blocked until proof, approval, and authority are proven.', 'MEDIUM', 'Build readiness-only handoff after payment proof intake, not before.', '/home/openclaw', 'local deterministic codex', 'PLANNED');

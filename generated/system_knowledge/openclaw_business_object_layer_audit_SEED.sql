INSERT INTO audit_run (run_ref, generated_at, freshness_status, fresh_for_minutes, readiness, overall_score, business_object_count, gap_count, missing_eval_count, stale_reasons_json) VALUES ('openclaw_business_object_layer_audit_run', '2026-05-31T21:39:11+00:00', 'FRESH', 60, 'READY_FOR_BUILD_PLANNING_NOT_EXECUTION', 3.67, 16, 13, 10, '[]');
INSERT INTO audit_input (input_ref, path, required, status, sha256, schema_version, generated_at, source_ref) VALUES ('estate_topology', 'generated/read_models/openclaw_estate_topology_registry.json', 1, 'PRESENT', 'sha256:e32c278f0bb6c52fd2c3e514406f93e9b2c8dd9724825164ec4158d21c7fb2ae', 'openclaw_estate_topology_registry_read_model_v0', '2026-05-31T04:28:39+00:00', 'generated/read_models/openclaw_estate_topology_registry.json');
INSERT INTO audit_input (input_ref, path, required, status, sha256, schema_version, generated_at, source_ref) VALUES ('reference_resolver', 'generated/read_models/openclaw_reference_resolver.json', 1, 'PRESENT', 'sha256:ca025f59ab8060942c7a75f1b1e4a8d562d9c50e807d7c96fa5c1312f009adba', 'openclaw_reference_resolver_read_model_v0', '2026-05-31T04:09:09+00:00', 'generated/read_models/openclaw_reference_resolver.json');
INSERT INTO audit_input (input_ref, path, required, status, sha256, schema_version, generated_at, source_ref) VALUES ('change_sentinel', 'generated/read_models/openclaw_change_sentinel.json', 1, 'PRESENT', 'sha256:732fefb22a8fd5f394ab1d9c6583b1fee1c063546545eb92f5e33137aa583463', 'openclaw_change_sentinel_read_model_v0', '2026-05-31T21:38:42+00:00', 'generated/read_models/openclaw_change_sentinel.json');
INSERT INTO audit_input (input_ref, path, required, status, sha256, schema_version, generated_at, source_ref) VALUES ('authority_semantics_registry', 'generated/read_models/openclaw_authority_semantics_registry.json', 1, 'PRESENT', 'sha256:73f8d59f3a0cefdf435e532da55eca2590e59a081a6e795db5f5bb2191c89383', 'openclaw_authority_semantics_registry_v0', '2026-05-31T15:00:00+00:00', 'generated/read_models/openclaw_authority_semantics_registry.json');
INSERT INTO audit_input (input_ref, path, required, status, sha256, schema_version, generated_at, source_ref) VALUES ('context_wiki_index', 'generated/read_models/openclaw_context_wiki_index.json', 1, 'PRESENT', 'sha256:093bf33205108c12f205a18dc537952db0a7add651f3b80f2714417b13d3620f', 'openclaw_context_wiki_compiler_v0', '2026-05-31T21:39:09+00:00', 'generated/read_models/openclaw_context_wiki_index.json');
INSERT INTO audit_input (input_ref, path, required, status, sha256, schema_version, generated_at, source_ref) VALUES ('lane_capability_harvest', 'generated/read_models/openclaw_lane_capability_harvest.json', 0, 'PRESENT', 'sha256:f37a900ac43108090e70d85e710f1d67e961b81568dc061f730b7ebdb8ec3f05', 'openclaw_lane_capability_harvest_read_model_v0', '2026-05-31T21:39:09+00:00', 'generated/read_models/openclaw_lane_capability_harvest.json');
INSERT INTO audit_input (input_ref, path, required, status, sha256, schema_version, generated_at, source_ref) VALUES ('external_system_knowledge_registry_index', 'generated/read_models/external_system_knowledge_registry_index.json', 0, 'PRESENT', 'sha256:5665a7b3bfbfec9a9c9a6df1a99a13f93194dd04fb46958176c2cd1f30769c50', 'external_system_knowledge_registry_index_v0', '', 'generated/read_models/external_system_knowledge_registry_index.json');
INSERT INTO audit_input (input_ref, path, required, status, sha256, schema_version, generated_at, source_ref) VALUES ('live_arts_bundle', 'generated/read_models/live_arts_md_invoice_review_bundle.json', 1, 'PRESENT', 'sha256:32aed1bf62bceab78634e1feeb02651b41155f27827aae8433e5df18db1d352b', 'live_arts_md_invoice_review_bundle_v0', '2026-05-28T00:00:00+00:00', 'generated/read_models/live_arts_md_invoice_review_bundle.json');
INSERT INTO audit_input (input_ref, path, required, status, sha256, schema_version, generated_at, source_ref) VALUES ('capital_hilton_bundle', 'generated/read_models/invoice_review_bundle.json', 1, 'PRESENT', 'sha256:f384551a2558a0f8c8ef8bbfeea37f4d9d3fdd08f422a543e4385cd09964ed71', 'invoice_review_bundle_v0', '2026-05-29T18:53:14+00:00', 'generated/read_models/invoice_review_bundle.json');
INSERT INTO audit_input (input_ref, path, required, status, sha256, schema_version, generated_at, source_ref) VALUES ('hermes_mission_sentinel', 'generated/read_models/hermes_mission_sentinel.json', 0, 'PRESENT', 'sha256:5fb7f99839fd0763bb60eddcbaf7167a301c7ef6a90880d0888a8233435b0a47', 'hermes_mission_sentinel_v0', '2026-05-28T15:01:54-04:00', 'generated/read_models/hermes_mission_sentinel.json');
INSERT INTO audit_input (input_ref, path, required, status, sha256, schema_version, generated_at, source_ref) VALUES ('hermes_chief_build_handoff', 'generated/read_models/hermes_chief_build_handoff.json', 0, 'PRESENT', 'sha256:3fc1448b7a8236a3142814315790c427797c646295276429c6ceee42b005388a', 'hermes_chief_build_handoff_v0', '2026-05-28T15:01:54-04:00', 'generated/read_models/hermes_chief_build_handoff.json');
INSERT INTO audit_input (input_ref, path, required, status, sha256, schema_version, generated_at, source_ref) VALUES ('purpose_bound_automation_charter', 'generated/read_models/purpose_bound_automation_charter.json', 0, 'PRESENT', 'sha256:3460326c5e60000944ec87e8ab2361ed024df50ac7d736c33ce154ed6cb5d750', 'purpose_bound_automation_charter_v0', '2026-05-28T21:43:08+00:00', 'generated/read_models/purpose_bound_automation_charter.json');
INSERT INTO audit_input (input_ref, path, required, status, sha256, schema_version, generated_at, source_ref) VALUES ('hermes_gravity_controller', 'generated/read_models/hermes_gravity_controller.json', 0, 'PRESENT', 'sha256:51d57984bea39a6769fcaba0129e69a26e7761bfefc0a18b0d9ff77ffe628bec', 'hermes_gravity_controller_v0', '2026-05-28T12:00:00+00:00', 'generated/read_models/hermes_gravity_controller.json');
INSERT INTO audit_input (input_ref, path, required, status, sha256, schema_version, generated_at, source_ref) VALUES ('service_supervision', 'generated/read_models/openclaw_service_supervision.json', 0, 'PRESENT', 'sha256:b92e768756c9a0d4302569f350e78db6c978d21871a9529fe9dcc324c565728d', 'openclaw_service_supervision_read_model_v0', '2026-05-31T03:52:22+00:00', 'generated/read_models/openclaw_service_supervision.json');
INSERT INTO audit_category_score (category, score, max_score, confidence, status, strongest_evidence, biggest_gap, fastest_improvement, rationale, source_refs_json, freshness_notes) VALUES ('Workflow Design', 4.0, 5.0, 'MEDIUM_HIGH', 'STRONG_WITH_STALE_HANDOFFS', 'Live Arts and Capital Hilton bundles expose explicit receipt gates, blocker lists, and safe action payloads.', 'Hermes/Chief handoff still carries stale Live Arts candidate-selection blockers.', 'Regenerate Hermes/Chief posture from the confirmed 2026-1001 bundle state.', 'Live Arts and Capital Hilton have explicit rails, blockers, receipts, and safe actions, but Hermes/Chief still contains stale Live Arts candidate-selection blockers.', '[
  {
    "note": "Selected invoice and PDF package rails.",
    "path": "generated/read_models/live_arts_md_invoice_review_bundle.json"
  },
  {
    "note": "Capital Hilton blocker and receipt rails.",
    "path": "generated/read_models/invoice_review_bundle.json"
  },
  {
    "note": "Stale candidate blocker still present.",
    "path": "generated/read_models/hermes_mission_sentinel.json"
  }
]', 'Score confidence drops if any required audit input is missing; workflow score depends on current bundle and Hermes hashes.');
INSERT INTO audit_category_score (category, score, max_score, confidence, status, strongest_evidence, biggest_gap, fastest_improvement, rationale, source_refs_json, freshness_notes) VALUES ('Data Access', 3.5, 5.0, 'MEDIUM_HIGH', 'GOOD_LOCAL_READ_MODELS_BRIDGE_PARTIAL', 'Estate topology, Reference Resolver, Change Sentinel, Context Wiki, and Service Supervision read-models are present.', 'Bridge mirror/Mac-local availability remains partial or unavailable.', 'Repair bridge mirror and refresh resolver output.', 'Registries, resolver, wiki, invoice bundles, and supervision read-models exist; bridge mirror and Mac-local paths remain unavailable or partial.', '[
  {
    "note": "Resolver drift_count=0.",
    "path": "generated/read_models/openclaw_reference_resolver.json"
  },
  {
    "note": "Wiki pages=12.",
    "path": "generated/read_models/openclaw_context_wiki_index.json"
  }
]', 'Data-access score is valid only while input_manifest hashes match current files.');
INSERT INTO audit_category_score (category, score, max_score, confidence, status, strongest_evidence, biggest_gap, fastest_improvement, rationale, source_refs_json, freshness_notes) VALUES ('Authority', 4.5, 5.0, 'MEDIUM_HIGH', 'STRONG_DEFAULT_DENY_WITH_REGISTRY', 'Authority Semantics Registry is present and defines prohibition flags, authority grants, positive templates, and golden fixtures.', 'Mac helper permission architecture remains unresolved and must preserve the same boundary.', 'Keep Event Bridge and future Mac helper payloads validating against the authority semantics registry.', 'Business read-models, supervision, and the Authority Semantics Registry carry default-deny flags; Mac export package is scoped and no ledger/email/browser/workbook-cell authority is granted.', '[
  {
    "note": "Authority registry schema=openclaw_authority_semantics_registry_v0.",
    "path": "generated/read_models/openclaw_authority_semantics_registry.json"
  },
  {
    "note": "Mac package no_email=True no_ledger=True.",
    "path": "generated/read_models/live_arts_md_invoice_review_bundle.json"
  },
  {
    "note": "Startup readiness=READY.",
    "path": "generated/read_models/openclaw_service_supervision.json"
  }
]', 'Authority score should be rechecked whenever the Authority Semantics Registry, Live Arts package, or service supervision hashes change.');
INSERT INTO audit_category_score (category, score, max_score, confidence, status, strongest_evidence, biggest_gap, fastest_improvement, rationale, source_refs_json, freshness_notes) VALUES ('Evals', 2.5, 5.0, 'MEDIUM_HIGH', 'FOCUSED_TESTS_PRESENT_END_TO_END_GAPS', 'Focused tests exist for wiki, resolver, sentinel, service supervision, and this audit.', 'Business-object end-to-end evals are still missing.', 'Add synthetic result-intake and attachment-promotion tests without executing PDF export.', 'Registry and monitor tests exist, but business-object end-to-end evals for Mac helper, PDF result intake, attachment promotion, manual proof, payment watch, and Capital Hilton proof are still missing.', '[
  {
    "note": "Wiki compiler tests exist.",
    "path": "tests/test_openclaw_context_wiki_compiler.py"
  },
  {
    "note": "Service supervision tests exist.",
    "path": "tests/test_openclaw_service_supervision.py"
  }
]', 'Eval score is less volatile than workflow state, but should be refreshed when source/test files change.');
INSERT INTO audit_category_score (category, score, max_score, confidence, status, strongest_evidence, biggest_gap, fastest_improvement, rationale, source_refs_json, freshness_notes) VALUES ('Audit Trails & Recovery', 4.0, 5.0, 'MEDIUM_HIGH', 'GOOD_RECEIPTS_AND_MONITORS_STALE_VIEWS', 'Change Sentinel and Service Supervision are active read-model sources; invalid artifact guardrails are explicit.', 'Stale generated views can persist unless their input hashes are checked.', 'Use this audit freshness contract and sentinel stale-audit detection.', 'Reference resolver, sentinel, service supervision, receipts, and invalid artifact guardrails are strong; stale Hermes/wiki claims and missing bridge mirror still need recovery paths.', '[
  {
    "note": "Sentinel run_status=BUSINESS_OBJECT_AUDIT_STALE.",
    "path": "generated/read_models/openclaw_change_sentinel.json"
  },
  {
    "note": "Invalid PDF placeholders are explicitly not trusted.",
    "path": "generated/read_models/live_arts_md_invoice_review_bundle.json"
  }
]', 'Audit-trail score depends directly on sentinel/reference resolver freshness signals.');
INSERT INTO audit_category_score (category, score, max_score, confidence, status, strongest_evidence, biggest_gap, fastest_improvement, rationale, source_refs_json, freshness_notes) VALUES ('Business Object Proximity', 3.5, 5.0, 'MEDIUM_HIGH', 'LIVE_ARTS_CLOSE_CAPITAL_HILTON_FARTHER', 'Live Arts selected invoice and scoped PDF package are present in the current bundle.', 'Actual Mac export result and attachment promotion are still missing.', 'Complete safe Mac helper export trial and result-intake evals.', 'Live Arts has selected invoice and a scoped Mac PDF package ready, but attachment, recipient, approval, proof, payment, and ledger states remain gated; Capital Hilton is still selection/proof blocked.', '[
  {
    "note": "PDF package status=PDF_EXPORT_PACKAGE_READY_FOR_MAC.",
    "path": "generated/read_models/live_arts_md_invoice_review_bundle.json"
  },
  {
    "note": "Capital Hilton status=READY_FOR_REVIEW_BLOCKED_FOR_SELECTION.",
    "path": "generated/read_models/invoice_review_bundle.json"
  }
]', 'Business proximity can change quickly as workflow receipts arrive; stale input hashes invalidate this score.');
INSERT INTO business_object_inventory (object_name, implementation_status, business_object_proximity, current_fact, blockers_json, next_safe_action, source_refs_json) VALUES ('Live Arts invoice', 'SELECTED_NOT_SEND_READY', 'HIGH', '2026-1001 — June 2026 Speaker Rental — $900', '[
  "attachment_ready=false",
  "recipient confirmation pending",
  "Guardian/operator approval missing",
  "send proof missing"
]', 'Finish artifact proof path before recipient/Guardian/send-readiness promotion.', '[
  {
    "note": "",
    "path": "generated/read_models/live_arts_md_invoice_review_bundle.json"
  }
]');
INSERT INTO business_object_inventory (object_name, implementation_status, business_object_proximity, current_fact, blockers_json, next_safe_action, source_refs_json) VALUES ('Live Arts PDF artifact', 'PACKAGE_READY_EXPORT_NOT_CONFIRMED', 'HIGH', 'PDF_EXPORT_PACKAGE_READY_FOR_MAC for invoice 2026-1001', '[
  "actual Mac export completion receipt missing",
  "attachment_ready=false",
  "operator review after export required"
]', 'Resolve Mac helper/permission path, then ingest selected_invoice_pdf_export_completed_candidate.', '[
  {
    "note": "pdf_export_package",
    "path": "generated/read_models/live_arts_md_invoice_review_bundle.json"
  }
]');
INSERT INTO business_object_inventory (object_name, implementation_status, business_object_proximity, current_fact, blockers_json, next_safe_action, source_refs_json) VALUES ('Live Arts payment watch', 'READINESS_ONLY_NOT_ACTIVE', 'MEDIUM', 'ledger_match=NOT_ATTEMPTED; bank_read=False', '[
  "manual send proof missing",
  "bank/payment confirmation missing",
  "ledger posting disallowed"
]', 'Keep readiness-only until manual/send proof exists.', '[
  {
    "note": "payment_watch",
    "path": "generated/read_models/live_arts_md_invoice_review_bundle.json"
  }
]');
INSERT INTO business_object_inventory (object_name, implementation_status, business_object_proximity, current_fact, blockers_json, next_safe_action, source_refs_json) VALUES ('Capital Hilton invoice', 'READY_FOR_REVIEW_BLOCKED_FOR_SELECTION', 'MEDIUM_LOW', 'Which invoice page/period should OpenClaw prepare for Capital Hilton?', '[
  "active_workbook_confirmed_receipt",
  "invoice_record_selected_receipt",
  "invoice_period_confirmed_receipt",
  "generated_invoice_artifact_linkage_receipt",
  "excel_invoice_generated_receipt",
  "invoice_attachment_proof_receipt",
  "clara_email_draft_receipt",
  "purchase_order_confirmed_receipt"
]', 'Confirm invoice record/period and Coupa proof before attachment or send readiness.', '[
  {
    "note": "",
    "path": "generated/read_models/invoice_review_bundle.json"
  }
]');
INSERT INTO business_object_inventory (object_name, implementation_status, business_object_proximity, current_fact, blockers_json, next_safe_action, source_refs_json) VALUES ('Clara draft', 'DRAFT_PREVIEW_NOT_SEND_READY', 'MEDIUM', 'Live Arts and Capital Hilton drafts are draft-only / not send-ready.', '[
  "attachment_readiness",
  "recipient_confirmation",
  "clara_draft_receipt"
]', 'Promote only after attachment, recipient, draft receipt, Guardian/operator approvals.', '[
  {
    "note": "clara draft",
    "path": "generated/read_models/live_arts_md_invoice_review_bundle.json"
  },
  {
    "note": "Capital Hilton clara draft",
    "path": "generated/read_models/invoice_review_bundle.json"
  }
]');
INSERT INTO business_object_inventory (object_name, implementation_status, business_object_proximity, current_fact, blockers_json, next_safe_action, source_refs_json) VALUES ('client comms thread', 'BLOCKED_UNTIL_SENT_RECEIPT', 'MEDIUM', 'client_comms_thread:live_arts_md:cc5418d57c6ca036', '[
  "thread watch blocked until sent receipt",
  "no Gmail draft/send performed"
]', 'Keep thread watch future-gated until send receipt exists.', '[
  {
    "note": "client_comms_thread",
    "path": "generated/read_models/live_arts_md_invoice_review_bundle.json"
  }
]');
INSERT INTO business_object_inventory (object_name, implementation_status, business_object_proximity, current_fact, blockers_json, next_safe_action, source_refs_json) VALUES ('Guardian approval', 'BLOCKED_PREREQUISITES_MISSING', 'MEDIUM', 'Guardian approval is required and not a send authority by itself.', '[
  "attachment readiness",
  "recipient confirmation",
  "operator approval/send receipts"
]', 'Create request only after prerequisites are true.', '[
  {
    "note": "",
    "path": "generated/read_models/live_arts_md_invoice_review_bundle.json"
  },
  {
    "note": "",
    "path": "generated/read_models/invoice_review_bundle.json"
  }
]');
INSERT INTO business_object_inventory (object_name, implementation_status, business_object_proximity, current_fact, blockers_json, next_safe_action, source_refs_json) VALUES ('Mac edge job package', 'PDF_EXPORT_PACKAGE_READY_FOR_MAC', 'HIGH', 'execution_venue=MAC_LOCAL; required_capability=MAC_EXCEL_PDF_EXPORT; no_workbook_cell_read=True', '[
  "Mac export not completed",
  "result receipt missing",
  "helper/permission architecture unresolved"
]', 'Mac emits scoped result only after local helper succeeds.', '[
  {
    "note": "Mac edge job package",
    "path": "generated/read_models/live_arts_md_invoice_review_bundle.json"
  }
]');
INSERT INTO business_object_inventory (object_name, implementation_status, business_object_proximity, current_fact, blockers_json, next_safe_action, source_refs_json) VALUES ('Mac Excel helper/proposed helper', 'HELPER_ARCHITECTURE_RECOMMENDED', 'MEDIUM', 'Mac-local Excel/PDF helper code belongs with the Mac app/helper architecture.', '[
  "in-app Excel Automation blocked",
  "file/folder and Apple Events permission shape unresolved"
]', 'Implement/verify helper architecture on Mac; PC only emits packages.', '[
  {
    "note": "mac_excel_edge_worker",
    "path": "generated/read_models/openclaw_estate_topology_registry.json"
  }
]');
INSERT INTO business_object_inventory (object_name, implementation_status, business_object_proximity, current_fact, blockers_json, next_safe_action, source_refs_json) VALUES ('Access Broker', 'PARTIAL', 'MEDIUM', 'Swift UI surface belongs in Mac app; policy/registry side belongs in backend when present.', '[
  "split Mac UI/backend policy not fully implemented",
  "Mac permission failures still modeled as partial"
]', 'Define helper permission repair path without collapsing ownership boundaries.', '[
  {
    "note": "access_broker",
    "path": "generated/read_models/openclaw_estate_topology_registry.json"
  }
]');
INSERT INTO business_object_inventory (object_name, implementation_status, business_object_proximity, current_fact, blockers_json, next_safe_action, source_refs_json) VALUES ('service supervision', 'READY', 'INFRA_HIGH', 'request-response=active/running; watch=/usr/bin/env python3 /home/openclaw/scripts/run_openclaw_request_response_service.py --watch-seconds 21600 --poll-interval 1 --active-poll-interval 0.05 --active-window-seconds 180 --max-requests 100 --format summary', '[]', 'Keep observing; keeper may start inactive allowlisted units only.', '[
  {
    "note": "",
    "path": "generated/read_models/openclaw_service_supervision.json"
  }
]');
INSERT INTO business_object_inventory (object_name, implementation_status, business_object_proximity, current_fact, blockers_json, next_safe_action, source_refs_json) VALUES ('reference resolver', 'RESOLVED_REMOTE', 'INFRA_HIGH', 'review branch remote=RESOLVED_REMOTE; local=UNREACHABLE; mac=LOCAL_PATH_UNREACHABLE', '[
  "Mac local path unreachable from PC",
  "estate mirror=MISSING"
]', 'Use resolver output for volatile refs; do not copy branch heads into source truth.', '[
  {
    "note": "",
    "path": "generated/read_models/openclaw_reference_resolver.json"
  }
]');
INSERT INTO business_object_inventory (object_name, implementation_status, business_object_proximity, current_fact, blockers_json, next_safe_action, source_refs_json) VALUES ('change sentinel', 'BUSINESS_OBJECT_AUDIT_STALE', 'INFRA_MEDIUM', 'material_changes=1; timer observed=True', '[]', 'Observe only; do not make sentinel start services directly.', '[
  {
    "note": "",
    "path": "generated/read_models/openclaw_change_sentinel.json"
  },
  {
    "note": "",
    "path": "generated/read_models/openclaw_service_supervision.json"
  }
]');
INSERT INTO business_object_inventory (object_name, implementation_status, business_object_proximity, current_fact, blockers_json, next_safe_action, source_refs_json) VALUES ('estate topology registry', 'PRESENT_EXTERNAL_REGISTRY_MATERIALIZED', 'INFRA_HIGH', 'machines=2; working_copies=5; context_registry_area=CANONICAL_ON_MAIN; external_registry=EXTERNAL_REGISTRY_MATERIALIZED', '[
  "bridge mirror missing"
]', 'Keep openclaw-eyes as canonical owner and consume imported registry artifacts as read-only external inputs.', '[
  {
    "note": "",
    "path": "generated/read_models/openclaw_estate_topology_registry.json"
  }
]');
INSERT INTO business_object_inventory (object_name, implementation_status, business_object_proximity, current_fact, blockers_json, next_safe_action, source_refs_json) VALUES ('context wiki', 'PRESENT_GENERATED_VIEW', 'INFRA_MEDIUM', 'pages=12; contradictions=10', '[]', 'Fix upstream registries/read-models, then regenerate; do not edit wiki as source truth.', '[
  {
    "note": "",
    "path": "generated/read_models/openclaw_context_wiki_index.json"
  },
  {
    "note": "",
    "path": "generated/wiki/openclaw/"
  }
]');
INSERT INTO business_object_inventory (object_name, implementation_status, business_object_proximity, current_fact, blockers_json, next_safe_action, source_refs_json) VALUES ('openclaw-eyes registry branch', 'EXTERNAL_REGISTRY_MATERIALIZED', 'INFRA_HIGH', 'canonical_owner=openclaw-eyes; main_head=1a6b7b0b463968f3161e048bd7936dc06505a3bb; review_head=1a6b7b0b463968f3161e048bd7936dc06505a3bb; local_role=READ_ONLY_EXTERNAL_INPUT', '[]', 'Use the materialized cache as READ_ONLY_EXTERNAL_INPUT; do not make /home/openclaw the canonical owner.', '[
  {
    "note": "",
    "path": "generated/read_models/openclaw_reference_resolver.json"
  },
  {
    "note": "",
    "path": "generated/read_models/openclaw_estate_topology_registry.json"
  },
  {
    "note": "",
    "path": "generated/read_models/external_system_knowledge_registry_index.json"
  }
]');
INSERT INTO audit_gap (rank, gap_ref, gap, severity, owner_hint, build_bucket) VALUES (1, 'mac_helper_permission_architecture', 'Mac Excel helper / Access Broker permission path is unresolved; in-app Excel automation is blocked.', 'HIGH', 'MAC_APP', 'Now');
INSERT INTO audit_gap (rank, gap_ref, gap, severity, owner_hint, build_bucket) VALUES (2, 'live_arts_pdf_export_completion', 'Live Arts PDF package is ready, but selected_invoice_pdf_export_completed_candidate is missing.', 'HIGH', 'MAC_APP+PC_BACKEND', 'Now');
INSERT INTO audit_gap (rank, gap_ref, gap, severity, owner_hint, build_bucket) VALUES (3, 'live_arts_attachment_ready', 'Live Arts attachment_ready remains false until valid export and operator review receipts exist.', 'HIGH', 'PC_BACKEND', 'Now');
INSERT INTO audit_gap (rank, gap_ref, gap, severity, owner_hint, build_bucket) VALUES (4, 'live_arts_manual_send_proof', 'Manual send metadata exists, but proof screenshot/ref is missing and file-backed proof is false.', 'HIGH', 'OPERATOR_PROOF', 'Next');
INSERT INTO audit_gap (rank, gap_ref, gap, severity, owner_hint, build_bucket) VALUES (5, 'live_arts_recipient_confirmation', 'Dane/Draper/Earnie email details are not confirmed; Winship copy is known only.', 'HIGH', 'PC_BACKEND', 'Next');
INSERT INTO audit_gap (rank, gap_ref, gap, severity, owner_hint, build_bucket) VALUES (6, 'guardian_approval_not_created', 'Guardian approval request is required but not created/ready for Live Arts.', 'HIGH', 'PC_BACKEND', 'Next');
INSERT INTO audit_gap (rank, gap_ref, gap, severity, owner_hint, build_bucket) VALUES (7, 'clara_final_draft_blocked', 'Clara drafts are preview/draft-only and not send-ready.', 'MEDIUM', 'PC_BACKEND', 'Next');
INSERT INTO audit_gap (rank, gap_ref, gap, severity, owner_hint, build_bucket) VALUES (8, 'payment_watch_readiness_only', 'Payment watch is readiness-only until send/manual-send proof exists; no bank read or ledger match has run.', 'MEDIUM', 'PC_BACKEND', 'Next');
INSERT INTO audit_gap (rank, gap_ref, gap, severity, owner_hint, build_bucket) VALUES (9, 'ledger_posting_blocked', 'Ledger posting remains explicitly disallowed and must stay parked until proof chain exists.', 'HIGH', 'LEDGER', 'Parked');
INSERT INTO audit_gap (rank, gap_ref, gap, severity, owner_hint, build_bucket) VALUES (10, 'hermes_handoff_stale', 'Hermes/Chief still list invoice candidate selection as blocking despite Live Arts confirmed selection.', 'MEDIUM', 'PC_BACKEND', 'Now');
INSERT INTO audit_gap (rank, gap_ref, gap, severity, owner_hint, build_bucket) VALUES (11, 'estate_bridge_mirror_missing', 'Reference resolver marks estate topology read-model bridge mirror as MISSING.', 'MEDIUM', 'BRIDGE_TRANSPORT', 'Next');
INSERT INTO audit_gap (rank, gap_ref, gap, severity, owner_hint, build_bucket) VALUES (12, 'capital_hilton_selection_and_coupa', 'Capital Hilton still needs invoice record/period selection, Coupa proof, recipients, and artifact linkage.', 'MEDIUM', 'PC_BACKEND', 'Later');
INSERT INTO audit_gap (rank, gap_ref, gap, severity, owner_hint, build_bucket) VALUES (13, 'business_object_evals_missing', 'End-to-end business-object evals are missing for Mac helper, result intake, attachment promotion, proof, payment, and Capital Hilton.', 'HIGH', 'PC_BACKEND', 'Now');
INSERT INTO audit_recommended_action (action_ref, bucket, rank, task, reason) VALUES ('now:1', 'now', 1, 'Reconcile stale Hermes/Chief Live Arts blockers against the confirmed 2026-1001 bundle state.', 'Avoid sending Chief after already-solved candidate selection work.');
INSERT INTO audit_recommended_action (action_ref, bucket, rank, task, reason) VALUES ('now:2', 'now', 2, 'Build or verify Mac helper/Access Broker permission path for scoped Excel PDF export.', 'This is the current blocker before Live Arts PDF export retry.');
INSERT INTO audit_recommended_action (action_ref, bucket, rank, task, reason) VALUES ('now:3', 'now', 3, 'Add end-to-end evals for Mac result intake and attachment promotion without executing Excel/PDF.', 'The backend needs proof that selected_invoice_pdf_export_completed_candidate promotes safely.');
INSERT INTO audit_recommended_action (action_ref, bucket, rank, task, reason) VALUES ('next:1', 'next', 1, 'After Mac export succeeds, ingest result candidate and keep artifact OPERATOR_REVIEW_REQUIRED until reviewed.', 'Attachment readiness must remain receipt-gated.');
INSERT INTO audit_recommended_action (action_ref, bucket, rank, task, reason) VALUES ('next:2', 'next', 2, 'Confirm Live Arts recipients and Guardian/operator approval gates.', 'Clara/send readiness is blocked by recipient and approval receipts.');
INSERT INTO audit_recommended_action (action_ref, bucket, rank, task, reason) VALUES ('next:3', 'next', 3, 'Capture manual-send proof if manual send already happened, then activate payment watch readiness only.', 'Payment watch cannot become real until send proof exists.');
INSERT INTO audit_recommended_action (action_ref, bucket, rank, task, reason) VALUES ('next:4', 'next', 4, 'Repair estate topology bridge mirror and Mac bridge permission representation.', 'Resolver reports missing bridge mirror and Mac bridge unavailable.');
INSERT INTO audit_recommended_action (action_ref, bucket, rank, task, reason) VALUES ('later:1', 'later', 1, 'Advance Capital Hilton invoice selection/Coupa proof/artifact linkage rails.', 'Capital Hilton remains farther from business-object execution than Live Arts.');
INSERT INTO audit_recommended_action (action_ref, bucket, rank, task, reason) VALUES ('later:2', 'later', 2, 'Decide Mac app remote/backup strategy and runtime actor canonical home.', 'Topology known unknowns still affect repo ownership.');
INSERT INTO audit_recommended_action (action_ref, bucket, rank, task, reason) VALUES ('parked:1', 'parked', 1, 'Ledger posting automation.', 'Explicitly blocked until sent/payment/ledger receipts exist.');
INSERT INTO audit_recommended_action (action_ref, bucket, rank, task, reason) VALUES ('parked:2', 'parked', 2, 'Live email/Gmail/browser/Coupa execution.', 'Outside this audit and still receipt/authority gated.');
INSERT INTO audit_recommended_action (action_ref, bucket, rank, task, reason) VALUES ('parked:3', 'parked', 3, 'Broad LM summarization or Chief launch.', 'This audit is deterministic and read-only.');
INSERT INTO audit_freshness_signal (signal_ref, status, input_ref, reason, source_ref, observed_at) VALUES ('freshness:current', 'FRESH', '', 'Audit generated from current input manifest.', 'openclaw_business_object_layer_audit.py', '2026-05-31T21:39:11+00:00');

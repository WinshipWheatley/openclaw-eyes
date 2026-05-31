INSERT INTO sentinel_run (run_ref, generated_at, run_status, baseline_available, observed_target_count, observed_change_count, material_change_count, lm_called, timer_installed, chief_launched) VALUES ('openclaw_change_sentinel_run', '2026-05-31T04:42:21+00:00', 'NO_MATERIAL_CHANGE', 1, 25, 0, 0, 0, 0, 0);
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('input_read_model:reference_resolver', 'INPUT_READ_MODEL', 'generated/read_models/openclaw_reference_resolver.json', 'NO_MATERIAL_CHANGE', 'present', 'sha256:a3c456ace2027d44db3d3018a147a39b6fdf5dab492aebb0965a9a515908db2e', '{
  "exists": true,
  "input_ref": "reference_resolver",
  "path": "generated/read_models/openclaw_reference_resolver.json",
  "schema_version": "openclaw_reference_resolver_read_model_v0"
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('input_read_model:estate_topology', 'INPUT_READ_MODEL', 'generated/read_models/openclaw_estate_topology_registry.json', 'NO_MATERIAL_CHANGE', 'present', 'sha256:bcbe4604167416aeb5b72886a035ec3177ac52cc6c74b2570efc4b9c9f8dc629', '{
  "exists": true,
  "input_ref": "estate_topology",
  "path": "generated/read_models/openclaw_estate_topology_registry.json",
  "schema_version": "openclaw_estate_topology_registry_read_model_v0"
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('input_read_model:live_arts_bundle', 'INPUT_READ_MODEL', 'generated/read_models/live_arts_md_invoice_review_bundle.json', 'NO_MATERIAL_CHANGE', 'present', 'sha256:5d7df5fe25901c833dc3f1ddf2a5b026a5918186f8228ed51b3ed4eadfa56d13', '{
  "exists": true,
  "input_ref": "live_arts_bundle",
  "path": "generated/read_models/live_arts_md_invoice_review_bundle.json",
  "schema_version": "live_arts_md_invoice_review_bundle_v0"
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('input_read_model:capital_hilton_bundle', 'INPUT_READ_MODEL', 'generated/read_models/invoice_review_bundle.json', 'NO_MATERIAL_CHANGE', 'present', 'sha256:292371b68401848e4422694acd491cc8186f34015ba1c643b3617539c9911ab8', '{
  "exists": true,
  "input_ref": "capital_hilton_bundle",
  "path": "generated/read_models/invoice_review_bundle.json",
  "schema_version": "invoice_review_bundle_v0"
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('input_read_model:sync_health', 'INPUT_READ_MODEL', 'generated/read_models/sync_health.json', 'NO_MATERIAL_CHANGE', 'present', 'sha256:578d770c2e753f6f0c4d3d96e14665d3f127eaca76cc3750bd66be7fb4bafecb', '{
  "exists": true,
  "input_ref": "sync_health",
  "path": "generated/read_models/sync_health.json",
  "schema_version": "sync_health_read_model_v0"
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('input_read_model:request_response_service_status', 'INPUT_READ_MODEL', 'generated/read_models/openclaw_request_response_service_status.json', 'NO_MATERIAL_CHANGE', 'present', 'sha256:e35398e3a940c58187b0bb25f9658e65d1a9cbd049be7a36179de73d9d2a5dad', '{
  "exists": true,
  "input_ref": "request_response_service_status",
  "path": "generated/read_models/openclaw_request_response_service_status.json",
  "schema_version": "openclaw_request_response_service_v1"
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('input_read_model:business_object_audit', 'INPUT_READ_MODEL', 'generated/read_models/openclaw_business_object_layer_audit.json', 'NO_MATERIAL_CHANGE', 'present', 'sha256:173f336827bd5ae7d24af60963f42530aa85fc4335e846e405a5ed8c8fccd58e', '{
  "exists": true,
  "input_ref": "business_object_audit",
  "path": "generated/read_models/openclaw_business_object_layer_audit.json",
  "schema_version": "openclaw_business_object_layer_audit_read_model_v0"
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('git_branch:openclaw_eyes_registry_review_branch', 'GIT_BRANCH', 'generated/read_models/openclaw_reference_resolver.json', 'NO_MATERIAL_CHANGE', '1a6b7b0b463968f3161e048bd7936dc06505a3bb', 'sha256:c917606a41ea2f602457a282b418e300adf6cf18f898022fdbe68d0c7fc58a16', '{
  "branch": "codex/system-knowledge-registry-v0-local",
  "current_head_commit": "1a6b7b0b463968f3161e048bd7936dc06505a3bb",
  "remote_status": "RESOLVED_REMOTE",
  "remote_url": "git@github.com:WinshipWheatley/openclaw-eyes.git",
  "repo_name": "openclaw-eyes",
  "repo_ref": "openclaw-eyes",
  "resolution_source": "readonly_equivalent",
  "resolution_status": "RESOLVED_REMOTE",
  "target_ref": "openclaw_eyes_registry_review_branch"
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('repo_dirty:openclaw_eyes_registry_review_branch', 'REPO_STATE', 'generated/read_models/openclaw_reference_resolver.json', 'REPO_DIRTY', 'DIRTY', 'sha256:6c0f5a9981a579e4fb6a7345b81e075f910f2ad96a4a1c21c2a568ca1387d539', '{
  "dirty_status": "DIRTY",
  "local_path": "/home/openclaw",
  "local_status": "UNREACHABLE",
  "repo_ref": "openclaw-eyes",
  "target_ref": "openclaw_eyes_registry_review_branch"
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('mac_mirror:openclaw_eyes_registry_review_branch', 'MAC_HEARTBEAT', 'generated/read_models/openclaw_reference_resolver.json', 'UNKNOWN', 'LOCAL_PATH_UNREACHABLE', 'sha256:c705c7196044eb308cf73a993c13fb0af215f0ae4aa4873afd1beaf90d0ea160', '{
  "mac_bridge_resolution_path": "",
  "mac_bridge_status": "MAC_BRIDGE_UNAVAILABLE",
  "mac_mirror_path": "/Users/hwinshipwheatley/Eyes",
  "mac_mirror_status": "LOCAL_PATH_UNREACHABLE",
  "target_ref": "openclaw_eyes_registry_review_branch"
}', 'LOCAL_PATH_UNREACHABLE', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('git_branch:openclaw_eyes_main_branch', 'GIT_BRANCH', 'generated/read_models/openclaw_reference_resolver.json', 'NO_MATERIAL_CHANGE', '1a6b7b0b463968f3161e048bd7936dc06505a3bb', 'sha256:e002f62edb1ef789db5992e4c42923bafa3e4680a053798ce87dcbb95208269d', '{
  "branch": "main",
  "current_head_commit": "1a6b7b0b463968f3161e048bd7936dc06505a3bb",
  "remote_status": "RESOLVED_REMOTE",
  "remote_url": "git@github.com:WinshipWheatley/openclaw-eyes.git",
  "repo_name": "openclaw-eyes-main",
  "repo_ref": "openclaw-eyes-main",
  "resolution_source": "readonly_equivalent",
  "resolution_status": "RESOLVED_REMOTE",
  "target_ref": "openclaw_eyes_main_branch"
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('repo_dirty:openclaw_eyes_main_branch', 'REPO_STATE', 'generated/read_models/openclaw_reference_resolver.json', 'NO_MATERIAL_CHANGE', 'UNKNOWN', 'sha256:ee34ab2b6a19fc8838d7e1473da91bb14fd1c972bf09f2908cbee8f0efbd864d', '{
  "dirty_status": "UNKNOWN",
  "local_path": "",
  "local_status": "UNKNOWN",
  "repo_ref": "openclaw-eyes-main",
  "target_ref": "openclaw_eyes_main_branch"
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('mac_mirror:openclaw_eyes_main_branch', 'MAC_HEARTBEAT', 'generated/read_models/openclaw_reference_resolver.json', 'UNKNOWN', 'UNKNOWN', 'sha256:162fb073f72649f1dba8febcb1e40f3d5dbc74be46eadf86d52e3e48e36442a6', '{
  "mac_bridge_resolution_path": "",
  "mac_bridge_status": "MAC_BRIDGE_UNAVAILABLE",
  "mac_mirror_path": "",
  "mac_mirror_status": "UNKNOWN",
  "target_ref": "openclaw_eyes_main_branch"
}', 'UNKNOWN', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('read_model_mirror:estate_topology_registry_read_model_mirror', 'READ_MODEL_MIRROR', 'generated/read_models/openclaw_reference_resolver.json', 'BRIDGE_STALE', 'MISSING:False:False', 'sha256:f862a60959499fe1e5b03ad67e1946d6cbbce3bf90189fe166c93f5798e3e8ce', '{
  "bridge_exists": false,
  "bridge_path": "/mnt/e/openclaw/generated/read_models/openclaw_estate_topology_registry.json",
  "hash_match": false,
  "resolved_status": "MISSING",
  "source_exists": true,
  "source_path": "generated/read_models/openclaw_estate_topology_registry.json",
  "target_ref": "estate_topology_registry_read_model_mirror"
}', 'source or bridge counterpart missing', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('known_unknowns:unresolved', 'KNOWN_UNKNOWN', 'generated/read_models/openclaw_estate_topology_registry.json', 'ACTION_REQUIRED', '6', 'sha256:b34075790bbc043423e7c796b47125c70f4531c92b44f9a6d1faf9f72060f6ee', '{
  "unknown_ids": [
    "codex_web_commits_unreachable",
    "mac_app_remote_backup_strategy",
    "dual_openclaw_eyes_long_term",
    "runtime_actor_canonical_home",
    "hermes_first_read_repo",
    "mac_bridge_permission_model"
  ],
  "unresolved_count": 6
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('codex_web_artifacts:stale_or_unreachable', 'CODEX_WEB_ARTIFACT', 'generated/read_models/openclaw_estate_topology_registry.json', 'ACTION_REQUIRED', '2', 'sha256:f2d8894a1e3ffb0510f29cc62d71649ab59f4d13fb3b93def95cd39643e8a137', '{
  "artifact_count": 2,
  "artifact_ids": [
    "codex_web_registry_commit_33e00a6",
    "codex_web_registry_commit_4ca4ed42171c23d60ef89493559808ef2789a19e"
  ],
  "statuses": {
    "codex_web_registry_commit_33e00a6": "UNREACHABLE",
    "codex_web_registry_commit_4ca4ed42171c23d60ef89493559808ef2789a19e": "UNREACHABLE"
  }
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('workflow_state:live_arts_md_invoice_workflow', 'WORKFLOW_STATE', 'generated/read_models/live_arts_md_invoice_review_bundle.json', 'NO_MATERIAL_CHANGE', 'sha256:2ba48386654f54498e222caa81793b6e9d0b2e1198f9db5680e0c057f77d8b06', 'sha256:2ba48386654f54498e222caa81793b6e9d0b2e1198f9db5680e0c057f77d8b06', '{
  "artifact_review_status": "NOT_READY",
  "attachment_ready": false,
  "bundle_status": "SIMPLE_EMAIL_INVOICE_REVIEW",
  "candidate_selection_status": "OPERATOR_CONFIRMED",
  "client_ref": "live_arts_md",
  "invoice_selection_status": "OPERATOR_CONFIRMED",
  "selected_invoice_ids": [
    "2026-1001"
  ],
  "selected_invoice_summary": "2026-1001 \u2014 June 2026 Speaker Rental \u2014 $900",
  "workflow_ref": "live_arts_md_invoice_workflow"
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('pdf_export_package:live_arts_md_invoice_workflow', 'PDF_EXPORT_PACKAGE', 'generated/read_models/live_arts_md_invoice_review_bundle.json', 'NO_MATERIAL_CHANGE', 'PDF_EXPORT_PACKAGE_READY_FOR_MAC', 'sha256:3df12ff7063ab9dbb924a4881f1de626703027d9ad612d33abfa5fd86e8d069a', '{
  "client_ref": "live_arts_md",
  "invoice_id": "2026-1001",
  "job_ref": "mac_edge_job_2026-1001_0b03bcc7",
  "request_payload_ready": true,
  "result_intended_use": "selected_invoice_pdf_export_completed_candidate",
  "selected_print_areas": [
    "June 2026 Speaker Rental!G2:G5",
    "June 2026 Speaker Rental!F40:G43",
    "June 2026 Speaker Rental!B49:G53"
  ],
  "selected_sheet_label": "June 2026 Speaker Rental",
  "status": "PDF_EXPORT_PACKAGE_READY_FOR_MAC",
  "workflow_ref": "live_arts_md_invoice_workflow"
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('payment_watch:live_arts_md_invoice_workflow', 'PAYMENT_WATCH', 'generated/read_models/live_arts_md_invoice_review_bundle.json', 'NO_MATERIAL_CHANGE', 'READINESS_ONLY_NOT_ACTIVE', 'sha256:2b4df287ce812b5251b44f06a44984f94ded6c1453d3b1dce3b649df163b14eb', '{
  "client_ref": "live_arts_md",
  "payment_watch_status": "READINESS_ONLY_NOT_ACTIVE",
  "workflow_ref": "live_arts_md_invoice_workflow"
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('workflow_state:capital_hilton_invoice_workflow', 'WORKFLOW_STATE', 'generated/read_models/invoice_review_bundle.json', 'NO_MATERIAL_CHANGE', 'sha256:fb5d4a9bfdee073cb7527be0affbe86ad0214a9a6e9d7510a187822a81027223', 'sha256:fb5d4a9bfdee073cb7527be0affbe86ad0214a9a6e9d7510a187822a81027223', '{
  "bundle_status": "READY_FOR_REVIEW_BLOCKED_FOR_SELECTION",
  "client_ref": "capital_hilton",
  "generated_artifact_status": "GENERATION_AUTHORITY_REQUIRED",
  "invoice_period_status": "NEEDS_OPERATOR_SELECTION",
  "invoice_record_selection_status": "NEEDS_OPERATOR_SELECTION",
  "recipient_review_status": "NEEDS_CONTACT_CONFIRMATION",
  "semantic_status": {
    "clara_draft_status": "DRAFT_ONLY",
    "coupa_portal_rail_status": "PRIMARY_PAYMENT_TRIGGER_BLOCKED_PROOF_MISSING",
    "coupa_submission_proof_status": "MISSING",
    "email_send_execution_status": "NOT_SENT",
    "excel_invoice_artifact_status": "GENERATED_INVOICE_ARTIFACT_CANDIDATE",
    "excel_invoice_attachment_ready": false,
    "guardian_approval_request_status": "BLOCKED_PREREQUISITES_MISSING",
    "guardian_output_validation_status": "PASSED_FOR_DRAFT_DISPLAY_ONLY",
    "operator_approval_status": "NOT_GRANTED",
    "payment_watch_status": "NOT_RECEIVED",
    "portal_submission_execution_status": "NOT_SUBMITTED",
    "primary_invoice_trigger": "COUPA_SUPPLIER_PORTAL_INVOICE",
    "supporting_artifacts": [
      "excel_invoice_for_records",
      "clara_email_draft_for_annette"
    ]
  },
  "supplier_portal_proof_status": "PROOF_REQUESTED",
  "workflow_ref": "capital_hilton_invoice_workflow"
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('payment_watch:capital_hilton_invoice_workflow', 'PAYMENT_WATCH', 'generated/read_models/invoice_review_bundle.json', 'NO_MATERIAL_CHANGE', 'NOT_READY', 'sha256:56faca26e33a23df6f1f82bdd997b06e817808cc100bf30bd47f0b2f3aaac009', '{
  "client_ref": "capital_hilton",
  "payment_watch_status": "NOT_READY",
  "workflow_ref": "capital_hilton_invoice_workflow"
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('mac_heartbeat:sync_health', 'MAC_HEARTBEAT', 'generated/read_models/sync_health.json', 'BRIDGE_STALE', 'stale_needs_mac_sync', 'sha256:b93cd274f755a65b0445142cee092e331db4c5ebbb63fcf8c791d6b145b9886d', '{
  "hash_mismatch": 7,
  "last_mac_completion": {
    "status": "synced",
    "time": "2026-05-23T23:36:01+00:00"
  },
  "last_mac_heartbeat": {
    "manifest_written": true,
    "marker_seen": true,
    "status": "idle",
    "time": "2026-05-31T04:38:43+00:00"
  },
  "mirror_status": "needs_mac_sync",
  "missing_expected": 265,
  "sync_lifecycle_state": "actionable_sync_failure",
  "trust_status": "stale_needs_mac_sync"
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('business_object_audit:freshness', 'BUSINESS_OBJECT_AUDIT', 'generated/read_models/openclaw_business_object_layer_audit.json', 'NO_MATERIAL_CHANGE', 'FRESH', 'sha256:edd7974d907f6cd996e5c31010d7d7f7e5141bc3ef8763197fbba092fe90db23', '{
  "current_hashes": {
    "capital_hilton_bundle": "sha256:f384551a2558a0f8c8ef8bbfeea37f4d9d3fdd08f422a543e4385cd09964ed71",
    "context_wiki_index": "sha256:ed4b535363c9ae0befdcf2356dcab59a9adfe20e8ee14c6c1f1dc6566c848c1b",
    "estate_topology": "sha256:e32c278f0bb6c52fd2c3e514406f93e9b2c8dd9724825164ec4158d21c7fb2ae",
    "external_system_knowledge_registry_index": "sha256:5665a7b3bfbfec9a9c9a6df1a99a13f93194dd04fb46958176c2cd1f30769c50",
    "hermes_chief_build_handoff": "sha256:3fc1448b7a8236a3142814315790c427797c646295276429c6ceee42b005388a",
    "hermes_gravity_controller": "sha256:51d57984bea39a6769fcaba0129e69a26e7761bfefc0a18b0d9ff77ffe628bec",
    "hermes_mission_sentinel": "sha256:5fb7f99839fd0763bb60eddcbaf7167a301c7ef6a90880d0888a8233435b0a47",
    "live_arts_bundle": "sha256:32aed1bf62bceab78634e1feeb02651b41155f27827aae8433e5df18db1d352b",
    "purpose_bound_automation_charter": "sha256:3460326c5e60000944ec87e8ab2361ed024df50ac7d736c33ce154ed6cb5d750",
    "reference_resolver": "sha256:ca025f59ab8060942c7a75f1b1e4a8d562d9c50e807d7c96fa5c1312f009adba",
    "service_supervision": "sha256:b92e768756c9a0d4302569f350e78db6c978d21871a9529fe9dcc324c565728d"
  },
  "fresh_for_minutes": 60,
  "freshness_status": "FRESH",
  "mismatched_inputs": [],
  "missing_required_inputs": [],
  "recommended_command": "python3 scripts/export_openclaw_business_object_layer_audit.py",
  "recorded_hashes": {
    "capital_hilton_bundle": "sha256:f384551a2558a0f8c8ef8bbfeea37f4d9d3fdd08f422a543e4385cd09964ed71",
    "context_wiki_index": "sha256:ed4b535363c9ae0befdcf2356dcab59a9adfe20e8ee14c6c1f1dc6566c848c1b",
    "estate_topology": "sha256:e32c278f0bb6c52fd2c3e514406f93e9b2c8dd9724825164ec4158d21c7fb2ae",
    "external_system_knowledge_registry_index": "sha256:5665a7b3bfbfec9a9c9a6df1a99a13f93194dd04fb46958176c2cd1f30769c50",
    "hermes_chief_build_handoff": "sha256:3fc1448b7a8236a3142814315790c427797c646295276429c6ceee42b005388a",
    "hermes_gravity_controller": "sha256:51d57984bea39a6769fcaba0129e69a26e7761bfefc0a18b0d9ff77ffe628bec",
    "hermes_mission_sentinel": "sha256:5fb7f99839fd0763bb60eddcbaf7167a301c7ef6a90880d0888a8233435b0a47",
    "live_arts_bundle": "sha256:32aed1bf62bceab78634e1feeb02651b41155f27827aae8433e5df18db1d352b",
    "purpose_bound_automation_charter": "sha256:3460326c5e60000944ec87e8ab2361ed024df50ac7d736c33ce154ed6cb5d750",
    "reference_resolver": "sha256:ca025f59ab8060942c7a75f1b1e4a8d562d9c50e807d7c96fa5c1312f009adba",
    "service_supervision": "sha256:b92e768756c9a0d4302569f350e78db6c978d21871a9529fe9dcc324c565728d"
  },
  "skipped_self_referential_inputs": [
    "change_sentinel"
  ]
}', '', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('service_status:openclaw-request-response.service', 'SERVICE', 'systemd:user:show', 'UNKNOWN', '', 'sha256:d72730b1ae8f78574f7e4af6f9a8125217892deccf76a115711d1de7ef5e7fbd', '{
  "active_state": "",
  "available": false,
  "error": "Failed to connect to bus: Operation not permitted",
  "exec_main_status": "",
  "n_restarts": "",
  "result": "",
  "service_name": "openclaw-request-response.service",
  "sub_state": ""
}', 'Failed to connect to bus: Operation not permitted', '2026-05-31T04:42:21+00:00');
INSERT INTO observed_target (target_ref, target_type, source_path, observation_status, observed_value, fingerprint, observed_json, unreachable_reason, observed_at) VALUES ('service_restart_count:openclaw-request-response.service', 'SERVICE', 'systemd:user:show', 'UNKNOWN', '', 'sha256:d72730b1ae8f78574f7e4af6f9a8125217892deccf76a115711d1de7ef5e7fbd', '{
  "active_state": "",
  "available": false,
  "error": "Failed to connect to bus: Operation not permitted",
  "exec_main_status": "",
  "n_restarts": "",
  "result": "",
  "service_name": "openclaw-request-response.service",
  "sub_state": ""
}', 'Failed to connect to bus: Operation not permitted', '2026-05-31T04:42:21+00:00');
INSERT INTO hermes_summary (summary_ref, run_ref, what_changed, why_it_matters, what_to_do_next, action_required, can_wait, lm_summary_candidate_json) VALUES ('hermes_summary:latest', 'openclaw_change_sentinel_run', 'No material change since the previous sentinel snapshot.', 'OpenClaw can keep using the current generated state.', 'No action required; rerun on the next 20-minute cadence or manually when needed.', 0, 1, '{
  "future_use": "A later bounded diff summarizer may read material_changes only.",
  "input_scope": "observed_change and material_change rows from this run",
  "lm_call_performed": false
}');

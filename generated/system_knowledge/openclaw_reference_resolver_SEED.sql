INSERT INTO reference_target (target_ref, target_type, repo_ref, local_path, remote_url, branch, mac_mirror_path, mac_bridge_resolution_path, source_path, bridge_path, receipt_type, artifact_ref, canonical_input_json, refresh_policy, owner_component, status) VALUES ('openclaw_eyes_registry_review_branch', 'GIT_BRANCH', 'openclaw-eyes', '/home/openclaw', 'git@github.com:WinshipWheatley/openclaw-eyes.git', 'codex/system-knowledge-registry-v0-local', '/Users/hwinshipwheatley/Eyes', '', '', '', '', '', '{
  "branch": "codex/system-knowledge-registry-v0-local",
  "remote_url": "git@github.com:WinshipWheatley/openclaw-eyes.git",
  "repo_ref": "openclaw-eyes"
}', 'ON_EXPORT', 'openclaw_estate_topology_registry', 'ACTIVE');
INSERT INTO reference_target (target_ref, target_type, repo_ref, local_path, remote_url, branch, mac_mirror_path, mac_bridge_resolution_path, source_path, bridge_path, receipt_type, artifact_ref, canonical_input_json, refresh_policy, owner_component, status) VALUES ('estate_topology_registry_read_model_mirror', 'READ_MODEL_MIRROR', '', '', '', '', '', '', 'generated/read_models/openclaw_estate_topology_registry.json', '/mnt/e/openclaw/generated/read_models/openclaw_estate_topology_registry.json', '', '', '{
  "bridge_path": "/mnt/e/openclaw/generated/read_models/openclaw_estate_topology_registry.json",
  "source_path": "generated/read_models/openclaw_estate_topology_registry.json"
}', 'ON_EXPORT', 'openclaw_estate_topology_registry', 'ACTIVE');
INSERT INTO reference_target (target_ref, target_type, repo_ref, local_path, remote_url, branch, mac_mirror_path, mac_bridge_resolution_path, source_path, bridge_path, receipt_type, artifact_ref, canonical_input_json, refresh_policy, owner_component, status) VALUES ('openclaw_eyes_main_branch', 'GIT_BRANCH', 'openclaw-eyes-main', '', 'git@github.com:WinshipWheatley/openclaw-eyes.git', 'main', '', '', '', '', '', '', '{
  "branch": "main",
  "remote_url": "git@github.com:WinshipWheatley/openclaw-eyes.git",
  "repo_ref": "openclaw-eyes"
}', 'ON_EXPORT', 'openclaw_estate_topology_registry', 'ACTIVE');
INSERT INTO reference_resolution (resolution_ref, target_ref, resolved_status, resolved_value, resolved_json, dirty_status, error_message, resolved_at) VALUES ('openclaw_eyes_registry_review_branch_resolution', 'openclaw_eyes_registry_review_branch', 'RESOLVED_REMOTE', '1a6b7b0b463968f3161e048bd7936dc06505a3bb', '{
  "branch": "codex/system-knowledge-registry-v0-local",
  "current_head_commit": "1a6b7b0b463968f3161e048bd7936dc06505a3bb",
  "dirty_status": "DIRTY",
  "local_error": "local branch not reachable: codex/system-knowledge-registry-v0-local",
  "local_path": "/home/openclaw",
  "local_status": "UNREACHABLE",
  "mac_bridge_error": "Mac bridge resolution path not configured",
  "mac_bridge_resolution_path": "",
  "mac_bridge_status": "MAC_BRIDGE_UNAVAILABLE",
  "mac_mirror_error": "Mac mirror path is not reachable from this machine",
  "mac_mirror_path": "/Users/hwinshipwheatley/Eyes",
  "mac_mirror_status": "LOCAL_PATH_UNREACHABLE",
  "reachable": true,
  "remote_error": "",
  "remote_resolution_source": "readonly_equivalent",
  "remote_status": "RESOLVED_REMOTE",
  "remote_url": "git@github.com:WinshipWheatley/openclaw-eyes.git",
  "repo_ref": "openclaw-eyes",
  "resolution_source": "readonly_equivalent",
  "resolved_at": "2026-05-31T04:09:09+00:00",
  "resolved_status": "RESOLVED_REMOTE",
  "target_ref": "openclaw_eyes_registry_review_branch",
  "target_type": "GIT_BRANCH"
}', 'DIRTY', '', '2026-05-31T04:09:09+00:00');
INSERT INTO reference_resolution (resolution_ref, target_ref, resolved_status, resolved_value, resolved_json, dirty_status, error_message, resolved_at) VALUES ('estate_topology_registry_read_model_mirror_resolution', 'estate_topology_registry_read_model_mirror', 'MISSING', 'sha256:1d1a95fb7e61b38703ce26c45895ed031f7b9aef329a8e3e4306d7e71711b8df', '{
  "bridge_exists": false,
  "bridge_path": "/mnt/e/openclaw/generated/read_models/openclaw_estate_topology_registry.json",
  "hash_match": false,
  "resolved_at": "2026-05-31T04:09:09+00:00",
  "resolved_status": "MISSING",
  "sha256_bridge": "",
  "sha256_source": "sha256:1d1a95fb7e61b38703ce26c45895ed031f7b9aef329a8e3e4306d7e71711b8df",
  "source_exists": true,
  "source_path": "generated/read_models/openclaw_estate_topology_registry.json",
  "target_ref": "estate_topology_registry_read_model_mirror",
  "target_type": "READ_MODEL_MIRROR"
}', '', 'source or bridge counterpart missing', '2026-05-31T04:09:09+00:00');
INSERT INTO reference_resolution (resolution_ref, target_ref, resolved_status, resolved_value, resolved_json, dirty_status, error_message, resolved_at) VALUES ('openclaw_eyes_main_branch_resolution', 'openclaw_eyes_main_branch', 'RESOLVED_REMOTE', '1a6b7b0b463968f3161e048bd7936dc06505a3bb', '{
  "branch": "main",
  "current_head_commit": "1a6b7b0b463968f3161e048bd7936dc06505a3bb",
  "dirty_status": "UNKNOWN",
  "local_error": "local path not configured",
  "local_path": "",
  "local_status": "UNKNOWN",
  "mac_bridge_error": "Mac bridge resolution path not configured",
  "mac_bridge_resolution_path": "",
  "mac_bridge_status": "MAC_BRIDGE_UNAVAILABLE",
  "mac_mirror_error": "Mac mirror path not configured",
  "mac_mirror_path": "",
  "mac_mirror_status": "UNKNOWN",
  "reachable": true,
  "remote_error": "",
  "remote_resolution_source": "readonly_equivalent",
  "remote_status": "RESOLVED_REMOTE",
  "remote_url": "git@github.com:WinshipWheatley/openclaw-eyes.git",
  "repo_ref": "openclaw-eyes-main",
  "resolution_source": "readonly_equivalent",
  "resolved_at": "2026-05-31T04:09:09+00:00",
  "resolved_status": "RESOLVED_REMOTE",
  "target_ref": "openclaw_eyes_main_branch",
  "target_type": "GIT_BRANCH"
}', 'UNKNOWN', '', '2026-05-31T04:09:09+00:00');
INSERT INTO reference_dependency (dependency_ref, target_ref, consumer_component, generated_model_path, reason) VALUES ('estate_topology_uses_openclaw_eyes_registry_review_branch', 'openclaw_eyes_registry_review_branch', 'openclaw_estate_topology_registry', 'generated/read_models/openclaw_estate_topology_registry.json', 'Estate topology stores the branch ref as canonical input and resolves current_head_commit during export.');
INSERT INTO reference_dependency (dependency_ref, target_ref, consumer_component, generated_model_path, reason) VALUES ('estate_topology_checks_openclaw_eyes_main_for_canonical_registry', 'openclaw_eyes_main_branch', 'openclaw_estate_topology_registry', 'generated/read_models/openclaw_estate_topology_registry.json', 'Estate topology marks the system knowledge registry canonical only when main resolves to the registry commit.');
INSERT INTO resolution_run (run_ref, started_at, completed_at, targets_checked, drift_count, status) VALUES ('openclaw_reference_resolver_run', '2026-05-31T04:09:09+00:00', '2026-05-31T04:09:09+00:00', 3, 0, 'RESOLVED_LOCAL');

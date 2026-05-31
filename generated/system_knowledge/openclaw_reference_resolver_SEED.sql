INSERT INTO reference_target (target_ref, target_type, repo_ref, local_path, remote_url, branch, mac_mirror_path, mac_bridge_resolution_path, source_path, bridge_path, receipt_type, artifact_ref, canonical_input_json, refresh_policy, owner_component, status) VALUES ('openclaw_eyes_registry_review_branch', 'GIT_BRANCH', 'openclaw-eyes', '/home/openclaw', 'git@github.com:WinshipWheatley/openclaw-eyes.git', 'codex/system-knowledge-registry-v0-local', '/Users/hwinshipwheatley/Eyes', '', '', '', '', '', '{
  "branch": "codex/system-knowledge-registry-v0-local",
  "remote_url": "git@github.com:WinshipWheatley/openclaw-eyes.git",
  "repo_ref": "openclaw-eyes"
}', 'ON_EXPORT', 'openclaw_estate_topology_registry', 'ACTIVE');
INSERT INTO reference_target (target_ref, target_type, repo_ref, local_path, remote_url, branch, mac_mirror_path, mac_bridge_resolution_path, source_path, bridge_path, receipt_type, artifact_ref, canonical_input_json, refresh_policy, owner_component, status) VALUES ('estate_topology_registry_read_model_mirror', 'READ_MODEL_MIRROR', '', '', '', '', '', '', 'generated/read_models/openclaw_estate_topology_registry.json', '/mnt/e/openclaw/generated/read_models/openclaw_estate_topology_registry.json', '', '', '{
  "bridge_path": "/mnt/e/openclaw/generated/read_models/openclaw_estate_topology_registry.json",
  "source_path": "generated/read_models/openclaw_estate_topology_registry.json"
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
  "resolved_at": "2026-05-31T02:59:53+00:00",
  "resolved_status": "RESOLVED_REMOTE",
  "target_ref": "openclaw_eyes_registry_review_branch",
  "target_type": "GIT_BRANCH"
}', 'DIRTY', '', '2026-05-31T02:59:53+00:00');
INSERT INTO reference_resolution (resolution_ref, target_ref, resolved_status, resolved_value, resolved_json, dirty_status, error_message, resolved_at) VALUES ('estate_topology_registry_read_model_mirror_resolution', 'estate_topology_registry_read_model_mirror', 'MISSING', 'sha256:8b3e48e23dd812e3f2fe8178bee322c9e0557192aa7e48bb55734f1a811258c1', '{
  "bridge_exists": false,
  "bridge_path": "/mnt/e/openclaw/generated/read_models/openclaw_estate_topology_registry.json",
  "hash_match": false,
  "resolved_at": "2026-05-31T02:59:53+00:00",
  "resolved_status": "MISSING",
  "sha256_bridge": "",
  "sha256_source": "sha256:8b3e48e23dd812e3f2fe8178bee322c9e0557192aa7e48bb55734f1a811258c1",
  "source_exists": true,
  "source_path": "generated/read_models/openclaw_estate_topology_registry.json",
  "target_ref": "estate_topology_registry_read_model_mirror",
  "target_type": "READ_MODEL_MIRROR"
}', '', 'source or bridge counterpart missing', '2026-05-31T02:59:53+00:00');
INSERT INTO reference_dependency (dependency_ref, target_ref, consumer_component, generated_model_path, reason) VALUES ('estate_topology_uses_openclaw_eyes_registry_review_branch', 'openclaw_eyes_registry_review_branch', 'openclaw_estate_topology_registry', 'generated/read_models/openclaw_estate_topology_registry.json', 'Estate topology stores the branch ref as canonical input and resolves current_head_commit during export.');
INSERT INTO resolution_run (run_ref, started_at, completed_at, targets_checked, drift_count, status) VALUES ('openclaw_reference_resolver_run', '2026-05-31T02:59:53+00:00', '2026-05-31T02:59:53+00:00', 2, 0, 'RESOLVED_LOCAL');

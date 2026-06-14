-- OpenClaw Eyes System Knowledge Registry schema

-- Generated for documentation/read-model/SQLite review only.

CREATE TABLE IF NOT EXISTS system_component (
  component_id TEXT NOT NULL,
  display_name TEXT NOT NULL,
  component_type TEXT NOT NULL,
  evidence_status TEXT NOT NULL,
  evidence_paths_json TEXT NOT NULL,
  summary TEXT NOT NULL,
  authority_boundary TEXT NOT NULL,
  PRIMARY KEY (component_id)
);

CREATE TABLE IF NOT EXISTS capability (
  capability_id TEXT NOT NULL,
  component_id TEXT NOT NULL,
  capability_name TEXT NOT NULL,
  evidence_status TEXT NOT NULL,
  evidence_basis TEXT NOT NULL,
  boundary TEXT NOT NULL,
  PRIMARY KEY (capability_id)
);

CREATE TABLE IF NOT EXISTS workflow_rail (
  workflow_id TEXT NOT NULL,
  component_id TEXT NOT NULL,
  rail_name TEXT NOT NULL,
  evidence_status TEXT NOT NULL,
  evidence_basis TEXT NOT NULL,
  boundary TEXT NOT NULL,
  PRIMARY KEY (workflow_id)
);

CREATE TABLE IF NOT EXISTS knowledge_claim (
  claim_id TEXT NOT NULL,
  subject TEXT NOT NULL,
  claim TEXT NOT NULL,
  evidence_status TEXT NOT NULL,
  evidence_paths_json TEXT NOT NULL,
  confidence TEXT NOT NULL,
  PRIMARY KEY (claim_id)
);

CREATE TABLE IF NOT EXISTS known_unknown (
  unknown_id TEXT NOT NULL,
  subject TEXT NOT NULL,
  unknown_status TEXT NOT NULL,
  reason TEXT NOT NULL,
  next_safe_check TEXT NOT NULL,
  PRIMARY KEY (unknown_id)
);

CREATE TABLE IF NOT EXISTS build_task (
  task_id TEXT NOT NULL,
  task_rank INTEGER NOT NULL,
  title TEXT NOT NULL,
  model_class_recommendation TEXT NOT NULL,
  rationale TEXT NOT NULL,
  status TEXT NOT NULL,
  boundary TEXT NOT NULL,
  PRIMARY KEY (task_id)
);

CREATE TABLE IF NOT EXISTS agent_role (
  role_id TEXT NOT NULL,
  agent_name TEXT NOT NULL,
  role_summary TEXT NOT NULL,
  evidence_status TEXT NOT NULL,
  evidence_paths_json TEXT NOT NULL,
  authority_notes TEXT NOT NULL,
  PRIMARY KEY (role_id)
);

CREATE TABLE IF NOT EXISTS artifact_policy (
  policy_id TEXT NOT NULL,
  artifact_name TEXT NOT NULL,
  allowed_surfaces TEXT NOT NULL,
  blocked_actions TEXT NOT NULL,
  evidence_basis TEXT NOT NULL,
  evidence_status TEXT NOT NULL,
  PRIMARY KEY (policy_id)
);

CREATE TABLE IF NOT EXISTS registry_sqlite_display_surface (
  surface_id TEXT NOT NULL,
  surface_name TEXT NOT NULL,
  table_name TEXT NOT NULL,
  display_purpose TEXT NOT NULL,
  operator_notes TEXT NOT NULL,
  PRIMARY KEY (surface_id)
);

CREATE TABLE IF NOT EXISTS repo_relationship_analysis (
  analysis_id TEXT NOT NULL,
  relationship_name TEXT NOT NULL,
  local_evidence_status TEXT NOT NULL,
  conclusion TEXT NOT NULL,
  known_unknown_refs_json TEXT NOT NULL,
  next_step TEXT NOT NULL,
  PRIMARY KEY (analysis_id)
);

-- OpenClaw System Knowledge Registry schema

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

CREATE TABLE IF NOT EXISTS brain_route_inventory (
  brain_id TEXT NOT NULL,
  legacy_router_wired TEXT NOT NULL,
  current_state TEXT NOT NULL,
  mission_lane TEXT NOT NULL,
  disposition_action TEXT NOT NULL,
  compose_status TEXT NOT NULL,
  evidence_ref TEXT NOT NULL,
  boundary TEXT NOT NULL,
  PRIMARY KEY (brain_id)
);

CREATE TABLE IF NOT EXISTS orchestration_decision (
  decision_id TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  decision TEXT NOT NULL,
  status TEXT NOT NULL,
  boundary TEXT NOT NULL,
  next_safe_action TEXT NOT NULL,
  PRIMARY KEY (decision_id)
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
  owner_lane TEXT NOT NULL,
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

CREATE TABLE IF NOT EXISTS authority_boundary (
  boundary_id TEXT NOT NULL,
  boundary_name TEXT NOT NULL,
  allowed TEXT NOT NULL,
  blocked TEXT NOT NULL,
  evidence_basis TEXT NOT NULL,
  notes TEXT NOT NULL,
  PRIMARY KEY (boundary_id)
);

CREATE TABLE IF NOT EXISTS safety_posture (
  posture_id TEXT NOT NULL,
  posture_name TEXT NOT NULL,
  state TEXT NOT NULL,
  evidence_basis TEXT NOT NULL,
  operator_summary TEXT NOT NULL,
  next_safe_action TEXT NOT NULL,
  PRIMARY KEY (posture_id)
);

CREATE TABLE IF NOT EXISTS advice_integrity_receipt (
  receipt_id TEXT NOT NULL,
  desired_outcome TEXT NOT NULL,
  verified_constraints TEXT NOT NULL,
  protected_currencies_considered TEXT NOT NULL,
  minimum_sufficient_option TEXT NOT NULL,
  recommended_posture TEXT NOT NULL,
  premium_justification TEXT NOT NULL,
  restraint_rationale TEXT NOT NULL,
  integrity_tests_applied TEXT NOT NULL,
  client_agency_preserved TEXT NOT NULL,
  commercial_interest_alignment TEXT NOT NULL,
  trust_gear_state TEXT NOT NULL,
  agent_contributions TEXT NOT NULL,
  evidence_refs TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  status TEXT NOT NULL,
  PRIMARY KEY (receipt_id)
);

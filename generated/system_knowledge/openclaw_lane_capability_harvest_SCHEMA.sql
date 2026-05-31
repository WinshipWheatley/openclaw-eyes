CREATE TABLE lane (
  lane_ref TEXT PRIMARY KEY,
  lane_name TEXT,
  business_object_type TEXT,
  client_ref TEXT,
  workflow_ref TEXT,
  status TEXT,
  current_stage TEXT,
  canonical_owner_repo TEXT,
  source_refs TEXT,
  operator_summary TEXT,
  developer_summary TEXT
);

CREATE TABLE harvested_capability (
  capability_ref TEXT PRIMARY KEY,
  capability_name TEXT,
  capability_type TEXT,
  produced_by_lane TEXT,
  status TEXT,
  reusable INTEGER,
  reusable_by TEXT,
  not_reusable_by TEXT,
  evidence_refs TEXT,
  tests_refs TEXT,
  risk_notes TEXT
);

CREATE TABLE capability_dependency (
  dependency_ref TEXT PRIMARY KEY,
  capability_ref TEXT,
  depends_on_capability_ref TEXT,
  dependency_type TEXT,
  notes TEXT
);

CREATE TABLE lane_reuse_plan (
  reuse_plan_ref TEXT PRIMARY KEY,
  source_lane_ref TEXT,
  target_lane_ref TEXT,
  reused_capabilities TEXT,
  new_capabilities_to_add TEXT,
  blocked_capabilities TEXT,
  expected_tests TEXT,
  status TEXT
);

CREATE TABLE next_lane_candidate (
  candidate_ref TEXT PRIMARY KEY,
  lane_name TEXT,
  business_object_type TEXT,
  reason_to_build TEXT,
  capabilities_reused TEXT,
  capabilities_added TEXT,
  novelty_score INTEGER,
  reuse_score INTEGER,
  risk_score INTEGER,
  expected_leverage TEXT,
  recommended_order INTEGER,
  preferred_model TEXT,
  prerequisites TEXT,
  do_not_do TEXT,
  status TEXT
);

CREATE TABLE hermes_recommendation (
  recommendation_ref TEXT PRIMARY KEY,
  generated_at TEXT,
  recommended_next_lane TEXT,
  reason TEXT,
  evidence_refs TEXT,
  required_preconditions TEXT,
  expected_new_capability TEXT,
  expected_reused_capabilities TEXT,
  confidence TEXT,
  operator_copy TEXT,
  chief_build_task_ref TEXT
);

CREATE TABLE capability_gap (
  gap_ref TEXT PRIMARY KEY,
  gap_name TEXT,
  affected_lanes TEXT,
  missing_capability TEXT,
  why_it_matters TEXT,
  severity TEXT,
  suggested_fix TEXT,
  target_repo TEXT,
  preferred_model TEXT,
  status TEXT
);

CREATE TABLE proof_run (
  proof_ref TEXT,
  proof_run_id TEXT PRIMARY KEY,
  started_at TEXT,
  completed_at TEXT,
  status TEXT,
  correlation_id TEXT,
  request_path TEXT,
  response_path TEXT,
  mac_job_path TEXT,
  expected_route TEXT,
  actual_route TEXT,
  selected_handler_id TEXT,
  boundary_flags TEXT,
  operator_summary TEXT
);

CREATE TABLE proof_step (
  step_ref TEXT,
  proof_run_id TEXT,
  status TEXT,
  summary TEXT,
  path TEXT
);

CREATE TABLE proof_artifact (
  artifact_ref TEXT,
  proof_run_id TEXT,
  path TEXT,
  artifact_exists INTEGER,
  purpose TEXT
);

CREATE TABLE proof_result (
  proof_ref TEXT,
  proof_run_id TEXT,
  status TEXT,
  route_status TEXT,
  workflow_status TEXT,
  selected_handler_id TEXT,
  correlation_id TEXT
);

CREATE TABLE proof_failure (
  failure_ref TEXT,
  proof_run_id TEXT,
  failure_status TEXT,
  reason TEXT,
  exact_file TEXT
);

CREATE TABLE proof_boundary_check (
  check_ref TEXT,
  proof_run_id TEXT,
  status TEXT,
  expected TEXT,
  actual TEXT,
  detail TEXT
);

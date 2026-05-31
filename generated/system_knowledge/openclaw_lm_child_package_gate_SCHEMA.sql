CREATE TABLE lm_package (
  package_ref TEXT PRIMARY KEY,
  parent_package_ref TEXT NOT NULL,
  mission TEXT NOT NULL,
  model_class TEXT NOT NULL,
  budget_limit INTEGER NOT NULL CHECK(budget_limit >= 0),
  allowed_files TEXT NOT NULL,
  forbidden_files TEXT NOT NULL,
  allowed_commands TEXT NOT NULL,
  forbidden_actions TEXT NOT NULL,
  required_tests TEXT NOT NULL,
  expected_outputs TEXT NOT NULL,
  authority_profile_ref TEXT NOT NULL,
  guardian_required INTEGER NOT NULL CHECK(guardian_required IN (0, 1)),
  live_action_authority INTEGER NOT NULL DEFAULT 0 CHECK(live_action_authority IN (0, 1)),
  status TEXT NOT NULL,
  package_depth INTEGER NOT NULL DEFAULT 0 CHECK(package_depth >= 0),
  stop_conditions TEXT NOT NULL,
  child_receipt_required INTEGER NOT NULL DEFAULT 1 CHECK(child_receipt_required IN (0, 1)),
  source_refs TEXT NOT NULL
);

CREATE TABLE child_spawn_policy (
  policy_ref TEXT PRIMARY KEY,
  parent_model_class TEXT NOT NULL,
  child_model_class TEXT NOT NULL,
  spawn_allowed INTEGER NOT NULL DEFAULT 0 CHECK(spawn_allowed IN (0, 1)),
  max_children INTEGER NOT NULL DEFAULT 0 CHECK(max_children >= 0),
  max_depth INTEGER NOT NULL DEFAULT 0 CHECK(max_depth >= 0),
  max_total_budget INTEGER NOT NULL DEFAULT 0 CHECK(max_total_budget >= 0),
  allowed_child_task_types TEXT NOT NULL,
  forbidden_child_task_types TEXT NOT NULL,
  requires_guardian_approval INTEGER NOT NULL CHECK(requires_guardian_approval IN (0, 1)),
  requires_operator_approval INTEGER NOT NULL CHECK(requires_operator_approval IN (0, 1)),
  policy_status TEXT NOT NULL
);

CREATE TABLE child_package_request (
  request_ref TEXT PRIMARY KEY,
  parent_package_ref TEXT NOT NULL,
  proposed_child_package_ref TEXT NOT NULL,
  reason TEXT NOT NULL,
  requested_model_class TEXT NOT NULL,
  requested_budget INTEGER NOT NULL CHECK(requested_budget >= 0),
  requested_files TEXT NOT NULL,
  requested_commands TEXT NOT NULL,
  requested_authority TEXT NOT NULL,
  validation_status TEXT NOT NULL,
  guardian_status TEXT NOT NULL,
  child_task_type TEXT NOT NULL,
  requested_depth INTEGER NOT NULL CHECK(requested_depth >= 0),
  stop_conditions TEXT NOT NULL,
  receipt_required INTEGER NOT NULL CHECK(receipt_required IN (0, 1)),
  validation_reasons TEXT NOT NULL
);

CREATE TABLE package_receipt (
  receipt_ref TEXT PRIMARY KEY,
  package_ref TEXT NOT NULL,
  worker_ref TEXT NOT NULL,
  result_status TEXT NOT NULL,
  files_changed TEXT NOT NULL,
  tests_run TEXT NOT NULL,
  boundary_check TEXT NOT NULL,
  child_packages_spawned TEXT NOT NULL,
  budget_used INTEGER NOT NULL CHECK(budget_used >= 0),
  proof_refs TEXT NOT NULL
);

CREATE TABLE package_gate_decision (
  decision_ref TEXT PRIMARY KEY,
  package_ref TEXT NOT NULL,
  decision TEXT NOT NULL CHECK(decision IN ('ALLOW', 'BLOCK', 'REQUIRE_GUARDIAN', 'REQUIRE_OPERATOR', 'BUDGET_EXCEEDED', 'AUTHORITY_DENIED')),
  reason TEXT NOT NULL,
  source_refs TEXT NOT NULL,
  request_ref TEXT NOT NULL
);

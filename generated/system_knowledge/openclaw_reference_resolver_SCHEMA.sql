CREATE TABLE reference_target (
    target_ref TEXT PRIMARY KEY,
    target_type TEXT NOT NULL CHECK(target_type IN ('GIT_BRANCH', 'READ_MODEL_MIRROR', 'WORKFLOW_RECEIPT', 'ARTIFACT', 'SERVICE', 'FILE_PATH', 'UNKNOWN')),
    repo_ref TEXT NOT NULL,
    local_path TEXT NOT NULL,
    remote_url TEXT NOT NULL,
    branch TEXT NOT NULL,
    source_path TEXT NOT NULL,
    bridge_path TEXT NOT NULL,
    receipt_type TEXT NOT NULL,
    artifact_ref TEXT NOT NULL,
    canonical_input_json TEXT NOT NULL,
    refresh_policy TEXT NOT NULL,
    owner_component TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE reference_resolution (
    resolution_ref TEXT PRIMARY KEY,
    target_ref TEXT NOT NULL REFERENCES reference_target(target_ref),
    resolved_status TEXT NOT NULL CHECK(resolved_status IN ('RESOLVED', 'UNREACHABLE', 'DIRTY', 'DRIFT', 'MISSING', 'UNKNOWN')),
    resolved_value TEXT NOT NULL,
    resolved_json TEXT NOT NULL,
    dirty_status TEXT NOT NULL,
    error_message TEXT NOT NULL,
    resolved_at TEXT NOT NULL
);

CREATE TABLE reference_dependency (
    dependency_ref TEXT PRIMARY KEY,
    target_ref TEXT NOT NULL REFERENCES reference_target(target_ref),
    consumer_component TEXT NOT NULL,
    generated_model_path TEXT NOT NULL,
    reason TEXT NOT NULL
);

CREATE TABLE drift_event (
    drift_ref TEXT PRIMARY KEY,
    target_ref TEXT NOT NULL REFERENCES reference_target(target_ref),
    drift_type TEXT NOT NULL,
    expected_value TEXT NOT NULL,
    actual_value TEXT NOT NULL,
    severity TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    operator_summary TEXT NOT NULL
);

CREATE TABLE resolution_run (
    run_ref TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    targets_checked INTEGER NOT NULL,
    drift_count INTEGER NOT NULL,
    status TEXT NOT NULL
);

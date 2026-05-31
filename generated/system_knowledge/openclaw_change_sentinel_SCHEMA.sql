CREATE TABLE sentinel_run (
    run_ref TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    run_status TEXT NOT NULL CHECK(run_status IN ('NO_MATERIAL_CHANGE', 'MATERIAL_CHANGE_DETECTED', 'DRIFT_DETECTED', 'BRIDGE_STALE', 'SERVICE_UNSTABLE', 'REPO_DIRTY', 'REMOTE_REF_MOVED', 'WORKFLOW_STATE_CHANGED', 'BUSINESS_OBJECT_AUDIT_STALE', 'ACTION_REQUIRED', 'UNKNOWN')),
    baseline_available INTEGER NOT NULL CHECK(baseline_available IN (0, 1)),
    observed_target_count INTEGER NOT NULL,
    observed_change_count INTEGER NOT NULL,
    material_change_count INTEGER NOT NULL,
    lm_called INTEGER NOT NULL CHECK(lm_called IN (0, 1)),
    timer_installed INTEGER NOT NULL CHECK(timer_installed IN (0, 1)),
    chief_launched INTEGER NOT NULL CHECK(chief_launched IN (0, 1))
);

CREATE TABLE observed_target (
    target_ref TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,
    source_path TEXT NOT NULL,
    observation_status TEXT NOT NULL CHECK(observation_status IN ('NO_MATERIAL_CHANGE', 'MATERIAL_CHANGE_DETECTED', 'DRIFT_DETECTED', 'BRIDGE_STALE', 'SERVICE_UNSTABLE', 'REPO_DIRTY', 'REMOTE_REF_MOVED', 'WORKFLOW_STATE_CHANGED', 'BUSINESS_OBJECT_AUDIT_STALE', 'ACTION_REQUIRED', 'UNKNOWN')),
    observed_value TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    observed_json TEXT NOT NULL,
    unreachable_reason TEXT NOT NULL,
    observed_at TEXT NOT NULL
);

CREATE TABLE observed_change (
    change_ref TEXT PRIMARY KEY,
    target_ref TEXT NOT NULL REFERENCES observed_target(target_ref),
    change_status TEXT NOT NULL CHECK(change_status IN ('NO_MATERIAL_CHANGE', 'MATERIAL_CHANGE_DETECTED', 'DRIFT_DETECTED', 'BRIDGE_STALE', 'SERVICE_UNSTABLE', 'REPO_DIRTY', 'REMOTE_REF_MOVED', 'WORKFLOW_STATE_CHANGED', 'BUSINESS_OBJECT_AUDIT_STALE', 'ACTION_REQUIRED', 'UNKNOWN')),
    before_value TEXT NOT NULL,
    after_value TEXT NOT NULL,
    before_fingerprint TEXT NOT NULL,
    after_fingerprint TEXT NOT NULL,
    reason TEXT NOT NULL,
    detected_at TEXT NOT NULL
);

CREATE TABLE material_change (
    material_ref TEXT PRIMARY KEY,
    change_ref TEXT NOT NULL REFERENCES observed_change(change_ref),
    material_status TEXT NOT NULL CHECK(material_status IN ('NO_MATERIAL_CHANGE', 'MATERIAL_CHANGE_DETECTED', 'DRIFT_DETECTED', 'BRIDGE_STALE', 'SERVICE_UNSTABLE', 'REPO_DIRTY', 'REMOTE_REF_MOVED', 'WORKFLOW_STATE_CHANGED', 'BUSINESS_OBJECT_AUDIT_STALE', 'ACTION_REQUIRED', 'UNKNOWN')),
    severity TEXT NOT NULL,
    operator_summary TEXT NOT NULL,
    action_required INTEGER NOT NULL CHECK(action_required IN (0, 1)),
    can_wait INTEGER NOT NULL CHECK(can_wait IN (0, 1))
);

CREATE TABLE recommended_action (
    action_ref TEXT PRIMARY KEY,
    material_ref TEXT NOT NULL REFERENCES material_change(material_ref),
    action_title TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('NO_MATERIAL_CHANGE', 'MATERIAL_CHANGE_DETECTED', 'DRIFT_DETECTED', 'BRIDGE_STALE', 'SERVICE_UNSTABLE', 'REPO_DIRTY', 'REMOTE_REF_MOVED', 'WORKFLOW_STATE_CHANGED', 'BUSINESS_OBJECT_AUDIT_STALE', 'ACTION_REQUIRED', 'UNKNOWN')),
    reason TEXT NOT NULL,
    can_wait INTEGER NOT NULL CHECK(can_wait IN (0, 1)),
    validation_command TEXT NOT NULL,
    forbidden_actions_json TEXT NOT NULL
);

CREATE TABLE chief_queue_candidate (
    candidate_ref TEXT PRIMARY KEY,
    material_ref TEXT NOT NULL REFERENCES material_change(material_ref),
    task_title TEXT NOT NULL,
    reason TEXT NOT NULL,
    target_repo TEXT NOT NULL,
    recommended_model TEXT NOT NULL,
    urgency TEXT NOT NULL,
    validation_command TEXT NOT NULL,
    forbidden_actions_json TEXT NOT NULL,
    launch_chief INTEGER NOT NULL CHECK(launch_chief IN (0, 1))
);

CREATE TABLE hermes_summary (
    summary_ref TEXT PRIMARY KEY,
    run_ref TEXT NOT NULL REFERENCES sentinel_run(run_ref),
    what_changed TEXT NOT NULL,
    why_it_matters TEXT NOT NULL,
    what_to_do_next TEXT NOT NULL,
    action_required INTEGER NOT NULL CHECK(action_required IN (0, 1)),
    can_wait INTEGER NOT NULL CHECK(can_wait IN (0, 1)),
    lm_summary_candidate_json TEXT NOT NULL
);

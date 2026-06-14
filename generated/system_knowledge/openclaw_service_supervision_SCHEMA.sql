CREATE TABLE supervision_run (
    run_ref TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    startup_readiness TEXT NOT NULL,
    boot_persistence_state TEXT NOT NULL,
    boot_persistence_reason TEXT NOT NULL,
    linger_status TEXT NOT NULL,
    supervised_unit_count INTEGER NOT NULL,
    ready_unit_count INTEGER NOT NULL,
    risk_count INTEGER NOT NULL
);

CREATE TABLE supervised_unit (
    unit_name TEXT PRIMARY KEY,
    unit_kind TEXT NOT NULL,
    unit_path TEXT NOT NULL,
    enabled INTEGER NOT NULL CHECK(enabled IN (0, 1)),
    active INTEGER NOT NULL CHECK(active IN (0, 1)),
    active_state TEXT NOT NULL,
    sub_state TEXT NOT NULL,
    last_start_time TEXT NOT NULL,
    restart_count TEXT NOT NULL,
    expected_behavior TEXT NOT NULL,
    startup_readiness TEXT NOT NULL,
    reboot_persistence_status TEXT NOT NULL,
    latest_log_excerpt_summary TEXT NOT NULL,
    allowed_supervision_action TEXT NOT NULL,
    recommended_operator_action TEXT NOT NULL,
    observed_json TEXT NOT NULL
);

CREATE TABLE supervision_risk (
    risk_ref TEXT PRIMARY KEY,
    unit_name TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    operator_summary TEXT NOT NULL,
    detected_at TEXT NOT NULL
);

CREATE TABLE recommended_operator_action (
    action_ref TEXT PRIMARY KEY,
    unit_name TEXT NOT NULL,
    action_title TEXT NOT NULL,
    reason TEXT NOT NULL,
    recommended_command TEXT NOT NULL,
    allowed_supervision_action TEXT NOT NULL,
    forbidden_actions_json TEXT NOT NULL
);

CREATE TABLE keeper_status (
    status_ref TEXT PRIMARY KEY,
    status_path TEXT NOT NULL,
    last_action_status TEXT NOT NULL,
    action_count INTEGER NOT NULL,
    status TEXT NOT NULL,
    observed_json TEXT NOT NULL
);

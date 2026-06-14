CREATE TABLE audit_run (
    run_ref TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    freshness_status TEXT NOT NULL CHECK(freshness_status IN ('FRESH', 'STALE_INPUT_CHANGED', 'STALE_TTL_EXPIRED', 'STALE_MISSING_INPUT', 'STALE_DEPENDENCY_DRIFT', 'UNKNOWN')),
    fresh_for_minutes INTEGER NOT NULL,
    readiness TEXT NOT NULL,
    overall_score REAL NOT NULL,
    business_object_count INTEGER NOT NULL,
    gap_count INTEGER NOT NULL,
    missing_eval_count INTEGER NOT NULL,
    stale_reasons_json TEXT NOT NULL
);

CREATE TABLE audit_input (
    input_ref TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    required INTEGER NOT NULL CHECK(required IN (0, 1)),
    status TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    source_ref TEXT NOT NULL
);

CREATE TABLE audit_category_score (
    category TEXT PRIMARY KEY,
    score REAL NOT NULL,
    max_score REAL NOT NULL,
    confidence TEXT NOT NULL,
    status TEXT NOT NULL,
    strongest_evidence TEXT NOT NULL,
    biggest_gap TEXT NOT NULL,
    fastest_improvement TEXT NOT NULL,
    rationale TEXT NOT NULL,
    source_refs_json TEXT NOT NULL,
    freshness_notes TEXT NOT NULL
);

CREATE TABLE business_object_inventory (
    object_name TEXT PRIMARY KEY,
    implementation_status TEXT NOT NULL,
    business_object_proximity TEXT NOT NULL,
    current_fact TEXT NOT NULL,
    blockers_json TEXT NOT NULL,
    next_safe_action TEXT NOT NULL,
    source_refs_json TEXT NOT NULL
);

CREATE TABLE audit_gap (
    rank INTEGER PRIMARY KEY,
    gap_ref TEXT NOT NULL,
    gap TEXT NOT NULL,
    severity TEXT NOT NULL,
    owner_hint TEXT NOT NULL,
    build_bucket TEXT NOT NULL
);

CREATE TABLE audit_recommended_action (
    action_ref TEXT PRIMARY KEY,
    bucket TEXT NOT NULL,
    rank INTEGER NOT NULL,
    task TEXT NOT NULL,
    reason TEXT NOT NULL
);

CREATE TABLE audit_freshness_signal (
    signal_ref TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK(status IN ('FRESH', 'STALE_INPUT_CHANGED', 'STALE_TTL_EXPIRED', 'STALE_MISSING_INPUT', 'STALE_DEPENDENCY_DRIFT', 'UNKNOWN')),
    input_ref TEXT NOT NULL,
    reason TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    observed_at TEXT NOT NULL
);

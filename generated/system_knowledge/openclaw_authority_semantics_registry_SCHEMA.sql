CREATE TABLE authority_field_semantics (
    field_ref TEXT PRIMARY KEY,
    field_name TEXT NOT NULL,
    field_family TEXT NOT NULL,
    true_meaning TEXT NOT NULL,
    false_meaning TEXT NOT NULL,
    allowed_locations TEXT NOT NULL,
    forbidden_locations TEXT NOT NULL,
    required_for_event_bridge INTEGER NOT NULL CHECK(required_for_event_bridge IN (0, 1)),
    required_for_finance INTEGER NOT NULL CHECK(required_for_finance IN (0, 1)),
    default_value TEXT NOT NULL,
    risk_if_wrong TEXT NOT NULL,
    operator_copy TEXT NOT NULL,
    developer_copy TEXT NOT NULL,
    positive_replacement_field TEXT NOT NULL,
    golden_path_example_ref TEXT NOT NULL
);

CREATE TABLE authority_profile (
    profile_ref TEXT PRIMARY KEY,
    profile_name TEXT NOT NULL,
    applies_to TEXT NOT NULL,
    purpose TEXT NOT NULL,
    required_fields TEXT NOT NULL,
    forbidden_fields TEXT NOT NULL,
    default_deny INTEGER NOT NULL CHECK(default_deny IN (0, 1)),
    receipts_required TEXT NOT NULL,
    dangerous_authorities TEXT NOT NULL,
    allowed_actions TEXT NOT NULL,
    blocked_actions TEXT NOT NULL,
    positive_structure_refs TEXT NOT NULL,
    golden_path_template_ref TEXT NOT NULL
);

CREATE TABLE authority_validation_rule (
    rule_ref TEXT PRIMARY KEY,
    profile_ref TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    field_name TEXT NOT NULL,
    expected_value TEXT NOT NULL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL,
    growth_stage TEXT NOT NULL,
    remediation TEXT NOT NULL,
    positive_replacement TEXT NOT NULL,
    golden_path_template_ref TEXT NOT NULL
);

CREATE TABLE device_authority_shard (
    device_ref TEXT PRIMARY KEY,
    device_name TEXT NOT NULL,
    device_class TEXT NOT NULL,
    repo_ref TEXT NOT NULL,
    local_path TEXT NOT NULL,
    authority_profiles TEXT NOT NULL,
    known_limitations TEXT NOT NULL,
    positive_structures_required TEXT NOT NULL,
    last_seen_status TEXT NOT NULL,
    source_refs TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE authority_drift_signal (
    drift_ref TEXT PRIMARY KEY,
    detected_at TEXT NOT NULL,
    field_name TEXT NOT NULL,
    component_ref TEXT NOT NULL,
    profile_ref TEXT NOT NULL,
    drift_type TEXT NOT NULL,
    growth_stage TEXT NOT NULL,
    severity TEXT NOT NULL,
    operator_summary TEXT NOT NULL,
    developer_summary TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    positive_replacement TEXT NOT NULL,
    source_ref TEXT NOT NULL
);

CREATE TABLE authority_remediation_policy (
    policy_ref TEXT PRIMARY KEY,
    drift_type TEXT NOT NULL,
    growth_stage TEXT NOT NULL,
    severity TEXT NOT NULL,
    default_response TEXT NOT NULL,
    auto_fix_allowed INTEGER NOT NULL CHECK(auto_fix_allowed IN (0, 1)),
    auto_remove_allowed INTEGER NOT NULL CHECK(auto_remove_allowed IN (0, 1)),
    quarantine_allowed INTEGER NOT NULL CHECK(quarantine_allowed IN (0, 1)),
    positive_occupation_required INTEGER NOT NULL CHECK(positive_occupation_required IN (0, 1)),
    requires_receipt INTEGER NOT NULL CHECK(requires_receipt IN (0, 1)),
    requires_guardian_review INTEGER NOT NULL CHECK(requires_guardian_review IN (0, 1)),
    requires_operator_approval INTEGER NOT NULL CHECK(requires_operator_approval IN (0, 1)),
    safe_remediation_path TEXT NOT NULL,
    forbidden_remediation TEXT NOT NULL
);

CREATE TABLE positive_occupation_template (
    template_ref TEXT PRIMARY KEY,
    template_name TEXT NOT NULL,
    applies_to TEXT NOT NULL,
    purpose TEXT NOT NULL,
    replaces_bad_pattern TEXT NOT NULL,
    required_fields TEXT NOT NULL,
    forbidden_fields TEXT NOT NULL,
    example_payload TEXT NOT NULL,
    validation_profile_ref TEXT NOT NULL,
    owner_component TEXT NOT NULL,
    generated_fixture_path TEXT NOT NULL,
    operator_summary TEXT NOT NULL,
    developer_summary TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE golden_path_fixture (
    fixture_ref TEXT PRIMARY KEY,
    template_ref TEXT NOT NULL,
    fixture_name TEXT NOT NULL,
    fixture_kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    expected_validation_status TEXT NOT NULL,
    expected_route TEXT NOT NULL,
    forbidden_side_effects TEXT NOT NULL,
    source_ref TEXT NOT NULL
);

from launch_ladder_contract_check import (
    ACTIVE_SOURCE_SET,
    MISSION_CONTROL_APP_SURFACE,
    MISSION_CONTROL_SOURCE_SET_BASELINE,
    REQUIRED_MISSION_CONTROL_FIXTURES,
    UPLOAD_AUTHORITY_COMMIT,
    check_contract,
    freshness_warnings,
    load_corpus,
    load_mission_control_fixtures,
    mission_control_fixture_failures,
)


def test_launch_ladder_static_contract_is_present():
    report = check_contract()
    assert report.failures == ()


def test_active_app_planning_source_set_warnings_are_preserved():
    corpus = load_corpus()
    warnings = freshness_warnings(corpus)
    joined = "\n".join(warnings)

    assert ACTIVE_SOURCE_SET in joined
    assert UPLOAD_AUTHORITY_COMMIT in joined
    assert "generated MANIFEST.md" in joined
    assert "upload authority" in joined
    assert "package-level freshness markers" in joined
    assert "Freshness normalization TODO" in joined


def test_source_set_ladder_delta_bridge_contract_is_present():
    corpus = load_corpus()
    launch_text = corpus.launch_ladder_text.lower()

    assert "CHAT_STAY_UP_TO_DATE.md" in corpus.launch_ladder_text
    assert "Source-Set Ladder" in corpus.launch_ladder_text
    assert UPLOAD_AUTHORITY_COMMIT in corpus.launch_ladder_text
    assert "source-set folders are not launch ladder steps" in launch_text
    assert "openclaw_audit_build_readiness" in corpus.launch_ladder_text
    assert "law_program" in corpus.launch_ladder_text
    assert "DELTA_BRIDGE_NAME" in corpus.script_text
    assert "counted_in_24=false" in corpus.script_text


def test_workspace_launch_profiles_and_prototype_bridge_retirement_are_documented():
    corpus = load_corpus()
    launch_text = corpus.launch_ladder_text

    assert "Workspace Launch Profile" in launch_text
    assert "named, evidence-backed view/navigation route" in launch_text
    assert "Opening VS Code/workspace/files is safe navigation" in launch_text
    assert "Any execution must be a separate Launch Packet / Launch Ladder action" in launch_text

    for field in (
        "profile_id",
        "display_name",
        "purpose",
        "owner_lane",
        "domain",
        "target_machine",
        "context",
        "target_root",
        "path",
        "workspace_file",
        "workspace_hint",
        "recommended_files",
        "tabs",
        "optional_prompt_path",
        "prompt_hint",
        "evidence_sources",
        "freshness_fields",
        "allowed_navigation_actions",
        "explicitly_forbidden_execution_actions",
        "required_next_launch_packet_for_execution",
    ):
        assert field in launch_text

    assert "pc_wsl_repo_view" in launch_text
    assert "mac_upload_prep_view" in launch_text
    assert "mac_desktop_app_planning_view" in launch_text
    assert "legal_visual_polish_view" in launch_text
    assert "audit_runtime_review_view" in launch_text
    assert "hermes_advisory_packet_view" in launch_text
    assert "run_tests" in launch_text
    assert "provider_or_model_calls" in launch_text
    assert "installed_unit_checks" in launch_text
    assert (
        "/Users/hwinshipwheatley/OpenClaw_Watch/.claude/Chat_Stay Up To Date.md"
        in launch_text
    )
    assert "prototype/example only" in launch_text
    assert "not canonical" in launch_text
    assert "explicit Mac cleanup step" in launch_text


def test_workspace_launch_profile_to_launch_packet_handoff_is_documented():
    corpus = load_corpus()
    launch_text = corpus.launch_ladder_text

    assert "Workspace Profile To Launch Packet Handoff" in launch_text
    assert "profile-to-packet handoff is explicit and one-way" in launch_text
    assert "The Workspace Launch Profile opens context only" in launch_text
    assert "The profile may point to `required_next_launch_packet_for_execution`" in launch_text
    assert "The Launch Packet authorizes a bounded next action" in launch_text
    assert "operator-readable scope" in launch_text
    assert "evidence/freshness" in launch_text
    assert "Workspace Launch Profile must not contain executable commands" in launch_text
    assert "silently authorize them" in launch_text

    for field in (
        "handoff_reason",
        "handoff_evidence_sources",
        "handoff_freshness_fields",
        "handoff_operator_readable_scope",
        "packet_id",
        "source_profile_id",
        "bounded_next_action",
        "target_machine",
        "target_workspace",
        "operator_readable_scope",
        "execution_commands",
        "validation_commands",
        "withheld_surfaces",
        "approval_receipt_or_operator_decision",
    ):
        assert field in launch_text

    assert "operator_harness_refresh_packet" in launch_text
    assert "A Workspace Launch Profile with executable commands is invalid" in launch_text
    assert "commands belong in a Launch Packet" in launch_text
    assert "launcher action" in launch_text
    assert "higher Launch Ladder action" in launch_text


def test_action_authorization_approval_receipt_contract_is_documented():
    corpus = load_corpus()
    launch_text = corpus.launch_ladder_text

    assert "Action Authorization / Approval Receipt" in launch_text
    assert "Launch Packet exists does not equal approved" in launch_text
    assert "Approval Receipt records explicit operator authorization" in launch_text
    assert "Approval Receipt binds to one Launch Packet/action/scope" in launch_text
    assert "visible evidence/freshness state at approval time" in launch_text
    assert "expired receipts cannot authorize new execution" in launch_text
    assert "single-use receipts cannot be replayed after consumption" in launch_text
    for lifecycle_state in (
        "permitted",
        "executed",
        "succeeded",
        "failed",
        "expired",
        "revoked",
    ):
        assert lifecycle_state in launch_text
    assert "must not broaden the Launch Packet scope" in launch_text

    for field in (
        "receipt_id",
        "launch_packet_id",
        "approved_by_operator",
        "approved_at",
        "approved_scope",
        "evidence_snapshot",
        "freshness_snapshot",
        "expiry",
        "replay_policy",
        "consumed_state",
        "execution_result_reference",
        "revocation_state",
        "forbidden_scope_expansion",
    ):
        assert field in launch_text

    for fixture in (
        "receipt_docs_test_2026_05_02_001",
        "receipt_docs_test_expired",
        "receipt_docs_test_consumed",
        "receipt_docs_test_revoked",
        "invalid_broadened_receipt",
    ):
        assert fixture in launch_text

    assert "Approval Receipt cannot broaden the Launch Packet scope" in launch_text


def test_ui_state_claim_rules_are_documented():
    corpus = load_corpus()
    launch_text = corpus.launch_ladder_text

    assert "UI State Claim Rules" in launch_text
    assert '"Profile available" does not mean "packet available."' in launch_text
    assert '"Packet available" does not mean "approved."' in launch_text
    assert '"Approved" does not mean "executed."' in launch_text
    assert '"Executed" does not mean "succeeded."' in launch_text
    assert '"Current/fresh" requires evidence/freshness proof' in launch_text
    assert '"Synced/tested/healthy/running" cannot be shown unless backed by explicit evidence' in launch_text
    assert "configured vs observed" in launch_text
    assert "requested vs approved" in launch_text
    assert "approved vs executed" in launch_text
    assert "executed vs succeeded" in launch_text
    assert "current vs stale" in launch_text
    assert "Convenience must not collapse navigation, approval, and execution into one hidden action" in launch_text
    assert "Opening a Workspace Launch Profile must not auto-approve, auto-run, or auto-consume a Launch Packet" in launch_text
    assert "invalid_tests_passed_without_evidence" in launch_text
    assert "UI state claim says tests passed without evidence" in launch_text
    assert "invalid_profile_open_auto_approves_and_runs" in launch_text
    assert "Opening a Workspace Launch Profile silently approves/runs a packet" in launch_text


def test_product_taste_operator_experience_eval_spine_is_documented():
    corpus = load_corpus()
    launch_text = corpus.launch_ladder_text

    assert "Product Taste / Operator Experience Eval Spine" in launch_text
    assert "Taste is not decorative polish" in launch_text
    assert "operator trust, calm control, clear authority hierarchy" in launch_text
    assert "legible evidence, sparse high-confidence actions, and zero fake intelligence" in launch_text
    assert "operator can orient within a few seconds" in launch_text
    assert "authority boundaries are visually obvious" in launch_text
    assert "highest-risk actions cannot be confused with navigation" in launch_text
    assert "status copy is exact and evidence-backed" in launch_text
    assert "calm, sparse, premium, and controlled" in launch_text
    assert "fake-futuristic AI slop" in launch_text
    assert "generic SaaS admin dashboard" in launch_text
    assert "vague chatbot panels" in launch_text

    for failure in (
        "Visual clutter",
        "Vague agent status",
        "Fake intelligence language",
        "Scary controls with unclear blast radius",
        "Hidden authority or hidden execution",
        "Dead generic admin-panel energy",
        "Unclear state hierarchy",
        "Chatbot slop",
        "Over-automation",
        "Evidence buried too deeply",
    ):
        assert failure in launch_text

    for category in (
        "Copy/state-language checks",
        "Cockpit/instrument hierarchy checks",
        "Action safety visibility checks",
        "Density/calmness checks",
        "Evidence visibility checks",
        "Operator trust checks",
        "Anti-slop checks",
        "Accessibility/legibility checks",
    ):
        assert category in launch_text

    for golden in (
        "golden_calm_mission_control_overview",
        "golden_navigation_only_workspace_card",
        "golden_bounded_packet_card",
        "golden_approval_receipt_card",
        "golden_stale_evidence_warning",
        "golden_blocked_action_with_clear_reason",
        "golden_ready_but_not_approved_action",
        "golden_fresh_evidence_backed_status",
    ):
        assert golden in launch_text

    for malformed in (
        "invalid_chatbot_i_handled_it_state",
        "invalid_glowing_ai_brain_panel",
        "invalid_one_click_hides_approval",
        "invalid_tests_passed_without_evidence",
        "invalid_healthy_running_without_observation",
        "invalid_dense_admin_table_no_next_action",
        "invalid_profile_card_matches_execution_action",
        "invalid_fake_urgency_or_confidence",
    ):
        assert malformed in launch_text

    assert "app planning source set must preserve this eval spine before implementation" in launch_text
    assert "Do not start app implementation" in launch_text


def test_workspace_launch_profile_source_set_and_apple_platform_posture_are_documented():
    corpus = load_corpus()
    launch_text = corpus.launch_ladder_text

    assert "active app-planning posture is `02_MAC_IOS_APP_BUILD`" in launch_text
    assert "read-only Mac desktop Mission Control fixture contract stays in `02_MAC_IOS_APP_BUILD`" in launch_text
    assert "does not move the active ChatGPT Project source-set posture to `03_BACKEND_AND_DATA_MODEL`" in launch_text
    assert "does not create source-set folder `04`" in launch_text
    assert "does not create generated source-set scripts" in launch_text
    assert "does not edit generated source-set folders" in launch_text
    assert "does not start app/backend/runtime implementation" in launch_text
    assert "`Mac/iOS` is Apple-platform planning shorthand" in launch_text
    assert "Mac desktop app first, iOS companion later" in launch_text
    assert "Do not read this brief as iOS-first implementation" in launch_text


def test_mac_desktop_mission_control_fixture_contract_is_documented():
    corpus = load_corpus()
    launch_text = corpus.launch_ladder_text

    assert "Mac Desktop Mission Control Fixture Contract" in launch_text
    assert "docs/planning/launch_ladder/fixtures/mission_control/" in launch_text
    for fixture_name in REQUIRED_MISSION_CONTROL_FIXTURES:
        assert fixture_name in launch_text

    for state_rule in (
        "`profile_available`: navigation context exists only",
        "`packet_available`: bounded action object exists for review only",
        "`launch_ready`: preconditions appear satisfied for operator review only",
        "`approved`: Approval Receipt permits one named packet/action/scope only",
        "`executed`: attempted, not necessarily successful",
        "`succeeded`: execution result plus validation evidence",
        "`stale`: source basis, timestamp, evidence, or freshness is no longer valid",
        "`blocked`: authority, evidence, freshness, validation, or scope is missing or invalid",
        "`unknown`: app lacks evidence; do not soften this into confidence",
    ):
        assert state_rule in launch_text

    assert "must not collapse profile, packet, approval, execution, and result" in launch_text
    assert "Product Taste / Operator Experience Evals must reject AI slop" in launch_text
    assert "All nine required fixture files exist and parse as JSON" in launch_text
    assert "Workspace Launch Profiles with executable command fields are invalid" in launch_text
    assert "Expired receipts cannot authorize execution" in launch_text
    assert "`healthy`, `current`, `tested`, `running`, or `synced` without evidence are invalid" in launch_text


def test_mac_desktop_mission_control_fixtures_validate_static_boundaries():
    failures = mission_control_fixture_failures()
    assert failures == ()

    fixtures = load_mission_control_fixtures()
    assert set(fixtures) == set(REQUIRED_MISSION_CONTROL_FIXTURES)

    for fixture in fixtures.values():
        assert fixture["app_surface"] == MISSION_CONTROL_APP_SURFACE
        assert fixture["source_set_baseline"] == MISSION_CONTROL_SOURCE_SET_BASELINE
        assert fixture["source_manifest_commit"] == UPLOAD_AUTHORITY_COMMIT
        assert fixture["hard_boundaries"]["no_runtime_calls"] is True
        assert fixture["hard_boundaries"]["no_service_control"] is True
        assert fixture["hard_boundaries"]["no_provider_model_calls"] is True
        assert fixture["hard_boundaries"]["no_private_data_vault_log_legalprivate_secrets_inspection"] is True
        assert fixture["hard_boundaries"]["no_approval_mutation_guardian_control"] is True
        assert fixture["hard_boundaries"]["no_app_execution"] is True

    assert fixtures["fixture_fresh_navigation_profile.json"]["expected_validation"]["navigation_only"] is True
    assert fixtures["fixture_fresh_navigation_profile.json"]["expected_validation"]["authorizes_execution"] is False
    assert fixtures["fixture_malformed_executable_profile.json"]["expected_validation"]["fixture_valid"] is False
    assert fixtures["fixture_malformed_executable_profile.json"]["expected_validation"]["contains_executable_commands"] is True
    assert fixtures["fixture_packet_available_not_approved.json"]["expected_validation"]["approval_receipt_present"] is False
    assert fixtures["fixture_packet_available_not_approved.json"]["expected_validation"]["authorizes_execution"] is False
    assert fixtures["fixture_approval_receipt_valid.json"]["expected_validation"]["authorizes_one_named_packet_action_scope"] is True
    assert fixtures["fixture_approval_receipt_valid.json"]["expected_validation"]["app_can_execute"] is False
    assert fixtures["fixture_approval_receipt_expired.json"]["expected_validation"]["expired"] is True
    assert fixtures["fixture_approval_receipt_expired.json"]["expected_validation"]["authorizes_execution"] is False
    assert fixtures["fixture_stale_evidence_route.json"]["expected_validation"]["launch_ready_claim_allowed"] is False
    assert fixtures["fixture_blocked_missing_authority.json"]["expected_validation"]["must_distinguish_launch_ready_from_launch_authorized"] is True
    assert fixtures["fixture_ui_claim_without_evidence.json"]["expected_validation"]["fixture_valid"] is False
    assert fixtures["fixture_ui_claim_without_evidence.json"]["expected_validation"]["must_not_soften_unknown_into_confidence"] is True
    assert fixtures["fixture_operator_experience_golden_overview.json"]["expected_validation"]["must_preserve_taste_eval"] is True

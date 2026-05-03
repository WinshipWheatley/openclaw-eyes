from launch_ladder_contract_check import (
    ACTIVE_SOURCE_SET,
    FIRST_SCREEN_ALLOWED_APP_PHRASES,
    FIRST_SCREEN_EXTRA_HARD_BOUNDARIES,
    FIRST_SCREEN_ZONES,
    KNOWLEDGE_SUBSTRATE_APP_CARDS,
    KNOWLEDGE_SUBSTRATE_FIXTURE_NAMES,
    KNOWLEDGE_SUBSTRATE_SENSITIVITY_LEVELS,
    KNOWLEDGE_SUBSTRATE_TABLES,
    KNOWLEDGE_SUBSTRATE_UI_STATES,
    MISSION_CONTROL_APP_SURFACE,
    MISSION_CONTROL_SOURCE_SET_BASELINE,
    REQUIRED_FIRST_SCREEN_FIXTURES,
    REQUIRED_MISSION_CONTROL_FIXTURES,
    REQUIRED_KNOWLEDGE_SUBSTRATE_DOCS,
    SOUND_ANTI_VIBE_TESTS,
    SOUND_REQUIRED_SECTIONS,
    SOUND_VIBE_TESTS,
    TASTE_ANTI_VIBE_TESTS,
    TASTE_REQUIRED_SECTIONS,
    TASTE_VIBE_TESTS,
    UPLOAD_AUTHORITY_COMMIT,
    check_contract,
    first_screen_composition_failures,
    freshness_warnings,
    knowledge_substrate_package_failures,
    load_corpus,
    load_first_screen_fixtures,
    load_mission_control_fixtures,
    mission_control_fixture_failures,
    taste_and_quiet_feedback_failures,
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


def test_knowledge_substrate_planning_package_is_documented():
    failures = knowledge_substrate_package_failures()
    assert failures == ()

    corpus = load_corpus()
    knowledge_text = corpus.knowledge_substrate_text

    for filename in REQUIRED_KNOWLEDGE_SUBSTRATE_DOCS:
        assert filename in knowledge_text or filename == "README.md"

    assert "Compiled Knowledge Substrate" in knowledge_text
    assert "SQLite stores the memory; markdown speaks it; HTML preserves shape; FTS finds it; compiled notes make it useful" in knowledge_text
    assert "not vanilla RAG" in knowledge_text
    assert "not classic flat chunk-vector RAG" in knowledge_text
    assert "Karpathy-style LLM Wiki thinking" in knowledge_text
    assert "retrieval finds candidates" in knowledge_text
    assert "compilation creates durable inspectable knowledge" in knowledge_text
    assert "SQLite should be treated as the canonical local memory substrate" in knowledge_text
    assert "Markdown is an export and handoff surface" in knowledge_text
    assert "HTML/rich fragments preserve source shape" in knowledge_text or "HTML or rich fragments preserve source shape" in knowledge_text
    assert "FTS5/search finds relevant records quickly" in knowledge_text
    assert "Compiled notes make recurring knowledge useful" in knowledge_text
    assert "Operator promotions determine what is accepted, rejected, marked historical, marked sensitive, or excluded" in knowledge_text
    assert "Raw files are evidence, not truth" in knowledge_text
    assert "Extracted text is parsed evidence, not truth" in knowledge_text
    assert "Compiled notes are interpretation, not truth" in knowledge_text
    assert "Claims are evidence-backed and confidence-bounded, not truth by default" in knowledge_text
    assert "Unknown means unknown" in knowledge_text

    for table_name in KNOWLEDGE_SUBSTRATE_TABLES:
        assert table_name in knowledge_text

    for safety_level in KNOWLEDGE_SUBSTRATE_SENSITIVITY_LEVELS:
        assert safety_level in knowledge_text

    for card_name in KNOWLEDGE_SUBSTRATE_APP_CARDS:
        assert card_name in knowledge_text

    for ui_state in KNOWLEDGE_SUBSTRATE_UI_STATES:
        assert ui_state in knowledge_text

    for fixture_name in KNOWLEDGE_SUBSTRATE_FIXTURE_NAMES:
        assert fixture_name in knowledge_text

    assert "This package is app-planning only and does not authorize ingestion" in knowledge_text
    assert "Fixtures are synthetic only" in knowledge_text
    assert "Do not ingest real files" in knowledge_text
    assert "Do not scan user directories" in knowledge_text
    assert "No external model access to raw/extracted sensitive content unless sanitized through a future explicit approval path" in knowledge_text
    assert "Secrets/credentials must never be summarized into prompts" in knowledge_text
    assert "no language collapses raw/extracted/compiled/promoted into one truth state" in knowledge_text
    assert "no private/vault/legal/business files are inspected" in knowledge_text


def test_first_screen_composition_spec_is_documented():
    failures = first_screen_composition_failures()
    assert failures == ()

    corpus = load_corpus()
    launch_text = corpus.launch_ladder_text
    launch_lower = launch_text.lower()

    assert "Mac Desktop First Screen Composition Spec" in launch_text
    assert "first-screen layout thesis" in launch_lower
    assert "top operating context band" in launch_lower
    assert "left active lanes column" in launch_lower
    assert "center current focus / selected lane" in launch_lower
    assert "right next safe move panel" in launch_lower
    assert "lower evidence/freshness drawer" in launch_lower
    assert "quiet recent changes strip" in launch_lower
    assert "future knowledge/context strip" in launch_lower
    assert "default visible copy for current project state" in launch_lower
    assert "card density and hierarchy rules" in launch_lower
    assert "state color/emphasis guidance" in launch_lower
    assert "what must be tucked away" in launch_lower
    assert "first-screen golden examples" in launch_lower
    assert "first-screen malformed examples" in launch_lower
    assert "boundaries before implementation" in launch_lower

    for phrase in FIRST_SCREEN_ALLOWED_APP_PHRASES:
        assert phrase in launch_text
    assert "Do not name the app" in launch_text
    assert "Do not invent product names" in launch_text

    for card in (
        "Active Lane Card",
        "Next Safe Move Card",
        "Evidence/Freshness Card",
        "Recent Commit / Source-Set Card",
        "Knowledge Context Card",
        "Blocked Without Panic Card",
        "Unknown Without Fake Confidence Card",
    ):
        assert card in launch_text

    for fixture_name in REQUIRED_FIRST_SCREEN_FIXTURES:
        assert fixture_name in launch_text

    assert "Calm cockpit / personal command desk" in launch_text or "calm cockpit / personal command desk" in launch_text
    assert "Evidence-backed, not bureaucratic" in launch_text or "evidence-backed, not bureaucratic" in launch_text
    assert "Personal/operator-specific, not generic SaaS" in launch_text or "personal/operator-specific, not generic SaaS" in launch_text
    assert "Next safe move, not task-manager sprawl" in launch_text or "next safe move, not task-manager sprawl" in launch_text
    assert "Knowledge context, not a RAG search box" in launch_text or "knowledge context, not a RAG search box" in launch_text
    assert "Unknown means unknown" in launch_text
    assert "Blocked means protected boundary, not panic" in launch_text
    assert "Nothing moves just because it is visible" in launch_text
    assert "do not show synced/current until push evidence exists" in launch_text
    assert "No SQLite database" in launch_text
    assert "No ingestion scripts" in launch_text
    assert "No old business-file scanning" in launch_text
    assert "No provider/model calls" in launch_text


def test_first_screen_composition_fixtures_validate_static_boundaries():
    failures = first_screen_composition_failures()
    assert failures == ()

    fixtures = load_first_screen_fixtures()
    assert set(fixtures) == set(REQUIRED_FIRST_SCREEN_FIXTURES)

    for filename, fixture in fixtures.items():
        assert fixture["fixture_id"] == filename.removesuffix(".json")
        assert fixture["fixture_type"] == "first_screen_composition"
        assert fixture["app_surface"] == MISSION_CONTROL_APP_SURFACE
        assert fixture["source_set_baseline"] == MISSION_CONTROL_SOURCE_SET_BASELINE
        assert fixture["source_manifest_commit"] == UPLOAD_AUTHORITY_COMMIT
        assert fixture["expected_validation"]["app_can_execute"] is False
        assert fixture["hard_boundaries"]["no_swiftui_appkit_implementation"] is True
        assert fixture["hard_boundaries"]["no_backend_api_schema_implementation"] is True
        assert fixture["hard_boundaries"]["no_provider_model_calls"] is True
        assert fixture["hard_boundaries"]["no_private_data_vault_log_legalprivate_secrets_inspection"] is True
        assert fixture["hard_boundaries"]["no_app_execution"] is True
        for boundary in FIRST_SCREEN_EXTRA_HARD_BOUNDARIES:
            assert fixture["hard_boundaries"][boundary] is True

        if filename.startswith("golden_"):
            assert fixture["expected_validation"]["fixture_valid"] is True
            assert fixture["expected_validation"]["read_only_app_planning_posture"] is True
            for zone in FIRST_SCREEN_ZONES:
                assert zone in fixture["zones"]

        if filename.startswith("malformed_"):
            assert fixture["expected_validation"]["fixture_valid"] is False
            assert fixture["expected_validation"]["expected_invalid_reason"]

    local_ahead = fixtures["golden_first_screen_local_ahead_of_origin.json"]
    assert local_ahead["source_control_state"]["local_ahead_of_origin"] is True
    assert local_ahead["source_control_state"]["origin_sync_verified"] is False
    assert local_ahead["source_control_state"]["push_evidence_present"] is False
    assert local_ahead["expected_validation"]["must_not_claim_synced_or_current"] is True

    knowledge = fixtures["golden_first_screen_knowledge_context_non_ingestive.json"]
    assert knowledge["knowledge_context"]["future_context_only"] is True
    assert knowledge["knowledge_context"]["knowledge_context_not_rag_search_box"] is True
    assert knowledge["knowledge_context"]["active_ingestion"] is False
    assert knowledge["knowledge_context"]["sqlite_database_exists"] is False
    assert knowledge["knowledge_context"]["business_archive_scanned"] is False
    assert knowledge["knowledge_context"]["business_file_truth_claims"] is False

    unknown = fixtures["golden_first_screen_unknown_preserved.json"]
    assert unknown["expected_validation"]["must_not_soften_unknown_into_confidence"] is True

    ai_command_center = fixtures["malformed_first_screen_ai_command_center.json"]
    assert ai_command_center["expected_validation"]["rejects_chatbot_home"] is True
    assert ai_command_center["expected_validation"]["rejects_ai_command_center"] is True
    assert ai_command_center["expected_validation"]["rejects_business_file_truth_claims"] is True

    profile_executes = fixtures["malformed_first_screen_profile_executes_work.json"]
    assert profile_executes["profile_card"]["on_open_execution"]
    assert profile_executes["expected_validation"]["rejects_profile_execution"] is True
    assert profile_executes["expected_validation"]["requires_separate_launch_packet_for_execution"] is True

    synced_after_failure = fixtures["malformed_first_screen_synced_after_push_failure.json"]
    assert synced_after_failure["source_control_state"]["local_ahead_of_origin"] is True
    assert synced_after_failure["source_control_state"]["push_evidence_present"] is False
    assert synced_after_failure["expected_validation"]["rejects_fake_synced_current_claims"] is True


def test_taste_and_quiet_feedback_specs_are_documented():
    failures = taste_and_quiet_feedback_failures()
    assert failures == ()

    corpus = load_corpus()
    launch_text = corpus.launch_ladder_text
    launch_lower = launch_text.lower()

    assert "Mac Desktop Taste And Atmosphere Spec" in launch_text
    assert "Mac Desktop Sound Haptics Quiet Feedback Addendum" in launch_text

    for section in TASTE_REQUIRED_SECTIONS:
        assert section.lower() in launch_lower
    for section in SOUND_REQUIRED_SECTIONS:
        assert section.lower() in launch_lower

    for vibe_test in TASTE_VIBE_TESTS:
        assert vibe_test in launch_text
    for anti_vibe_test in TASTE_ANTI_VIBE_TESTS:
        assert anti_vibe_test in launch_text
    for vibe_test in SOUND_VIBE_TESTS:
        assert vibe_test in launch_text
    for anti_vibe_test in SOUND_ANTI_VIBE_TESTS:
        assert anti_vibe_test in launch_text

    for phrase in FIRST_SCREEN_ALLOWED_APP_PHRASES:
        assert phrase in launch_text

    assert "Opening the Mac desktop app should feel like sitting down at a trusted personal command surface" in launch_text
    assert "well-built studio console before a session" in launch_text
    assert "Target emotional state: centered operational clarity" in launch_text
    assert "I know where things stand. I know what is safe. I know what is blocked. I know what deserves my attention." in launch_text
    assert "Dominant blend: quiet instrument panel + studio console + evidence drawer + chart table" in launch_text
    assert "Cockpit guides discipline, not decoration" in launch_text
    assert "Studio console is the strongest personal metaphor" in launch_text
    assert "Tactile but not skeuomorphic" in launch_text
    assert "Dimensional but not flashy" in launch_text
    assert "Evidence-backed but not bureaucratic" in launch_text
    assert "Personal but not cute" in launch_text
    assert "Creative but not whimsical slop" in launch_text
    assert "Minimal purposeful motion only" in launch_text
    assert "fake AI thinking animation" in launch_text
    assert "hidden-worker theatre" in launch_text
    assert "Knowledge substrate must not default to RAG search/chat-with-files UX" in launch_text
    assert "Taste comes from structure, not branding" in launch_text
    assert "personal and daily-use-worthy, not merely correct" in launch_text

    assert "Recommended next artifact: combined source-set generation for the app-planning package" in launch_text
    assert "Do not do another broad design pass" in launch_text
    assert "15_MAC_DESKTOP_SOUND_HAPTICS_QUIET_FEEDBACK_ADDENDUM.md" in launch_text
    assert "separate addendum" in launch_text
    assert "This recommendation does not create source-set folders" in launch_text

    assert "Sound should play a minor, disciplined role" in launch_text
    assert "soft relay, settled switch, quiet indication that a visible state transition completed" in launch_text
    assert "Emotional target: settled confidence, not excitement" in launch_text
    assert "Sound should be off by default for v1" in launch_text
    assert "Quiet feedback mode should be opt-in" in launch_text
    assert "Critical information must never be sound-only" in launch_text
    assert "Brand/audio identity is deferred" in launch_text
    assert "separate addendum to `14_MAC_DESKTOP_TASTE_AND_ATMOSPHERE_SPEC.md`" in launch_text

    assert "does not create audio assets" in launch_text
    assert "sound asset folders" in launch_text
    assert "haptic implementation" in launch_text
    assert "notification behavior" in launch_text
    assert "sound settings UI" in launch_text
    assert "Do not generate audio assets" in launch_text
    assert "app/product/brand/codename/mascot/logo/slogan" in launch_text

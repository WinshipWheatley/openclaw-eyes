from launch_ladder_contract_check import (
    OMITTED_CURRENT_PRODUCT_SPEC_FILES,
    UPLOADED_CURRENT_PRODUCT_SPEC,
    UPLOAD_AUTHORITY_COMMIT,
    check_contract,
    freshness_warnings,
    load_corpus,
)


def test_launch_ladder_static_contract_is_present():
    report = check_contract()
    assert report.failures == ()


def test_current_product_spec_source_set_warnings_are_preserved():
    corpus = load_corpus()
    warnings = freshness_warnings(corpus)
    joined = "\n".join(warnings)

    assert UPLOADED_CURRENT_PRODUCT_SPEC in joined
    assert UPLOAD_AUTHORITY_COMMIT in joined
    assert "generated MANIFEST.md" in joined
    assert "upload authority" in joined
    assert "package-level freshness markers" in joined
    assert OMITTED_CURRENT_PRODUCT_SPEC_FILES[0] in joined
    assert "do not generate Mac/iOS app-build prompts" in joined
    assert "Freshness normalization TODO" in joined


def test_source_set_ladder_delta_bridge_contract_is_present():
    corpus = load_corpus()
    launch_text = corpus.launch_ladder_text.lower()

    assert "CHAT_STAY_UP_TO_DATE.md" in corpus.launch_ladder_text
    assert "Source-Set Ladder" in corpus.launch_ladder_text
    assert "005a4081d6fa78d36a22c1e26d7f6731f8e2dbb2" in corpus.launch_ladder_text
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


def test_workspace_launch_profile_source_set_and_apple_platform_posture_are_documented():
    corpus = load_corpus()
    launch_text = corpus.launch_ladder_text

    assert "This Workspace Launch Profile and profile-to-packet handoff contract slice stays in `01_CURRENT_PRODUCT_SPEC`" in launch_text
    assert "does not move the active ChatGPT Project source-set posture to `02_MAC_IOS_APP_BUILD`" in launch_text
    assert "does not create source-set folder `04`" in launch_text
    assert "does not create generated source-set scripts" in launch_text
    assert "does not edit generated source-set folders" in launch_text
    assert "`Mac/iOS` is Apple-platform planning shorthand" in launch_text
    assert "Mac desktop app first, iOS companion later" in launch_text
    assert "Do not read this brief as iOS-first implementation" in launch_text

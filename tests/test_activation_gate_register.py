import json

import activation_gate_register as register


FIXED_NOW = "2026-06-26T00:00:00-04:00"


def _payload():
    return register.build_activation_gate_register(last_verified_at=FIXED_NOW)


def _live_payload(sources):
    return register.build_activation_gate_register(
        last_verified_at=FIXED_NOW,
        live_env_sources=sources,
    )


def _capabilities_by_id(payload):
    return {item["capability_id"]: item for item in payload["capabilities"]}


def _test_source(values=None, *, error=None, ref="maestro-listener.service"):
    source = {
        "source_type": "test_source",
        "source_ref": ref,
        "values": values or {},
        "notes": "fake source for deterministic test",
    }
    if error is not None:
        source.pop("values")
        source["error"] = error
    return source


def test_known_capabilities_are_present():
    payload = _payload()
    capabilities = _capabilities_by_id(payload)

    for capability_id in register.REQUIRED_CAPABILITY_IDS:
        assert capability_id in capabilities
    for capability_id in register.REGISTER_GAP_CAPABILITY_IDS:
        assert capability_id in capabilities

    assert "lm_consult_spine" in capabilities
    assert "runtime_module_activation_gate" in capabilities
    assert payload["schema_version"] == register.SCHEMA_VERSION


def test_register_gap_capabilities_are_catalogued_with_no_activation_authority():
    capabilities = _capabilities_by_id(_payload())

    assert len(register.REGISTER_GAP_CAPABILITY_IDS) == 19
    for capability_id in register.REGISTER_GAP_CAPABILITY_IDS:
        capability = capabilities[capability_id]
        assert capability["activation_allowed_now"] is False
        assert capability["operator_approval_required"] is True
        assert capability["rollback_note"]
        assert capability["next_required_step"]
        assert capability["canary_status"]


def test_packet_source_sqlite_flip_is_standalone_capability():
    capabilities = _capabilities_by_id(_payload())
    packet_source = capabilities["packet_source_sqlite_flip"]
    continuity = capabilities["continuity_capsule"]

    assert packet_source["flag_or_config"] == ["OPENCLAW_PACKET_SOURCE"]
    assert packet_source["gate_stage"] == "canary"
    assert packet_source["risk_level"] == "medium"
    assert packet_source["activation_allowed_now"] is False
    assert "OPENCLAW_PACKET_SOURCE" in continuity["flag_or_config"]
    assert packet_source["capability_id"] != continuity["capability_id"]


def test_register_gap_whitelist_names_are_present():
    for name in [
        "OPENCLAW_MAESTRO_BRAIN_LIVE",
        "OPENCLAW_LLM_DIAGNOSTICS",
        "HITL_ENABLED",
        "OPENCLAW_ACTION_RUNTIME",
        "OPENCLAW_CONTROL_PLANE_EMIT",
        "OPENCLAW_OLLAMA_MODEL",
        "OPENCLAW_PROTECTED_GENERATE_LOCAL_TIMEOUT",
        "CASSANDRA_MORNING_BRIEF_TEST_MODE",
    ]:
        assert name in register.LIVE_ENV_WHITELIST


def test_high_risk_gap_capabilities_remain_off_or_blocked():
    capabilities = _capabilities_by_id(_payload())

    for capability_id in [
        "hitl_pipeline",
        "action_runtime",
        "walk_away_autonomy_mode",
        "nemotron_provider",
        "claude_agent_hard_block",
        "openai_adapter_stub",
    ]:
        capability = capabilities[capability_id]
        assert capability["activation_allowed_now"] is False
        assert capability["risk_level"] == "high"
        assert capability["gate_stage"] in {"intentionally_off", "blocked"}


def test_already_enabled_gap_guardrails_do_not_grant_activation_authority():
    capabilities = _capabilities_by_id(_payload())

    for capability_id in [
        "authority_gate_send_hold",
        "external_model_packet_policy",
        "maestro_brain_live",
        "llm_diagnostics_logging",
        "ollama_model_defaults",
        "protected_generate_ollama_timeouts",
    ]:
        capability = capabilities[capability_id]
        assert "enabled" in json.dumps(capability["current_state_if_verifiable"], sort_keys=True)
        assert capability["activation_allowed_now"] is False


def test_required_fields_and_gate_stages_are_valid():
    payload = _payload()

    for capability in payload["capabilities"]:
        assert set(register.REQUIRED_FIELDS) <= set(capability)
        assert capability["gate_stage"] in register.GATE_STAGES


def test_known_flags_are_detected_without_live_env_reads():
    payload = _payload()
    flags = payload["verification"]["flag_detection"]

    assert flags["OPENCLAW_INTERPRETER_LM"]["status"] == "found"
    assert "interpreter_lm.py" in flags["OPENCLAW_INTERPRETER_LM"]["files"]
    assert flags["OPENCLAW_FRONTDOOR_MODEL_PROFILE"]["status"] == "found"
    assert "protected_generate.py" in flags["OPENCLAW_FRONTDOOR_MODEL_PROFILE"]["files"]
    assert flags["OPENCLAW_PACKET_SOURCE"]["status"] == "found"
    assert "maestro_context_packet.py" in flags["OPENCLAW_PACKET_SOURCE"]["files"]
    assert flags["OPENCLAW_FREEFORM_CLOUD"]["status"] == "found"
    assert "protected_generate.py" in flags["OPENCLAW_FREEFORM_CLOUD"]["files"]
    assert flags["OPENCLAW_POLISH_LOOP_LOCAL_BUILDER"]["status"] in {
        "found",
        "not_found_in_scanned_repo_paths",
    }
    assert flags["OPENCLAW_POLISH_LOOP_FILE_LEDGER_BRIDGE"]["status"] == "found"
    assert "polish_loop/orchestrator.py" in flags["OPENCLAW_POLISH_LOOP_FILE_LEDGER_BRIDGE"]["files"]
    assert flags["OPENCLAW_POLISH_LOOP_TASK_PACKAGE_V1"]["status"] == "found"
    assert "polish_loop/worker_runtime.py" in flags["OPENCLAW_POLISH_LOOP_TASK_PACKAGE_V1"]["files"]

    assert payload["policy"]["production_env_files_inspected"] is False
    assert payload["policy"]["systemd_inspected_or_modified"] is False


def test_polish_loop_builder_flag_detection_handles_bridge_present(tmp_path):
    orchestrator = tmp_path / "polish_loop" / "orchestrator.py"
    orchestrator.parent.mkdir()
    orchestrator.write_text(
        'LOCAL_BUILDER_FLAG = "OPENCLAW_POLISH_LOOP_LOCAL_BUILDER"\n',
        encoding="utf-8",
    )

    payload = register.build_activation_gate_register(
        repo_root=tmp_path,
        last_verified_at=FIXED_NOW,
    )
    flag = payload["verification"]["flag_detection"]["OPENCLAW_POLISH_LOOP_LOCAL_BUILDER"]

    assert flag["status"] == "found"
    assert flag["files"] == ["polish_loop/orchestrator.py"]


def test_file_ledger_bridge_flag_is_registered_as_intentionally_off():
    capabilities = _capabilities_by_id(_payload())
    bridge = capabilities["polish_loop_file_ledger_bridge"]

    assert bridge["flag_or_config"] == ["OPENCLAW_POLISH_LOOP_FILE_LEDGER_BRIDGE"]
    assert bridge["gate_stage"] == "intentionally_off"
    assert bridge["risk_level"] == "medium"
    assert bridge["activation_allowed_now"] is False
    assert "canary" in bridge["next_required_step"].lower()


def test_task_package_flag_is_registered_as_intentionally_off():
    capabilities = _capabilities_by_id(_payload())
    package = capabilities["polish_loop_task_package_v1"]

    assert package["flag_or_config"] == ["OPENCLAW_POLISH_LOOP_TASK_PACKAGE_V1"]
    assert package["gate_stage"] == "intentionally_off"
    assert package["risk_level"] == "medium"
    assert package["activation_allowed_now"] is False
    assert "canary" in package["next_required_step"].lower()


def test_unknown_or_unverified_current_state_is_honest():
    capabilities = _capabilities_by_id(_payload())

    continuity = capabilities["continuity_capsule"]["current_state_if_verifiable"]
    assert "unknown" in continuity["production"]
    assert "audit_reported" in continuity["production"]

    computer_use = capabilities["computer_use_worker_gateway"]
    assert computer_use["gate_stage"] == "proposed"
    assert computer_use["current_state_if_verifiable"]["production"] == "not_applicable_proposed_only"

    frontdoor = capabilities["frontdoor_model_profile"]["current_state_if_verifiable"]
    assert "production state unknown" in frontdoor["summary"]


def test_no_capability_is_marked_safe_to_enable_without_evidence():
    payload = _payload()

    assert payload["summary"]["activation_allowed_now"] == []
    for capability in payload["capabilities"]:
        assert capability["activation_allowed_now"] is False


def test_blocked_sensitive_tracks_remain_blocked_or_intentionally_off():
    capabilities = _capabilities_by_id(_payload())

    for capability_id in register.SENSITIVE_BLOCKED_CAPABILITY_IDS:
        capability = capabilities[capability_id]
        assert capability["activation_allowed_now"] is False
        assert capability["operator_approval_required"] is True
        assert capability["gate_stage"] in {"blocked", "intentionally_off", "synthetic"}

    assert capabilities["legal_sealed_ingestion"]["gate_stage"] == "blocked"
    assert capabilities["polish_loop_factory_mode"]["gate_stage"] == "blocked"
    assert capabilities["cassandra_telegram_delivery"]["gate_stage"] == "intentionally_off"


def test_json_output_is_valid_and_stable():
    payload = _payload()
    encoded = register.stable_json(payload)
    decoded = json.loads(encoded)

    assert decoded == payload
    assert encoded == register.stable_json(_payload())


def test_markdown_output_includes_required_capabilities():
    markdown = register.render_markdown(_payload())

    assert "# Activation Gate Register" in markdown
    for capability_id in register.REQUIRED_CAPABILITY_IDS:
        assert f"`{capability_id}`" in markdown
    assert "Feature activation performed by this task: `no`" in markdown


def test_write_outputs_creates_deterministic_json_and_markdown(tmp_path):
    paths = register.write_outputs(output_dir=tmp_path, last_verified_at=FIXED_NOW)

    first_json = paths["json"].read_text(encoding="utf-8")
    first_markdown = paths["markdown"].read_text(encoding="utf-8")
    register.write_outputs(output_dir=tmp_path, last_verified_at=FIXED_NOW)

    assert paths["json"].read_text(encoding="utf-8") == first_json
    assert paths["markdown"].read_text(encoding="utf-8") == first_markdown
    assert json.loads(first_json)["summary"]["total_capabilities"] >= len(register.REQUIRED_CAPABILITY_IDS)


def test_live_continuity_enabled_marks_enabled_verified():
    payload = _live_payload([
        _test_source({"OPENCLAW_CONTINUITY_CAPSULE": "1"}),
    ])
    continuity = _capabilities_by_id(payload)["continuity_capsule"]

    assert continuity["live_production_state"] == "enabled_verified"
    assert continuity["current_state_if_verifiable"]["production"] == "enabled_verified"
    assert continuity["activation_allowed_now"] is False
    assert continuity["live_state"]["findings"][0]["redacted_value_category"] == "set_true"


def test_live_packet_source_sqlite_records_runtime_context():
    payload = _live_payload([
        _test_source({
            "OPENCLAW_CONTINUITY_CAPSULE": "1",
            "OPENCLAW_PACKET_SOURCE": "sqlite",
        })
    ])

    packet_source = payload["live_reconciliation"]["runtime_context"]["packet_source"]
    continuity = _capabilities_by_id(payload)["continuity_capsule"]
    standalone = _capabilities_by_id(payload)["packet_source_sqlite_flip"]

    assert packet_source["status"] == "enabled_verified"
    assert packet_source["findings"][0]["variable_name"] == "OPENCLAW_PACKET_SOURCE"
    assert packet_source["findings"][0]["redacted_value_category"] == "set_sqlite"
    assert continuity["live_state"]["related_findings"][0]["redacted_value_category"] == "set_sqlite"
    assert standalone["live_production_state"] == "enabled_verified"
    assert standalone["activation_allowed_now"] is False


def test_missing_interpreter_lm_stays_default_off():
    payload = _live_payload([
        _test_source({"OPENCLAW_CONTINUITY_CAPSULE": "1"}),
    ])
    interpreter = _capabilities_by_id(payload)["interpreter_lm"]

    assert interpreter["live_production_state"] == "unset_default_off"
    assert interpreter["activation_allowed_now"] is False
    assert interpreter["live_state"]["findings"][0]["redacted_value_category"] == "unset"


def test_missing_frontdoor_profile_stays_default_off():
    payload = _live_payload([
        _test_source({"OPENCLAW_CONTINUITY_CAPSULE": "1"}),
    ])
    frontdoor = _capabilities_by_id(payload)["frontdoor_model_profile"]

    assert frontdoor["live_production_state"] == "unset_default_off"
    assert frontdoor["activation_allowed_now"] is False


def test_polish_loop_local_builder_zero_keeps_bridge_off():
    payload = _live_payload([
        _test_source({"OPENCLAW_POLISH_LOOP_LOCAL_BUILDER": "0"}),
    ])
    bridge = _capabilities_by_id(payload)["polish_loop_local_builder_bridge"]

    assert bridge["live_production_state"] == "disabled_verified"
    assert bridge["activation_allowed_now"] is False
    assert "NOT_READY" in bridge["reason_if_off"]


def test_conflicting_sources_are_reported():
    payload = _live_payload([
        _test_source({"OPENCLAW_CONTINUITY_CAPSULE": "1"}, ref="maestro-listener.service"),
        _test_source({"OPENCLAW_CONTINUITY_CAPSULE": "0"}, ref="openclaw-request-response.service"),
    ])
    continuity = _capabilities_by_id(payload)["continuity_capsule"]

    assert continuity["live_production_state"] == "conflicting_sources"
    assert payload["summary"]["conflicting_live_state"] == ["continuity_capsule"]
    assert continuity["activation_allowed_now"] is False


def test_secret_like_values_are_redacted():
    payload = _live_payload([
        _test_source({
            "OPENROUTER_API_KEY": "sk-super-secret",
            "OPENROUTER_MODEL": "vendor/private-model",
            "NVIDIA_API_KEY": "nvapi-secret",
            "OPENAI_API_KEY": "sk-openai-secret",
            "OPENCLAW_EXTERNAL_SHADOW_CREDENTIAL": "shadow-secret",
            "OPENCLAW_FREEFORM_CLOUD": "0",
        })
    ])
    encoded = register.stable_json(payload)
    external = _capabilities_by_id(payload)["external_model_openrouter_path"]
    nemotron = _capabilities_by_id(payload)["nemotron_provider"]
    openai = _capabilities_by_id(payload)["openai_adapter_stub"]
    shadow = _capabilities_by_id(payload)["external_shadow_lm_config"]

    assert "sk-super-secret" not in encoded
    assert "vendor/private-model" not in encoded
    assert "nvapi-secret" not in encoded
    assert "sk-openai-secret" not in encoded
    assert "shadow-secret" not in encoded
    categories = {
        finding["variable_name"]: finding["redacted_value_category"]
        for finding in external["live_state"]["related_findings"]
    }
    assert categories["OPENROUTER_API_KEY"] == "set_other_redacted"
    assert categories["OPENROUTER_MODEL"] == "set_other_redacted"
    assert external["live_production_state"] == "configured_but_inert"
    assert nemotron["live_state"]["findings"][0]["redacted_value_category"] == "set_other_redacted"
    assert openai["live_state"]["findings"][0]["redacted_value_category"] == "set_other_redacted"
    assert shadow["live_state"]["findings"][0]["redacted_value_category"] == "set_other_redacted"


def test_unknown_unreadable_source_records_operator_verification_needed():
    payload = _live_payload([
        _test_source(error="permission_denied"),
    ])
    continuity = _capabilities_by_id(payload)["continuity_capsule"]

    assert continuity["live_production_state"] == "unknown_requires_operator_verification"
    assert payload["live_reconciliation"]["source_errors"][0]["status"] == "unknown_requires_operator_verification"
    assert continuity["live_state"]["findings"][0]["redacted_value_category"] == "unknown"


def test_live_enabled_does_not_grant_activation_allowed_now():
    payload = _live_payload([
        _test_source({
            "OPENCLAW_CONTINUITY_CAPSULE": "1",
            "OPENCLAW_PACKET_SOURCE": "sqlite",
        })
    ])

    assert payload["summary"]["verified_enabled"] == ["continuity_capsule", "packet_source_sqlite_flip"]
    assert payload["summary"]["activation_allowed_now"] == []
    for capability in payload["capabilities"]:
        assert capability["activation_allowed_now"] is False


def test_live_json_output_is_valid():
    payload = _live_payload([
        _test_source({"OPENCLAW_CONTINUITY_CAPSULE": "1"}),
    ])

    assert json.loads(register.stable_json(payload)) == payload


def test_markdown_includes_live_state_evidence():
    payload = _live_payload([
        _test_source({
            "OPENCLAW_CONTINUITY_CAPSULE": "1",
            "OPENCLAW_PACKET_SOURCE": "sqlite",
        })
    ])
    markdown = register.render_markdown(payload)

    assert "## Live Environment Reconciliation" in markdown
    assert "Live-state evidence:" in markdown
    assert "`enabled_verified`" in markdown
    assert "`OPENCLAW_PACKET_SOURCE`" in markdown
    assert "`set_sqlite`" in markdown


def test_live_generation_remains_deterministic_under_fake_sources():
    sources = [
        _test_source({
            "OPENCLAW_CONTINUITY_CAPSULE": "1",
            "OPENCLAW_PACKET_SOURCE": "sqlite",
            "OPENCLAW_POLISH_LOOP_LOCAL_BUILDER": "0",
        })
    ]
    first = _live_payload(sources)
    second = _live_payload(sources)

    assert register.stable_json(first) == register.stable_json(second)

import json

import activation_gate_register as register


FIXED_NOW = "2026-06-26T00:00:00-04:00"


def _payload():
    return register.build_activation_gate_register(last_verified_at=FIXED_NOW)


def _capabilities_by_id(payload):
    return {item["capability_id"]: item for item in payload["capabilities"]}


def test_known_capabilities_are_present():
    payload = _payload()
    capabilities = _capabilities_by_id(payload)

    for capability_id in register.REQUIRED_CAPABILITY_IDS:
        assert capability_id in capabilities

    assert "lm_consult_spine" in capabilities
    assert "runtime_module_activation_gate" in capabilities
    assert payload["schema_version"] == register.SCHEMA_VERSION


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
    assert flags["OPENCLAW_FREEFORM_CLOUD"]["status"] == "found"
    assert "protected_generate.py" in flags["OPENCLAW_FREEFORM_CLOUD"]["files"]
    assert flags["OPENCLAW_POLISH_LOOP_LOCAL_BUILDER"]["status"] == "not_found_in_scanned_repo_paths"

    assert payload["policy"]["production_env_files_inspected"] is False
    assert payload["policy"]["systemd_inspected_or_modified"] is False


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

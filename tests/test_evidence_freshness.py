import json

from scripts.build_evidence_freshness import (
    CLAIMS_NOT_MADE,
    READ_MODEL_VERSION,
    build_evidence_freshness,
    format_operator_evidence_freshness,
    main,
)


REQUIRED_ARTIFACT_FIELDS = {
    "artifact_id",
    "path",
    "exists",
    "freshness_state",
    "basis",
    "body_ingested",
}


def _read_model(**overrides):
    defaults = {
        "run_generated_status_check": False,
        "run_export_check": False,
    }
    defaults.update(overrides)
    return build_evidence_freshness(**defaults)


def _payload_text(payload):
    return json.dumps(payload, sort_keys=True).lower()


def test_json_output_has_required_top_level_fields():
    payload = _read_model()

    assert payload["read_model_version"] == READ_MODEL_VERSION
    assert payload["mode"] == "deterministic_freshness_read_model"
    for key in [
        "runtime_authority",
        "activation_allowed",
        "backend_execution_authorized",
        "body_ingested",
        "metadata_only",
        "broad_scan",
        "git_head",
        "generated_status_current",
        "read_model_exports_current",
        "artifact_count",
        "freshness_counts",
        "artifacts",
        "claims_not_made",
    ]:
        assert key in payload
    assert payload["artifact_count"] == len(payload["artifacts"])


def test_artifacts_have_required_fields_and_no_body_ingest():
    payload = _read_model()

    assert payload["body_ingested"] is False
    assert payload["metadata_only"] is True
    assert payload["broad_scan"] is False
    assert payload["hard_drive_scan"] is False
    assert payload["private_data_access"] is False
    for artifact in payload["artifacts"]:
        assert REQUIRED_ARTIFACT_FIELDS <= set(artifact)
        assert artifact["freshness_state"] in {"current", "missing", "stale", "unknown"}
        assert artifact["basis"] in {
            "generated_status_check",
            "export_check",
            "file_exists",
            "not_checked",
        }
        assert artifact["body_ingested"] is False


def test_generated_status_and_export_current_are_represented():
    payload = build_evidence_freshness(
        run_generated_status_check=True,
        run_export_check=True,
    )

    assert payload["generated_status_check"]["checked"] is True
    assert payload["generated_status_current"] in {True, False}
    assert payload["read_model_exports_check"]["checked"] is True
    assert payload["read_model_exports_current"] in {True, False}


def test_missing_artifact_handling_is_safe_for_temp_export_root(tmp_path):
    payload = build_evidence_freshness(
        export_root=tmp_path,
        run_generated_status_check=False,
        run_export_check=False,
        expected_export_paths=("missing_artifact.json",),
    )
    artifacts = {artifact["artifact_id"]: artifact for artifact in payload["artifacts"]}

    missing = artifacts["missing_artifact"]
    assert missing["path"] == str(tmp_path / "missing_artifact.json")
    assert missing["exists"] is False
    assert missing["freshness_state"] == "missing"
    assert missing["basis"] == "file_exists"
    assert missing["body_ingested"] is False


def test_output_does_not_emit_raw_bodies_or_claim_live_health():
    payload = _read_model()
    output = format_operator_evidence_freshness(payload)
    text = _payload_text(payload) + "\n" + output.lower()

    for forbidden in [
        "extracted_text",
        "all systems nominal",
        "runtime healthy",
        "runtime ready",
        "agents are active",
        "dynamic worlds are active",
        "strategic gravity scoring is implemented",
        "live heartbeat",
        "process heartbeat",
        "networking enabled",
        "customer deployment active",
    ]:
        assert forbidden not in text
    assert payload["runtime_authority"] is False
    assert payload["activation_allowed"] is False
    assert payload["backend_execution_authorized"] is False
    assert payload["claims_not_made"] == CLAIMS_NOT_MADE


def test_operator_output_uses_cockpit_grammar():
    output = format_operator_evidence_freshness(_read_model())

    assert "Evidence Freshness Read-Model v0" in output
    assert "Evidence:" in output
    assert "Boundary:" in output
    assert "Blocked:" in output
    assert "Next safe move:" in output
    assert "Generated status current:" in output
    assert "Read-model exports current:" in output
    assert output.index("Evidence:") < output.index("Boundary:")
    assert output.index("Boundary:") < output.index("Blocked:")
    assert output.index("Blocked:") < output.index("Next safe move:")
    assert '"artifacts"' not in output


def test_cli_json_output_is_machine_readable(capsys):
    exit_code = main(["--format", "json", "--skip-generated-status-check", "--skip-export-check"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["read_model_version"] == READ_MODEL_VERSION
    assert payload["body_ingested"] is False
    assert payload["runtime_authority"] is False


def test_cli_operator_output(capsys):
    exit_code = main(["--format", "operator", "--skip-generated-status-check", "--skip-export-check"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Evidence Freshness Read-Model v0" in output
    assert "Evidence:" in output
    assert "Boundary:" in output
    assert "Blocked:" in output
    assert "Next safe move:" in output

import json
from pathlib import Path

from scripts.export_read_models import (
    CLAIMS_NOT_MADE,
    EXPORT_VERSION,
    EXPECTED_EXPORT_PATHS,
    build_expected_exports,
    export_read_models,
    format_operator_export_summary,
    main,
)


def _export_root(tmp_path):
    return tmp_path / "generated" / "read_models"


def _summary(tmp_path):
    return export_read_models(export_root=_export_root(tmp_path))


def test_export_directory_is_created(tmp_path):
    export_root = _export_root(tmp_path)

    assert not export_root.exists()
    summary = export_read_models(export_root=export_root)

    assert export_root.is_dir()
    assert summary["export_root"] == export_root.as_posix()


def test_expected_exports_exist(tmp_path):
    summary = _summary(tmp_path)
    paths = {export["path"] for export in summary["exports"]}

    assert paths == {
        (_export_root(tmp_path) / path).as_posix()
        for path in EXPECTED_EXPORT_PATHS
    }
    for path in paths:
        assert Path(path).is_file()


def test_expected_json_exports_parse(tmp_path):
    summary = _summary(tmp_path)

    for export in summary["exports"]:
        if export["format"] != "json":
            continue
        with Path(export["path"]).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        assert isinstance(payload, dict)


def test_expected_operator_text_exports_exist(tmp_path):
    summary = _summary(tmp_path)
    operator_paths = [
        Path(export["path"])
        for export in summary["exports"]
        if export["format"] == "operator_text"
    ]

    assert operator_paths
    for path in operator_paths:
        text = path.read_text(encoding="utf-8")
        assert "Evidence:" in text
        assert "Boundary:" in text
        assert "Blocked:" in text
        assert "Next safe move:" in text


def test_exports_are_metadata_read_model_only(tmp_path):
    summary = _summary(tmp_path)

    assert summary["export_version"] == EXPORT_VERSION
    assert summary["metadata_only"] is True
    assert summary["body_ingested"] is False
    assert summary["runtime_authority"] is False
    assert summary["activation_allowed"] is False
    assert summary["backend_execution_authorized"] is False
    assert summary["broad_scan"] is False
    for export in summary["exports"]:
        assert export["body_ingested"] is False
        assert export["runtime_authority"] is False
        assert export["activation_allowed"] is False
        assert export["backend_execution_authorized"] is False


def test_no_raw_source_bodies_are_exported(tmp_path):
    summary = _summary(tmp_path)

    for export in summary["exports"]:
        text = Path(export["path"]).read_text(encoding="utf-8")
        assert "extracted_text" not in text
        assert "source_body" not in text
    assert "full_body_ingest" in summary["claims_not_made"]


def test_check_passes_when_exports_are_current(tmp_path):
    export_root = _export_root(tmp_path)
    export_read_models(export_root=export_root)

    summary = export_read_models(export_root=export_root, check=True)

    assert summary["check_mode"] is True
    assert summary["check_status"] == "current"
    assert summary["stale_exports"] == []


def test_check_reports_stale_when_export_differs(tmp_path):
    export_root = _export_root(tmp_path)
    export_read_models(export_root=export_root)
    (export_root / "helm_state.json").write_text("stale\n", encoding="utf-8")

    summary = export_read_models(export_root=export_root, check=True)

    assert summary["check_status"] == "stale"
    assert (export_root / "helm_state.json").as_posix() in summary["stale_exports"]


def test_operator_output_uses_cockpit_grammar(tmp_path):
    output = format_operator_export_summary(_summary(tmp_path))

    assert "Read-Model Exports v0" in output
    assert "Evidence:" in output
    assert "Boundary:" in output
    assert "Blocked:" in output
    assert "Next safe move:" in output
    assert output.index("Evidence:") < output.index("Boundary:")
    assert output.index("Boundary:") < output.index("Blocked:")
    assert output.index("Blocked:") < output.index("Next safe move:")
    assert "generated/read_models" in output


def test_operator_output_does_not_claim_runtime_behavior(tmp_path):
    output = format_operator_export_summary(_summary(tmp_path)).lower()

    for forbidden in [
        "all systems nominal",
        "runtime healthy",
        "runtime ready",
        "runtime activation is allowed",
        "agents are active",
        "dynamic worlds are active",
        "strategic gravity scoring is implemented",
        "broker connected",
        "external tools active",
        "networking enabled",
        "customer deployment active",
        "live heartbeat",
        "process heartbeat",
    ]:
        assert forbidden not in output


def test_build_expected_exports_does_not_write_files(tmp_path):
    export_root = _export_root(tmp_path)
    exports = build_expected_exports(export_root=export_root)

    assert exports
    assert not export_root.exists()


def test_cli_json_output_writes_exports_and_is_machine_readable(tmp_path, capsys):
    export_root = _export_root(tmp_path)

    exit_code = main(["--format", "json", "--export-root", export_root.as_posix()])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["export_version"] == EXPORT_VERSION
    assert payload["body_ingested"] is False
    assert (export_root / "source_inventory.json").is_file()


def test_cli_operator_output(tmp_path, capsys):
    export_root = _export_root(tmp_path)

    exit_code = main(["--format", "operator", "--export-root", export_root.as_posix()])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Read-Model Exports v0" in output
    assert "Evidence:" in output
    assert (export_root / "artifact_registry.operator.txt").is_file()


def test_cli_check_passes_when_exports_are_current(tmp_path, capsys):
    export_root = _export_root(tmp_path)
    main(["--format", "json", "--export-root", export_root.as_posix()])

    exit_code = main(["--check", "--export-root", export_root.as_posix()])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "OK: read-model exports are current." in output


def test_claims_not_made_are_exposed(tmp_path):
    summary = _summary(tmp_path)

    assert summary["claims_not_made"] == CLAIMS_NOT_MADE
    assert "runtime_activation_authority" in summary["claims_not_made"]
    assert "broker_connection" in summary["claims_not_made"]
    assert "customer_deployment" in summary["claims_not_made"]

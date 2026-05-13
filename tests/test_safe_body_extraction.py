import json

from scripts.build_source_inventory import BlockedExample, build_inventory
from scripts.extract_accepted_sources import (
    EVIDENCE_LABEL,
    EXTRACTION_ARTIFACT_VERSION,
    build_extraction_artifact,
    format_operator_extraction,
    main,
)
from scripts.promote_accepted_context import build_promotion_manifest, write_json_artifact


def _inventory(tmp_path, *, large=False):
    (tmp_path / "docs").mkdir()
    body = "# Allowed\n\nSafe body.\n"
    if large:
        body = "# Allowed\n\n" + ("x" * 80)
    (tmp_path / "docs" / "allowed.md").write_text(body, encoding="utf-8")
    (tmp_path / "docs" / "unapproved.md").write_text("# Not approved\n", encoding="utf-8")
    return build_inventory(
        root=tmp_path,
        allowlist=("docs/allowed.md",),
        blocked_examples=(
            BlockedExample(
                ".chief.env",
                "secret_or_credential",
                "credential file is outside source inventory scope",
            ),
        ),
    )


def _promotion(tmp_path, *, large=False):
    return build_promotion_manifest(
        _inventory(tmp_path, large=large),
        requested_paths=("docs/allowed.md",),
        reason_for_promotion="extract deterministic source evidence",
    )


def test_approved_file_extracts(tmp_path):
    artifact = build_extraction_artifact(_promotion(tmp_path))

    assert artifact["artifact_version"] == EXTRACTION_ARTIFACT_VERSION
    assert artifact["summary"]["extracted_records"] == 1
    assert artifact["summary"]["refused_records"] == 0
    record = artifact["records"][0]
    assert record["path"] == "docs/allowed.md"
    assert record["extraction_state"] == "extracted"
    assert record["extracted_text"] == "# Allowed\n\nSafe body.\n"
    assert record["source_sha256"]


def test_unapproved_file_does_not_extract(tmp_path):
    manifest = _promotion(tmp_path)
    malicious_record = dict(manifest["records"][0])
    malicious_record["path"] = "docs/unapproved.md"
    manifest["records"] = [malicious_record]

    artifact = build_extraction_artifact(manifest)

    assert artifact["summary"]["extracted_records"] == 0
    assert artifact["summary"]["refused_records"] == 1
    assert artifact["refusals"][0]["reason_refused"] == "path_not_in_source_inventory_allowlist"


def test_no_go_path_is_refused(tmp_path):
    manifest = _promotion(tmp_path)
    malicious_record = dict(manifest["records"][0])
    malicious_record["path"] = ".chief.env"
    manifest["records"] = [malicious_record]

    artifact = build_extraction_artifact(manifest)

    assert artifact["summary"]["extracted_records"] == 0
    assert artifact["refusals"][0]["path"] == ".chief.env"
    assert artifact["refusals"][0]["body_ingested"] is False


def test_max_size_is_enforced(tmp_path):
    artifact = build_extraction_artifact(_promotion(tmp_path, large=True), max_bytes=20)

    assert artifact["summary"]["extracted_records"] == 0
    assert artifact["summary"]["refused_records"] == 1
    assert artifact["refusals"][0]["reason_refused"].startswith("max_size_exceeded:")


def test_extracted_body_is_labeled_parsed_evidence_not_truth(tmp_path):
    artifact = build_extraction_artifact(_promotion(tmp_path))
    record = artifact["records"][0]

    assert record["evidence_label"] == EVIDENCE_LABEL
    assert record["truth_status"] == "not_truth"
    assert record["ingestion_state"] == "extracted"
    assert record["body_ingested"] is True


def test_no_runtime_authority_or_sqlite_touch(tmp_path):
    artifact = build_extraction_artifact(_promotion(tmp_path))

    assert artifact["scope"]["sqlite_touched"] is False
    assert artifact["scope"]["runtime_authority"] is False
    assert artifact["scope"]["runtime_activation"] is False
    assert artifact["scope"]["agent_activation"] is False
    for record in artifact["records"]:
        assert record["runtime_authority"] is False
        assert record["not_runtime_authority"] is True


def test_operator_output_uses_gate_grammar(tmp_path):
    artifact = build_extraction_artifact(_promotion(tmp_path))
    output = format_operator_extraction(artifact)

    assert "Evidence:" in output
    assert "Boundary:" in output
    assert "Blocked:" in output
    assert "Next safe move:" in output
    assert "parsed_evidence_not_truth" in output
    assert "SQLite is untouched" in output
    assert "`runtime_authority=false`" in output
    assert "No agents, modules, brokers, customer deployment, external tools, or runtime behavior are activated." in output
    assert "# Allowed" not in output
    assert '"extracted_text"' not in output


def test_cli_json_output_is_machine_readable(tmp_path, capsys):
    promotion_path = tmp_path / "promotion.json"
    write_json_artifact(_promotion(tmp_path), promotion_path)

    exit_code = main(
        [
            "--promotion-manifest",
            str(promotion_path),
            "--format",
            "json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["artifact_version"] == EXTRACTION_ARTIFACT_VERSION
    assert payload["summary"]["extracted_records"] == 1
    assert payload["records"][0]["evidence_label"] == EVIDENCE_LABEL

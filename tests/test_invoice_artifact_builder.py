import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import invoice_artifact_builder as builder
from scripts.build_invoice_artifact import main as build_main
from scripts.export_invoice_artifact_readback import main as export_main


FIXED_NOW = "2026-05-25T23:59:00+00:00"


def _payload(tmp_path: Path | None = None) -> dict:
    repo_root = tmp_path if tmp_path else Path.cwd()
    artifact_root = repo_root / "generated" / "invoice_artifacts" / "capital_hilton" if tmp_path else builder.DEFAULT_ARTIFACT_ROOT
    return builder.build_payload(generated_at=FIXED_NOW, repo_root=repo_root, artifact_root=artifact_root, write_files=True)


def test_required_models_exist():
    for name in [
        "InvoiceArtifactBuildRequest",
        "InvoiceArtifact",
        "InvoiceArtifactReadback",
        "InvoiceAttachmentRef",
        "InvoiceArtifactBlocker",
    ]:
        assert hasattr(builder, name)


def test_capital_hilton_example_exists_and_builds_artifacts(tmp_path):
    payload = _payload(tmp_path)

    assert payload["build_request"]["invoice_type"] == "CAPITAL_HILTON_PERFORMANCE_INVOICE"
    assert payload["capital_hilton_example"]["known_facts"][0] == "4 performance dates"
    assert payload["readback"]["status"] == "ARTIFACT_READY"
    assert len(payload["artifacts"]) == 3
    assert {artifact["output_format"] for artifact in payload["artifacts"]} == {"PDF", "XLSX", "CSV_SUMMARY"}


def test_artifact_refs_have_hashes_and_files_exist(tmp_path):
    payload = _payload(tmp_path)

    for artifact in payload["artifacts"]:
        assert artifact["hash_or_fingerprint"].startswith("sha256:")
        assert artifact["file_size_bytes"] > 0
        assert artifact["local_path_policy"].startswith("bounded_generated_artifact_ref:")
        rel = artifact["local_path_policy"].split(":", 1)[1]
        assert (tmp_path / rel).is_file()


def test_attachment_refs_require_artifact_proof(tmp_path):
    payload = _payload(tmp_path)
    attachment_refs = {ref["artifact_type"]: ref for ref in payload["attachment_refs"]}

    assert attachment_refs["WINSHIP_BRANDED_INVOICE_PDF"]["approved_for_email_package"] is True
    assert attachment_refs["WINSHIP_BRANDED_INVOICE_XLSX"]["approved_for_email_package"] is True
    assert attachment_refs["INVOICE_METADATA_SUMMARY"]["approved_for_email_package"] is False
    for ref in payload["attachment_refs"]:
        assert ref["raw_body_included"] is False
        assert ref["hash_or_fingerprint"].startswith("sha256:")


def test_hash_required_before_attachment_ready(tmp_path):
    request = builder.build_capital_hilton_request(generated_at=FIXED_NOW)
    artifacts = builder.build_artifacts(
        request,
        repo_root=tmp_path,
        artifact_root=tmp_path / "generated" / "invoice_artifacts",
        write_files=True,
    )
    broken = artifacts[0].__class__(**{**artifacts[0].__dict__, "hash_or_fingerprint": "", "attachment_ready": False})
    refs = builder.build_attachment_refs((broken,))

    assert refs[0].approved_for_email_package is False


def test_output_path_is_bounded(tmp_path):
    request = builder.build_capital_hilton_request(generated_at=FIXED_NOW)

    try:
        builder.build_artifacts(request, repo_root=tmp_path, artifact_root=tmp_path / "outside", write_files=True)
    except ValueError as exc:
        assert "generated/invoice_artifacts" in str(exc)
    else:
        raise AssertionError("unsafe output path should fail")


def test_blockers_exist_and_external_actions_blocked():
    payload = _payload()
    blockers = {row["blocker_type"]: row for row in payload["invoice_artifact_blockers"]}

    for blocker_type in builder.BLOCKER_TYPES:
        assert blocker_type in blockers
        assert blockers[blocker_type]["fail_closed"] is True
    assert blockers["EMAIL_SEND_ATTEMPTED"]["severity"] == "critical"
    assert blockers["COUPA_SUBMIT_ATTEMPTED"]["severity"] == "critical"
    assert blockers["EXTERNAL_ACTION_ATTEMPTED"]["severity"] == "critical"


def test_authority_boundary_all_live_false_except_bounded_local_generation(tmp_path):
    payload = _payload(tmp_path)

    assert payload["authority_boundary"]["bounded_local_artifact_generation_allowed"] is True
    assert payload["authority_boundary"]["bounded_local_file_hash_allowed"] is True
    for key, value in payload["authority_boundary"].items():
        if key in {
            "bounded_local_artifact_generation_allowed",
            "bounded_local_file_hash_allowed",
            "local_generated_read_model_allowed",
        }:
            continue
        assert value is False, key
    for key in [
        "email_send_performed",
        "mail_or_gmail_send_performed",
        "coupa_access_or_submit_performed",
        "browser_access_performed",
        "external_action_performed",
        "credential_handling_performed",
        "raw_file_body_in_read_model",
        "raw_body_ingestion_performed",
        "mac_sync_import_performed",
        "swift_change_performed",
        "git_push_performed",
    ]:
        assert payload["machine_proof"][key] is False


def test_scripts_build_and_export(tmp_path, capsys):
    artifact_root = tmp_path / "generated" / "invoice_artifacts" / "capital_hilton"
    assert build_main([
        "--fixture",
        "capital_hilton",
        "--repo-root",
        str(tmp_path),
        "--export-root",
        str(tmp_path),
        "--artifact-root",
        str(artifact_root),
        "--format",
        "json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["readback"]["status"] == "ARTIFACT_READY"

    assert export_main([
        "--export-root",
        str(tmp_path),
        "--repo-root",
        str(tmp_path),
        "--artifact-root",
        str(artifact_root),
        "--format",
        "summary",
    ]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["readback_status"] == "ARTIFACT_READY"
    assert (tmp_path / builder.JSON_EXPORT_NAME).is_file()
    assert (tmp_path / builder.OPERATOR_EXPORT_NAME).is_file()


def test_generated_outputs_have_no_raw_bodies_or_secrets(tmp_path):
    payload = _payload(tmp_path)
    builder.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir() if path.is_file())

    assert "actual secret value" not in text.lower()
    assert "raw private body value" not in text.lower()
    assert "credential value" not in text.lower()
    assert "token value" not in text.lower()
    assert "raw file body value" not in text.lower()
    assert "attachment bytes" not in text.lower()
    assert "AKIA" not in text
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gated_email_draft_adapter as adapter
from scripts.export_gated_email_draft_adapter import main as export_main
from scripts.run_gated_email_draft_adapter import main as run_main


FIXED_NOW = "2026-05-25T23:59:00+00:00"


def _payload(tmp_path: Path | None = None, *, write_files: bool = False) -> dict:
    repo_root = tmp_path or ROOT
    artifact_root = repo_root / "generated" / "email_drafts" / "gated_email_draft_adapter_v0"
    return adapter.build_payload(
        generated_at=FIXED_NOW,
        repo_root=repo_root,
        artifact_root=artifact_root,
        write_files=write_files,
    )


def test_required_models_exist():
    for name in [
        "GatedEmailDraftAdapter",
        "EmailDraftCreationRequest",
        "EmailDraftArtifact",
        "EmailDraftGate",
        "EmailDraftReadback",
        "EmailDraftProofPlan",
        "EmailDraftAdapterBlocker",
    ]:
        assert hasattr(adapter, name)


def test_capital_hilton_draft_examples_exist():
    payload = _payload()

    metadata = payload["examples"]["capital_hilton_metadata_draft_package"]
    local = payload["examples"]["capital_hilton_local_eml_draft_artifact"]

    assert metadata["request"]["provider_target"] == "METADATA_ONLY_DRAFT"
    assert metadata["readback"]["status"] == "METADATA_DRAFT_READY"
    assert local["request"]["provider_target"] == "LOCAL_EML_FILE"
    assert local["readback"]["status"] == "LOCAL_DRAFT_ARTIFACT_READY"
    assert "Nothing has been sent" in local["readback"]["operator_message"]


def test_local_eml_is_bounded_written_and_hashed(tmp_path):
    payload = _payload(tmp_path, write_files=True)
    local_artifact = payload["examples"]["capital_hilton_local_eml_draft_artifact"]["local_artifact"]
    policy = local_artifact["local_path_policy"]
    rel_path = policy.removeprefix("bounded_local_eml_ref:")
    eml_path = tmp_path / rel_path
    text = eml_path.read_text(encoding="utf-8")

    assert eml_path.exists()
    assert str(eml_path.resolve()).startswith(str((tmp_path / "generated" / "email_drafts").resolve()))
    assert local_artifact["hash_or_fingerprint"].startswith("sha256:")
    assert local_artifact["file_size_bytes"] > 0
    assert "X-OpenClaw-Review-Only: true" in text
    assert "Nothing was sent" in text
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)


def test_missing_recipient_blocks_with_fix():
    example = _payload()["examples"]["missing_recipient"]

    assert example["readback"]["status"] == "NOT_READY_MISSING_RECIPIENT"
    assert "Confirm Annette/contact route" in example["readback"]["how_to_fix"]
    assert example["gate"]["draft_create_allowed"] is False


def test_missing_body_blocks_with_fix():
    example = _payload()["examples"]["missing_body"]

    assert example["readback"]["status"] == "NOT_READY_MISSING_BODY"
    assert "Cassandra" in example["readback"]["how_to_fix"]
    assert example["draft_artifact"]["draft_status"] == "BLOCKED_MISSING_BODY"


def test_missing_attachment_blocks_with_fix():
    example = _payload()["examples"]["missing_attachment"]

    assert example["readback"]["status"] == "NOT_READY_MISSING_ATTACHMENT"
    assert "Generate, attach, and hash" in example["readback"]["how_to_fix"]
    assert example["draft_artifact"]["draft_status"] == "BLOCKED_MISSING_ATTACHMENT"


def test_send_attempt_blocks_and_keeps_authority_false():
    example = _payload()["examples"]["attempted_send"]

    assert example["readback"]["status"] == "BLOCKED_SEND_GATE"
    assert "send attempt" in example["readback"]["operator_message"].lower()
    assert example["gate"]["send_allowed"] is False
    assert example["gate"]["external_authority"] is False
    assert "send attempted but blocked" in example["gate"]["missing_items"]


def test_live_provider_unavailable_blocks():
    example = _payload()["examples"]["live_provider_unavailable"]

    assert example["request"]["provider_target"] == "GMAIL_DRAFT"
    assert example["request"]["requested_mode"] == "LIVE_GMAIL_DRAFT_GATED"
    assert example["readback"]["status"] == "BLOCKED_PROVIDER_UNAVAILABLE"
    assert example["gate"]["required_provider_adapter_ref"] == "missing_live_provider_adapter"


def test_all_blockers_exist_and_fail_closed():
    blockers = {row["blocker_type"]: row for row in _payload()["email_draft_adapter_blockers"]}

    for blocker_type in adapter.BLOCKER_TYPES:
        assert blocker_type in blockers
        assert blockers[blocker_type]["fail_closed"] is True
    assert blockers["SEND_ATTEMPTED"]["severity"] == "critical"
    assert blockers["RAW_ATTACHMENT_BODY_INCLUDED"]["severity"] == "critical"


def test_all_live_authority_false_except_bounded_local_eml():
    payload = _payload()

    assert payload["machine_proof"]["all_live_authority_false_except_bounded_local_eml"] is True
    allowed_true = {
        "bounded_local_eml_artifact_allowed",
        "bounded_local_file_hash_allowed",
        "local_generated_read_model_allowed",
    }
    for key, value in payload["authority_boundary"].items():
        if key in allowed_true:
            assert value is True
        else:
            assert value is False, key
    for key in [
        "email_send_performed",
        "gmail_send_performed",
        "mail_send_performed",
        "attachment_send_performed",
        "live_gmail_draft_created",
        "live_mail_draft_created",
        "coupa_access_performed",
        "browser_access_performed",
        "approval_execution_performed",
        "workflow_run_performed",
        "agent_dispatch_performed",
        "external_action_performed",
        "credential_handling_performed",
        "raw_attachment_body_included",
        "raw_body_ingestion_performed",
        "mac_sync_import_performed",
        "swift_change_performed",
        "git_push_performed",
    ]:
        assert payload["machine_proof"][key] is False


def test_export_writes_json_and_operator_markdown(tmp_path, capsys):
    assert export_main(["--repo-root", str(tmp_path), "--export-root", str(tmp_path), "--artifact-root", str(tmp_path / "generated" / "email_drafts" / "gated_email_draft_adapter_v0"), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / adapter.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / adapter.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["read_model_id"] == adapter.READ_MODEL_ID
    assert summary["local_draft_status"] == "LOCAL_DRAFT_ARTIFACT_READY"
    assert summary["all_live_authority_false_except_bounded_local_eml"] is True
    assert payload["schema_version"] == adapter.SCHEMA_VERSION
    assert "Gated Email Draft Adapter" in operator
    assert "No email send" in operator


def test_run_cli_writes_outputs(tmp_path, capsys):
    export_root = tmp_path / "read_models"
    artifact_root = tmp_path / "generated" / "email_drafts" / "gated_email_draft_adapter_v0"

    assert run_main(["--fixture", "capital_hilton", "--repo-root", str(tmp_path), "--export-root", str(export_root), "--artifact-root", str(artifact_root), "--format", "json"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["read_model_id"] == adapter.READ_MODEL_ID
    assert (export_root / adapter.JSON_EXPORT_NAME).exists()
    assert result["examples"]["capital_hilton_local_eml_draft_artifact"]["local_artifact"]["hash_or_fingerprint"].startswith("sha256:")


def test_generated_outputs_have_no_raw_email_attachment_or_secrets(tmp_path):
    payload = _payload(tmp_path, write_files=True)
    adapter.write_exports(payload, tmp_path)
    files = list(tmp_path.iterdir()) + list((tmp_path / "generated" / "email_drafts" / "gated_email_draft_adapter_v0").iterdir())
    text = "\n".join(path.read_text(encoding="utf-8") for path in files if path.is_file())

    assert "actual secret value" not in text.lower()
    assert "raw private body value" not in text.lower()
    assert "credential value" not in text.lower()
    assert "token value" not in text.lower()
    assert "raw attachment body value" not in text.lower()
    assert "attachment bytes" not in text.lower()
    assert "AKIA" not in text
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)

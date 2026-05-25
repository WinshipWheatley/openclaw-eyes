import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import repo_b_niles_music_worker_wrapper as wrapper
from scripts.export_repo_b_niles_music_worker_wrapper import main as export_main
from scripts.run_repo_b_niles_music_worker_wrapper import main as run_main


FIXED_NOW = "2026-05-25T23:00:00+00:00"


def _payload() -> dict:
    return wrapper.build_payload(generated_at=FIXED_NOW)


def test_required_models_exist():
    for name in [
        "RepoBNilesMusicWorkerDecision",
        "NilesCreativeCapability",
        "NilesCreativeWorkerRequest",
        "NilesCreativeWorkerReadback",
        "NilesCreativeWorkerBlocker",
    ]:
        assert hasattr(wrapper, name)


def test_repo_b_music_components_classified():
    payload = _payload()
    decisions = {row["source_module"]: row for row in payload["niles_worker_decisions"]}

    assert decisions["chief_album_brain.py"]["recommended_posture"] == "WRAP_AS_WORKER"
    assert "local LLM extraction" in decisions["chief_album_brain.py"]["blocked_items"]
    assert decisions["chief_album_mixer.py"]["recommended_posture"] == "REBUILD_SMALL_SUBSET_IN_REPO_A"
    assert "LLM mix brief generation" in decisions["chief_album_mixer.py"]["blocked_items"]
    assert decisions["chief_album_io.py"]["recommended_posture"] == "PROMOTE_SELECTED_MODULE"
    assert decisions["album_work_log.csv"]["recommended_posture"] == "REFERENCE_ONLY"


def test_creative_capabilities_are_safe_and_cover_required_types():
    payload = _payload()
    capability_types = {row["capability_type"] for row in payload["creative_capabilities"]}

    for required in [
        "SETLIST_PLANNING",
        "ALBUM_TASK_TRACKING",
        "SONG_METADATA_ORGANIZATION",
        "MIX_NOTE_SUMMARY",
        "ARRANGEMENT_IDEA",
        "LIVE_SHOW_PLANNING",
        "CREATIVE_PROJECT_STATUS",
        "WORK_LOG_READBACK",
        "SOURCE_REF_NAVIGATION",
    ]:
        assert required in capability_types

    for capability in payload["creative_capabilities"]:
        assert capability["deterministic"] is True
        assert capability["external_authority"] is False
        assert capability["file_mutation_required"] is False
        assert capability["raw_private_data_required"] is False
        assert capability["wrapper_allowed"] is True


def test_request_and_readback_models_for_setlist_fixture():
    request = wrapper.build_request("setlist", FIXED_NOW)
    readback = wrapper.build_fixture_readback(request)

    assert request.requested_capability == "SETLIST_PLANNING"
    assert request.world_ref == "music"
    assert request.folder_ref == "music/live_music/setlists"
    assert readback.status == "FIXTURE_READBACK_READY"
    assert "external posting" in readback.blocked_actions
    assert "DAW access" in readback.blocked_actions


def test_required_examples_exist():
    examples = _payload()["examples"]

    assert examples["setlist_planning"]["request"]["requested_capability"] == "SETLIST_PLANNING"
    assert examples["x32_live_show_context"]["request"]["folder_ref"] == "music/live_music/x32"
    assert examples["album_song_workspace"]["readback"]["status"] == "FIXTURE_READBACK_READY"
    assert examples["mix_notes_summary"]["readback"]["status"] == "FIXTURE_READBACK_READY"
    assert examples["struna_creative_build_bridge"]["request"]["project_ref"] == "struna"


def test_x32_context_uses_source_ref_navigation_and_no_mixer_mutation():
    example = _payload()["examples"]["x32_live_show_context"]

    assert example["request"]["requested_capability"] == "SOURCE_REF_NAVIGATION"
    assert example["readback"]["status"] == "MISSING_INPUTS"
    assert "X32 show-file metadata source ref" in example["readback"]["missing_inputs"]
    assert "mixer mutation" in example["readback"]["blocked_actions"]


def test_album_song_workspace_excludes_raw_lyrics():
    example = _payload()["examples"]["album_song_workspace"]

    assert "raw notes" in " ".join(example["readback"]["creative_output"]).lower()
    assert "raw lyric body exposure" in example["readback"]["blocked_actions"]
    assert example["request"]["source_refs"]


def test_mix_notes_summary_blocks_raw_note_bodies():
    example = _payload()["examples"]["mix_notes_summary"]

    assert "Raw note bodies remain excluded" in " ".join(example["readback"]["creative_output"])
    assert "raw note body exposure" in example["readback"]["blocked_actions"]


def test_daw_mutation_blocked():
    payload = _payload()
    blockers = {row["blocker_type"]: row for row in payload["niles_worker_blockers"]}
    example = payload["examples"]["daw_mutation_blocker"]

    assert blockers["DAW_MUTATION_ATTEMPTED"]["fail_closed"] is True
    assert example["readback"]["status"] == "BLOCKED_FILE_MUTATION"
    assert "DAW control" in example["readback"]["blocked_actions"]
    assert "No DAW was opened." in example["readback"]["creative_output"]


def test_struna_example_preserves_metadata_not_legal_truth():
    example = _payload()["examples"]["struna_creative_build_bridge"]

    assert example["request"]["project_ref"] == "struna"
    output = " ".join(example["readback"]["creative_output"])
    assert "not legal advice or proof" in output
    assert "source mutation" in example["readback"]["blocked_actions"]


def test_authority_boundary_all_false():
    payload = _payload()

    assert payload["machine_proof"]["all_live_authority_false"] is True
    for key, value in payload["authority_boundary"].items():
        assert value is False, key
    for key in [
        "repo_b_code_imported",
        "repo_b_runtime_executed",
        "daw_control_performed",
        "audio_file_mutation_performed",
        "video_file_mutation_performed",
        "project_file_mutation_performed",
        "export_publish_upload_performed",
        "external_action_performed",
        "credential_handling_performed",
        "raw_private_body_exposure",
        "mac_sync_import_performed",
        "swift_change_performed",
        "git_push_performed",
    ]:
        assert payload["machine_proof"][key] is False


def test_export_writes_json_and_operator_markdown(tmp_path, capsys):
    assert export_main(["--export-root", str(tmp_path), "--generated-at", FIXED_NOW, "--format", "summary"]) == 0
    summary = json.loads(capsys.readouterr().out)
    payload = json.loads((tmp_path / wrapper.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    operator = (tmp_path / wrapper.OPERATOR_EXPORT_NAME).read_text(encoding="utf-8")

    assert summary["posture"] == "WRAP_AS_WORKER_WITH_PROMOTED_DETERMINISTIC_SUBSET"
    assert payload["schema_version"] == wrapper.SCHEMA_VERSION
    assert "Repo B Niles Music Worker Wrapper" in operator
    assert "No DAW control" in operator


def test_run_fixture_setlist_outputs_selected_readback(tmp_path, capsys):
    assert run_main([
        "--export-root",
        str(tmp_path),
        "--generated-at",
        FIXED_NOW,
        "--fixture",
        "setlist",
        "--format",
        "json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["selected_fixture"] == "setlist"
    assert payload["selected_request"]["requested_capability"] == "SETLIST_PLANNING"
    assert payload["selected_readback"]["status"] == "FIXTURE_READBACK_READY"


def test_generated_outputs_have_no_secrets_private_bodies_or_contacts(tmp_path):
    payload = wrapper.build_payload(generated_at=FIXED_NOW, selected_fixture="setlist")
    wrapper.write_exports(payload, tmp_path)
    text = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())

    assert "OPENSSH_PRIVATE_KEY_MARKER" not in text
    assert "GMAIL_APP_PASSWORD" not in text
    assert "SMTP_PASSWORD" not in text
    assert "raw lyric body value" not in text.lower()
    assert "private session note body" not in text.lower()
    assert not re.search(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", text)


def test_source_does_not_execute_repo_b_or_media_actions():
    source = Path("repo_b_niles_music_worker_wrapper.py").read_text(encoding="utf-8").lower()
    forbidden = [
        "subprocess.run",
        "from chief_album",
        "import chief_album",
        "from chief_fundo",
        "import chief_fundo",
        "urllib.request",
        "requests.",
        "httpx.",
        "ollama_call",
        "pyautogui",
        "osascript",
        "applescript",
        "selenium",
        "playwright",
        "webbrowser",
        "os.system",
        "shell=true",
    ]
    for token in forbidden:
        assert token not in source

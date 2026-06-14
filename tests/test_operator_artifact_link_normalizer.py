import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "operator_artifact_link_normalizer.py"
SPEC = importlib.util.spec_from_file_location("operator_artifact_link_normalizer", MODULE_PATH)
normalizer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(normalizer)


def test_windows_path_for_wsl_mounted_drive() -> None:
    path = Path("/mnt/e/OpenClaw_Operator_Reports/task/report.md")

    assert normalizer.windows_path_for_wsl_path(path) == r"E:\OpenClaw_Operator_Reports\task\report.md"


def test_source_file_copied_to_operator_report_dir_and_original_remains(tmp_path: Path) -> None:
    source = tmp_path / "worker_cache" / "report.md"
    source.parent.mkdir()
    source.write_text("operator report\n", encoding="utf-8")

    entry = normalizer.maybe_copy_to_operator_reports(
        source,
        "artifact-task",
        report_root=tmp_path / "reports",
    )

    operator_copy = Path(entry["operator_copy_path"])
    assert entry["exists"] is True
    assert entry["safe_to_export"] is True
    assert entry["operator_copy_blocked"] is False
    assert operator_copy.exists()
    assert operator_copy.read_text(encoding="utf-8") == "operator report\n"
    assert source.exists()
    assert source.read_text(encoding="utf-8") == "operator report\n"
    assert entry["operator_copy_windows_path"]
    assert any("Open from Windows" in instruction for instruction in entry["open_instructions"])


def test_manifest_json_parses(tmp_path: Path) -> None:
    source = tmp_path / "worker_cache" / "report.md"
    source.parent.mkdir()
    source.write_text("operator report\n", encoding="utf-8")
    entry = normalizer.maybe_copy_to_operator_reports(
        source,
        "manifest-task",
        report_root=tmp_path / "reports",
    )

    manifest_path = normalizer.write_operator_artifact_manifest(
        [entry],
        task_id="manifest-task",
        report_dir=entry["operator_report_dir"],
        description="Test manifest.",
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "operator_artifact_manifest_v0"
    assert payload["task_id"] == "manifest-task"
    assert payload["artifact_count"] == 1
    assert payload["artifacts"][0]["source_path"] == source.resolve(strict=False).as_posix()
    assert payload["safety"] == {
        "external_api_called": False,
        "originals_moved": False,
        "originals_deleted": False,
        "secret_like_paths_exported": False,
    }


def test_open_instructions_are_written_to_open_me(tmp_path: Path) -> None:
    source = tmp_path / "worker_cache" / "report.md"
    source.parent.mkdir()
    source.write_text("operator report\n", encoding="utf-8")
    entry = normalizer.maybe_copy_to_operator_reports(
        source,
        "open-me-task",
        report_root=tmp_path / "reports",
    )

    open_me = normalizer.write_open_me(
        [entry],
        task_id="open-me-task",
        report_dir=entry["operator_report_dir"],
        description="Operator-facing report.",
    )
    text = open_me.read_text(encoding="utf-8")

    assert "Source WSL path" in text
    assert "Source Windows path" in text
    assert "Operator copy WSL path" in text
    assert "Operator copy Windows path" in text
    assert "copied, not moved" in text


def test_secret_looking_path_is_refused(tmp_path: Path) -> None:
    source = tmp_path / "secrets" / "token.txt"
    source.parent.mkdir()
    source.write_text("dummy\n", encoding="utf-8")

    entry = normalizer.maybe_copy_to_operator_reports(
        source,
        "blocked-task",
        report_root=tmp_path / "reports",
    )

    assert entry["exists"] is True
    assert entry["safe_to_export"] is False
    assert entry["operator_copy_blocked"] is True
    assert entry["blocked_reason"] == "path_looks_like_secret_or_credential_material"
    assert entry["operator_copy_path"] == ""
    assert not (tmp_path / "reports" / "blocked-task" / "token.txt").exists()


def test_missing_file_returns_blocked_result(tmp_path: Path) -> None:
    missing = tmp_path / "missing.md"

    entry = normalizer.maybe_copy_to_operator_reports(
        missing,
        "missing-task",
        report_root=tmp_path / "reports",
    )

    assert entry["exists"] is False
    assert entry["safe_to_export"] is False
    assert entry["operator_copy_blocked"] is True
    assert entry["blocked_reason"] == "source_file_missing"
    assert "Artifact was not copied: source_file_missing." in entry["open_instructions"]


def test_existing_unrelated_report_file_is_not_overwritten(tmp_path: Path) -> None:
    source = tmp_path / "worker_cache" / "report.md"
    source.parent.mkdir()
    source.write_text("new report\n", encoding="utf-8")
    destination_dir = tmp_path / "reports" / "collision-task"
    destination_dir.mkdir(parents=True)
    existing = destination_dir / "report.md"
    existing.write_text("existing report\n", encoding="utf-8")

    entry = normalizer.maybe_copy_to_operator_reports(
        source,
        "collision-task",
        report_root=tmp_path / "reports",
    )

    operator_copy = Path(entry["operator_copy_path"])
    assert operator_copy.exists()
    assert operator_copy.name != "report.md"
    assert operator_copy.read_text(encoding="utf-8") == "new report\n"
    assert existing.read_text(encoding="utf-8") == "existing report\n"

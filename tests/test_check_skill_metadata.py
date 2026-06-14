from __future__ import annotations

from pathlib import Path

from scripts.check_skill_metadata import (
    build_skill_metadata_report,
    check_skill_metadata,
    format_operator_report,
    main,
)


def _write_skill(root: Path, name: str, description: str) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                f"description: {description}",
                "---",
                "",
                "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_report_skill(path: Path, description: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "name: fixture-skill\n"
        f"description: {description}\n"
        "---\n"
        "\n"
        "# Fixture Skill\n",
        encoding="utf-8",
    )


def _write_raw_skill(path: Path, frontmatter_description: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "name: fixture-skill\n"
        f"{frontmatter_description}\n"
        "---\n"
        "\n"
        "# Fixture Skill\n",
        encoding="utf-8",
    )


def test_check_skill_metadata_passes_for_descriptions_within_byte_limit(tmp_path: Path) -> None:
    _write_skill(tmp_path, "valid-skill", "a" * 64)

    result = check_skill_metadata(tmp_path, max_description_bytes=1024)

    assert result["status"] == "pass"
    assert result["loaded_summary"] == {"loaded": 1, "failed": 0, "skipped": 0}
    assert result["description_too_long"] == []
    assert result["cache_is_source_of_truth"] is False


def test_check_skill_metadata_fails_for_over_limit_description(tmp_path: Path) -> None:
    _write_skill(tmp_path, "long-skill", "é" * 600)

    result = check_skill_metadata(tmp_path, max_description_bytes=1024)

    assert result["status"] == "fail"
    assert result["description_too_long"][0]["skill_id"] == "long-skill.SKILL"
    assert result["description_too_long"][0]["reasons"][0]["code"] == "DESCRIPTION_TOO_LONG"


def test_main_returns_nonzero_for_over_limit_description(tmp_path: Path, capsys) -> None:
    _write_skill(tmp_path, "long-skill", "é" * 600)

    exit_code = main(["--skills-path", str(tmp_path)])

    assert exit_code == 1
    assert "fail: checked 1 skills; 1 over 1024 bytes" in capsys.readouterr().out


def test_main_accepts_root_alias_and_no_codex_cache_flag(tmp_path: Path, capsys) -> None:
    _write_skill(tmp_path, "valid-skill", "a" * 64)

    exit_code = main(["--root", str(tmp_path), "--no-codex-cache"])

    assert exit_code == 0
    assert "pass: checked 1 skills; 0 over 1024 bytes" in capsys.readouterr().out


def test_skill_metadata_report_rejects_multibyte_description_over_byte_limit(tmp_path: Path) -> None:
    _write_report_skill(tmp_path / "skills" / "bad" / "SKILL.md", "é" * 513)

    report = build_skill_metadata_report([tmp_path])

    assert report["scanned_skill_files"] == 1
    assert report["issue_count"] == 1
    assert report["issues"][0]["code"] == "DESCRIPTION_TOO_LONG"
    assert report["issues"][0]["description_bytes"] == 1026


def test_skill_metadata_operator_report_names_failing_path(tmp_path: Path) -> None:
    skill_path = tmp_path / "skills" / "bad" / "SKILL.md"
    _write_report_skill(skill_path, "x" * 1025)

    report = build_skill_metadata_report([tmp_path])
    output = format_operator_report(report)

    assert "FAIL: invalid skill metadata found." in output
    assert skill_path.as_posix() in output
    assert "DESCRIPTION_TOO_LONG" in output


def test_skill_metadata_counts_quoted_description_trailing_whitespace(tmp_path: Path) -> None:
    skill_path = tmp_path / "skills" / "quoted" / "SKILL.md"
    description = ("x" * 1024) + " "
    _write_raw_skill(skill_path, f'description: "{description}"')

    report = build_skill_metadata_report([tmp_path])

    assert report["scanned_skill_files"] == 1
    assert report["issue_count"] == 1
    assert report["issues"][0]["code"] == "DESCRIPTION_TOO_LONG"
    assert report["issues"][0]["description_bytes"] == 1025


def test_skill_metadata_preserves_block_scalar_final_newline(tmp_path: Path) -> None:
    skill_path = tmp_path / "skills" / "block" / "SKILL.md"
    _write_raw_skill(skill_path, "description: |\n  " + ("x" * 1024))

    report = build_skill_metadata_report([tmp_path])

    assert report["scanned_skill_files"] == 1
    assert report["issue_count"] == 1
    assert report["issues"][0]["code"] == "DESCRIPTION_TOO_LONG"
    assert report["issues"][0]["description_bytes"] == 1025

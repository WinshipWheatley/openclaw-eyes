from __future__ import annotations

from scripts.check_skill_metadata import (
    build_skill_metadata_report,
    format_operator_report,
)


def _write_skill(path, description: str) -> None:
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


def _write_raw_skill(path, frontmatter_description: str) -> None:
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


def test_skill_metadata_report_rejects_multibyte_description_over_byte_limit(tmp_path):
    _write_skill(tmp_path / "skills" / "bad" / "SKILL.md", "é" * 513)

    report = build_skill_metadata_report([tmp_path])

    assert report["scanned_skill_files"] == 1
    assert report["issue_count"] == 1
    assert report["issues"][0]["code"] == "DESCRIPTION_TOO_LONG"
    assert report["issues"][0]["description_bytes"] == 1026


def test_skill_metadata_operator_report_names_failing_path(tmp_path):
    skill_path = tmp_path / "skills" / "bad" / "SKILL.md"
    _write_skill(skill_path, "x" * 1025)

    report = build_skill_metadata_report([tmp_path])
    output = format_operator_report(report)

    assert "FAIL: invalid skill metadata found." in output
    assert skill_path.as_posix() in output
    assert "DESCRIPTION_TOO_LONG" in output


def test_skill_metadata_counts_quoted_description_trailing_whitespace(tmp_path):
    skill_path = tmp_path / "skills" / "quoted" / "SKILL.md"
    description = ("x" * 1024) + " "
    _write_raw_skill(skill_path, f'description: "{description}"')

    report = build_skill_metadata_report([tmp_path])

    assert report["scanned_skill_files"] == 1
    assert report["issue_count"] == 1
    assert report["issues"][0]["code"] == "DESCRIPTION_TOO_LONG"
    assert report["issues"][0]["description_bytes"] == 1025


def test_skill_metadata_preserves_block_scalar_final_newline(tmp_path):
    skill_path = tmp_path / "skills" / "block" / "SKILL.md"
    _write_raw_skill(skill_path, "description: |\n  " + ("x" * 1024))

    report = build_skill_metadata_report([tmp_path])

    assert report["scanned_skill_files"] == 1
    assert report["issue_count"] == 1
    assert report["issues"][0]["code"] == "DESCRIPTION_TOO_LONG"
    assert report["issues"][0]["description_bytes"] == 1025

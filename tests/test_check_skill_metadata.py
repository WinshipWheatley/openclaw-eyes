from __future__ import annotations

from pathlib import Path

from scripts.check_skill_metadata import check_skill_metadata, main


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

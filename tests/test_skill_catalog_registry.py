from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from skill_loader import SkillLoaderError, load_skills


def _write_skill(
    path: Path,
    *,
    skill_id: str = "valid.music_law_advisory",
    owner_agent: str = "chief",
    tools: tuple[str, ...] = ("chief_musiclaw_brain", "niles_track_registry"),
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tool_lines = "\n".join(f"  - {tool}" for tool in tools)
    path.write_text(
        f"""---
id: {skill_id}
name: Music Law Advisory
description: Advisory music-law skill for publishing, splits, sync, samples, and rights questions.
owner_agent: {owner_agent}
triggers:
  - music law
  - publishing splits
  - sample clearance
tools:
{tool_lines}
authority: advisory_only
capability_needed: multi-step-reasoning
tiers:
  simple: |
    Identify the music-rights question, use the music-law facts, answer plainly, and say this is general information, not legal advice. Consult an entertainment lawyer before taking action.
  rich: |
    Analyze publishing, sync, samples, splits, and live dispute context with edge cases. This is general information, not legal advice. Consult an entertainment lawyer before taking action.
---
# Music Law Advisory

Use the existing Chief music-law brain and read-model facts to answer advisory music-rights questions.
Never send, sign, file, threaten, or take legal action.
""",
        encoding="utf-8",
    )


def test_load_skills_persists_invocable_records_to_catalog(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    _write_skill(skills_root / "music-law-advisory" / "SKILL.md")
    catalog_path = tmp_path / "system_catalog.sqlite3"

    result = load_skills(
        str(skills_root),
        include_patterns=("**/SKILL.md",),
        catalog_path=catalog_path,
        persist_catalog=True,
        strict_mode=True,
    )

    assert result["summary"]["loaded"] == 1
    assert result["summary"]["catalog_written"] == 1
    assert result["catalog_path"] == catalog_path.as_posix()

    con = sqlite3.connect(catalog_path)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT skill_id, owner_agent, triggers_json, tools_json, authority, capability_needed, tiers_json "
        "FROM skills WHERE skill_id = ?",
        ("valid.music_law_advisory",),
    ).fetchone()
    con.close()

    assert row is not None
    assert row["owner_agent"] == "chief"
    assert json.loads(row["triggers_json"]) == ["music law", "publishing splits", "sample clearance"]
    assert json.loads(row["tools_json"]) == ["chief_musiclaw_brain", "niles_track_registry"]
    assert row["authority"] == "advisory_only"
    assert row["capability_needed"] == "multi-step-reasoning"
    tiers = json.loads(row["tiers_json"])
    assert "Consult an entertainment lawyer before taking action." in tiers["simple"]
    assert "Consult an entertainment lawyer before taking action." in tiers["rich"]


def test_load_skills_rejects_unknown_owner_or_tool_before_catalog_write(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    _write_skill(
        skills_root / "bad" / "SKILL.md",
        skill_id="bad.unknown_owner",
        owner_agent="fin",
        tools=("missing_musiclaw_tool",),
    )
    catalog_path = tmp_path / "system_catalog.sqlite3"

    with pytest.raises(SkillLoaderError) as exc:
        load_skills(
            str(skills_root),
            include_patterns=("**/SKILL.md",),
            catalog_path=catalog_path,
            persist_catalog=True,
            strict_mode=True,
        )

    assert exc.value.result is not None
    assert exc.value.result["summary"]["catalog_written"] == 0
    assert exc.value.result["summary"]["runtime_validation_failed"] == 1
    assert "UNKNOWN_OWNER_AGENT" in json.dumps(exc.value.result)
    assert "UNKNOWN_TOOL" in json.dumps(exc.value.result)

    con = sqlite3.connect(catalog_path)
    tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "skills" not in tables
    con.close()

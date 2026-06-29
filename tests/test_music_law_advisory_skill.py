from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from skill_loader import load_skills


SKILL_PATH = Path("skills/music-law-advisory/SKILL.md")
LAWYER_FLAG = "This is general information, not legal advice. Consult an entertainment lawyer before taking action."


def test_music_law_advisory_skill_loads_and_preserves_safety_tiers(tmp_path: Path) -> None:
    catalog_path = tmp_path / "system_catalog.sqlite3"

    result = load_skills(
        str(SKILL_PATH),
        include_patterns=("SKILL.md",),
        catalog_path=catalog_path,
        persist_catalog=True,
        strict_mode=True,
    )

    assert result["summary"]["loaded"] == 1
    assert result["summary"]["catalog_written"] == 1

    skill = result["skills"][0]
    metadata = skill["metadata"]
    assert skill["id"] == "music_law_advisory"
    assert metadata["owner_agent"] == "chief"
    assert metadata["authority"] == "advisory_only"
    assert metadata["capability_needed"] == "multi-step-reasoning"
    assert "chief_musiclaw_brain" in metadata["tools"]
    assert "niles_album_review_packet" in metadata["tools"]
    assert any("publishing" in trigger for trigger in metadata["triggers"])
    assert LAWYER_FLAG in metadata["tiers"]["simple"]
    assert LAWYER_FLAG in metadata["tiers"]["rich"]
    assert "never send" in skill["content"].lower()
    assert "chief_musiclaw_brain._ensure_musiclaw_safety" in skill["content"]

    con = sqlite3.connect(catalog_path)
    con.row_factory = sqlite3.Row
    row = con.execute(
        "SELECT skill_id, authority, tiers_json FROM skills WHERE skill_id = ?",
        ("music_law_advisory",),
    ).fetchone()
    con.close()

    assert row is not None
    assert row["authority"] == "advisory_only"
    tiers = json.loads(row["tiers_json"])
    assert LAWYER_FLAG in tiers["simple"]
    assert LAWYER_FLAG in tiers["rich"]

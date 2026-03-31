from __future__ import annotations

from pathlib import Path

import pytest

from search import search
from skill_loader import SkillLoaderError, load_skills
from skill_vetter import SkillVetterError, vet_skills


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "skills"


def test_skill_pipeline_smoke_end_to_end() -> None:
    loaded = load_skills(str(FIXTURE_ROOT), strict_mode=False)

    assert loaded["summary"] == {"loaded": 2, "failed": 1, "skipped": 0}
    assert [skill["id"] for skill in loaded["skills"]] == [
        "valid.release-planning",
        "weak.quick-note",
    ]
    assert loaded["errors"] == [
        {
            "path": "broken-missing-description.md",
            "reason": "missing required fields: description",
        }
    ]

    vetted = vet_skills(loaded["skills"], strict_mode=False)
    assert vetted["summary"] == {"total": 2, "passed": 1, "failed": 1}
    assert vetted["results"] == [
        {
            "skill_id": "valid.release-planning",
            "status": "pass",
            "reasons": [],
        },
        {
            "skill_id": "weak.quick-note",
            "status": "fail",
            "reasons": [
                {
                    "code": "DESCRIPTION_TOO_SHORT",
                    "message": "description must be at least 20 characters",
                },
                {
                    "code": "CONTENT_TOO_SHORT",
                    "message": "content must contain at least 12 words",
                },
            ],
        },
    ]

    ranked = search(
        "release planning calendar sync",
        skills_path=str(FIXTURE_ROOT),
    )
    assert ranked["summary"] == {"returned": 1, "scanned": 2}
    assert ranked["results"][0]["id"] == "valid.release-planning"
    assert ranked["results"][0]["source_path"] == "valid-release.md"
    assert ranked["results"][0]["score"] > 0
    assert ranked["errors"] == [
        {
            "code": "LOADER_ERROR",
            "message": "Failed to load broken-missing-description.md: missing required fields: description",
        }
    ]


def test_skill_pipeline_strict_failures_are_clear() -> None:
    with pytest.raises(SkillLoaderError) as loader_error:
        load_skills(str(FIXTURE_ROOT), strict_mode=True)

    assert loader_error.value.result == {
        "skills": [
            {
                "id": "valid.release-planning",
                "name": "Release Planning Skill",
                "description": "Deterministic release planning workflow for smoke testing.",
                "source_path": "valid-release.md",
                "content": (
                    "Use this skill to coordinate release planning, schedule checkpoints,\n"
                    "prepare calendar sync notes, and keep deliverables aligned across the stack."
                ),
                "metadata": {"owner": "OpenClaw", "tags": ["release", "planning"]},
            },
            {
                "id": "weak.quick-note",
                "name": "Quick Note",
                "description": "Brief note.",
                "source_path": "weak-note.md",
                "content": "Tiny note only.",
            },
        ],
        "errors": [
            {
                "path": "broken-missing-description.md",
                "reason": "missing required fields: description",
            }
        ],
        "summary": {"loaded": 2, "failed": 1, "skipped": 0},
    }

    loaded = load_skills(str(FIXTURE_ROOT), strict_mode=False)
    with pytest.raises(SkillVetterError) as vetter_error:
        vet_skills(loaded["skills"], strict_mode=True)

    assert vetter_error.value.result["summary"] == {"total": 2, "passed": 1, "failed": 1}
    assert vetter_error.value.result["results"][1]["skill_id"] == "weak.quick-note"

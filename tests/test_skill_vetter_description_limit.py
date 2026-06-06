from __future__ import annotations

from skill_vetter import description_byte_length, vet_skills


def _skill(description: str) -> dict[str, str]:
    return {
        "id": "skill.description-limit",
        "name": "Description Limit Skill",
        "description": description,
        "content": "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu",
    }


def test_description_limit_counts_utf8_bytes_not_characters() -> None:
    description = "é" * 600

    assert len(description) == 600
    assert description_byte_length(description) == 1200

    result = vet_skills([_skill(description)], ruleset={"max_description_bytes": 1024})

    assert result["summary"] == {"total": 1, "passed": 0, "failed": 1}
    assert result["results"][0]["reasons"] == [
        {
            "code": "DESCRIPTION_TOO_LONG",
            "message": "description must be at most 1024 bytes; got 1200",
        }
    ]


def test_description_at_byte_limit_passes() -> None:
    description = "a" * 1024

    result = vet_skills([_skill(description)], ruleset={"max_description_bytes": 1024})

    assert result["summary"] == {"total": 1, "passed": 1, "failed": 0}
    assert result["results"][0]["reasons"] == []

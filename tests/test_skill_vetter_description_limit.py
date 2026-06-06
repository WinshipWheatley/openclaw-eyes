from __future__ import annotations

from skill_vetter import vet_skills


def test_skill_vetter_rejects_description_over_1024_bytes() -> None:
    skill = {
        "id": "overlong.description",
        "name": "Overlong Description",
        "description": "x" * 1025,
        "source_path": "overlong.md",
        "content": (
            "This skill body has enough words to isolate description length "
            "validation from the existing minimum content words rule."
        ),
    }

    vetted = vet_skills([skill], strict_mode=False)

    assert vetted["summary"] == {"total": 1, "passed": 0, "failed": 1}
    assert vetted["results"] == [
        {
            "skill_id": "overlong.description",
            "status": "fail",
            "reasons": [
                {
                    "code": "DESCRIPTION_TOO_LONG",
                    "message": "description must be at most 1024 UTF-8 bytes",
                }
            ],
        }
    ]


def test_skill_vetter_rejects_multibyte_description_over_1024_bytes() -> None:
    skill = {
        "id": "overlong.description.bytes",
        "name": "Overlong Description Bytes",
        "description": "é" * 513,
        "source_path": "overlong.md",
        "content": (
            "This skill body has enough words to isolate description byte "
            "validation from the existing minimum content words rule."
        ),
    }

    vetted = vet_skills([skill], strict_mode=False)

    assert vetted["summary"] == {"total": 1, "passed": 0, "failed": 1}
    assert vetted["results"] == [
        {
            "skill_id": "overlong.description.bytes",
            "status": "fail",
            "reasons": [
                {
                    "code": "DESCRIPTION_TOO_LONG",
                    "message": "description must be at most 1024 UTF-8 bytes",
                }
            ],
        }
    ]


def test_skill_vetter_supports_legacy_max_description_length_ruleset_alias() -> None:
    skill = {
        "id": "legacy.alias.bytes",
        "name": "Legacy Alias Bytes",
        "description": "é" * 20,
        "source_path": "legacy-alias.md",
        "content": (
            "This skill body has enough words to isolate legacy ruleset alias "
            "validation from the existing minimum content words rule."
        ),
    }

    vetted = vet_skills(
        [skill],
        ruleset={"max_description_length": 39},
        strict_mode=False,
    )

    assert vetted["summary"] == {"total": 1, "passed": 0, "failed": 1}
    assert vetted["results"] == [
        {
            "skill_id": "legacy.alias.bytes",
            "status": "fail",
            "reasons": [
                {
                    "code": "DESCRIPTION_TOO_LONG",
                    "message": "description must be at most 39 UTF-8 bytes",
                }
            ],
        }
    ]

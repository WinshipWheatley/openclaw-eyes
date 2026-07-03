from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "requirements.lock"
SOURCES = (
    ROOT / "requirements-gmail-readonly.txt",
    ROOT / "requirements-openclaw-api.txt",
    ROOT / "requirements-dev.txt",
)


def _requirement_names(path: Path) -> set[str]:
    names: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        names.add(re.split(r"[<=>[; ]", line, maxsplit=1)[0].lower())
    return names


def _lock_requirement_blocks(text: str) -> dict[str, str]:
    blocks: dict[str, str] = {}
    current_name = ""
    current_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if raw_line[:1].strip() and "==" in line:
            if current_name:
                blocks[current_name] = "\n".join(current_lines)
            current_name = re.split(r"==", line, maxsplit=1)[0].lower()
            current_lines = [line]
            continue
        if current_name:
            current_lines.append(line)
    if current_name:
        blocks[current_name] = "\n".join(current_lines)
    return blocks


def test_requirements_lock_is_hash_pinned_for_all_current_inputs() -> None:
    lock_text = LOCK.read_text(encoding="utf-8")
    blocks = _lock_requirement_blocks(lock_text)

    expected_top_level = set().union(*(_requirement_names(path) for path in SOURCES))
    assert expected_top_level <= set(blocks)

    for name, block in blocks.items():
        assert "==" in block, f"{name} is not exactly pinned"
        assert "--hash=sha256:" in block, f"{name} is missing a sha256 hash"


def test_dependency_hygiene_docs_explain_hash_locked_install() -> None:
    doc = (ROOT / "docs" / "operations" / "DEPENDENCY_HYGIENE.md").read_text(encoding="utf-8")

    assert "requirements.lock" in doc
    assert "--require-hashes" in doc

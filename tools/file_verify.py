from __future__ import annotations

import re
from pathlib import Path


def _extract_candidate_path(text: str) -> str | None:
    quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', text)
    for left, right in quoted:
        candidate = (left or right).strip()
        if candidate:
            return candidate

    absolute = re.search(r'(/[^\s,;:]+)', text)
    if absolute:
        return absolute.group(1).strip()

    return None


def answer_file_verification(text: str) -> str:
    candidate = _extract_candidate_path(text)
    if not candidate:
        return "I can verify a file or path if you give me the exact path."

    path = Path(candidate).expanduser()
    if path.exists():
        kind = "folder" if path.is_dir() else "file"
        return f"Confirmed. {path} exists, and it's a {kind}."

    return f"Confirmed. {path} does not exist from here."

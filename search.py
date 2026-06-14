"""
search.py

Find relevant skills and/or source snippets for a user query using a deterministic
ranking pipeline over loaded content.
Implements the env-001-spec-tools search specification.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

from skill_loader import load_skills


class SearchError(Exception):
    """Base exception for search errors."""


def search(
    query: str,
    scope: Optional[str] = None,
    limit: Optional[int] = None,
    filters: Optional[Dict[str, Any]] = None,
    skills_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search for relevant skills and/or source snippets.

    Args:
        query: Search text from the caller
        scope: Search target ('skills', 'docs', or 'all'). Default: 'skills'
        limit: Maximum number of results to return. Default: 10
        filters: Key-value constraints (e.g., tag/path filters)
        skills_path: Root directory to scan for skills. Default: current directory

    Returns:
        Dictionary with:
        - results: List of ranked search hits
        - summary: Counts for returned and scanned
        - errors: Optional list of query/processing errors

    Raises:
        SearchError: For validation or processing errors in strict contexts
    """
    if scope is None:
        scope = "skills"
    if limit is None:
        limit = 10
    if filters is None:
        filters = {}
    if skills_path is None:
        skills_path = os.getcwd()

    errors = []

    if not query or not query.strip():
        return {
            "results": [],
            "summary": {"returned": 0, "scanned": 0},
            "errors": [{"code": "INVALID_QUERY", "message": "query cannot be empty or whitespace-only"}],
        }

    valid_scopes = ["skills", "docs", "all"]
    if scope not in valid_scopes:
        errors.append(
            {
                "code": "INVALID_SCOPE",
                "message": f"scope must be one of {valid_scopes}, got: {scope}",
            }
        )
        scope = "skills"

    query_normalized = query.strip().lower()
    query_terms = _tokenize(query_normalized)

    searchable_items = []
    if scope in ["skills", "all"]:
        try:
            loaded = load_skills(skills_path, strict_mode=False)
            for skill in loaded["skills"]:
                searchable_items.append(
                    {
                        "type": "skill",
                        "data": skill,
                    }
                )
            for error in loaded.get("errors", []):
                errors.append(
                    {
                        "code": "LOADER_ERROR",
                        "message": f"Failed to load {error['path']}: {error['reason']}",
                    }
                )
        except Exception as exc:
            errors.append(
                {
                    "code": "LOAD_FAILED",
                    "message": f"Failed to load skills: {exc}",
                }
            )

    if filters:
        searchable_items = _apply_filters(searchable_items, filters)

    scanned_count = len(searchable_items)
    scored_results = []
    for item in searchable_items:
        score = _score_item(item, query_terms, query_normalized)
        if score > 0:
            scored_results.append(_format_result(item, score, query_normalized))

    scored_results.sort(key=lambda result: (-result["score"], result["source_path"]))
    limited_results = scored_results[:limit]

    response = {
        "results": limited_results,
        "summary": {
            "returned": len(limited_results),
            "scanned": scanned_count,
        },
    }

    if errors:
        response["errors"] = errors

    return response


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"\w+", text)
    return [token for token in tokens if token]


def _score_item(item: Dict[str, Any], query_terms: List[str], query_text: str) -> float:
    if item["type"] == "skill":
        skill = item["data"]
        searchable_text = " ".join(
            [
                skill.get("name", ""),
                skill.get("description", ""),
                skill.get("content", ""),
            ]
        ).lower()

        term_matches = 0
        for term in query_terms:
            term_matches += searchable_text.count(term)

        phrase_bonus = 0.5 if query_text in searchable_text else 0.0
        name_match_bonus = 0.0
        name_lower = skill.get("name", "").lower()
        if query_text in name_lower:
            name_match_bonus = 1.0
        elif any(term in name_lower for term in query_terms):
            name_match_bonus = 0.3

        base_score = term_matches / max(len(query_terms), 1)
        return base_score + phrase_bonus + name_match_bonus

    return 0.0


def _format_result(item: Dict[str, Any], score: float, query_text: str) -> Dict[str, Any]:
    if item["type"] == "skill":
        skill = item["data"]
        excerpt = _generate_excerpt(
            skill.get("description", "") or skill.get("content", ""),
            query_text,
            max_length=150,
        )

        result = {
            "id": skill["id"],
            "type": "skill",
            "source_path": skill["source_path"],
            "score": round(score, 4),
            "excerpt": excerpt,
        }

        if "metadata" in skill and skill["metadata"]:
            result["metadata"] = skill["metadata"]

        return result

    return {
        "id": "unknown",
        "type": item["type"],
        "source_path": "",
        "score": round(score, 4),
        "excerpt": "",
    }


def _generate_excerpt(text: str, query_text: str, max_length: int = 150) -> str:
    if not text:
        return ""

    text = text.strip()
    text_lower = text.lower()
    query_pos = text_lower.find(query_text)

    if query_pos >= 0:
        start = max(0, query_pos - 50)
        end = min(len(text), query_pos + len(query_text) + 50)
        excerpt = text[start:end]
        if start > 0:
            excerpt = "..." + excerpt
        if end < len(text):
            excerpt = excerpt + "..."
    else:
        excerpt = text[:max_length]
        if len(text) > max_length:
            excerpt = excerpt + "..."

    return excerpt


def _apply_filters(items: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not filters:
        return items

    filtered = []
    for item in items:
        include = True

        if "path" in filters:
            path_pattern = filters["path"]
            if item["type"] == "skill":
                source_path = item["data"].get("source_path", "")
                if path_pattern not in source_path:
                    include = False

        if include:
            filtered.append(item)

    return filtered


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python search.py <query> [--scope <scope>] [--limit <limit>] [--path <skills_path>]")
        print("\nSearch for relevant skills and/or source snippets.")
        print("\nOptions:")
        print("  --scope <scope>    Search target: skills, docs, or all (default: skills)")
        print("  --limit <limit>    Maximum results to return (default: 10)")
        print("  --path <path>      Root directory for skills (default: current directory)")
        sys.exit(1)

    query = sys.argv[1]
    scope = None
    limit = None
    skills_path = None

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--scope" and i + 1 < len(sys.argv):
            scope = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == "--path" and i + 1 < len(sys.argv):
            skills_path = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    try:
        result = search(query, scope=scope, limit=limit, skills_path=skills_path)
        print(json.dumps(result, indent=2))
        if result.get("errors"):
            sys.exit(1)
    except SearchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

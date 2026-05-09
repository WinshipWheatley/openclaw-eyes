#!/usr/bin/env python3
"""Evidence Packet v0 Generator.

A read-only, deterministic evidence tool that turns a natural-language topic
into a bounded packet from the existing Mac Watch index.

It strictly adheres to Operator Anti-Drift and Authority doctrines:
- Mac Watch files are support material, not canonical authority.
- No moves, renames, deletes, or writes on the Mac.
- No provider/model calls, no embeddings, no SQLite.
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX_PATH = ROOT / "reports" / "mac_watch_index" / "MAC_WATCH_MARKDOWN_INDEX.json"
DEFAULT_OUT_DIR = Path("/tmp/openclaw_evidence")

STOP_WORDS = {
    "what", "should", "we", "for", "are", "but", "to", "which",
    "docs", "feed", "a", "the", "of", "in", "and", "is", "it", "on", "with",
    "this", "that", "these", "those", "how", "do", "can", "you", "me", "my",
    "i", "or", "as", "at", "be", "by", "from", "an", "was"
}

def is_safe_path(path_str: str) -> bool:
    """Reject unsafe paths to prevent injection or escape."""
    if not path_str:
        return False
    if path_str.startswith("/"):
        return False
    if path_str.startswith("-"):
        return False
    if ".." in path_str:
        return False
    for char in ';&|$`\\<>*?[]{}()\n\r':
        if char in path_str:
            return False
    return True

def tokenize_topic(topic: str) -> list[str]:
    """Deterministically tokenize the natural language topic."""
    lowered = topic.lower()
    # Replace non-alphanumeric with space
    cleaned = re.sub(r'[^a-z0-9]', ' ', lowered)
    tokens = [word for word in cleaned.split() if word and word not in STOP_WORDS and len(word) > 1]
    return tokens

def score_file(info: dict, tokens: list[str]) -> tuple[int, list[str]]:
    """Rank the file based on token matches in various fields."""
    score = 0
    matched_fields = set()
    
    rel_path = str(info.get("relative_path", "")).lower()
    first_heading = str(info.get("first_heading", "")).lower()
    headings = [str(h).lower() for h in info.get("headings", [])]
    excerpt = str(info.get("excerpt_preview", "")).lower()
    tags = [str(t).lower() for t in info.get("tags", [])]
    family = str(info.get("group", "")).lower()

    for token in tokens:
        if token in first_heading or any(token in h for h in headings):
            score += 10
            matched_fields.add("headings")
        if token in rel_path:
            score += 5
            matched_fields.add("path")
        if token in family:
            score += 5
            matched_fields.add("family")
        if token in tags:
            score += 5
            matched_fields.add("tags")
        if token in excerpt:
            score += 1
            matched_fields.add("excerpt")

    # Boosts based on classification metadata
    if info.get("group") == "active packets and rails":
        score += 15
        matched_fields.add("active_group_boost")
    if info.get("freshness_class") in ("fresh", "recent"):
        score += 5
        matched_fields.add("freshness_boost")
    if info.get("authority_guess") not in ("none", "", None):
        score += 5
        matched_fields.add("authority_boost")

    # Hardcoded deterministic boosts for critical roadmap patterns
    if "active handoff" in first_heading or "active_handoff" in rel_path or "active handoff" in rel_path:
        score += 20
        matched_fields.add("active_handoff_boost")
    if "rail_map" in rel_path or "rail map" in first_heading or "rail_map" in first_heading or "source_set_index" in rel_path:
        score += 20
        matched_fields.add("rail_map_boost")
    if "packet 07" in first_heading or "07_operator_harness" in rel_path:
        score += 20
        matched_fields.add("packet_07_boost")

    return score, sorted(list(matched_fields))

def fetch_file_content(relative_path: str) -> str:
    """Safely fetch file content via SSH alias 'mac'."""
    if not is_safe_path(relative_path):
        return "ERROR: Path failed safety check."
    
    remote_path = f"OpenClaw_Watch/{relative_path}"
    # Quote the path to ensure spaces and other allowed chars are handled safely by the remote shell
    safe_remote_path = shlex.quote(remote_path)
    
    try:
        res = subprocess.run(
            ["ssh", "mac", f"cat -- {safe_remote_path}"],
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout
    except subprocess.CalledProcessError as e:
        return f"ERROR: Failed to fetch file content. {e.stderr.strip()}"
    except Exception as e:
        return f"ERROR: Exception during fetch: {str(e)}"

def generate_packet(topic: str, index_path: str, out_dir: str, max_files: int):
    """Generate the bounded evidence packet."""
    index_file = Path(index_path)
    if not index_file.is_file():
        print(f"Error: Index file not found at {index_path}")
        sys.exit(1)

    try:
        with open(index_file, "r", encoding="utf-8") as f:
            index_data = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in index file {index_path}")
        sys.exit(1)

    files = index_data.get("files", [])
    if not files:
        print("Warning: No files found in index.")
    
    # Enforce hard cap
    actual_max = min(max_files, 12)
    
    tokens = tokenize_topic(topic)
    scored_files = []
    
    # Validate against known paths in index
    known_paths = {str(f.get("relative_path", "")) for f in files}

    for f in files:
        score, matched_fields = score_file(f, tokens)
        if score > 0:
            f_copy = dict(f)
            f_copy["score"] = score
            f_copy["matched_fields"] = matched_fields
            scored_files.append(f_copy)

    # Sort descending by score, then alphabetically by path for determinism
    scored_files.sort(key=lambda x: (-x["score"], x.get("relative_path", "")))
    
    selected_files = scored_files[:actual_max]
    
    packet_files = []
    for f in selected_files:
        rel_path = str(f.get("relative_path", ""))
        if rel_path not in known_paths or not is_safe_path(rel_path):
            continue
            
        content = fetch_file_content(rel_path)
        
        packet_files.append({
            "source_path": rel_path,
            "title": f.get("first_heading", ""),
            "tags": f.get("tags", []),
            "authority_guess": f.get("authority_guess", "none"),
            "freshness_class": f.get("freshness_class", "stale"),
            "family_guess": f.get("group", "unknowns"),
            "needs_deeper_review": f.get("needs_deeper_review", False),
            "why_included": f"Matched keywords {tokens} in {', '.join(f.get('matched_fields', []))}.",
            "matched_fields": f.get("matched_fields", []),
            "content": content[:5000] # bounded to safe max
        })

    # Prepare output
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    topic_slug = re.sub(r'[^a-z0-9]', '_', topic.lower()).strip('_')[:30]
    if not topic_slug:
        topic_slug = "topic"
        
    out_path_dir = Path(out_dir)
    out_path_dir.mkdir(parents=True, exist_ok=True)
    
    json_path = out_path_dir / f"PACKET_{timestamp}_{topic_slug}.json"
    md_path = out_path_dir / f"PACKET_{timestamp}_{topic_slug}.md"
    
    packet_data = {
        "topic": topic,
        "tokens": tokens,
        "timestamp": timestamp,
        "selected_count": len(packet_files),
        "banner": "Mac Watch support material only. Not canonical repo authority.",
        "files": packet_files
    }
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(packet_data, f, indent=2)
        
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Evidence Packet: {topic}\n\n")
        f.write(f"> **AUTHORITY BANNER:** {packet_data['banner']}\n\n")
        
        for pf in packet_files:
            f.write(f"## {pf['source_path']}\n")
            f.write(f"- **Title:** {pf['title']}\n")
            f.write(f"- **Tags:** {', '.join(pf['tags'])}\n")
            f.write(f"- **Authority:** {pf['authority_guess']}\n")
            f.write(f"- **Freshness:** {pf['freshness_class']}\n")
            f.write(f"- **Family:** {pf['family_guess']}\n")
            if pf['needs_deeper_review'] or pf['freshness_class'] == 'stale':
                f.write(f"- **WARNING:** Needs deeper review or is stale.\n")
            f.write(f"- **Why Included:** {pf['why_included']}\n\n")
            f.write("```markdown\n")
            f.write(pf['content'])
            if not pf['content'].endswith("\n"):
                f.write("\n")
            f.write("```\n\n")

    print(f"Generated packet for topic: '{topic}'")
    print(f"Selected {len(packet_files)} files.")
    print(f"JSON output: {json_path}")
    print(f"Markdown output: {md_path}")

def main():
    parser = argparse.ArgumentParser(description="Evidence Packet v0 Generator")
    parser.add_argument("--topic", required=True, help="Natural language topic")
    parser.add_argument("--index-path", default=str(DEFAULT_INDEX_PATH), help="Path to index JSON")
    parser.add_argument("--max-files", type=int, default=10, help="Bounded top N files")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output directory")
    
    args = parser.parse_args()
    
    generate_packet(args.topic, args.index_path, args.out_dir, args.max_files)

if __name__ == "__main__":
    main()

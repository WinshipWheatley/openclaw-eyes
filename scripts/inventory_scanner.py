import os
import argparse
import json
from pathlib import Path
from datetime import datetime

ROOT_REGISTRY = {
    "test_fixture_01": {
        "root_path": "tests/fixtures/dummy_drive_root",
        "drive_label": "Synthetic Test Drive",
        "sensitivity_class": "non_sensitive",
        "max_depth": 3,
        "allowed_extensions": [".md", ".txt", ".json"]
    }
}

EXCLUDED_NAMES = {
    ".git", ".env", "node_modules", "__pycache__", ".cache", 
    ".pytest_cache", ".google-secrets", ".ssh", ".pii_vault.enc"
}

def is_excluded(path: Path):
    if path.name.startswith("."):
        return True
    if path.name in EXCLUDED_NAMES:
        return True
    if "secret" in path.name.lower() or "credential" in path.name.lower():
        return True
    return False

def scan_root(root_id, dry_run=False):
    if root_id not in ROOT_REGISTRY:
        raise ValueError(f"Unknown root_id: {root_id}")

    config = ROOT_REGISTRY[root_id]
    root_path = Path(config["root_path"])
    results = []

    def walk(current_path, depth):
        if depth > config["max_depth"]:
            return
        
        for item in current_path.iterdir():
            if is_excluded(item):
                continue
            
            if item.is_dir():
                walk(item, depth + 1)
            elif item.is_file():
                if item.suffix not in config["allowed_extensions"]:
                    continue
                
                stat = item.stat()
                results.append({
                    "root_id": root_id,
                    "drive_label": config["drive_label"],
                    "absolute_path": str(item.absolute()),
                    "relative_path": str(item.relative_to(root_path)),
                    "file_name": item.name,
                    "extension": item.suffix,
                    "file_type_guess": "text" if item.suffix in [".txt", ".md"] else "json",
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "sensitivity_guess": config["sensitivity_class"],
                    "ingest_eligibility": "eligible_metadata_only",
                    "exclusion_reason": None
                })

    walk(root_path, 1)
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data = scan_root(args.root_id, args.dry_run)
    print(json.dumps(data, indent=2))

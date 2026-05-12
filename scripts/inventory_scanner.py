import argparse
import json
import hashlib
from pathlib import Path
from datetime import datetime
from business_ops_ledger import record_file_inventory_entry, init_business_ops_ledger

ROOT_REGISTRY = {
    "test_fixture_01": {
        "root_path": "tests/fixtures/dummy_drive_root",
        "drive_label": "Synthetic Test Drive",
        "root_category": "synthetic_fixture",
        "sensitivity_class": "non_sensitive",
        "scan_mode": "metadata_only",
        "max_depth": 3,
        "allowed_extensions": [".md", ".txt", ".json"],
        "excluded_patterns": [],
        "requires_operator_approval": False,
        "content_read_allowed": False,
        "hashing_allowed": False
    },
    "openclaw_docs_dryrun_01": {
        "root_path": "/home/openclaw/docs/operations",
        "drive_label": "OpenClaw Operations Docs",
        "root_category": "project_drive",
        "sensitivity_class": "operational",
        "scan_mode": "metadata_only",
        "max_depth": 1,
        "allowed_extensions": [".md"],
        "excluded_patterns": [],
        "requires_operator_approval": True,
        "content_read_allowed": False,
        "hashing_allowed": False
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

def validate_root_config(config, confirm_real_root=False, dry_run=False, db_path=None):
    if config["scan_mode"] != "metadata_only":
        raise ValueError(f"Scan mode {config['scan_mode']} is not permitted.")
    if config["content_read_allowed"]:
        raise ValueError("Content reading is not permitted.")
    if config["hashing_allowed"]:
        raise ValueError("Hashing is not permitted.")

    if config.get("requires_operator_approval", True):
        if not confirm_real_root:
            raise ValueError(f"Root requires operator approval. Please use --confirm-real-root.")
        if not dry_run or db_path:
            raise ValueError("Real roots can only be scanned in --dry-run mode without persistence.")

def scan_root(root_id, dry_run=False, db_path=None, confirm_real_root=False):
    if root_id not in ROOT_REGISTRY:
        raise ValueError(f"Unknown root_id: {root_id}")

    config = ROOT_REGISTRY[root_id]
    validate_root_config(config, confirm_real_root, dry_run, db_path)

    root_path = Path(config["root_path"])

    results = []

    if db_path and not dry_run:
        init_business_ops_ledger(db_path)

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
                rel_path = item.relative_to(root_path)
                file_id = hashlib.sha256(f"{root_id}:{rel_path}".encode()).hexdigest()[:16]

                meta = {
                    "file_id": file_id,
                    "root_id": root_id,
                    "drive_label": config["drive_label"],
                    "absolute_path": str(item.absolute()),
                    "relative_path": str(rel_path),
                    "file_name": item.name,
                    "extension": item.suffix,
                    "file_type_guess": "text" if item.suffix in [".txt", ".md"] else "json",
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "content_hash": None,
                    "sensitivity_guess": config["sensitivity_class"],
                    "ingest_eligibility": "eligible_metadata_only",
                    "exclusion_reason": None
                }

                if db_path and not dry_run:
                    record_file_inventory_entry(**meta, db_path=db_path)

                results.append(meta)

    walk(root_path, 1)
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--db")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--confirm-real-root", action="store_true")
    args = parser.parse_args()

    if args.replace and not args.db:
        print("Error: --replace requires --db")
        exit(1)

    if args.replace:
        from business_ops_ledger import delete_file_inventory_by_root
        delete_file_inventory_by_root(args.root_id, args.db)

    data = scan_root(args.root_id, args.dry_run, args.db, args.confirm_real_root)
    if not args.db:
        print(json.dumps(data, indent=2))

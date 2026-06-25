import sqlite3
import hashlib
import json
from pathlib import Path
from typing import Dict, Any, Tuple

class TamperError(Exception):
    pass

class ResolverError(Exception):
    pass

def resolve_current_read_model(
    conn: sqlite3.Connection,
    governed_root: Path,
    read_model_domain: str
) -> Tuple[Path, Dict[str, Any]]:
    """
    T013: Approved-run resolver and tamper verification.
    Looks up the active read model for a given domain, validates its hash
    against the DB and the file bytes on disk, and returns the (path, payload).
    """
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT current_run_id FROM ar_published_read_models WHERE read_model_domain = ?",
        (read_model_domain,)
    ).fetchone()
    
    if not row or not row["current_run_id"]:
        raise ResolverError(f"No active read model for domain {read_model_domain}")
        
    run_id = row["current_run_id"]
    
    run_row = conn.execute(
        "SELECT status, published_artifact_hash, published_artifact_path FROM ar_materialization_runs WHERE run_id = ?",
        (run_id,)
    ).fetchone()
    
    if not run_row:
        raise ResolverError(f"Run {run_id} not found")
        
    if run_row["status"] != "published":
        raise ResolverError(f"Run {run_id} is not published")
        
    expected_hash = run_row["published_artifact_hash"]
    if not expected_hash:
        raise ResolverError(f"Run {run_id} is missing published_artifact_hash")
        
    # Using relative path from governed_root, but wait, published_artifact_path might be absolute or relative?
    # ar_counterparty_contact_operations.py materialization_run_publish accepts it as a string.
    # We should assume it's relative if we are passing governed_root. Wait, let's check what `publish_read_model` does.
    # It passes: str(governed_artifact_path(rel_path, governed_root))
    # Wait, governed_artifact_path returns `governed_root / rel_path`, which is an ABSOLUTE path if governed_root is absolute!
    # So `run_row["published_artifact_path"]` is the full path.
    file_path = Path(run_row["published_artifact_path"])
    
    # Just to be safe, if it was stored as relative we can do `governed_root / path`.
    if not file_path.is_absolute():
        file_path = governed_root / file_path
    
    if not file_path.exists():
        raise TamperError(f"Artifact file missing: {file_path}")
        
    if not file_path.is_file() or file_path.is_symlink():
        raise TamperError(f"Artifact is not a regular file: {file_path}")
        
    # Verify hash of file bytes
    verify_sha256 = hashlib.sha256()
    with file_path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            verify_sha256.update(chunk)
            
    actual_hash = verify_sha256.hexdigest()
    if actual_hash != expected_hash:
        raise TamperError(f"Tamper detected! File hash {actual_hash} does not match expected {expected_hash}")
        
    # Parse payload
    try:
        payload = json.loads(file_path.read_text("utf-8"))
    except json.JSONDecodeError as e:
        raise TamperError(f"Artifact is not valid JSON: {e}") from e
        
    return file_path, payload

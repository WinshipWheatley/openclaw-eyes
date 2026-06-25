import hashlib
import os
import uuid
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Union

from ar_counterparty_contact_operations import (
    materialization_run_start,
    materialization_add_evidence,
    materialization_run_fail,
    materialization_run_publish,
    materialization_set_current_read_model,
    object_path,
    governed_artifact_path,
    stable_payload_hash,
    stable_json
)

class MaterializationError(Exception):
    pass

def atomically_write_payload(payload_str: str, target_dir: Path, payload_hash: str) -> str:
    """
    Atomically writes a string payload into governed content-addressed storage.
    Returns the relative path object_path(payload_hash).
    """
    rel_path = object_path(payload_hash)
    final_path = governed_artifact_path(rel_path, target_dir)
    
    # Ensure target directory exists
    target_d = target_dir.resolve()
    target_d.mkdir(parents=True, exist_ok=True)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 1. Idempotent check
    if final_path.exists():
        if not final_path.is_file() or final_path.is_symlink():
            raise MaterializationError(f"Existing target is not a regular file: {final_path}")
            
        verify_sha256 = hashlib.sha256()
        with final_path.open('rb') as vf:
            while True:
                chunk = vf.read(65536)
                if not chunk:
                    break
                verify_sha256.update(chunk)
        if verify_sha256.hexdigest() != payload_hash:
            raise MaterializationError(f"Existing file corrupted: hash {verify_sha256.hexdigest()} does not match name {payload_hash}")
        return rel_path

    # 2. Open source and write to a temporary file
    temp_filename = f".import-{uuid.uuid4().hex}.tmp"
    temp_path = target_d / temp_filename
    
    try:
        dst_fd = os.open(str(temp_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
        try:
            with open(dst_fd, 'wb', closefd=False) as dst_file:
                dst_file.write(payload_str.encode("utf-8"))
                dst_file.flush()
                os.fsync(dst_file.fileno())
        finally:
            os.close(dst_fd)
            
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise MaterializationError(f"Failed to write payload: {e}") from e

    # 3. Atomic replace
    try:
        os.replace(str(temp_path), str(final_path))
    except Exception as e:
        temp_path.unlink(missing_ok=True)
        raise MaterializationError(f"Atomic replace failed: {e}") from e
        
    # 4. Parent directory fsync (POSIX)
    try:
        dir_fd = os.open(str(target_d), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        # Ignore dir fsync errors on platforms where it's unsupported
        pass
        
    return rel_path


def publish_read_model(
    conn: sqlite3.Connection,
    governed_root: Union[str, Path],
    read_model_domain: str,
    generator_id: str,
    generator_version: str,
    schema_version: str,
    freshness_cutoff: str,
    evidence_ids: List[str],
    generator_fn: Callable[[], Dict[str, Any]]
) -> str:
    """
    Executes a complete materialization run: 
    registers it in DB, generates the payload, writes it atomically,
    and publishes it as the current read model.
    Returns the run_id.
    """
    governed_root = Path(governed_root)
    run_id = "run:" + uuid.uuid4().hex
    run_start_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    
    # 1. Start materialization run in DB
    try:
        materialization_run_start(
            conn, run_id, generator_id, generator_version, schema_version, freshness_cutoff, run_start_ts
        )
        for ev_id in evidence_ids:
            materialization_add_evidence(conn, run_id, ev_id, "used")
    except Exception as e:
        # If DB inserts fail, we can't record the run. Just raise.
        raise MaterializationError(f"Failed to start materialization run: {e}") from e
        
    # 2. Generate payload
    try:
        payload = generator_fn()
    except Exception as e:
        run_fail_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            materialization_run_fail(conn, run_id, run_fail_ts, "GENERATOR_ERROR", str(e))
        except Exception as fail_e:
            pass # Suppress secondary errors during fail recording
        raise MaterializationError(f"Generator failed: {e}") from e
        
    # 3. Hash and serialize
    try:
        payload_hash = stable_payload_hash(payload)
        payload_str = stable_json(payload)
    except Exception as e:
        run_fail_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        materialization_run_fail(conn, run_id, run_fail_ts, "SERIALIZATION_ERROR", str(e))
        raise MaterializationError(f"Failed to serialize payload: {e}") from e
        
    # 4. Atomically write to storage
    try:
        rel_path = atomically_write_payload(payload_str, governed_root, payload_hash)
    except Exception as e:
        run_fail_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        materialization_run_fail(conn, run_id, run_fail_ts, "STORAGE_ERROR", str(e))
        raise MaterializationError(f"Failed to write payload: {e}") from e
        
    # 5. Publish in DB
    run_pub_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        materialization_run_publish(
            conn, run_id, run_pub_ts, payload_hash, str(governed_artifact_path(rel_path, governed_root)), payload_hash
        )
        materialization_set_current_read_model(
            conn, read_model_domain, run_id, run_pub_ts
        )
    except Exception as e:
        # Payload exists but DB publish failed
        run_fail_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            materialization_run_fail(conn, run_id, run_fail_ts, "PUBLISH_ERROR", str(e))
        except Exception:
            pass
        raise MaterializationError(f"Failed to publish materialization run: {e}") from e

    return run_id

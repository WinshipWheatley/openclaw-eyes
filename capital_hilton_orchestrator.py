import sqlite3
from pathlib import Path
from typing import List, Union

from materialization_publisher import publish_read_model
from capital_hilton_payload_builder import build_capital_hilton_read_model

def orchestrate_capital_hilton_read_model(
    conn: sqlite3.Connection,
    governed_root: Union[str, Path],
    freshness_cutoff: str,
    evidence_ids: List[str]
) -> str:
    """
    T012: Orchestrates the generation and publication of the Capital Hilton read-model.
    Connects the Capital Hilton payload builder to the materialization publisher.
    Returns the new run_id.
    """
    def generator_fn():
        return build_capital_hilton_read_model(conn)
        
    return publish_read_model(
        conn=conn,
        governed_root=governed_root,
        read_model_domain="capital_hilton_ar_context",
        generator_id="capital_hilton_payload_builder",
        generator_version="1.0.0",
        schema_version="AR_CAPITAL_HILTON_READ_MODEL_V0",
        freshness_cutoff=freshness_cutoff,
        evidence_ids=evidence_ids,
        generator_fn=generator_fn
    )

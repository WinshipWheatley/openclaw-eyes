import os
import sys
import json
import sqlite3
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

# Add CWD to sys.path to allow importing from root
sys.path.append(os.getcwd())

# --- Configuration ---
DEFAULT_DB_PATH = ".openclaw/business_ops/ledger.sqlite"

class AgentContextAssembler:
    """
    Deterministic, read-only context substrate assembler v0.
    Generates context packets for agent orientation without execution authority.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_PATH

    def get_git_head(self) -> str:
        """Returns the current git HEAD commit hash."""
        try:
            return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        except Exception:
            return "unknown"

    def get_verified_receipt_rows(self) -> List[Dict[str, Any]]:
        """
        Queries the ledger for SQLITE_VERIFIED receipt instances.
        Includes action_intent_gate_receipt, approval_request_record, approval_log_entry,
        orientation_snapshot_receipt, and test_proof_receipt.
        """
        if not os.path.exists(self.db_path):
            return []

        receipts = []
        try:
            # Use URI for read-only
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            cursor = conn.cursor()

            # Query for the SQLITE_VERIFIED receipt types
            cursor.execute("""
                SELECT ts, event_type, operator_visible_summary
                FROM events
                WHERE event_type IN (
                    'action_intent_gate_receipt',
                    'approval_request_record',
                    'approval_log_entry',
                    'orientation_snapshot_receipt',
                    'test_proof_receipt'
                )
                ORDER BY ts DESC LIMIT 10
            """)
            rows = cursor.fetchall()
            conn.close()

            for ts, etype, summary in rows:
                receipt = {
                    "receipt_type": etype,
                    "timestamp": ts,
                    "summary": summary,
                    "execution": False
                }

                if etype == "action_intent_gate_receipt":
                    receipt["truth"] = "gate/evaluation handling recorded only"
                elif etype == "approval_request_record":
                    receipt["truth"] = "approval request formally recorded only"
                    receipt["decision"] = False
                elif etype == "approval_log_entry":
                    receipt["truth"] = "approval decision recorded only"
                elif etype == "orientation_snapshot_receipt":
                    receipt["truth"] = "orientation terrain recorded only"
                elif etype == "test_proof_receipt":
                    receipt["truth"] = "test/proof terrain recorded only"

                receipts.append(receipt)

        except Exception:
            # Silently fail for read-only robustness in v0
            pass

        return receipts

    def assemble_cassandra_orientation_packet(self) -> Dict[str, Any]:
        """Assembles the v0 Cassandra orientation context packet."""

        return {
            "substrate_version": "v0",
            "actor_id": "cassandra",
            "purpose": "orientation_only",
            "source_commit": self.get_git_head(),
            "verified_capability_types": [
                "action_intent_gate_receipt",
                "approval_request_record",
                "approval_log_entry",
                "orientation_snapshot_receipt",
                "test_proof_receipt"
            ],
            "verified_receipt_rows": self.get_verified_receipt_rows(),
            "allowed_context": {
                "orientation": True,
                "receipt_spine_status": True
            },
            "blocked_context": {
                "gmail": True,
                "pii": True,
                "outreach": True,
                "send_authority": True,
                "runtime_execution": True,
                "guardian_runtime_action": True,
                "hermes_runtime_action": True
            },
            "authority": {
                "execution_authority": 0,
                "mutation_authority": 0,
                "context_packet_only": True
            }
        }

    def assemble_chief_operational_packet(self) -> Dict[str, Any]:
        """Assembles the v0 Chief operational review context packet."""

        rows = self.get_verified_receipt_rows()

        # Derive operational summary
        pending_count = sum(1 for r in rows if r["receipt_type"] == "approval_request_record")

        latest_gate = None
        for r in rows:
            if r["receipt_type"] == "action_intent_gate_receipt":
                latest_gate = r["summary"]
                break

        return {
            "substrate_version": "v0",
            "actor_id": "chief",
            "purpose": "operational_review_only",
            "source_commit": self.get_git_head(),
            "verified_capability_types": [
                "action_intent_gate_receipt",
                "approval_request_record",
                "approval_log_entry",
                "orientation_snapshot_receipt",
                "test_proof_receipt"
            ],
            "verified_receipt_rows": rows,
            "operational_summary": {
                "pending_approval_requests_count": pending_count,
                "latest_recorded_gate_evaluation": latest_gate
            },
            "allowed_context": {
                "receipt_spine_status": True,
                "approval_request_review": True,
                "approval_decision_review": True,
                "gate_evaluation_review": True,
                "safe_next_step_recommendation": True
            },
            "blocked_context": {
                "gmail": True,
                "pii": True,
                "outreach": True,
                "send_authority": True,
                "runtime_execution": True,
                "runtime_mutation": True,
                "guardian_runtime_action": True,
                "hermes_runtime_action": True,
                "live_service_status": True,
                "self_permission_expansion": True
            },
            "authority": {
                "execution_authority": 0,
                "mutation_authority": 0,
                "approval_authority": 0,
                "context_packet_only": True,
                "recommendation_only": True
            }
        }

    def assemble_guardian_safety_packet(self) -> Dict[str, Any]:
        """Assembles the v0 Guardian safety inspection context packet."""

        rows = self.get_verified_receipt_rows()

        # Derive safety summary
        pending_count = sum(1 for r in rows if r["receipt_type"] == "approval_request_record")

        latest_decision_ts = None
        for r in rows:
            if r["receipt_type"] == "approval_log_entry":
                latest_decision_ts = r["timestamp"]
                break

        # Safely attempt to get T2 rule count
        t2_rule_count = None
        try:
            from chief_approval_policy import _ALWAYS_T2
            t2_rule_count = len(_ALWAYS_T2)
        except Exception:
            pass

        return {
            "substrate_version": "v0",
            "actor_id": "guardian",
            "purpose": "safety_inspection_only",
            "source_commit": self.get_git_head(),
            "verified_capability_types": [
                "action_intent_gate_receipt",
                "approval_request_record",
                "approval_log_entry",
                "orientation_snapshot_receipt",
                "test_proof_receipt"
            ],
            "verified_receipt_rows": rows,
            "safety_policy_summary": {
                "pending_approval_requests_count": pending_count,
                "latest_safety_decision_timestamp": latest_decision_ts,
                "active_hard_t2_rule_count": t2_rule_count
            },
            "allowed_context": {
                "safety_gate_inspection": True,
                "policy_matching_review": True,
                "approval_request_review": True,
                "approval_decision_review": True,
                "truth_label_verification": True
            },
            "blocked_context": {
                "gmail": True,
                "pii": True,
                "outreach": True,
                "send_authority": True,
                "runtime_execution": True,
                "runtime_mutation": True,
                "guardian_runtime_action": True,
                "chief_operational_authority": True,
                "cassandra_orientation_authority": True,
                "hermes_runtime_action": True,
                "live_service_status": True,
                "self_permission_expansion": True
            },
            "authority": {
                "execution_authority": 0,
                "mutation_authority": 0,
                "approval_authority": 0,
                "denial_authority": 0,
                "routing_authority": 0,
                "context_packet_only": True,
                "inspection_only": True
            }
        }

    def assemble_niles_producer_packet(self) -> Dict[str, Any]:
        """Assembles the v0 Niles producer context packet."""

        return {
            "substrate_version": "v0",
            "actor_id": "niles",
            "purpose": "creative_orientation_only",
            "source_commit": self.get_git_head(),
            "producer_context": {
                "six_pillars": [
                    "Rhythmic Spine",
                    "Spatial Cinematic Architecture",
                    "Controlled Chaos / Emotional Rawness",
                    "Polished Indie Illusion",
                    "Mythic + Social Lyricism",
                    "Healing Dance Transcendence"
                ],
                "reference_extraction_principle": "Reference Extraction Principle: References are used to extract functions, techniques, and qualities, not to imitate artists. Goal is synthesis, not mimicry.",
                "artifact_types": [
                    "lyric", "song_brief", "arrangement_map", "mix_notes", "ableton_clip_summary",
                    "logic_project_summary", "daw_session_summary", "plugin_chain_summary",
                    "hardware_routing_summary", "demo_review", "setlist", "production_question"
                ],
                "suggested_moves": [
                    "add_arrival_point_without_clutter",
                    "widen_delay_return_preserve_vocal_clarity",
                    "sketch_spacious_groove_suggestion_only",
                    "production_optimization_suggestion"
                ]
            },
            "verified_capability_types": [
                "action_intent_gate_receipt",
                "approval_request_record",
                "approval_log_entry",
                "orientation_snapshot_receipt",
                "test_proof_receipt"
            ],
            "verified_receipt_rows": self.get_verified_receipt_rows(),
            "allowed_context": {
                "creative_critique": True,
                "pillar_alignment_review": True,
                "reference_extraction_analysis": True,
                "artifact_review": True,
                "taste_governor_framing": True
            },
            "blocked_context": {
                "daw_live_state": True,
                "hardware_live_state": True,
                "ableton_execution": True,
                "logic_execution": True,
                "audio_analysis_claims": True,
                "file_mutation": True,
                "gmail": True,
                "pii": True,
                "outreach": True,
                "legal_sensitive_data": True,
                "business_sensitive_data": True,
                "runtime_execution": True,
                "runtime_mutation": True,
                "send_authority": True,
                "self_permission_expansion": True
            },
            "authority": {
                "execution_authority": 0,
                "mutation_authority": 0,
                "approval_authority": 0,
                "daw_execution_authority": 0,
                "hardware_authority": 0,
                "recommendation_only": True,
                "context_packet_only": True
            }
        }

def main():
    assembler = AgentContextAssembler()

    # Check for actor flags
    actor = None
    if "--cassandra" in sys.argv:
        actor = "cassandra"
    elif "--chief" in sys.argv:
        actor = "chief"
    elif "--guardian" in sys.argv:
        actor = "guardian"
    elif "--niles" in sys.argv:
        actor = "niles"
    elif "--actor" in sys.argv:
        try:
            idx = sys.argv.index("--actor")
            actor = sys.argv[idx + 1]
        except (ValueError, IndexError):
            pass

    if actor == "cassandra":
        packet = assembler.assemble_cassandra_orientation_packet()
        print(json.dumps(packet, indent=2))
    elif actor == "chief":
        packet = assembler.assemble_chief_operational_packet()
        print(json.dumps(packet, indent=2))
    elif actor == "guardian":
        packet = assembler.assemble_guardian_safety_packet()
        print(json.dumps(packet, indent=2))
    elif actor == "niles":
        packet = assembler.assemble_niles_producer_packet()
        print(json.dumps(packet, indent=2))
    else:
        print("Usage: python scripts/generate_agent_context.py --cassandra | --chief | --guardian | --niles | --actor [cassandra|chief|guardian|niles]")
        sys.exit(1)

if __name__ == "__main__":
    main()

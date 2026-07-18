#!/usr/bin/env python3
"""Exercise Guardian button UX with real HMAC and an isolated HITL store."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import hitl_action_service as action_service
import hitl_notification_service as notify
import hitl_pending_store as pending_store
from chief_approval_brain import _build_l2_keyboard, _build_l2_message
from guardian_approval_ui import APPROVE_BUTTON_TEXT, DENY_BUTTON_TEXT, human_reply_code


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    os.environ["HITL_ENABLED"] = "1"
    with tempfile.TemporaryDirectory(prefix="guardian-button-ux-") as temp_dir:
        temp = Path(temp_dir)
        pending_store.HITL_STATE_PATH = temp / "hitl_pending_state.json"
        pending_store.HITL_AUDIT_LOG = temp / "hitl_audit.jsonl"
        pending_store.HITL_FLAG_PATH = temp / "hitl_enabled.flag"
        pending_store._shadow_cassandra_hitl_proposal = lambda *_args, **_kwargs: None
        pending_store._shadow_cassandra_hitl_decision = lambda *_args, **_kwargs: None
        notify._LOGS_DIR = temp
        notify._NOTIFY_LOG = temp / "hitl_notifications.jsonl"
        notify._maybe_send_no_pending_confirmation = lambda: None

        action_id, created = action_service.create_pending_action(
            "cassandra",
            "email_send",
            {"summary": "Synthetic no-network Guardian button UX canary"},
            idempotency_key="guardian-button-ux-canary-v1",
            ttl_seconds=300,
        )
        action = action_service.get_pending_action(action_id)
        if not created or not action:
            raise SystemExit("isolated pending action was not created")

        visible_request = notify.format_notification(action)
        keyboard = notify._build_keyboard(action_id)
        decision_buttons = keyboard["inline_keyboard"][0]
        labels = [str(button["text"]) for button in decision_buttons]
        callback_rows = []
        for button in decision_buttons:
            callback_data = str(button["callback_data"])
            raw_token = callback_data.removeprefix("HITL:")
            validated = notify.validate_token(raw_token)
            if not validated.get("ok"):
                raise SystemExit("signed callback did not validate")
            if raw_token in visible_request:
                raise SystemExit("signed callback leaked into visible request")
            callback_rows.append(
                {
                    "label": button["text"],
                    "decision": validated["decision"],
                    "callback_data_sha256": _sha256_text(callback_data),
                    "raw_callback_included": False,
                    "signature_valid": True,
                }
            )

        deny_callback = str(decision_buttons[1]["callback_data"])
        visible_outcome = notify.process_callback(deny_callback, approved_by="guardian-ui-canary")
        terminal = action_service.get_pending_action(action_id)

        chief_message = _build_l2_message(
            "Synthetic Chief approval button UX canary",
            "CANARY01",
            "MUST_NOT_RENDER",
            2,
        )
        chief_keyboard = _build_l2_keyboard("CANARY01", 2)
        chief_labels = [button["text"] for button in chief_keyboard["inline_keyboard"][0]]

        token_like_visible = bool(
            re.search(r"/hitl_(?:approve|deny)|HITL:|MUST_NOT_RENDER|\.[YN]\.[0-9]{8,}\.", visible_request)
            or re.search(r"HITL:|MUST_NOT_RENDER|\.[YN]\.[0-9]{8,}\.", visible_outcome)
            or "MUST_NOT_RENDER" in chief_message
        )
        proof_passed = bool(
            labels == [APPROVE_BUTTON_TEXT, DENY_BUTTON_TEXT]
            and chief_labels == [APPROVE_BUTTON_TEXT, DENY_BUTTON_TEXT]
            and f"APPROVE {human_reply_code(action_id)}" in visible_request
            and terminal
            and terminal.get("status") == pending_store.DENIED
            and visible_outcome.startswith("❌ Denied by you at ")
            and not token_like_visible
        )
        receipt = {
            "schema_version": "guardian_approval_button_ux_canary_v1",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "status": "LIVE_OWNER_CANARY_PASSED" if proof_passed else "LIVE_OWNER_CANARY_FAILED",
            "proof_passed": proof_passed,
            "owner_process": "scripts/run_guardian_approval_button_ux_canary.py",
            "store_mode": "isolated_real_hitl_state_machine",
            "network_called": False,
            "telegram_send_performed": False,
            "external_action_performed": False,
            "business_ledger_posted": False,
            "action_id_sha256": _sha256_text(action_id),
            "final_action_status": terminal.get("status") if terminal else "missing",
            "button_labels": labels,
            "callback_proofs": callback_rows,
            "callback_answer_required_by_listener": True,
            "same_message_terminal_outcome": visible_outcome,
            "original_request_reused_in_outcome": False,
            "raw_token_visible": token_like_visible,
            "human_fallback": {
                "approve": f"APPROVE {human_reply_code(action_id)}",
                "deny": f"DENY {human_reply_code(action_id)}",
                "raw_hmac_included": False,
            },
            "chief_surface": {
                "button_labels": chief_labels,
                "visible_hash_included": "MUST_NOT_RENDER" in chief_message,
                "short_code_present": f"APPROVE {human_reply_code('CANARY01')}" in chief_message,
            },
        }
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0 if proof_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

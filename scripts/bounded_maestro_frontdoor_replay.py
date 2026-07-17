#!/usr/bin/env python3
"""Run one delivery-suppressed Maestro front-door processor replay."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import maestro_listener


async def _run(*, text: str, message_id: str) -> None:
    request = maestro_listener.build_maestro_chat_replay_request(
        text,
        message_id=message_id,
    )
    maestro_listener.write_bridge_request(request)
    response = await maestro_listener.poll_bridge_response(request["request_id"])
    detail = response.get("detail_disclosure") or {}
    print(
        json.dumps(
            {
                "source_request_id": response.get("source_request_id"),
                "request_actor": request.get("actor"),
                "replay_mode": request.get("replay_mode"),
                "delivery_suppressed": request.get("delivery_suppressed"),
                "operator_message": response.get("operator_message"),
                "operator_response_disposition": detail.get(
                    "operator_response_disposition"
                ),
                "telegram_photo_delivery_requested": detail.get(
                    "telegram_photo_delivery_requested"
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--message-id", required=True)
    args = parser.parse_args()
    asyncio.run(_run(text=args.text, message_id=args.message_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

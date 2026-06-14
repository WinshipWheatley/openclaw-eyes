"""Thin API transport over ``chief_compose.compose``.

The module is import-safe when FastAPI is not installed. Pure helper functions
are covered by tests; ``create_app`` raises a clear dependency error until the
runtime installs FastAPI/uvicorn.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_work_packet import get_agent_work_packet_approval_state, init_agent_work_packet_schema
from business_ops_ledger import DEFAULT_DB_PATH, init_business_ops_ledger, record_file_inventory_entry
from chief_compose import compose, execute_packet_with_state
from compose_contract import ComposeResult, GateState

try:  # pragma: no cover - exercised only when optional runtime deps exist.
    from fastapi import FastAPI, Header, HTTPException, WebSocket
except ModuleNotFoundError:  # pragma: no cover - current repo venv lacks FastAPI.
    FastAPI = None  # type: ignore[assignment]
    Header = None  # type: ignore[assignment]
    HTTPException = None  # type: ignore[assignment]
    WebSocket = None  # type: ignore[assignment]


FASTAPI_AVAILABLE = FastAPI is not None
DEFAULT_BIND_HOSTS = ("127.0.0.1",)
DEFAULT_API_TOKEN_ENV = "OPENCLAW_API_TOKEN"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def verify_bearer_header(authorization: str | None, expected_token: str | None) -> bool:
    if not expected_token:
        return False
    prefix = "Bearer "
    return bool(authorization and authorization.startswith(prefix) and authorization[len(prefix) :] == expected_token)


def _button_label_for_surface(surface: str) -> str:
    labels = {
        "invoice_send": "Approve invoice send",
        "email_send": "Approve email send",
        "sms_send": "Approve text send",
        "phone_log": "Approve phone action",
        "calendar_create": "Approve calendar create",
        "ledger_mutation": "Approve ledger change",
        "coupa_submit": "Approve Coupa submit",
        "obs_launch": "Approve OBS launch",
        "livestream_setup": "Approve livestream setup",
    }
    return labels.get(surface, f"Approve {surface.replace('_', ' ')}")


def render_api_compose_result(result: ComposeResult) -> dict[str, Any]:
    payload = result.to_dict()
    meta = dict(payload.get("meta") or {})
    intent = payload.get("intent")
    if intent == "unknown_review":
        meta["debug_intent"] = "unknown_review"
        payload["intent"] = "needs_clarification"
        if payload.get("gate_state") == GateState.PENDING_APPROVAL.value:
            payload["segments"] = [
                "I'm not sure what to do with that yet.",
                "Nothing has been sent yet.",
                "Tell me whether this is an action, a lookup, or a question.",
            ]
    if payload.get("gate_state") == GateState.PENDING_APPROVAL.value:
        segments = [str(segment) for segment in payload.get("segments") or [] if str(segment).strip()]
        if "Nothing has been sent yet." not in segments:
            segments.insert(1 if segments else 0, "Nothing has been sent yet.")
        pending = payload.get("pending_approval") or {}
        preview = dict(pending.get("preview") or {})
        surface = str(pending.get("surface") or payload.get("intent") or "action")
        preview.setdefault("button_label", _button_label_for_surface(surface))
        pending["preview"] = preview
        payload["pending_approval"] = pending
        payload["segments"] = segments
    if payload.get("gate_state") == GateState.READ_ONLY.value:
        payload["packet_id"] = None
        payload["pending_approval"] = None
    payload["meta"] = meta
    return payload


def list_pending_packets(*, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    path = init_agent_work_packet_schema(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
SELECT packet_id, candidate_action_type, intent_category, goal, status, created_at
FROM agent_work_packets
WHERE approval_required = 1 AND execution_allowed = 0 AND action_created = 0
ORDER BY created_at DESC, packet_id DESC
""".strip()
        ).fetchall()
        packets = []
        for row in rows:
            state = get_agent_work_packet_approval_state(packet_id=row["packet_id"], db_path=path)
            surface = row["candidate_action_type"] or row["intent_category"]
            packets.append(
                {
                    "packet_id": row["packet_id"],
                    "surface": surface,
                    "preview": {
                        "goal": row["goal"],
                        "button_label": _button_label_for_surface(surface),
                        "packet_hash": state.packet_hash,
                    },
                    "created_at": row["created_at"],
                    "status": row["status"],
                }
            )
        return packets
    finally:
        conn.close()


def approve_packet(
    packet_id: str,
    *,
    surface: str,
    expected_packet_hash: str | None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    receipt = execute_packet_with_state(
        packet_id,
        surface=surface,
        expected_packet_hash=expected_packet_hash,
        db_path=str(db_path) if db_path else None,
    )
    return receipt.to_dict()


def register_file_reference(
    *,
    path_ref: str,
    display_name: str | None = None,
    intended_use: str = "",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(path_ref).expanduser()
    absolute = path.resolve(strict=False)
    exists = absolute.exists()
    stat = absolute.stat() if exists else None
    size_bytes = int(stat.st_size) if stat else 0
    modified_at = (
        datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat()
        if stat
        else utc_now()
    )
    name = display_name or absolute.name or "operator_file"
    extension = absolute.suffix or None
    metadata_hash = hashlib.sha256(
        "\0".join([absolute.as_posix(), str(size_bytes), modified_at, intended_use]).encode("utf-8")
    ).hexdigest()
    file_id = f"api_file_{metadata_hash[:20]}"
    init_business_ops_ledger(str(db_path or DEFAULT_DB_PATH))
    ok = record_file_inventory_entry(
        file_id=file_id,
        root_id="api_file_intake",
        drive_label=None,
        absolute_path=absolute.as_posix(),
        relative_path=absolute.name or absolute.as_posix(),
        file_name=name,
        extension=extension,
        file_type_guess=extension.lstrip(".") if extension else None,
        size_bytes=size_bytes,
        modified_at=modified_at,
        content_hash=f"metadata:{metadata_hash}",
        sensitivity_guess="unknown",
        ingest_eligibility="eligible_metadata_only" if exists else "unknown",
        exclusion_reason=None if exists else "path_not_verified",
        db_path=str(db_path) if db_path else None,
    )
    return {
        "file_id": file_id,
        "stored_ref": f"file_inventory:{file_id}",
        "acknowledged": bool(ok),
        "exists": exists,
        "metadata_only": True,
    }


def health_payload(*, db_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(db_path or DEFAULT_DB_PATH)
    return {
        "ok": True,
        "listener_seen": Path("chief_listener.py").exists(),
        "ledger_ok": path.exists() or path.parent.exists(),
    }


def _require_fastapi() -> None:
    if not FASTAPI_AVAILABLE:
        raise RuntimeError("FastAPI runtime is not installed. Install fastapi and uvicorn before starting the API.")


def create_app(*, db_path: str | Path | None = None, token_env: str = DEFAULT_API_TOKEN_ENV) -> Any:
    _require_fastapi()
    app = FastAPI(title="OpenClaw Compose API", version="0.1.0")  # type: ignore[misc,operator]

    def _require_auth(authorization: str | None) -> None:
        expected = os.environ.get(token_env)
        if not verify_bearer_header(authorization, expected):
            raise HTTPException(status_code=401, detail="missing_or_invalid_bearer_token")  # type: ignore[misc]

    @app.get("/health")  # type: ignore[union-attr]
    def health() -> dict[str, Any]:
        return health_payload(db_path=db_path)

    @app.post("/message")  # type: ignore[union-attr]
    def message(body: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:  # type: ignore[misc]
        _require_auth(authorization)
        result = compose(
            str(body.get("text") or ""),
            source_kind=str(body.get("source_kind") or "mission_control"),
            source_channel=str(body.get("source_channel") or "api"),
            requested_by="winship",
            db_path=str(db_path) if db_path else None,
        )
        return render_api_compose_result(result)

    @app.get("/packets")  # type: ignore[union-attr]
    def packets(state: str = "pending", authorization: str | None = Header(default=None)) -> dict[str, Any]:  # type: ignore[misc]
        _require_auth(authorization)
        if state != "pending":
            return {"packets": []}
        return {"packets": list_pending_packets(db_path=db_path)}

    @app.post("/packets/{packet_id}/approve")  # type: ignore[union-attr]
    def approve(packet_id: str, body: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:  # type: ignore[misc]
        _require_auth(authorization)
        return approve_packet(
            packet_id,
            surface=str(body.get("surface") or ""),
            expected_packet_hash=body.get("packet_hash"),
            db_path=db_path,
        )

    @app.post("/packets/{packet_id}/rework")  # type: ignore[union-attr]
    def rework(packet_id: str, body: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:  # type: ignore[misc]
        _require_auth(authorization)
        return {"packet_id": packet_id, "gate_state": GateState.REWORK.value, "note": str(body.get("note") or "")}

    @app.post("/file")  # type: ignore[union-attr]
    def file_intake(body: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:  # type: ignore[misc]
        _require_auth(authorization)
        return register_file_reference(
            path_ref=str(body.get("path_ref") or ""),
            display_name=body.get("display_name"),
            intended_use=str(body.get("intended_use") or ""),
            db_path=db_path,
        )

    @app.websocket("/ws")  # type: ignore[union-attr]
    async def websocket_endpoint(websocket: Any) -> None:
        if not verify_bearer_header(websocket.headers.get("authorization"), os.environ.get(token_env)):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        while True:
            text = await websocket.receive_text()
            result = render_api_compose_result(
                compose(
                    text,
                    source_kind="mission_control",
                    source_channel="api_ws",
                    requested_by="winship",
                    db_path=str(db_path) if db_path else None,
                )
            )
            for segment in result.get("segments") or []:
                await websocket.send_json({"type": "segment", "text": segment})
            await websocket.send_json({"type": "final", "result": result})

    return app


__all__ = [
    "DEFAULT_API_TOKEN_ENV",
    "FASTAPI_AVAILABLE",
    "approve_packet",
    "create_app",
    "health_payload",
    "list_pending_packets",
    "register_file_reference",
    "render_api_compose_result",
    "verify_bearer_header",
]

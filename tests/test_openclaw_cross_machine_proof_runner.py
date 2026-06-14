import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openclaw_cross_machine_proof_runner as runner
from scripts.run_openclaw_cross_machine_proof import main as proof_main


FIXED_NOW = "2026-05-31T15:00:00+00:00"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _context(tmp_path: Path) -> dict:
    return runner.build_proof_context(
        proof_ref="event_bridge_live_arts_prepare_pdf",
        generated_at=FIXED_NOW,
        pc_bridge_root=tmp_path / "bridge",
        mac_bridge_root="/Volumes/openclaw_e",
    )


def _write_worker_manifest(context: dict) -> None:
    _write_json(
        Path(context["worker_manifest_path"]),
        {
            "worker_id": "mac_local_proof_worker:test",
            "status": "READY",
            "supported_job_kinds": ["EMIT_EVENT_BRIDGE_ENVELOPE"],
        },
    )


def _write_mac_result(context: dict, *, boundary_flags: dict | None = None) -> None:
    _write_json(
        Path(context["mac_result_path"]),
        {
            "job_id": context["job_id"],
            "proof_run_id": context["proof_run_id"],
            "status": "EVENT_EMITTED",
            "emitted_event_path": context["request_path"],
            "correlation_id": context["correlation_id"],
            "error_code": "",
            "error_message": "",
            "boundary_flags": boundary_flags or dict(runner.MAC_JOB_SAFETY_FLAGS),
        },
    )


def _write_event(context: dict) -> None:
    _write_json(Path(context["request_path"]), context["event_envelope"])


def _response_payload(context: dict, *, route_status: str = "ROUTE_MATCHED", pdf_export_performed: bool = False) -> dict:
    handler = (
        "invoice_review_action_request.live_arts_md"
        if route_status == "ROUTE_MATCHED"
        else ""
    )
    return {
        "source_request_id": context["event_id"],
        "event_id": context["event_id"],
        "correlation_id": context["correlation_id"],
        "route_status": route_status,
        "workflow_status": "WORKFLOW_ACTION_ROUTED" if route_status == "ROUTE_MATCHED" else "WORKFLOW_BLOCKED",
        "selected_handler_id": handler,
        "event_bridge_adapter_response": {
            "route_status": route_status,
            "workflow_status": "WORKFLOW_ACTION_ROUTED" if route_status == "ROUTE_MATCHED" else "WORKFLOW_BLOCKED",
            "router_decision": {"selected_handler_id": handler},
            "machine_proof": {
                "handler_execution_performed": False,
                "processor_execution_performed": False,
                "model_call_performed": False,
                "email_send_performed": False,
                "gmail_access_performed": False,
                "browser_access_performed": False,
                "coupa_access_performed": False,
                "ledger_post_performed": False,
                "workbook_cell_read_performed": False,
                "pdf_export_performed": pdf_export_performed,
            },
        },
        "machine_proof": {
            "handler_execution_performed": False,
            "processor_execution_performed": False,
            "model_call_performed": False,
            "email_send_performed": False,
            "gmail_access_performed": False,
            "browser_access_performed": False,
            "coupa_access_performed": False,
            "ledger_post_performed": False,
            "workbook_cell_read_performed": False,
            "pdf_export_performed": pdf_export_performed,
        },
    }


def _write_response(context: dict, *, route_status: str = "ROUTE_MATCHED", pdf_export_performed: bool = False) -> None:
    _write_json(
        Path(context["response_path"]),
        _response_payload(
            context,
            route_status=route_status,
            pdf_export_performed=pdf_export_performed,
        ),
    )


def test_proof_runner_creates_run_and_writes_mac_job(tmp_path: Path) -> None:
    read_model = runner.run_cross_machine_proof(
        proof_ref="event_bridge_live_arts_prepare_pdf",
        generated_at=FIXED_NOW,
        pc_bridge_root=tmp_path / "bridge",
        timeout_seconds=0,
    )

    proof_run = read_model["proof_runs"][0]
    assert proof_run["proof_run_id"].startswith("proof_run_event_bridge_live_arts_prepare_pdf_")
    assert proof_run["correlation_id"].startswith("correlation:cross_machine_proof:")
    assert Path(proof_run["mac_job_path"]).is_file()
    assert read_model["status"] == "MAC_WORKER_MISSING"


def test_mock_mac_result_and_pc_route_response_produces_pass(tmp_path: Path) -> None:
    context = _context(tmp_path)
    _write_worker_manifest(context)
    _write_event(context)
    _write_mac_result(context)
    _write_response(context)

    read_model = runner.run_cross_machine_proof(
        proof_ref="event_bridge_live_arts_prepare_pdf",
        generated_at=FIXED_NOW,
        pc_bridge_root=tmp_path / "bridge",
        timeout_seconds=0,
    )

    assert read_model["status"] == "PASS"
    result = read_model["proof_results"][0]
    assert result["route_status"] == "ROUTE_MATCHED"
    assert result["workflow_status"] == "WORKFLOW_ACTION_ROUTED"
    assert result["selected_handler_id"] == "invoice_review_action_request.live_arts_md"
    assert not read_model["proof_failures"]


def test_missing_mac_result_is_not_acked(tmp_path: Path) -> None:
    context = _context(tmp_path)
    _write_worker_manifest(context)

    read_model = runner.run_cross_machine_proof(
        proof_ref="event_bridge_live_arts_prepare_pdf",
        generated_at=FIXED_NOW,
        pc_bridge_root=tmp_path / "bridge",
        timeout_seconds=0,
    )

    assert read_model["status"] == "MAC_JOB_NOT_ACKED"
    assert read_model["proof_failures"][0]["exact_file"] == context["mac_result_path"]


def test_missing_pc_response_is_reported(tmp_path: Path) -> None:
    context = _context(tmp_path)
    _write_worker_manifest(context)
    _write_event(context)
    _write_mac_result(context)

    read_model = runner.run_cross_machine_proof(
        proof_ref="event_bridge_live_arts_prepare_pdf",
        generated_at=FIXED_NOW,
        pc_bridge_root=tmp_path / "bridge",
        timeout_seconds=0,
    )

    assert read_model["status"] == "RESPONSE_NOT_FOUND"
    assert read_model["proof_failures"][0]["failure_status"] == "RESPONSE_NOT_FOUND"


def test_route_rejected_has_exact_reason(tmp_path: Path) -> None:
    context = _context(tmp_path)
    _write_worker_manifest(context)
    _write_event(context)
    _write_mac_result(context)
    _write_response(context, route_status="ROUTE_REJECTED_VALIDATION")

    read_model = runner.run_cross_machine_proof(
        proof_ref="event_bridge_live_arts_prepare_pdf",
        generated_at=FIXED_NOW,
        pc_bridge_root=tmp_path / "bridge",
        timeout_seconds=0,
    )

    assert read_model["status"] == "ROUTE_REJECTED"
    assert "route_status expected" in read_model["proof_failures"][0]["reason"]


def test_boundary_flag_violation_fails(tmp_path: Path) -> None:
    context = _context(tmp_path)
    _write_worker_manifest(context)
    _write_event(context)
    _write_mac_result(context)
    _write_response(context, pdf_export_performed=True)

    read_model = runner.run_cross_machine_proof(
        proof_ref="event_bridge_live_arts_prepare_pdf",
        generated_at=FIXED_NOW,
        pc_bridge_root=tmp_path / "bridge",
        timeout_seconds=0,
    )

    assert read_model["status"] == "BOUNDARY_VIOLATION"
    assert "pdf_export_performed" in read_model["proof_failures"][0]["reason"]


def test_missing_mac_worker_exports_work_package_and_sqlite(tmp_path: Path) -> None:
    result = runner.export_openclaw_cross_machine_proof_runner(
        proof_ref="event_bridge_live_arts_prepare_pdf",
        generated_at=FIXED_NOW,
        pc_bridge_root=tmp_path / "bridge",
        read_model_root=tmp_path / "read_models",
        system_knowledge_root=tmp_path / "system_knowledge",
        timeout_seconds=0,
    )

    assert result.status == "MAC_WORKER_MISSING"
    assert result.mac_worker_exists is False
    assert Path(result.mac_work_package_path).is_file()
    payload = json.loads(Path(result.json_path).read_text(encoding="utf-8"))
    assert payload["proof_failures"][0]["failure_status"] == "MAC_WORKER_MISSING"

    connection = sqlite3.connect(result.sqlite_path)
    try:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert set(runner.REQUIRED_SQLITE_TABLES).issubset(table_names)
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_cli_returns_nonzero_for_missing_mac_worker_and_writes_json(tmp_path: Path) -> None:
    rc = proof_main(
        [
            "--proof",
            "event_bridge_live_arts_prepare_pdf",
            "--pc-bridge-root",
            str(tmp_path / "bridge"),
            "--read-model-root",
            str(tmp_path / "read_models"),
            "--system-knowledge-root",
            str(tmp_path / "system_knowledge"),
            "--generated-at",
            FIXED_NOW,
            "--timeout-seconds",
            "0",
        ]
    )

    assert rc == 2
    payload = json.loads((tmp_path / "read_models" / runner.JSON_EXPORT_NAME).read_text(encoding="utf-8"))
    assert payload["status"] == "MAC_WORKER_MISSING"


def test_no_dangerous_runtime_imports_or_calls() -> None:
    text = Path(runner.__file__).read_text(encoding="utf-8")
    forbidden = (
        "import smtplib",
        "import webbrowser",
        "import openpyxl",
        "import pandas",
        "subprocess" + ".run",
        "requests.",
        "selenium",
    )
    for token in forbidden:
        assert token not in text

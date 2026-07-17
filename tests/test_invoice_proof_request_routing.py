from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_st_annes_artifact(root: Path) -> Path:
    package = root / "st-annes" / "2026-06" / "canonical-v4"
    package.mkdir(parents=True)
    workbook = b"st annes june workbook"
    pdf = b"st annes canonical v4 pdf"
    (package / "invoice.xlsx").write_bytes(workbook)
    (package / "invoice.pdf").write_bytes(pdf)
    (package / "invoice_manifest.json").write_text(
        json.dumps(
            {
                "schema": "openclaw_invoice_manifest_v1",
                "invoice_key": "2026-06_st-annes",
                "client_slug": "st-annes",
                "invoice_number": "3",
                "service_period_start": "2026-06-01",
                "service_period_end": "2026-06-30",
                "status": "draft",
                "amount": 875.0,
                "source_sheet": "June 2026",
                "package_workbook_sha256": _sha256(workbook),
                "current_pdf_sha256": _sha256(pdf),
                "latest_send_receipt_path": None,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return package / "invoice.pdf"


def _request(text: str, *, request_id: str, created_at: str) -> dict:
    import maestro_listener

    return maestro_listener.build_operator_maestro_chat_request(
        text,
        message_id=request_id,
        chat_id=42,
        created_at=created_at,
    )


def test_historical_1690_replay_resolves_prior_st_annes_context_and_surfaces_pdf(
    tmp_path,
    monkeypatch,
) -> None:
    import invoice_proof_request
    import openclaw_request_processor as processor

    artifact_root = tmp_path / "invoice_artifacts"
    pdf_path = _write_st_annes_artifact(artifact_root)
    monkeypatch.setattr(invoice_proof_request, "DEFAULT_INVOICE_ARTIFACT_ROOTS", (artifact_root,))
    monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "0")
    monkeypatch.setenv("OPENCLAW_LM1_SHARED_SEAM", "0")

    prior_path = tmp_path / "mission_control_operator_instruction_request_maestro_telegram_1688.json"
    current_path = tmp_path / "mission_control_operator_instruction_request_maestro_telegram_1690.json"
    prior_request = _request(
        "lets test the st annes invoice flow",
        request_id="1688",
        created_at="2026-07-17T03:55:49+00:00",
    )
    current_request = _request(
        "let me see the exported pdf proof",
        request_id="1690",
        created_at="2026-07-17T03:56:16+00:00",
    )
    prior_path.write_text(
        json.dumps(prior_request, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    current_path.write_text(
        json.dumps(current_request, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    response = processor.process_request_path(
        current_path,
        export_root=tmp_path / "read_models",
        generated_at="2026-07-17T03:56:17+00:00",
        duplicate_check=False,
    )
    payload, _status = processor.build_payloads(
        response,
        generated_at="2026-07-17T03:56:17+00:00",
    )

    assert response.request_type == "ARTIFACT_RETRIEVAL"
    assert response.workflow_ref == "st_annes_invoice_proof_retrieval"
    assert response.detail_disclosure["operator_display"]["speaker_ref"] == "maestro"
    resolution = response.detail_disclosure["invoice_artifact_retrieval"]
    assert resolution["context_source"] == "prior_same_chat_request"
    assert resolution["context_request_id"] == prior_request["request_id"]
    assert resolution["locator_result"]["status"] == "FOUND"
    assert resolution["locator_result"]["canonical_candidate"]["pdf_path"] == pdf_path.as_posix()
    assert len(response.proof_artifacts) == 1
    artifact = response.proof_artifacts[0]
    assert artifact["bridge_path"] == pdf_path.as_posix()
    assert artifact["presentation"] == {
        "presenter": "ProofPresenter",
        "mode": "quicklook",
        "should_open": True,
    }
    assert payload["proof_artifacts"] == [artifact]
    assert "I'm on it" not in response.operator_message
    assert "pull that up" not in response.operator_message
    assert response.proof_to_response["artifact_locator_performed"] is True
    assert response.proof_to_response["proof_presentation_requested"] is True
    assert response.proof_to_response["external_action_performed"] is False


def test_addressed_agent_owns_proof_response_voice_without_changing_route(
    tmp_path,
    monkeypatch,
) -> None:
    import invoice_proof_request
    import openclaw_request_processor as processor

    artifact_root = tmp_path / "invoice_artifacts"
    _write_st_annes_artifact(artifact_root)
    monkeypatch.setattr(invoice_proof_request, "DEFAULT_INVOICE_ARTIFACT_ROOTS", (artifact_root,))
    request_path = tmp_path / "mission_control_operator_instruction_request_addressed.json"
    request_path.write_text(
        json.dumps(
            _request(
                "Chief, show me the St Anne's exported PDF proof",
                request_id="addressed-chief-proof",
                created_at="2026-07-17T04:00:00+00:00",
            ),
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    response = processor.process_request_path(
        request_path,
        export_root=tmp_path / "read_models",
        generated_at="2026-07-17T04:00:01+00:00",
        duplicate_check=False,
    )
    payload, _status = processor.build_payloads(
        response,
        generated_at="2026-07-17T04:00:01+00:00",
    )

    assert response.request_type == "ARTIFACT_RETRIEVAL"
    assert response.detail_disclosure["operator_display"]["speaker_ref"] == "chief"
    assert payload["response_author"] == "CHIEF"
    assert payload["voice_profile_ref"] == "voice:chief:operational"

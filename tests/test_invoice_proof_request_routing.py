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


def test_surface_classifier_prefers_origin_over_generic_operator_chat_ref() -> None:
    from operator_response_disposition import surface_class_from_request

    assert surface_class_from_request(
        {
            "active_surface_ref": "operator_maestro_chat",
            "origin_surface": "mission_control_mac",
            "source_channel": "mission_control",
        }
    ) == "mac"
    assert surface_class_from_request(
        {
            "active_surface_ref": "operator_maestro_chat",
            "origin_surface": "telegram_pc_maestro_listener",
            "source_channel": "maestro_listener",
        }
    ) == "telegram"


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
        "presenter": "TelegramPhoto",
        "mode": "photo",
        "should_send": True,
    }
    disposition = response.detail_disclosure["operator_response_disposition"]
    assert disposition["active_surface"] == "telegram"
    assert disposition["artifact_variant"] == "current"
    assert disposition["delivery_mode"] == "telegram_photo"
    assert "QuickLook" not in response.operator_message
    assert "/Volumes/" not in response.operator_message
    assert payload["proof_artifacts"] == [artifact]
    assert "I'm on it" not in response.operator_message
    assert "pull that up" not in response.operator_message
    assert response.proof_to_response["artifact_locator_performed"] is True
    assert response.proof_to_response["proof_presentation_requested"] is True
    assert response.proof_to_response["external_action_performed"] is False


def test_recommended_live_arts_cut_selects_verified_candidate_for_telegram(
    tmp_path,
    monkeypatch,
) -> None:
    import invoice_proof_request
    import openclaw_request_processor as processor

    pdf = tmp_path / "candidate.pdf"
    png = tmp_path / "candidate.png"
    pdf.write_bytes(b"candidate pdf")
    png.write_bytes(b"candidate png")
    registry = tmp_path / "invoice_candidate_artifact_registry.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": "invoice_candidate_artifact_registry_v0",
                "candidates": [
                    {
                        "artifact_id": "lamd-2026-07-candidate-b",
                        "client_ref": "live_arts_md",
                        "service_period": "2026-07",
                        "invoice_number": "2026-1004",
                        "review_label": "Candidate B",
                        "status": "verified_review_candidate",
                        "active_for_review": True,
                        "finalized": False,
                        "pdf_path": pdf.as_posix(),
                        "pdf_sha256": _sha256(pdf.read_bytes()),
                        "rendered_image_path": png.as_posix(),
                        "rendered_image_sha256": _sha256(png.read_bytes()),
                        "source_receipt_ref": "receipt:test-candidate-b",
                    }
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(invoice_proof_request, "DEFAULT_CANDIDATE_REGISTRY_PATH", registry)
    monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "0")
    monkeypatch.setenv("OPENCLAW_LM1_SHARED_SEAM", "0")

    request_path = tmp_path / "mission_control_operator_instruction_request_maestro_telegram_1711.json"
    request_path.write_text(
        json.dumps(
            _request(
                "Let me see the Live Art, Maryland July invoice cut you recommend",
                request_id="1711",
                created_at="2026-07-17T20:13:22+00:00",
            ),
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    response = processor.process_request_path(
        request_path,
        export_root=tmp_path / "read_models",
        generated_at="2026-07-17T20:13:23+00:00",
        duplicate_check=False,
    )

    artifact = response.proof_artifacts[0]
    disposition = response.detail_disclosure["operator_response_disposition"]
    assert response.request_type == "ARTIFACT_RETRIEVAL"
    assert response.detail_disclosure["invoice_artifact_retrieval"]["client_ref"] == "live_arts_md"
    assert artifact["artifact_variant"] == "candidate"
    assert artifact["sha256"] == "sha256:" + _sha256(pdf.read_bytes())
    assert artifact["rendered_image_sha256"] == "sha256:" + _sha256(png.read_bytes())
    assert artifact["presentation"]["mode"] == "photo"
    assert disposition["artifact_variant"] == "candidate"
    assert disposition["delivery_mode"] == "telegram_photo"
    assert "candidate" in response.operator_message.lower()
    assert "not final" in response.operator_message.lower()
    assert "QuickLook" not in response.operator_message
    assert pdf.as_posix() not in response.operator_message


def test_suppressed_replay_selects_photo_without_claiming_or_requesting_delivery(
    tmp_path,
    monkeypatch,
) -> None:
    import invoice_proof_request
    import maestro_listener
    import openclaw_request_processor as processor

    pdf = tmp_path / "candidate.pdf"
    png = tmp_path / "candidate.png"
    pdf.write_bytes(b"candidate pdf")
    png.write_bytes(b"candidate png")
    registry = tmp_path / "invoice_candidate_artifact_registry.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": "invoice_candidate_artifact_registry_v0",
                "candidates": [
                    {
                        "artifact_id": "lamd-2026-07-candidate-b",
                        "client_ref": "live_arts_md",
                        "service_period": "2026-07",
                        "invoice_number": "2026-1004",
                        "review_label": "Candidate B",
                        "status": "verified_review_candidate",
                        "active_for_review": True,
                        "finalized": False,
                        "pdf_path": pdf.as_posix(),
                        "pdf_sha256": _sha256(pdf.read_bytes()),
                        "rendered_image_path": png.as_posix(),
                        "rendered_image_sha256": _sha256(png.read_bytes()),
                        "source_receipt_ref": "receipt:test-candidate-b",
                    }
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(invoice_proof_request, "DEFAULT_CANDIDATE_REGISTRY_PATH", registry)
    monkeypatch.setenv("OPENCLAW_INTERPRETER_LM", "0")
    monkeypatch.setenv("OPENCLAW_LM1_SHARED_SEAM", "0")

    request = maestro_listener.build_maestro_chat_replay_request(
        "Let me see the Live Art, Maryland July invoice cut you recommend",
        message_id="replay-1711",
        created_at="2026-07-17T20:13:22+00:00",
    )
    request_path = tmp_path / "mission_control_operator_instruction_request_replay_1711.json"
    request_path.write_text(json.dumps(request, sort_keys=True) + "\n", encoding="utf-8")

    response = processor.process_request_path(
        request_path,
        export_root=tmp_path / "read_models",
        generated_at="2026-07-17T20:13:23+00:00",
        duplicate_check=False,
    )

    disposition = response.detail_disclosure["operator_response_disposition"]
    proof = response.proof_to_response
    presentation = response.proof_artifacts[0]["presentation"]
    assert disposition["delivery_mode"] == "telegram_photo"
    assert disposition["delivery_suppressed"] is True
    assert disposition["delivery_status"] == "suppressed_test_replay"
    assert proof["telegram_photo_delivery_requested"] is False
    assert response.detail_disclosure["telegram_photo_delivery_requested"] is False
    assert presentation["should_send"] is False
    assert presentation["delivery_suppressed"] is True
    assert "did not deliver" in response.operator_message.lower()
    assert "as an image in this chat" not in response.operator_message.lower()
    assert response.detail_disclosure["request_message_provenance"]["actor"] == "pc_codex_desktop_replay"


def test_suppressed_replay_copy_preserves_each_addressed_agent_voice() -> None:
    import agent_voice_profiles

    messages = {
        speaker: agent_voice_profiles.artifact_ready_message_for_speaker(
            speaker,
            label="Live Arts MD July candidate invoice",
            path="/must/not/leak.pdf",
            delivery_mode="telegram_photo",
            artifact_variant="candidate",
            delivery_suppressed=True,
        )
        for speaker in ("maestro", "chief", "cassandra", "guardian", "niles", "hermes")
    }

    assert len(set(messages.values())) == len(messages)
    for speaker, message in messages.items():
        assert "did not deliver" in message.lower(), speaker
        assert "QuickLook" not in message
        assert "/must/not/leak.pdf" not in message
        assert agent_voice_profiles.require_voice_conformance(speaker, message)["passed"] is True


def test_remote_artifact_copy_preserves_each_addressed_agent_voice() -> None:
    import agent_voice_profiles

    messages = {
        speaker: agent_voice_profiles.artifact_ready_message_for_speaker(
            speaker,
            label="Live Arts MD July candidate invoice",
            path="/must/not/leak.pdf",
            delivery_mode="telegram_photo",
            artifact_variant="candidate",
        )
        for speaker in ("maestro", "chief", "cassandra", "guardian", "niles", "hermes")
    }

    assert len(set(messages.values())) == len(messages)
    for speaker, message in messages.items():
        assert "not final" in message.lower(), speaker
        assert "QuickLook" not in message
        assert "/must/not/leak.pdf" not in message
        assert agent_voice_profiles.require_voice_conformance(speaker, message)["passed"] is True


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

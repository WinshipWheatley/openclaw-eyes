import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import workflow_dod_reconciler as reconciler
import fleet_receipt_index


FIXED_NOW = "2026-07-16T17:40:00+00:00"


def _evidence(
    *,
    store: str,
    receipt_ref: str,
    subject_ref: str,
    claims: dict,
    writer: str = "openclaw_test_writer",
    valid_hash: bool = True,
) -> dict:
    content_hash = reconciler.evidence_content_hash(claims)
    if not valid_hash:
        content_hash = "0" * 64
    return {
        "store": store,
        "receipt_ref": receipt_ref,
        "writer": writer,
        "subject_ref": subject_ref,
        "claims": claims,
        "content_hash": content_hash,
    }


def test_install_builtin_registry_adds_three_versioned_data_entries(tmp_path: Path) -> None:
    ledger_path = tmp_path / "business_ops.sqlite"

    installed = reconciler.install_builtin_registry(
        db_path=ledger_path,
        installed_at=FIXED_NOW,
    )

    assert installed["status"] == "INSTALLED"
    assert installed["workflow_refs"] == [
        "capital_hilton_gig_invoice",
        "lamd_speaker_rental_monthly",
        "st_annes_invoice_e2e",
    ]
    st_annes = reconciler.load_registry_entry("st_annes_invoice_e2e", db_path=ledger_path)
    assert st_annes["registry_version"] == "2026-07-16.1"
    assert [item["milestone_ref"] for item in st_annes["milestones"]][:3] == [
        "invoice_artifact_verified",
        "operator_confirmed_pdf",
        "work_log_reconciled",
    ]
    assert st_annes["milestones"][1]["gate"] == "operator-word"
    assert st_annes["milestones"][5]["gate"] == "money/send"

    lamd = reconciler.load_registry_entry("lamd_speaker_rental_monthly", db_path=ledger_path)
    assert lamd["workflow_data"]["amount"] == 100
    assert lamd["workflow_data"]["recurrence_day"] == 16
    assert lamd["workflow_data"]["workbook_kind"] == "speaker_rentals"

    capital = reconciler.load_registry_entry("capital_hilton_gig_invoice", db_path=ledger_path)
    assert capital["workflow_data"]["confirmed_gig_dates"] == [
        "2026-06-12",
        "2026-06-19",
        "2026-07-02",
        "2026-07-03",
    ]
    assert capital["workflow_data"]["excluded_gig_dates"] == ["2026-06-26"]
    assert capital["workflow_data"]["verify_or_credit_dates"] == ["2026-06-05"]
    assert capital["workflow_data"]["next_invoice_dates"] == ["2026-07-10"]


def test_reconciler_accepts_only_allowlisted_hash_valid_evidence(tmp_path: Path) -> None:
    ledger_path = tmp_path / "business_ops.sqlite"
    reconciler.install_builtin_registry(db_path=ledger_path, installed_at=FIXED_NOW)
    evidence = [
        _evidence(
            store="workflow_package_queue_receipts",
            receipt_ref="workflow:locator-found",
            subject_ref="st_annes:2026-06",
            claims={"artifact_locator_status": "FOUND"},
        ),
        _evidence(
            store="random_json_file",
            receipt_ref="untrusted:operator-confirmed",
            subject_ref="st_annes:2026-06",
            claims={"operator_confirmed_pdf": True},
        ),
        _evidence(
            store="operator_truth_store",
            receipt_ref="operator-truth:bad-hash",
            subject_ref="st_annes:2026-06",
            claims={"operator_confirmed_pdf": True},
            valid_hash=False,
        ),
    ]

    result = reconciler.reconcile_workflow(
        "st_annes_invoice_e2e",
        evidence=evidence,
        db_path=ledger_path,
        generated_at=FIXED_NOW,
    )

    assert result["milestones"][0]["status"] == "PROVEN"
    assert result["frontier"]["milestone_ref"] == "operator_confirmed_pdf"
    assert result["frontier"]["status"] == "UNKNOWN"
    assert {item["reason"] for item in result["rejected_evidence"]} == {
        "content_hash_mismatch",
        "store_not_allowlisted",
    }
    assert result["machine_proof"]["advance_performed"] is False
    assert result["machine_proof"]["business_action_performed"] is False


def test_contradictory_receipts_block_and_cite_both_refs(tmp_path: Path) -> None:
    ledger_path = tmp_path / "business_ops.sqlite"
    reconciler.install_builtin_registry(db_path=ledger_path, installed_at=FIXED_NOW)
    evidence = [
        _evidence(
            store="workflow_package_queue_receipts",
            receipt_ref="workflow:locator-found",
            subject_ref="st_annes:2026-06",
            claims={"artifact_locator_status": "FOUND"},
        ),
        _evidence(
            store="operator_truth_store",
            receipt_ref="operator-truth:confirm",
            subject_ref="st_annes:2026-06",
            claims={"operator_confirmed_pdf": True},
            writer="operator_winship",
        ),
        _evidence(
            store="operator_truth_store",
            receipt_ref="operator-truth:deny",
            subject_ref="st_annes:2026-06",
            claims={"operator_confirmed_pdf": False},
            writer="operator_winship",
        ),
    ]

    result = reconciler.reconcile_workflow(
        "st_annes_invoice_e2e",
        evidence=evidence,
        db_path=ledger_path,
        generated_at=FIXED_NOW,
    )

    assert result["status"] == "BLOCKED"
    assert result["frontier"]["milestone_ref"] == "operator_confirmed_pdf"
    assert result["frontier"]["status"] == "BLOCKED"
    assert result["frontier"]["contradiction_receipt_refs"] == [
        "operator-truth:confirm",
        "operator-truth:deny",
    ]


def test_out_of_order_proof_reports_anomaly_without_inferring_operator_word(tmp_path: Path) -> None:
    ledger_path = tmp_path / "business_ops.sqlite"
    reconciler.install_builtin_registry(db_path=ledger_path, installed_at=FIXED_NOW)
    evidence = [
        _evidence(
            store="workflow_package_queue_receipts",
            receipt_ref="workflow:locator-found",
            subject_ref="st_annes:2026-06",
            claims={"artifact_locator_status": "FOUND"},
        ),
        _evidence(
            store="st_annes_truth_drift_receipts",
            receipt_ref="drift:in-sync",
            subject_ref="st_annes:2026-06",
            claims={"work_log_reconciled": True},
        ),
    ]

    result = reconciler.reconcile_workflow(
        "st_annes_invoice_e2e",
        evidence=evidence,
        db_path=ledger_path,
        generated_at=FIXED_NOW,
    )

    assert result["frontier"]["milestone_ref"] == "operator_confirmed_pdf"
    assert result["frontier"]["status"] == "UNKNOWN"
    assert result["milestones"][2]["status"] == "PROVEN"
    assert result["anomalies"] == [
        {
            "kind": "OUT_OF_ORDER_PROOF",
            "frontier_milestone_ref": "operator_confirmed_pdf",
            "later_proven_milestone_refs": ["work_log_reconciled"],
        }
    ]
    assert result["machine_proof"]["operator_word_inferred"] is False


def test_reconcile_is_read_only_and_idempotent(tmp_path: Path) -> None:
    ledger_path = tmp_path / "business_ops.sqlite"
    reconciler.install_builtin_registry(db_path=ledger_path, installed_at=FIXED_NOW)
    before = hashlib.sha256(ledger_path.read_bytes()).hexdigest()

    first = reconciler.reconcile_workflow(
        "st_annes_invoice_e2e",
        evidence=[],
        db_path=ledger_path,
        generated_at=FIXED_NOW,
    )
    second = reconciler.reconcile_workflow(
        "st_annes_invoice_e2e",
        evidence=[],
        db_path=ledger_path,
        generated_at=FIXED_NOW,
    )
    after = hashlib.sha256(ledger_path.read_bytes()).hexdigest()

    assert first == second
    assert before == after
    assert first["frontier"]["advance_mode"] == "RECOMMEND_ONLY"
    assert first["machine_proof"]["registry_mutation_performed"] is False
    assert first["machine_proof"]["receipt_mutation_performed"] is False


def test_shared_entry_parser_is_surface_agnostic() -> None:
    requests = (
        "run the st annes test",
        "Are we done with the St. Anne's invoice?",
        "whats going on with the st. annes invoice test? are we done what we need to test it?",
    )

    assert [reconciler.requested_workflow_ref(text) for text in requests] == [
        "st_annes_invoice_e2e",
        "st_annes_invoice_e2e",
        "st_annes_invoice_e2e",
    ]
    assert reconciler.requested_workflow_ref("send the St. Anne's invoice") is None


def test_registry_definition_hash_is_stable_and_matches_stored_json(tmp_path: Path) -> None:
    ledger_path = tmp_path / "business_ops.sqlite"
    reconciler.install_builtin_registry(db_path=ledger_path, installed_at=FIXED_NOW)

    entry = reconciler.load_registry_entry("st_annes_invoice_e2e", db_path=ledger_path)
    definition = dict(entry)
    stored_hash = definition.pop("definition_hash")
    definition.pop("installed_at")

    assert stored_hash == hashlib.sha256(
        json.dumps(definition, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def test_collect_trusted_evidence_normalizes_workflow_truth_and_drift_receipts(
    tmp_path: Path,
) -> None:
    response_dir = tmp_path / "responses"
    response_dir.mkdir()
    (response_dir / "openclaw_response_for_mac_locator.json").write_text(
        json.dumps(
            {
                "request_id": "locator-request",
                "detail_disclosure": {
                    "workflow_package_request_consumer": {
                        "workflow_ref": "st_annes_monthly_invoice_rollup",
                        "artifact_locator_result": {
                            "status": "FOUND",
                            "service_period": "2026-06",
                            "canonical_candidate": {
                                "pdf_sha256": "a" * 64,
                                "invoice_number": "3",
                            },
                            "machine_proof": {
                                "manifest_hashes_verified": True,
                                "external_action_performed": False,
                            },
                        },
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    truth_path = tmp_path / "operator_truth_store.json"
    truth_path.write_text(
        json.dumps(
            {
                "schema_version": "operator_truth_store_v0",
                "entities": {
                    "st_annes.invoice_2026_06.pdf_confirmation": {
                        "entity_key": "st_annes.invoice_2026_06.pdf_confirmation",
                        "value": "confirmed",
                        "provenance": "operator_corrected",
                        "source_surface": "operator_terminal",
                        "source_ref": "operator-msg:confirmed-pdf",
                        "source_text_hash": "b" * 64,
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    drift_path = tmp_path / "st_annes_invoice_truth_drift.json"
    drift_path.write_text(
        json.dumps(
            {
                "schema_version": "st_annes_invoice_truth_drift_v0",
                "generated_at": FIXED_NOW,
                "client_ref": "st_annes",
                "service_period": "2026-06",
                "status": "IN_SYNC",
                "workbook_truth": {"service_count": 7},
                "mirror_truth": {"confirmed_event_count": 7},
                "machine_proof": {
                    "workbook_hash_verified": True,
                    "workbook_mutation_performed": False,
                    "ledger_mutation_performed": False,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    evidence = reconciler.collect_trusted_evidence(
        response_dir=response_dir,
        fleet_receipt_index_path=tmp_path / "missing-fleet.sqlite3",
        operator_truth_path=truth_path,
        drift_receipt_path=drift_path,
        protected_generate_audit_path=tmp_path / "missing-protected.jsonl",
        broker_audit_path=tmp_path / "missing-broker.jsonl",
    )

    assert [(item["store"], item["claims"]) for item in evidence] == [
        ("operator_truth_store", {"operator_confirmed_pdf": True}),
        ("st_annes_truth_drift_receipts", {"work_log_reconciled": True}),
        ("workflow_package_queue_receipts", {"artifact_locator_status": "FOUND"}),
    ]
    ledger_path = tmp_path / "business_ops.sqlite"
    reconciler.install_builtin_registry(db_path=ledger_path, installed_at=FIXED_NOW)
    result = reconciler.reconcile_workflow(
        "st_annes_invoice_e2e",
        evidence=evidence,
        db_path=ledger_path,
        generated_at=FIXED_NOW,
    )
    assert [item["status"] for item in result["milestones"][:3]] == [
        "PROVEN",
        "PROVEN",
        "PROVEN",
    ]
    assert result["frontier"]["milestone_ref"] == "telegram_pdf_delivered"


def test_collect_trusted_evidence_rejects_ungraded_operator_truth(tmp_path: Path) -> None:
    truth_path = tmp_path / "operator_truth_store.json"
    truth_path.write_text(
        json.dumps(
            {
                "schema_version": "operator_truth_store_v0",
                "entities": {
                    "st_annes.invoice_2026_06.pdf_confirmation": {
                        "entity_key": "st_annes.invoice_2026_06.pdf_confirmation",
                        "value": "confirmed",
                        "provenance": "chat_guess",
                        "source_surface": "unknown",
                        "source_ref": "",
                        "source_text_hash": "not-a-hash",
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    evidence = reconciler.collect_trusted_evidence(
        response_dir=tmp_path / "responses",
        fleet_receipt_index_path=tmp_path / "missing-fleet.sqlite3",
        operator_truth_path=truth_path,
        drift_receipt_path=tmp_path / "missing-drift.json",
        protected_generate_audit_path=tmp_path / "missing-protected.jsonl",
        broker_audit_path=tmp_path / "missing-broker.jsonl",
    )

    assert evidence == []


def test_answered_claim_requires_matching_delivery_boundary_hash(tmp_path: Path) -> None:
    response_dir = tmp_path / "responses"
    response_dir.mkdir()
    request_id = "maestro_telegram_1665_ce0ca2b9fad1"
    answer = (
        "The St. Anne's invoice dry-run passed and nothing was sent. "
        "The June workbook has 7 services totaling $875, while the work-log mirror has 0 confirmed."
    )
    (response_dir / f"openclaw_response_for_mac_{request_id}.json").write_text(
        json.dumps(
            {
                "source_request_id": request_id,
                "workflow_ref": "st_annes_monthly_invoice_rollup",
                "operator_message": answer,
                "one_line_answer": answer,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    fleet_path = tmp_path / "fleet.sqlite3"

    response_only = reconciler.collect_trusted_evidence(
        response_dir=response_dir,
        fleet_receipt_index_path=fleet_path,
        operator_truth_path=tmp_path / "missing-truth.json",
        drift_receipt_path=tmp_path / "missing-drift.json",
        protected_generate_audit_path=tmp_path / "missing-protected.jsonl",
        broker_audit_path=tmp_path / "missing-broker.jsonl",
    )
    assert not any(
        item["claims"].get("operator_answer_delivered") is True
        for item in response_only
    )

    fleet_receipt_index.register_delivered_text_receipt(
        surface="operator_maestro_chat",
        bot_identity="maestro",
        chat_id="chat-42",
        source_message_id="1665",
        delivered_message_id="9004",
        source_request_id=request_id,
        delivered_text="A different answer reached the channel.",
        delivery_succeeded=True,
        delivered_at=FIXED_NOW,
        db_path=fleet_path,
    )
    mismatched = reconciler.collect_trusted_evidence(
        response_dir=response_dir,
        fleet_receipt_index_path=fleet_path,
        operator_truth_path=tmp_path / "missing-truth.json",
        drift_receipt_path=tmp_path / "missing-drift.json",
        protected_generate_audit_path=tmp_path / "missing-protected.jsonl",
        broker_audit_path=tmp_path / "missing-broker.jsonl",
    )
    assert not any(
        item["claims"].get("operator_answer_delivered") is True
        for item in mismatched
    )

    fleet_receipt_index.register_delivered_text_receipt(
        surface="operator_maestro_chat",
        bot_identity="maestro",
        chat_id="chat-42",
        source_message_id="1665",
        delivered_message_id="9005",
        source_request_id=request_id,
        delivered_text=answer,
        delivery_succeeded=True,
        delivered_at=FIXED_NOW,
        db_path=fleet_path,
    )

    evidence = reconciler.collect_trusted_evidence(
        response_dir=response_dir,
        fleet_receipt_index_path=fleet_path,
        operator_truth_path=tmp_path / "missing-truth.json",
        drift_receipt_path=tmp_path / "missing-drift.json",
        protected_generate_audit_path=tmp_path / "missing-protected.jsonl",
        broker_audit_path=tmp_path / "missing-broker.jsonl",
    )
    delivered = [item for item in evidence if item["store"] == "fleet_receipt_index"]

    assert len(delivered) == 1
    assert delivered[0]["writer"] == "maestro_listener"
    assert delivered[0]["claims"] == {"operator_answer_delivered": True}
    assert delivered[0]["receipt_ref"] == "fleet-delivery:9005"


def test_cli_installs_registry_into_explicit_ledger(tmp_path: Path, capsys) -> None:
    ledger_path = tmp_path / "business_ops.sqlite"

    assert reconciler.main(
        [
            "--install",
            "--db",
            str(ledger_path),
            "--generated-at",
            FIXED_NOW,
        ]
    ) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "INSTALLED"
    assert output["workflow_refs"] == [
        "capital_hilton_gig_invoice",
        "lamd_speaker_rental_monthly",
        "st_annes_invoice_e2e",
    ]
    assert reconciler.load_registry_entry(
        "st_annes_invoice_e2e",
        db_path=ledger_path,
    ) is not None

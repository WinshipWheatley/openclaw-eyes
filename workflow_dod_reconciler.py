"""Read-only definition-of-done registry reconciler.

Registry installation is explicit and ledger-backed. Reconciliation only measures
trusted receipts, identifies the true frontier, and recommends one next advance. It
does not execute an advance or grant authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import business_ops_ledger
import fleet_receipt_index


SCHEMA_VERSION = "workflow_dod_reconciler_v0"
REGISTRY_VERSION = "2026-07-16.1"
REGISTRY_SOURCE_REF = "FABLE-DIRECTIVE-DOD-REGISTRY-RECONCILER-20260716"
DEFAULT_RESPONSE_DIR = Path("/mnt/e/openclaw/mission_control_responses/to_mac")
DEFAULT_FLEET_RECEIPT_INDEX_PATH = fleet_receipt_index.DEFAULT_SQLITE_PATH
DEFAULT_OPERATOR_TRUTH_PATH = Path("/mnt/c/OpenClaw/logs/operator_truth_store.json")
DEFAULT_DRIFT_RECEIPT_PATH = Path("generated/read_models/st_annes_invoice_truth_drift.json")
DEFAULT_PROTECTED_GENERATE_AUDIT_PATH = Path(
    "/mnt/c/OpenClaw/logs/protected_generate_audit.jsonl"
)
DEFAULT_BROKER_AUDIT_PATH = Path("/mnt/c/OpenClaw/logs/google_access_audit.jsonl")
TRUSTED_RECEIPT_STORES = frozenset(
    {
        "protected_generate_audit",
        "workflow_package_queue_receipts",
        "fleet_receipt_index",
        "operator_truth_store",
        "broker_google_access_audit",
        "st_annes_truth_drift_receipts",
    }
)


def _condition(
    claim: str,
    expected: Any,
    *,
    stores: Sequence[str],
    subject_ref: str,
) -> dict[str, Any]:
    return {
        "claim": claim,
        "equals": expected,
        "stores": list(stores),
        "subject_ref": subject_ref,
    }


def _milestone(
    milestone_ref: str,
    label: str,
    *,
    gate: str,
    advance: str,
    conditions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "milestone_ref": milestone_ref,
        "label": label,
        "gate": gate,
        "advance": advance,
        "verify": {"all": [dict(item) for item in conditions]},
    }


_ST_ANNES_SUBJECT = "st_annes:2026-06"


BUILTIN_REGISTRY_ENTRIES: tuple[dict[str, Any], ...] = (
    {
        "schema_version": "workflow_dod_registry_entry_v0",
        "workflow_ref": "st_annes_invoice_e2e",
        "registry_version": REGISTRY_VERSION,
        "label": "St. Anne's invoice end-to-end",
        "workflow_data": {
            "client_ref": "st_annes",
            "service_period": "2026-06",
            "invoice_number": "3",
            "amount": 875,
            "test_recipient": "winshiplive@gmail.com",
            "live_recipient": "draper.carter@gmail.com",
            "live_cc": "winshiplive@gmail.com",
        },
        "milestones": [
            _milestone(
                "invoice_artifact_verified",
                "Canonical June invoice PDF verified",
                gate="auto",
                advance="Run the allowlisted manifest and hash locator.",
                conditions=[
                    _condition(
                        "artifact_locator_status",
                        "FOUND",
                        stores=("workflow_package_queue_receipts",),
                        subject_ref=_ST_ANNES_SUBJECT,
                    )
                ],
            ),
            _milestone(
                "operator_confirmed_pdf",
                "Operator confirmed the PDF",
                gate="operator-word",
                advance="Ask the operator to confirm or deny the displayed PDF.",
                conditions=[
                    _condition(
                        "operator_confirmed_pdf",
                        True,
                        stores=("operator_truth_store",),
                        subject_ref=_ST_ANNES_SUBJECT,
                    )
                ],
            ),
            _milestone(
                "work_log_reconciled",
                "Workbook and work-log mirror agree",
                gate="auto",
                advance="Prepare the hash-verified workbook to work-log reconciliation.",
                conditions=[
                    _condition(
                        "work_log_reconciled",
                        True,
                        stores=("st_annes_truth_drift_receipts",),
                        subject_ref=_ST_ANNES_SUBJECT,
                    )
                ],
            ),
            _milestone(
                "telegram_pdf_delivered",
                "Invoice proof delivered to the operator's phone",
                gate="operator-word",
                advance="Pop the verified PDF through the bound proof surface.",
                conditions=[
                    _condition(
                        "telegram_pdf_delivered",
                        True,
                        stores=("fleet_receipt_index",),
                        subject_ref=_ST_ANNES_SUBJECT,
                    )
                ],
            ),
            _milestone(
                "clara_email_draft_ready",
                "Clara Reid test email draft and attachment are ready",
                gate="auto",
                advance="Prepare Clara Reid's bounded draft with the verified PDF.",
                conditions=[
                    _condition(
                        "clara_email_draft_ready",
                        True,
                        stores=("workflow_package_queue_receipts",),
                        subject_ref=_ST_ANNES_SUBJECT,
                    )
                ],
            ),
            _milestone(
                "guardian_approval_received",
                "Guardian-line test-send approval received",
                gate="money/send",
                advance="Request approval through Guardian's Telegram line.",
                conditions=[
                    _condition(
                        "guardian_approval_received",
                        True,
                        stores=("fleet_receipt_index", "operator_truth_store"),
                        subject_ref=_ST_ANNES_SUBJECT,
                    )
                ],
            ),
            _milestone(
                "test_loopback_sent",
                "Test-mode email sent only to the operator",
                gate="money/send",
                advance="Send the approved test-mode loopback to the locked self recipient.",
                conditions=[
                    _condition(
                        "test_loopback_sent",
                        True,
                        stores=("broker_google_access_audit",),
                        subject_ref=_ST_ANNES_SUBJECT,
                    )
                ],
            ),
            _milestone(
                "broker_self_check_passed",
                "Returned email content and attachment verified",
                gate="auto",
                advance="Read the broker audit and compare subject, body, and attachment hash.",
                conditions=[
                    _condition(
                        "broker_self_check_passed",
                        True,
                        stores=("broker_google_access_audit",),
                        subject_ref=_ST_ANNES_SUBJECT,
                    )
                ],
            ),
            _milestone(
                "live_graduation_word_received",
                "Explicit out-of-testmode instruction received",
                gate="operator-word",
                advance="Ask for the exact out-of-testmode instruction through a non-Guardian agent.",
                conditions=[
                    _condition(
                        "live_graduation_word_received",
                        True,
                        stores=("operator_truth_store",),
                        subject_ref=_ST_ANNES_SUBJECT,
                    )
                ],
            ),
            _milestone(
                "live_invoice_sent",
                "Live invoice sent to Draper with operator CC",
                gate="money/send",
                advance="Send only after the exact graduation word and live approval gate.",
                conditions=[
                    _condition(
                        "live_invoice_sent",
                        True,
                        stores=("broker_google_access_audit", "fleet_receipt_index"),
                        subject_ref=_ST_ANNES_SUBJECT,
                    )
                ],
            ),
            _milestone(
                "treasurer_ack_observed",
                "Glenn acknowledgment observed",
                gate="auto",
                advance="Monitor for Draper's reply or Glenn's acknowledgment.",
                conditions=[
                    _condition(
                        "treasurer_ack_observed",
                        True,
                        stores=("broker_google_access_audit",),
                        subject_ref=_ST_ANNES_SUBJECT,
                    )
                ],
            ),
            _milestone(
                "check_observed",
                "Check receipt or processed ledger proof observed",
                gate="money/send",
                advance="Wait for operator-posted check proof or verified ledger processing.",
                conditions=[
                    _condition(
                        "check_observed",
                        True,
                        stores=("operator_truth_store", "workflow_package_queue_receipts"),
                        subject_ref=_ST_ANNES_SUBJECT,
                    )
                ],
            ),
            _milestone(
                "rollover_resolved",
                "Late-payment rollover state resolved",
                gate="auto",
                advance="Remove paid rollover items from the next invoice when applicable.",
                conditions=[
                    _condition(
                        "rollover_resolved",
                        True,
                        stores=("workflow_package_queue_receipts",),
                        subject_ref=_ST_ANNES_SUBJECT,
                    )
                ],
            ),
        ],
    },
    {
        "schema_version": "workflow_dod_registry_entry_v0",
        "workflow_ref": "lamd_speaker_rental_monthly",
        "registry_version": REGISTRY_VERSION,
        "label": "Live Arts MD monthly speaker rental invoice",
        "workflow_data": {
            "client_ref": "live_arts_md",
            "amount": 100,
            "recurrence_day": 16,
            "workbook_kind": "speaker_rentals",
            "test_mode_required": True,
        },
        "milestones": [
            _milestone(
                "speaker_rental_workbook_verified",
                "Speaker-rentals workbook invoice verified",
                gate="auto",
                advance="Locate and verify the monthly speaker-rentals workbook artifact.",
                conditions=[
                    _condition(
                        "speaker_rental_workbook_verified",
                        True,
                        stores=("workflow_package_queue_receipts",),
                        subject_ref="live_arts_md:speaker_rental:monthly",
                    )
                ],
            )
        ],
    },
    {
        "schema_version": "workflow_dod_registry_entry_v0",
        "workflow_ref": "capital_hilton_gig_invoice",
        "registry_version": REGISTRY_VERSION,
        "label": "Capital Hilton gig invoice",
        "workflow_data": {
            "client_ref": "capital_hilton",
            "confirmed_gig_dates": [
                "2026-06-12",
                "2026-06-19",
                "2026-07-02",
                "2026-07-03",
            ],
            "excluded_gig_dates": ["2026-06-26"],
            "verify_or_credit_dates": ["2026-06-05"],
            "next_invoice_dates": ["2026-07-10"],
            "new_po_question_pending": True,
        },
        "milestones": [
            _milestone(
                "current_invoice_dates_verified",
                "Current invoice gig dates verified from the Mac workbook",
                gate="auto",
                advance="Read the Mac workbook and resolve the June 5 verify-or-credit question.",
                conditions=[
                    _condition(
                        "current_invoice_dates_verified",
                        True,
                        stores=("workflow_package_queue_receipts", "operator_truth_store"),
                        subject_ref="capital_hilton:current_invoice",
                    )
                ],
            )
        ],
    },
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _definition_hash(definition: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(definition).encode("utf-8")).hexdigest()


def evidence_content_hash(claims: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(dict(claims)).encode("utf-8")).hexdigest()


def _json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalized_evidence(
    *,
    store: str,
    receipt_ref: str,
    writer: str,
    subject_ref: str,
    claims: Mapping[str, Any],
) -> dict[str, Any]:
    claim_dict = dict(claims)
    return {
        "store": store,
        "receipt_ref": receipt_ref,
        "writer": writer,
        "subject_ref": subject_ref,
        "claims": claim_dict,
        "content_hash": evidence_content_hash(claim_dict),
    }


def _workflow_response_evidence(response_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not response_dir.is_dir():
        return results
    for path in sorted(response_dir.glob("openclaw_response_for_mac_*.json")):
        payload = _json_object(path)
        details = payload.get("detail_disclosure")
        consumer = (
            details.get("workflow_package_request_consumer")
            if isinstance(details, Mapping)
            else None
        )
        if not isinstance(consumer, Mapping):
            continue
        locator = consumer.get("artifact_locator_result")
        if not isinstance(locator, Mapping) or locator.get("status") != "FOUND":
            continue
        proof = locator.get("machine_proof")
        candidate = locator.get("canonical_candidate")
        if not isinstance(proof, Mapping) or not isinstance(candidate, Mapping):
            continue
        if proof.get("manifest_hashes_verified") is not True:
            continue
        if proof.get("external_action_performed") is not False:
            continue
        if not re.fullmatch(r"[0-9a-f]{64}", str(candidate.get("pdf_sha256") or "")):
            continue
        service_period = str(locator.get("service_period") or candidate.get("service_period") or "")
        if service_period != "2026-06":
            continue
        receipt_ref = str(payload.get("request_id") or path.name)
        results.append(
            _normalized_evidence(
                store="workflow_package_queue_receipts",
                receipt_ref=f"workflow-response:{receipt_ref}",
                writer="workflow_package_request_consumer",
                subject_ref=_ST_ANNES_SUBJECT,
                claims={"artifact_locator_status": "FOUND"},
            )
        )
    return results


def _delivery_boundary_evidence(
    response_dir: Path,
    fleet_receipt_index_path: Path,
) -> list[dict[str, Any]]:
    try:
        rows = fleet_receipt_index.read_delivered_text_receipts(
            db_path=fleet_receipt_index_path,
        )
    except fleet_receipt_index.ReceiptIndexUnavailable:
        return []
    results: list[dict[str, Any]] = []
    for row in rows:
        if row.get("surface") != "operator_maestro_chat":
            continue
        if row.get("bot_identity") != "maestro" or row.get("delivery_succeeded") != 1:
            continue
        request_id = str(row.get("source_request_id") or "").strip()
        delivered_message_id = str(row.get("delivered_message_id") or "").strip()
        delivered_hash = str(row.get("delivered_text_hash") or "").strip().lower()
        if not request_id or not delivered_message_id:
            continue
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", delivered_hash):
            continue
        payload = _json_object(
            response_dir / f"openclaw_response_for_mac_{request_id}.json"
        )
        if not payload:
            continue
        details = payload.get("detail_disclosure")
        layered = (
            details.get("layered_response_fields")
            if isinstance(details, Mapping)
            else None
        )
        workflow_refs = {
            str(payload.get("workflow_ref") or ""),
            str(payload.get("client_ref") or ""),
            str(layered.get("workflow_ref") or "") if isinstance(layered, Mapping) else "",
            str(layered.get("client_ref") or "") if isinstance(layered, Mapping) else "",
        }
        if not any("st_annes" in ref.casefold() for ref in workflow_refs):
            continue
        candidates = [
            payload.get("operator_message"),
            payload.get("one_line_answer"),
            payload.get("plain_summary"),
            layered.get("operator_message") if isinstance(layered, Mapping) else None,
            layered.get("one_line_answer") if isinstance(layered, Mapping) else None,
            layered.get("eliwinship") if isinstance(layered, Mapping) else None,
        ]
        candidate_hashes = {
            "sha256:" + hashlib.sha256(str(text).encode("utf-8")).hexdigest()
            for text in candidates
            if isinstance(text, str) and text
        }
        if delivered_hash not in candidate_hashes:
            continue
        results.append(
            _normalized_evidence(
                store="fleet_receipt_index",
                receipt_ref=f"fleet-delivery:{delivered_message_id}",
                writer="maestro_listener",
                subject_ref=_ST_ANNES_SUBJECT,
                claims={"operator_answer_delivered": True},
            )
        )
    return results


def _operator_truth_evidence(path: Path) -> list[dict[str, Any]]:
    payload = _json_object(path)
    if payload.get("schema_version") != "operator_truth_store_v0":
        return []
    entities = payload.get("entities")
    if not isinstance(entities, Mapping):
        return []
    record = entities.get("st_annes.invoice_2026_06.pdf_confirmation")
    if not isinstance(record, Mapping):
        return []
    if record.get("provenance") != "operator_corrected":
        return []
    source_hash = str(record.get("source_text_hash") or "").strip().lower()
    source_ref = str(record.get("source_ref") or "").strip()
    source_surface = str(record.get("source_surface") or "").strip()
    if not re.fullmatch(r"[0-9a-f]{64}", source_hash) or not source_ref or not source_surface:
        return []
    value = str(record.get("value") or "").strip().lower()
    artifact_hash = ""
    if value in {"confirmed", "denied"}:
        confirmed = value == "confirmed"
    else:
        hash_match = re.search(r"\bsha-?256\s*:?[ ]*([0-9a-f]{64})\b", value)
        if hash_match is None or "invoice pdf" not in value:
            return []
        if value.startswith("confirmed "):
            confirmed = True
        elif value.startswith("denied "):
            confirmed = False
        else:
            return []
        artifact_hash = hash_match.group(1)
    claims: dict[str, Any] = {"operator_confirmed_pdf": confirmed}
    if artifact_hash:
        claims["operator_confirmed_pdf_sha256"] = artifact_hash
    return [
        _normalized_evidence(
            store="operator_truth_store",
            receipt_ref=f"operator-truth:{source_ref}",
            writer="operator_winship",
            subject_ref=_ST_ANNES_SUBJECT,
            claims=claims,
        )
    ]


def _drift_evidence(path: Path) -> list[dict[str, Any]]:
    payload = _json_object(path)
    if payload.get("schema_version") != "st_annes_invoice_truth_drift_v0":
        return []
    if payload.get("client_ref") != "st_annes" or payload.get("service_period") != "2026-06":
        return []
    proof = payload.get("machine_proof")
    workbook = payload.get("workbook_truth")
    mirror = payload.get("mirror_truth")
    if not all(isinstance(item, Mapping) for item in (proof, workbook, mirror)):
        return []
    if proof.get("workbook_hash_verified") is not True:
        return []
    if proof.get("workbook_mutation_performed") is not False:
        return []
    if proof.get("ledger_mutation_performed") is not False:
        return []
    status = str(payload.get("status") or "")
    if status not in {"IN_SYNC", "DRIFT_DETECTED"}:
        return []
    work_count = workbook.get("service_count")
    mirror_count = mirror.get("confirmed_event_count")
    reconciled = status == "IN_SYNC" and work_count == mirror_count
    generated_at = str(payload.get("generated_at") or "unknown")
    return [
        _normalized_evidence(
            store="st_annes_truth_drift_receipts",
            receipt_ref=f"st-annes-drift:{generated_at}",
            writer="st_annes_invoice_truth_drift",
            subject_ref=_ST_ANNES_SUBJECT,
            claims={"work_log_reconciled": reconciled},
        )
    ]


def _structured_audit_evidence(path: Path, *, store: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return results
    for index, line in enumerate(lines, start=1):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, Mapping):
            continue
        claims = payload.get("dod_claims")
        if not isinstance(claims, Mapping) or not claims:
            continue
        subject_ref = str(payload.get("subject_ref") or "").strip()
        writer = str(payload.get("writer") or payload.get("actor") or "").strip()
        receipt_ref = str(
            payload.get("receipt_ref")
            or payload.get("audit_ref")
            or f"{Path(path).name}:{index}"
        ).strip()
        if not subject_ref or not writer:
            continue
        results.append(
            _normalized_evidence(
                store=store,
                receipt_ref=receipt_ref,
                writer=writer,
                subject_ref=subject_ref,
                claims=claims,
            )
        )
    return results


def collect_trusted_evidence(
    *,
    response_dir: Path = DEFAULT_RESPONSE_DIR,
    fleet_receipt_index_path: Path = DEFAULT_FLEET_RECEIPT_INDEX_PATH,
    operator_truth_path: Path = DEFAULT_OPERATOR_TRUTH_PATH,
    drift_receipt_path: Path = DEFAULT_DRIFT_RECEIPT_PATH,
    protected_generate_audit_path: Path = DEFAULT_PROTECTED_GENERATE_AUDIT_PATH,
    broker_audit_path: Path = DEFAULT_BROKER_AUDIT_PATH,
) -> list[dict[str, Any]]:
    evidence = [
        *_workflow_response_evidence(Path(response_dir)),
        *_delivery_boundary_evidence(
            Path(response_dir),
            Path(fleet_receipt_index_path),
        ),
        *_operator_truth_evidence(Path(operator_truth_path)),
        *_drift_evidence(Path(drift_receipt_path)),
        *_structured_audit_evidence(
            Path(protected_generate_audit_path),
            store="protected_generate_audit",
        ),
        *_structured_audit_evidence(
            Path(broker_audit_path),
            store="broker_google_access_audit",
        ),
    ]
    evidence.sort(key=lambda item: (item["store"], item["receipt_ref"]))
    return evidence


def install_builtin_registry(
    *,
    db_path: str | Path,
    installed_at: str,
) -> dict[str, Any]:
    installed: list[str] = []
    for definition in BUILTIN_REGISTRY_ENTRIES:
        if not business_ops_ledger.record_workflow_dod_registry_entry(
            dict(definition),
            definition_hash=_definition_hash(definition),
            source_ref=REGISTRY_SOURCE_REF,
            installed_at=installed_at,
            db_path=db_path,
        ):
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "INSTALL_FAILED",
                "workflow_refs": installed,
            }
        installed.append(str(definition["workflow_ref"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "INSTALLED",
        "workflow_refs": sorted(installed),
    }


def load_registry_entry(
    workflow_ref: str,
    *,
    db_path: str | Path,
) -> dict[str, Any] | None:
    return business_ops_ledger.get_workflow_dod_registry_entry(
        workflow_ref,
        db_path=db_path,
    )


def _validate_evidence(
    raw_evidence: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for item in raw_evidence:
        store = str(item.get("store") or "").strip()
        receipt_ref = str(item.get("receipt_ref") or "").strip()
        reason = ""
        claims = item.get("claims")
        if store not in TRUSTED_RECEIPT_STORES:
            reason = "store_not_allowlisted"
        elif not receipt_ref:
            reason = "receipt_ref_missing"
        elif not str(item.get("writer") or "").strip():
            reason = "writer_missing"
        elif not str(item.get("subject_ref") or "").strip():
            reason = "subject_ref_missing"
        elif not isinstance(claims, Mapping):
            reason = "claims_missing"
        else:
            content_hash = str(item.get("content_hash") or "").strip().lower()
            if content_hash and content_hash != evidence_content_hash(claims):
                reason = "content_hash_mismatch"
        if reason:
            rejected.append({"receipt_ref": receipt_ref, "store": store, "reason": reason})
            continue
        accepted.append(
            {
                "store": store,
                "receipt_ref": receipt_ref,
                "writer": str(item.get("writer") or "").strip(),
                "subject_ref": str(item.get("subject_ref") or "").strip(),
                "claims": dict(claims or {}),
                "content_hash": str(item.get("content_hash") or "").strip().lower(),
            }
        )
    accepted.sort(key=lambda item: (item["store"], item["receipt_ref"]))
    rejected.sort(key=lambda item: (item["store"], item["receipt_ref"], item["reason"]))
    return accepted, rejected


def _measure_condition(
    condition: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    claim = str(condition.get("claim") or "")
    subject_ref = str(condition.get("subject_ref") or "")
    stores = {str(item) for item in condition.get("stores") or []}
    matching = [
        item
        for item in evidence
        if item.get("store") in stores
        and item.get("subject_ref") == subject_ref
        and claim in (item.get("claims") or {})
    ]
    values: dict[str, list[str]] = {}
    for item in matching:
        value_key = _canonical_json((item.get("claims") or {}).get(claim))
        values.setdefault(value_key, []).append(str(item.get("receipt_ref") or ""))
    all_refs = sorted({ref for refs in values.values() for ref in refs})
    if len(values) > 1:
        return {
            "status": "BLOCKED",
            "claim": claim,
            "receipt_refs": all_refs,
            "contradiction_receipt_refs": all_refs,
        }
    expected_key = _canonical_json(condition.get("equals"))
    if expected_key in values:
        return {
            "status": "PROVEN",
            "claim": claim,
            "receipt_refs": sorted(values[expected_key]),
            "contradiction_receipt_refs": [],
        }
    return {
        "status": "UNKNOWN",
        "claim": claim,
        "receipt_refs": all_refs,
        "contradiction_receipt_refs": [],
    }


def _measure_milestone(
    milestone: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    verify = milestone.get("verify") if isinstance(milestone.get("verify"), Mapping) else {}
    conditions = [
        _measure_condition(condition, evidence)
        for condition in verify.get("all") or []
        if isinstance(condition, Mapping)
    ]
    statuses = {item["status"] for item in conditions}
    status = "BLOCKED" if "BLOCKED" in statuses else "PROVEN" if conditions and statuses == {"PROVEN"} else "UNKNOWN"
    receipt_refs = sorted({ref for item in conditions for ref in item["receipt_refs"]})
    contradiction_refs = sorted(
        {ref for item in conditions for ref in item["contradiction_receipt_refs"]}
    )
    return {
        "milestone_ref": str(milestone.get("milestone_ref") or ""),
        "label": str(milestone.get("label") or ""),
        "gate": str(milestone.get("gate") or "auto"),
        "advance": str(milestone.get("advance") or ""),
        "status": status,
        "receipt_refs": receipt_refs,
        "contradiction_receipt_refs": contradiction_refs,
    }


def reconcile_workflow(
    workflow_ref: str,
    *,
    evidence: Sequence[Mapping[str, Any]],
    db_path: str | Path,
    generated_at: str,
) -> dict[str, Any]:
    definition = load_registry_entry(workflow_ref, db_path=db_path)
    if definition is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "workflow_ref": workflow_ref,
            "status": "BLOCKED",
            "reason": "registry_entry_missing",
            "milestones": [],
            "frontier": None,
            "anomalies": [],
            "rejected_evidence": [],
            "generated_at": generated_at,
            "machine_proof": {
                "advance_performed": False,
                "business_action_performed": False,
                "operator_word_inferred": False,
                "registry_mutation_performed": False,
                "receipt_mutation_performed": False,
            },
        }
    accepted, rejected = _validate_evidence(evidence)
    milestones = [
        _measure_milestone(item, accepted)
        for item in definition.get("milestones") or []
        if isinstance(item, Mapping)
    ]
    frontier_index = next(
        (index for index, item in enumerate(milestones) if item["status"] != "PROVEN"),
        None,
    )
    frontier = dict(milestones[frontier_index]) if frontier_index is not None else None
    if frontier is not None:
        frontier["advance_mode"] = "RECOMMEND_ONLY"
    anomalies: list[dict[str, Any]] = []
    if frontier_index is not None:
        later_proven = [
            item["milestone_ref"]
            for item in milestones[frontier_index + 1 :]
            if item["status"] == "PROVEN"
        ]
        if later_proven:
            anomalies.append(
                {
                    "kind": "OUT_OF_ORDER_PROOF",
                    "frontier_milestone_ref": milestones[frontier_index]["milestone_ref"],
                    "later_proven_milestone_refs": later_proven,
                }
            )
    status = (
        "COMPLETE"
        if frontier is None
        else "BLOCKED"
        if frontier["status"] == "BLOCKED"
        else "IN_PROGRESS"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "workflow_ref": workflow_ref,
        "registry_version": definition.get("registry_version"),
        "definition_hash": definition.get("definition_hash"),
        "status": status,
        "milestones": milestones,
        "frontier": frontier,
        "anomalies": anomalies,
        "rejected_evidence": rejected,
        "accepted_evidence_count": len(accepted),
        "generated_at": generated_at,
        "machine_proof": {
            "trusted_store_allowlist_enforced": True,
            "advance_performed": False,
            "business_action_performed": False,
            "operator_word_inferred": False,
            "registry_mutation_performed": False,
            "receipt_mutation_performed": False,
        },
    }


def requested_workflow_ref(source_text: str) -> str | None:
    text = " ".join(
        str(source_text or "")
        .translate(str.maketrans({"\u2018": "'", "\u2019": "'"}))
        .strip()
        .lower()
        .split()
    )
    st_annes = bool(re.search(r"\bst\.?\s+anne(?:'s|s)?\b", text))
    done_or_test = (
        "run the test" in text
        or "run the st annes test" in text
        or "are we done" in text
        or ("whats going on" in text and "test" in text)
        or ("what's going on" in text and "test" in text)
    )
    return "st_annes_invoice_e2e" if st_annes and done_or_test else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--generated-at", required=True)
    args = parser.parse_args(argv)
    if not args.install:
        parser.error("--install is required")
    result = install_builtin_registry(
        db_path=args.db,
        installed_at=args.generated_at,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "INSTALLED" else 2


__all__ = [
    "BUILTIN_REGISTRY_ENTRIES",
    "SCHEMA_VERSION",
    "TRUSTED_RECEIPT_STORES",
    "collect_trusted_evidence",
    "evidence_content_hash",
    "install_builtin_registry",
    "load_registry_entry",
    "main",
    "reconcile_workflow",
    "requested_workflow_ref",
]


if __name__ == "__main__":
    raise SystemExit(main())

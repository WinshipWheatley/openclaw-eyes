import hashlib
import json

from scripts.build_invoice_proof_artifacts import (
    SCHEMA_VERSION,
    artifact_from_gig_dir,
    build_invoice_proof_artifacts,
    stable_json,
)

PDF_BYTES = b"%PDF-1.4\nfake reynolds invoice body for test\n%%EOF\n"


def _make_gig_dir(root, name, *, venue, date, fee, with_pdf=True):
    gig = root / name
    gig.mkdir(parents=True)
    (gig / "gig_facts.json").write_text(
        json.dumps(
            {
                "record_type": "gig_intake",
                "gig": {
                    "venue_name": venue,
                    "date": date,
                    "fee_amount": fee,
                    "currency": "USD",
                },
            }
        )
    )
    if with_pdf:
        (gig / f"Invoice_{name}.pdf").write_bytes(PDF_BYTES)
    return gig


def test_entry_is_generated_from_real_file_metadata(tmp_path):
    gig = _make_gig_dir(tmp_path, "reynolds", venue="Reynolds Tavern", date="2026-06-27", fee="250.00")
    entry = artifact_from_gig_dir(gig)

    assert entry is not None
    assert entry["kind"] == "branded_invoice_pdf"
    assert entry["provenance"] == "openclaw_produced"
    assert entry["client_ref"] == "reynolds_tavern"
    assert entry["client_display"] == "Reynolds Tavern"
    assert entry["world_ref"] == "finance"
    assert entry["gig_date"] == "2026-06-27"
    assert entry["amount"] == "250.00"
    # real hash of the real file on disk — not hand-authored
    assert entry["sha256"] == "sha256:" + hashlib.sha256(PDF_BYTES).hexdigest()
    assert entry["size_bytes"] == len(PDF_BYTES)
    assert entry["mac_artifact_path"].endswith("Invoice_reynolds.pdf")
    assert entry["path_exists"] is True
    # registering a proof never sends or pays
    assert entry["authority_boundary"] == {
        "sent": False,
        "paid": False,
        "email_send_allowed": False,
        "outward_action_allowed": False,
    }
    assert "show me the proof" in entry["resolve_on_intents"]


def test_bridge_path_maps_share_root():
    # a real share path maps deterministically to the PC bridge path
    from scripts.build_invoice_proof_artifacts import _bridge_path

    mac = "/Volumes/openclaw_e/orchestration/artifacts/reynolds/x.pdf"
    assert _bridge_path(mac) == "/mnt/e/openclaw/orchestration/artifacts/reynolds/x.pdf"
    # non-share paths pass through unchanged
    assert _bridge_path("/tmp/x.pdf") == "/tmp/x.pdf"


def test_build_scans_roots_and_marks_latest_active(tmp_path):
    _make_gig_dir(tmp_path, "reynolds", venue="Reynolds Tavern", date="2026-06-27", fee="250.00")
    _make_gig_dir(tmp_path, "earlier_gig", venue="Earlier Venue", date="2026-05-01", fee="180.00")

    model = build_invoice_proof_artifacts(roots=[str(tmp_path)])
    assert model["schema_version"] == SCHEMA_VERSION
    assert model["artifact_count"] == 2

    active = [a for a in model["artifacts"] if a["is_active_invoice"]]
    assert len(active) == 1
    # latest gig_date is the active invoice
    assert active[0]["gig_date"] == "2026-06-27"


def test_non_gig_and_pdfless_dirs_are_skipped(tmp_path):
    # folder with no gig_facts.json
    (tmp_path / "random_folder").mkdir()
    (tmp_path / "random_folder" / "notes.txt").write_text("hi")
    # gig facts but no produced PDF yet
    _make_gig_dir(tmp_path, "pending_gig", venue="Pending", date="2026-07-01", fee="300.00", with_pdf=False)

    model = build_invoice_proof_artifacts(roots=[str(tmp_path)])
    assert model["artifact_count"] == 0


def test_output_is_deterministic(tmp_path):
    _make_gig_dir(tmp_path, "reynolds", venue="Reynolds Tavern", date="2026-06-27", fee="250.00")
    a = stable_json(build_invoice_proof_artifacts(roots=[str(tmp_path)]))
    b = stable_json(build_invoice_proof_artifacts(roots=[str(tmp_path)]))
    assert a == b


def test_missing_root_is_ignored_not_error():
    model = build_invoice_proof_artifacts(roots=["/nonexistent/path/for/test"])
    assert model["artifact_count"] == 0

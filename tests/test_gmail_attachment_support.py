"""IB-2: the broker can attach a PDF to a Gmail send — bounded to prevent exfil (PDF only,
from the allowlisted invoices dir), fail-closed, and gated by the same send path as text email."""

import base64
import google_access_broker as broker


def _pdf(tmp_path, name="WL-2026-0001__St_Annes.pdf"):
    d = tmp_path / "invoices"; d.mkdir()
    f = d / name; f.write_bytes(b"%PDF-1.4\n%mock invoice\n%%EOF\n")
    return d, f


class _FakeGmail:
    def __init__(self, sink): self.sink = sink
    def users(self): return self
    def messages(self): return self
    def send(self, userId, body): self.sink["raw"] = body["raw"]; return self
    def execute(self): return {"id": "m1", "threadId": "t1", "labelIds": []}


def _mock_gmail(monkeypatch, sink):
    import googleapiclient.discovery
    monkeypatch.setattr(googleapiclient.discovery, "build", lambda *a, **k: _FakeGmail(sink))


def test_pdf_attachment_from_allowlisted_dir_is_attached(tmp_path, monkeypatch):
    d, f = _pdf(tmp_path); monkeypatch.setenv("OPENCLAW_INVOICES_DIR", str(d))
    sink = {}; _mock_gmail(monkeypatch, sink)
    res = broker._exec_gmail_send(object(), {
        "to": "winshiplive@gmail.com", "subject": "Invoice", "body": "See attached.",
        "attachments": [str(f)],
    })
    assert res["ok"] is True
    raw = base64.urlsafe_b64decode(sink["raw"]).decode("utf-8", "replace")
    assert "multipart" in raw.lower() and "attachment" in raw.lower()
    assert f.name in raw and "application/pdf" in raw.lower()


def test_attachment_outside_allowlisted_dir_is_rejected(tmp_path, monkeypatch):
    d, _ = _pdf(tmp_path); monkeypatch.setenv("OPENCLAW_INVOICES_DIR", str(d))
    evil = tmp_path / "secret.pdf"; evil.write_bytes(b"%PDF-1.4 secret")
    sink = {}; _mock_gmail(monkeypatch, sink)
    res = broker._exec_gmail_send(object(), {
        "to": "winshiplive@gmail.com", "subject": "x", "body": "y", "attachments": [str(evil)]})
    assert res["ok"] is False and "attachment" in res["error"].lower()
    assert "raw" not in sink   # nothing sent


def test_non_pdf_attachment_rejected(tmp_path, monkeypatch):
    d, _ = _pdf(tmp_path); monkeypatch.setenv("OPENCLAW_INVOICES_DIR", str(d))
    txt = d / "notes.txt"; txt.write_text("secret notes")
    res = broker._exec_gmail_send(object(), {
        "to": "x@y.com", "subject": "x", "body": "y", "attachments": [str(txt)]})
    assert res["ok"] is False and "pdf" in res["error"].lower()


def test_path_traversal_out_of_allowlist_rejected(tmp_path, monkeypatch):
    d, _ = _pdf(tmp_path); monkeypatch.setenv("OPENCLAW_INVOICES_DIR", str(d))
    outside = tmp_path / "outside.pdf"; outside.write_bytes(b"%PDF-1.4")
    trav = str(d / ".." / "outside.pdf")
    res = broker._exec_gmail_send(object(), {
        "to": "x@y.com", "subject": "x", "body": "y", "attachments": [trav]})
    assert res["ok"] is False


def test_no_attachment_still_plain_text(tmp_path, monkeypatch):
    sink = {}; _mock_gmail(monkeypatch, sink)
    res = broker._exec_gmail_send(object(), {"to": "x@y.com", "subject": "s", "body": "b"})
    assert res["ok"] is True
    raw = base64.urlsafe_b64decode(sink["raw"]).decode("utf-8", "replace")
    assert "multipart" not in raw.lower()   # unchanged plain-text path


def test_executor_passes_valid_attachment_to_broker(tmp_path, monkeypatch):
    import email_send_executor as ese
    d, f = _pdf(tmp_path); monkeypatch.setenv("OPENCLAW_INVOICES_DIR", str(d))
    captured = {}
    monkeypatch.setattr("google_access_broker.call",
                        lambda agent, cap, params: captured.update(params) or {"ok": True, "data": {}})
    res = ese.send_email_via_google_broker(to="winshiplive@gmail.com", subject="Invoice",
                                           body="attached", attachment_path=str(f))
    assert res["ok"] is True and captured.get("attachments") == [str(f)]


def test_executor_rejects_bad_attachment(tmp_path, monkeypatch):
    import email_send_executor as ese
    d, _ = _pdf(tmp_path); monkeypatch.setenv("OPENCLAW_INVOICES_DIR", str(d))
    evil = tmp_path / "evil.pdf"; evil.write_bytes(b"%PDF")
    res = ese.send_email_via_google_broker(to="x@y.com", subject="x", body="y", attachment_path=str(evil))
    assert res["ok"] is False and "attachment" in res["error"].lower()


def test_test_mode_redirect_preserves_attachment(tmp_path, monkeypatch):
    d, f = _pdf(tmp_path); monkeypatch.setenv("OPENCLAW_INVOICES_DIR", str(d))
    monkeypatch.setenv("OPENCLAW_SEND_HOLD_PATH", str(tmp_path / "SEND_HOLD.md"))
    (tmp_path / "SEND_HOLD.md").write_text("HOLD")
    monkeypatch.setattr(broker, "_is_configured", lambda: True)
    monkeypatch.setattr(broker, "_load_credentials", lambda: object())
    monkeypatch.setattr(broker, "_resolve_broker_run_mode", lambda: ("test_dry_run", "run-1"))
    sent = {}
    monkeypatch.setattr(broker, "_exec_gmail_send", lambda creds, params: sent.update(params) or {"ok": True, "data": {}})
    res = broker.call("cassandra", "google.gmail.send",
                      {"to": "attorney@example.com", "subject": "Invoice", "body": "pay", "attachments": [str(f)]})
    assert res["ok"] is True
    assert sent["to"] == "winshiplive@gmail.com"      # redirected
    assert sent["attachments"] == [str(f)]            # attachment preserved through the redirect

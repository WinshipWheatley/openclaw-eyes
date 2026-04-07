"""tests/test_cassandra_md_enrichment.py — Unit tests for Cassandra dashboard enrichment sections."""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import dashboard_gen


# ── A) Inner Circle pin status ────────────────────────────────────────────────

class TestContactPinStatus(unittest.TestCase):
    def test_unpinned_inner_circle(self):
        nicknames = {"dad": {"name": "Pop", "tier": "inner_circle"}}
        result = dashboard_gen._get_contact_pin_status(nicknames)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["nickname"], "dad")
        self.assertFalse(result[0]["pinned"])

    def test_pinned_inner_circle(self):
        nicknames = {"dad": {"name": "Pop", "tier": "inner_circle", "telegram_chat_id": 12345}}
        result = dashboard_gen._get_contact_pin_status(nicknames)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["pinned"])

    def test_no_inner_circle_contacts(self):
        nicknames = {"client": {"name": "Alice", "tier": "client"}}
        result = dashboard_gen._get_contact_pin_status(nicknames)
        self.assertEqual(result, [])

    def test_metadata_key_skipped(self):
        nicknames = {"_meta": {"source": "internal"}, "mom": {"name": "Mom", "tier": "inner_circle"}}
        result = dashboard_gen._get_contact_pin_status(nicknames)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["nickname"], "mom")


# ── B) Send states ────────────────────────────────────────────────────────────

class TestRecentSendStates(unittest.TestCase):
    def _make_jsonl(self, tmp_dir, filename, entries):
        path = Path(tmp_dir) / filename
        path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        return path

    def test_entries_from_correspondence_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = [
                {"ts": "2026-04-03T10:00:00", "state": "sent_confirmed", "recipient": "dad"},
                {"ts": "2026-04-03T09:00:00", "state": "send_failed", "recipient": "mom"},
            ]
            corr_path = self._make_jsonl(tmp, "cassandra_correspondence.jsonl", entries)
            with patch.object(dashboard_gen, "CORRESPONDENCE_LOG", corr_path), \
                 patch.object(dashboard_gen, "OUTREACH_LOG", Path(tmp) / "nonexistent.jsonl"):
                result = dashboard_gen._get_recent_send_states(limit=5)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["state"], "sent_confirmed")  # most recent first

    def test_no_log_files_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(dashboard_gen, "CORRESPONDENCE_LOG", Path(tmp) / "a.jsonl"), \
                 patch.object(dashboard_gen, "OUTREACH_LOG", Path(tmp) / "b.jsonl"):
                result = dashboard_gen._get_recent_send_states()
        self.assertEqual(result, [])

    def test_correct_icons_in_gen_cassandra(self):
        entries = [
            {"ts": "2026-04-03T11:00:00", "state": "sent_confirmed", "recipient": "dad"},
            {"ts": "2026-04-03T10:00:00", "state": "send_failed", "recipient": "mom"},
            {"ts": "2026-04-03T09:00:00", "state": "blocked", "recipient": "draper"},
            {"ts": "2026-04-03T08:00:00", "state": "draft", "recipient": "dad"},
        ]
        with patch.object(dashboard_gen, "_get_recent_send_states", return_value=entries):
            output = self._run_gen_cassandra()
        self.assertIn("✅ [sent_confirmed]", output)
        self.assertIn("❌ [send_failed]", output)
        self.assertIn("🚫 [blocked]", output)
        self.assertIn("📝 [draft]", output)

    def _run_gen_cassandra(self):
        with patch.object(dashboard_gen, "load_json", return_value={}), \
             patch.object(dashboard_gen, "get_capability_flags", return_value={}), \
             patch.object(dashboard_gen, "get_processes", return_value={"cassandra": []}), \
             patch.object(dashboard_gen, "load_jsonl", return_value=[]), \
             patch.object(dashboard_gen, "_get_future_action_pending", return_value=None), \
             patch.object(dashboard_gen, "get_queued_tasks", return_value=[]):
            return dashboard_gen.gen_cassandra()


# ── C) Future-action queue ────────────────────────────────────────────────────

class TestFutureActionPending(unittest.TestCase):
    def test_db_with_pending(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE future_actions (id INTEGER, status TEXT)")
            conn.execute("INSERT INTO future_actions VALUES (1, 'pending')")
            conn.execute("INSERT INTO future_actions VALUES (2, 'pending')")
            conn.execute("INSERT INTO future_actions VALUES (3, 'done')")
            conn.commit()
            conn.close()
            with patch.object(dashboard_gen, "FUTURE_ACTIONS_DB", db_path):
                result = dashboard_gen._get_future_action_pending()
            self.assertEqual(result, 2)
        finally:
            db_path.unlink(missing_ok=True)

    def test_db_with_zero_pending(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE future_actions (id INTEGER, status TEXT)")
            conn.execute("INSERT INTO future_actions VALUES (1, 'done')")
            conn.commit()
            conn.close()
            with patch.object(dashboard_gen, "FUTURE_ACTIONS_DB", db_path):
                result = dashboard_gen._get_future_action_pending()
            self.assertEqual(result, 0)
        finally:
            db_path.unlink(missing_ok=True)

    def test_db_does_not_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(dashboard_gen, "FUTURE_ACTIONS_DB", Path(tmp) / "nonexistent.db"):
                result = dashboard_gen._get_future_action_pending()
        self.assertIsNone(result)


# ── D) Pending approval ───────────────────────────────────────────────────────

def _minimal_gen_cassandra_with_approval(approval_data, nicknames=None):
    """Helper: run gen_cassandra with controlled inputs."""
    if nicknames is None:
        nicknames = {}
    with patch.object(dashboard_gen, "load_json", side_effect=lambda path: (
        approval_data if path == dashboard_gen.APPROVAL_PENDING else {}
    )), \
         patch.object(dashboard_gen, "get_capability_flags", return_value={}), \
         patch.object(dashboard_gen, "get_processes", return_value={"cassandra": []}), \
         patch.object(dashboard_gen, "load_jsonl", return_value=[]), \
         patch.object(dashboard_gen, "_get_recent_send_states", return_value=[]), \
         patch.object(dashboard_gen, "_get_future_action_pending", return_value=None), \
         patch.object(dashboard_gen, "get_queued_tasks", return_value=[]):
        # Patch CONTACT_NICKNAMES load separately since load_json is patched broadly
        with patch.object(dashboard_gen, "_get_contact_pin_status", return_value=[]):
            return dashboard_gen.gen_cassandra()


class TestPendingApproval(unittest.TestCase):
    def test_cassandra_relevant_approval_shown(self):
        data = {"status": "pending", "action": "google calendar read", "tier": 0, "requested_at": "2026-04-03T10:00:00"}
        output = _minimal_gen_cassandra_with_approval(data)
        self.assertIn("### Pending Approval", output)
        self.assertIn("google calendar read", output)

    def test_unrelated_approval_not_shown(self):
        data = {"status": "pending", "action": "delete some files", "tier": 1, "requested_at": "2026-04-03T10:00:00"}
        output = _minimal_gen_cassandra_with_approval(data)
        self.assertNotIn("### Pending Approval", output)

    def test_no_pending_approval(self):
        output = _minimal_gen_cassandra_with_approval({})
        self.assertNotIn("### Pending Approval", output)


# ── E) Gaps and next action ───────────────────────────────────────────────────

class TestGapsAndNextAction(unittest.TestCase):
    def _run_with_flags_and_pins(self, flags, pin_status):
        with patch.object(dashboard_gen, "load_json", return_value={}), \
             patch.object(dashboard_gen, "get_capability_flags", return_value=flags), \
             patch.object(dashboard_gen, "get_processes", return_value={"cassandra": []}), \
             patch.object(dashboard_gen, "load_jsonl", return_value=[]), \
             patch.object(dashboard_gen, "_get_contact_pin_status", return_value=pin_status), \
             patch.object(dashboard_gen, "_get_recent_send_states", return_value=[]), \
             patch.object(dashboard_gen, "_get_future_action_pending", return_value=None), \
             patch.object(dashboard_gen, "get_queued_tasks", return_value=[]):
            return dashboard_gen.gen_cassandra()

    def test_gaps_shown_when_disconnected_and_unpinned(self):
        flags = {"PII_VAULT_CONNECTED": False, "GMAIL_CONNECTED": False}
        pins = [{"nickname": "dad", "display_name": "Pop", "pinned": False}]
        output = self._run_with_flags_and_pins(flags, pins)
        self.assertIn("### Gaps / Unknowns", output)
        self.assertIn("capability gap", output)
        self.assertIn("dad", output)
        self.assertIn("### Next Recommended Action", output)

    def test_no_gaps_when_all_connected_and_pinned(self):
        flags = {"GMAIL_CONNECTED": True}
        pins = [{"nickname": "dad", "display_name": "Pop", "pinned": True}]
        output = self._run_with_flags_and_pins(flags, pins)
        # Gaps section omitted when no log yet still shows the info note
        # but no capability gaps or unpinned contacts
        self.assertNotIn("capability gap", output)
        self.assertNotIn("without pinned chat_id", output)


# ── F) Task mode metadata ─────────────────────────────────────────────────────

class TestTaskModeMetadata(unittest.TestCase):
    def test_execution_mode_shown(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_path = Path(tmp) / "impl-foo.md"
            task_path.write_text("# Task\n**Execution mode:** Claude Code /simplify preferred\n")
            with patch.object(dashboard_gen, "TASKS_DIR", Path(tmp)), \
                 patch.object(dashboard_gen, "get_queued_tasks", return_value=["impl-foo"]), \
                 patch.object(dashboard_gen, "load_json", return_value={}), \
                 patch.object(dashboard_gen, "get_capability_flags", return_value={}), \
                 patch.object(dashboard_gen, "get_processes", return_value={"cassandra": []}), \
                 patch.object(dashboard_gen, "load_jsonl", return_value=[]), \
                 patch.object(dashboard_gen, "_get_contact_pin_status", return_value=[]), \
                 patch.object(dashboard_gen, "_get_recent_send_states", return_value=[]), \
                 patch.object(dashboard_gen, "_get_future_action_pending", return_value=None):
                output = dashboard_gen.gen_cassandra()
        self.assertIn("Claude Code /simplify preferred", output)
        self.assertIn("impl-foo", output)

    def test_no_execution_mode_no_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_path = Path(tmp) / "impl-bar.md"
            task_path.write_text("# Task\nSome content without mode line.\n")
            with patch.object(dashboard_gen, "TASKS_DIR", Path(tmp)), \
                 patch.object(dashboard_gen, "get_queued_tasks", return_value=["impl-bar"]), \
                 patch.object(dashboard_gen, "load_json", return_value={}), \
                 patch.object(dashboard_gen, "get_capability_flags", return_value={}), \
                 patch.object(dashboard_gen, "get_processes", return_value={"cassandra": []}), \
                 patch.object(dashboard_gen, "load_jsonl", return_value=[]), \
                 patch.object(dashboard_gen, "_get_contact_pin_status", return_value=[]), \
                 patch.object(dashboard_gen, "_get_recent_send_states", return_value=[]), \
                 patch.object(dashboard_gen, "_get_future_action_pending", return_value=None):
                output = dashboard_gen.gen_cassandra()
        self.assertIn("impl-bar", output)
        # No backtick mode suffix
        for line in output.splitlines():
            if "impl-bar" in line:
                self.assertNotIn(" · `", line)


# ── G) Regression — existing sections preserved ───────────────────────────────

class TestRegressionExistingSections(unittest.TestCase):
    def test_existing_sections_present(self):
        fake_convo = [{"ts": "2026-04-03T10:00:00", "user": "hi", "route": "llm", "replies": ["hello"]}]
        with patch.object(dashboard_gen, "load_json", return_value={}), \
             patch.object(dashboard_gen, "get_capability_flags", return_value={}), \
             patch.object(dashboard_gen, "get_processes", return_value={"cassandra": []}), \
             patch.object(dashboard_gen, "load_jsonl", return_value=fake_convo), \
             patch.object(dashboard_gen, "_get_contact_pin_status", return_value=[]), \
             patch.object(dashboard_gen, "_get_recent_send_states", return_value=[]), \
             patch.object(dashboard_gen, "_get_future_action_pending", return_value=None), \
             patch.object(dashboard_gen, "get_queued_tasks", return_value=[]):
            output = dashboard_gen.gen_cassandra()
        for section in ["### Processes", "### Capabilities", "### Contacts", "### Recent Messages"]:
            self.assertIn(section, output, f"Missing required section: {section}")


if __name__ == "__main__":
    unittest.main()

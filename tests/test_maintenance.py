import tempfile
import unittest
from pathlib import Path

from shivaay_memory import MemoryEngine
from shivaay_memory.maintenance import MemoryMaintenance, possible_update_text


class MemoryMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.engine = MemoryEngine(str(Path(self.tempdir.name) / "memory.sqlite3"))
        self.maintenance = MemoryMaintenance(self.engine)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_scan_proposes_duplicate_without_mutating_memories(self):
        first = self.engine.add_memory("SHIVAAY uses SQLite for local persistent memory.", project="SHIVAAY")
        second = self.engine.add_memory("SHIVAAY uses SQLite for persistent local memory.", project="SHIVAAY")
        suggestions = self.maintenance.scan(project="SHIVAAY")
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["kind"], "possible_duplicate")
        self.assertEqual(self.engine.get_memory(first)["status"], "active")
        self.assertEqual(self.engine.get_memory(second)["status"], "active")

    def test_apply_preserves_history_and_creates_corrected_memory(self):
        old = self.engine.add_memory("SHIVAAY uses SQLite for local persistent memory.", project="SHIVAAY")
        self.engine.add_memory("SHIVAAY uses SQLite for persistent local memory.", project="SHIVAAY")
        suggestion = self.maintenance.scan(project="SHIVAAY")[0]
        new_id = self.maintenance.apply(suggestion["id"])
        self.assertEqual(self.engine.get_memory(old)["status"], "superseded")
        self.assertEqual(self.engine.get_memory(new_id)["status"], "active")
        self.assertEqual(self.maintenance.list(status="applied")[0]["applied_memory_id"], new_id)

    def test_dismiss_and_repeat_scan_do_not_duplicate_suggestions(self):
        self.engine.add_memory("I do not use cloud inference for private data.", project="SHIVAAY")
        self.engine.add_memory("I use cloud inference for private data.", project="SHIVAAY")
        first = self.maintenance.scan(project="SHIVAAY")
        again = self.maintenance.scan(project="SHIVAAY")
        self.assertEqual(len(first), 1)
        self.assertEqual(again, [])
        self.maintenance.dismiss(first[0]["id"])
        self.assertEqual(self.maintenance.list(status="pending"), [])
        self.assertEqual(self.maintenance.list(status="dismissed")[0]["status"], "dismissed")

    def test_explicit_update_cue_requires_same_claim_family_and_changed_value(self):
        self.assertTrue(possible_update_text(
            "Actually, I prefer detailed explanations.",
            "I prefer concise explanations.",
        ))
        self.assertFalse(possible_update_text(
            "I prefer detailed explanations.",
            "I prefer concise explanations.",
        ))
        self.assertFalse(possible_update_text(
            "Actually, I like dogs.",
            "I prefer concise explanations.",
        ))

    def test_apply_only_pending_suggestions(self):
        with self.assertRaises(KeyError):
            self.maintenance.apply(999)

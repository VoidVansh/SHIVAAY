import tempfile
import unittest
from pathlib import Path

from shivaay_memory import MemoryEngine


class MemoryEngineTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tempdir.name) / "test.sqlite3")
        self.engine = MemoryEngine(self.db)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_add_search_and_project_isolation(self):
        mid = self.engine.add_memory(
            "SHIVAAY uses SQLite for local persistent memory.",
            category="architecture", project="SHIVAAY", importance=5
        )
        self.assertGreater(mid, 0)
        self.assertEqual(len(self.engine.search("SQLite persistent memory", project="SHIVAAY")), 1)
        self.assertEqual(self.engine.search("SQLite", project="another-project"), [])

    def test_sensitive_memory_requires_approval(self):
        with self.assertRaises(PermissionError):
            self.engine.add_memory("my password is not for storage")
        with self.assertRaises(PermissionError):
            self.engine.add_memory("private medical note", sensitivity="sensitive")
        mid = self.engine.add_memory(
            "Sensitive note approved by user", sensitivity="sensitive", approve_sensitive=True
        )
        self.assertGreater(mid, 0)

    def test_correction_preserves_old_record(self):
        old = self.engine.add_memory("The project uses database A.", project="SHIVAAY")
        new = self.engine.correct_memory(old, "The project uses database B.")
        self.assertEqual(self.engine.get_memory(old)["status"], "superseded")
        self.assertEqual(self.engine.get_memory(old)["superseded_by"], new)
        self.assertEqual(self.engine.get_memory(new)["status"], "active")

    def test_conversation_archive_and_context(self):
        count = self.engine.archive_conversation(
            "chat-1",
            [{"role": "user", "content": "We chose SQLite for the local memory database."},
             {"role": "assistant", "content": "I will use SQLite."}],
            project="SHIVAAY",
        )
        self.assertEqual(count, 2)
        self.assertTrue(self.engine.search_conversations("SQLite local database", project="SHIVAAY"))
        self.assertIn("conversation=chat-1", self.engine.build_context("SQLite", project="SHIVAAY"))

    def test_context_respects_character_budget(self):
        self.engine.add_memory("Important local memory " + ("details " * 200), project="SHIVAAY", importance=5)
        self.engine.save_summary("project", "SHIVAAY", "Project summary " + ("context " * 500))
        context = self.engine.build_context("local memory", project="SHIVAAY", max_chars=600)
        self.assertLessEqual(len(context), 600)
        self.assertIn("Project summary", context)

    def test_summary_upsert(self):
        self.engine.save_summary("project", "SHIVAAY", "First summary")
        self.engine.save_summary("project", "SHIVAAY", "Updated summary")
        self.assertEqual(self.engine.get_summary("project", "SHIVAAY")["content"], "Updated summary")


if __name__ == "__main__":
    unittest.main()

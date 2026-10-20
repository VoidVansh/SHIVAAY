import sqlite3
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

    def test_store_connection_closes_after_context_exit(self):
        connection = self.engine.store.connect()
        with connection as conn:
            conn.execute("SELECT 1")
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

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

    def test_context_includes_memory_provenance(self):
        self.engine.add_memory("SHIVAAY uses local SQLite.", project="SHIVAAY",
                               source_ref="conversation-42", category="decision", importance=5)
        context = self.engine.build_context("local SQLite", project="SHIVAAY")
        self.assertIn("ref=conversation-42", context)
        self.assertIn("category=decision", context)
        self.assertIn("importance=5", context)

    def test_delete_conversation_removes_archive_and_summary_but_linked_memories_are_opt_in(self):
        conversation_id = "conversation-to-delete"
        self.engine.archive_conversation(conversation_id, [
            {"role": "user", "content": "A private message"},
            {"role": "assistant", "content": "A reply"},
        ], project="SHIVAAY")
        self.engine.save_summary("conversation", conversation_id, "A continuity summary")
        linked = self.engine.add_memory("A linked project fact.", project="SHIVAAY",
                                        source_ref=conversation_id)
        result = self.engine.delete_conversation(conversation_id)
        self.assertEqual(result["messages_deleted"], 2)
        self.assertEqual(result["summaries_deleted"], 1)
        self.assertEqual(result["linked_memories_deleted"], 0)
        self.assertEqual(self.engine.get_conversation_messages(conversation_id), [])
        self.assertIsNotNone(self.engine.get_memory(linked))
        self.engine.delete_conversation(conversation_id, include_linked_memories=True)
        self.assertIsNone(self.engine.get_memory(linked))

    def test_delete_cleans_references_and_preserves_other_history(self):
        original = self.engine.add_memory("The original fact.", project="SHIVAAY")
        corrected = self.engine.correct_memory(original, "The corrected fact.", reason="test")
        with self.engine.store.connect() as conn:
            conn.execute("""CREATE TABLE memory_embeddings (
                memory_id INTEGER PRIMARY KEY, model TEXT, dimensions INTEGER,
                vector_json TEXT, updated_at TEXT)""")
            conn.execute("INSERT INTO memory_embeddings VALUES (?, 'fake', 2, '[1,0]', 'now')", (corrected,))
            conn.execute("""CREATE TABLE maintenance_suggestions (
                id INTEGER PRIMARY KEY, memory_id INTEGER NOT NULL, compared_memory_id INTEGER,
                kind TEXT, reason TEXT, status TEXT, applied_memory_id INTEGER)""")
            conn.execute("INSERT INTO maintenance_suggestions VALUES (1, ?, ?, 'possible_conflict', 'test', 'pending', NULL)",
                         (original, corrected))
        self.assertTrue(self.engine.delete_memory(corrected))
        self.assertIsNone(self.engine.get_memory(corrected))
        self.assertEqual(self.engine.get_memory(original)["superseded_by"], None)
        self.assertEqual(self.engine.store.execute("SELECT COUNT(*) AS n FROM memory_embeddings")[0]["n"], 0)
        self.assertEqual(self.engine.store.execute("SELECT COUNT(*) AS n FROM maintenance_suggestions")[0]["n"], 0)
        self.assertFalse(self.engine.delete_memory(corrected))

    def test_context_tracks_only_memories_actually_included(self):
        memory_id = self.engine.add_memory("A relevant memory is visible.", project="SHIVAAY")
        context = self.engine.build_context("relevant memory", project="SHIVAAY")
        row = self.engine.get_memory(memory_id)
        self.assertIn("Relevant saved memories", context)
        self.assertGreaterEqual(row["access_count"], 1)
        self.assertIsNotNone(row["last_accessed_at"])

    def test_context_uses_real_newlines(self):
        self.engine.add_memory("Line one\nLine two", project="SHIVAAY")
        context = self.engine.build_context("line one", project="SHIVAAY")
        self.assertIn("\n", context)
        self.assertNotIn("\\n", context)

    def test_related_prior_conversation_summary_is_retrieved(self):
        self.engine.archive_conversation("old-chat", [
            {"role": "user", "content": "We chose SQLite for local memory storage."}
        ], project="SHIVAAY")
        self.engine.save_summary("conversation", "old-chat",
                                 "SHIVAAY uses SQLite for local-first persistent memory storage.",
                                 source_ref="old-chat")
        context = self.engine.build_context("How does local persistent memory use SQLite?",
                                            project="SHIVAAY")
        self.assertIn("Related prior conversation summaries", context)
        self.assertIn("old-chat", context)
        excluded = self.engine.build_context("How does local persistent memory use SQLite?",
                                             project="SHIVAAY", exclude_conversation_id="old-chat")
        self.assertNotIn("old-chat", excluded)

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

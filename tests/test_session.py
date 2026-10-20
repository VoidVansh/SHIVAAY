import tempfile
import unittest
from pathlib import Path

from shivaay_memory.engine import MemoryEngine
from shivaay_memory.extraction import CandidateQueue, RuleBasedExtractor
from shivaay_memory.session import MemorySession


class MemorySessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = MemoryEngine(str(Path(self.temp.name) / "memory.sqlite3"))

    def tearDown(self):
        self.temp.cleanup()

    def test_context_is_built_from_local_memory(self):
        self.engine.add_memory(
            "User is building the SHIVAAY assistant.",
            category="project", project="SHIVAAY", importance=5,
        )
        session = MemorySession(self.engine)
        context = session.context_for("Continue building SHIVAAY", project="SHIVAAY")
        self.assertIn("SHIVAAY", context)
        self.assertIn("Relevant saved memories", context)

    def test_turn_is_archived_and_candidates_need_review(self):
        session = MemorySession(self.engine, extractor=RuleBasedExtractor())
        result = session.finish_turn(
            "chat-001",
            "I'm building SHIVAAY as a local-first assistant.",
            "That sounds like a useful project.",
            project="SHIVAAY",
        )
        self.assertEqual(result.archived_messages, 2)
        self.assertTrue(result.candidate_ids)
        self.assertEqual(len(session.queue.list(status="pending")), len(result.candidate_ids))
        self.assertEqual(self.engine.stats()["conversations"], 2)
        self.assertEqual(self.engine.stats()["memories"], 0)

    def test_no_extractor_means_no_candidates(self):
        session = MemorySession(self.engine)
        result = session.finish_turn("chat-002", "Hello", "Hi there")
        self.assertEqual(result.candidate_ids, ())
        self.assertEqual(result.archived_messages, 2)


if __name__ == "__main__":
    unittest.main()

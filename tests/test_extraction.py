import tempfile
import unittest
from pathlib import Path

from shivaay_memory import MemoryEngine
from shivaay_memory.extraction import CandidateQueue, RuleBasedExtractor


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.engine = MemoryEngine(str(Path(self.tempdir.name) / "memory.sqlite3"))
        self.queue = CandidateQueue(self.engine)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_extractor_only_uses_user_messages(self):
        messages = [
            {"role": "assistant", "content": "Remember that the user likes tea."},
            {"role": "user", "content": "Please remember that I prefer short, direct answers."},
        ]
        candidates = RuleBasedExtractor().extract(messages, project="SHIVAAY")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].category, "preference")

    def test_candidate_requires_review_before_becoming_memory(self):
        candidates = RuleBasedExtractor().extract(
            [{"role": "user", "content": "I prefer concise explanations and practical examples."}],
            project="SHIVAAY",
        )
        ids = self.queue.propose(candidates, source_ref="chat-123")
        self.assertTrue(ids)
        self.assertEqual(self.engine.list_memories(project="SHIVAAY"), [])
        memory_id = self.queue.approve(ids[0])
        self.assertEqual(self.engine.get_memory(memory_id)["status"], "active")
        self.assertEqual(self.queue.list(status="approved")[0]["memory_id"], memory_id)

    def test_rejection_and_duplicate_proposal(self):
        candidate = RuleBasedExtractor().extract(
            [{"role": "user", "content": "I plan to build a local-first assistant with persistent memory."}],
            project="SHIVAAY",
        )[0]
        ids = self.queue.propose([candidate])
        self.assertEqual(self.queue.propose([candidate]), [])
        self.queue.reject(ids[0])
        self.assertEqual(self.queue.list(status="pending"), [])
        self.assertEqual(self.queue.list(status="rejected")[0]["id"], ids[0])


if __name__ == "__main__":
    unittest.main()

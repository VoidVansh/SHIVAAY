import tempfile
import unittest
from pathlib import Path

from shivaay_memory.chat import MemoryChat, OllamaBackend
from shivaay_memory.engine import MemoryEngine
from shivaay_memory.extraction import RuleBasedExtractor


class FakeBackend:
    def __init__(self, answer="Hello from SHIVAAY"):
        self.answer = answer
        self.calls = []

    def reply(self, messages):
        self.calls.append(messages)
        return self.answer


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = MemoryEngine(str(Path(self.tmp.name) / "memory.sqlite3"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_context_is_sent_and_turn_is_archived(self):
        self.engine.add_memory("The SHIVAAY project should be local-first.", project="shivaay", importance=5)
        backend = FakeBackend()
        chat = MemoryChat(self.engine, backend, project="shivaay")
        answer, result = chat.send("How should I build the SHIVAAY project?")
        self.assertEqual(answer, "Hello from SHIVAAY")
        self.assertIn("local-first", backend.calls[0][0]["content"])
        self.assertEqual(result.archived_messages, 2)
        self.assertEqual(len(chat.history), 2)

    def test_rule_extractor_only_queues_candidates(self):
        backend = FakeBackend()
        chat = MemoryChat(self.engine, backend, extractor=RuleBasedExtractor())
        _, result = chat.send("Please remember that my project is SHIVAAY and I want to build it carefully.")
        self.assertGreaterEqual(len(result.candidate_ids), 1)
        self.assertEqual(self.engine.list_memories(), [])

    def test_remote_ollama_host_rejected(self):
        with self.assertRaises(ValueError):
            OllamaBackend(host="https://example.com")

    def test_empty_user_message_rejected(self):
        chat = MemoryChat(self.engine, FakeBackend())
        with self.assertRaises(ValueError):
            chat.send("   ")


if __name__ == "__main__":
    unittest.main()

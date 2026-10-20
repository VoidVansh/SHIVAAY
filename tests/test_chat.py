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


class FakeSemanticIndex:
    def search(self, query, *, project=None, limit=8):
        return [{"id": 42, "semantic_score": 0.91, "source_type": "user_statement",
                 "confidence": 1.0, "text": "The user wants meaning-based memory retrieval."}]


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

    def test_semantic_hits_are_added_to_prompt(self):
        backend = FakeBackend()
        chat = MemoryChat(self.engine, backend, semantic_index=FakeSemanticIndex())
        chat.send("How should memory recall work?")
        self.assertIn("meaning-based memory retrieval", backend.calls[0][0]["content"])
        self.assertIn("similarity=0.910", backend.calls[0][0]["content"])

    def test_existing_conversation_can_be_resumed_with_recent_history(self):
        self.engine.archive_conversation("resume-me", [
            {"role": "user", "content": "We chose SQLite."},
            {"role": "assistant", "content": "Yes, local SQLite."},
        ], project="SHIVAAY")
        backend = FakeBackend()
        chat = MemoryChat(self.engine, backend, project="SHIVAAY", conversation_id="resume-me")
        self.assertEqual(len(chat.history), 2)
        chat.send("What did we choose?")
        self.assertIn("We chose SQLite.", backend.calls[0][1]["content"])
        self.assertEqual(len(self.engine.get_conversation_messages("resume-me")), 4)

    def test_periodic_summary_is_saved_and_reused(self):
        class SummaryBackend:
            def __init__(self):
                self.calls = []
            def reply(self, messages):
                self.calls.append(messages)
                if "Summarize conversation data faithfully" in messages[0]["content"]:
                    return "User is building SHIVAAY; next step is improve memory."
                return "Ordinary reply"
        backend = SummaryBackend()
        chat = MemoryChat(self.engine, backend, project="SHIVAAY",
                          conversation_id="summary-test", summary_interval=2)
        chat.send("I am building SHIVAAY.")
        chat.send("Next, improve memory.")
        saved = self.engine.get_summary("conversation", "summary-test")
        self.assertIn("next step", saved["content"])
        chat.send("What should we do next?")
        self.assertIn("Current conversation summary", backend.calls[-1][0]["content"])
        self.assertIn("next step is improve memory", backend.calls[-1][0]["content"])

    def test_resumed_chat_summarizes_archived_turns_after_last_summary(self):
        self.engine.save_summary("conversation", "resume-summary", "Older summary.",
                                 source_ref="resume-summary")
        self.engine.store.execute(
            "UPDATE summaries SET updated_at='2000-01-01T00:00:00.000Z' WHERE scope='conversation' AND scope_key=?",
            ("resume-summary",),
        )
        self.engine.archive_conversation("resume-summary", [
            {"role": "user", "content": "We decided the interface should be centered."},
            {"role": "assistant", "content": "I will keep the interface centered."},
        ], project="SHIVAAY")

        class SummaryBackend:
            def __init__(self):
                self.calls = []
            def reply(self, messages):
                self.calls.append(messages)
                if "Summarize conversation data faithfully" in messages[0]["content"]:
                    return "Summary includes the centered interface decision."
                return "Continuing the project."

        backend = SummaryBackend()
        chat = MemoryChat(self.engine, backend, project="SHIVAAY",
                          conversation_id="resume-summary", summary_interval=2)
        self.assertEqual(len(chat._summary_window), 2)
        chat.send("Continue from that decision.")
        saved = self.engine.get_summary("conversation", "resume-summary")
        self.assertIn("centered interface decision", saved["content"])
        summary_call = next(call for call in backend.calls
                            if "Summarize conversation data faithfully" in call[0]["content"])
        self.assertIn("We decided the interface should be centered", summary_call[1]["content"])

    def test_summary_failure_does_not_fail_successful_chat_turn(self):
        class FlakyBackend:
            def __init__(self):
                self.calls = 0
            def reply(self, messages):
                self.calls += 1
                if "Summarize conversation data faithfully" in messages[0]["content"]:
                    raise RuntimeError("summary unavailable")
                return "Still answered"
        chat = MemoryChat(self.engine, FlakyBackend(), summary_interval=1)
        answer, _ = chat.send("Please answer normally.")
        self.assertEqual(answer, "Still answered")
        self.assertIsNotNone(chat.last_summary_error)
        self.assertEqual(len(self.engine.search_conversations("normally")), 1)

    def test_rule_extractor_only_queues_candidates(self):
        backend = FakeBackend()
        chat = MemoryChat(self.engine, backend, extractor=RuleBasedExtractor())
        _, result = chat.send("Please remember that my project is SHIVAAY and I want to build it carefully.")
        self.assertGreaterEqual(len(result.candidate_ids), 1)
        self.assertEqual(self.engine.list_memories(), [])

    def test_remote_ollama_host_rejected(self):
        with self.assertRaises(ValueError):
            OllamaBackend(host="https://example.com")

    def test_lookalike_remote_host_rejected(self):
        with self.assertRaises(ValueError):
            OllamaBackend(host="http://127.0.0.1.evil.example:11434")

    def test_empty_user_message_rejected(self):
        chat = MemoryChat(self.engine, FakeBackend())
        with self.assertRaises(ValueError):
            chat.send("   ")


if __name__ == "__main__":
    unittest.main()

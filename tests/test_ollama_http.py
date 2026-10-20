"""HTTP-level tests for the local Ollama adapter; no Ollama install/model required."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from shivaay_memory.chat import MemoryChat, OllamaBackend
from shivaay_memory.engine import MemoryEngine


class OllamaBackendHTTPTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.response_body = {"message": {"content": "  Local reply  "}}
        self.status_code = 200
        self.raw_response = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                owner.requests.append((self.path, self.headers.get("Content-Type"), json.loads(body)))
                payload = owner.raw_response if owner.raw_response is not None else json.dumps(owner.response_body).encode("utf-8")
                self.send_response(owner.status_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_sends_expected_local_chat_payload_and_strips_reply(self):
        backend = OllamaBackend(model="test-model", host=self.host, timeout=2)
        messages = [{"role": "user", "content": "Remember this project decision."}]
        self.assertEqual(backend.reply(messages), "Local reply")
        path, content_type, payload = self.requests[0]
        self.assertEqual(path, "/api/chat")
        self.assertEqual(content_type, "application/json")
        self.assertEqual(payload, {"model": "test-model", "messages": messages, "stream": False})

    def test_malformed_message_shape_is_reported_cleanly(self):
        self.response_body = {"not_message": True}
        backend = OllamaBackend(host=self.host, timeout=2)
        with self.assertRaisesRegex(RuntimeError, "empty or malformed"):
            backend.reply([{"role": "user", "content": "Hello"}])

    def test_full_memory_chat_round_trip_uses_local_http_backend_and_archives_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = MemoryEngine(str(Path(tmp) / "memory.sqlite3"))
            engine.add_memory("SHIVAAY uses local SQLite for persistent memory.",
                              project="SHIVAAY", importance=5)
            chat = MemoryChat(engine, OllamaBackend(model="test-model", host=self.host),
                              project="SHIVAAY", conversation_id="http-integration")
            answer, turn = chat.send("Which database does SHIVAAY use?")
            self.assertEqual(answer, "Local reply")
            self.assertEqual(turn.archived_messages, 2)
            archived = engine.get_conversation_messages("http-integration")
            self.assertEqual([row["role"] for row in archived], ["user", "assistant"])
            sent_messages = self.requests[0][2]["messages"]
            self.assertEqual(sent_messages[-1], {
                "role": "user", "content": "Which database does SHIVAAY use?"
            })
            self.assertIn("local SQLite", sent_messages[0]["content"])

    def test_invalid_json_and_http_error_are_reported_as_local_backend_failures(self):
        self.raw_response = b"not-json"
        backend = OllamaBackend(host=self.host, timeout=2)
        with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
            backend.reply([{"role": "user", "content": "Hello"}])

        self.raw_response = None
        self.status_code = 500
        with self.assertRaisesRegex(RuntimeError, "Could not reach local Ollama"):
            backend.reply([{"role": "user", "content": "Hello"}])

    def test_remote_hosts_are_rejected_before_any_request(self):
        for host in ("https://example.com", "http://192.0.2.10:11434",
                     "http://localhost.evil.example:11434", "http://user@localhost:11434"):
            with self.subTest(host=host), self.assertRaises(ValueError):
                OllamaBackend(host=host)
        self.assertEqual(self.requests, [])


if __name__ == "__main__":
    unittest.main()

"""HTTP-level tests for the local Ollama adapter; no Ollama install/model required."""
from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from shivaay_memory.chat import OllamaBackend


class OllamaBackendHTTPTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.response_body = {"message": {"content": "  Local reply  "}}
        self.status_code = 200
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                owner.requests.append((self.path, self.headers.get("Content-Type"), json.loads(body)))
                payload = json.dumps(owner.response_body).encode("utf-8")
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

    def test_invalid_json_response_is_reported_cleanly(self):
        self.response_body = {"not_message": True}
        backend = OllamaBackend(host=self.host, timeout=2)
        with self.assertRaisesRegex(RuntimeError, "empty or malformed"):
            backend.reply([{"role": "user", "content": "Hello"}])

    def test_remote_hosts_are_rejected_before_any_request(self):
        for host in ("https://example.com", "http://192.0.2.10:11434",
                     "http://localhost.evil.example:11434", "http://user@localhost:11434"):
            with self.subTest(host=host), self.assertRaises(ValueError):
                OllamaBackend(host=host)
        self.assertEqual(self.requests, [])


if __name__ == "__main__":
    unittest.main()

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shivaay_memory.cli import main
from shivaay_memory.engine import MemoryEngine


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tempdir.name) / "configured-memory.sqlite3")

    def tearDown(self):
        self.tempdir.cleanup()

    def run_cli(self, *args):
        output = io.StringIO()
        with patch.dict(os.environ, {"SHIVAAY_MEMORY_DB": self.db}), patch("sys.argv", ["shivaay-memory", *args]), contextlib.redirect_stdout(output):
            main()
        return output.getvalue()

    def test_environment_database_path_is_honored(self):
        output = self.run_cli("init")
        self.assertIn(self.db, output)
        self.assertTrue(Path(self.db).is_file())

    def test_show_exposes_memory_provenance(self):
        engine = MemoryEngine(self.db)
        memory_id = engine.add_memory("I prefer concise answers.", project="SHIVAAY", source_ref="chat-7")
        payload = json.loads(self.run_cli("show", "--id", str(memory_id)))
        self.assertEqual(payload["text"], "I prefer concise answers.")
        self.assertEqual(payload["source_ref"], "chat-7")
        self.assertEqual(payload["project"], "SHIVAAY")

    def test_show_unknown_id_fails_clearly(self):
        with self.assertRaises(SystemExit) as error:
            self.run_cli("show", "--id", "999")
        self.assertEqual(error.exception.code, 2)

    def test_doctor_reports_integrity_and_policy(self):
        payload = json.loads(self.run_cli("doctor"))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["integrity"]["integrity"], ["ok"])
        self.assertEqual(payload["candidate_policy"]["auto_save_enabled"], 0)


if __name__ == "__main__":
    unittest.main()

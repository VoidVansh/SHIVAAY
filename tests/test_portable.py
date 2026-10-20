import json
import tempfile
import unittest
from pathlib import Path

from shivaay_memory import MemoryEngine
from shivaay_memory.portable import export_json, import_json


class PortableTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.sqlite3"
        self.target = self.root / "target.sqlite3"
        self.file = self.root / "export.json"
        self.engine = MemoryEngine(str(self.source))
        old_id = self.engine.add_memory("Original project fact", project="SHIVAAY", importance=4)
        self.engine.correct_memory(old_id, "Corrected project fact", reason="test correction")
        self.engine.archive_conversation("chat-1", [
            {"role": "user", "content": "A source conversation"},
            {"role": "assistant", "content": "An answer"},
        ], project="SHIVAAY")
        self.engine.save_summary("project", "SHIVAAY", "Project summary", source_ref="chat-1")
        MemoryEngine(str(self.target))

    def tearDown(self):
        self.tmp.cleanup()

    def test_export_import_preserves_core_data_and_supersession(self):
        result = export_json(self.source, self.file)
        self.assertEqual(result["memories"], 2)
        imported = import_json(self.target, self.file)
        self.assertEqual(imported["memories_imported"], 2)
        target_engine = MemoryEngine(str(self.target))
        rows = target_engine.list_memories(project="SHIVAAY", include_superseded=True)
        self.assertEqual(len(rows), 2)
        old = next(row for row in rows if row["status"] == "superseded")
        new = next(row for row in rows if row["status"] == "active")
        self.assertEqual(old["superseded_by"], new["id"])
        self.assertEqual(len(target_engine.search_conversations("source conversation", project="SHIVAAY")), 1)
        self.assertEqual(target_engine.get_summary("project", "SHIVAAY")["content"], "Project summary")

    def test_existing_export_requires_overwrite(self):
        export_json(self.source, self.file)
        with self.assertRaises(FileExistsError):
            export_json(self.source, self.file)

    def test_sensitive_records_need_explicit_approval(self):
        self.engine.add_memory("This is a personal note", project="SHIVAAY",
                               sensitivity="sensitive", approve_sensitive=True)
        export_json(self.source, self.file)
        with self.assertRaises(PermissionError):
            import_json(self.target, self.file)
        self.assertTrue(import_json(self.target, self.file, allow_sensitive=True)["ok"])

    def test_invalid_format_is_rejected(self):
        self.file.write_text(json.dumps({"format": "wrong", "version": 1}), encoding="utf-8")
        with self.assertRaises(ValueError):
            import_json(self.target, self.file)

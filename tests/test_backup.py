import tempfile
import unittest
from pathlib import Path

from shivaay_memory import MemoryEngine
from shivaay_memory.backup import backup_database, check_database, restore_database


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.sqlite3"
        self.backup = self.root / "backups" / "memory.sqlite3"
        self.restored = self.root / "restored.sqlite3"
        self.engine = MemoryEngine(str(self.source))
        self.engine.add_memory("SHIVAAY memory must remain local.", project="SHIVAAY")
        self.engine.archive_conversation("test-chat", [{"role": "user", "content": "hello"}])

    def tearDown(self):
        self.tmp.cleanup()

    def test_backup_and_restore_preserve_memory_and_conversations(self):
        result = backup_database(self.source, self.backup)
        self.assertTrue(result["ok"])
        restored = restore_database(self.backup, self.restored)
        self.assertTrue(restored["ok"])
        report = check_database(self.restored)
        self.assertTrue(report["ok"])
        self.assertEqual(report["counts"]["memories"], 1)
        self.assertEqual(report["counts"]["conversations"], 1)
        check_engine = MemoryEngine(str(self.restored))
        self.assertEqual(len(check_engine.search("local")), 1)

    def test_existing_destination_requires_explicit_overwrite(self):
        backup_database(self.source, self.backup)
        with self.assertRaises(FileExistsError):
            backup_database(self.source, self.backup)

    def test_same_path_is_rejected(self):
        with self.assertRaises(ValueError):
            backup_database(self.source, self.source)

    def test_missing_database_is_rejected(self):
        with self.assertRaises(FileNotFoundError):
            check_database(self.root / "missing.sqlite3")

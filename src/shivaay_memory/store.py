"""SQLite persistence layer for SHIVAAY memory."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_DB = Path.home() / ".local" / "share" / "shivaay" / "memory.sqlite3"


class MemoryStore:
    """Owns the local SQLite database and its schema."""

    def __init__(self, db_path: str | os.PathLike[str] | None = None) -> None:
        chosen = db_path or os.environ.get("SHIVAAY_MEMORY_DB") or DEFAULT_DB
        self.db_path = Path(chosen).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    def _initialize(self) -> None:
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'general',
                    project TEXT NOT NULL DEFAULT 'general',
                    source_type TEXT NOT NULL DEFAULT 'user_statement',
                    source_ref TEXT,
                    confidence REAL NOT NULL DEFAULT 1.0 CHECK(confidence >= 0 AND confidence <= 1),
                    importance INTEGER NOT NULL DEFAULT 3 CHECK(importance BETWEEN 1 AND 5),
                    sensitivity TEXT NOT NULL DEFAULT 'normal'
                        CHECK(sensitivity IN ('normal','sensitive')),
                    status TEXT NOT NULL DEFAULT 'active'
                        CHECK(status IN ('active','superseded','archived')),
                    superseded_by INTEGER REFERENCES memories(id),
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    last_accessed_at TEXT,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    tags TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_memories_project_status
                    ON memories(project, status);
                CREATE INDEX IF NOT EXISTS idx_memories_category
                    ON memories(category);
                CREATE INDEX IF NOT EXISTS idx_memories_updated
                    ON memories(updated_at DESC);

                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    text, category, project, tags, content='memories', content_rowid='id'
                );

                CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, text, category, project, tags)
                    VALUES (new.id, new.text, new.category, new.project, new.tags);
                END;
                CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, text, category, project, tags)
                    VALUES ('delete', old.id, old.text, old.category, old.project, old.tags);
                END;
                CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, text, category, project, tags)
                    VALUES ('delete', old.id, old.text, old.category, old.project, old.tags);
                    INSERT INTO memories_fts(rowid, text, category, project, tags)
                    VALUES (new.id, new.text, new.category, new.project, new.tags);
                END;

                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    project TEXT NOT NULL DEFAULT 'general',
                    role TEXT NOT NULL CHECK(role IN ('user','assistant','system','tool')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    metadata TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_conversations_id
                    ON conversations(conversation_id, id);
                CREATE INDEX IF NOT EXISTS idx_conversations_project
                    ON conversations(project, id DESC);

                CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts USING fts5(
                    content, conversation_id, project, content='conversations', content_rowid='id'
                );
                CREATE TRIGGER IF NOT EXISTS conversations_ai AFTER INSERT ON conversations BEGIN
                    INSERT INTO conversations_fts(rowid, content, conversation_id, project)
                    VALUES (new.id, new.content, new.conversation_id, new.project);
                END;
                CREATE TRIGGER IF NOT EXISTS conversations_ad AFTER DELETE ON conversations BEGIN
                    INSERT INTO conversations_fts(conversations_fts, rowid, content, conversation_id, project)
                    VALUES ('delete', old.id, old.content, old.conversation_id, old.project);
                END;

                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT NOT NULL CHECK(scope IN ('user','project','conversation')),
                    scope_key TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_ref TEXT,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    UNIQUE(scope, scope_key)
                );
                """
            )

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            cur = conn.execute(sql, params)
            if cur.description:
                return [dict(row) for row in cur.fetchall()]
            return []

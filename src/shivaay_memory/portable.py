"""Portable JSON export/import for core SHIVAAY memory data.

Semantic vectors and review queues are intentionally not exported: vectors are
model-specific and can be rebuilt, while queue schemas can change between versions.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

FORMAT = "shivaay-memory-export"
VERSION = 1
MEMORY_FIELDS = (
    "text", "category", "project", "source_type", "source_ref", "confidence",
    "importance", "sensitivity", "status", "created_at", "updated_at",
    "last_accessed_at", "access_count", "tags", "note",
)
CONVERSATION_FIELDS = ("conversation_id", "project", "role", "content", "created_at", "metadata")
SUMMARY_FIELDS = ("scope", "scope_key", "content", "source_ref", "created_at", "updated_at")
VALID_SOURCE_TYPES = {"user_statement", "assistant_inference", "conversation_summary", "external_source", "user_correction"}
VALID_STATUSES = {"active", "superseded", "archived"}
VALID_ROLES = {"user", "assistant", "system", "tool"}


def export_json(database: str | Path, destination: str | Path, *, overwrite: bool = False) -> dict[str, Any]:
    source = Path(database).expanduser().resolve()
    target = Path(destination).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Database does not exist: {source}")
    if source == target:
        raise ValueError("Export destination must differ from the database path.")
    if target.exists() and not overwrite:
        raise FileExistsError(f"Export file already exists: {target}; pass overwrite=True to replace it.")
    with sqlite3.connect(source) as conn:
        conn.row_factory = sqlite3.Row
        memories = [dict(row) for row in conn.execute("SELECT * FROM memories ORDER BY id")]
        conversations = [dict(row) for row in conn.execute("SELECT * FROM conversations ORDER BY id")]
        summaries = [dict(row) for row in conn.execute("SELECT * FROM summaries ORDER BY id")]
    payload = {
        "format": FORMAT, "version": VERSION,
        "memories": [{key: row.get(key) for key in ("id", *MEMORY_FIELDS, "superseded_by")} for row in memories],
        "conversations": [{key: row.get(key) for key in ("id", *CONVERSATION_FIELDS)} for row in conversations],
        "summaries": [{key: row.get(key) for key in ("id", *SUMMARY_FIELDS)} for row in summaries],
        "notes": [
            "Contains private personal data; store this file securely.",
            "Embeddings are omitted and can be rebuilt after import.",
            "Candidate and maintenance queues and policy settings are not included.",
        ],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    # Write then atomically replace only after complete JSON serialization.
    temp = target.with_name(target.name + ".tmp")
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if target.exists() and not overwrite:
            raise FileExistsError(f"Export file already exists: {target}")
        temp.replace(target)
    finally:
        if temp.exists():
            temp.unlink()
    return {"path": str(target), "memories": len(memories), "conversations": len(conversations),
            "summaries": len(summaries), "ok": True}


def _validate(payload: Any, *, allow_sensitive: bool) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(payload, dict) or payload.get("format") != FORMAT or payload.get("version") != VERSION:
        raise ValueError(f"Unsupported export format; expected {FORMAT!r} version {VERSION}.")
    collections = {}
    for name in ("memories", "conversations", "summaries"):
        value = payload.get(name)
        if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
            raise ValueError(f"Export field {name!r} must be an array of objects.")
        collections[name] = value
    for row in collections["memories"]:
        if not isinstance(row.get("text"), str) or not row["text"].strip():
            raise ValueError("Every memory must contain non-empty text.")
        if row.get("source_type", "user_statement") not in VALID_SOURCE_TYPES:
            raise ValueError("Export contains an unsupported memory source_type.")
        if row.get("status", "active") not in VALID_STATUSES:
            raise ValueError("Export contains an unsupported memory status.")
        if row.get("sensitivity", "normal") == "sensitive" and not allow_sensitive:
            raise PermissionError("Export contains sensitive memories; re-run import with explicit --allow-sensitive.")
        if row.get("sensitivity", "normal") not in {"normal", "sensitive"}:
            raise ValueError("Export contains an unsupported sensitivity value.")
        try:
            if not 0 <= float(row.get("confidence", 1.0)) <= 1:
                raise ValueError("Memory confidence must be between 0 and 1.")
            if not 1 <= int(row.get("importance", 3)) <= 5:
                raise ValueError("Memory importance must be between 1 and 5.")
        except (TypeError, ValueError) as exc:
            raise ValueError("Export contains invalid confidence or importance.") from exc
    for row in collections["conversations"]:
        if row.get("role") not in VALID_ROLES or not isinstance(row.get("content"), str):
            raise ValueError("Export contains an invalid conversation message.")
    for row in collections["summaries"]:
        if row.get("scope") not in {"user", "project", "conversation"} or not row.get("scope_key"):
            raise ValueError("Export contains an invalid summary.")
        if not isinstance(row.get("content"), str):
            raise ValueError("Summary content must be text.")
    return collections


def import_json(database: str | Path, source: str | Path, *, allow_sensitive: bool = False) -> dict[str, Any]:
    target = Path(database).expanduser().resolve()
    input_path = Path(source).expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Export file does not exist: {input_path}")
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    data = _validate(payload, allow_sensitive=allow_sensitive)
    if not target.is_file():
        raise FileNotFoundError(f"Target database does not exist; initialize it first: {target}")

    memory_id_map: dict[int, int] = {}
    with sqlite3.connect(target) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        # All records are inserted in one transaction; any failure rolls back the import.
        for row in data["memories"]:
            columns = list(MEMORY_FIELDS)
            values = []
            for field in columns:
                default = {
                    "category": "general", "project": "general", "source_type": "user_statement",
                    "source_ref": None, "confidence": 1.0, "importance": 3, "sensitivity": "normal",
                    "status": "active", "created_at": None, "updated_at": None,
                    "last_accessed_at": None, "access_count": 0, "tags": "", "note": "",
                }.get(field)
                values.append(row.get(field, default))
            cols = ", ".join(columns)
            placeholders = ", ".join(
                "COALESCE(?, strftime('%Y-%m-%dT%H:%M:%fZ','now'))"
                if field in {"created_at", "updated_at"} else "?"
                for field in columns
            )
            cur = conn.execute(f"INSERT INTO memories ({cols}) VALUES ({placeholders})", values)
            old_id = row.get("id")
            if isinstance(old_id, int):
                memory_id_map[old_id] = int(cur.lastrowid)
        for row in data["memories"]:
            old_id, old_parent = row.get("id"), row.get("superseded_by")
            if isinstance(old_id, int) and isinstance(old_parent, int) and old_parent in memory_id_map:
                conn.execute("UPDATE memories SET superseded_by=? WHERE id=?",
                             (memory_id_map[old_parent], memory_id_map[old_id]))
        for row in data["conversations"]:
            conn.execute(
                "INSERT INTO conversations (conversation_id, project, role, content, created_at, metadata) VALUES (?, ?, ?, ?, COALESCE(?, strftime('%Y-%m-%dT%H:%M:%fZ','now')), ?)",
                (row.get("conversation_id", "imported"), row.get("project", "general"),
                 row["role"], row["content"], row.get("created_at"), row.get("metadata", "")),
            )
        for row in data["summaries"]:
            conn.execute(
                """INSERT INTO summaries (scope, scope_key, content, source_ref, created_at, updated_at)
                   VALUES (?, ?, ?, ?, COALESCE(?, strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                           COALESCE(?, strftime('%Y-%m-%dT%H:%M:%fZ','now')))
                   ON CONFLICT(scope, scope_key) DO UPDATE SET content=excluded.content,
                   source_ref=excluded.source_ref, updated_at=excluded.updated_at""",
                (row["scope"], row["scope_key"], row["content"], row.get("source_ref"),
                 row.get("created_at"), row.get("updated_at")),
            )
    return {"database": str(target), "memories_imported": len(data["memories"]),
            "conversations_imported": len(data["conversations"]),
            "summaries_imported": len(data["summaries"]), "ok": True}

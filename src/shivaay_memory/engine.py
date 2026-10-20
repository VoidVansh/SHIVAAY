"""Memory policies, retrieval, maintenance, and conversation archive."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from typing import Any, Iterable

from .store import MemoryStore


SENSITIVE_HINTS = (
    "password", "passcode", "private key", "secret key", "api key",
    "medical diagnosis", "bank account", "credit card", "home address",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _terms(query: str) -> str:
    """Convert user text into a safe FTS5 OR query; avoid raw FTS syntax."""
    words = re.findall(r"[\w-]{2,}", query.casefold())
    return " OR ".join('"' + w.replace('"', '""') + '"' for w in words[:24])


class MemoryEngine:
    """High-level API used by the SHIVAAY application."""

    def __init__(self, db_path: str | None = None) -> None:
        self.store = MemoryStore(db_path)

    def add_memory(
        self,
        text: str,
        *,
        category: str = "general",
        project: str = "general",
        source_type: str = "user_statement",
        source_ref: str | None = None,
        confidence: float = 1.0,
        importance: int = 3,
        sensitivity: str = "normal",
        approve_sensitive: bool = False,
        tags: Iterable[str] = (),
        note: str = "",
    ) -> int:
        text = text.strip()
        if not text:
            raise ValueError("Memory text cannot be empty.")
        if source_type not in {"user_statement", "assistant_inference", "conversation_summary", "external_source", "user_correction"}:
            raise ValueError("Unsupported source_type.")
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1.")
        if not 1 <= importance <= 5:
            raise ValueError("importance must be between 1 and 5.")
        if sensitivity not in {"normal", "sensitive"}:
            raise ValueError("sensitivity must be normal or sensitive.")
        if sensitivity == "sensitive" and not approve_sensitive:
            raise PermissionError("Sensitive memory requires explicit approval.")
        if sensitivity == "normal" and any(hint in text.casefold() for hint in SENSITIVE_HINTS):
            raise PermissionError("This text looks sensitive. Mark it sensitive and explicitly approve storage, or remove the sensitive detail.")

        with self.store.connect() as conn:
            cur = conn.execute(
                """INSERT INTO memories
                   (text, category, project, source_type, source_ref, confidence,
                    importance, sensitivity, tags, note)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (text, category.strip() or "general", project.strip() or "general",
                 source_type, source_ref, confidence, importance, sensitivity,
                 ",".join(sorted({t.strip() for t in tags if t.strip()})), note),
            )
            return int(cur.lastrowid)

    def get_memory(self, memory_id: int) -> dict[str, Any] | None:
        rows = self.store.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        return rows[0] if rows else None

    def list_memories(
        self, *, project: str | None = None, include_superseded: bool = False, limit: int = 100
    ) -> list[dict[str, Any]]:
        where, params = [], []
        if not include_superseded:
            where.append("status = 'active'")
        if project:
            where.append("project = ?")
            params.append(project)
        sql = "SELECT * FROM memories"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY importance DESC, updated_at DESC LIMIT ?"
        params.append(max(1, min(limit, 500)))
        return self.store.execute(sql, tuple(params))

    def search(self, query: str, *, project: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        fts_query = _terms(query)
        if not fts_query:
            return []
        where = ["memories_fts MATCH ?", "m.status = 'active'"]
        params: list[Any] = [fts_query]
        if project:
            where.append("m.project = ?")
            params.append(project)
        params.append(max(1, min(limit, 100)))
        try:
            rows = self.store.execute(
                f"""SELECT m.*, bm25(memories_fts, 1.0, 0.3, 0.2, 0.1) AS lexical_rank
                    FROM memories_fts JOIN memories m ON m.id = memories_fts.rowid
                    WHERE {' AND '.join(where)}
                    ORDER BY lexical_rank ASC, m.importance DESC, m.updated_at DESC
                    LIMIT ?""",
                tuple(params),
            )
        except Exception as exc:
            if "fts5" in str(exc).casefold() or "no such table" in str(exc).casefold():
                raise RuntimeError("SQLite FTS5 is unavailable in this Python build.") from exc
            raise
        if rows:
            ids = [r["id"] for r in rows]
            with self.store.connect() as conn:
                conn.executemany(
                    "UPDATE memories SET last_accessed_at = ?, access_count = access_count + 1 WHERE id = ?",
                    [(_now(), i) for i in ids],
                )
        return rows

    def retrieve(self, query: str, *, project: str | None = None, limit: int = 8) -> list[dict[str, Any]]:
        """Retrieve lexical matches then rank with importance, confidence, and recency."""
        candidates = self.search(query, project=project, limit=max(limit * 4, 20))
        now = datetime.now(timezone.utc)
        scored = []
        for item in candidates:
            try:
                updated = datetime.fromisoformat(item["updated_at"].replace("Z", "+00:00"))
                age_days = max(0.0, (now - updated).total_seconds() / 86400)
            except (ValueError, TypeError):
                age_days = 365
            recency = math.exp(-age_days / 180)
            lexical = 1.0 / (1.0 + max(0.0, float(item.get("lexical_rank") or 0)))
            score = (
                0.42 * lexical
                + 0.24 * (item["importance"] / 5)
                + 0.20 * item["confidence"]
                + 0.14 * recency
            )
            item["retrieval_score"] = round(score, 4)
            scored.append(item)
        scored.sort(key=lambda x: x["retrieval_score"], reverse=True)
        return scored[:max(1, min(limit, 50))]

    def correct_memory(
        self, memory_id: int, new_text: str, *, reason: str = "User correction",
        category: str | None = None, project: str | None = None,
    ) -> int:
        old = self.get_memory(memory_id)
        if not old:
            raise KeyError(f"No memory with id {memory_id}.")
        if old["status"] != "active":
            raise ValueError("Only active memories can be corrected.")
        new_id = self.add_memory(
            new_text,
            category=category or old["category"],
            project=project or old["project"],
            source_type="user_correction",
            source_ref=f"memory:{memory_id}",
            confidence=1.0,
            importance=old["importance"],
            sensitivity=old["sensitivity"],
            approve_sensitive=old["sensitivity"] == "sensitive",
            tags=old["tags"].split(",") if old["tags"] else (),
            note=reason,
        )
        with self.store.connect() as conn:
            conn.execute(
                """UPDATE memories SET status='superseded', superseded_by=?,
                   updated_at=? WHERE id=?""",
                (new_id, _now(), memory_id),
            )
        return new_id

    def archive_conversation(
        self, conversation_id: str, messages: Iterable[dict[str, str]], *, project: str = "general"
    ) -> int:
        if not conversation_id.strip():
            raise ValueError("conversation_id cannot be empty.")
        count = 0
        with self.store.connect() as conn:
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "").strip()
                if role not in {"user", "assistant", "system", "tool"} or not content:
                    continue
                conn.execute(
                    "INSERT INTO conversations (conversation_id, project, role, content) VALUES (?, ?, ?, ?)",
                    (conversation_id, project, role, content),
                )
                count += 1
        return count

    def search_conversations(
        self, query: str, *, project: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        fts_query = _terms(query)
        if not fts_query:
            return []
        where = ["conversations_fts MATCH ?"]
        params: list[Any] = [fts_query]
        if project:
            where.append("c.project = ?")
            params.append(project)
        params.append(max(1, min(limit, 100)))
        return self.store.execute(
            f"""SELECT c.* FROM conversations_fts
                JOIN conversations c ON c.id=conversations_fts.rowid
                WHERE {' AND '.join(where)}
                ORDER BY c.id DESC LIMIT ?""",
            tuple(params),
        )

    def save_summary(self, scope: str, key: str, content: str, *, source_ref: str | None = None) -> None:
        if scope not in {"user", "project", "conversation"}:
            raise ValueError("scope must be user, project, or conversation.")
        if not key.strip() or not content.strip():
            raise ValueError("Summary key and content cannot be empty.")
        with self.store.connect() as conn:
            conn.execute(
                """INSERT INTO summaries(scope, scope_key, content, source_ref)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(scope, scope_key) DO UPDATE SET
                   content=excluded.content, source_ref=excluded.source_ref,
                   updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')""",
                (scope, key, content.strip(), source_ref),
            )

    def get_summary(self, scope: str, key: str) -> dict[str, Any] | None:
        rows = self.store.execute(
            "SELECT * FROM summaries WHERE scope=? AND scope_key=?", (scope, key)
        )
        return rows[0] if rows else None

    def build_context(
        self, query: str, *, project: str | None = None, limit: int = 8,
        memory_override: list[dict[str, Any]] | None = None, max_chars: int = 8000,
    ) -> str:
        """Pack relevant context into a bounded, source-labelled character budget.

        This is a dependency-free safety bound, not an exact model-token counter.
        Higher-priority summaries and ranked memories are considered before older
        conversation excerpts. Individual entries are clipped only when needed
        to preserve their source label within the remaining budget.
        """
        budget = max(500, min(int(max_chars), 50000))
        chunks: list[str] = []
        used = 0

        def add_group(title: str, entries: list[str]) -> None:
            nonlocal used
            if not entries or used >= budget:
                return
            heading = f"[{title}]"
            if used + len(heading) + 1 > budget:
                return
            chunks.append(heading)
            used += len(heading) + 1
            for entry in entries:
                if used >= budget:
                    break
                remaining = budget - used - 1
                if remaining <= 0:
                    break
                if len(entry) > remaining:
                    # Preserve the beginning/source metadata; do not split into another entry.
                    if remaining >= 80:
                        entry = entry[:remaining - 1].rstrip() + "…"
                    else:
                        break
                chunks.append(entry)
                used += len(entry) + 1
                if used >= budget:
                    break

        project_summary = self.get_summary("project", project) if project else None
        user_summary = self.get_summary("user", "default")
        if project_summary:
            content = project_summary["content"].strip()
            add_group(f"Project summary: {project}", [content[:1600] + ("…" if len(content) > 1600 else "")])
        if user_summary:
            content = user_summary["content"].strip()
            add_group("User summary", [content[:1600] + ("…" if len(content) > 1600 else "")])

        memories = memory_override if memory_override is not None else self.retrieve(query, project=project, limit=limit)
        memory_entries = []
        for memory in memories[:max(1, min(limit, 50))]:
            text = memory["text"].replace("\\n", " ").strip()
            if len(text) > 1200:
                text = text[:1197] + "..."
            score = memory.get("hybrid_score", memory.get("retrieval_score"))
            score_label = f"; score={score:.3f}" if isinstance(score, (int, float)) else ""
            memory_entries.append(
                f"- (memory #{memory['id']}; source={memory['source_type']}; "
                f"confidence={memory['confidence']:.2f}; project={memory['project']}{score_label}) {text}"
            )
        add_group("Relevant saved memories", memory_entries)

        conversations = self.search_conversations(query, project=project, limit=min(limit, 5))
        conversation_entries = []
        for item in conversations:
            excerpt = item["content"].replace("\\n", " ").strip()
            if len(excerpt) > 500:
                excerpt = excerpt[:497] + "..."
            conversation_entries.append(
                f"- ({item['role']}, conversation={item['conversation_id']}) {excerpt}"
            )
        add_group("Relevant conversation excerpts — verify against full conversation if needed",
                  conversation_entries)
        return "\\n".join(chunks) if chunks else "[No relevant saved context found.]"

    def delete_memory(self, memory_id: int) -> bool:
        """Explicit hard deletion; caller should confirm with the user first."""
        with self.store.connect() as conn:
            cur = conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
            return cur.rowcount > 0

    def stats(self) -> dict[str, int]:
        result = {}
        for table in ("memories", "conversations", "summaries"):
            rows = self.store.execute(f"SELECT COUNT(*) AS count FROM {table}")
            result[table] = rows[0]["count"]
        return result

"""Conservative memory candidate extraction and review queue.

This first extractor is deliberately rule-based: it proposes candidates but never
silently turns every message into a durable fact. A future model-backed extractor
can implement the same CandidateExtractor interface and feed this review queue.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .engine import MemoryEngine
from .maintenance import possible_conflict_text
from .scoring import score_candidate


@dataclass(frozen=True)
class MemoryCandidate:
    text: str
    category: str = "general"
    project: str = "general"
    source_type: str = "user_statement"
    confidence: float = 0.72
    importance: int = 3
    reason: str = "Matched a conservative memory heuristic."


class CandidateExtractor:
    """Interface for extracting candidate memories from a conversation."""

    def extract(self, messages: Iterable[dict[str, str]], *, project: str = "general") -> list[MemoryCandidate]:
        raise NotImplementedError


class RuleBasedExtractor(CandidateExtractor):
    """Low-dependency baseline for explicit, potentially durable user statements."""

    RULES = [
        (re.compile(r"\b(?:remember|please remember|don't forget)\s+(?:that\s+)?(.{8,220})", re.I),
         "preference", 4, "Explicit remember request"),
        (re.compile(r"\b(?:I prefer|I like|I love|I hate|I don't like|I dislike)\s+(.{5,180})", re.I),
         "preference", 3, "Explicit preference"),
        (re.compile(r"\b(?:my goal is|I want to|I plan to|I'm building|I am building|my project is)\s+(.{8,200})", re.I),
         "goal", 4, "Explicit goal or project statement"),
        (re.compile(r"\b(?:we decided|decision:|the plan is)\s+(.{8,200})", re.I),
         "decision", 4, "Explicit decision"),
        (re.compile(r"\b(?:always|never)\s+(?:be\s+)?(.{8,160})", re.I),
         "preference", 3, "Possible stable rule or preference"),
    ]

    def extract(self, messages: Iterable[dict[str, str]], *, project: str = "general") -> list[MemoryCandidate]:
        found: dict[str, MemoryCandidate] = {}
        for message in messages:
            if message.get("role") != "user":
                continue
            content = (message.get("content") or "").strip()
            if not content or len(content) > 12000:
                continue
            for pattern, category, importance, reason in self.RULES:
                for match in pattern.finditer(content):
                    captured = match.group(1).strip(" \t\r\n.,;:")
                    if len(captured) < 8:
                        continue
                    # Keep the original claim in context rather than storing only a fragment.
                    start = max(0, match.start() - 45)
                    end = min(len(content), match.end() + 30)
                    candidate_text = re.sub(r"\s+", " ", content[start:end]).strip()
                    if len(candidate_text) > 260:
                        candidate_text = candidate_text[:257] + "..."
                    key = re.sub(r"\W+", " ", candidate_text.casefold()).strip()
                    found.setdefault(key, MemoryCandidate(
                        text=candidate_text, category=category, project=project,
                        confidence=0.72, importance=importance, reason=reason,
                    ))
        return list(found.values())


class CandidateQueue:
    """SQLite queue for proposed memories, stored beside the main memory tables."""

    def __init__(self, engine: MemoryEngine):
        self.engine = engine
        self.db_path = engine.store.db_path
        with engine.store.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    category TEXT NOT NULL,
                    project TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_ref TEXT,
                    confidence REAL NOT NULL,
                    importance INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending','approved','rejected','duplicate')),
                    memory_id INTEGER,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    reviewed_at TEXT
                )
            """)
            # Safe additive migration for databases created by older SHIVAAY versions.
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(memory_candidates)").fetchall()}
            if "recurrence_count" not in columns:
                conn.execute("ALTER TABLE memory_candidates ADD COLUMN recurrence_count INTEGER NOT NULL DEFAULT 1")
            if "last_seen_at" not in columns:
                conn.execute("ALTER TABLE memory_candidates ADD COLUMN last_seen_at TEXT")
            conn.execute("UPDATE memory_candidates SET last_seen_at=created_at WHERE last_seen_at IS NULL")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_candidates_status ON memory_candidates(status, id DESC)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_policy (
                    id INTEGER PRIMARY KEY CHECK(id=1),
                    auto_save_enabled INTEGER NOT NULL DEFAULT 0,
                    min_confidence REAL NOT NULL DEFAULT 0.90,
                    min_score REAL NOT NULL DEFAULT 0.85,
                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                )
            """)
            conn.execute("INSERT OR IGNORE INTO memory_policy(id) VALUES (1)")

    def propose(self, candidates: Iterable[MemoryCandidate], *, source_ref: str | None = None) -> list[int]:
        ids: list[int] = []
        with self.engine.store.connect() as conn:
            for candidate in candidates:
                normalized = re.sub(r"\W+", " ", candidate.text.casefold()).strip()
                if not normalized:
                    continue
                exists = conn.execute(
                    """SELECT id FROM memory_candidates
                       WHERE project=? AND status IN ('pending','approved')
                       AND lower(text)=lower(?) LIMIT 1""",
                    (candidate.project, candidate.text),
                ).fetchone()
                if exists:
                    # Repeated exact mentions are useful evidence of durability.
                    # Keep the same review item; never create duplicate memories.
                    conn.execute(
                        """UPDATE memory_candidates
                           SET recurrence_count=recurrence_count+1,
                               last_seen_at=strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                               confidence=MAX(confidence, ?),
                               importance=MAX(importance, ?)
                           WHERE id=?""",
                        (candidate.confidence, candidate.importance, exists["id"]),
                    )
                    continue
                cur = conn.execute(
                    """INSERT INTO memory_candidates
                       (text, category, project, source_type, source_ref, confidence, importance, reason)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (candidate.text, candidate.category, candidate.project, candidate.source_type,
                     source_ref, candidate.confidence, candidate.importance, candidate.reason),
                )
                ids.append(int(cur.lastrowid))
        policy = self.get_policy()
        if policy["auto_save_enabled"]:
            for candidate_id in ids:
                rows = self.engine.store.execute(
                    "SELECT * FROM memory_candidates WHERE id=? AND status='pending'", (candidate_id,)
                )
                if not rows:
                    continue
                row = rows[0]
                metrics = score_candidate(row)
                if (metrics["sensitivity_risk"] != 0
                        or row["confidence"] < policy["min_confidence"]
                        or metrics["score"] < policy["min_score"]):
                    continue
                # Never silently auto-save a likely contradiction of an active memory.
                # The candidate stays pending so the user can decide which claim is current.
                active_memories = self.engine.list_memories(project=row["project"], limit=500)
                if any(possible_conflict_text(row["text"], memory["text"])
                       for memory in active_memories):
                    continue
                try:
                    self.approve(candidate_id)
                except PermissionError:
                    # Sensitive-text safeguards are authoritative over auto-save policy.
                    continue
        return ids

    def get_policy(self) -> dict:
        rows = self.engine.store.execute("SELECT * FROM memory_policy WHERE id=1")
        return dict(rows[0]) if rows else {"auto_save_enabled": 0, "min_confidence": 0.90, "min_score": 0.85}

    def set_policy(self, *, auto_save_enabled: bool | None = None,
                   min_confidence: float | None = None, min_score: float | None = None) -> dict:
        current = self.get_policy()
        confidence = current["min_confidence"] if min_confidence is None else min_confidence
        score = current["min_score"] if min_score is None else min_score
        if not 0 <= confidence <= 1 or not 0 <= score <= 1:
            raise ValueError("Policy thresholds must be between 0 and 1.")
        enabled = current["auto_save_enabled"] if auto_save_enabled is None else int(auto_save_enabled)
        with self.engine.store.connect() as conn:
            conn.execute("""UPDATE memory_policy SET auto_save_enabled=?, min_confidence=?, min_score=?,
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=1""",
                (int(bool(enabled)), confidence, score))
        return self.get_policy()

    def list(self, *, status: str = "pending", limit: int = 50) -> list[dict]:
        if status not in {"pending", "approved", "rejected", "duplicate", "all"}:
            raise ValueError("Unsupported candidate status.")
        sql = "SELECT * FROM memory_candidates"
        params: list = []
        if status != "all":
            sql += " WHERE status=?"
            params.append(status)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        rows = self.engine.store.execute(sql, tuple(params))
        enriched = []
        policy = self.get_policy()
        active_by_project: dict[str, list[dict]] = {}
        for row in rows:
            item = dict(row)
            metrics = score_candidate(item)
            item.update({f"score_{key}": value for key, value in metrics.items()})
            if item["status"] != "pending":
                decision, reason = item["status"], "Candidate has already been reviewed."
            elif not policy["auto_save_enabled"]:
                decision, reason = "review", "Automatic saving is disabled."
            elif metrics["sensitivity_risk"] != 0:
                decision, reason = "blocked", "Sensitivity heuristic flagged this candidate."
            elif item["confidence"] < policy["min_confidence"]:
                decision, reason = "review", "Confidence is below the configured auto-save threshold."
            elif metrics["score"] < policy["min_score"]:
                decision, reason = "review", "Score is below the configured auto-save threshold."
            else:
                project = item["project"]
                if project not in active_by_project:
                    active_by_project[project] = self.engine.list_memories(project=project, limit=500)
                conflict = any(possible_conflict_text(item["text"], memory["text"])
                               for memory in active_by_project[project])
                if conflict:
                    decision, reason = "blocked", "Possible contradiction with an active memory; review manually."
                else:
                    decision, reason = "eligible", (
                        "Meets current thresholds; queued items are not auto-approved retroactively."
                    )
            item["auto_save_decision"] = decision
            item["auto_save_reason"] = reason
            enriched.append(item)
        return enriched

    def approve(self, candidate_id: int) -> int:
        with self.engine.store.connect() as conn:
            row = conn.execute("SELECT * FROM memory_candidates WHERE id=?", (candidate_id,)).fetchone()
            if not row:
                raise KeyError(f"No candidate with id {candidate_id}.")
            if row["status"] != "pending":
                raise ValueError(f"Candidate is already {row['status']}.")
            # Avoid creating an obvious duplicate of an active memory.
            active = conn.execute(
                "SELECT id, text FROM memories WHERE project=? AND status='active'",
                (row["project"],),
            ).fetchall()
            candidate_norm = re.sub(r"\W+", " ", row["text"].casefold()).strip()
            for item in active:
                old_norm = re.sub(r"\W+", " ", item["text"].casefold()).strip()
                if candidate_norm == old_norm:
                    conn.execute(
                        "UPDATE memory_candidates SET status='duplicate', memory_id=?, reviewed_at=? WHERE id=?",
                        (item["id"], datetime.now(timezone.utc).isoformat(), candidate_id),
                    )
                    return int(item["id"])
        memory_id = self.engine.add_memory(
            row["text"], category=row["category"], project=row["project"],
            source_type=row["source_type"], source_ref=row["source_ref"],
            confidence=row["confidence"], importance=row["importance"],
            note=f"Approved candidate #{candidate_id}: {row['reason']}",
        )
        with self.engine.store.connect() as conn:
            conn.execute(
                "UPDATE memory_candidates SET status='approved', memory_id=?, reviewed_at=? WHERE id=?",
                (memory_id, datetime.now(timezone.utc).isoformat(), candidate_id),
            )
        return memory_id

    def reject(self, candidate_id: int) -> None:
        with self.engine.store.connect() as conn:
            cur = conn.execute(
                "UPDATE memory_candidates SET status='rejected', reviewed_at=? WHERE id=? AND status='pending'",
                (datetime.now(timezone.utc).isoformat(), candidate_id),
            )
            if cur.rowcount == 0:
                row = conn.execute("SELECT status FROM memory_candidates WHERE id=?", (candidate_id,)).fetchone()
                if not row:
                    raise KeyError(f"No candidate with id {candidate_id}.")
                raise ValueError(f"Candidate is already {row['status']}.")


def extract_from_json(engine: MemoryEngine, file_path: str, *, project: str = "general",
                      source_ref: str | None = None) -> list[int]:
    import json
    with open(Path(file_path), "r", encoding="utf-8") as handle:
        messages = json.load(handle)
    if not isinstance(messages, list):
        raise ValueError("Conversation JSON must be an array of {role, content} objects.")
    candidates = RuleBasedExtractor().extract(messages, project=project)
    return CandidateQueue(engine).propose(candidates, source_ref=source_ref)

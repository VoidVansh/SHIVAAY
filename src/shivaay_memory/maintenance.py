"""Conservative, review-first maintenance for saved memories.

This module never edits memories during a scan. It creates review suggestions
for likely duplicates and possible contradictions; the user must explicitly
apply or dismiss each suggestion.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from .engine import MemoryEngine

_NEGATIONS = {"not", "never", "no", "don't", "dont", "doesn't", "doesnt", "isn't", "isnt", "can't", "cant", "won't", "wont"}
_STOP = {"the", "a", "an", "is", "am", "are", "was", "were", "to", "of", "for", "and", "or", "in", "on", "with", "my", "i", "we", "it", "this", "that"}


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9']+", text.casefold()) if w not in _STOP}


def _similarity(a: str, b: str) -> float:
    left, right = " ".join(sorted(_tokens(a))), " ".join(sorted(_tokens(b)))
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _same_subject(a: str, b: str) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / max(1, min(len(ta), len(tb))) >= 0.72


def possible_conflict_text(a: str, b: str) -> bool:
    """Return a conservative warning signal for shared claims with differing negation.

    This is a heuristic guardrail, not natural-language entailment. Callers should
    route matches to review rather than automatically choosing either statement.
    """
    negation_differs = bool(_tokens(a) & _NEGATIONS) != bool(_tokens(b) & _NEGATIONS)
    return _same_subject(a, b) and negation_differs and _similarity(a, b) >= 0.45


_CLAIM_FAMILIES = (
    re.compile(r"\\b(i\\s+prefer)\\s+(.+)", re.I),
    re.compile(r"\\b(i\\s+(?:like|love|hate|want|need))\\s+(.+)", re.I),
    re.compile(r"\\b(i\\s+(?:plan to|intend to|use|study))\\s+(.+)", re.I),
    re.compile(r"\\b(my\\s+(?:goal|project|plan)\\s+is)\\s+(.+)", re.I),
    re.compile(r"\\b(i\\s+am\\s+building)\\s+(.+)", re.I),
)
_EXPLICIT_UPDATE_CUE = re.compile(
    r"\\b(?:actually|instead|from now on|no longer|not anymore|rather than|"
    r"correction|update:|i changed my mind|i now prefer|i now want)\\b",
    re.I,
)


def possible_update_text(new_text: str, existing_text: str) -> bool:
    """Detect an explicit, same-claim-family update that needs user review.

    This deliberately requires an update cue in the new statement. It does not
    assume that two different preferences or goals automatically contradict.
    """
    if not _EXPLICIT_UPDATE_CUE.search(new_text):
        return False
    def claim(text: str) -> tuple[str, str] | None:
        for pattern in _CLAIM_FAMILIES:
            match = pattern.search(text)
            if match:
                predicate = re.sub(r"\\s+", " ", match.group(1).casefold()).strip()
                value = re.split(r"[.!?;\\n]", match.group(2), maxsplit=1)[0]
                value = " ".join(sorted(_tokens(value)))
                return predicate, value
        return None
    new_claim, old_claim = claim(new_text), claim(existing_text)
    return bool(new_claim and old_claim and new_claim[0] == old_claim[0]
                and new_claim[1] and old_claim[1] and new_claim[1] != old_claim[1])


class MemoryMaintenance:
    """Find potential maintenance actions and persist them for human review."""

    def __init__(self, engine: MemoryEngine) -> None:
        self.engine = engine
        with engine.store.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS maintenance_suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_id INTEGER NOT NULL REFERENCES memories(id),
                    compared_memory_id INTEGER REFERENCES memories(id),
                    kind TEXT NOT NULL CHECK(kind IN ('possible_duplicate','possible_conflict')),
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending','applied','dismissed','stale')),
                    applied_memory_id INTEGER REFERENCES memories(id),
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                    UNIQUE(memory_id, compared_memory_id, kind)
                )
            """)

    def scan(self, *, project: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        """Create suggestions without changing active memories."""
        memories = self.engine.list_memories(project=project, limit=limit)
        memories.sort(key=lambda item: item["id"])  # deterministic pair direction and review history
        created: list[dict[str, Any]] = []
        with self.engine.store.connect() as conn:
            for i, first in enumerate(memories):
                for second in memories[i + 1:]:
                    score = _similarity(first["text"], second["text"])
                    negation_differs = bool(_tokens(first["text"]) & _NEGATIONS) != bool(_tokens(second["text"]) & _NEGATIONS)
                    if _same_subject(first["text"], second["text"]) and negation_differs and score >= 0.45:
                        kind = "possible_conflict"
                        reason = "These memories share key terms but differ in negation; check whether one corrects the other."
                    elif score >= 0.82:
                        kind = "possible_duplicate"
                        reason = f"These memories are highly similar (text similarity {score:.2f}); review whether one is redundant."
                    else:
                        continue
                    cur = conn.execute(
                        """INSERT OR IGNORE INTO maintenance_suggestions
                           (memory_id, compared_memory_id, kind, reason)
                           VALUES (?, ?, ?, ?)""",
                        (first["id"], second["id"], kind, reason),
                    )
                    if cur.rowcount:
                        created.append({"id": cur.lastrowid, "memory_id": first["id"],
                                        "compared_memory_id": second["id"], "kind": kind,
                                        "reason": reason, "status": "pending"})
        return created

    def list(self, *, status: str = "pending", limit: int = 100) -> list[dict[str, Any]]:
        if status not in {"pending", "applied", "dismissed", "stale", "all"}:
            raise ValueError("Invalid maintenance suggestion status.")
        where = "" if status == "all" else "WHERE s.status = ?"
        params: tuple[Any, ...] = () if status == "all" else (status,)
        params += (max(1, min(limit, 500)),)
        return self.engine.store.execute(
            f"""SELECT s.*, m.text AS memory_text, c.text AS compared_text
                FROM maintenance_suggestions s
                JOIN memories m ON m.id=s.memory_id
                LEFT JOIN memories c ON c.id=s.compared_memory_id
                {where} ORDER BY s.id DESC LIMIT ?""", params
        )

    def apply(self, suggestion_id: int, *, chosen_text: str | None = None, reason: str | None = None) -> int:
        """Apply an explicitly reviewed suggestion as a correction with history."""
        rows = self.engine.store.execute(
            "SELECT * FROM maintenance_suggestions WHERE id=? AND status='pending'",
            (suggestion_id,),
        )
        if not rows:
            raise KeyError(f"No pending maintenance suggestion with id {suggestion_id}.")
        item = rows[0]
        old = self.engine.get_memory(item["memory_id"])
        if not old or old["status"] != "active":
            with self.engine.store.connect() as conn:
                conn.execute("UPDATE maintenance_suggestions SET status='stale' WHERE id=?", (suggestion_id,))
            raise ValueError("The source memory is no longer active; suggestion marked stale.")
        compared = self.engine.get_memory(item["compared_memory_id"]) if item["compared_memory_id"] else None
        text = (chosen_text or (compared["text"] if compared else "")).strip()
        if not text:
            raise ValueError("No replacement text available; supply chosen_text.")
        new_id = self.engine.correct_memory(item["memory_id"], text, reason=reason or f"Applied maintenance suggestion #{suggestion_id}")
        with self.engine.store.connect() as conn:
            conn.execute(
                "UPDATE maintenance_suggestions SET status='applied', applied_memory_id=? WHERE id=?",
                (new_id, suggestion_id),
            )
        return new_id

    def dismiss(self, suggestion_id: int) -> None:
        with self.engine.store.connect() as conn:
            cur = conn.execute(
                "UPDATE maintenance_suggestions SET status='dismissed' WHERE id=? AND status='pending'",
                (suggestion_id,),
            )
            if cur.rowcount == 0:
                raise KeyError(f"No pending maintenance suggestion with id {suggestion_id}.")

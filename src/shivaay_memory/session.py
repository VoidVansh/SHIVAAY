"""Conversation lifecycle helpers that connect chat turns to local memory.

This module is deliberately provider-neutral: the caller still owns model inference.
It retrieves context before a reply and archives/proposes memories after a reply.
Candidate extraction is opt-in via an injected extractor; proposals are never
approved automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .engine import MemoryEngine
from .extraction import CandidateExtractor, CandidateQueue


@dataclass(frozen=True)
class TurnResult:
    archived_messages: int
    candidate_ids: tuple[int, ...]


class MemorySession:
    """Small integration layer for an application chat loop."""

    def __init__(
        self,
        engine: MemoryEngine,
        *,
        extractor: CandidateExtractor | None = None,
        queue: CandidateQueue | None = None,
    ) -> None:
        self.engine = engine
        self.extractor = extractor
        self.queue = queue or CandidateQueue(engine)

    def context_for(
        self, user_message: str, *, project: str = "general", limit: int = 8,
        memory_override: list[dict] | None = None, max_chars: int = 8000,
        exclude_conversation_id: str | None = None,
    ) -> str:
        """Return source-labelled memory context to add to the model prompt."""
        return self.engine.build_context(user_message, project=project, limit=limit,
                                         memory_override=memory_override, max_chars=max_chars,
                                         exclude_conversation_id=exclude_conversation_id)

    def finish_turn(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
        *,
        project: str = "general",
    ) -> TurnResult:
        """Archive a completed turn and queue possible memories for human review."""
        messages = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_message},
        ]
        archived = self.engine.archive_conversation(
            conversation_id, messages, project=project
        )
        candidate_ids: list[int] = []
        if self.extractor is not None and user_message.strip():
            candidates = self.extractor.extract(
                [{"role": "user", "content": user_message}], project=project
            )
            candidate_ids = self.queue.propose(
                candidates, source_ref=conversation_id
            )
        return TurnResult(archived_messages=archived, candidate_ids=tuple(candidate_ids))

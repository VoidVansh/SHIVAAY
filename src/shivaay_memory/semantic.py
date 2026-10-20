"""Optional local semantic retrieval using embeddings from local Ollama.

The core package has no embedding dependency. Vectors are stored as JSON in
SQLite and cosine similarity is computed with the standard library.
"""
from __future__ import annotations

import ipaddress
import json
import math
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlsplit
from typing import Protocol, Sequence

from .engine import MemoryEngine


class EmbeddingBackend(Protocol):
    """Produces a numeric embedding for a string."""
    model: str

    def embed(self, text: str) -> list[float]:
        ...


class OllamaEmbeddingBackend:
    """Embedding client restricted to an Ollama server on loopback."""
    def __init__(self, model: str = "nomic-embed-text", host: str = "http://127.0.0.1:11434", timeout: int = 60):
        self.model = model.strip()
        self.host = host.rstrip("/")
        self.timeout = timeout
        parsed = urlsplit(self.host)
        hostname = (parsed.hostname or "").casefold()
        local = hostname == "localhost"
        if not local:
            try:
                local = ipaddress.ip_address(hostname).is_loopback
            except ValueError:
                local = False
        if not self.model:
            raise ValueError("Embedding model name cannot be empty.")
        if parsed.scheme != "http" or not local or parsed.username or parsed.password:
            raise ValueError("Embedding host must be an HTTP loopback URL; remote hosts are rejected.")

    def embed(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Cannot embed empty text.")
        payload = json.dumps({"model": self.model, "input": text}).encode("utf-8")
        req = urllib.request.Request(self.host + "/api/embed", data=payload,
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError("Could not reach local Ollama embeddings API. No remote fallback is attempted.") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Local Ollama returned invalid embedding JSON.") from exc
        vectors = data.get("embeddings")
        if not isinstance(vectors, list) or not vectors or not isinstance(vectors[0], list):
            raise RuntimeError("Local Ollama returned no embedding vector.")
        try:
            vector = [float(value) for value in vectors[0]]
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Embedding vector contains non-numeric values.") from exc
        if not vector or not all(math.isfinite(value) for value in vector):
            raise RuntimeError("Embedding vector is empty or contains invalid numbers.")
        return vector


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if norm_left == 0 or norm_right == 0:
        return 0.0
    return dot / (norm_left * norm_right)


class SemanticMemoryIndex:
    """SQLite-backed vector index. Rebuild it when changing embedding models."""
    def __init__(self, engine: MemoryEngine, backend: EmbeddingBackend):
        self.engine = engine
        self.backend = backend
        with self.engine.store.connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS memory_embeddings (
                memory_id INTEGER PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
                model TEXT NOT NULL, dimensions INTEGER NOT NULL, vector_json TEXT NOT NULL,
                updated_at TEXT NOT NULL)""")

    def index_memory(self, memory_id: int) -> None:
        memory = self.engine.get_memory(memory_id)
        if not memory:
            raise KeyError(f"No memory with id {memory_id}.")
        vector = self.backend.embed(memory["text"])
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.engine.store.connect() as conn:
            conn.execute("""INSERT INTO memory_embeddings(memory_id, model, dimensions, vector_json, updated_at)
                VALUES (?, ?, ?, ?, ?) ON CONFLICT(memory_id) DO UPDATE SET
                model=excluded.model, dimensions=excluded.dimensions,
                vector_json=excluded.vector_json, updated_at=excluded.updated_at""",
                (memory_id, self.backend.model, len(vector), json.dumps(vector), stamp))

    def index_all(self, *, project: str | None = None, limit: int = 10000) -> int:
        memories = self.engine.list_memories(project=project, limit=max(1, min(limit, 10000)))
        for memory in memories:
            self.index_memory(memory["id"])
        return len(memories)

    def hybrid_search(self, query: str, *, project: str | None = None, limit: int = 8,
                      lexical_weight: float = 0.55, semantic_weight: float = 0.45) -> list[dict]:
        """Fuse lexical and embedding rankings using weighted reciprocal-rank fusion.

        BM25 and cosine scores are not directly comparable, so fuse ranks rather
        than pretending their raw scores share a scale. Memories found by both
        methods receive evidence from both rankings.
        """
        if not 0 <= lexical_weight <= 1 or not 0 <= semantic_weight <= 1:
            raise ValueError("Hybrid weights must be between 0 and 1.")
        if lexical_weight + semantic_weight == 0:
            raise ValueError("At least one hybrid weight must be positive.")
        lexical = self.engine.retrieve(query, project=project, limit=max(20, limit * 3))
        semantic = self.search(query, project=project, limit=max(20, limit * 3))
        fused: dict[int, dict] = {}
        for rank, row in enumerate(lexical, start=1):
            item = dict(row)
            item["lexical_rank"] = rank
            item["hybrid_score"] = lexical_weight / (rank + 1)
            item["retrieval_sources"] = ["lexical"]
            fused[item["id"]] = item
        for rank, row in enumerate(semantic, start=1):
            memory_id = row["id"]
            if memory_id in fused:
                item = fused[memory_id]
                item["hybrid_score"] += semantic_weight / (rank + 1)
                item["semantic_rank"] = rank
                item["semantic_score"] = row.get("semantic_score")
                item["retrieval_sources"].append("semantic")
            else:
                item = dict(row)
                item["semantic_rank"] = rank
                item["hybrid_score"] = semantic_weight / (rank + 1)
                item["retrieval_sources"] = ["semantic"]
                fused[memory_id] = item
        results = sorted(fused.values(), key=lambda item: (
            item["hybrid_score"], item.get("importance", 0), item.get("confidence", 0)
        ), reverse=True)
        for item in results:
            item["hybrid_score"] = round(item["hybrid_score"], 6)
        return results[:max(1, min(limit, 50))]

    def search(self, query: str, *, project: str | None = None, limit: int = 8) -> list[dict]:
        query_vector = self.backend.embed(query)
        where = ["m.status='active'", "e.model=?", "e.dimensions=?"]
        params: list[object] = [self.backend.model, len(query_vector)]
        if project:
            where.append("m.project=?")
            params.append(project)
        rows = self.engine.store.execute(
            "SELECT m.*, e.vector_json FROM memory_embeddings e JOIN memories m ON m.id=e.memory_id WHERE "
            + " AND ".join(where), tuple(params))
        scored = []
        for row in rows:
            vector = json.loads(row.pop("vector_json"))
            score = cosine_similarity(query_vector, vector)
            row["semantic_score"] = round(score, 6)
            scored.append(row)
        scored.sort(key=lambda row: row["semantic_score"], reverse=True)
        return [row for row in scored if row["semantic_score"] > 0][:max(1, min(limit, 50))]

    def remove_stale_entries(self) -> int:
        """Drop vectors for deleted/superseded memories or a different model."""
        with self.engine.store.connect() as conn:
            cur = conn.execute("""DELETE FROM memory_embeddings WHERE memory_id NOT IN
                (SELECT id FROM memories WHERE status='active') OR model<>?""", (self.backend.model,))
            return cur.rowcount

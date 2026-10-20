"""Command-line utilities for optional local semantic memory retrieval."""
from __future__ import annotations

import argparse
import json
import sys

from .engine import MemoryEngine
from .semantic import OllamaEmbeddingBackend, SemanticMemoryIndex


def main() -> None:
    parser = argparse.ArgumentParser(prog="shivaay-semantic", description="Index and search SHIVAAY memories with local embeddings")
    parser.add_argument("--db", help="SQLite database path (or set SHIVAAY_MEMORY_DB)")
    parser.add_argument("--model", default="nomic-embed-text", help="Embedding model already available in local Ollama")
    parser.add_argument("--host", default="http://127.0.0.1:11434", help="Loopback Ollama host only")
    sub = parser.add_subparsers(dest="command", required=True)
    index = sub.add_parser("index", help="Embed all active memories into the local vector index")
    index.add_argument("--project")
    index.add_argument("--limit", type=int, default=10000)
    index.add_argument("--rebuild", action="store_true", help="Recompute vectors even when current-model vectors already exist")
    search = sub.add_parser("search", help="Find semantically similar saved memories")
    search.add_argument("query")
    search.add_argument("--project")
    search.add_argument("--limit", type=int, default=8)
    sub.add_parser("clean", help="Remove vectors for superseded/deleted memories or other models")
    args = parser.parse_args()
    try:
        engine = MemoryEngine(args.db)
        backend = OllamaEmbeddingBackend(model=args.model, host=args.host)
        indexer = SemanticMemoryIndex(engine, backend)
        if args.command == "index":
            count = indexer.index_all(project=args.project, limit=args.limit, force=args.rebuild)
            print(f"Created/refreshed {count} vector(s) using {args.model}; existing current-model vectors were reused unless --rebuild was set.")
        elif args.command == "search":
            print(json.dumps(indexer.search(args.query, project=args.project, limit=args.limit), indent=2, ensure_ascii=False))
        elif args.command == "clean":
            print(f"Removed {indexer.remove_stale_entries()} stale vector entry/entries.")
    except (ValueError, RuntimeError, KeyError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()

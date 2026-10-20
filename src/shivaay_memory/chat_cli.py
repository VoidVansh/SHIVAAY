"""Interactive command-line chat using local Ollama and SHIVAAY memory."""
from __future__ import annotations

import argparse
import sys

from .chat import MemoryChat, OllamaBackend
from .engine import MemoryEngine
from .extraction import RuleBasedExtractor
from .semantic import OllamaEmbeddingBackend, SemanticMemoryIndex


def main() -> None:
    parser = argparse.ArgumentParser(prog="shivaay-chat", description="Chat with SHIVAAY using local Ollama")
    parser.add_argument("--db", help="SQLite database path (or set SHIVAAY_MEMORY_DB)")
    parser.add_argument("--project", default="general", help="Memory scope for this chat")
    parser.add_argument("--model", default="qwen2.5:3b", help="Chat model already available in local Ollama")
    parser.add_argument("--host", default="http://127.0.0.1:11434", help="Local Ollama host; non-loopback hosts are rejected")
    parser.add_argument("--capture-candidates", action="store_true", help="Queue possible memories for review; never auto-approve")
    parser.add_argument("--semantic", action="store_true", help="Also retrieve memories by meaning using local embeddings")
    parser.add_argument("--embedding-model", default="nomic-embed-text", help="Embedding model available in local Ollama")
    args = parser.parse_args()

    try:
        engine = MemoryEngine(args.db)
        backend = OllamaBackend(model=args.model, host=args.host)
        semantic_index = None
        if args.semantic:
            semantic_backend = OllamaEmbeddingBackend(model=args.embedding_model, host=args.host)
            semantic_index = SemanticMemoryIndex(engine, semantic_backend)
            print("Indexing active memories for semantic retrieval; this may take a while on first run...")
            count = semantic_index.index_all(project=args.project)
            print(f"Indexed {count} memory/memories.")
        chat = MemoryChat(engine, backend, project=args.project,
                          extractor=RuleBasedExtractor() if args.capture_candidates else None,
                          semantic_index=semantic_index)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"SHIVAAY error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    retrieval = "lexical + semantic" if args.semantic else "lexical"
    print(f"SHIVAAY local chat · model={args.model} · project={args.project} · retrieval={retrieval}")
    print("Type /quit to exit. Chat turns are archived locally.")
    while True:
        try:
            user_text = input("\nYou: ")
        except (EOFError, KeyboardInterrupt):
            print("\nSHIVAAY: Session ended.")
            break
        if user_text.strip().casefold() in {"/exit", "/quit"}:
            break
        if not user_text.strip():
            continue
        try:
            answer, turn = chat.send(user_text)
            print(f"\nSHIVAAY: {answer}")
            if turn.candidate_ids:
                print(f"[Queued {len(turn.candidate_ids)} memory candidate(s). Review with shivaay-memory candidates.]")
        except (ValueError, RuntimeError) as exc:
            print(f"SHIVAAY error: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()

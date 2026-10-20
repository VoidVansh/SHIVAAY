"""Interactive command-line chat using local Ollama and SHIVAAY memory."""
from __future__ import annotations

import argparse
import sys

from .chat import MemoryChat, OllamaBackend
from .engine import MemoryEngine
from .extraction import RuleBasedExtractor


def main() -> None:
    parser = argparse.ArgumentParser(prog="shivaay-chat", description="Chat with SHIVAAY using local Ollama")
    parser.add_argument("--db", help="SQLite database path (or set SHIVAAY_MEMORY_DB)")
    parser.add_argument("--project", default="general", help="Memory scope for this chat")
    parser.add_argument("--model", default="qwen2.5:3b", help="Model already available in local Ollama")
    parser.add_argument("--host", default="http://127.0.0.1:11434", help="Local Ollama host; non-loopback hosts are rejected")
    parser.add_argument("--capture-candidates", action="store_true", help="Queue possible memories for review; never auto-approve")
    args = parser.parse_args()

    try:
        engine = MemoryEngine(args.db)
        backend = OllamaBackend(model=args.model, host=args.host)
        chat = MemoryChat(engine, backend, project=args.project,
                          extractor=RuleBasedExtractor() if args.capture_candidates else None)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"SHIVAAY error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    print(f"SHIVAAY local chat · model={args.model} · project={args.project}")
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
                print(f"[Queued {len(turn.candidate_ids)} memory candidate(s). Review with shivaay-memory candidates.] ")
        except (ValueError, RuntimeError) as exc:
            print(f"SHIVAAY error: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()

"""Command-line interface for the SHIVAAY memory engine."""

from __future__ import annotations

import argparse
import json
import sys

from .engine import MemoryEngine


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shivaay-memory", description="SHIVAAY local memory")
    parser.add_argument("--db", help="SQLite database path (or set SHIVAAY_MEMORY_DB)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialize the database and print its location")

    add = sub.add_parser("add", help="Save one memory")
    add.add_argument("--text", required=True)
    add.add_argument("--category", default="general")
    add.add_argument("--project", default="general")
    add.add_argument("--source", default="user_statement", dest="source_type",
                     choices=["user_statement", "assistant_inference", "conversation_summary", "external_source", "user_correction"])
    add.add_argument("--source-ref")
    add.add_argument("--confidence", type=float, default=1.0)
    add.add_argument("--importance", type=int, default=3, choices=range(1, 6))
    add.add_argument("--sensitive", action="store_true")
    add.add_argument("--approve-sensitive", action="store_true")
    add.add_argument("--tag", action="append", default=[])
    add.add_argument("--note", default="")

    search = sub.add_parser("search", help="Search saved memories")
    search.add_argument("query")
    search.add_argument("--project")
    search.add_argument("--limit", type=int, default=10)

    listing = sub.add_parser("list", help="List saved memories")
    listing.add_argument("--project")
    listing.add_argument("--include-superseded", action="store_true")
    listing.add_argument("--limit", type=int, default=100)

    correct = sub.add_parser("correct", help="Correct a memory while preserving its history")
    correct.add_argument("--id", required=True, type=int)
    correct.add_argument("--text", required=True)
    correct.add_argument("--reason", default="User correction")

    archive = sub.add_parser("archive", help="Archive conversation messages from a JSON file")
    archive.add_argument("--conversation-id", required=True)
    archive.add_argument("--file", required=True, help="JSON array of {role, content} messages")
    archive.add_argument("--project", default="general")

    summary = sub.add_parser("summary", help="Save or replace a scope summary")
    summary.add_argument("--scope", choices=["user", "project", "conversation"], required=True)
    summary.add_argument("--key", required=True)
    summary.add_argument("--text", required=True)
    summary.add_argument("--source-ref")

    context = sub.add_parser("context", help="Build prompt context from relevant memory")
    context.add_argument("query")
    context.add_argument("--project")
    context.add_argument("--limit", type=int, default=8)

    sub.add_parser("stats", help="Show local memory counts")
    delete = sub.add_parser("delete", help="Permanently delete a memory (cannot be undone)")
    delete.add_argument("--id", type=int, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    engine = MemoryEngine(args.db)
    try:
        if args.command == "init":
            print(f"Initialized: {engine.store.db_path}")
        elif args.command == "add":
            mid = engine.add_memory(
                args.text, category=args.category, project=args.project,
                source_type=args.source_type, source_ref=args.source_ref,
                confidence=args.confidence, importance=args.importance,
                sensitivity="sensitive" if args.sensitive else "normal",
                approve_sensitive=args.approve_sensitive, tags=args.tag, note=args.note,
            )
            print(f"Saved memory #{mid}")
        elif args.command == "search":
            print(json.dumps(engine.search(args.query, project=args.project, limit=args.limit), indent=2, ensure_ascii=False))
        elif args.command == "list":
            print(json.dumps(engine.list_memories(project=args.project, include_superseded=args.include_superseded, limit=args.limit), indent=2, ensure_ascii=False))
        elif args.command == "correct":
            print(f"Saved corrected memory as #{engine.correct_memory(args.id, args.text, reason=args.reason)}")
        elif args.command == "archive":
            with open(args.file, "r", encoding="utf-8") as f:
                messages = json.load(f)
            if not isinstance(messages, list):
                raise ValueError("Conversation JSON must be an array.")
            print(f"Archived {engine.archive_conversation(args.conversation_id, messages, project=args.project)} messages.")
        elif args.command == "summary":
            engine.save_summary(args.scope, args.key, args.text, source_ref=args.source_ref)
            print("Summary saved.")
        elif args.command == "context":
            print(engine.build_context(args.query, project=args.project, limit=args.limit))
        elif args.command == "stats":
            print(json.dumps({"database": str(engine.store.db_path), **engine.stats()}, indent=2))
        elif args.command == "delete":
            print("Deleted." if engine.delete_memory(args.id) else "Memory not found.")
    except (ValueError, PermissionError, KeyError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()

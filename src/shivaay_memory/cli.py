"""Command-line interface for the SHIVAAY memory engine."""

from __future__ import annotations

import argparse
import json
import sys

from .engine import MemoryEngine
from .extraction import CandidateQueue, extract_from_json
from .maintenance import MemoryMaintenance


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

    extract = sub.add_parser("extract", help="Propose memory candidates from user messages in a JSON file")
    extract.add_argument("--file", required=True, help="JSON array of {role, content} messages")
    extract.add_argument("--project", default="general")
    extract.add_argument("--source-ref", help="Conversation ID or source reference")

    candidates = sub.add_parser("candidates", help="Review queued memory candidates")
    candidates.add_argument("--status", choices=["pending", "approved", "rejected", "duplicate", "all"], default="pending")
    candidates.add_argument("--limit", type=int, default=50)

    approve = sub.add_parser("approve-candidate", help="Approve a candidate and save it as a memory")
    approve.add_argument("--id", required=True, type=int)

    reject = sub.add_parser("reject-candidate", help="Reject a pending candidate")
    reject.add_argument("--id", required=True, type=int)

    summary = sub.add_parser("summary", help="Save or replace a scope summary")
    summary.add_argument("--scope", choices=["user", "project", "conversation"], required=True)
    summary.add_argument("--key", required=True)
    summary.add_argument("--text", required=True)
    summary.add_argument("--source-ref")

    context = sub.add_parser("context", help="Build prompt context from relevant memory")
    context.add_argument("query")
    context.add_argument("--project")
    context.add_argument("--limit", type=int, default=8)

    scan = sub.add_parser("maintenance-scan", help="Scan for possible duplicate/conflicting memories without changing them")
    scan.add_argument("--project")
    scan.add_argument("--limit", type=int, default=500)

    maintenance = sub.add_parser("maintenance", help="List memory maintenance suggestions")
    maintenance.add_argument("--status", choices=["pending", "applied", "dismissed", "stale", "all"], default="pending")
    maintenance.add_argument("--limit", type=int, default=100)

    apply_maintenance = sub.add_parser("apply-maintenance", help="Apply a reviewed maintenance suggestion")
    apply_maintenance.add_argument("--id", required=True, type=int)
    apply_maintenance.add_argument("--text", help="Explicit replacement text, recommended for conflicts")
    apply_maintenance.add_argument("--reason", default="Reviewed memory maintenance")

    dismiss_maintenance = sub.add_parser("dismiss-maintenance", help="Dismiss a maintenance suggestion")
    dismiss_maintenance.add_argument("--id", required=True, type=int)

    policy = sub.add_parser("memory-policy", help="Inspect or configure conservative automatic memory saving")
    policy.add_argument("--auto-save", choices=["on", "off"])
    policy.add_argument("--min-confidence", type=float)
    policy.add_argument("--min-score", type=float)

    sub.add_parser("stats", help="Show local memory counts")
    delete = sub.add_parser("delete", help="Permanently delete a memory (cannot be undone)")
    delete.add_argument("--id", type=int, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    engine = MemoryEngine(args.db)
    queue = CandidateQueue(engine)
    maintenance = MemoryMaintenance(engine)
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
        elif args.command == "extract":
            ids = extract_from_json(engine, args.file, project=args.project, source_ref=args.source_ref)
            print(f"Queued {len(ids)} memory candidate(s) for review.")
            if ids:
                print("Candidate IDs: " + ", ".join(map(str, ids)))
        elif args.command == "candidates":
            print(json.dumps(queue.list(status=args.status, limit=args.limit), indent=2, ensure_ascii=False))
        elif args.command == "approve-candidate":
            print(f"Approved candidate; saved memory #{queue.approve(args.id)}")
        elif args.command == "reject-candidate":
            queue.reject(args.id)
            print("Candidate rejected.")
        elif args.command == "summary":
            engine.save_summary(args.scope, args.key, args.text, source_ref=args.source_ref)
            print("Summary saved.")
        elif args.command == "context":
            print(engine.build_context(args.query, project=args.project, limit=args.limit))
        elif args.command == "maintenance-scan":
            suggestions = maintenance.scan(project=args.project, limit=args.limit)
            print(json.dumps(suggestions, indent=2, ensure_ascii=False))
            print(f"Created {len(suggestions)} new suggestion(s). No memories were changed.", file=sys.stderr)
        elif args.command == "maintenance":
            print(json.dumps(maintenance.list(status=args.status, limit=args.limit), indent=2, ensure_ascii=False))
        elif args.command == "apply-maintenance":
            new_id = maintenance.apply(args.id, chosen_text=args.text, reason=args.reason)
            print(f"Applied suggestion; saved corrected memory as #{new_id}. Previous memory preserved as superseded.")
        elif args.command == "dismiss-maintenance":
            maintenance.dismiss(args.id)
            print("Maintenance suggestion dismissed.")
        elif args.command == "memory-policy":
            if args.auto_save is None and args.min_confidence is None and args.min_score is None:
                print(json.dumps(queue.get_policy(), indent=2))
            else:
                updated = queue.set_policy(
                    auto_save_enabled=None if args.auto_save is None else args.auto_save == "on",
                    min_confidence=args.min_confidence,
                    min_score=args.min_score,
                )
                print(json.dumps(updated, indent=2))
        elif args.command == "stats":
            stats = {"database": str(engine.store.db_path), **engine.stats()}
            stats["pending_candidates"] = len(queue.list(status="pending", limit=200))
            print(json.dumps(stats, indent=2))
        elif args.command == "delete":
            print("Deleted." if engine.delete_memory(args.id) else "Memory not found.")
    except (ValueError, PermissionError, KeyError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()

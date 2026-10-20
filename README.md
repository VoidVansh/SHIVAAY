# SHIVAAY — Adaptive Local Memory

A local-first persistent memory engine for SHIVAAY. It stores memories and conversation history in SQLite, searches with SQLite FTS5, tracks provenance and confidence, supports corrections and superseded facts, and keeps projects separated.

> **Privacy note:** memory storage is local by default. If SHIVAAY sends retrieved context to a cloud model API, that context leaves your computer. Local storage alone does not make cloud inference private.

## What is implemented

- SQLite database with schema migrations and full-text search (FTS5).
- Individual memories with category, project, source, confidence, importance, sensitivity, timestamps and lifecycle status.
- Explicit approval gate for sensitive memories.
- Search/retrieval ranking with project filters and recency/importance weighting.
- Corrections that preserve the old record as superseded rather than silently erasing history.
- Conversation archive and compact project/user summaries.
- CLI for adding, searching, listing, correcting, archiving and retrieving context.
- Tests using temporary local databases.

## Requirements

- Python 3.11+
- No third-party runtime dependencies (SQLite is included with Python).

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
shivaay-memory init
shivaay-memory add --text "SHIVAAY should be honest and never invent facts." --category preference --project SHIVAAY --source "user statement" --importance 5
shivaay-memory search "honest facts" --project SHIVAAY
shivaay-memory context "What are SHIVAAY's principles?" --project SHIVAAY
```

The database defaults to `~/.local/share/shivaay/memory.sqlite3`. Set `SHIVAAY_MEMORY_DB` to choose another path. Keep the database out of Git; it can contain personal information.

## Examples

```bash
# Archive a conversation and preserve its source ID
shivaay-memory archive --conversation-id chat-001 --text "We decided to use SQLite locally."

# Save a summary for a project
shivaay-memory summary --scope project --key SHIVAAY --text "Local-first memory engine; SQLite + FTS5; Python."

# Search memories
shivaay-memory search "database" --project SHIVAAY --limit 10

# Build context to insert into a model prompt
shivaay-memory context "What database did we choose?" --project SHIVAAY --limit 8

# Correct an outdated memory (old record is marked superseded)
shivaay-memory correct --id 1 --text "SHIVAAY uses PostgreSQL for the main application." --reason "Architecture decision changed"

# Review stored memories
shivaay-memory list --include-superseded
```

## Important design choices

- **Memory is not model training.** It retrieves relevant saved context and supplies it to the selected model at inference time.
- Explicit user statements and model inferences are different provenance types. Inferences should use lower confidence and must not be presented as confirmed facts.
- Sensitive details are not saved unless the caller explicitly approves them.
- Similar records are not automatically deleted. Update/correction operations preserve history.
- Search is lexical in this first milestone. The storage/retrieval interfaces are designed so local semantic search can be added later without making it mandatory on low-memory PCs.

## Development

```bash
python -m unittest discover -s tests -v
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the initial architecture and roadmap.


## Automatic memory candidate review

The second milestone adds a conservative candidate extractor. It scans only user messages from a supplied JSON conversation, proposes potentially durable memories, and queues them for review. It does **not** automatically turn every message into a fact.

Create `conversation.json`:
```json
[
  {"role": "user", "content": "Please remember that I prefer concise answers."},
  {"role": "assistant", "content": "Got it."}
]
```

Then:
```bash
shivaay-memory extract --file conversation.json --project SHIVAAY --source-ref chat-001
shivaay-memory candidates
shivaay-memory approve-candidate --id 1
shivaay-memory reject-candidate --id 2
```

Candidate extraction currently uses conservative rules, not an LLM. It is an intermediate safety-first step before model-backed extraction and live chat integration. See [automatic memory capture](docs/AUTOMATIC_MEMORY.md) and [roadmap](docs/ROADMAP.md).

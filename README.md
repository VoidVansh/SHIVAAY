# SHIVAAY — Adaptive Local Memory

A local-first persistent memory engine and chat runtime for SHIVAAY. It stores memories and conversation history in SQLite, searches with SQLite FTS5, tracks provenance and confidence, supports corrections and superseded facts, and can connect local Ollama models to retrieved context and optional semantic search.

> **Privacy note:** memory storage is local by default. The included chat and embedding backends reject non-loopback Ollama hosts and have no cloud fallback. A future cloud backend would send prompt/context off-device.

## Implemented

- SQLite memory store, FTS5 search, source/provenance and confidence metadata.
- Sensitivity gate, correction history, project/user summaries, and conversation archive.
- Candidate extraction and human review queue; proposals are not auto-approved.
- Provider-neutral memory-aware chat orchestration and interactive local chat CLI.
- Optional SQLite-backed semantic index using local Ollama embeddings; no vector database or Python numerical package required.
- Automated tests on Python 3.11, 3.12 and 3.13 (check the latest Actions run for current status).

## Install the memory engine

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
shivaay-memory init
shivaay-memory add --text "SHIVAAY should be honest and never invent facts." --category preference --project SHIVAAY --source user_statement --importance 5
shivaay-memory search "honest facts" --project SHIVAAY
shivaay-memory context "What are SHIVAAY's principles?" --project SHIVAAY
```

The database defaults to `~/.local/share/shivaay/memory.sqlite3`. Set `SHIVAAY_MEMORY_DB` or pass `--db` to choose another path. Keep the database out of Git; it can contain personal information.

## Run an actual local chat

1. Install and start [Ollama](https://ollama.com/) on your computer.
2. Pull a model suitable for your RAM, for example `ollama pull qwen2.5:3b` (model availability and resource use can vary).
3. Install SHIVAAY with `pip install -e .` from this repository.
4. Start chatting:

```bash
shivaay-chat --project SHIVAAY --model qwen2.5:3b --capture-candidates --context-chars 8000
```

Type `/quit` to exit. Each completed turn is archived in the local SQLite database. `--capture-candidates` queues possible memories for later review; it does not approve them automatically. Review them with `shivaay-memory candidates`, then approve/reject by ID. Omit the flag to disable automatic candidate proposals.

The chat backend defaults to `http://127.0.0.1:11434` and rejects non-loopback hosts. If Ollama is not running or the model is unavailable, SHIVAAY reports an error and does not fall back to a cloud service. Model weights consume disk space and inference performance depends on CPU/RAM; a small quantized model is a sensible starting point on a 4–8 GB RAM machine.

## Semantic memory search (optional)

Semantic search can find conceptually related memories even when your question uses different wording. It uses local Ollama embeddings and stores vectors in the same SQLite database.

```bash
ollama pull nomic-embed-text
# Create/update vectors for current active memories
shivaay-semantic index --project SHIVAAY
# Search by meaning rather than exact keywords
shivaay-semantic search "make the app work without internet" --project SHIVAAY
# Clean vectors for superseded/deleted memories or other models
shivaay-semantic clean
```

The initial indexing run embeds each active memory and may take time. Re-index after adding or correcting memories. Semantic search is optional; enable it in the interactive chat with `--semantic`. When enabled, chat fuses lexical and semantic rankings and avoids repeating the same memory in two context blocks. It indexes current active memories at startup, so re-run `shivaay-semantic index` after approving or correcting memories. See [docs/SEMANTIC_MEMORY.md](docs/SEMANTIC_MEMORY.md).

## Memory tools

```bash
shivaay-memory search "database" --project SHIVAAY --limit 10
shivaay-memory context "What database did we choose?" --project SHIVAAY --limit 8
shivaay-memory list --include-superseded
shivaay-memory correct --id 1 --text "The corrected fact goes here." --reason "User correction"
shivaay-memory candidates
shivaay-memory approve-candidate --id 1
shivaay-memory reject-candidate --id 2
shivaay-memory memory-policy
shivaay-memory maintenance-scan --project SHIVAAY
shivaay-memory maintenance --status pending
shivaay-memory check-db
shivaay-memory backup --file ~/shivaay-backups/memory.sqlite3
```

To archive an existing conversation from a JSON file, use an array of `{role, content}` objects and run `shivaay-memory archive --conversation-id chat-001 --file conversation.json --project SHIVAAY`. To propose candidates from that file, use `shivaay-memory extract --file conversation.json --project SHIVAAY --source-ref chat-001`.

## Design boundaries

- **Memory is not model training.** It retrieves saved context and supplies it to the model at inference time.
- Extraction is conservative. User-stated details and model inferences must remain distinguishable; inferences should not be presented as confirmed facts.
- Sensitive details are gated, but avoid putting credentials or secrets into conversation archives in the first place.
- Semantic similarity and candidate scores are heuristic signals, not proof that a memory is true. Maintenance only proposes possible duplicates/conflicts; it never changes memories during scans. Candidate auto-save is off by default and must be explicitly enabled with thresholds.
- This is a working foundation, not yet a finished JARVIS-style desktop HUD. Hybrid semantic retrieval is available in chat when the `--semantic` option is enabled; the default remains lightweight lexical-only retrieval.

## Tests

```bash
python -m unittest discover -s tests -v
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/AUTOMATIC_MEMORY.md](docs/AUTOMATIC_MEMORY.md), [docs/MODEL_EXTRACTION.md](docs/MODEL_EXTRACTION.md), [docs/LOCAL_CHAT.md](docs/LOCAL_CHAT.md), [docs/SEMANTIC_MEMORY.md](docs/SEMANTIC_MEMORY.md), [docs/MEMORY_MAINTENANCE.md](docs/MEMORY_MAINTENANCE.md), [docs/ADAPTIVE_SCORING.md](docs/ADAPTIVE_SCORING.md), [docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md), and [docs/CONTEXT_BUDGET.md](docs/CONTEXT_BUDGET.md).

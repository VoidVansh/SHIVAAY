# Linux installation and first run

This guide installs the current feature branch on a Linux PC. SHIVAAY's memory package requires Python 3.11+ and has no third-party runtime dependencies. Chat inference is handled by local Ollama; the adapter rejects non-loopback hosts and does not fall back to a cloud provider.

## 1. Install system tools

On Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
python3 --version
```

Confirm Python is version 3.11 or newer. On another distribution, install equivalent packages using its package manager.

## 2. Clone and install SHIVAAY

```bash
git clone --branch feature/automatic-memory-capture https://github.com/VoidVansh/SHIVAAY.git
cd SHIVAAY
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Run the tests before using your personal database:

```bash
python -m unittest discover -s tests -v
```

## 3. Set up local chat (optional)

Install Ollama by following its official Linux instructions at https://ollama.com/download/linux, then pull a model:

```bash
ollama pull qwen2.5:3b
```

The 3B model is a starting point for modest systems, not a guarantee of speed or quality on every CPU. If your PC is low on RAM, close other applications and expect slower responses.

## 4. Initialize and chat

```bash
shivaay-memory init
shivaay-memory check-db
shivaay-chat --project SHIVAAY --model qwen2.5:3b --capture-candidates
```

The database is stored locally by default at `~/.local/share/shivaay/memory.sqlite3`. Chat turns and rolling summaries are archived locally. The CLI prints a conversation ID; to continue that same conversation later, pass it back:

```bash
shivaay-chat --project SHIVAAY --conversation-id YOUR_CONVERSATION_ID
```

Candidate capture queues possible memories for review; it does not automatically save them as durable memories. Review candidates with `shivaay-memory candidates`, then approve or reject them explicitly.

## 5. Optional semantic retrieval

```bash
ollama pull nomic-embed-text
shivaay-chat --project SHIVAAY --model qwen2.5:3b --semantic --capture-candidates
```

The first semantic indexing pass can take time. It reuses existing vectors for the same embedding model and indexes new memories incrementally. Use `shivaay-semantic index --project SHIVAAY --rebuild` to rebuild vectors. Without `--semantic`, chat uses lexical retrieval only.

## 6. Protect and back up your data

- Memory databases, archived chats, summaries and JSON exports can contain private data. Do not store credentials or secrets in chat.
- Create a verified SQLite backup with `shivaay-memory backup --file ~/shivaay-backups/memory.sqlite3`.
- Portable JSON export is available with `shivaay-memory export-json --file ~/shivaay-backups/shivaay-memory.json`; that file is **not encrypted**.
- For another database location, set `SHIVAAY_MEMORY_DB=/path/to/memory.sqlite3` or pass the global `--db` option before the subcommand.
- To keep processing local, use the default loopback Ollama endpoint. Do not change the backend to a remote service unless you intentionally accept sending prompt context to that provider.

## Current limitation

This branch provides the memory engine and terminal chat, not the finished SHIVAAY desktop HUD. No real local-model benchmark is claimed by this guide; model speed depends on your hardware and chosen model.

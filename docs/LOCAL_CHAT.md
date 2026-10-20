# Local chat runtime

SHIVAAY has a chat orchestration layer in `shivaay_memory.chat`. It connects retrieval, a model response, conversation archiving, and optional memory-candidate extraction. Candidate memories are not silently approved.

## Privacy-first model backend

`OllamaBackend` calls `http://127.0.0.1:11434` by default and refuses non-loopback hosts. It has no cloud fallback. If Ollama is not running or the model is missing, it reports an error instead of sending the prompt elsewhere.

Install Ollama separately, start it, and download a model appropriate for your hardware. A small quantized model is a sensible starting point on a 4–8 GB RAM machine; model size and context length affect memory use. For example, pull `qwen2.5:3b` for chat.

## Run the CLI

```bash
shivaay-chat --project SHIVAAY --model qwen2.5:3b --capture-candidates --context-chars 8000
```

For semantic retrieval as well as full-text retrieval, first pull the embedding model and enable the flag:

```bash
ollama pull nomic-embed-text
shivaay-chat --project SHIVAAY --model qwen2.5:3b --capture-candidates --semantic
```

When `--semantic` is enabled, SHIVAAY indexes the project's current active memories at startup. First indexing can take a while. Re-run `shivaay-semantic index --project SHIVAAY` after new memories are approved or existing memories are corrected, so the vector index stays current. When semantic indexing is enabled, chat fuses lexical and semantic rankings and deduplicates memories by ID. The default context budget is 8,000 characters; adjust it with `--context-chars` (500–50,000). This is a character cap rather than an exact model-token count.

Type `/quit` to exit. Each completed turn is archived locally. `--capture-candidates` queues possible memories for later review; it does not approve them automatically. Review them with `shivaay-memory candidates`, then approve/reject by ID. Omit the flag to disable automatic candidate proposals.

## Python API

```python
from shivaay_memory.chat import MemoryChat, OllamaBackend
from shivaay_memory.engine import MemoryEngine
from shivaay_memory.extraction import RuleBasedExtractor
from shivaay_memory.semantic import OllamaEmbeddingBackend, SemanticMemoryIndex

engine = MemoryEngine()
semantic_index = SemanticMemoryIndex(engine, OllamaEmbeddingBackend())
semantic_index.index_all(project="shivaay")
chat = MemoryChat(engine, OllamaBackend(), project="shivaay",
                  extractor=RuleBasedExtractor(), semantic_index=semantic_index)
answer, turn = chat.send("What do you remember about my project?")
print(answer)
```

## Important boundaries

- SQLite memory, embeddings and archived turns are local by default; this module does not upload them.
- Chat and embedding adapters only accept loopback Ollama URLs. There is no remote fallback.
- Ollama must be installed and running locally. Model files take disk space and inference speed depends on CPU/RAM; integrated graphics are not required.
- Semantic retrieval is optional and requires a separate embedding model. The CLI's `--semantic` option indexes current active memories at startup; the next index pass adds missing vectors and cleans stale ones; use `shivaay-semantic index --rebuild` to recompute all vectors for the selected model.
- The CLI is functional but is not the polished JARVIS-style desktop HUD yet.
- Candidate extraction proposes possible memories, but does not save them as durable memories until a person approves them. Avoid putting credentials or other secrets into chat logs.

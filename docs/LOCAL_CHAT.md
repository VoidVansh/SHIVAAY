# Local chat runtime

SHIVAAY now has an optional chat orchestration layer in `shivaay_memory.chat`.
It connects retrieval, a model response, conversation archiving, and optional
memory-candidate extraction. It does not silently approve candidate memories.

## Privacy-first model backend

`OllamaBackend` calls `http://127.0.0.1:11434` by default and refuses non-loopback
hosts. It has no cloud fallback. If Ollama is not running or the model is missing,
it reports an error instead of sending the prompt elsewhere.

Install Ollama separately, start it, and download a model appropriate for your
hardware. A small quantized model is the sensible starting point on a 4–8 GB RAM
machine; model size and context length affect memory use. For example, if Ollama
is installed, pull `qwen2.5:3b` and then use the Python API below.

```python
from shivaay_memory.chat import MemoryChat, OllamaBackend
from shivaay_memory.engine import MemoryEngine
from shivaay_memory.extraction import RuleBasedExtractor

engine = MemoryEngine()  # SQLite file stays on this computer
chat = MemoryChat(
    engine,
    OllamaBackend(model="qwen2.5:3b"),
    project="shivaay",
    extractor=RuleBasedExtractor(),  # optional; proposals require review
)
while True:
    try:
        user_text = input("You: ")
    except (EOFError, KeyboardInterrupt):
        print("\\nSHIVAAY: Session ended.")
        break
    if user_text.strip().casefold() in {"/exit", "/quit"}:
        break
    try:
        answer, turn = chat.send(user_text)
        print(f"SHIVAAY: {answer}")
        if turn.candidate_ids:
            print(f"[Memory review: {len(turn.candidate_ids)} candidate(s) queued]")
    except (ValueError, RuntimeError) as exc:
        print(f"SHIVAAY error: {exc}")
```

## Important boundaries

- SQLite memory and archived turns are local by default; this module does not upload them.
- Ollama must be installed and running locally. Model files take disk space and inference
  speed depends on CPU/RAM; integrated graphics are not required.
- Memory retrieval is lexical at present. Semantic/vector retrieval is a future enhancement.
- The Python API is the current interface; this commit does not yet add a polished desktop HUD.
- Candidate extraction proposes possible memories, but does not save them as durable memories
  until a person approves them. Avoid putting credentials or other secrets into chat logs.

# Context budget and packing

The memory engine packs retrieved context in priority order: project summary, user summary, ranked saved memories, then matching conversation excerpts. Each memory includes its ID, source type, confidence, and project so the model can distinguish records and the user can trace where claims came from.

The default cap is 8,000 characters. Adjust it in the chat CLI:

```bash
shivaay-chat --project SHIVAAY --context-chars 6000
```

The accepted range is 500–50,000 characters. This is deliberately a standard-library-only bound and **not an exact token count**; tokenization differs by model. The packer preserves entry labels, truncates an oversized entry only when needed to fit the remaining budget, and prioritizes summaries and saved memories over conversation excerpts. When semantic retrieval is enabled, lexical and semantic rankings are fused before packing, so a memory found by both methods is included only once.

For tight-RAM machines, a smaller context budget can reduce prompt-processing work, but an excessively small budget may omit useful history.

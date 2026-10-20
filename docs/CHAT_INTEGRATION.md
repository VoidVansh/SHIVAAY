# Chat-loop integration

`shivaay_memory.session.MemorySession` connects the storage layer to an app's
chat loop without binding SHIVAAY to a particular inference provider.

Typical flow:

1. Call `session.context_for(user_message, project=...)` before inference.
2. Add that returned, source-labelled context to the model's prompt.
3. Generate the assistant response using your selected local or opted-in cloud model.
4. Call `session.finish_turn(conversation_id, user_message, assistant_response, project=...)`.
5. Review candidates with `CandidateQueue.list(status="pending")` and approve or reject.

Example:

    from shivaay_memory.engine import MemoryEngine
    from shivaay_memory.extraction import CandidateQueue, RuleBasedExtractor
    from shivaay_memory.session import MemorySession

    engine = MemoryEngine()  # local SQLite by default
    session = MemorySession(engine, extractor=RuleBasedExtractor())
    context = session.context_for("Continue SHIVAAY", project="SHIVAAY")
    # Add context to your model prompt, then generate a reply.
    result = session.finish_turn(
        "conversation-unique-id",
        "I'm building SHIVAAY as a local-first assistant.",
        "Let's work on its memory engine next.",
        project="SHIVAAY",
    )
    print(result.candidate_ids)  # suggestions only; not durable memories yet

## Important integration notes

- Generate a unique conversation ID for each conversation and retain it across turns.
- This helper archives every supplied user and assistant message; call it once per completed turn.
- Retrieval is currently lexical/FTS5 based, not embedding-based semantic search.
- The caller decides which messages are passed to the model. This library does not run inference.
- Candidate generation and durable memory storage are separate steps; approval remains explicit.
- Use a local inference backend for strict local processing. Cloud model calls send prompt data to that provider.


## Rolling conversation summaries

The interactive `MemoryChat` runtime periodically compacts conversation turns into a `conversation` summary. The default CLI refresh interval is 10 user turns; pass `--summary-every 0` to disable it. The CLI prints a conversation ID; pass `--conversation-id <ID>` on a later launch to restore recent user/assistant history and continue the same summary thread. A summary is included in later prompts as a labelled continuity aid, while the full messages remain in the local archive. Summary generation uses the configured chat backend and therefore adds one extra inference call per interval.

If summary generation fails, the successful user/assistant turn remains archived and the summary window is retained for a later retry. Summaries are fallible model-generated notes, not verified facts; latest explicit user corrections should take precedence.

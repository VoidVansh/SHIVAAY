# SHIVAAY Memory Architecture (Milestone 1)

## Data flow

1. **Capture** — the host app passes messages and candidate memories to the library.
2. **Evaluate** — callers label source type, confidence, importance, project and sensitivity. Candidate extraction can use conservative rules or a provider-neutral structured-model adapter. Extracted candidates remain review-first unless the owner explicitly enables conservative auto-save thresholds.
3. **Persist** — SQLite stores individual memories, conversation messages and replaceable summaries. FTS5 indexes text.
4. **Retrieve** — lexical search narrows candidates; ranking blends lexical match, importance, confidence and recency.
5. **Inject** — `build_context()` returns a source-labelled text block for the model prompt.
6. **Correct** — corrections create a new record and mark the old record superseded, preserving provenance.
7. **Review** — list/search/delete APIs and CLI allow the owner to inspect and control saved data. Hard deletion cleans dependent suggestions and semantic vectors; conversation archives have a separate delete command, with linked-memory deletion requiring an explicit flag.

## Memory types

- **Individual memory:** one durable claim, preference, decision or project detail.
- **Conversation archive:** source material for later search; it is not automatically treated as fact.
- **Summary:** compact, replaceable overview for the user, a project or a conversation.
- **Provenance:** user statement, assistant inference, conversation summary, external source or user correction.

## Safety and reliability

- Sensitive memory requires explicit approval.
- Basic sensitive-text heuristics block some likely secrets; heuristics are not a perfect detector.
- Inferences should have lower confidence and remain labelled as inferences.
- Superseded memories are excluded from default retrieval but retained for audit/history.
- Deleting a memory is a permanent database action. Conversation archive entries are currently separate and are not deleted by deleting a memory.
- Do not store the database in the Git repository. The repository contains source code only.

## Current limitations / next milestones

This is a foundation, not yet a complete ChatGPT-equivalent memory system.

1. Add a model-provider interface and automatic memory extraction with explicit structured output.
2. Add importance/usefulness scoring, duplicate detection, merge proposals and conflict detection.
3. Add semantic retrieval using an optional local embedding model, keeping FTS5 as a fallback.
4. Add bounded conversation-window summaries and source links to archived messages.
5. Add a review queue for uncertain or sensitive candidates and user correction UX. Core memory, conversation archives and summaries now support portable JSON export/import; embeddings and review queues are intentionally rebuilt or omitted.
6. Add integration tests against SHIVAAY's eventual chat loop and a small local model.
7. Add optional database encryption at rest; verified SQLite backup/restore is available, but backup files are not encrypted.

The engine does not train or fine-tune the model. It provides persistent context at inference time. If a remote API is used, prompt context sent to it is processed by that provider.

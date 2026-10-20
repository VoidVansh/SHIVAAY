# SHIVAAY Memory Architecture

## Runtime data flow

1. **Capture** — the chat host archives user and assistant turns. Candidate extraction is opt-in and examines user messages, not assistant claims.
2. **Evaluate** — candidates carry category, project, source, confidence, importance and a reason. Transparent heuristics estimate durability, usefulness and sensitivity risk.
3. **Review or save** — proposals enter a SQLite queue. By default they require approval. Auto-save can be enabled explicitly with thresholds, but sensitive candidates and likely negation-based conflicts with active memories remain pending. Queue output explains the decision.
4. **Persist** — SQLite stores individual memories, conversation messages, replaceable summaries, candidate decisions and maintenance suggestions. FTS5 indexes searchable text.
5. **Retrieve** — lexical search ranks by relevance, importance, confidence, recency and bounded recall-frequency feedback. Optional local Ollama embeddings provide semantic retrieval; chat fuses lexical and semantic rankings when enabled.
6. **Pack context** — the engine builds source-labelled context under a configurable character budget. The budget is a dependency-free approximation, not an exact model-token count.
7. **Generate** — the included chat adapter calls Ollama over a loopback HTTP endpoint only. It has no cloud fallback and rejects non-loopback hosts.
8. **Summarize and resume** — periodic summaries compact recent turns; on restart, the chat can rebuild the unsummarized window from the local archive.
9. **Correct and maintain** — corrections supersede older memory records rather than silently rewriting history. Duplicate/conflict scans create review suggestions and never change memories on their own.
10. **Inspect and recover** — CLI commands expose memory provenance, database health, candidate policy, backups, restore, and portable JSON export/import.

## Stored record types

- **Individual memory:** a durable claim, preference, decision, goal or project detail.
- **Conversation archive:** the source conversation, retained separately from curated memory.
- **Summary:** a compact, replaceable overview for the user, a project or a conversation.
- **Candidate:** a proposed memory that can be pending, approved, rejected or marked duplicate.
- **Maintenance suggestion:** a proposed duplicate/conflict review action; it must be applied or dismissed explicitly.
- **Provenance:** the source type/reference and confidence attached to saved claims, so user statements and assistant inferences can remain distinguishable.

## Privacy and safety boundaries

- Memory storage defaults to a local SQLite database at `~/.local/share/shivaay/memory.sqlite3`; override it with `SHIVAAY_MEMORY_DB` or the CLI's `--db`.
- The included Ollama chat and embedding adapters use loopback endpoints only. A future remote backend would change the data boundary and must be disclosed.
- Candidate auto-save is disabled by default. The sensitivity and conflict checks are heuristics, not perfect detection or proof that a claim is true.
- Conversation archives can contain personal information. Avoid putting passwords, API keys or other secrets into chats that are archived.
- Backups are verified SQLite copies, not encrypted files. Optional encryption at rest remains open.
- Memory retrieval is not model training or fine-tuning. It supplies stored context at inference time.

## Remaining milestones

- Integrate this memory runtime with SHIVAAY's actual desktop HUD.
- Add optional encryption at rest.
- Run end-to-end quality and performance tests with a real local model on the target PC.
- Improve contradiction detection and sensitivity classification beyond heuristics.

The repository has automated tests on Python 3.11, 3.12 and 3.13, including HTTP-level tests against a temporary loopback server. Those tests validate the adapter and orchestration contract without proving model quality or performance on the user's machine.

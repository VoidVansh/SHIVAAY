# SHIVAAY roadmap

## Milestone 1 — Local persistence
- [x] SQLite memory store and FTS5 search
- [x] Conversation archive and summaries
- [x] Provenance, confidence, importance, project scoping
- [x] Correction history and basic sensitive-memory gate
- [x] Hard-delete memory cleanup for derived indexes and dependent suggestions
- [x] Conversation archive/summary deletion with opt-in linked-memory cleanup

## Milestone 2 — Candidate extraction and review
- [x] Conservative rule-based candidate extractor from user messages
- [x] Provider-neutral structured model extractor and optional local-chat integration
- [x] Candidate queue, duplicate proposal suppression, approve/reject controls
- [x] CLI commands and CI workflow

## Milestone 3 — Model-backed adaptive memory
- [x] Provider-neutral chat backend interface
- [x] Local Ollama chat adapter and interactive terminal chat
- [x] Local Ollama embedding adapter
- [x] Candidate scoring for durability, future usefulness, confidence and sensitivity
- [x] Review-first duplicate and possible-conflict suggestions
- [x] User-configurable opt-in auto-save policy for high-confidence, low-risk candidates

## Milestone 4 — Retrieval quality
- [x] Optional local embeddings and semantic retrieval
- [x] Hybrid lexical + semantic ranking inside chat when semantic indexing is enabled
- [x] Periodic conversation-window summaries, related prior-summary retrieval and conversation resume
- [x] Character-bounded context packing (dependency-free approximation)
- [x] Recall-frequency feedback in retrieval ranking
- [x] Efficient incremental re-indexing after memory corrections

## Milestone 5 — Application integration and reliability
- [x] Provider-neutral session integration and local chat CLI
- [ ] Integrate memory runtime with SHIVAAY's actual desktop HUD
- [x] SQLite backup/restore and database integrity checks
- [x] Export/import in portable JSON format
- [ ] Optional encryption at rest
- [ ] End-to-end tests against a real local model
- [x] Linux installation and first-run guide

The checklist tracks implementation state, not a promise that untested behavior is production-ready. Semantic retrieval remains opt-in; when enabled, chat fuses lexical and semantic rankings and deduplicates memories by ID. Retrieved context has a configurable character budget, not a precise token budget. Backups use SQLite online backup and require explicit overwrite to replace existing files. Maintenance suggestions and candidate scores are heuristic. Auto-save is disabled by default; when explicitly enabled, it requires configured thresholds and excludes candidates flagged as sensitive. Scans never modify memories.

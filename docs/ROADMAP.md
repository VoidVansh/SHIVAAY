# SHIVAAY roadmap

## Milestone 1 — Local persistence
- [x] SQLite memory store and FTS5 search
- [x] Conversation archive and summaries
- [x] Provenance, confidence, importance, project scoping
- [x] Correction history and basic sensitive-memory gate

## Milestone 2 — Candidate extraction and review
- [x] Conservative rule-based candidate extraction from user messages
- [x] Candidate queue, duplicate proposal suppression, approve/reject controls
- [x] CLI commands for extraction and review
- [x] CI workflow for Python 3.11/3.12 tests
- [ ] Verify CI results and repair any test/runtime issues

## Milestone 3 — Model-backed adaptive memory
- [ ] Provider-neutral structured extractor interface with JSON schema
- [ ] Local-model adapter first; optional cloud adapter explicitly configured
- [ ] Candidate scoring for durability, future usefulness, confidence and sensitivity
- [ ] Contradiction detection and proposed updates rather than silent overwrites
- [ ] User-configurable auto-save policy for low-risk, high-confidence memories

## Milestone 4 — Retrieval quality
- [ ] Optional local embeddings and semantic retrieval
- [ ] Hybrid lexical + semantic ranking with project/time/source filters
- [ ] Conversation window summaries and source-level traceability
- [ ] Token-budgeted context packing

## Milestone 5 — Application integration and reliability
- [ ] Integrate with SHIVAAY's actual chat loop and UI
- [ ] Backup/restore, export/import and database integrity checks
- [ ] Optional encryption at rest
- [ ] End-to-end tests and Linux installation guide

The checklist tracks implementation state, not a promise that untested behavior is production-ready.

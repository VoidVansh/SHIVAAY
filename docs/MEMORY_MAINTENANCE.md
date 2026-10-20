# Memory maintenance

SHIVAAY can scan saved memories for likely duplicates and possible contradictions. This is deliberately conservative and review-first: **a scan never edits or deletes a memory**.

```bash
# Scan active memories (optionally scoped to a project)
shivaay-memory maintenance-scan --project SHIVAAY

# Inspect pending suggestions
shivaay-memory maintenance --status pending

# Dismiss a suggestion you disagree with
shivaay-memory dismiss-maintenance --id 1

# Apply a suggestion only after reviewing its two text fields
shivaay-memory maintenance --status pending
shivaay-memory apply-maintenance --id 1
```

Applying a suggestion uses the existing correction flow, preserving the old record as superseded and creating a new active record. For duplicate suggestions, the compared memory text becomes the replacement by default. For a possible conflict, inspect both texts first and pass an explicit replacement with `--text` when needed.

The detector uses simple lexical similarity and negation heuristics, not deep semantic reasoning. It can miss contradictions and can flag unrelated text. Treat every result as a hint, not a verdict. The suggestions table is stored in the same local SQLite database.

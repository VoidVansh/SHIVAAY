# Portable JSON export and import

The portable format moves core memory data between SHIVAAY databases without copying SQLite internals.

Export the active database:

```bash
shivaay-memory export-json --file ~/shivaay-backups/shivaay-memory.json
```

Import into an already initialized target database:

```bash
shivaay-memory --db ~/.local/share/shivaay/memory.sqlite3 import-json --file ~/shivaay-backups/shivaay-memory.json
```

If the export contains records explicitly marked sensitive, import stops unless you explicitly approve them:

```bash
shivaay-memory --db ~/.local/share/shivaay/memory.sqlite3 import-json --file ~/shivaay-backups/shivaay-memory.json --allow-sensitive
```

Import is **additive**, not a replacement: memory records and archived messages are appended, while matching summary keys are updated. Do not import the same file repeatedly unless you intentionally want duplicate memory/archive records. Existing memory IDs are remapped; supersession links are remapped too. Validate the target with `shivaay-memory check-db` afterward.

Included: memories (including superseded history), conversation archive entries, and user/project/conversation summaries. Not included: model-specific embedding vectors (rebuild with `shivaay-semantic index`), candidate review queues, maintenance suggestions, or auto-save policy settings.

The JSON export contains private conversation and memory content. Store it securely; this feature does not encrypt the export.

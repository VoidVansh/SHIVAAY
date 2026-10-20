# Backup, restore, and database integrity

SHIVAAY uses SQLite's online backup API, so committed data in the write-ahead log is included consistently. Backups include memories, conversation archives, summaries, and any candidate, embedding, or maintenance tables present in the database.

Check the active database:

```bash
shivaay-memory check-db
```

Create a backup (existing destinations are never overwritten unless requested):

```bash
shivaay-memory backup --file ~/shivaay-backups/memory.sqlite3
```

Restore a backup to the database selected by `--db` or `SHIVAAY_MEMORY_DB`:

```bash
shivaay-memory --db ~/.local/share/shivaay/memory.sqlite3 restore --file ~/shivaay-backups/memory.sqlite3 --overwrite
```

**Restore replaces the target database.** Stop SHIVAAY and other clients first, and make a separate backup of the current target before using `--overwrite`. If the target exists, restore refuses to proceed unless overwrite is explicitly specified. The source is integrity-checked before copying and the destination is checked afterward.

Keep backups in a private directory: they contain the same private information as your memory database. This feature does not encrypt backups.

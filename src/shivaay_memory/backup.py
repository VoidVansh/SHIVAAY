"""Safe SQLite backup, restore, and integrity checks for SHIVAAY memory."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


def check_database(path: str | Path) -> dict[str, Any]:
    db = Path(path).expanduser().resolve()
    if not db.is_file():
        raise FileNotFoundError(f"Database does not exist: {db}")
    with closing(sqlite3.connect(db)) as conn:
        integrity_rows = conn.execute("PRAGMA integrity_check").fetchall()
        integrity = [row[0] for row in integrity_rows]
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        counts = {}
        for table in ("memories", "conversations", "summaries", "memory_candidates",
                      "memory_embeddings", "maintenance_suggestions"):
            if table in tables:
                # Table names are fixed internal constants, not user input.
                counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    return {"path": str(db), "ok": integrity == ["ok"], "integrity": integrity, "counts": counts}


def _copy_database(source: Path, destination: Path, *, overwrite: bool) -> dict[str, Any]:
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Source database does not exist: {source}")
    if source == destination:
        raise ValueError("Source and destination database paths must differ.")
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Destination already exists: {destination}; pass overwrite=True to replace it.")
    report = check_database(source)
    if not report["ok"]:
        raise ValueError(f"Source database failed integrity check: {report['integrity']}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(destination)) as dst:
            src.backup(dst)
            dst.commit()
            integrity = dst.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise sqlite3.DatabaseError(f"Destination integrity check failed: {integrity}")
    except sqlite3.DatabaseError as exc:
        raise RuntimeError(f"SQLite backup/restore failed: {exc}") from exc
    final_report = check_database(destination)
    if not final_report["ok"]:
        raise RuntimeError(f"Destination database failed integrity check: {final_report['integrity']}")
    return {"source": str(source), "destination": str(destination), "ok": True,
            "counts": final_report["counts"]}


def backup_database(source: str | Path, destination: str | Path, *, overwrite: bool = False) -> dict[str, Any]:
    """Create a consistent SQLite backup, including committed WAL data."""
    return _copy_database(Path(source), Path(destination), overwrite=overwrite)


def restore_database(source: str | Path, destination: str | Path, *, overwrite: bool = False) -> dict[str, Any]:
    """Restore a verified backup to a target path; existing targets need opt-in overwrite."""
    return _copy_database(Path(source), Path(destination), overwrite=overwrite)

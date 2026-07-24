"""Compact SQLite control-plane store; heavy artifacts never enter this DB."""
from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path
import sqlite3
from typing import Any

SCHEMA_VERSION = 2


class ControlDatabase:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def migrate(self) -> int:
        with closing(self.connect()) as conn, conn:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_meta (version INTEGER NOT NULL)")
            row = conn.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
            version = int(row[0]) if row else 0
            if version < 1:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS storage_checks (
                      id INTEGER PRIMARY KEY,
                      checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      state TEXT NOT NULL,
                      ready INTEGER NOT NULL,
                      free_bytes INTEGER,
                      payload_json TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS dataset_registry (
                      role TEXT PRIMARY KEY,
                      root TEXT,
                      available INTEGER NOT NULL,
                      file_count INTEGER NOT NULL,
                      total_bytes INTEGER NOT NULL,
                      fingerprint TEXT,
                      payload_json TEXT NOT NULL,
                      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS project_state (
                      key TEXT PRIMARY KEY,
                      value_json TEXT NOT NULL,
                      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
                conn.execute("DELETE FROM schema_meta")
                conn.execute("INSERT INTO schema_meta(version) VALUES (1)")
                version = 1
            if version < 2:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS projects (
                      id TEXT PRIMARY KEY,
                      name TEXT NOT NULL,
                      app6_root TEXT NOT NULL,
                      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS source_snapshots (
                      id INTEGER PRIMARY KEY,
                      project_id TEXT NOT NULL,
                      code_hash TEXT NOT NULL,
                      file_count INTEGER NOT NULL,
                      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY(project_id) REFERENCES projects(id)
                    );
                    CREATE TABLE IF NOT EXISTS modules (
                      id TEXT PRIMARY KEY,
                      source_path TEXT NOT NULL,
                      content_hash TEXT NOT NULL,
                      indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS functions (
                      id TEXT PRIMARY KEY,
                      module_id TEXT NOT NULL,
                      technical_name TEXT NOT NULL,
                      source_line INTEGER NOT NULL,
                      FOREIGN KEY(module_id) REFERENCES modules(id)
                    );
                    CREATE TABLE IF NOT EXISTS runs (
                      id TEXT PRIMARY KEY,
                      state TEXT NOT NULL,
                      heavy_path TEXT NOT NULL,
                      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS events (
                      id INTEGER PRIMARY KEY,
                      run_id TEXT NOT NULL,
                      event_type TEXT NOT NULL,
                      payload_json TEXT NOT NULL,
                      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      FOREIGN KEY(run_id) REFERENCES runs(id)
                    );
                    """
                )
                conn.execute("UPDATE schema_meta SET version=2")
                version = 2
            if version != SCHEMA_VERSION:
                raise RuntimeError(f"unsupported control DB schema version: {version}")
            return version

    def record_storage(self, payload: dict[str, Any]) -> None:
        with closing(self.connect()) as conn, conn:
            conn.execute(
                "INSERT INTO storage_checks(state, ready, free_bytes, payload_json) VALUES (?, ?, ?, ?)",
                (payload["state"], int(bool(payload["ready"])), payload.get("free_bytes"), json.dumps(payload, ensure_ascii=False)),
            )

    def upsert_dataset(self, role: str, payload: dict[str, Any]) -> None:
        with closing(self.connect()) as conn, conn:
            conn.execute(
                """INSERT INTO dataset_registry(role, root, available, file_count, total_bytes, fingerprint, payload_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(role) DO UPDATE SET root=excluded.root, available=excluded.available,
                     file_count=excluded.file_count, total_bytes=excluded.total_bytes,
                     fingerprint=excluded.fingerprint, payload_json=excluded.payload_json,
                     updated_at=CURRENT_TIMESTAMP""",
                (role, payload.get("root"), int(bool(payload["available"])), payload["file_count"], payload["total_bytes"], payload.get("fingerprint"), json.dumps(payload, ensure_ascii=False)),
            )

    def counts(self) -> dict[str, int]:
        with closing(self.connect()) as conn, conn:
            return {
                "storage_checks": int(conn.execute("SELECT COUNT(*) FROM storage_checks").fetchone()[0]),
                "datasets": int(conn.execute("SELECT COUNT(*) FROM dataset_registry").fetchone()[0]),
                "projects": int(conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]),
                "modules": int(conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0]),
                "functions": int(conn.execute("SELECT COUNT(*) FROM functions").fetchone()[0]),
                "runs": int(conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]),
                "events": int(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]),
            }

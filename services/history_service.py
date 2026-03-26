from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from config import get_settings
from models.schemas import HistoryRecord


class HistoryService:
    def __init__(self) -> None:
        self.db_path = Path(get_settings().sqlite_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS generation_history (
                    session_id TEXT PRIMARY KEY,
                    feature_name TEXT NOT NULL,
                    brand_score REAL NOT NULL,
                    token_count INTEGER NOT NULL,
                    generation_time_ms INTEGER NOT NULL,
                    platforms TEXT NOT NULL,
                    zip_path TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )

    def record(self, item: HistoryRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO generation_history
                (session_id, feature_name, brand_score, token_count, generation_time_ms, platforms, zip_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.session_id,
                    item.feature_name,
                    item.brand_score,
                    item.token_count,
                    item.generation_time_ms,
                    json.dumps(item.platforms),
                    item.zip_path,
                    item.created_at.isoformat(),
                ),
            )

    def list_records(self) -> list[HistoryRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT session_id, feature_name, brand_score, token_count, generation_time_ms, platforms, zip_path, created_at
                FROM generation_history
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [
            HistoryRecord(
                session_id=row[0],
                feature_name=row[1],
                brand_score=row[2],
                token_count=row[3],
                generation_time_ms=row[4],
                platforms=json.loads(row[5]),
                zip_path=row[6],
                created_at=row[7],
            )
            for row in rows
        ]

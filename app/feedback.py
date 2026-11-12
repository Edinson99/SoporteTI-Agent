"""Almacenamiento local y minimizado de valoraciones de guias."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_FEEDBACK_RETENTION_DAYS = 180
FeedbackRating = Literal["useful", "not_useful"]


class FeedbackStoreError(RuntimeError):
    """Error explicito al leer o escribir la base local de feedback."""


class LocalFeedbackStore:
    """Persiste solo el id de la guia, la valoracion y la fecha UTC."""

    def __init__(self, database_path: Path | None = None) -> None:
        configured_path = os.getenv("SOPORTE_FEEDBACK_DB")
        self.database_path = database_path or Path(
            configured_path or _PROJECT_ROOT / "data" / "feedback.sqlite3"
        )

    @staticmethod
    def _ensure_schema(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback_votes (
                article_id TEXT NOT NULL,
                rating TEXT NOT NULL
                    CHECK (rating IN ('useful', 'not_useful')),
                created_at TEXT NOT NULL
            )
            """
        )

    @staticmethod
    def _purge_expired(connection: sqlite3.Connection) -> None:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=_FEEDBACK_RETENTION_DAYS)
        ).isoformat(timespec="seconds")
        connection.execute(
            "DELETE FROM feedback_votes WHERE created_at < ?",
            (cutoff,),
        )

    def record(
        self,
        article_id: str,
        rating: FeedbackRating,
    ) -> None:
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.database_path, timeout=10) as connection:
                self._ensure_schema(connection)
                self._purge_expired(connection)
                connection.execute(
                    """
                    INSERT INTO feedback_votes (
                        article_id, rating, created_at
                    ) VALUES (?, ?, ?)
                    """,
                    (
                        article_id,
                        rating,
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    ),
                )
        except (OSError, sqlite3.Error) as error:
            raise FeedbackStoreError(
                "No fue posible guardar la valoracion local."
            ) from error

    def summary(self) -> list[dict[str, int | str]]:
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.database_path, timeout=10) as connection:
                connection.row_factory = sqlite3.Row
                self._ensure_schema(connection)
                self._purge_expired(connection)
                rows = connection.execute(
                    """
                    SELECT
                        article_id,
                        SUM(CASE WHEN rating = 'useful' THEN 1 ELSE 0 END) AS useful,
                        SUM(CASE WHEN rating = 'not_useful' THEN 1 ELSE 0 END) AS not_useful,
                        COUNT(*) AS total
                    FROM feedback_votes
                    GROUP BY article_id
                    ORDER BY article_id
                    """
                ).fetchall()
        except (OSError, sqlite3.Error) as error:
            raise FeedbackStoreError(
                "No fue posible consultar el resumen de valoraciones."
            ) from error
        return [dict(row) for row in rows]

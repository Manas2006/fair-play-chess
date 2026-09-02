from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3


VALID_DECISIONS = {"clear", "insufficient", "escalate"}


class ReviewStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS review_decisions (
                    account_id TEXT PRIMARY KEY,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL
                )
                """
            )

    def upsert(self, account_id: str, decision: str, reason: str, reviewer: str) -> dict[str, str]:
        if decision not in VALID_DECISIONS:
            raise ValueError(f"decision must be one of {sorted(VALID_DECISIONS)}")
        reviewed_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO review_decisions(account_id, decision, reason, reviewer, reviewed_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(account_id) DO UPDATE SET
                    decision=excluded.decision,
                    reason=excluded.reason,
                    reviewer=excluded.reviewer,
                    reviewed_at=excluded.reviewed_at
                """,
                (account_id, decision, reason, reviewer, reviewed_at),
            )
        return {
            "account_id": account_id,
            "decision": decision,
            "reason": reason,
            "reviewer": reviewer,
            "reviewed_at": reviewed_at,
        }

    def all(self) -> dict[str, dict[str, str]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM review_decisions").fetchall()
        return {str(row["account_id"]): dict(row) for row in rows}

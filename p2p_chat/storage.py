"""Storage module: SQLite-backed message persistence and log replay.

When a new peer joins the network, existing nodes send them a *history
response* containing recent chat messages serialised as JSON.  This
module handles both persisting individual messages and retrieving the
chat backlog for replay.
"""

import json
import sqlite3
import threading
from pathlib import Path


class MessageStore:
    """Thread-safe SQLite store for chat messages.

    Parameters
    ----------
    db_path:
        File system path to the SQLite database.  Defaults to
        ``chat_log.db`` in the current working directory.  Pass
        ``":memory:"`` for an in-memory store (useful in tests).
    """

    def __init__(self, db_path: str = "chat_log.db") -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        # Use a single persistent connection so that ":memory:" databases
        # (used in tests) are not silently discarded between calls.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id        TEXT PRIMARY KEY,
                    type      TEXT    NOT NULL,
                    sender    TEXT    NOT NULL,
                    timestamp REAL    NOT NULL,
                    content   TEXT    NOT NULL,
                    peers     TEXT    NOT NULL,
                    signature TEXT    NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_timestamp ON messages (timestamp)"
            )
            self._conn.commit()

    def save(self, message: dict) -> None:
        """Persist *message*.  Silently ignores duplicate IDs."""
        with self._lock:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO messages
                    (id, type, sender, timestamp, content, peers, signature)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message["id"],
                    message["type"],
                    message["sender"],
                    message["timestamp"],
                    message["content"],
                    json.dumps(message.get("peers", [])),
                    message.get("signature", ""),
                ),
            )
            self._conn.commit()

    def get_recent(self, limit: int = 50) -> list[dict]:
        """Return up to *limit* recent ``"chat"`` messages in chronological
        order (oldest first)."""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, type, sender, timestamp, content, peers, signature
                FROM messages
                WHERE type = 'chat'
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "type": row["type"],
                "sender": row["sender"],
                "timestamp": row["timestamp"],
                "content": row["content"],
                "peers": json.loads(row["peers"]),
                "signature": row["signature"],
            }
            for row in reversed(rows)
        ]

    def count(self) -> int:
        """Return the total number of messages stored (all types)."""
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

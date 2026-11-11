import os
import sqlite3
from contextlib import contextmanager

from modules.config import ROOT

DB_PATH = os.getenv("CHAT_MEMORY_DB") or str(ROOT / "chat_memory.db")
# 保留最近多少条消息（一轮问答 = user + assistant 两条）
HISTORY_LIMIT = int(os.getenv("CHAT_HISTORY_LIMIT", "12"))


@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_messages(session_id, id)"
        )


def load_history(session_id: str, limit: int = HISTORY_LIMIT) -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT role, content FROM chat_messages "
            "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [{"role": role, "content": content} for role, content in reversed(rows)]


def append_message(session_id: str, role: str, content: str) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )

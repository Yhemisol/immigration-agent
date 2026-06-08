"""SQLite persistence for crawl results and change detection."""
import sqlite3
import hashlib
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "immigration.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS items (
                id          TEXT PRIMARY KEY,
                source      TEXT NOT NULL,
                url         TEXT NOT NULL,
                title       TEXT NOT NULL,
                content     TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                first_seen  TEXT NOT NULL,
                last_seen   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reports (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date    TEXT NOT NULL,
                new_count   INTEGER NOT NULL,
                email_sent  INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            );
        """)


def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def upsert_item(source: str, url: str, title: str, content: str) -> tuple[bool, str]:
    """Insert or update item. Returns (is_new, item_id)."""
    item_id = hashlib.md5(url.encode()).hexdigest()
    content_hash = compute_hash(content)
    now = datetime.utcnow().isoformat()

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT content_hash FROM items WHERE id = ?", (item_id,)
        ).fetchone()

        if existing is None:
            conn.execute(
                """INSERT INTO items (id, source, url, title, content, content_hash, first_seen, last_seen)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (item_id, source, url, title, content, content_hash, now, now),
            )
            return True, item_id

        if existing["content_hash"] != content_hash:
            conn.execute(
                """UPDATE items SET title=?, content=?, content_hash=?, last_seen=?
                   WHERE id=?""",
                (title, content, content_hash, now, item_id),
            )
            return True, item_id

        conn.execute("UPDATE items SET last_seen=? WHERE id=?", (now, item_id))
        return False, item_id


def log_report(new_count: int, email_sent: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO reports (run_date, new_count, email_sent, created_at) VALUES (?, ?, ?, ?)",
            (datetime.utcnow().date().isoformat(), new_count, int(email_sent), datetime.utcnow().isoformat()),
        )

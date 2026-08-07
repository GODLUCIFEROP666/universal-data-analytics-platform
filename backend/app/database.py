"""
database.py — SQLite database layer for lightweight application data.

Tables:
  admin_users  — single admin account with bcrypt-hashed password
  app_counters — total_visitors, total_uploads, total_analyses, active_users

All operations use parameterized queries (no SQL injection).
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

def _get_db_path() -> str:
    return os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "..", "data.db"))

_lock = threading.Lock()
_connection: Optional[sqlite3.Connection] = None

COUNTER_KEYS = ("total_visitors", "total_uploads", "total_analyses")


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

def _get_connection() -> sqlite3.Connection:
    """Return a shared SQLite connection (thread-safe via explicit lock)."""
    global _connection
    if _connection is None:
        db_path = os.path.abspath(_get_db_path())
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        _connection = sqlite3.connect(db_path, check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA journal_mode=WAL")
        _connection.execute("PRAGMA foreign_keys=ON")
    return _connection


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create tables and seed default data on first run."""
    with _lock:
        conn = _get_connection()
        cursor = conn.cursor()

        # ── Create tables ────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                username     TEXT    UNIQUE NOT NULL COLLATE NOCASE,
                password_hash TEXT   NOT NULL,
                created_at   TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_counters (
                key   TEXT    PRIMARY KEY,
                value INTEGER NOT NULL DEFAULT 0
            )
        """)

        conn.commit()

        # ── Seed default admin (only if table is empty) ──────────────────
        row = cursor.execute("SELECT COUNT(*) AS cnt FROM admin_users").fetchone()
        if row["cnt"] == 0:
            try:
                import bcrypt
                initial_password = os.environ.get("ADMIN_INITIAL_PASSWORD", "").strip() or "ChangeMeOnFirstLogin#123"
                default_hash = bcrypt.hashpw(initial_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                cursor.execute(
                    "INSERT INTO admin_users (username, password_hash) VALUES (?, ?)",
                    ("jignesh", default_hash),
                )
                conn.commit()
                logger.info("Default admin account 'jignesh' created.")
            except Exception as exc:
                logger.error("Failed to seed default admin: %s", exc)

        # ── Seed counters (only missing keys) ────────────────────────────
        for key in COUNTER_KEYS:
            cursor.execute(
                "INSERT OR IGNORE INTO app_counters (key, value) VALUES (?, 0)",
                (key,),
            )
        conn.commit()
        logger.info("Database initialized at %s", os.path.abspath(_get_db_path()))


# ---------------------------------------------------------------------------
# Counter operations
# ---------------------------------------------------------------------------

def get_counter(key: str) -> int:
    """Return the current value of a counter."""
    with _lock:
        conn = _get_connection()
        row = conn.execute(
            "SELECT value FROM app_counters WHERE key = ?", (key,)
        ).fetchone()
        return int(row["value"]) if row else 0


def increment_counter(key: str) -> int:
    """Increment a counter by 1 and return the new value."""
    with _lock:
        conn = _get_connection()
        conn.execute(
            "UPDATE app_counters SET value = value + 1 WHERE key = ?", (key,)
        )
        conn.commit()
        row = conn.execute(
            "SELECT value FROM app_counters WHERE key = ?", (key,)
        ).fetchone()
        return int(row["value"]) if row else 0


def decrement_counter(key: str, floor: int = 0) -> int:
    """Decrement a counter by 1 (clamped to floor) and return the new value."""
    with _lock:
        conn = _get_connection()
        conn.execute(
            "UPDATE app_counters SET value = MAX(value - 1, ?) WHERE key = ?",
            (floor, key),
        )
        conn.commit()
        row = conn.execute(
            "SELECT value FROM app_counters WHERE key = ?", (key,)
        ).fetchone()
        return int(row["value"]) if row else 0


def get_all_counters() -> Dict[str, int]:
    """Return all counters as a dictionary."""
    with _lock:
        conn = _get_connection()
        rows = conn.execute("SELECT key, value FROM app_counters").fetchall()
        return {row["key"]: int(row["value"]) for row in rows}


# ---------------------------------------------------------------------------
# Admin operations
# ---------------------------------------------------------------------------

def get_admin_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Return admin record (id, username, password_hash) or None."""
    with _lock:
        conn = _get_connection()
        clean_user = username.strip()
        row = conn.execute(
            "SELECT id, username, password_hash FROM admin_users WHERE LOWER(username) = LOWER(?)",
            (clean_user,),
        ).fetchone()
        if row is None:
            return None
        return {"id": int(row["id"]), "username": row["username"], "password_hash": row["password_hash"]}


def update_admin_password(username: str, new_hash: str) -> bool:
    """Update the password hash for an admin user. Returns True on success."""
    with _lock:
        conn = _get_connection()
        cursor = conn.execute(
            "UPDATE admin_users SET password_hash = ? WHERE username = ?",
            (new_hash, username),
        )
        conn.commit()
        return cursor.rowcount > 0

"""
migrate_to_mongo.py — Migration script to transfer existing SQLite data to MongoDB Atlas.

Usage:
    python migrate_to_mongo.py

Reads MONGODB_URI from environment variables or backend/.env file.
Reads SQLite database from DATABASE_PATH or backend/data.db.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

from app.auth_utils import _load_env_file
from app.database import DB_NAME, get_mongo_client, _sanitize_mongo_uri


def migrate_sqlite_to_mongodb() -> bool:
    _load_env_file()

    mongo_uri = os.environ.get("MONGODB_URI", "").strip()
    if not mongo_uri:
        logger.error("MONGODB_URI environment variable is missing. Cannot migrate.")
        return False

    db_path = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "data.db"))
    db_path = os.path.abspath(db_path)

    if not os.path.exists(db_path):
        logger.info("SQLite database file '%s' not found. Nothing to migrate.", db_path)
        return True

    client = get_mongo_client()
    if client is None:
        logger.error("Failed to connect to MongoDB Atlas.")
        return False

    mongo_db = client[DB_NAME]
    logger.info("Connected to MongoDB Atlas database '%s'. Starting migration from SQLite...", DB_NAME)

    try:
        sqlite_conn = sqlite3.connect(db_path)
        sqlite_conn.row_factory = sqlite3.Row
        cursor = sqlite_conn.cursor()

        # Check existing tables in SQLite
        tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

        # ── 1. Migrate admin_users ──────────────────────────────────────────────
        if "admin_users" in tables:
            admins = cursor.execute("SELECT * FROM admin_users").fetchall()
            migrated_admins = 0
            for admin in admins:
                username = admin["username"].strip()
                username_lower = username.lower()
                password_hash = admin["password_hash"]
                created_at = admin["created_at"] if "created_at" in admin.keys() else None

                existing = mongo_db.admin_users.find_one({"username_lowercase": username_lower})
                if not existing:
                    mongo_db.admin_users.insert_one({
                        "username": username,
                        "username_lowercase": username_lower,
                        "password_hash": password_hash,
                        "created_at": created_at,
                    })
                    migrated_admins += 1
                else:
                    if password_hash and password_hash.strip() and not existing.get("password_hash"):
                        mongo_db.admin_users.update_one(
                            {"_id": existing["_id"]},
                            {"$set": {"password_hash": password_hash, "username_lowercase": username_lower}}
                        )
                        migrated_admins += 1
            logger.info("Migrated %d admin user(s) into 'admin_users' collection.", migrated_admins)

        # ── 2. Migrate app_counters to visitors collection ──────────────────────
        if "app_counters" in tables:
            counters = cursor.execute("SELECT * FROM app_counters").fetchall()
            migrated_counters = 0
            for c in counters:
                key = c["key"]
                value = int(c["value"])

                existing = mongo_db.visitors.find_one({"key": key})
                if not existing:
                    mongo_db.visitors.insert_one({"key": key, "value": value})
                    migrated_counters += 1
                else:
                    # Update value if SQLite had higher counter
                    if existing.get("value", 0) < value:
                        mongo_db.visitors.update_one({"key": key}, {"$set": {"value": value}})
                        migrated_counters += 1
            logger.info("Migrated %d counter record(s) into 'visitors' collection.", migrated_counters)

        sqlite_conn.close()
        logger.info("Migration from SQLite to MongoDB Atlas completed successfully!")
        return True

    except Exception as exc:
        logger.error("Migration failed: %s", _sanitize_mongo_uri(str(exc)))
        return False


if __name__ == "__main__":
    success = migrate_sqlite_to_mongodb()
    sys.exit(0 if success else 1)

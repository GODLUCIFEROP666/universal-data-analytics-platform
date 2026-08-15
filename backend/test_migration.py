"""Unit tests for SQLite to MongoDB Atlas migration script."""
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))

import mongomock
from app.database import set_db_client, DB_NAME, get_admin_by_username, get_all_counters
from migrate_to_mongo import migrate_sqlite_to_mongodb


class TestMigration(unittest.TestCase):

    def setUp(self):
        self.mock_client = mongomock.MongoClient()
        set_db_client(self.mock_client)

        # Create temporary SQLite database
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()

        # Create tables & data matching SQLite schema
        cursor.execute("""
            CREATE TABLE admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE app_counters (
                key TEXT PRIMARY KEY,
                value INTEGER NOT NULL DEFAULT 0
            )
        """)

        # Insert jignesh admin record with exact SQLite hash
        self.test_hash = "$2b$12$/zU9Ry5GqrahDlkhws0youZCydSTDuZ8IPVe.hnVCSur5xL6YR0fm"
        cursor.execute(
            "INSERT INTO admin_users (username, password_hash, created_at) VALUES (?, ?, ?)",
            ("jignesh", self.test_hash, "2026-08-05 15:51:56")
        )
        cursor.execute("INSERT INTO app_counters (key, value) VALUES ('total_visitors', 17)")
        cursor.execute("INSERT INTO app_counters (key, value) VALUES ('total_uploads', 13)")
        cursor.execute("INSERT INTO app_counters (key, value) VALUES ('total_analyses', 24)")

        conn.commit()
        conn.close()

        os.environ["DATABASE_PATH"] = self.temp_db_path
        os.environ["MONGODB_URI"] = "mongodb://localhost:27017/universal_data_analytics"

    def tearDown(self):
        set_db_client(None)
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)
        os.environ.pop("DATABASE_PATH", None)

    def test_sqlite_to_mongodb_migration(self):
        # Run migration
        success = migrate_sqlite_to_mongodb()
        self.assertTrue(success)

        # Verify admin_users collection
        mongo_db = self.mock_client[DB_NAME]
        admin_doc = mongo_db.admin_users.find_one({"username_lowercase": "jignesh"})
        self.assertIsNotNone(admin_doc)
        self.assertEqual(admin_doc["username"], "jignesh")
        self.assertEqual(admin_doc["username_lowercase"], "jignesh")
        self.assertEqual(admin_doc["password_hash"], self.test_hash)

        # Verify visitors collection
        counters = get_all_counters()
        self.assertEqual(counters["total_visitors"], 17)
        self.assertEqual(counters["total_uploads"], 13)
        self.assertEqual(counters["total_analyses"], 24)

    def test_migration_idempotency_no_duplication(self):
        # Run migration twice
        migrate_sqlite_to_mongodb()
        migrate_sqlite_to_mongodb()

        mongo_db = self.mock_client[DB_NAME]
        count = mongo_db.admin_users.count_documents({"username_lowercase": "jignesh"})
        self.assertEqual(count, 1)

        visitor_doc = mongo_db.visitors.find_one({"key": "total_visitors"})
        self.assertEqual(visitor_doc["value"], 17)

    def test_migration_does_not_overwrite_valid_password_with_empty(self):
        # Pre-seed mongodb with valid user
        mongo_db = self.mock_client[DB_NAME]
        mongo_db.admin_users.insert_one({
            "username": "jignesh",
            "username_lowercase": "jignesh",
            "password_hash": self.test_hash
        })

        # Run migration
        migrate_sqlite_to_mongodb()

        admin = get_admin_by_username("jignesh")
        self.assertEqual(admin["password_hash"], self.test_hash)


if __name__ == "__main__":
    unittest.main()

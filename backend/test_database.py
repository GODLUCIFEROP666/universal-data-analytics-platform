"""Unit tests for MongoDB database module."""
import os
import sys
import unittest

sys.path.insert(0, ".")

os.environ["JWT_SECRET"] = "super-secret-jwt-key-for-unit-testing-32bytes"

import mongomock
from fastapi import HTTPException
from app.auth_utils import hash_password, verify_password
from app.database import (
    _sanitize_mongo_uri,
    decrement_counter,
    get_admin_by_username,
    get_all_counters,
    get_analytics_history,
    get_counter,
    increment_counter,
    init_db,
    record_analytics_event,
    set_db_client,
    update_admin_password,
)


class TestDatabaseMongoDB(unittest.TestCase):

    def setUp(self):
        # Create fresh mongomock client for each test
        self.mock_client = mongomock.MongoClient()
        set_db_client(self.mock_client)
        init_db()
        # Clear collections to give tests a clean baseline state
        db = self.mock_client["universal_data_analytics"]
        db.admin_users.delete_many({})
        db.visitors.delete_many({})
        db.analytics_history.delete_many({})

    def tearDown(self):
        set_db_client(None)

    def test_sanitize_mongo_uri(self):
        uri = "mongodb+srv://admin_user:secret_pass123@cluster0.mongodb.net/test?retryWrites=true"
        sanitized = _sanitize_mongo_uri(uri)
        self.assertIn("admin_user", sanitized)
        self.assertNotIn("secret_pass123", sanitized)
        self.assertIn(":***@", sanitized)
        self.assertEqual(_sanitize_mongo_uri(""), "<empty>")



    def test_visitor_counters(self):
        self.assertEqual(get_counter("total_visitors"), 0)
        c1 = increment_counter("total_visitors")
        self.assertEqual(c1, 1)
        self.assertEqual(get_counter("total_visitors"), 1)

        c2 = increment_counter("total_visitors")
        self.assertEqual(c2, 2)

        dec = decrement_counter("total_visitors")
        self.assertEqual(dec, 1)

        all_counters = get_all_counters()
        self.assertIn("total_visitors", all_counters)
        self.assertIn("total_uploads", all_counters)
        self.assertIn("total_analyses", all_counters)
        self.assertEqual(all_counters["total_visitors"], 1)

    def test_admin_authentication_and_case_insensitivity(self):
        # Insert test admin
        db = self.mock_client["universal_data_analytics"]
        admin_pass = "TestAdminPass#123"
        hashed = hash_password(admin_pass)
        db.admin_users.insert_one({
            "username": "jignesh",
            "username_lowercase": "jignesh",
            "password_hash": hashed
        })

        # Test case insensitivity and whitespace handling
        admin1 = get_admin_by_username("jignesh")
        self.assertIsNotNone(admin1)
        self.assertTrue(verify_password(admin_pass, admin1["password_hash"]))

        admin2 = get_admin_by_username("  JIGNESH  ")
        self.assertIsNotNone(admin2)
        self.assertEqual(admin2["username"], "jignesh")

        admin3 = get_admin_by_username("non_existent_user")
        self.assertIsNone(admin3)

    def test_update_admin_password(self):
        db = self.mock_client["universal_data_analytics"]
        hashed = hash_password("OldPassword123")
        db.admin_users.insert_one({
            "username": "admin_user",
            "username_lowercase": "admin_user",
            "password_hash": hashed
        })

        new_hash = hash_password("NewPassword456")
        updated = update_admin_password("ADMIN_USER", new_hash)
        self.assertTrue(updated)

        admin = get_admin_by_username("admin_user")
        self.assertTrue(verify_password("NewPassword456", admin["password_hash"]))
        self.assertFalse(verify_password("OldPassword123", admin["password_hash"]))

    def test_analytics_history(self):
        event = record_analytics_event("upload", "sales_data.csv", {"format": "csv", "size_bytes": 1024})
        self.assertIsNotNone(event)
        self.assertIn("id", event)
        self.assertIsInstance(event["id"], str)

        history = get_analytics_history(limit=10)
        self.assertGreaterEqual(len(history), 1)
        self.assertEqual(history[0]["filename"], "sales_data.csv")
        self.assertEqual(history[0]["action"], "upload")
        self.assertIsInstance(history[0]["id"], str)

    def test_behavior_when_mongo_unavailable(self):
        set_db_client(None)
        old_uri = os.environ.get("MONGODB_URI")
        os.environ["MONGODB_URI"] = ""
        try:
            with unittest.mock.patch("app.database._load_env_file"):
                with self.assertRaises((HTTPException, RuntimeError)):
                    get_counter("total_visitors")
                with self.assertRaises((HTTPException, RuntimeError)):
                    increment_counter("total_visitors")
                with self.assertRaises((HTTPException, RuntimeError)):
                    decrement_counter("total_visitors")
                with self.assertRaises((HTTPException, RuntimeError)):
                    get_all_counters()
                with self.assertRaises((HTTPException, RuntimeError)):
                    get_admin_by_username("jignesh")
                with self.assertRaises((HTTPException, RuntimeError)):
                    update_admin_password("jignesh", "hash")
                self.assertIsNone(record_analytics_event("upload", "test.csv"))
                with self.assertRaises((HTTPException, RuntimeError)):
                    get_analytics_history()
        finally:
            if old_uri is not None:
                os.environ["MONGODB_URI"] = old_uri
            else:
                os.environ.pop("MONGODB_URI", None)

    def test_initial_admin_seeding_when_empty(self):
        os.environ["ADMIN_INITIAL_PASSWORD"] = "InitialPass#123"
        init_db()
        admin = get_admin_by_username("jignesh")
        self.assertIsNotNone(admin)
        self.assertTrue(verify_password("InitialPass#123", admin["password_hash"]))





if __name__ == "__main__":
    unittest.main()

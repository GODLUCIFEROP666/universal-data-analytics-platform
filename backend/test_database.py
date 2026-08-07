"""Unit tests for database module."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, ".")

# Use temp database file for testing
test_db_fd, test_db_path = tempfile.mkstemp(suffix=".db")
os.close(test_db_fd)
os.environ["DATABASE_PATH"] = test_db_path
os.environ["JWT_SECRET"] = "super-secret-jwt-key-for-unit-testing-32bytes"

from app.database import (
    decrement_counter,
    get_admin_by_username,
    get_all_counters,
    get_counter,
    increment_counter,
    init_db,
    update_admin_password,
)
from app.auth_utils import hash_password, verify_password


class TestDatabase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except Exception:
                pass

    def test_default_admin(self):
        admin = get_admin_by_username("jignesh")
        self.assertIsNotNone(admin)
        self.assertEqual(admin["username"], "jignesh")
        expected_pass = os.environ.get("ADMIN_INITIAL_PASSWORD", "ChangeMeOnFirstLogin#123")
        self.assertTrue(verify_password(expected_pass, admin["password_hash"]))

    def test_counters(self):
        val = increment_counter("total_visitors")
        self.assertGreaterEqual(val, 1)
        val2 = get_counter("total_visitors")
        self.assertEqual(val, val2)

        dec = decrement_counter("total_visitors")
        self.assertEqual(dec, val - 1)

        all_c = get_all_counters()
        self.assertIn("total_visitors", all_c)
        self.assertIn("total_uploads", all_c)
        self.assertIn("total_analyses", all_c)

    def test_update_password(self):
        new_hash = hash_password("NewSecret123")
        success = update_admin_password("jignesh", new_hash)
        self.assertTrue(success)

        admin = get_admin_by_username("jignesh")
        self.assertTrue(verify_password("NewSecret123", admin["password_hash"]))

        # Restore initial password
        expected_pass = os.environ.get("ADMIN_INITIAL_PASSWORD", "ChangeMeOnFirstLogin#123")
        orig_hash = hash_password(expected_pass)
        update_admin_password("jignesh", orig_hash)


if __name__ == "__main__":
    unittest.main()

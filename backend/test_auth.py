import os
import sys
import unittest

os.environ["JWT_SECRET"] = "super-secret-jwt-key-for-unit-testing-32bytes"
sys.path.insert(0, ".")

from app.auth_utils import create_token, decode_token, hash_password, verify_password


class TestAuthUtils(unittest.TestCase):

    def test_hash_and_verify_password(self):
        password = "TestPassword@123"
        hashed = hash_password(password)
        self.assertNotEqual(password, hashed)
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("WrongPassword", hashed))

    def test_jwt_token(self):
        username = "jignesh"
        token = create_token(username)
        self.assertIsInstance(token, str)

        decoded_username = decode_token(token)
        self.assertEqual(decoded_username, username)

    def test_invalid_jwt_token(self):
        self.assertIsNone(decode_token("invalid.jwt.token"))


if __name__ == "__main__":
    unittest.main()

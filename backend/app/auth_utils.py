"""
auth_utils.py — Password hashing (bcrypt) and JWT token helpers.

- Passwords are NEVER stored or logged in plain text.
- JWT secret comes from the JWT_SECRET environment variable.
- Token expiry: 24 hours.
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JWT configuration
# ---------------------------------------------------------------------------

_jwt_secret: Optional[str] = None


def _load_env_file() -> None:
    """Lightweight zero-dependency loader for backend/.env file."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    candidates = [
        os.path.join(base_dir, ".env"),
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.getcwd(), "backend", ".env"),
    ]
    seen_paths = set()
    for env_path in candidates:
        norm_path = os.path.normpath(env_path)
        if norm_path in seen_paths:
            continue
        seen_paths.add(norm_path)
        if os.path.exists(norm_path):
            try:
                with open(norm_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            if k and (k not in os.environ or not os.environ[k].strip()):
                                os.environ[k] = v
            except Exception as exc:
                logger.warning("Could not parse .env file %s: %s", norm_path, exc)


def validate_jwt_secret() -> str:
    """Validate that JWT_SECRET is provided in environment variables or .env file; raise RuntimeError if missing."""
    _load_env_file()

    env_secret = os.environ.get("JWT_SECRET", "").strip()
    if not env_secret:
        raise RuntimeError(
            "JWT_SECRET environment variable is missing. "
            "The backend refuses to start without a configured JWT_SECRET. "
            "Please set JWT_SECRET in your environment or backend/.env file before starting the server."
        )
    return env_secret


def _get_jwt_secret() -> str:
    global _jwt_secret
    if _jwt_secret is None:
        _jwt_secret = validate_jwt_secret()
    return _jwt_secret


JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Hash a plain-text password using bcrypt. Returns the hash as a string."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------

def create_token(username: str) -> str:
    """Create a JWT token for the given admin username."""
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[str]:
    """Decode a JWT token and return the username, or None if invalid/expired."""
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub", "")
        return username if username else None
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

def get_current_admin(request: Request) -> str:
    """FastAPI dependency: extract and validate the JWT token from the Authorization header.
    Returns the admin username. Raises 401 if invalid."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")

    token = auth_header[7:].strip()
    username = decode_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return username

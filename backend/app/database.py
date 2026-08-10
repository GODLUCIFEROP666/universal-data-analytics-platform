"""
database.py — MongoDB Atlas database layer for application data.

Database:
  universal_data_analytics

Collections:
  visitors          — counter metrics (total_visitors, total_uploads, total_analyses)
  admin_users       — admin accounts with bcrypt-hashed passwords
  analytics_history — event history log of uploads and analyses
"""
from __future__ import annotations

import logging
import os
import re
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pymongo import MongoClient, ReturnDocument, ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

from app.auth_utils import _load_env_file

logger = logging.getLogger(__name__)

DB_NAME = "universal_data_analytics"
COUNTER_KEYS = ("total_visitors", "total_uploads", "total_analyses")

_lock = threading.Lock()
_client: Optional[MongoClient] = None


def _sanitize_mongo_uri(uri: str) -> str:
    """Mask credentials in MongoDB URI for logging purposes."""
    if not uri:
        return "<empty>"
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", uri)


def get_mongo_client() -> Optional[MongoClient]:
    """Return shared PyMongo MongoClient instance or None if MONGODB_URI is invalid/unreachable."""
    global _client
    with _lock:
        if _client is None:
            if "MONGODB_URI" not in os.environ or not os.environ["MONGODB_URI"].strip():
                _load_env_file()
            uri = os.environ.get("MONGODB_URI", "").strip()
            if not uri:
                logger.warning("MONGODB_URI is not set in environment variables.")
                return None
            try:
                client = MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
                # Force ping to verify authentication and cluster availability
                client.admin.command('ping')
                _client = client
                logger.info("MongoDB client connected and authenticated successfully (URI: %s)", _sanitize_mongo_uri(uri))
            except Exception as exc:
                sanitized_msg = _sanitize_mongo_uri(str(exc))
                logger.error("Failed to connect/authenticate with MongoDB: %s", sanitized_msg)
                return None
        return _client


def _get_db():
    client = get_mongo_client()
    if client is None:
        return None
    return client[DB_NAME]


def set_db_client(client: Optional[MongoClient]) -> None:
    """Helper to set or override the MongoClient (useful for testing)."""
    global _client
    with _lock:
        _client = client


def init_db() -> None:
    """
    Initialize indexes on MongoDB collections after verifying connection.
    Does NOT seed default data per user request ('dont add seed data any').
    """
    _load_env_file()
    client = get_mongo_client()
    if client is None:
        logger.error("Database initialization failed — MongoDB connection or authentication failed. Check MONGODB_URI.")
        return

    try:
        db = client[DB_NAME]
        db.admin_users.create_index("username_lowercase", unique=True)
        db.analytics_history.create_index([("timestamp", DESCENDING)])
        db.visitors.create_index("key", unique=True)
        logger.info("MongoDB indexes verified for '%s'", DB_NAME)
    except PyMongoError as exc:
        sanitized_msg = _sanitize_mongo_uri(str(exc))
        logger.error("MongoDB index initialization error: %s", sanitized_msg)


def _ensure_db():
    db = _get_db()
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="MongoDB service unavailable. Please check MONGODB_URI configuration and database user authentication credentials."
        )
    return db


def get_counter(key: str) -> int:
    """Return the current value of a counter from the 'visitors' collection."""
    db = _ensure_db()
    try:
        doc = db.visitors.find_one({"key": key})
        if doc and "value" in doc:
            return int(doc["value"])
        return 0
    except PyMongoError as exc:
        logger.error("Failed to get counter '%s': %s", key, _sanitize_mongo_uri(str(exc)))
        raise HTTPException(status_code=503, detail=f"MongoDB query failed for counter '{key}'") from exc


def increment_counter(key: str) -> int:
    """Atomically increment a counter by 1 and return the new value."""
    db = _ensure_db()
    try:
        doc = db.visitors.find_one_and_update(
            {"key": key},
            {"$inc": {"value": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int(doc["value"]) if doc and "value" in doc else 0
    except PyMongoError as exc:
        logger.error("Failed to increment counter '%s': %s", key, _sanitize_mongo_uri(str(exc)))
        raise HTTPException(status_code=503, detail=f"MongoDB update failed for counter '{key}'") from exc


def decrement_counter(key: str, floor: int = 0) -> int:
    """Decrement a counter by 1 (clamped to floor) and return the new value."""
    db = _ensure_db()
    try:
        current = get_counter(key)
        new_val = max(current - 1, floor)
        doc = db.visitors.find_one_and_update(
            {"key": key},
            {"$set": {"value": new_val}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int(doc["value"]) if doc and "value" in doc else 0
    except PyMongoError as exc:
        logger.error("Failed to decrement counter '%s': %s", key, _sanitize_mongo_uri(str(exc)))
        raise HTTPException(status_code=503, detail=f"MongoDB update failed for counter '{key}'") from exc


def get_all_counters() -> Dict[str, int]:
    """Return all counters as a dictionary from the 'visitors' collection."""
    db = _ensure_db()
    result = {key: 0 for key in COUNTER_KEYS}
    try:
        cursor = db.visitors.find({})
        for doc in cursor:
            k = doc.get("key")
            v = doc.get("value", 0)
            if k:
                result[k] = int(v)
        return result
    except PyMongoError as exc:
        logger.error("Failed to get all counters: %s", _sanitize_mongo_uri(str(exc)))
        raise HTTPException(status_code=503, detail="MongoDB query failed for all counters") from exc


def get_admin_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Return admin record (id, username, password_hash) or None."""
    db = _ensure_db()
    try:
        clean_user = username.strip()
        doc = db.admin_users.find_one({"username_lowercase": clean_user.lower()})
        if not doc:
            doc = db.admin_users.find_one({"username": {"$regex": f"^{re.escape(clean_user)}$", "$options": "i"}})
        if not doc:
            return None
        return {
            "id": str(doc["_id"]),
            "username": doc.get("username", clean_user),
            "password_hash": doc.get("password_hash", ""),
        }
    except PyMongoError as exc:
        logger.error("Failed to fetch admin by username: %s", _sanitize_mongo_uri(str(exc)))
        raise HTTPException(status_code=503, detail="MongoDB query failed for admin authentication") from exc


def update_admin_password(username: str, new_hash: str) -> bool:
    """Update password hash for an admin user. Returns True on success."""
    db = _ensure_db()
    try:
        clean_user = username.strip()
        result = db.admin_users.update_one(
            {"$or": [
                {"username_lowercase": clean_user.lower()},
                {"username": {"$regex": f"^{re.escape(clean_user)}$", "$options": "i"}},
            ]},
            {"$set": {"password_hash": new_hash}},
        )
        return result.modified_count > 0 or result.matched_count > 0
    except PyMongoError as exc:
        logger.error("Failed to update admin password: %s", _sanitize_mongo_uri(str(exc)))
        raise HTTPException(status_code=503, detail="MongoDB update failed for admin password") from exc


def record_analytics_event(action: str, filename: str, details: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Record an event in the 'analytics_history' collection."""
    db = _get_db()
    if db is None:
        logger.warning("Analytics event recording skipped — MongoDB unavailable.")
        return None
    try:
        record = {
            "action": action,
            "filename": filename,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        res = db.analytics_history.insert_one(record)
        record["id"] = str(res.inserted_id)
        if "_id" in record:
            record["_id"] = str(record["_id"])
        return record
    except PyMongoError as exc:
        logger.error("Failed to record analytics event: %s", _sanitize_mongo_uri(str(exc)))
        return None


def get_analytics_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve recent analytics history records."""
    db = _ensure_db()
    try:
        cursor = db.analytics_history.find({}).sort("timestamp", DESCENDING).limit(limit)
        results = []
        for doc in cursor:
            doc["id"] = str(doc["_id"])
            doc["_id"] = str(doc["_id"])
            results.append(doc)
        return results
    except PyMongoError as exc:
        logger.error("Failed to fetch analytics history: %s", _sanitize_mongo_uri(str(exc)))
        raise HTTPException(status_code=503, detail="MongoDB query failed for analytics history") from exc

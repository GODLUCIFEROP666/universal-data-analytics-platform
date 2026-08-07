"""
counters.py — Session tracking and admin statistics routes.

Endpoints:
  POST /api/session/start  — increment total_visitors + active_users (public)
  POST /api/session/end    — decrement active_users (public, called via sendBeacon)
  GET  /api/admin/stats    — return all counters (admin-only)
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.auth_utils import get_current_admin
from app.database import decrement_counter, get_all_counters, get_counter, increment_counter

from threading import Lock

router = APIRouter(tags=["counters"])

_active_users_lock = Lock()
_active_users = 0


@router.get("/api/visitor-count")
async def get_visitor_count() -> Dict[str, Any]:
    """Return the current total visitors count from SQLite database."""
    count = get_counter("total_visitors")
    return {"visitor_count": count}


@router.post("/api/session/start")
async def session_start() -> Dict[str, Any]:
    """Called when user clicks Start. Increments visitor count (SQLite) and active user count (in-memory)."""
    global _active_users
    visitor_count = increment_counter("total_visitors")
    with _active_users_lock:
        _active_users += 1
    return {"visitor_count": visitor_count}


@router.post("/api/session/end")
async def session_end() -> Dict[str, Any]:
    """Called on page unload (via sendBeacon). Decrements in-memory active user count."""
    global _active_users
    with _active_users_lock:
        _active_users = max(_active_users - 1, 0)
    return {"ok": True}


@router.get("/api/admin/stats")
async def admin_stats(
    _username: str = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Return all counters (SQLite metrics + in-memory active_users). Admin-only."""
    stats = get_all_counters()
    with _active_users_lock:
        stats["active_users"] = _active_users
    return stats

"""
auth.py — Admin authentication routes.

Endpoints:
  POST /api/auth/login          — validate credentials, return JWT
  GET  /api/auth/me             — validate token, return username
  PUT  /api/auth/change-password — change admin password (protected)
  POST /api/auth/logout         — no-op (stateless JWT, frontend clears token)
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth_utils import (
    create_token,
    get_current_admin,
    hash_password,
    verify_password,
)
from app.database import get_admin_by_username, update_admin_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/login")
async def login(body: LoginRequest) -> Dict[str, Any]:
    """Authenticate admin and return a JWT token."""
    admin = get_admin_by_username(body.username)
    if admin is None:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    if not verify_password(body.password, admin["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = create_token(admin["username"])
    return {"token": token, "username": admin["username"]}


@router.get("/me")
async def me(username: str = Depends(get_current_admin)) -> Dict[str, Any]:
    """Return the currently authenticated admin username."""
    return {"username": username}


@router.put("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    username: str = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Change the admin password. Requires old password verification."""
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")

    admin = get_admin_by_username(username)
    if admin is None:
        raise HTTPException(status_code=401, detail="Admin account not found.")

    if not verify_password(body.old_password, admin["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")

    new_hash = hash_password(body.new_password)
    success = update_admin_password(username, new_hash)
    if not success:
        raise HTTPException(status_code=500, detail="Password update failed.")

    return {"message": "Password changed successfully."}


@router.post("/logout")
async def logout() -> Dict[str, Any]:
    """Logout endpoint. JWT is stateless — frontend clears the token."""
    return {"message": "Logged out successfully."}

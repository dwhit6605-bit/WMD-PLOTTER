"""
Authentication utilities: password hashing, JWT creation/verification,
FastAPI middleware, and per-request user dependencies.
"""

import os
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

JWT_SECRET: str = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET:
    JWT_SECRET = secrets.token_hex(32)
    logger.warning(
        "JWT_SECRET not set in backend/.env — using ephemeral key. "
        "All sessions will be invalidated on every restart."
    )

JWT_ALGORITHM   = "HS256"
JWT_EXPIRE_DAYS = int(os.environ.get("JWT_EXPIRE_DAYS", "7"))
COOKIE_NAME     = "wmd_token"

ALLOW_REGISTRATION = os.environ.get("ALLOW_REGISTRATION", "false").lower() == "true"
REGISTRATION_CODE  = os.environ.get("REGISTRATION_CODE", "")

# ── Password hashing ──────────────────────────────────────────────────────────

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_ctx.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_token(user_id: int, username: str, role: str, org_id=None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "username": username, "role": role, "exp": expire}
    if org_id is not None:
        payload["org_id"] = org_id
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


# ── Route helpers ─────────────────────────────────────────────────────────────

# Paths that don't require authentication — enumerate explicitly so /auth/me stays protected
_PUBLIC_EXACT = {
    "/login", "/register", "/request-access",
    "/sw.js", "/manifest.json",
    # Auth actions that work without a cookie
    "/auth/login", "/auth/logout", "/auth/register", "/auth/registration-status",
    "/auth/request-access",
}
_PUBLIC_PREFIXES = ("/static/icons/", "/kml/")
_PUBLIC_API      = {"/api/health"}


def _is_public(path: str) -> bool:
    if path in _PUBLIC_EXACT or path in _PUBLIC_API:
        return True
    return any(path.startswith(p) for p in _PUBLIC_PREFIXES)


def _is_api_path(path: str) -> bool:
    # /auth/* is treated as an API path so unauthenticated requests get JSON 401, not an HTML redirect
    return any(path.startswith(p) for p in ("/api/", "/kml/", "/export/", "/auth/"))


# ── Middleware ────────────────────────────────────────────────────────────────

async def auth_middleware(request: Request, call_next):
    """
    Checks every request for a valid JWT cookie.
    - Public paths bypass the check.
    - API paths return 401 JSON on failure.
    - Page paths redirect to /login on failure.
    """
    if _is_public(request.url.path):
        # Public paths never *require* a session, but if the caller happens to
        # have a valid one, decode it so endpoints can serve per-user data.
        # Without this, request.state.user is unset even for a signed-in user,
        # and any Depends(current_user) under a public prefix (e.g. /kml/)
        # rejects everyone. Failures here are ignored on purpose — a bad or
        # absent cookie simply means anonymous.
        token = request.cookies.get(COOKIE_NAME)
        if token:
            try:
                payload = decode_token(token)
                payload["id"] = int(payload["sub"])
                request.state.user = payload
            except Exception:
                pass
        return await call_next(request)

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        if _is_api_path(request.url.path):
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        return RedirectResponse(url="/login", status_code=302)

    try:
        payload = decode_token(token)
        payload["id"] = int(payload["sub"])   # convenience alias used throughout main.py
        request.state.user = payload
    except jwt.ExpiredSignatureError:
        resp = RedirectResponse(url="/login?reason=expired", status_code=302)
        resp.delete_cookie(COOKIE_NAME)
        return resp
    except jwt.InvalidTokenError:
        resp = RedirectResponse(url="/login", status_code=302)
        resp.delete_cookie(COOKIE_NAME)
        return resp

    return await call_next(request)


# ── FastAPI dependencies ──────────────────────────────────────────────────────

def current_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_admin(request: Request) -> dict:
    user = current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

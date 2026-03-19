"""FastAPI authentication dependencies shared across routers."""

from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.auth import decode_access_token
from app.config import settings
from app.logger import setup_logger

logger = setup_logger(__name__)

security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Get current authenticated user from JWT token."""
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    email = payload.get("email")
    role = payload.get("role")
    if not user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return {"id": user_id, "email": email, "role": role}


def get_current_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Legacy alias — all users are admin in this system."""
    return current_user


def get_current_admin_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
) -> dict | None:
    """Try to get current admin, return None if not authenticated."""
    try:
        if credentials is None:
            return None
        token = credentials.credentials
        payload = decode_access_token(token)
        if payload is None:
            return None
        user_id = payload.get("sub")
        email = payload.get("email")
        role = payload.get("role")
        if not user_id or not email or role != "admin":
            return None
        return {"id": user_id, "email": email, "role": role}
    except Exception:
        return None


def require_admin(x_admin_token: str | None = Header(default=None)):
    """Validate admin token if configured (legacy)."""
    if not settings.admin_token:
        logger.warning("Admin token not configured - admin endpoints are unprotected")
        return
    if x_admin_token != settings.admin_token:
        logger.warning(f"Invalid admin token attempt from {x_admin_token}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
        )

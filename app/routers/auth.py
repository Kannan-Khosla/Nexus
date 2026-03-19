"""Authentication endpoints: register, login, forgot/reset password, user info."""

from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timedelta, timezone
from app.supabase_config import supabase
from app.config import settings
from app.logger import setup_logger
from app.auth import get_password_hash, verify_password, create_access_token, decode_access_token
from app.email_service import email_service
from app.dependencies import get_current_user
from app.schemas import UserRegister, UserLogin, Token, ForgotPasswordRequest, ResetPasswordRequest

logger = setup_logger(__name__)
router = APIRouter()

@router.post("/auth/register", response_model=Token)
def register(user_data: UserRegister):
    """Register a new Admin account (Open Registration)."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Check if user already exists
        existing = (
            supabase.table("users")
            .select("id")
            .eq("email", user_data.email.lower())
            .execute()
        )
        if existing.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        
        # Validate password length
        if len(user_data.password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters",
            )
        
        # Hash password and create user
        password_hash = get_password_hash(user_data.password)
        new_user = (
            supabase.table("users")
            .insert(
                {
                    "email": user_data.email.lower(),
                    "password_hash": password_hash,
                    "name": user_data.name,
                    "role": "admin", # Always admin
                }
            )
            .execute()
        )
        
        user = new_user.data[0]
        user_id = user["id"]
        
        # Create access token
        access_token = create_access_token(
            data={"sub": user_id, "email": user["email"], "role": user["role"]}
        )
        
        logger.info(f"New admin registered: {user['email']}")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in register: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )


@router.post("/auth/login", response_model=Token)
def login(credentials: UserLogin):
    """Login and get JWT token."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Find user
        user_res = (
            supabase.table("users")
            .select("*")
            .eq("email", credentials.email.lower())
            .limit(1)
            .execute()
        )
        
        if not user_res.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )
        
        user = user_res.data[0]
        
        # Verify password
        if not verify_password(credentials.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )
        
        # Create access token
        access_token = create_access_token(
            data={"sub": user["id"], "email": user["email"], "role": user["role"]}
        )
        
        logger.info(f"User logged in: {user['email']}")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in login: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed",
        )

@router.post("/auth/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    """Request a password reset link."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Check if user exists
        user_res = (
            supabase.table("users")
            .select("id, email, name")
            .eq("email", req.email.lower())
            .limit(1)
            .execute()
        )
        
        if not user_res.data:
            # Silently fail to prevent user enumeration
            return {"message": "If an account exists, a reset link has been sent."}
        
        user = user_res.data[0]
        
        # Generate reset token (short-lived, e.g. 1 hour)
        reset_token = create_access_token(
            data={"sub": user["id"], "type": "reset"},
            expires_delta=timedelta(hours=1)
        )
        
        # Generate link using configured frontend URL
        frontend_url = settings.frontend_url.rstrip('/')
        reset_link = f"{frontend_url}/reset-password?token={reset_token}"

        # Send email
        email_service.send_email(
            to_emails=[user["email"]],
            subject="Reset Your Password",
            body_text=f"Hi {user['name']},\n\nClick the link below to reset your password:\n{reset_link}\n\nThis link expires in 1 hour.\n\nIf you didn't request this, please ignore this email.",
            body_html=f"""
                <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2>Reset Your Password</h2>
                    <p>Hi {user['name']},</p>
                    <p>Click the button below to reset your password:</p>
                    <a href="{reset_link}" style="display: inline-block; padding: 12px 24px; background-color: #6366f1; color: white; text-decoration: none; border-radius: 6px;">Reset Password</a>
                    <p style="margin-top: 20px; font-size: 12px; color: #666;">This link expires in 1 hour. If you didn't request this, please ignore this email.</p>
                </div>
            """
        )
        
        return {"message": "If an account exists, a reset link has been sent."}
        
    except Exception as e:
        logger.error(f"Error in forgot_password: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process request",
        )

@router.post("/auth/reset-password")
def reset_password(req: ResetPasswordRequest):
    """Reset password using token."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify token
        payload = decode_access_token(req.token)
        if not payload or payload.get("type") != "reset":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token",
            )
            
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token payload",
            )
        
        # Validate new password
        if len(req.new_password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters",
            )
            
        # Hash new password
        password_hash = get_password_hash(req.new_password)
        
        # Update user
        supabase.table("users").update({
            "password_hash": password_hash,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", user_id).execute()
        
        return {"message": "Password successfully reset"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in reset_password: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password",
        )


@router.get("/auth/me")
def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user information."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        user_res = (
            supabase.table("users")
            .select("id, email, name, role, created_at")
            .eq("id", current_user["id"])
            .limit(1)
            .execute()
        )
        
        if not user_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        
        user = user_res.data[0]
        return {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
            "created_at": user["created_at"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_current_user_info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user info",
        )

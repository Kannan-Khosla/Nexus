from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Header, HTTPException, status, Depends, Query
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse, Response
from typing import Optional
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, EmailStr
from openai import OpenAI
from datetime import datetime, timedelta, timezone
from supabase_config import supabase
from config import settings
from logger import setup_logger
from middleware import error_handler, http_exception_handler, validation_exception_handler
from auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
)
from storage import upload_file, download_file, delete_file, list_attachments
from email_service import email_service
from routing_service import routing_service
from email_polling_service import email_polling_service
from spam_classifier import spam_classifier
import re
import time
import io
import base64
import json
import asyncio
from contextlib import asynccontextmanager

# Set up logging
logger = setup_logger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=settings.openai_api_key)


# Background task for email polling
async def email_polling_task():
    """Background task that polls email accounts periodically."""
    while True:
        try:
            if settings.email_polling_enabled:
                logger.debug("Starting email polling cycle")
                # Run synchronous polling in executor to avoid blocking event loop
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, email_polling_service.poll_all_accounts)
                if result.get("success"):
                    if result.get("total_tickets", 0) > 0:
                        logger.info(f"Email polling: {result.get('total_emails', 0)} emails processed, {result.get('total_tickets', 0)} tickets created")
                else:
                    logger.warning(f"Email polling failed: {result.get('error')}")
            else:
                logger.debug("Email polling is disabled")
            
            # Wait for the configured interval
            await asyncio.sleep(settings.email_polling_interval)
        except Exception as e:
            logger.error(f"Error in email polling task: {e}", exc_info=True)
            # Wait before retrying on error
            await asyncio.sleep(settings.email_polling_interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("Starting email polling background task")
    polling_task = asyncio.create_task(email_polling_task())
    yield
    # Shutdown
    logger.info("Shutting down email polling background task")
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        pass


# Create FastAPI app with lifespan
app = FastAPI(title="AI Support API", version="1.0.0", lifespan=lifespan)

# Register error handlers
app.add_exception_handler(Exception, error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTTP Bearer token security
security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)


# ---------------------------
# 📦 MODELS
# ---------------------------


class TicketRequest(BaseModel):
    context: str
    subject: str
    message: str
    priority: str = "medium"  # low, medium, high, urgent


class MessageRequest(BaseModel):
    message: str


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class RatingRequest(BaseModel):
    message_id: str
    rating: int  # 1-5


class EscalateRequest(BaseModel):
    reason: str | None = None


class AdminReplyRequest(BaseModel):
    message: str


class AssignAdminRequest(BaseModel):
    admin_email: str


class SLADefinitionRequest(BaseModel):
    name: str
    description: str | None = None
    priority: str  # low, medium, high, urgent
    response_time_minutes: int
    resolution_time_minutes: int
    business_hours_only: bool = False
    business_hours_start: str | None = None  # HH:MM format
    business_hours_end: str | None = None  # HH:MM format
    business_days: list[int] | None = None  # [1-7] where 1=Monday, 7=Sunday


class UpdatePriorityRequest(BaseModel):
    priority: str  # low, medium, high, urgent


class TimeEntryRequest(BaseModel):
    duration_minutes: int
    description: str | None = None
    entry_type: str = "work"  # work, waiting, research, communication, other
    billable: bool = True


class EmailAccountRequest(BaseModel):
    email: EmailStr
    display_name: str | None = None
    provider: str  # smtp, sendgrid, ses, mailgun, other
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    api_key: str | None = None
    credentials: dict | None = None
    is_active: bool = True
    is_default: bool = False
    imap_host: str | None = None
    imap_port: int | None = None
    imap_enabled: bool = False


class SendEmailRequest(BaseModel):
    to_emails: list[EmailStr]
    subject: str
    body_text: str
    body_html: str | None = None
    cc_emails: list[EmailStr] | None = None
    bcc_emails: list[EmailStr] | None = None
    reply_to: EmailStr | None = None
    account_id: str | None = None


class EmailWebhookRequest(BaseModel):
    raw_email: str | None = None
    from_email: EmailStr | None = None
    to_email: EmailStr | None = None
    subject: str | None = None
    body: str | None = None
    message_id: str | None = None
    in_reply_to: str | None = None

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class EmailTemplateRequest(BaseModel):
    name: str
    subject: str
    body_text: str
    body_html: str | None = None
    template_type: str  # ticket_created, ticket_reply, ticket_closed, ticket_assigned, custom
    variables: dict | None = None
    is_active: bool = True


class DeleteTicketsRequest(BaseModel):
    ticket_ids: list[str]


class RestoreTicketsRequest(BaseModel):
    ticket_ids: list[str]


class OrganizationRequest(BaseModel):
    name: str
    slug: str
    description: str | None = None


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str = "admin"  # admin or viewer


class RoutingRuleRequest(BaseModel):
    name: str
    description: str | None = None
    priority: int = 0
    is_active: bool = True
    conditions: dict  # {keywords: [], issue_types: [], tags: [], context: [], priority: []}
    action_type: str  # assign_to_agent, assign_to_group, set_priority, add_tag, set_category
    action_value: str  # Agent email, group name, priority value, tag name, category name


class TagRequest(BaseModel):
    name: str
    color: str | None = None
    description: str | None = None


class CategoryRequest(BaseModel):
    name: str
    color: str | None = None
    description: str | None = None


class TicketTagsRequest(BaseModel):
    tag_ids: list[str]


class TicketCategoryRequest(BaseModel):
    category: str | None = None


# ---------------------------
# 🧠 ROUTES
# ---------------------------


@app.get("/")
def health_check():
    """Simple health check.

    Returns
    -------
    dict
        `{ "message": "..." }` indicating the API is up.
    """
    return {"message": "AI Support API (threaded system) is running"}


# ---------------------------
# 🔐 AUTHENTICATION HELPERS
# ---------------------------
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


def get_current_customer(current_user: dict = Depends(get_current_user)) -> dict:
    """Get current user, ensuring they are a customer."""
    if current_user["role"] != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for customers only",
        )
    return current_user


def get_current_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Get current user, ensuring they are an admin or super_admin."""
    if current_user["role"] not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def get_current_super_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Get current user, ensuring they are a super_admin."""
    if current_user["role"] != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return current_user


def get_current_admin_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional)) -> dict | None:
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


# ---------------------------
# 🔐 AUTHENTICATION ENDPOINTS
# ---------------------------
@app.post("/auth/register", response_model=Token)
def register(user_data: UserRegister):
    """Register a new customer account."""
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
        if len(user_data.password.encode('utf-8')) > 72:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password cannot be longer than 72 bytes",
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
                    "role": "customer",
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
        
        logger.info(f"New customer registered: {user['email']}")
        
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


@app.post("/auth/login", response_model=Token)
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

@app.post("/auth/forgot-password")
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

@app.post("/auth/reset-password")
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


@app.get("/auth/me")
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


@app.post("/auth/admin/register", response_model=Token)
def register_admin(
    user_data: UserRegister,
    bootstrap_key: str = Query(default=None),
    current_admin: dict | None = Depends(get_current_admin_optional),
):
    """
    Register a new admin account.
    
    Two ways to use this:
    1. If no admins exist yet: Use bootstrap_key from ADMIN_BOOTSTRAP_KEY env var (optional)
    2. If admins exist: Must be logged in as admin (JWT token required)
    """
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Check if any admins exist
        admin_count = (
            supabase.table("users")
            .select("id", count="exact")
            .eq("role", "admin")
            .execute()
            .count
        )
        
        # Bootstrap mode: No admins exist yet
        if admin_count == 0:
            # Check bootstrap key if provided
            bootstrap_key_env = getattr(settings, "admin_bootstrap_key", None)
            if bootstrap_key_env:
                if bootstrap_key != bootstrap_key_env:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Bootstrap key required for first admin. Set ADMIN_BOOTSTRAP_KEY in .env",
                    )
            logger.info("Bootstrap mode: Creating first admin account")
        else:
            # Normal mode: Require admin authentication
            if current_admin is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Admin authentication required. Login as admin first or use bootstrap key if no admins exist.",
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
        if len(user_data.password.encode('utf-8')) > 72:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password cannot be longer than 72 bytes",
            )
        
        # Hash password and create admin user
        password_hash = get_password_hash(user_data.password)
        new_user = (
            supabase.table("users")
            .insert(
                {
                    "email": user_data.email.lower(),
                    "password_hash": password_hash,
                    "name": user_data.name,
                    "role": "admin",
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
        
        if admin_count == 0:
            logger.info(f"First admin created via bootstrap: {user['email']}")
        else:
            logger.info(f"New admin registered by {current_admin['email']}: {user['email']}")
        
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
        logger.error(f"Error in register_admin: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin registration failed",
        )


# ---------------------------
# 🔐 LEGACY ADMIN AUTH (kept for backward compatibility)
# ---------------------------
def require_admin(x_admin_token: str | None = Header(default=None)):
    """Validate admin token if configured."""
    if not settings.admin_token:
        # If no token configured, allow all (dev mode)
        logger.warning("Admin token not configured - admin endpoints are unprotected")
        return
    if x_admin_token != settings.admin_token:
        logger.warning(f"Invalid admin token attempt from {x_admin_token}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
        )


# ---------------------------
# 🛡️ RELIABILITY & GUARDRAILS
# ---------------------------
def is_rate_limited(ticket_id: str) -> tuple[bool, dict]:
    """Check if ticket has exceeded AI reply rate limit."""
    try:
        window_start = (
            datetime.utcnow() - timedelta(seconds=settings.ai_reply_window_seconds)
        ).isoformat()
        count = (
            supabase.table("messages")
            .select("id", count="exact")
            .eq("ticket_id", ticket_id)
            .eq("sender", "ai")
            .gte("created_at", window_start)
            .execute()
            .count
        )
        limited = count >= settings.ai_reply_max_per_window
        if limited:
            logger.warning(
                f"Rate limit exceeded for ticket {ticket_id}: {count} replies in window"
            )
        return limited, {"ai_replies_in_window": count}
    except Exception as e:
        logger.error(f"Error checking rate limit for ticket {ticket_id}: {e}")
        return False, {}


PROFANITY = re.compile(r"\b(fuck|shit|bitch|asshole)(?:ing|s|ed)?\b", re.IGNORECASE)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?:\+?\d[\s-]?)?(?:\(?\d{3}\)?[\s-]?)?\d{3}[\s-]?\d{4}")
CC = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


def sanitize_output(text: str) -> tuple[str, dict]:
    redacted = text or ""
    flags = {"profanity": False, "email": False, "phone": False, "cc": False}
    if PROFANITY.search(redacted):
        flags["profanity"] = True
        redacted = PROFANITY.sub("***", redacted)
    if EMAIL.search(redacted):
        flags["email"] = True
        redacted = EMAIL.sub("***@***.***", redacted)
    # Check CC before PHONE to avoid phone regex matching credit card numbers
    if CC.search(redacted):
        flags["cc"] = True
        redacted = CC.sub("**** **** **** ****", redacted)
    if PHONE.search(redacted):
        flags["phone"] = True
        redacted = PHONE.sub("***-***-****", redacted)
    return redacted, flags


def generate_ai_reply(prompt: str) -> str:
    """
    Generate AI reply with exponential backoff retry logic.
    
    Parameters
    ----------
    prompt : str
        The prompt to send to OpenAI
    
    Returns
    -------
    str
        The generated AI reply
    
    Raises
    ------
    Exception
        If all retry attempts fail
    """
    delay = settings.openai_initial_delay
    max_retries = settings.openai_max_retries
    
    for attempt in range(max_retries + 1):
        try:
            logger.debug(f"Calling OpenAI API (attempt {attempt + 1}/{max_retries + 1})")
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
            )
            response = completion.choices[0].message.content
            logger.debug("OpenAI API call successful")
            return response
        except Exception as e:
            if attempt < max_retries:
                logger.warning(
                    f"OpenAI API call failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                time.sleep(delay)
                delay *= settings.openai_backoff_multiplier
            else:
                logger.error(f"OpenAI API call failed after {max_retries + 1} attempts: {e}")
                raise e


# ---------------------------------------------------
# POST /ticket → Create or reuse ticket, AI replies
# ---------------------------------------------------
@app.post("/ticket")
def create_or_continue_ticket(
    req: TicketRequest, current_user: dict = Depends(get_current_customer)
):
    """Create or continue a ticket and optionally generate an AI reply.

    Parameters
    ----------
    req : TicketRequest
        `{ context, subject, message }`
    current_user : dict
        Current authenticated customer

    Returns
    -------
    dict
        `{ ticket_id, reply? }` or `{ ticket_id, rate_limited, wait_seconds }`
    """
    try:
        if supabase is None:
            return {"error": "Supabase is not configured. Please set SUPABASE_URL and SUPABASE_KEY in .env file"}
        
        user_id = current_user["id"]
        
        # 1️⃣ Find open ticket with same context & subject for this user
        existing = (
            supabase.table("tickets")
            .select("*")
            .eq("context", req.context)
            .eq("subject", req.subject)
            .eq("status", "open")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if existing.data:
            ticket = existing.data[0]
            ticket_id = ticket["id"]
            logger.info(f"Continuing existing ticket: {ticket_id}")
        else:
            # Create new ticket
            priority = req.priority if hasattr(req, 'priority') and req.priority in ['low', 'medium', 'high', 'urgent'] else 'medium'
            
            # Auto-assign SLA based on priority
            sla_id = None
            try:
                sla_res = (
                    supabase.table("sla_definitions")
                    .select("id")
                    .eq("priority", priority)
                    .eq("is_active", True)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if sla_res.data:
                    sla_id = sla_res.data[0]["id"]
            except Exception as e:
                logger.warning(f"Could not auto-assign SLA for priority {priority}: {e}")
            
            new_ticket = (
                supabase.table("tickets")
                .insert(
                    {
                        "context": req.context,
                        "subject": req.subject,
                        "status": "open",
                        "priority": priority,
                        "sla_id": sla_id,
                        "user_id": user_id,
                        "source": "web",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                .execute()
            )
            ticket = new_ticket.data[0]
            ticket_id = ticket["id"]
            logger.info(f"Created new ticket: {ticket_id}")
            
            # Apply routing rules if organization exists
            if ticket.get("organization_id"):
                try:
                    routing_result = routing_service.apply_routing_rules(ticket_id, ticket.get("organization_id"))
                    if routing_result.get("success") and routing_result.get("rules_matched", 0) > 0:
                        logger.info(f"Applied {routing_result['rules_matched']} routing rule(s) to ticket {ticket_id}")
                        # Reload ticket to get updated assignment/priority
                        ticket_res = (
                            supabase.table("tickets")
                            .select("*")
                            .eq("id", ticket_id)
                            .limit(1)
                            .execute()
                        )
                        if ticket_res.data:
                            ticket = ticket_res.data[0]
                except Exception as e:
                    logger.warning(f"Failed to apply routing rules to ticket {ticket_id}: {e}")

        # 2️⃣ Add customer message
        supabase.table("messages").insert(
            {
                "ticket_id": ticket_id,
                "sender": "customer",
                "message": req.message,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()

        # 3️⃣ Check if human is assigned — skip AI if true
        if ticket.get("assigned_to"):
            logger.info(
                f"Human agent assigned ({ticket['assigned_to']}), skipping AI reply for ticket {ticket_id}"
            )
            return {
                "ticket_id": ticket_id,
                "reply": f"Human agent {ticket['assigned_to']} will handle this ticket.",
            }

        # 4️⃣ Fetch full message history for context
        history = (
            supabase.table("messages")
            .select("sender, message")
            .eq("ticket_id", ticket_id)
            .order("created_at", desc=False)
            .execute()
        )
        conversation_history = "\n".join(
            [f"{m['sender'].capitalize()}: {m['message']}" for m in history.data]
        )

        # 5️⃣ Generate AI reply
        prompt = f"""
        You are an AI support assistant for {req.context}.
        Continue the following ticket conversation helpfully and politely.
        ----
        {conversation_history}
        ----
        Reply as the assistant:
        """

        # 5.1️⃣ Rate limit check
        limited, _meta = is_rate_limited(ticket_id)
        if limited:
            return {
                "ticket_id": ticket_id,
                "rate_limited": True,
                "wait_seconds": settings.ai_reply_window_seconds,
            }

        # 5.2️⃣ Generate AI reply with retry/backoff
        logger.info(f"Generating AI reply for ticket {ticket_id}")
        raw_answer = generate_ai_reply(prompt)

        # 5.3️⃣ Sanitize output for profanity/PII
        answer, flags = sanitize_output(raw_answer)

        # 6️⃣ Store AI reply
        supabase.table("messages").insert(
            {
                "ticket_id": ticket_id,
                "sender": "ai",
                "message": answer,
                "confidence": 0.95,
                "success": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()

        return {"ticket_id": ticket_id, "reply": answer}

    except Exception as e:
        logger.error(f"Error in create_or_continue_ticket: {e}", exc_info=True)
        raise


# ---------------------------------------------------
# POST /ticket/{ticket_id}/reply → Continue thread
# ---------------------------------------------------
@app.post("/ticket/{ticket_id}/reply")
def reply_to_existing_ticket(
    ticket_id: str, req: MessageRequest, current_user: dict = Depends(get_current_customer)
):
    """Append a customer message and optionally generate an AI reply.

    If a human is assigned, AI reply is skipped.
    Rate limiting and output sanitization apply if AI is used.
    """
    try:
        if supabase is None:
            return {"error": "Supabase is not configured. Please set SUPABASE_URL and SUPABASE_KEY in .env file"}
        
        user_id = current_user["id"]
        
        # 1️⃣ Verify ticket exists and belongs to user
        ticket_res = (
            supabase.table("tickets").select("*").eq("id", ticket_id).limit(1).execute()
        )
        if not ticket_res.data:
            return {"error": f"Ticket {ticket_id} not found."}

        ticket = ticket_res.data[0]
        
        # Verify ticket belongs to current user
        if ticket.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this ticket",
            )

        # 2️⃣ Store new customer message
        supabase.table("messages").insert(
            {
                "ticket_id": ticket_id,
                "sender": "customer",
                "message": req.message,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()

        # 3️⃣ If human assigned, skip AI
        if ticket.get("assigned_to"):
            logger.info(
                f"Human assigned ({ticket['assigned_to']}), skipping AI for ticket {ticket_id}"
            )
            return {
                "ticket_id": ticket_id,
                "reply": f"Human agent {ticket['assigned_to']} will handle this.",
            }

        # 4️⃣ Fetch all messages
        history = (
            supabase.table("messages")
            .select("sender, message")
            .eq("ticket_id", ticket_id)
            .order("created_at", desc=False)
            .execute()
        )
        conversation_history = "\n".join(
            [f"{m['sender'].capitalize()}: {m['message']}" for m in history.data]
        )

        # 5️⃣ Generate AI reply
        prompt = f"""
        You are an AI assistant continuing this customer support thread.
        ----
        {conversation_history}
        ----
        Respond concisely and politely as the assistant.
        """

        # 5.1️⃣ Rate limit check
        limited, _meta = is_rate_limited(ticket_id)
        if limited:
            return {
                "ticket_id": ticket_id,
                "rate_limited": True,
                "wait_seconds": settings.ai_reply_window_seconds,
            }

        # 5.2️⃣ Generate AI reply with retry/backoff
        raw_answer = generate_ai_reply(prompt)

        # 5.3️⃣ Sanitize output for profanity/PII
        answer, flags = sanitize_output(raw_answer)

        # 6️⃣ Store AI reply
        supabase.table("messages").insert(
            {
                "ticket_id": ticket_id,
                "sender": "ai",
                "message": answer,
                "confidence": 0.95,
                "success": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()

        return {"ticket_id": ticket_id, "reply": answer}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in reply_to_existing_ticket: {e}", exc_info=True)
        raise


# ---------------------------------------------------
# POST /ticket/{ticket_id}/rate → Rate an AI response
# ---------------------------------------------------
@app.post("/ticket/{ticket_id}/rate")
def rate_ai_response(
    ticket_id: str,
    req: RatingRequest,
    current_user: dict = Depends(get_current_customer),
):
    """Rate an AI response message."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        user_id = current_user["id"]
        
        # Validate rating
        if req.rating < 1 or req.rating > 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rating must be between 1 and 5",
            )
        
        # Verify ticket exists and belongs to user
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found",
            )
        ticket = ticket_res.data[0]
        if ticket.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this ticket",
            )
        
        # Verify message exists and is an AI response
        message_res = (
            supabase.table("messages")
            .select("*")
            .eq("id", req.message_id)
            .eq("ticket_id", ticket_id)
            .limit(1)
            .execute()
        )
        if not message_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found",
            )
        message = message_res.data[0]
        if message.get("sender") != "ai":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only AI messages can be rated",
            )
        
        # Check if user already rated this message
        existing_rating = (
            supabase.table("ratings")
            .select("*")
            .eq("ticket_id", ticket_id)
            .eq("message_id", req.message_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        if existing_rating.data:
            # Update existing rating
            supabase.table("ratings").update({"rating": req.rating}).eq(
                "id", existing_rating.data[0]["id"]
            ).execute()
            logger.info(f"Updated rating for message {req.message_id} by user {user_id}")
        else:
            # Create new rating
            supabase.table("ratings").insert(
                {
                    "ticket_id": ticket_id,
                    "message_id": req.message_id,
                    "user_id": user_id,
                    "rating": req.rating,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            ).execute()
            logger.info(f"Created rating for message {req.message_id} by user {user_id}")
        
        return {"success": True, "message": "Rating saved"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in rate_ai_response: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save rating",
        )


# ---------------------------------------------------
# POST /ticket/{ticket_id}/escalate → Request human support
# ---------------------------------------------------
@app.post("/ticket/{ticket_id}/escalate")
def escalate_to_human(
    ticket_id: str,
    req: EscalateRequest,
    current_user: dict = Depends(get_current_customer),
):
    """Request human support for a ticket."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        user_id = current_user["id"]
        
        # Verify ticket exists and belongs to user
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found",
            )
        ticket = ticket_res.data[0]
        if ticket.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this ticket",
            )
        
        # Check if escalation already exists
        existing_escalation = (
            supabase.table("human_escalations")
            .select("*")
            .eq("ticket_id", ticket_id)
            .eq("user_id", user_id)
            .execute()
        )
        
        if existing_escalation.data:
            escalation = existing_escalation.data[0]
            if escalation["status"] != "resolved":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Human support already requested for this ticket",
                )
        
        # Create escalation
        supabase.table("human_escalations").insert(
            {
                "ticket_id": ticket_id,
                "user_id": user_id,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
        
        # Update ticket status
        supabase.table("tickets").update(
            {"status": "human_assigned", "updated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", ticket_id).execute()
        
        # Add system message
        escalation_message = "Customer requested to connect with a human agent."
        if req.reason:
            escalation_message += f" Reason: {req.reason}"
        
        supabase.table("messages").insert(
            {
                "ticket_id": ticket_id,
                "sender": "system",
                "message": escalation_message,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
        
        logger.info(f"Ticket {ticket_id} escalated to human by user {user_id}")
        
        return {
            "success": True,
            "message": "Human support requested. An agent will assist you shortly.",
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in escalate_to_human: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to escalate ticket",
        )


# ---------------------------------------------------
# GET /ticket/{ticket_id} → Fetch full thread
# ---------------------------------------------------
@app.get("/ticket/{ticket_id}")
def get_ticket_thread(
    ticket_id: str, current_user: dict = Depends(get_current_user)
):
    """Fetch a ticket and its full message thread ordered by time."""
    try:
        if supabase is None:
            return {"error": "Supabase is not configured. Please set SUPABASE_URL and SUPABASE_KEY in .env file"}
        
        ticket = (
            supabase.table("tickets").select("*").eq("id", ticket_id).limit(1).execute()
        )
        if not ticket.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found",
            )
        
        ticket_data = ticket.data[0]
        user_id = current_user["id"]
        user_role = current_user["role"]
        
        # Verify access: customers can only see their tickets, admins can see all
        if user_role == "customer" and ticket_data.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this ticket",
            )
        
        messages = (
            supabase.table("messages")
            .select("*")
            .eq("ticket_id", ticket_id)
            .order("created_at", desc=False)
            .execute()
        )
        
        # Get ratings for AI messages
        ratings = (
            supabase.table("ratings")
            .select("*")
            .eq("ticket_id", ticket_id)
            .eq("user_id", user_id)
            .execute()
        )
        ratings_map = {r["message_id"]: r["rating"] for r in ratings.data}
        
        # Attach ratings to messages
        messages_with_ratings = messages.data.copy()
        for msg in messages_with_ratings:
            msg["user_rating"] = ratings_map.get(msg["id"])
        
        return {
            "ticket": ticket_data,
            "messages": messages_with_ratings,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_ticket_thread: {e}", exc_info=True)
        raise


# ---------------------------------------------------
# GET /stats → Ticket summary
# ---------------------------------------------------
@app.get("/stats")
def get_stats():
    """Fetch ticket metrics and a sample from the `ticket_summary` view."""
    try:
        total = supabase.table("tickets").select("id", count="exact").execute().count
        open_t = (
            supabase.table("tickets")
            .select("id", count="exact")
            .eq("status", "open")
            .execute()
            .count
        )
        closed_t = total - open_t

        summary = (
            supabase.table("ticket_summary")
            .select(
                "ticket_id, context, subject, status, total_messages, avg_confidence"
            )
            .limit(5)
            .execute()
        )

        return {
            "total_tickets": total,
            "open_tickets": open_t,
            "closed_tickets": closed_t,
            "sample_summary": summary.data,
        }

    except Exception as e:
        logger.error(f"Error in get_stats: {e}", exc_info=True)
        raise


# ---------------------------------------------------
# ADMIN ENDPOINTS
# ---------------------------------------------------
@app.get("/admin/tickets")
def admin_get_all_tickets(
    search: str = Query(default=None, description="Search in subject and message content"),
    status: str = Query(default=None, description="Filter by status (open, human_assigned, closed)"),
    context: str = Query(default=None, description="Filter by context/brand"),
    assigned_to: str = Query(default=None, description="Filter by assigned agent email"),
    date_from: str = Query(default=None, description="Filter from date (ISO format: YYYY-MM-DD)"),
    date_to: str = Query(default=None, description="Filter to date (ISO format: YYYY-MM-DD)"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=10, ge=1, le=100, description="Number of items per page"),
    current_admin: dict = Depends(get_current_admin)
):
    """
    List all tickets with advanced search, filter, and pagination options.
    
    Supports:
    - Full-text search in subject and message content
    - Filter by status, context, assigned agent, date range
    - Pagination with page and page_size parameters
    """
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        query = supabase.table("tickets").select("*", count="exact")
        
        # Exclude deleted tickets by default
        query = query.eq("is_deleted", False)
        
        # Apply filters
        if status:
            query = query.eq("status", status)
        if context:
            query = query.eq("context", context)
        if assigned_to:
            query = query.eq("assigned_to", assigned_to)
        if date_from:
            query = query.gte("created_at", f"{date_from}T00:00:00Z")
        if date_to:
            query = query.lte("created_at", f"{date_to}T23:59:59Z")
        
        # Get total count before pagination (for search we'll need to handle differently)
        base_res = query.order("updated_at", desc=True).execute()
        all_tickets = base_res.data
        
        # If search is provided, filter by subject and message content
        if search:
            filtered_tickets = []
            search_lower = search.lower()
            for ticket in all_tickets:
                # Check if search matches subject
                if search_lower in ticket.get("subject", "").lower():
                    filtered_tickets.append(ticket)
                    continue
                
                # Check if search matches any message in the ticket
                messages_res = (
                    supabase.table("messages")
                    .select("message")
                    .eq("ticket_id", ticket["id"])
                    .execute()
                )
                for msg in messages_res.data:
                    if search_lower in msg.get("message", "").lower():
                        filtered_tickets.append(ticket)
                        break
            
            all_tickets = filtered_tickets
        
        # Calculate pagination
        total_count = len(all_tickets)
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
        skip = (page - 1) * page_size
        tickets = all_tickets[skip:skip + page_size]
        
        return {
            "tickets": tickets,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in admin_get_all_tickets: {e}", exc_info=True)
        raise


@app.get("/admin/tickets/assigned")
def get_assigned_tickets(
    search: str = Query(default=None, description="Search in subject and message content"),
    status: str = Query(default=None, description="Filter by status (open, human_assigned, closed)"),
    context: str = Query(default=None, description="Filter by context/brand"),
    date_from: str = Query(default=None, description="Filter from date (ISO format: YYYY-MM-DD)"),
    date_to: str = Query(default=None, description="Filter to date (ISO format: YYYY-MM-DD)"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=10, ge=1, le=100, description="Number of items per page"),
    current_admin: dict = Depends(get_current_admin)
):
    """
    Get tickets assigned to the current admin with search, filter, and pagination options.
    
    Supports:
    - Full-text search in subject and message content
    - Filter by status, context, date range
    - Pagination with page and page_size parameters
    """
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        admin_email = current_admin["email"]
        query = supabase.table("tickets").select("*", count="exact").eq("assigned_to", admin_email)
        
        # Exclude deleted tickets by default
        query = query.eq("is_deleted", False)
        
        # Apply filters
        if status:
            query = query.eq("status", status)
        if context:
            query = query.eq("context", context)
        if date_from:
            query = query.gte("created_at", f"{date_from}T00:00:00Z")
        if date_to:
            query = query.lte("created_at", f"{date_to}T23:59:59Z")
        
        res = query.order("updated_at", desc=True).execute()
        all_tickets = res.data
        
        # If search is provided, filter by subject and message content
        if search:
            filtered_tickets = []
            search_lower = search.lower()
            for ticket in all_tickets:
                # Check if search matches subject
                if search_lower in ticket.get("subject", "").lower():
                    filtered_tickets.append(ticket)
                    continue
                
                # Check if search matches any message in the ticket
                messages_res = (
                    supabase.table("messages")
                    .select("message")
                    .eq("ticket_id", ticket["id"])
                    .execute()
                )
                for msg in messages_res.data:
                    if search_lower in msg.get("message", "").lower():
                        filtered_tickets.append(ticket)
                        break
            
            all_tickets = filtered_tickets
        
        # Calculate pagination
        total_count = len(all_tickets)
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
        skip = (page - 1) * page_size
        tickets = all_tickets[skip:skip + page_size]
        
        return {
            "tickets": tickets,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_assigned_tickets: {e}", exc_info=True)
        raise


@app.get("/customer/tickets")
def get_customer_tickets(
    search: str = Query(default=None, description="Search in subject and message content"),
    status: str = Query(default=None, description="Filter by status (open, human_assigned, closed)"),
    context: str = Query(default=None, description="Filter by context/brand"),
    date_from: str = Query(default=None, description="Filter from date (ISO format: YYYY-MM-DD)"),
    date_to: str = Query(default=None, description="Filter to date (ISO format: YYYY-MM-DD)"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=10, ge=1, le=100, description="Number of items per page"),
    current_user: dict = Depends(get_current_customer)
):
    """
    Get all tickets for the current customer with search, filter, and pagination options.
    
    Supports:
    - Full-text search in subject and message content
    - Filter by status, context, date range
    - Pagination with page and page_size parameters
    """
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        user_id = current_user["id"]
        query = supabase.table("tickets").select("*", count="exact").eq("user_id", user_id)
        
        # Exclude deleted tickets by default
        query = query.eq("is_deleted", False)
        
        # Apply filters
        if status:
            query = query.eq("status", status)
        if context:
            query = query.eq("context", context)
        if date_from:
            query = query.gte("created_at", f"{date_from}T00:00:00Z")
        if date_to:
            query = query.lte("created_at", f"{date_to}T23:59:59Z")
        
        res = query.order("updated_at", desc=True).execute()
        all_tickets = res.data
        
        # If search is provided, filter by subject and message content
        if search:
            filtered_tickets = []
            search_lower = search.lower()
            for ticket in all_tickets:
                # Check if search matches subject
                if search_lower in ticket.get("subject", "").lower():
                    filtered_tickets.append(ticket)
                    continue
                
                # Check if search matches any message in the ticket
                messages_res = (
                    supabase.table("messages")
                    .select("message")
                    .eq("ticket_id", ticket["id"])
                    .execute()
                )
                for msg in messages_res.data:
                    if search_lower in msg.get("message", "").lower():
                        filtered_tickets.append(ticket)
                        break
            
            all_tickets = filtered_tickets
        
        # Calculate pagination
        total_count = len(all_tickets)
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
        skip = (page - 1) * page_size
        tickets = all_tickets[skip:skip + page_size]
        
        return {
            "tickets": tickets,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_customer_tickets: {e}", exc_info=True)
        raise


# ---------------------------
# SLA & PRIORITY ENDPOINTS
# ---------------------------
@app.post("/admin/slas")
def create_sla_definition(
    req: SLADefinitionRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """Create a new SLA definition."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Validate priority
        if req.priority not in ['low', 'medium', 'high', 'urgent']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Priority must be one of: low, medium, high, urgent"
            )
        
        # Validate times
        if req.response_time_minutes <= 0 or req.resolution_time_minutes <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Response and resolution times must be positive"
            )
        
        sla_data = {
            "name": req.name,
            "description": req.description,
            "priority": req.priority,
            "response_time_minutes": req.response_time_minutes,
            "resolution_time_minutes": req.resolution_time_minutes,
            "business_hours_only": req.business_hours_only,
            "business_hours_start": req.business_hours_start,
            "business_hours_end": req.business_hours_end,
            "business_days": req.business_days or [1, 2, 3, 4, 5],
            "created_by": current_admin["id"]
        }
        
        result = (
            supabase.table("sla_definitions")
            .insert(sla_data)
            .execute()
        )
        
        logger.info(f"Created SLA definition: {result.data[0]['id']} by {current_admin['email']}")
        return {"sla": result.data[0]}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_sla_definition: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create SLA definition",
        )


@app.get("/admin/slas")
def list_sla_definitions(
    priority: str = Query(default=None, description="Filter by priority"),
    is_active: bool = Query(default=True, description="Filter by active status"),
    current_admin: dict = Depends(get_current_admin)
):
    """List all SLA definitions."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        query = supabase.table("sla_definitions").select("*")
        
        if priority:
            query = query.eq("priority", priority)
        if is_active is not None:
            query = query.eq("is_active", is_active)
        
        result = query.order("created_at", desc=True).execute()
        return {"slas": result.data}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_sla_definitions: {e}", exc_info=True)
        raise


@app.post("/ticket/{ticket_id}/priority")
def update_ticket_priority(
    ticket_id: str,
    req: UpdatePriorityRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """Update ticket priority."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Validate priority
        if req.priority not in ['low', 'medium', 'high', 'urgent']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Priority must be one of: low, medium, high, urgent"
            )
        
        # Verify ticket exists
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found",
            )
        
        old_priority = ticket_res.data[0].get("priority", "medium")
        
        # Auto-assign SLA based on new priority
        sla_id = None
        try:
            sla_res = (
                supabase.table("sla_definitions")
                .select("id")
                .eq("priority", req.priority)
                .eq("is_active", True)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if sla_res.data:
                sla_id = sla_res.data[0]["id"]
        except Exception as e:
            logger.warning(f"Could not auto-assign SLA for priority {req.priority}: {e}")
        
        # Update priority and SLA
        update_dict = {
            "priority": req.priority,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        if sla_id:
            update_dict["sla_id"] = sla_id
        
        result = (
            supabase.table("tickets")
            .update(update_dict)
            .eq("id", ticket_id)
            .execute()
        )
        
        # Log activity
        try:
            supabase.table("ticket_activities").insert({
                "ticket_id": ticket_id,
                "user_id": current_admin["id"],
                "action_type": "priority_changed",
                "old_value": old_priority,
                "new_value": req.priority,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            logger.warning(f"Could not log activity: {e}")  # Activity log is optional
        
        logger.info(f"Updated ticket {ticket_id} priority from {old_priority} to {req.priority}")
        return {"ticket": result.data[0]}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_ticket_priority: {e}", exc_info=True)
        raise


@app.get("/ticket/{ticket_id}/sla-status")
def get_ticket_sla_status(
    ticket_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get SLA status for a ticket."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Get ticket
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found",
            )
        
        ticket = ticket_res.data[0]
        user_id = current_user["id"]
        user_role = current_user["role"]
        
        # Verify access
        if user_role == "customer" and ticket.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this ticket",
            )
        
        # Get SLA definition
        sla_id = ticket.get("sla_id")
        priority = ticket.get("priority", "medium")
        
        sla_definition = None
        if sla_id:
            sla_res = (
                supabase.table("sla_definitions")
                .select("*")
                .eq("id", sla_id)
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            if sla_res.data:
                sla_definition = sla_res.data[0]
        
        # If no SLA assigned, try to find by priority
        if not sla_definition:
            sla_res = (
                supabase.table("sla_definitions")
                .select("*")
                .eq("priority", priority)
                .eq("is_active", True)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if sla_res.data:
                sla_definition = sla_res.data[0]
        
        if not sla_definition:
            return {
                "sla_defined": False,
                "message": "No SLA definition found for this ticket priority"
            }
        
        # Calculate SLA times
        # Handle datetime parsing with timezone (Supabase may return datetime objects or strings)
        created_at_val = ticket["created_at"]
        if isinstance(created_at_val, datetime):
            created_at = created_at_val
        elif isinstance(created_at_val, str):
            if created_at_val.endswith('Z'):
                created_at_val = created_at_val.replace('Z', '+00:00')
            elif '+' not in created_at_val and 'Z' not in created_at_val:
                created_at_val = created_at_val + '+00:00'
            created_at = datetime.fromisoformat(created_at_val)
        else:
            # Fallback: try to parse as ISO format
            created_at_str = str(created_at_val)
            if created_at_str.endswith('Z'):
                created_at_str = created_at_str.replace('Z', '+00:00')
            elif '+' not in created_at_str and 'Z' not in created_at_str:
                created_at_str = created_at_str + '+00:00'
            created_at = datetime.fromisoformat(created_at_str)
        # Ensure created_at is timezone-aware
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        
        response_time_minutes = sla_definition["response_time_minutes"]
        resolution_time_minutes = sla_definition["resolution_time_minutes"]
        
        # Calculate expected times
        first_response_time = created_at + timedelta(minutes=response_time_minutes)
        resolution_time = created_at + timedelta(minutes=resolution_time_minutes)
        
        # Check violations
        first_response_at = ticket.get("first_response_at")
        resolved_at = ticket.get("resolved_at")
        
        response_violation = None
        resolution_violation = None
        
        if first_response_at:
            if isinstance(first_response_at, datetime):
                first_response_dt = first_response_at
            elif isinstance(first_response_at, str):
                first_response_str = first_response_at
                if first_response_str.endswith('Z'):
                    first_response_str = first_response_str.replace('Z', '+00:00')
                elif '+' not in first_response_str and 'Z' not in first_response_str:
                    first_response_str = first_response_str + '+00:00'
                first_response_dt = datetime.fromisoformat(first_response_str)
            else:
                first_response_str = str(first_response_at)
                if first_response_str.endswith('Z'):
                    first_response_str = first_response_str.replace('Z', '+00:00')
                elif '+' not in first_response_str and 'Z' not in first_response_str:
                    first_response_str = first_response_str + '+00:00'
                first_response_dt = datetime.fromisoformat(first_response_str)
            # Ensure first_response_dt is timezone-aware
            if first_response_dt.tzinfo is None:
                first_response_dt = first_response_dt.replace(tzinfo=timezone.utc)
            if first_response_dt > first_response_time:
                response_violation = {
                    "violated": True,
                    "expected_time": first_response_time.isoformat(),
                    "actual_time": first_response_at,
                    "violation_minutes": int((first_response_dt - first_response_time).total_seconds() / 60)
                }
        else:
            if now > first_response_time:
                response_violation = {
                    "violated": True,
                    "expected_time": first_response_time.isoformat(),
                    "actual_time": None,
                    "violation_minutes": int((now - first_response_time).total_seconds() / 60)
                }
        
        if resolved_at:
            if isinstance(resolved_at, datetime):
                resolved_dt = resolved_at
            elif isinstance(resolved_at, str):
                resolved_str = resolved_at
                if resolved_str.endswith('Z'):
                    resolved_str = resolved_str.replace('Z', '+00:00')
                elif '+' not in resolved_str and 'Z' not in resolved_str:
                    resolved_str = resolved_str + '+00:00'
                resolved_dt = datetime.fromisoformat(resolved_str)
            else:
                resolved_str = str(resolved_at)
                if resolved_str.endswith('Z'):
                    resolved_str = resolved_str.replace('Z', '+00:00')
                elif '+' not in resolved_str and 'Z' not in resolved_str:
                    resolved_str = resolved_str + '+00:00'
                resolved_dt = datetime.fromisoformat(resolved_str)
            # Ensure resolved_dt is timezone-aware
            if resolved_dt.tzinfo is None:
                resolved_dt = resolved_dt.replace(tzinfo=timezone.utc)
            if resolved_dt > resolution_time:
                resolution_violation = {
                    "violated": True,
                    "expected_time": resolution_time.isoformat(),
                    "actual_time": resolved_at,
                    "violation_minutes": int((resolved_dt - resolution_time).total_seconds() / 60)
                }
        else:
            if now > resolution_time:
                resolution_violation = {
                    "violated": True,
                    "expected_time": resolution_time.isoformat(),
                    "actual_time": None,
                    "violation_minutes": int((now - resolution_time).total_seconds() / 60)
                }
        
        return {
            "sla_defined": True,
            "sla": {
                "id": sla_definition["id"],
                "name": sla_definition["name"],
                "priority": sla_definition["priority"],
                "response_time_minutes": response_time_minutes,
                "resolution_time_minutes": resolution_time_minutes
            },
            "response_time": {
                "expected": first_response_time.isoformat(),
                "actual": first_response_at,
                "violation": response_violation
            },
            "resolution_time": {
                "expected": resolution_time.isoformat(),
                "actual": resolved_at,
                "violation": resolution_violation
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_ticket_sla_status: {e}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get SLA status: {str(e)}",
        )


@app.post("/ticket/{ticket_id}/time-entry")
def create_time_entry(
    ticket_id: str,
    req: TimeEntryRequest,
    current_user: dict = Depends(get_current_user)
):
    """Log time spent on a ticket."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Validate entry type
        if req.entry_type not in ['work', 'waiting', 'research', 'communication', 'other']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Entry type must be one of: work, waiting, research, communication, other"
            )
        
        # Validate duration
        if req.duration_minutes <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duration must be greater than 0"
            )
        
        # Verify ticket exists
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found",
            )
        
        ticket = ticket_res.data[0]
        user_id = current_user["id"]
        user_role = current_user["role"]
        
        # Verify access
        if user_role == "customer" and ticket.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this ticket",
            )
        
        # Create time entry
        time_entry = {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "duration_minutes": req.duration_minutes,
            "description": req.description,
            "entry_type": req.entry_type,
            "billable": req.billable,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = (
            supabase.table("time_entries")
            .insert(time_entry)
            .execute()
        )
        
        logger.info(f"Created time entry: {req.duration_minutes} minutes for ticket {ticket_id}")
        return {"time_entry": result.data[0]}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_time_entry: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create time entry",
        )


@app.get("/ticket/{ticket_id}/time-entries")
def get_ticket_time_entries(
    ticket_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all time entries for a ticket."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify ticket exists and access
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found",
            )
        
        ticket = ticket_res.data[0]
        user_id = current_user["id"]
        user_role = current_user["role"]
        
        # Verify access
        if user_role == "customer" and ticket.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this ticket",
            )
        
        # Get time entries
        result = (
            supabase.table("time_entries")
            .select("*")
            .eq("ticket_id", ticket_id)
            .order("created_at", desc=True)
            .execute()
        )
        
        # Calculate totals
        total_minutes = sum(entry.get("duration_minutes", 0) for entry in result.data)
        billable_minutes = sum(
            entry.get("duration_minutes", 0) 
            for entry in result.data 
            if entry.get("billable", False)
        )
        
        return {
            "time_entries": result.data,
            "totals": {
                "total_minutes": total_minutes,
                "total_hours": round(total_minutes / 60, 2),
                "billable_minutes": billable_minutes,
                "billable_hours": round(billable_minutes / 60, 2)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_ticket_time_entries: {e}", exc_info=True)
        raise


@app.post("/ticket/{ticket_id}/admin/reply")
def admin_reply_to_ticket(
    ticket_id: str,
    req: AdminReplyRequest,
    current_admin: dict = Depends(get_current_admin),
):
    """Admin reply to a ticket."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify ticket exists
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found",
            )
        
        ticket = ticket_res.data[0]
        
        # Store admin message
        supabase.table("messages").insert(
            {
                "ticket_id": ticket_id,
                "sender": "admin",
                "message": req.message,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
        
        # Update ticket timestamps and status
        now = datetime.utcnow().isoformat()
        update_data = {
            "last_response_at": now,
            "updated_at": now
        }
        
        # Check if this is first response
        if not ticket.get("first_response_at"):
            update_data["first_response_at"] = now
        
        # Update ticket status if needed
        if ticket.get("status") == "open":
            update_data["status"] = "human_assigned"
            update_data["assigned_to"] = current_admin["email"]
        
        result = supabase.table("tickets").update(update_data).eq("id", ticket_id).execute()
        
        logger.info(f"Admin {current_admin['email']} replied to ticket {ticket_id}")
        
        return {"success": True, "message": "Reply sent", "ticket": result.data[0] if result.data else None}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in admin_reply_to_ticket: {e}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send reply: {str(e)}",
        )


@app.post("/admin/ticket/{ticket_id}/assign-admin")
def assign_ticket_to_admin(
    ticket_id: str,
    req: AssignAdminRequest,
    current_admin: dict = Depends(get_current_admin),
):
    """Assign a ticket to another admin."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify ticket exists
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found",
            )
        
        # Verify admin exists
        admin_res = (
            supabase.table("users")
            .select("*")
            .eq("email", req.admin_email.lower())
            .eq("role", "admin")
            .limit(1)
            .execute()
        )
        if not admin_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin not found",
            )
        
        # Update ticket
        supabase.table("tickets").update(
            {
                "assigned_to": req.admin_email.lower(),
                "status": "human_assigned",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", ticket_id).execute()
        
        # Add system message
        supabase.table("messages").insert(
            {
                "ticket_id": ticket_id,
                "sender": "system",
                "message": f"Ticket assigned to {req.admin_email} by {current_admin['email']}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()
        
        logger.info(f"Ticket {ticket_id} assigned to {req.admin_email} by {current_admin['email']}")
        
        return {
            "success": True,
            "message": f"Ticket assigned to {req.admin_email}",
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in assign_ticket_to_admin: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign ticket",
        )


@app.post("/admin/ticket/{ticket_id}/assign")
def assign_agent(
    ticket_id: str, agent_name: str, _: None = Depends(require_admin)
):
    """Assign a human agent and move ticket to `human_assigned` (legacy endpoint)."""
    try:
        if supabase is None:
            return {"error": "Supabase is not configured. Please set SUPABASE_URL and SUPABASE_KEY in .env file"}
        
        supabase.table("tickets").update(
            {"assigned_to": agent_name, "status": "human_assigned"}
        ).eq("id", ticket_id).execute()
        return {
            "success": True,
            "message": f"Ticket {ticket_id} assigned to {agent_name}",
        }
    except Exception as e:
        logger.error(f"Error in assign_agent: {e}", exc_info=True)
        raise


@app.post("/admin/ticket/{ticket_id}/close")
def close_ticket(
    ticket_id: str, current_admin: dict = Depends(get_current_admin)
):
    """Mark the ticket `closed`."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        supabase.table("tickets").update(
            {"status": "closed", "updated_at": datetime.utcnow().isoformat()}
        ).eq("id", ticket_id).execute()
        
        logger.info(f"Ticket {ticket_id} closed by admin {current_admin['email']}")
        
        return {"success": True, "message": f"Ticket {ticket_id} closed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in close_ticket: {e}", exc_info=True)
        raise


@app.post("/admin/tickets/delete")
def delete_tickets(
    req: DeleteTicketsRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """Soft delete multiple tickets (move to trash). Only closed tickets can be deleted."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        if not req.ticket_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No ticket IDs provided"
            )
        
        # Verify all tickets exist and are closed
        tickets_res = (
            supabase.table("tickets")
            .select("id, status, is_deleted")
            .in_("id", req.ticket_ids)
            .execute()
        )
        
        if not tickets_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No tickets found"
            )
        
        found_ids = {t["id"] for t in tickets_res.data}
        not_found = set(req.ticket_ids) - found_ids
        if not_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tickets not found: {', '.join(not_found)}"
            )
        
        # Check if any tickets are not closed
        not_closed = [t for t in tickets_res.data if t.get("status") != "closed"]
        if not_closed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete tickets that are not closed. Found {len(not_closed)} open/assigned ticket(s)."
            )
        
        # Check if any tickets are already deleted
        already_deleted = [t for t in tickets_res.data if t.get("is_deleted", False)]
        if already_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Some tickets are already deleted: {len(already_deleted)} ticket(s)"
            )
        
        # Soft delete tickets
        now = datetime.utcnow().isoformat()
        result = (
            supabase.table("tickets")
            .update({
                "is_deleted": True,
                "deleted_at": now,
                "updated_at": now
            })
            .in_("id", req.ticket_ids)
            .execute()
        )
        
        logger.info(f"Deleted {len(req.ticket_ids)} tickets by admin {current_admin['email']}")
        
        return {
            "success": True,
            "message": f"Successfully deleted {len(req.ticket_ids)} ticket(s)",
            "deleted_count": len(req.ticket_ids)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_tickets: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete tickets",
        )


@app.get("/admin/tickets/trash")
def get_trash_tickets(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=10, ge=1, le=100, description="Number of items per page"),
    current_admin: dict = Depends(get_current_admin)
):
    """Get all deleted tickets (trash)."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        query = (
            supabase.table("tickets")
            .select("*", count="exact")
            .eq("is_deleted", True)
            .order("deleted_at", desc=True)
        )
        
        # Calculate pagination
        total_res = query.execute()
        total_count = total_res.count if hasattr(total_res, 'count') else len(total_res.data)
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
        skip = (page - 1) * page_size
        
        tickets_res = query.range(skip, skip + page_size - 1).execute()
        tickets = tickets_res.data if tickets_res.data else []
        
        # Calculate days until permanent deletion (30 days)
        now = datetime.now(timezone.utc)
        for ticket in tickets:
            deleted_at_str = ticket.get("deleted_at")
            if deleted_at_str:
                if isinstance(deleted_at_str, str):
                    if deleted_at_str.endswith('Z'):
                        deleted_at_str = deleted_at_str.replace('Z', '+00:00')
                    elif '+' not in deleted_at_str and 'Z' not in deleted_at_str:
                        deleted_at_str = deleted_at_str + '+00:00'
                    deleted_at = datetime.fromisoformat(deleted_at_str)
                else:
                    deleted_at = deleted_at_str
                
                if deleted_at.tzinfo is None:
                    deleted_at = deleted_at.replace(tzinfo=timezone.utc)
                
                days_until_deletion = 30 - (now - deleted_at).days
                ticket["days_until_permanent_deletion"] = max(0, days_until_deletion)
        
        return {
            "tickets": tickets,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_trash_tickets: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get trash tickets",
        )


@app.post("/admin/tickets/restore")
def restore_tickets(
    req: RestoreTicketsRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """Restore tickets from trash."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        if not req.ticket_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No ticket IDs provided"
            )
        
        # Verify all tickets exist and are deleted
        tickets_res = (
            supabase.table("tickets")
            .select("id, is_deleted")
            .in_("id", req.ticket_ids)
            .execute()
        )
        
        if not tickets_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No tickets found"
            )
        
        found_ids = {t["id"] for t in tickets_res.data}
        not_found = set(req.ticket_ids) - found_ids
        if not_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tickets not found: {', '.join(not_found)}"
            )
        
        # Check if any tickets are not deleted
        not_deleted = [t for t in tickets_res.data if not t.get("is_deleted", False)]
        if not_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Some tickets are not in trash: {len(not_deleted)} ticket(s)"
            )
        
        # Restore tickets
        now = datetime.utcnow().isoformat()
        result = (
            supabase.table("tickets")
            .update({
                "is_deleted": False,
                "deleted_at": None,
                "updated_at": now
            })
            .in_("id", req.ticket_ids)
            .execute()
        )
        
        logger.info(f"Restored {len(req.ticket_ids)} tickets by admin {current_admin['email']}")
        
        return {
            "success": True,
            "message": f"Successfully restored {len(req.ticket_ids)} ticket(s)",
            "restored_count": len(req.ticket_ids)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in restore_tickets: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restore tickets",
        )


@app.delete("/admin/tickets/trash")
def permanently_delete_tickets(
    ticket_ids: list[str] = Query(..., description="List of ticket IDs to permanently delete"),
    current_admin: dict = Depends(get_current_admin)
):
    """Permanently delete tickets from trash. This action cannot be undone."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        if not ticket_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No ticket IDs provided"
            )
        
        # Verify all tickets exist and are deleted
        tickets_res = (
            supabase.table("tickets")
            .select("id, is_deleted")
            .in_("id", ticket_ids)
            .execute()
        )
        
        if not tickets_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No tickets found"
            )
        
        found_ids = {t["id"] for t in tickets_res.data}
        not_found = set(ticket_ids) - found_ids
        if not_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tickets not found: {', '.join(not_found)}"
            )
        
        # Check if any tickets are not deleted
        not_deleted = [t for t in tickets_res.data if not t.get("is_deleted", False)]
        if not_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot permanently delete tickets that are not in trash: {len(not_deleted)} ticket(s)"
            )
        
        # Permanently delete tickets (cascade will handle related records)
        result = (
            supabase.table("tickets")
            .delete()
            .in_("id", ticket_ids)
            .execute()
        )
        
        logger.info(f"Permanently deleted {len(ticket_ids)} tickets by admin {current_admin['email']}")
        
        return {
            "success": True,
            "message": f"Successfully permanently deleted {len(ticket_ids)} ticket(s)",
            "deleted_count": len(ticket_ids)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in permanently_delete_tickets: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to permanently delete tickets",
        )


# ---------------------------
# 📎 ATTACHMENT ENDPOINTS
# ---------------------------

@app.post("/ticket/{ticket_id}/attachments")
def upload_attachment(
    ticket_id: str,
    file: UploadFile = File(...),
    message_id: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    """Upload an attachment to a ticket."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify ticket exists and user has access
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found",
            )
        
        ticket = ticket_res.data[0]
        user_id = current_user["id"]
        user_role = current_user["role"]
        
        # Verify access (customer can only upload to their own tickets)
        if user_role == "customer" and ticket.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this ticket",
            )
        
        # Verify message_id if provided
        if message_id:
            message_res = (
                supabase.table("messages")
                .select("id")
                .eq("id", message_id)
                .eq("ticket_id", ticket_id)
                .limit(1)
                .execute()
            )
            if not message_res.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Message not found",
                )
        
        # Read file content
        file_content = file.file.read()
        file_name = file.filename
        mime_type = file.content_type or "application/octet-stream"
        
        # Upload file
        attachment = upload_file(
            file_content=file_content,
            file_name=file_name,
            mime_type=mime_type,
            ticket_id=ticket_id,
            user_id=user_id,
            message_id=message_id,
        )
        
        logger.info(f"Attachment uploaded: {attachment['id']} by {current_user['email']}")
        
        return {
            "success": True,
            "attachment": attachment,
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error in upload_attachment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload attachment",
        )


@app.get("/ticket/{ticket_id}/attachments")
def list_ticket_attachments(
    ticket_id: str,
    message_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """List all attachments for a ticket."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify ticket exists and user has access
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found",
            )
        
        ticket = ticket_res.data[0]
        user_id = current_user["id"]
        user_role = current_user["role"]
        
        # Verify access (customer can only view their own tickets)
        if user_role == "customer" and ticket.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this ticket",
            )
        
        # List attachments
        attachments = list_attachments(ticket_id=ticket_id, message_id=message_id)
        
        return {
            "attachments": attachments,
            "count": len(attachments),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_ticket_attachments: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list attachments",
        )


@app.get("/attachment/{attachment_id}")
def download_attachment(
    attachment_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Download an attachment."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Get attachment record
        attachment_res = (
            supabase.table("attachments")
            .select("*")
            .eq("id", attachment_id)
            .limit(1)
            .execute()
        )
        if not attachment_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attachment not found",
            )
        
        attachment = attachment_res.data[0]
        ticket_id = attachment["ticket_id"]
        
        # Verify ticket exists and user has access
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found",
            )
        
        ticket = ticket_res.data[0]
        user_id = current_user["id"]
        user_role = current_user["role"]
        
        # Verify access (customer can only download from their own tickets)
        if user_role == "customer" and ticket.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this attachment",
            )
        
        # Download file
        file_content, attachment_meta = download_file(attachment_id)
        
        # Return file as streaming response
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type=attachment_meta["mime_type"],
            headers={
                "Content-Disposition": f'attachment; filename="{attachment_meta["file_name"]}"',
                "Content-Length": str(attachment_meta["file_size"]),
            },
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error in download_attachment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download attachment",
        )


@app.delete("/attachment/{attachment_id}")
def delete_attachment(
    attachment_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete an attachment."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Get attachment record
        attachment_res = (
            supabase.table("attachments")
            .select("*")
            .eq("id", attachment_id)
            .limit(1)
            .execute()
        )
        if not attachment_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attachment not found",
            )
        
        attachment = attachment_res.data[0]
        ticket_id = attachment["ticket_id"]
        uploaded_by = attachment["uploaded_by"]
        user_id = current_user["id"]
        user_role = current_user["role"]
        
        # Verify access:
        # - Customer can only delete their own uploads
        # - Admin can delete any attachment
        if user_role == "customer" and uploaded_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own attachments",
            )
        
        # Verify ticket exists (for additional validation)
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found",
            )
        
        # Delete file
        delete_file(attachment_id)
        
        logger.info(f"Attachment deleted: {attachment_id} by {current_user['email']}")
        
        return {
            "success": True,
            "message": "Attachment deleted successfully",
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error in delete_attachment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete attachment",
        )


# ---------------------------
# 📧 EMAIL ENDPOINTS
# ---------------------------

@app.post("/admin/email-accounts")
def create_email_account(
    req: EmailAccountRequest,
    current_admin: dict = Depends(get_current_admin),
):
    """Create or update email account configuration."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Validate provider
        valid_providers = ["smtp", "sendgrid", "ses", "mailgun", "other"]
        if req.provider not in valid_providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Provider must be one of: {', '.join(valid_providers)}"
            )
        
        # If setting as default, unset other defaults
        if req.is_default:
            supabase.table("email_accounts").update({"is_default": False}).execute()
        
        # Encrypt sensitive data (placeholder - implement proper encryption)
        smtp_password_encrypted = req.smtp_password if req.smtp_password else None
        api_key_encrypted = req.api_key if req.api_key else None
        credentials_encrypted = json.dumps(req.credentials) if req.credentials else None
        
        account_data = {
            "email": req.email.lower(),
            "display_name": req.display_name,
            "provider": req.provider,
            "smtp_host": req.smtp_host,
            "smtp_port": req.smtp_port,
            "smtp_username": req.smtp_username,
            "smtp_password_encrypted": smtp_password_encrypted,
            "api_key_encrypted": api_key_encrypted,
            "credentials_encrypted": credentials_encrypted,
            "is_active": req.is_active,
            "is_default": req.is_default,
            "imap_host": req.imap_host,
            "imap_port": req.imap_port,
            "imap_enabled": req.imap_enabled,
            "created_by": current_admin["id"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Check if account exists
        existing = (
            supabase.table("email_accounts")
            .select("id")
            .eq("email", req.email.lower())
            .execute()
        )
        
        if existing.data:
            # Update existing
            result = (
                supabase.table("email_accounts")
                .update(account_data)
                .eq("id", existing.data[0]["id"])
                .execute()
            )
            logger.info(f"Updated email account: {req.email} by {current_admin['email']}")
        else:
            # Create new
            account_data["created_at"] = datetime.utcnow().isoformat()
            result = (
                supabase.table("email_accounts")
                .insert(account_data)
                .execute()
            )
            logger.info(f"Created email account: {req.email} by {current_admin['email']}")
        
        return {"success": True, "account": result.data[0] if result.data else None}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_email_account: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create email account",
        )


@app.get("/admin/email-accounts")
def list_email_accounts(
    current_admin: dict = Depends(get_current_admin),
):
    """List all email accounts."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        result = (
            supabase.table("email_accounts")
            .select("id, email, display_name, provider, is_active, is_default, imap_enabled, last_polled_at, created_at, updated_at")
            .order("created_at", desc=True)
            .execute()
        )
        
        return {"accounts": result.data if result.data else []}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_email_accounts: {e}", exc_info=True)
        raise


@app.post("/admin/email-accounts/{account_id}/test")
def test_email_account(
    account_id: str,
    current_admin: dict = Depends(get_current_admin),
):
    """Test email account connection."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        result = email_service.test_email_connection(account_id)
        
        if result.get("success"):
            return {"success": True, "message": result.get("message", "Connection successful")}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Connection failed")
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in test_email_account: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test email account",
        )


@app.post("/admin/email-accounts/{account_id}/test-imap")
def test_imap_connection(
    account_id: str,
    current_admin: dict = Depends(get_current_admin),
):
    """Test IMAP connection for an email account."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        result = email_service.test_imap_connection(account_id)
        
        if result.get("success"):
            return {"success": True, "message": result.get("message", "IMAP connection successful")}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "IMAP connection failed")
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in test_imap_connection: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test IMAP connection",
        )


@app.post("/admin/email-accounts/{account_id}/enable-polling")
def enable_email_polling(
    account_id: str,
    current_admin: dict = Depends(get_current_admin),
):
    """Enable IMAP polling for an email account."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify account exists
        account_res = (
            supabase.table("email_accounts")
            .select("id, email, is_active")
            .eq("id", account_id)
            .limit(1)
            .execute()
        )
        
        if not account_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email account not found"
            )
        
        account = account_res.data[0]
        
        if not account.get("is_active"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot enable polling for inactive account"
            )
        
        # Enable polling
        result = (
            supabase.table("email_accounts")
            .update({
                "imap_enabled": True,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
            .eq("id", account_id)
            .execute()
        )
        
        logger.info(f"Enabled IMAP polling for account {account.get('email')} by {current_admin['email']}")
        
        return {
            "success": True,
            "message": "Email polling enabled",
            "account": result.data[0] if result.data else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in enable_email_polling: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enable email polling",
        )


@app.post("/admin/email-accounts/{account_id}/disable-polling")
def disable_email_polling(
    account_id: str,
    current_admin: dict = Depends(get_current_admin),
):
    """Disable IMAP polling for an email account."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify account exists
        account_res = (
            supabase.table("email_accounts")
            .select("id, email")
            .eq("id", account_id)
            .limit(1)
            .execute()
        )
        
        if not account_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email account not found"
            )
        
        account = account_res.data[0]
        
        # Disable polling
        result = (
            supabase.table("email_accounts")
            .update({
                "imap_enabled": False,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
            .eq("id", account_id)
            .execute()
        )
        
        logger.info(f"Disabled IMAP polling for account {account.get('email')} by {current_admin['email']}")
        
        return {
            "success": True,
            "message": "Email polling disabled",
            "account": result.data[0] if result.data else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in disable_email_polling: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable email polling",
        )


@app.get("/admin/email-accounts/{account_id}/polling-status")
def get_polling_status(
    account_id: str,
    current_admin: dict = Depends(get_current_admin),
):
    """Get polling status for an email account."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        account_res = (
            supabase.table("email_accounts")
            .select("id, email, imap_enabled, is_active, last_polled_at, imap_host, imap_port")
            .eq("id", account_id)
            .limit(1)
            .execute()
        )
        
        if not account_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email account not found"
            )
        
        account = account_res.data[0]
        
        return {
            "success": True,
            "account_id": account_id,
            "email": account.get("email"),
            "imap_enabled": account.get("imap_enabled", False),
            "is_active": account.get("is_active", False),
            "last_polled_at": account.get("last_polled_at"),
            "imap_host": account.get("imap_host"),
            "imap_port": account.get("imap_port"),
            "can_poll": account.get("imap_enabled", False) and account.get("is_active", False)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_polling_status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get polling status",
        )


@app.post("/ticket/{ticket_id}/send-email")
def send_email_from_ticket(
    ticket_id: str,
    req: SendEmailRequest,
    current_user: dict = Depends(get_current_user),
):
    """Send email from a ticket."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify ticket exists and user has access
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found",
            )
        
        ticket = ticket_res.data[0]
        user_id = current_user["id"]
        user_role = current_user["role"]
        
        # Verify access
        if user_role == "customer" and ticket.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this ticket",
            )
        
        # Get email account
        account_id = req.account_id
        if not account_id:
            default_account = email_service.get_default_email_account()
            if not default_account:
                # Check if there are any accounts at all
                all_accounts = (
                    supabase.table("email_accounts")
                    .select("id, email, is_active, is_default")
                    .execute()
                )
                if not all_accounts.data:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No email account configured. Please set up an email account first via Admin Portal → Email Accounts."
                    )
                else:
                    # There are accounts but none are active/default
                    inactive_accounts = [acc for acc in all_accounts.data if not acc.get("is_active")]
                    no_default_accounts = [acc for acc in all_accounts.data if not acc.get("is_default")]
                    
                    error_msg = "No active email account found. "
                    if inactive_accounts:
                        error_msg += f"Found {len(inactive_accounts)} inactive account(s). "
                    if no_default_accounts and len(no_default_accounts) == len(all_accounts.data):
                        error_msg += "Please mark at least one account as 'Active' and 'Default' in Admin Portal → Email Accounts."
                    else:
                        error_msg += "Please activate an email account and set it as default."
                    
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=error_msg
                    )
            account_id = default_account["id"]
        
        # Send email
        result = email_service.send_email(
            account_id=account_id,
            to_emails=[email.lower() for email in req.to_emails],
            subject=req.subject,
            body_text=req.body_text,
            body_html=req.body_html,
            cc_emails=[email.lower() for email in req.cc_emails] if req.cc_emails else None,
            bcc_emails=[email.lower() for email in req.bcc_emails] if req.bcc_emails else None,
            reply_to=req.reply_to.lower() if req.reply_to else None,
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to send email")
            )
        
        # Save email message to database
        email_message_data = {
            "ticket_id": ticket_id,
            "email_account_id": account_id,
            "message_id": result.get("message_id", ""),
            "subject": req.subject,
            "body_text": req.body_text,
            "body_html": req.body_html,
            "from_email": current_user["email"],
            "to_email": [email.lower() for email in req.to_emails],
            "cc_email": [email.lower() for email in req.cc_emails] if req.cc_emails else [],
            "bcc_email": [email.lower() for email in req.bcc_emails] if req.bcc_emails else [],
            "status": "sent",
            "direction": "outbound",
            "has_attachments": False,
            "sent_at": datetime.utcnow().isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        email_result = supabase.table("email_messages").insert(email_message_data).execute()
        
        # Link to ticket thread
        if email_result.data:
            supabase.table("email_threads").insert({
                "ticket_id": ticket_id,
                "email_message_id": email_result.data[0]["id"],
                "thread_position": 1,  # TODO: Calculate proper position
                "created_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
        
        logger.info(f"Email sent from ticket {ticket_id} by {current_user['email']}")
        
        return {
            "success": True,
            "message": "Email sent successfully",
            "email_message": email_result.data[0] if email_result.data else None,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in send_email_from_ticket: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send email",
        )


@app.post("/webhooks/email")
async def receive_email_webhook(
    request: Request,
):
    """Receive incoming emails via webhook."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Get raw email body
        try:
            body = await request.body()
            raw_email = body.decode("utf-8")
        except Exception as e:
            # Try to get from JSON body
            try:
                json_body = await request.json()
                raw_email = json_body.get("raw_email") or json_body.get("body") or ""
            except:
                raw_email = ""
        
        if not raw_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Raw email content required"
            )
        
        parsed = email_service.parse_email(raw_email)
        if not parsed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to parse email"
            )
        
        # Spam filtering - check if email should be filtered
        from_email = parsed.get("from_email", "")
        if settings.email_spam_filter_enabled:
            # Check if sender is a registered user (less likely to be spam)
            is_registered_user = False
            if from_email:
                user_res = (
                    supabase.table("users")
                    .select("id")
                    .eq("email", from_email.lower())
                    .limit(1)
                    .execute()
                )
                is_registered_user = bool(user_res.data)
            
            # If not a registered user, check spam classification
            if not is_registered_user:
                if spam_classifier.should_filter(parsed, filter_promotions=settings.email_filter_promotions):
                    classification = spam_classifier.classify(parsed)
                    logger.info(
                        f"Filtered {classification['category']} email from {from_email} via webhook: "
                        f"{', '.join(classification['reasons'][:3])}"
                    )
                    # Optionally log filtered emails for review
                    if settings.email_log_filtered:
                        try:
                            default_account = email_service.get_default_email_account()
                            if default_account:
                                supabase.table("email_messages").insert({
                                    "email_account_id": default_account["id"],
                                    "message_id": parsed.get("message_id", ""),
                                    "subject": parsed.get("subject", ""),
                                    "body_text": parsed.get("body_text", "")[:500],
                                    "from_email": from_email,
                                    "to_email": parsed.get("to_emails", []),
                                    "status": "filtered",
                                    "direction": "inbound",
                                    "created_at": datetime.now(timezone.utc).isoformat(),
                                }).execute()
                        except Exception as e:
                            logger.warning(f"Failed to log filtered email: {e}")
                    return {
                        "success": True,
                        "message": "Email filtered as spam/promotion",
                        "filtered": True,
                        "category": classification["category"]
                    }
        
        # Find or create ticket
        ticket_id = None
        subject = parsed.get("subject", "")
        
        # Check if this is a reply to an existing ticket
        in_reply_to = parsed.get("in_reply_to", "")
        if in_reply_to:
            # Find ticket by email message ID
            existing_email = (
                supabase.table("email_messages")
                .select("ticket_id")
                .eq("message_id", in_reply_to)
                .limit(1)
                .execute()
            )
            if existing_email.data:
                ticket_id = existing_email.data[0]["ticket_id"]
        
        # If no ticket found, create new one
        if not ticket_id:
            # Extract ticket subject (remove Re:, Fwd:, etc.)
            clean_subject = re.sub(r'^(Re:|Fwd?:|RE:|FW?:)\s*', '', subject, flags=re.IGNORECASE).strip()
            
            # Create new ticket
            ticket_data = {
                "context": "email",
                "subject": clean_subject or "Email from " + from_email,
                "status": "open",
                "priority": "medium",
                "user_id": None,  # Will be linked if user exists
                "source": "email",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            
            # Try to find user by email
            user_res = (
                supabase.table("users")
                .select("id")
                .eq("email", from_email.lower())
                .limit(1)
                .execute()
            )
            if user_res.data:
                ticket_data["user_id"] = user_res.data[0]["id"]
            
            ticket_result = supabase.table("tickets").insert(ticket_data).execute()
            if ticket_result.data:
                ticket_id = ticket_result.data[0]["id"]
        
        if not ticket_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create or find ticket"
            )
        
        # Get default email account for receiving
        default_account = email_service.get_default_email_account()
        if not default_account:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No email account configured"
            )
        
        # Save email message
        email_message_data = {
            "ticket_id": ticket_id,
            "email_account_id": default_account["id"],
            "message_id": parsed.get("message_id", ""),
            "in_reply_to": parsed.get("in_reply_to"),
            "subject": subject,
            "body_text": parsed.get("body_text", ""),
            "body_html": parsed.get("body_html"),
            "from_email": from_email,
            "to_email": parsed.get("to_emails", []),
            "cc_email": parsed.get("cc_emails", []),
            "status": "received",
            "direction": "inbound",
            "has_attachments": len(parsed.get("attachments", [])) > 0,
            "received_at": datetime.utcnow().isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        email_result = supabase.table("email_messages").insert(email_message_data).execute()
        
        # Link to ticket thread
        if email_result.data:
            # Calculate thread position
            thread_count = (
                supabase.table("email_threads")
                .select("id", count="exact")
                .eq("ticket_id", ticket_id)
                .execute()
                .count
            )
            
            supabase.table("email_threads").insert({
                "ticket_id": ticket_id,
                "email_message_id": email_result.data[0]["id"],
                "thread_position": thread_count + 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
        
        # Create message in ticket
        message_text = parsed.get("body_text", "")[:1000]  # Limit length
        supabase.table("messages").insert({
            "ticket_id": ticket_id,
            "sender": "customer" if email_result.data else "system",
            "message": f"Email received from {from_email}:\n\n{message_text}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        
        logger.info(f"Email received and linked to ticket {ticket_id}")
        
        return {
            "success": True,
            "message": "Email received and processed",
            "ticket_id": ticket_id,
            "email_message": email_result.data[0] if email_result.data else None,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in receive_email_webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process email",
        )


@app.get("/ticket/{ticket_id}/emails")
def get_ticket_email_thread(
    ticket_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get email thread for a ticket."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify ticket exists and user has access
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found",
            )
        
        ticket = ticket_res.data[0]
        user_id = current_user["id"]
        user_role = current_user["role"]
        
        # Verify access
        if user_role == "customer" and ticket.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this ticket",
            )
        
        # Get email messages for this ticket
        email_messages = (
            supabase.table("email_messages")
            .select("*")
            .eq("ticket_id", ticket_id)
            .order("created_at", desc=False)
            .execute()
        )
        
        # Get thread positions
        threads = (
            supabase.table("email_threads")
            .select("*")
            .eq("ticket_id", ticket_id)
            .order("thread_position", desc=False)
            .execute()
        )
        
        # Build thread structure
        thread_map = {t["email_message_id"]: t for t in (threads.data if threads.data else [])}
        emails = []
        for msg in (email_messages.data if email_messages.data else []):
            thread_info = thread_map.get(msg["id"], {})
            emails.append({
                **msg,
                "thread_position": thread_info.get("thread_position", 0),
            })
        
        # Sort by thread position
        emails.sort(key=lambda x: x.get("thread_position", 0))
        
        return {
            "ticket_id": ticket_id,
            "emails": emails,
            "count": len(emails),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_ticket_email_thread: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get email thread",
        )


# ---------------------------
# 📧 EMAIL TEMPLATE ENDPOINTS
# ---------------------------

@app.post("/admin/email-templates")
def create_email_template(
    req: EmailTemplateRequest,
    current_admin: dict = Depends(get_current_admin),
):
    """Create or update email template."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Validate template type
        valid_types = ["ticket_created", "ticket_reply", "ticket_closed", "ticket_assigned", "custom"]
        if req.template_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template type must be one of: {', '.join(valid_types)}"
            )
        
        template_data = {
            "name": req.name,
            "subject": req.subject,
            "body_text": req.body_text,
            "body_html": req.body_html,
            "template_type": req.template_type,
            "variables": json.dumps(req.variables) if req.variables else None,
            "is_active": req.is_active,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Check if template exists
        existing = (
            supabase.table("email_templates")
            .select("id")
            .eq("name", req.name)
            .execute()
        )
        
        if existing.data:
            # Update existing
            result = (
                supabase.table("email_templates")
                .update(template_data)
                .eq("id", existing.data[0]["id"])
                .execute()
            )
            logger.info(f"Updated email template: {req.name} by {current_admin['email']}")
        else:
            # Create new
            template_data["created_at"] = datetime.utcnow().isoformat()
            template_data["created_by"] = current_admin["id"]
            result = (
                supabase.table("email_templates")
                .insert(template_data)
                .execute()
            )
            logger.info(f"Created email template: {req.name} by {current_admin['email']}")
        
        return {"success": True, "template": result.data[0] if result.data else None}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_email_template: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create email template",
        )


@app.get("/admin/email-templates")
def list_email_templates(
    template_type: str | None = Query(None),
    is_active: bool | None = Query(None),
    current_admin: dict = Depends(get_current_admin),
):
    """List email templates."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        query = supabase.table("email_templates").select("*")
        
        if template_type:
            query = query.eq("template_type", template_type)
        if is_active is not None:
            query = query.eq("is_active", is_active)
        
        result = query.order("created_at", desc=True).execute()
        
        return {"templates": result.data if result.data else []}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_email_templates: {e}", exc_info=True)
        raise


# ---------------------------
# 🏢 ORGANIZATION ENDPOINTS (Super Admin Only)
# ---------------------------

@app.post("/admin/organizations")
def create_organization(
    req: OrganizationRequest,
    current_super_admin: dict = Depends(get_current_super_admin)
):
    """Create a new organization. Only super admins can create organizations."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Validate slug format
        if not re.match(r'^[a-z0-9-]+$', req.slug):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Slug must contain only lowercase letters, numbers, and hyphens"
            )
        
        # Check if slug already exists
        existing = (
            supabase.table("organizations")
            .select("id")
            .eq("slug", req.slug)
            .execute()
        )
        if existing.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization with this slug already exists"
            )
        
        # Create organization
        org_data = {
            "name": req.name,
            "slug": req.slug,
            "description": req.description,
            "super_admin_id": current_super_admin["id"],
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = (
            supabase.table("organizations")
            .insert(org_data)
            .execute()
        )
        
        # Add super admin as organization member
        if result.data:
            supabase.table("organization_members").insert({
                "organization_id": result.data[0]["id"],
                "user_id": current_super_admin["id"],
                "role": "admin",
                "joined_at": datetime.utcnow().isoformat(),
                "is_active": True,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        
        logger.info(f"Created organization: {req.slug} by {current_super_admin['email']}")
        return {"success": True, "organization": result.data[0] if result.data else None}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_organization: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create organization",
        )


@app.get("/admin/organizations")
def list_organizations(
    current_super_admin: dict = Depends(get_current_super_admin)
):
    """List all organizations. Only super admins can list organizations."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Get organizations where user is super admin
        result = (
            supabase.table("organizations")
            .select("*")
            .eq("super_admin_id", current_super_admin["id"])
            .order("created_at", desc=True)
            .execute()
        )
        
        return {"organizations": result.data if result.data else []}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_organizations: {e}", exc_info=True)
        raise


@app.post("/admin/organizations/{organization_id}/invite")
def invite_member(
    organization_id: str,
    req: InviteMemberRequest,
    current_super_admin: dict = Depends(get_current_super_admin)
):
    """Invite a team member to an organization. Only super admins can invite members."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify organization exists and user is super admin
        org_res = (
            supabase.table("organizations")
            .select("*")
            .eq("id", organization_id)
            .eq("super_admin_id", current_super_admin["id"])
            .limit(1)
            .execute()
        )
        if not org_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found or you don't have permission"
            )
        
        # Validate role
        if req.role not in ["admin", "viewer"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role must be 'admin' or 'viewer'"
            )
        
        # Find or create user
        user_res = (
            supabase.table("users")
            .select("id, email, role")
            .eq("email", req.email.lower())
            .limit(1)
            .execute()
        )
        
        if not user_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. User must register first."
            )
        
        user = user_res.data[0]
        user_id = user["id"]
        
        # Check if user is already a member
        existing_member = (
            supabase.table("organization_members")
            .select("id")
            .eq("organization_id", organization_id)
            .eq("user_id", user_id)
            .execute()
        )
        if existing_member.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this organization"
            )
        
        # Add member
        member_data = {
            "organization_id": organization_id,
            "user_id": user_id,
            "role": req.role,
            "invited_by": current_super_admin["id"],
            "invited_at": datetime.utcnow().isoformat(),
            "is_active": True,
            "created_at": datetime.utcnow().isoformat()
        }
        
        result = (
            supabase.table("organization_members")
            .insert(member_data)
            .execute()
        )
        
        logger.info(f"Invited {req.email} to organization {organization_id} by {current_super_admin['email']}")
        return {"success": True, "member": result.data[0] if result.data else None}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in invite_member: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invite member",
        )


@app.get("/admin/organizations/{organization_id}/members")
def list_organization_members(
    organization_id: str,
    current_super_admin: dict = Depends(get_current_super_admin)
):
    """List all members of an organization. Only super admins can list members."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify organization exists and user is super admin
        org_res = (
            supabase.table("organizations")
            .select("id")
            .eq("id", organization_id)
            .eq("super_admin_id", current_super_admin["id"])
            .limit(1)
            .execute()
        )
        if not org_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found or you don't have permission"
            )
        
        # Get members with user details
        result = (
            supabase.table("organization_members")
            .select("*, users(email, name, role)")
            .eq("organization_id", organization_id)
            .order("created_at", desc=True)
            .execute()
        )
        
        return {"members": result.data if result.data else []}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_organization_members: {e}", exc_info=True)
        raise


@app.delete("/admin/organizations/{organization_id}/members/{member_id}")
def remove_member(
    organization_id: str,
    member_id: str,
    current_super_admin: dict = Depends(get_current_super_admin)
):
    """Remove a member from an organization. Only super admins can remove members."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify organization exists and user is super admin
        org_res = (
            supabase.table("organizations")
            .select("id")
            .eq("id", organization_id)
            .eq("super_admin_id", current_super_admin["id"])
            .limit(1)
            .execute()
        )
        if not org_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found or you don't have permission"
            )
        
        # Verify member exists
        member_res = (
            supabase.table("organization_members")
            .select("*")
            .eq("id", member_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
        )
        if not member_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found"
            )
        
        # Remove member
        supabase.table("organization_members").delete().eq("id", member_id).execute()
        
        logger.info(f"Removed member {member_id} from organization {organization_id} by {current_super_admin['email']}")
        return {"success": True, "message": "Member removed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in remove_member: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove member",
        )


# ---------------------------
# 🎯 ROUTING RULES ENDPOINTS
# ---------------------------

@app.post("/admin/routing-rules")
def create_routing_rule(
    req: RoutingRuleRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """Create a new routing rule."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Get user's organization (if any)
        org_member_res = (
            supabase.table("organization_members")
            .select("organization_id")
            .eq("user_id", current_admin["id"])
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        
        organization_id = None
        if org_member_res.data:
            organization_id = org_member_res.data[0]["organization_id"]
        
        # Validate action_type
        valid_actions = ["assign_to_agent", "assign_to_group", "set_priority", "add_tag", "set_category"]
        if req.action_type not in valid_actions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Action type must be one of: {', '.join(valid_actions)}"
            )
        
        rule_data = {
            "organization_id": organization_id,
            "name": req.name,
            "description": req.description,
            "priority": req.priority,
            "is_active": req.is_active,
            "conditions": json.dumps(req.conditions),
            "action_type": req.action_type,
            "action_value": req.action_value,
            "created_by": current_admin["id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = (
            supabase.table("routing_rules")
            .insert(rule_data)
            .execute()
        )
        
        logger.info(f"Created routing rule: {req.name} by {current_admin['email']}")
        return {"success": True, "rule": result.data[0] if result.data else None}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_routing_rule: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create routing rule",
        )


@app.get("/admin/routing-rules")
def list_routing_rules(
    current_admin: dict = Depends(get_current_admin)
):
    """List all routing rules for the admin's organization."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Get user's organization (if any)
        org_member_res = (
            supabase.table("organization_members")
            .select("organization_id")
            .eq("user_id", current_admin["id"])
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        
        query = supabase.table("routing_rules").select("*")
        
        if org_member_res.data:
            organization_id = org_member_res.data[0]["organization_id"]
            query = query.eq("organization_id", organization_id)
        else:
            # If no organization, return empty list or global rules
            query = query.is_("organization_id", "null")
        
        result = query.order("priority", desc=True).execute()
        
        # Parse conditions JSON
        rules = result.data if result.data else []
        for rule in rules:
            if isinstance(rule.get("conditions"), str):
                try:
                    rule["conditions"] = json.loads(rule["conditions"])
                except:
                    rule["conditions"] = {}
        
        return {"rules": rules}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_routing_rules: {e}", exc_info=True)
        raise


@app.delete("/admin/routing-rules/{rule_id}")
def delete_routing_rule(
    rule_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Delete a routing rule."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify rule exists and user has access
        rule_res = (
            supabase.table("routing_rules")
            .select("*")
            .eq("id", rule_id)
            .limit(1)
            .execute()
        )
        if not rule_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Routing rule not found"
            )
        
        # Check organization access
        rule = rule_res.data[0]
        if rule.get("organization_id"):
            org_member_res = (
                supabase.table("organization_members")
                .select("id")
                .eq("organization_id", rule["organization_id"])
                .eq("user_id", current_admin["id"])
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            if not org_member_res.data:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this routing rule"
                )
        
        supabase.table("routing_rules").delete().eq("id", rule_id).execute()
        
        logger.info(f"Deleted routing rule {rule_id} by {current_admin['email']}")
        return {"success": True, "message": "Routing rule deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_routing_rule: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete routing rule",
        )


# ---------------------------
# 🏷️ TAGS & CATEGORIES ENDPOINTS
# ---------------------------

@app.post("/admin/tags")
def create_tag(
    req: TagRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """Create a new tag."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Get user's organization (if any)
        org_member_res = (
            supabase.table("organization_members")
            .select("organization_id")
            .eq("user_id", current_admin["id"])
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        
        organization_id = None
        if org_member_res.data:
            organization_id = org_member_res.data[0]["organization_id"]
        
        tag_data = {
            "organization_id": organization_id,
            "name": req.name,
            "color": req.color,
            "description": req.description,
            "created_by": current_admin["id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = (
            supabase.table("tags")
            .insert(tag_data)
            .execute()
        )
        
        logger.info(f"Created tag: {req.name} by {current_admin['email']}")
        return {"success": True, "tag": result.data[0] if result.data else None}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_tag: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tag",
        )


@app.get("/admin/tags")
def list_tags(
    current_admin: dict = Depends(get_current_admin)
):
    """List all tags for the admin's organization."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Get user's organization (if any)
        org_member_res = (
            supabase.table("organization_members")
            .select("organization_id")
            .eq("user_id", current_admin["id"])
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        
        query = supabase.table("tags").select("*")
        
        if org_member_res.data:
            organization_id = org_member_res.data[0]["organization_id"]
            query = query.or_(f"organization_id.eq.{organization_id},organization_id.is.null")
        else:
            query = query.is_("organization_id", "null")
        
        result = query.order("name", desc=False).execute()
        
        return {"tags": result.data if result.data else []}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_tags: {e}", exc_info=True)
        raise


@app.put("/admin/tags/{tag_id}")
def update_tag(
    tag_id: str,
    req: TagRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """Update a tag."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify tag exists and user has access
        tag_res = (
            supabase.table("tags")
            .select("*")
            .eq("id", tag_id)
            .limit(1)
            .execute()
        )
        if not tag_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tag not found"
            )
        
        tag = tag_res.data[0]
        
        # Check organization access
        if tag.get("organization_id"):
            org_member_res = (
                supabase.table("organization_members")
                .select("id")
                .eq("organization_id", tag["organization_id"])
                .eq("user_id", current_admin["id"])
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            if not org_member_res.data:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this tag"
                )
        
        # Update tag
        update_data = {
            "name": req.name,
            "color": req.color,
            "description": req.description,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = (
            supabase.table("tags")
            .update(update_data)
            .eq("id", tag_id)
            .execute()
        )
        
        logger.info(f"Updated tag {tag_id} by {current_admin['email']}")
        return {"success": True, "tag": result.data[0] if result.data else None}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_tag: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update tag",
        )


@app.delete("/admin/tags/{tag_id}")
def delete_tag(
    tag_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Delete a tag."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify tag exists and user has access
        tag_res = (
            supabase.table("tags")
            .select("*")
            .eq("id", tag_id)
            .limit(1)
            .execute()
        )
        if not tag_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tag not found"
            )
        
        tag = tag_res.data[0]
        
        # Check organization access
        if tag.get("organization_id"):
            org_member_res = (
                supabase.table("organization_members")
                .select("id")
                .eq("organization_id", tag["organization_id"])
                .eq("user_id", current_admin["id"])
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            if not org_member_res.data:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this tag"
                )
        
        # Delete tag (cascade will handle ticket_tags)
        supabase.table("tags").delete().eq("id", tag_id).execute()
        
        logger.info(f"Deleted tag {tag_id} by {current_admin['email']}")
        return {"success": True, "message": "Tag deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_tag: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete tag",
        )


@app.post("/ticket/{ticket_id}/tags")
def add_tags_to_ticket(
    ticket_id: str,
    req: TicketTagsRequest,
    current_user: dict = Depends(get_current_user)
):
    """Add tags to a ticket."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify ticket exists and user has access
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        ticket = ticket_res.data[0]
        user_role = current_user["role"]
        
        # Verify access
        if user_role == "customer" and ticket.get("user_id") != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this ticket"
            )
        
        # Add tags
        added_tags = []
        for tag_id in req.tag_ids:
            # Check if tag already exists on ticket
            existing = (
                supabase.table("ticket_tags")
                .select("id")
                .eq("ticket_id", ticket_id)
                .eq("tag_id", tag_id)
                .execute()
            )
            if not existing.data:
                supabase.table("ticket_tags").insert({
                    "ticket_id": ticket_id,
                    "tag_id": tag_id,
                    "added_by": current_user["id"],
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
                added_tags.append(tag_id)
        
        logger.info(f"Added {len(added_tags)} tag(s) to ticket {ticket_id} by {current_user['email']}")
        return {"success": True, "added_tags": added_tags}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_tags_to_ticket: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add tags",
        )


@app.delete("/ticket/{ticket_id}/tags/{tag_id}")
def remove_tag_from_ticket(
    ticket_id: str,
    tag_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Remove a tag from a ticket."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify ticket exists and user has access
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        ticket = ticket_res.data[0]
        user_role = current_user["role"]
        
        # Verify access
        if user_role == "customer" and ticket.get("user_id") != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this ticket"
            )
        
        # Remove tag
        supabase.table("ticket_tags").delete().eq("ticket_id", ticket_id).eq("tag_id", tag_id).execute()
        
        logger.info(f"Removed tag {tag_id} from ticket {ticket_id} by {current_user['email']}")
        return {"success": True, "message": "Tag removed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in remove_tag_from_ticket: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove tag",
        )


@app.get("/ticket/{ticket_id}/tags")
def get_ticket_tags(
    ticket_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all tags for a ticket."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify ticket exists and user has access
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        ticket = ticket_res.data[0]
        user_role = current_user["role"]
        
        # Verify access
        if user_role == "customer" and ticket.get("user_id") != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this ticket"
            )
        
        # Get tags
        result = (
            supabase.table("ticket_tags")
            .select("*, tags(*)")
            .eq("ticket_id", ticket_id)
            .execute()
        )
        
        tags = []
        if result.data:
            for item in result.data:
                if item.get("tags"):
                    tags.append(item["tags"])
        
        return {"tags": tags}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_ticket_tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get tags",
        )


@app.post("/admin/categories")
def create_category(
    req: CategoryRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """Create a new category."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Get user's organization (if any)
        org_member_res = (
            supabase.table("organization_members")
            .select("organization_id")
            .eq("user_id", current_admin["id"])
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        
        organization_id = None
        if org_member_res.data:
            organization_id = org_member_res.data[0]["organization_id"]
        
        category_data = {
            "organization_id": organization_id,
            "name": req.name,
            "color": req.color,
            "description": req.description,
            "created_by": current_admin["id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = (
            supabase.table("categories")
            .insert(category_data)
            .execute()
        )
        
        logger.info(f"Created category: {req.name} by {current_admin['email']}")
        return {"success": True, "category": result.data[0] if result.data else None}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_category: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create category",
        )


@app.get("/admin/categories")
def list_categories(
    current_admin: dict = Depends(get_current_admin)
):
    """List all categories for the admin's organization."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Get user's organization (if any)
        org_member_res = (
            supabase.table("organization_members")
            .select("organization_id")
            .eq("user_id", current_admin["id"])
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        
        query = supabase.table("categories").select("*")
        
        if org_member_res.data:
            organization_id = org_member_res.data[0]["organization_id"]
            query = query.or_(f"organization_id.eq.{organization_id},organization_id.is.null")
        else:
            query = query.is_("organization_id", "null")
        
        result = query.order("name", desc=False).execute()
        
        return {"categories": result.data if result.data else []}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_categories: {e}", exc_info=True)
        raise


@app.put("/admin/categories/{category_id}")
def update_category(
    category_id: str,
    req: CategoryRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """Update a category."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify category exists and user has access
        category_res = (
            supabase.table("categories")
            .select("*")
            .eq("id", category_id)
            .limit(1)
            .execute()
        )
        if not category_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
        
        category = category_res.data[0]
        
        # Check organization access
        if category.get("organization_id"):
            org_member_res = (
                supabase.table("organization_members")
                .select("id")
                .eq("organization_id", category["organization_id"])
                .eq("user_id", current_admin["id"])
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            if not org_member_res.data:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this category"
                )
        
        # Update category
        update_data = {
            "name": req.name,
            "color": req.color,
            "description": req.description,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = (
            supabase.table("categories")
            .update(update_data)
            .eq("id", category_id)
            .execute()
        )
        
        logger.info(f"Updated category {category_id} by {current_admin['email']}")
        return {"success": True, "category": result.data[0] if result.data else None}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_category: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update category",
        )


@app.delete("/admin/categories/{category_id}")
def delete_category(
    category_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Delete a category."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify category exists and user has access
        category_res = (
            supabase.table("categories")
            .select("*")
            .eq("id", category_id)
            .limit(1)
            .execute()
        )
        if not category_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
        
        category = category_res.data[0]
        
        # Check organization access
        if category.get("organization_id"):
            org_member_res = (
                supabase.table("organization_members")
                .select("id")
                .eq("organization_id", category["organization_id"])
                .eq("user_id", current_admin["id"])
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            if not org_member_res.data:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this category"
                )
        
        # Delete category
        supabase.table("categories").delete().eq("id", category_id).execute()
        
        logger.info(f"Deleted category {category_id} by {current_admin['email']}")
        return {"success": True, "message": "Category deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_category: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete category",
        )


@app.put("/ticket/{ticket_id}/category")
def set_ticket_category(
    ticket_id: str,
    req: TicketCategoryRequest,
    current_user: dict = Depends(get_current_user)
):
    """Set category for a ticket."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        # Verify ticket exists and user has access
        ticket_res = (
            supabase.table("tickets")
            .select("*")
            .eq("id", ticket_id)
            .limit(1)
            .execute()
        )
        if not ticket_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket not found"
            )
        
        ticket = ticket_res.data[0]
        user_role = current_user["role"]
        
        # Verify access (only admins can set category)
        if user_role == "customer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can set ticket category"
            )
        
        # Update category
        supabase.table("tickets").update({
            "category": req.category,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", ticket_id).execute()
        
        logger.info(f"Set category '{req.category}' for ticket {ticket_id} by {current_user['email']}")
        return {"success": True, "message": "Category updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in set_ticket_category: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set category",
        )

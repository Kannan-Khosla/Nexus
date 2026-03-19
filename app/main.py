"""
AI Support API — Application Entry Point.

This file creates the FastAPI app, registers middleware, and includes all routers.
The actual endpoint logic lives in the `routers/` directory.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from app.config import settings
from app.logger import setup_logger
from app.middleware import error_handler, http_exception_handler, validation_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from app.email_polling_service import email_polling_service

# Routers
from app.routers import auth, tickets, admin, sla, attachments, email, routing, tags

logger = setup_logger(__name__)


# ---------------------------------------------------
# Background Tasks
# ---------------------------------------------------
async def email_polling_task():
    """Background task that polls email accounts periodically."""
    while True:
        try:
            if settings.email_polling_enabled:
                logger.debug("Starting email polling cycle")
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, email_polling_service.poll_all_accounts
                )
                if result.get("emails_processed", 0) > 0:
                    logger.info(
                        f"Email polling: processed {result['emails_processed']} emails"
                    )
        except Exception as e:
            logger.error(f"Email polling error: {e}", exc_info=True)
        await asyncio.sleep(settings.email_polling_interval)


# ---------------------------------------------------
# App Lifespan (Startup / Shutdown)
# ---------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    logger.info("Starting AI Support API...")
    polling_task = None
    if settings.email_polling_enabled:
        polling_task = asyncio.create_task(email_polling_task())
        logger.info(
            f"Email polling started (interval: {settings.email_polling_interval}s)"
        )
    yield
    if polling_task:
        polling_task.cancel()
        logger.info("Email polling stopped")
    logger.info("AI Support API shutting down")


# ---------------------------------------------------
# Create App
# ---------------------------------------------------
app = FastAPI(title="AI Support API", version="1.0.0", lifespan=lifespan)

# Error handlers
app.add_exception_handler(Exception, error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------
# Health Check
# ---------------------------------------------------
@app.get("/")
def health_check():
    """Simple health check."""
    return {"message": "AI Support API (threaded system) is running"}


# ---------------------------------------------------
# Register Routers
# ---------------------------------------------------
app.include_router(auth.router, tags=["Authentication"])
app.include_router(tickets.router, tags=["Tickets"])
app.include_router(admin.router, tags=["Admin"])
app.include_router(sla.router, tags=["SLA & Priority"])
app.include_router(attachments.router, tags=["Attachments"])
app.include_router(email.router, tags=["Email"])
app.include_router(routing.router, tags=["Routing"])
app.include_router(tags.router, tags=["Tags & Categories"])

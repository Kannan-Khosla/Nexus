"""Shared helper utilities: rate limiting, output sanitization, and AI reply generation."""

import re
import time
from datetime import datetime, timedelta
from app.supabase_config import supabase
from app.config import settings
from app.logger import setup_logger
from openai import OpenAI

logger = setup_logger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=settings.openai_api_key)


# ---------------------------------------------------
# Rate Limiting
# ---------------------------------------------------
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


# ---------------------------------------------------
# Output Sanitization (PII / Profanity)
# ---------------------------------------------------
PROFANITY = re.compile(r"\b(fuck|shit|bitch|asshole)(?:ing|s|ed)?\b", re.IGNORECASE)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?:\+?\d[\s-]?)?(?:\(?\d{3}\)?[\s-]?)?\d{3}[\s-]?\d{4}")
CC = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


def sanitize_output(text: str) -> tuple[str, dict]:
    redacted = text or ""
    flags = {"profanity": False, "email": False, "phone": False, "cc": False}
    if PROFANITY.search(redacted):
        flags["profanity"] = True
        redacted = PROFANITY.sub("***", redacted)
    if EMAIL_RE.search(redacted):
        flags["email"] = True
        redacted = EMAIL_RE.sub("***@***.***", redacted)
    if CC.search(redacted):
        flags["cc"] = True
        redacted = CC.sub("**** **** **** ****", redacted)
    if PHONE.search(redacted):
        flags["phone"] = True
        redacted = PHONE.sub("***-***-****", redacted)
    return redacted, flags


# ---------------------------------------------------
# AI Reply Generation (OpenAI with retry/backoff)
# ---------------------------------------------------
def generate_ai_reply(prompt: str) -> str:
    """Generate AI reply with exponential backoff retry logic."""
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

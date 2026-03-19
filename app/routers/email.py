"""Email endpoints: accounts, sending, receiving, threads, templates, polling."""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from datetime import datetime, timezone
from app.supabase_config import supabase
from app.config import settings
from app.logger import setup_logger
from app.dependencies import get_current_user, get_current_admin
from app.email_service import email_service
from app.email_polling_service import email_polling_service
from app.spam_classifier import spam_classifier
from app.helpers import sanitize_output, generate_ai_reply
from app.schemas import (
    EmailAccountRequest, SendEmailRequest, EmailWebhookRequest, EmailTemplateRequest,
)
import json
import re

logger = setup_logger(__name__)
router = APIRouter()

@router.post("/admin/email-accounts")
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


@router.get("/admin/email-accounts")
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


@router.post("/admin/email-accounts/{account_id}/test")
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


@router.post("/admin/email-accounts/{account_id}/test-imap")
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


@router.post("/admin/email-accounts/{account_id}/enable-polling")
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


@router.post("/admin/email-accounts/{account_id}/disable-polling")
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


@router.get("/admin/email-accounts/{account_id}/polling-status")
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


@router.post("/admin/email-accounts/{account_id}/poll-now")
def poll_email_account(
    account_id: str,
    current_admin: dict = Depends(get_current_admin),
):
    """Manually poll an email account."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        result = email_polling_service.poll_account(account_id)
        if result.get("success"):
            return result
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to poll account")
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error manually polling account: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to manually poll account",
        )



@router.post("/ticket/{ticket_id}/send-email")
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


@router.post("/webhooks/email")
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


@router.get("/ticket/{ticket_id}/emails")
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

@router.post("/admin/email-templates")
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


@router.get("/admin/email-templates")
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

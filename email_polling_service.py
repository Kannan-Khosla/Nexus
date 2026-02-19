"""Email polling service for automatically fetching emails and creating tickets."""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from logger import setup_logger
from supabase_config import supabase
from email_service import email_service
from routing_service import routing_service
from spam_classifier import spam_classifier
from config import settings
import re

logger = setup_logger(__name__)


class EmailPollingService:
    """Service for polling email accounts and creating tickets."""
    
    def __init__(self):
        self.supabase = supabase
        self.email_service = email_service
        self.routing_service = routing_service
    
    def process_email_to_ticket(self, parsed_email: Dict[str, Any], account_id: str) -> Optional[str]:
        """
        Process a parsed email and create/update ticket.
        Returns ticket_id if successful, None otherwise.
        """
        try:
            if not self.supabase:
                logger.error("Database not configured")
                return None
            
            # Spam filtering - check if email should be filtered
            if settings.email_spam_filter_enabled:
                # Check if sender is a registered user (less likely to be spam)
                from_email = parsed_email.get("from_email", "")
                is_registered_user = False
                if from_email:
                    user_res = (
                        self.supabase.table("users")
                        .select("id")
                        .eq("email", from_email.lower())
                        .limit(1)
                        .execute()
                    )
                    is_registered_user = bool(user_res.data)
                
                # If not a registered user, check spam classification
                if not is_registered_user:
                    if spam_classifier.should_filter(parsed_email, filter_promotions=settings.email_filter_promotions):
                        classification = spam_classifier.classify(parsed_email)
                        logger.info(
                            f"Filtered {classification['category']} email from {from_email}: "
                            f"{', '.join(classification['reasons'][:3])}"
                        )
                        # Optionally log filtered emails for review
                        if settings.email_log_filtered:
                            try:
                                self.supabase.table("email_messages").insert({
                                    "email_account_id": account_id,
                                    "message_id": parsed_email.get("message_id", ""),
                                    "subject": parsed_email.get("subject", ""),
                                    "body_text": parsed_email.get("body_text", "")[:500],  # Truncate
                                    "from_email": from_email,
                                    "to_email": parsed_email.get("to_emails", []),
                                    "status": "filtered",
                                    "direction": "inbound",
                                    "created_at": datetime.now(timezone.utc).isoformat(),
                                }).execute()
                            except Exception as e:
                                logger.warning(f"Failed to log filtered email: {e}")
                        return None
            
            subject = parsed_email.get("subject", "")
            message_id = parsed_email.get("message_id", "")
            
            # Check if email already processed (duplicate prevention)
            if message_id:
                existing_email = (
                    self.supabase.table("email_messages")
                    .select("ticket_id")
                    .eq("message_id", message_id)
                    .limit(1)
                    .execute()
                )
                if existing_email.data:
                    logger.debug(f"Email {message_id} already processed, skipping")
                    return existing_email.data[0]["ticket_id"]
            
            # Find or create ticket
            ticket_id = None
            
            # Check if this is a reply to an existing ticket
            in_reply_to = parsed_email.get("in_reply_to", "")
            if in_reply_to:
                # Find ticket by email message ID
                existing_email = (
                    self.supabase.table("email_messages")
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
                    self.supabase.table("users")
                    .select("id")
                    .eq("email", from_email.lower())
                    .limit(1)
                    .execute()
                )
                if user_res.data:
                    ticket_data["user_id"] = user_res.data[0]["id"]
                
                ticket_result = self.supabase.table("tickets").insert(ticket_data).execute()
                if ticket_result.data:
                    ticket_id = ticket_result.data[0]["id"]
                    logger.info(f"Created new ticket {ticket_id} from email {from_email}")
            
            if not ticket_id:
                logger.error("Failed to create or find ticket for email")
                return None
            
            # Save email message
            email_message_data = {
                "ticket_id": ticket_id,
                "email_account_id": account_id,
                "message_id": message_id,
                "in_reply_to": in_reply_to,
                "subject": subject,
                "body_text": parsed_email.get("body_text", ""),
                "body_html": parsed_email.get("body_html"),
                "from_email": from_email,
                "to_email": parsed_email.get("to_emails", []),
                "cc_email": parsed_email.get("cc_emails", []),
                "status": "received",
                "direction": "inbound",
                "has_attachments": len(parsed_email.get("attachments", [])) > 0,
                "received_at": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            
            email_result = self.supabase.table("email_messages").insert(email_message_data).execute()
            
            # Link to ticket thread
            if email_result.data:
                # Calculate thread position
                thread_count = (
                    self.supabase.table("email_threads")
                    .select("id", count="exact")
                    .eq("ticket_id", ticket_id)
                    .execute()
                    .count
                )
                
                self.supabase.table("email_threads").insert({
                    "ticket_id": ticket_id,
                    "email_message_id": email_result.data[0]["id"],
                    "thread_position": thread_count + 1,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }).execute()
            
            # Create message in ticket
            message_text = parsed_email.get("body_text", "")[:1000]  # Limit length
            self.supabase.table("messages").insert({
                "ticket_id": ticket_id,
                "sender": "customer",
                "message": f"Email received from {from_email}:\n\n{message_text}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
            
            # Apply routing rules if this is a new ticket
            if not in_reply_to:
                try:
                    ticket_res = (
                        self.supabase.table("tickets")
                        .select("organization_id")
                        .eq("id", ticket_id)
                        .limit(1)
                        .execute()
                    )
                    organization_id = ticket_res.data[0].get("organization_id") if ticket_res.data else None
                    routing_service.apply_routing_rules(ticket_id, organization_id)
                except Exception as e:
                    logger.warning(f"Failed to apply routing rules for ticket {ticket_id}: {e}")
            
            logger.info(f"Email processed and linked to ticket {ticket_id}")
            return ticket_id
            
        except Exception as e:
            logger.error(f"Error processing email to ticket: {e}", exc_info=True)
            return None
    
    def poll_account(self, account_id: str) -> Dict[str, Any]:
        """
        Poll a single email account for new emails.
        Returns dict with results.
        """
        try:
            account = self.email_service.get_email_account(account_id)
            if not account:
                return {"success": False, "error": "Account not found"}
            
            if not account.get("imap_enabled"):
                return {"success": False, "error": "IMAP polling not enabled for this account"}
            
            if not account.get("is_active"):
                return {"success": False, "error": "Account is not active"}
            
            # Determine since_date - use last_polled_at or default to 7 days ago
            last_polled = account.get("last_polled_at")
            if last_polled:
                try:
                    since_date = datetime.fromisoformat(last_polled.replace('Z', '+00:00'))
                except:
                    since_date = datetime.now(timezone.utc) - timedelta(days=7)
            else:
                # First time polling - only fetch emails from last 7 days
                since_date = datetime.now(timezone.utc) - timedelta(days=7)
            
            # Fetch emails
            fetched_emails = self.email_service.fetch_emails_imap(
                account,
                since_date=since_date,
                max_emails=50
            )
            
            if not fetched_emails:
                # Update last_polled_at even if no emails found
                self.supabase.table("email_accounts").update({
                    "last_polled_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", account_id).execute()
                return {
                    "success": True,
                    "emails_fetched": 0,
                    "tickets_created": 0,
                    "message": "No new emails found"
                }
            
            # Process each email
            tickets_created = 0
            emails_processed = 0
            
            for parsed_email in fetched_emails:
                ticket_id = self.process_email_to_ticket(parsed_email, account_id)
                if ticket_id:
                    tickets_created += 1
                emails_processed += 1
            
            # Update last_polled_at
            self.supabase.table("email_accounts").update({
                "last_polled_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", account_id).execute()
            
            logger.info(f"Polled account {account.get('email')}: {emails_processed} emails processed, {tickets_created} tickets created")
            
            return {
                "success": True,
                "emails_fetched": len(fetched_emails),
                "emails_processed": emails_processed,
                "tickets_created": tickets_created,
                "account_email": account.get("email")
            }
            
        except Exception as e:
            logger.error(f"Error polling account {account_id}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def poll_all_accounts(self) -> Dict[str, Any]:
        """
        Poll all active accounts with IMAP enabled.
        Returns summary of polling results.
        """
        try:
            if not self.supabase:
                return {"success": False, "error": "Database not configured"}
            
            # Get all active accounts with IMAP enabled
            accounts_res = (
                self.supabase.table("email_accounts")
                .select("id, email")
                .eq("is_active", True)
                .eq("imap_enabled", True)
                .execute()
            )
            
            if not accounts_res.data:
                return {
                    "success": True,
                    "accounts_polled": 0,
                    "total_emails": 0,
                    "total_tickets": 0,
                    "message": "No accounts with IMAP polling enabled"
                }
            
            accounts = accounts_res.data
            total_emails = 0
            total_tickets = 0
            results = []
            
            for account in accounts:
                result = self.poll_account(account["id"])
                results.append({
                    "account_id": account["id"],
                    "account_email": account["email"],
                    "result": result
                })
                if result.get("success"):
                    total_emails += result.get("emails_fetched", 0)
                    total_tickets += result.get("tickets_created", 0)
            
            return {
                "success": True,
                "accounts_polled": len(accounts),
                "total_emails": total_emails,
                "total_tickets": total_tickets,
                "results": results
            }
            
        except Exception as e:
            # Check for Supabase 521 Web Server Down error
            error_str = str(e)
            if "521" in error_str and "Web server is down" in error_str:
                logger.warning("Supabase server is down (Error 521). Skipping polling cycle.")
                return {"success": False, "error": "Supabase server is down (521)"}
            
            logger.error(f"Error polling all accounts: {e}", exc_info=True)
            return {"success": False, "error": str(e)}


# Global polling service instance
email_polling_service = EmailPollingService()


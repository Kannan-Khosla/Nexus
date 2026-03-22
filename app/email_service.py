"""Email service for sending and receiving emails via SMTP or email APIs."""
import smtplib
import imaplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import json
import re
import email
from email.header import decode_header
import httpx
from app.logger import setup_logger
from app.supabase_config import supabase
from app.config import settings

logger = setup_logger(__name__)


class EmailService:
    """Email service supporting SMTP and API providers."""
    
    def __init__(self):
        self.supabase = supabase
    
    def get_email_account(self, account_id: str) -> Optional[Dict]:
        """Get email account configuration."""
        try:
            result = self.supabase.table("email_accounts").select("*").eq("id", account_id).limit(1).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error getting email account: {e}", exc_info=True)
            return None
    
    def get_default_email_account(self) -> Optional[Dict]:
        """Get default email account. Falls back to any active account if no default is set."""
        try:
            # First, try to get the default active account
            result = (
                self.supabase.table("email_accounts")
                .select("*")
                .eq("is_default", True)
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            if result.data:
                logger.info(f"Found default email account: {result.data[0].get('email')}")
                return result.data[0]
            
            # Fallback: Get any active account if no default is set
            logger.warning("No default email account found. Trying to find any active account...")
            fallback_result = (
                self.supabase.table("email_accounts")
                .select("*")
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            if fallback_result.data:
                logger.info(f"Using fallback active email account: {fallback_result.data[0].get('email')}")
                return fallback_result.data[0]
            
            # No active accounts found
            logger.error("No active email accounts found in database")
            return None
        except Exception as e:
            logger.error(f"Error getting default email account: {e}", exc_info=True)
            return None
    
    def decrypt_credentials(self, encrypted_data: str) -> str:
        """Decrypt credentials. Placeholder - implement proper encryption."""
        # TODO: Implement proper encryption/decryption
        # For now, return as-is (assumes credentials are stored securely)
        return encrypted_data
    
    def send_email_smtp(
        self,
        account: Dict,
        to_emails: List[str],
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Send email via SMTP."""
        try:
            smtp_host = account.get("smtp_host")
            smtp_port = account.get("smtp_port", 587)
            smtp_username = account.get("smtp_username")
            smtp_password = self.decrypt_credentials(account.get("smtp_password_encrypted", ""))
            from_email = account.get("email")
            display_name = account.get("display_name", "")
            
            # Create message
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{display_name} <{from_email}>" if display_name else from_email
            msg["To"] = ", ".join(to_emails)
            msg["Subject"] = subject
            
            if reply_to:
                msg["Reply-To"] = reply_to
            
            if cc_emails:
                msg["Cc"] = ", ".join(cc_emails)
            
            # Add body
            msg.attach(MIMEText(body_text, "plain"))
            if body_html:
                msg.attach(MIMEText(body_html, "html"))
            
            # Add attachments
            if attachments:
                for att in attachments:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(att["content"])
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f'attachment; filename="{att["filename"]}"'
                    )
                    msg.attach(part)
            
            # Connect and send — port 465 requires SSL from the start,
            # while port 587 (and others) use STARTTLS upgrade.
            all_recipients = to_emails + (cc_emails or []) + (bcc_emails or [])
            if smtp_port == 465:
                with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                    server.login(smtp_username, smtp_password)
                    server.send_message(msg, to_addrs=all_recipients)
            else:
                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    server.starttls()
                    server.login(smtp_username, smtp_password)
                    server.send_message(msg, to_addrs=all_recipients)
            
            logger.info(f"Email sent via SMTP to {to_emails}")
            return {"success": True, "message_id": msg["Message-ID"]}
            
        except Exception as e:
            logger.error(f"Error sending email via SMTP: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def send_email_sendgrid(
        self,
        account: Dict,
        to_emails: List[str],
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Send email via SendGrid API."""
        try:
            api_key = self.decrypt_credentials(account.get("api_key_encrypted", ""))
            from_email = account.get("email")
            display_name = account.get("display_name", "")
            
            url = "https://api.sendgrid.com/v3/mail/send"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "personalizations": [{
                    "to": [{"email": email} for email in to_emails],
                }],
                "from": {
                    "email": from_email,
                    "name": display_name or ""
                },
                "subject": subject,
                "content": [
                    {
                        "type": "text/plain",
                        "value": body_text
                    }
                ]
            }
            
            if cc_emails:
                data["personalizations"][0]["cc"] = [{"email": email} for email in cc_emails]
            
            if bcc_emails:
                data["personalizations"][0]["bcc"] = [{"email": email} for email in bcc_emails]
            
            if body_html:
                data["content"].append({
                    "type": "text/html",
                    "value": body_html
                })
            
            if reply_to:
                data["reply_to"] = {"email": reply_to}
            
            if attachments:
                data["attachments"] = [
                    {
                        "content": att["content"].decode("base64") if isinstance(att["content"], bytes) else att["content"],
                        "filename": att["filename"],
                        "type": att.get("content_type", "application/octet-stream"),
                        "disposition": "attachment"
                    }
                    for att in attachments
                ]
            
            response = httpx.post(url, headers=headers, json=data, timeout=30.0)
            response.raise_for_status()
            
            logger.info(f"Email sent via SendGrid to {to_emails}")
            return {"success": True, "message_id": response.headers.get("X-Message-Id")}
            
        except Exception as e:
            logger.error(f"Error sending email via SendGrid: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def send_email_ses(
        self,
        account: Dict,
        to_emails: List[str],
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Send email via AWS SES API."""
        try:
            # AWS SES requires boto3, but we'll use HTTP API for now
            # This is a simplified version - in production, use boto3
            credentials = json.loads(self.decrypt_credentials(account.get("credentials_encrypted", "{}")))
            aws_access_key = credentials.get("access_key_id")
            aws_secret_key = credentials.get("secret_access_key")
            aws_region = credentials.get("region", "us-east-1")
            from_email = account.get("email")
            
            # Note: AWS SES API requires AWS Signature Version 4 signing
            # For production, use boto3 library instead
            logger.warning("AWS SES direct API not fully implemented. Use boto3 for production.")
            return {"success": False, "error": "AWS SES requires boto3 library"}
            
        except Exception as e:
            logger.error(f"Error sending email via AWS SES: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def send_email(
        self,
        account_id: Optional[str] = None,
        to_emails: List[str] = None,
        subject: str = "",
        body_text: str = "",
        body_html: Optional[str] = None,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Send email using configured account."""
        # Get account
        if account_id:
            account = self.get_email_account(account_id)
        else:
            account = self.get_default_email_account()
        
        if not account:
            return {"success": False, "error": "No email account configured"}
        
        if not account.get("is_active"):
            return {"success": False, "error": "Email account is not active"}
        
        provider = account.get("provider", "smtp")
        
        # Route to appropriate provider
        if provider == "smtp":
            return self.send_email_smtp(
                account, to_emails, subject, body_text, body_html,
                cc_emails, bcc_emails, reply_to, attachments
            )
        elif provider == "sendgrid":
            return self.send_email_sendgrid(
                account, to_emails, subject, body_text, body_html,
                cc_emails, bcc_emails, reply_to, attachments
            )
        elif provider == "ses":
            return self.send_email_ses(
                account, to_emails, subject, body_text, body_html,
                cc_emails, bcc_emails, reply_to, attachments
            )
        else:
            return {"success": False, "error": f"Unsupported provider: {provider}"}
    
    def test_email_connection(self, account_id: str) -> Dict[str, Any]:
        """Test email account connection."""
        account = self.get_email_account(account_id)
        if not account:
            return {"success": False, "error": "Email account not found"}
        
        provider = account.get("provider", "smtp")
        
        if provider == "smtp":
            try:
                smtp_host = account.get("smtp_host")
                smtp_port = account.get("smtp_port", 587)
                smtp_username = account.get("smtp_username")
                smtp_password = self.decrypt_credentials(account.get("smtp_password_encrypted", ""))
                
                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    server.starttls()
                    server.login(smtp_username, smtp_password)
                
                return {"success": True, "message": "SMTP connection successful"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        elif provider == "sendgrid":
            try:
                api_key = self.decrypt_credentials(account.get("api_key_encrypted", ""))
                response = httpx.get(
                    "https://api.sendgrid.com/v3/user/profile",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10.0
                )
                response.raise_for_status()
                return {"success": True, "message": "SendGrid API connection successful"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        else:
            return {"success": False, "error": f"Test not implemented for provider: {provider}"}
    
    def parse_email(self, raw_email: str) -> Dict[str, Any]:
        """Parse raw email content."""
        try:
            msg = email.message_from_string(raw_email)
            
            # Decode headers
            subject = self._decode_header(msg.get("Subject", ""))
            from_email = self._extract_email(msg.get("From", ""))
            to_emails = [self._extract_email(addr) for addr in msg.get_all("To", [])]
            cc_emails = [self._extract_email(addr) for addr in msg.get_all("Cc", [])]
            message_id = msg.get("Message-ID", "")
            in_reply_to = msg.get("In-Reply-To", "")
            references = msg.get("References", "")
            
            # Extract body
            body_text = ""
            body_html = ""
            
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        body_text = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                    elif content_type == "text/html":
                        body_html = part.get_payload(decode=True).decode("utf-8", errors="ignore")
            else:
                content_type = msg.get_content_type()
                payload = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
                if content_type == "text/html":
                    body_html = payload
                else:
                    body_text = payload
            
            # Extract attachments
            attachments = []
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_disposition() == "attachment":
                        filename = part.get_filename()
                        if filename:
                            attachments.append({
                                "filename": self._decode_header(filename),
                                "content": part.get_payload(decode=True),
                                "content_type": part.get_content_type()
                            })
            
            # Extract spam-related headers
            headers = {}
            spam_headers = [
                "List-Unsubscribe",
                "List-Unsubscribe-Post",
                "X-Spam-Score",
                "X-Spam-Status",
                "X-Spam-Flag",
                "Precedence",
                "X-Mailer",
                "X-Auto-Response-Suppress",
            ]
            for header_name in spam_headers:
                header_value = msg.get(header_name)
                if header_value:
                    headers[header_name] = header_value
            
            return {
                "subject": subject,
                "from_email": from_email,
                "to_emails": to_emails,
                "cc_emails": cc_emails,
                "message_id": message_id,
                "in_reply_to": in_reply_to,
                "references": references,
                "body_text": body_text,
                "body_html": body_html,
                "attachments": attachments,
                "date": msg.get("Date", ""),
                "_headers": headers  # Internal headers for spam detection
            }
        except Exception as e:
            logger.error(f"Error parsing email: {e}", exc_info=True)
            return {}
    
    def _decode_header(self, header: str) -> str:
        """Decode email header."""
        try:
            decoded_parts = decode_header(header)
            decoded_string = ""
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    decoded_string += part.decode(encoding or "utf-8", errors="ignore")
                else:
                    decoded_string += part
            return decoded_string
        except Exception:
            return header
    
    def _extract_email(self, address_string: str) -> str:
        """Extract email address from 'Name <email@domain.com>' format."""
        match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', address_string)
        return match.group(0) if match else address_string.strip()
    
    def _get_imap_settings(self, account: Dict) -> Dict[str, Any]:
        """Get IMAP settings for an email account, auto-detecting for common providers."""
        email_addr = account.get("email", "").lower()
        imap_host = account.get("imap_host")
        imap_port = account.get("imap_port")
        
        # Auto-detect IMAP settings for common providers
        if not imap_host:
            if "@gmail.com" in email_addr:
                imap_host = "imap.gmail.com"
                imap_port = 993
            elif "@outlook.com" in email_addr or "@hotmail.com" in email_addr or "@office365.com" in email_addr:
                imap_host = "outlook.office365.com"
                imap_port = 993
            else:
                # Try to use SMTP host as fallback (some providers use same host)
                imap_host = account.get("smtp_host")
                imap_port = 993  # Default IMAP SSL port
        
        # Default port if not set
        if not imap_port:
            imap_port = 993
        
        return {
            "host": imap_host,
            "port": imap_port,
            "use_ssl": True  # Most modern IMAP servers use SSL
        }
    
    def _parse_email_from_imap(self, raw_email: bytes) -> Dict[str, Any]:
        """Parse email from IMAP raw bytes."""
        try:
            msg = email.message_from_bytes(raw_email)
            return self.parse_email(msg.as_string())
        except Exception as e:
            logger.error(f"Error parsing email from IMAP: {e}", exc_info=True)
            return {}
    
    def fetch_emails_imap(
        self,
        account: Dict,
        since_date: Optional[datetime] = None,
        max_emails: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Fetch emails from IMAP server.
        
        Args:
            account: Email account dictionary
            since_date: Only fetch emails after this date (default: last_polled_at or 7 days ago)
            max_emails: Maximum number of emails to fetch per call
        
        Returns:
            List of parsed email dictionaries
        """
        try:
            imap_settings = self._get_imap_settings(account)
            if not imap_settings.get("host"):
                logger.error(f"No IMAP host configured for account {account.get('email')}")
                return []
            
            email_addr = account.get("email")
            smtp_username = account.get("smtp_username") or email_addr
            smtp_password = self.decrypt_credentials(account.get("smtp_password_encrypted", ""))
            
            if not smtp_password:
                logger.error(f"No password configured for IMAP account {email_addr}")
                return []
            
            # Connect to IMAP server
            if imap_settings.get("use_ssl"):
                mail = imaplib.IMAP4_SSL(imap_settings["host"], imap_settings["port"])
            else:
                mail = imaplib.IMAP4(imap_settings["host"], imap_settings["port"])
            
            logged_in = False
            selected = False
            try:
                # Login
                mail.login(smtp_username, smtp_password)
                logged_in = True
                
                # Select inbox
                mail.select("INBOX")
                selected = True
                
                # Build search criteria
                search_criteria = "ALL"
                if since_date:
                    # Format date for IMAP search: DD-MMM-YYYY
                    date_str = since_date.strftime("%d-%b-%Y")
                    search_criteria = f'(SINCE "{date_str}")'
                
                # Search for emails
                status, messages = mail.search(None, search_criteria)
                if status != "OK":
                    logger.warning(f"IMAP search failed for account {email_addr}")
                    return []
                
                email_ids = messages[0].split()
                
                # Limit number of emails
                if len(email_ids) > max_emails:
                    email_ids = email_ids[-max_emails:]  # Get most recent emails
                
                fetched_emails = []
                
                # Fetch each email
                for email_id in reversed(email_ids):  # Process newest first
                    try:
                        status, msg_data = mail.fetch(email_id, "(RFC822)")
                        if status == "OK" and msg_data[0]:
                            raw_email = msg_data[0][1]
                            parsed = self._parse_email_from_imap(raw_email)
                            if parsed:
                                parsed["_imap_id"] = email_id.decode()  # Store for reference
                                fetched_emails.append(parsed)
                    except Exception as e:
                        logger.warning(f"Error fetching email {email_id}: {e}")
                        continue
                
                logger.info(f"Fetched {len(fetched_emails)} emails from {email_addr}")
                return fetched_emails
                
            finally:
                try:
                    if selected:
                        mail.close()
                    if logged_in:
                        mail.logout()
                except Exception:
                    pass
                
        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP error for account {account.get('email')}: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Error fetching emails via IMAP for {account.get('email')}: {e}", exc_info=True)
            return []
    
    def test_imap_connection(self, account_id: str) -> Dict[str, Any]:
        """Test IMAP connection for an email account."""
        account = self.get_email_account(account_id)
        if not account:
            return {"success": False, "error": "Email account not found"}
        
        try:
            imap_settings = self._get_imap_settings(account)
            if not imap_settings.get("host"):
                return {"success": False, "error": "No IMAP host configured or auto-detected"}
            
            email_addr = account.get("email")
            smtp_username = account.get("smtp_username") or email_addr
            smtp_password = self.decrypt_credentials(account.get("smtp_password_encrypted", ""))
            
            if not smtp_password:
                return {"success": False, "error": "No password configured"}
            
            # Connect to IMAP server
            if imap_settings.get("use_ssl"):
                mail = imaplib.IMAP4_SSL(imap_settings["host"], imap_settings["port"])
            else:
                mail = imaplib.IMAP4(imap_settings["host"], imap_settings["port"])
            
            logged_in = False
            selected = False
            try:
                mail.login(smtp_username, smtp_password)
                logged_in = True
                mail.select("INBOX")
                selected = True
                return {
                    "success": True,
                    "message": f"IMAP connection successful to {imap_settings['host']}:{imap_settings['port']}"
                }
            finally:
                try:
                    if selected:
                        mail.close()
                    if logged_in:
                        mail.logout()
                except Exception:
                    pass
                
        except imaplib.IMAP4.error as e:
            return {"success": False, "error": f"IMAP error: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Connection error: {str(e)}"}


# Global email service instance
email_service = EmailService()


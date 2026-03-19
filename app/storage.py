"""Supabase Storage operations for file attachments."""
from app.supabase_config import supabase, supabase_storage
from app.logger import setup_logger
from typing import Optional
from datetime import datetime
import uuid
import os

logger = setup_logger(__name__)

# Storage bucket name
ATTACHMENTS_BUCKET = "attachments"

# Maximum file size (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Allowed MIME types
ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf",
    "text/plain", "text/csv",
    "application/msword",  # .doc
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/vnd.ms-excel",  # .xls
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/zip", "application/x-zip-compressed",
    "video/mp4", "video/mpeg", "video/quicktime",
    "audio/mpeg", "audio/wav", "audio/mp3",
}


def get_storage_client():
    """Get Supabase Storage client with service role key (bypasses RLS)."""
    # Use storage client with service role key if available, otherwise fall back to regular client
    client = supabase_storage if supabase_storage is not None else supabase
    if client is None:
        logger.error("Supabase client not initialized")
        return None
    return client.storage


def upload_file(
    file_content: bytes,
    file_name: str,
    mime_type: str,
    ticket_id: str,
    user_id: str,
    message_id: Optional[str] = None,
) -> dict:
    """
    Upload a file to Supabase Storage and create attachment record.
    
    Args:
        file_content: File content as bytes
        file_name: Original file name
        mime_type: MIME type of the file
        ticket_id: Ticket ID this attachment belongs to
        user_id: User ID who uploaded the file
        message_id: Optional message ID this attachment belongs to
    
    Returns:
        dict: Attachment record with id, file_path, etc.
    """
    try:
        # Validate file size
        file_size = len(file_content)
        if file_size > MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / (1024 * 1024):.1f}MB")
        
        # Validate MIME type
        if mime_type not in ALLOWED_MIME_TYPES:
            raise ValueError(f"MIME type {mime_type} is not allowed")
        
        # Generate unique file path
        file_extension = os.path.splitext(file_name)[1]
        unique_file_name = f"{uuid.uuid4()}{file_extension}"
        storage_path = f"{ticket_id}/{unique_file_name}"
        
        # Upload to Supabase Storage
        storage = get_storage_client()
        if storage is None:
            raise RuntimeError("Storage client not available")
        
        # Upload file
        # Supabase Storage API expects file as bytes or file-like object
        upload_result = storage.from_(ATTACHMENTS_BUCKET).upload(
            path=storage_path,
            file=file_content,
            file_options={"content-type": mime_type, "upsert": "false"}
        )
        
        if upload_result:
            logger.info(f"File uploaded to storage: {storage_path}")
        else:
            raise RuntimeError("Failed to upload file to storage")
        
        # Create attachment record in database
        attachment_data = {
            "ticket_id": ticket_id,
            "message_id": message_id,
            "file_name": file_name,
            "file_path": storage_path,
            "file_size": file_size,
            "mime_type": mime_type,
            "uploaded_by": user_id,
            "created_at": datetime.now().isoformat(),
        }
        
        result = supabase.table("attachments").insert(attachment_data).execute()
        
        if not result.data:
            # If database insert fails, try to delete the uploaded file
            try:
                storage.from_(ATTACHMENTS_BUCKET).remove([storage_path])
            except Exception as e:
                logger.error(f"Failed to clean up uploaded file after DB insert failure: {e}")
            raise RuntimeError("Failed to create attachment record")
        
        attachment = result.data[0]
        logger.info(f"Attachment created: {attachment['id']}")
        
        return attachment
        
    except Exception as e:
        logger.error(f"Error uploading file: {e}", exc_info=True)
        raise


def download_file(attachment_id: str) -> tuple[bytes, dict]:
    """
    Download a file from Supabase Storage.
    
    Args:
        attachment_id: Attachment ID
    
    Returns:
        tuple: (file_content, attachment_metadata)
    """
    try:
        # Get attachment record
        result = supabase.table("attachments").select("*").eq("id", attachment_id).limit(1).execute()
        
        if not result.data:
            raise ValueError("Attachment not found")
        
        attachment = result.data[0]
        file_path = attachment["file_path"]
        
        # Download from Supabase Storage
        storage = get_storage_client()
        if storage is None:
            raise RuntimeError("Storage client not available")
        
        file_content = storage.from_(ATTACHMENTS_BUCKET).download(file_path)
        
        if file_content is None:
            raise RuntimeError("Failed to download file from storage")
        
        logger.info(f"File downloaded: {file_path}")
        
        return file_content, attachment
        
    except Exception as e:
        logger.error(f"Error downloading file: {e}", exc_info=True)
        raise


def delete_file(attachment_id: str) -> bool:
    """
    Delete a file from Supabase Storage and remove attachment record.
    
    Args:
        attachment_id: Attachment ID
    
    Returns:
        bool: True if successful
    """
    try:
        # Get attachment record
        result = supabase.table("attachments").select("*").eq("id", attachment_id).limit(1).execute()
        
        if not result.data:
            raise ValueError("Attachment not found")
        
        attachment = result.data[0]
        file_path = attachment["file_path"]
        
        # Delete from Supabase Storage
        storage = get_storage_client()
        if storage is None:
            raise RuntimeError("Storage client not available")
        
        storage.from_(ATTACHMENTS_BUCKET).remove([file_path])
        logger.info(f"File deleted from storage: {file_path}")
        
        # Delete attachment record
        supabase.table("attachments").delete().eq("id", attachment_id).execute()
        logger.info(f"Attachment record deleted: {attachment_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error deleting file: {e}", exc_info=True)
        raise


def list_attachments(ticket_id: str, message_id: Optional[str] = None) -> list:
    """
    List attachments for a ticket or message.
    
    Args:
        ticket_id: Ticket ID
        message_id: Optional message ID to filter by
    
    Returns:
        list: List of attachment records
    """
    try:
        query = supabase.table("attachments").select("*").eq("ticket_id", ticket_id)
        
        if message_id:
            query = query.eq("message_id", message_id)
        
        result = query.order("created_at", desc=True).execute()
        
        return result.data if result.data else []
        
    except Exception as e:
        logger.error(f"Error listing attachments: {e}", exc_info=True)
        raise


def get_public_url(file_path: str, expires_in: int = 3600) -> Optional[str]:
    """
    Get a public URL for a file (if bucket is public).
    
    Args:
        file_path: Storage path of the file
        expires_in: URL expiration time in seconds (default 1 hour)
    
    Returns:
        str: Public URL or None if bucket is private
    """
    try:
        storage = get_storage_client()
        if storage is None:
            return None
        
        # Try to get public URL
        url = storage.from_(ATTACHMENTS_BUCKET).get_public_url(file_path)
        return url
        
    except Exception as e:
        logger.warning(f"Could not get public URL for {file_path}: {e}")
        return None


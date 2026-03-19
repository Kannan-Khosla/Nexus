"""File attachment endpoints: upload, download, list, delete."""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse, Response
from typing import Optional
from datetime import datetime, timezone
from app.supabase_config import supabase
from app.logger import setup_logger
from app.dependencies import get_current_user
from app.storage import upload_file, download_file, delete_file, list_attachments
import io
import base64

logger = setup_logger(__name__)
router = APIRouter()

@router.post("/ticket/{ticket_id}/attachments")
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


@router.get("/ticket/{ticket_id}/attachments")
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


@router.get("/attachment/{attachment_id}")
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


@router.delete("/attachment/{attachment_id}")
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

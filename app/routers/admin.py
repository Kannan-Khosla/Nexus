"""Admin endpoints: ticket management, assignment, close, delete, trash, restore."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime, timezone
from app.supabase_config import supabase
from app.logger import setup_logger
from app.dependencies import get_current_user, get_current_admin, require_admin
from app.schemas import AdminReplyRequest, AssignAdminRequest, DeleteTicketsRequest, RestoreTicketsRequest

logger = setup_logger(__name__)
router = APIRouter()

@router.get("/admin/tickets")
def admin_get_all_tickets(
    search: str = Query(default=None, description="Search in subject and message content"),
    filter_status: str = Query(default=None, description="Filter by status (open, human_assigned, closed)"),
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
        if filter_status:
            query = query.eq("status", filter_status)
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


@router.get("/admin/tickets/assigned")
def get_assigned_tickets(
    search: str = Query(default=None, description="Search in subject and message content"),
    filter_status: str = Query(default=None, description="Filter by status (open, human_assigned, closed)"),
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
        if filter_status:
            query = query.eq("status", filter_status)
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


@router.post("/ticket/{ticket_id}/admin/reply")
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


@router.post("/admin/ticket/{ticket_id}/assign-admin")
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


@router.post("/admin/ticket/{ticket_id}/assign")
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


@router.post("/admin/ticket/{ticket_id}/close")
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


@router.post("/admin/tickets/delete")
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


@router.get("/admin/tickets/trash")
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


@router.post("/admin/tickets/restore")
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


@router.delete("/admin/tickets/trash")
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

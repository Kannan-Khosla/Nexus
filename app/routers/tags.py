"""Tags and categories endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone
from app.supabase_config import supabase
from app.logger import setup_logger
from app.dependencies import get_current_user, get_current_admin
from app.schemas import TagRequest, CategoryRequest, TicketTagsRequest, TicketCategoryRequest

logger = setup_logger(__name__)
router = APIRouter()

@router.post("/admin/tags")
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
        
        # Organization logic removed
        organization_id = None
        
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


@router.get("/admin/tags")
def list_tags(
    current_admin: dict = Depends(get_current_admin)
):
    """List all tags."""
    try:
        if supabase is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured",
            )
        
        result = (
            supabase.table("tags")
            .select("*")
            .order("name", desc=False)
            .execute()
        )
        
        return {"tags": result.data if result.data else []}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_tags: {e}", exc_info=True)
        raise


@router.put("/admin/tags/{tag_id}")
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
        

        # Organization check removed
        
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


@router.delete("/admin/tags/{tag_id}")
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

        # Organization check removed
        
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


@router.post("/ticket/{ticket_id}/tags")
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


@router.delete("/ticket/{ticket_id}/tags/{tag_id}")
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


@router.get("/ticket/{ticket_id}/tags")
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


@router.post("/admin/categories")
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
        

        # Organization logic removed
        organization_id = None
        
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


@router.get("/admin/categories")
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
        

        # Organization logic removed
        
        query = supabase.table("categories").select("*")
        # List all categories (global)
        query = query.is_("organization_id", "null")
        
        result = query.order("name", desc=False).execute()
        
        return {"categories": result.data if result.data else []}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_categories: {e}", exc_info=True)
        raise


@router.put("/admin/categories/{category_id}")
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
        
        # Organization check removed
        
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


@router.delete("/admin/categories/{category_id}")
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
        
        # Organization check removed
        
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


@router.put("/ticket/{ticket_id}/category")
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

"""SLA, priority, and time tracking endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime, timezone
from app.supabase_config import supabase
from app.logger import setup_logger
from app.dependencies import get_current_user, get_current_admin
from app.schemas import SLADefinitionRequest, UpdatePriorityRequest, TimeEntryRequest

logger = setup_logger(__name__)
router = APIRouter()

@router.post("/admin/slas")
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


@router.get("/admin/slas")
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


@router.post("/ticket/{ticket_id}/priority")
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


@router.get("/ticket/{ticket_id}/sla-status")
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


@router.post("/ticket/{ticket_id}/time-entry")
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


@router.get("/ticket/{ticket_id}/time-entries")
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
